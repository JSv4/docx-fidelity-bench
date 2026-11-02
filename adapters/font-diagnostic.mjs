// Public production exports only. Python independently inspects PDF faces and page content.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const [sourceArg, registryArg, outputArg] = process.argv.slice(2);
const source = resolve(sourceArg), output = resolve(outputArg);
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const registry = JSON.parse(await readFile(registryArg, 'utf8'));
const { renderDocxArtifacts } = await import(pathToFileURL(resolve(source, 'npm-export/dist/index.js')));
const { chromium } = await import(pathToFileURL(resolve(source, 'npm-export/node_modules/playwright-core/index.mjs')));
const sha = value => createHash('sha256').update(value).digest('hex');
const canonical = value => Array.isArray(value) ? value.map(canonical)
  : value !== null && typeof value === 'object'
    ? Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])])) : value;
const executablePath = process.env.DOCXODUS_CHROMIUM_PATH || chromium.executablePath();
const browser = await chromium.launch({ executablePath, chromiumSandbox: true });
const observations = { schema: 1, suite: registry.suite, browser: browser.version(),
  browserExecutableSha256: sha(await readFile(executablePath)), cases: [] };
try {
  for (const item of registry.cases) {
    const bytes = await readFile(resolve(root, item.input));
    if (sha(bytes) !== item.sha256) throw new Error('Input changed: ' + item.id);
    const folder = resolve(output, item.id); await mkdir(folder);
    const record = { id: item.id, inputSha256: sha(bytes), status: 'unmeasured' };
    try {
      const options = { browser, reviewProfile: 'final', commentProfile: 'hidden', strictFonts: false,
        fontDirectories: [process.env.BENCH_FONT_DIRECTORY || '/usr/share/fonts/truetype/liberation2'], timeoutMs: 120000 };
      const result = await renderDocxArtifacts(bytes, { ...options, outputs: ['html', 'pdf'] });
      const screen = await renderDocxArtifacts(bytes, { ...options, outputs: ['html'] });
      const artifacts = { 'candidate.pdf': result.pdf, 'candidate.html': result.html,
        'report.json': JSON.stringify(result.renderReport), 'page-map.json': JSON.stringify(canonical(result.pageMap)),
        'screen-report.json': JSON.stringify(screen.renderReport), 'screen.html': screen.html,
        'screen-page-map.json': JSON.stringify(canonical(screen.pageMap)) };
      record.artifacts = {};
      for (const [name, value] of Object.entries(artifacts)) {
        await writeFile(resolve(folder, name), value); record.artifacts[name] = sha(value);
      }
      const context = await browser.newContext({ javaScriptEnabled: false, serviceWorkers: 'block' });
      try {
        await context.route('**/*', route => route.abort());
        const page = await context.newPage();
        await page.setContent(screen.html); await page.evaluate(() => document.fonts.ready);
        record.htmlPages = await page.locator('.page-box').evaluateAll(pages => pages.map(p => ({
          text: p.innerText.replace(/\s+/g, ' ').trim(),
          number: Number(p.getAttribute('data-page-number')),
        })));
        record.htmlTextNodes = (await page.evaluate(() => {
          const nodes = [], walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
          for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            const parent = node.parentElement, page = parent?.closest('.page-box');
            if (!node.nodeValue?.trim() || !page || parent.closest('style,script')) continue;
            nodes.push({ text: node.nodeValue, pageNumber: Number(page.getAttribute('data-page-number')),
              anchorId: parent.closest('[data-source-anchor-id]')?.getAttribute('data-source-anchor-id'),
              fragmentId: parent.closest('[data-page-fragment-id]')?.getAttribute('data-page-fragment-id') });
          }
          return nodes;
        })).map(({ text, ...location }) => ({ ...location, textDigest: sha(text), textCodePointCount: [...text].length }));
      } finally { await context.close(); }
      record.status = 'observed';
    } catch (error) { record.error = String(error); }
    observations.cases.push(record);
  }
} finally { await browser.close(); }
await writeFile(resolve(output, 'observations.json'), JSON.stringify(observations, null, 2) + '\n');
