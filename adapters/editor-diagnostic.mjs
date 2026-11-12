// Observe shipped browser UI and real clipboard actions; no renderer test harness is loaded.
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const source = resolve(process.argv[2]), registryPath = resolve(process.argv[3]), output = resolve(process.argv[4]);
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const registry = JSON.parse(await readFile(registryPath, 'utf8'));
const build = JSON.parse(await readFile(resolve(output, 'build.json'), 'utf8'));
const { chromium } = await import(pathToFileURL(resolve(source, 'npm/node_modules/playwright/index.mjs')).href);
const sha = data => createHash('sha256').update(data).digest('hex');
const framework = resolve(source, 'npm/dist/wasm/_framework');
const server = createServer(async (req, res) => {
  try {
    const name = new URL(req.url, 'http://localhost').pathname;
    let file;
    if (name === '/') file = resolve(root, 'docs/editor/host.html');
    else if (name === '/editor.bundle.js') file = resolve(source, 'npm/dist/editor.bundle.js');
    else if (name.startsWith('/_framework/')) {
      file = resolve(framework, name.slice('/_framework/'.length));
      if (!file.startsWith(framework + sep)) throw new Error('Invalid asset path');
    } else { res.writeHead(404); res.end(); return; }
    res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : file.endsWith('.wasm') ? 'application/wasm' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream');
    res.end(await readFile(file));
  } catch { res.writeHead(404); res.end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const url = `http://127.0.0.1:${server.address().port}`;
let browser;
const result = { schema: 1, suite: registry.suite, commit: build.commit, browser: null, richClipboardIsolation: 'separate-document', cases: [] };
try {
  const executablePath = chromium.executablePath();
  browser = await chromium.launch({ headless: true, executablePath });
  result.browser = browser.version();
  result.browserExecutableSha256 = sha(await readFile(executablePath));
  for (const item of registry.cases) {
    const page = await browser.newPage({ viewport: { width: 1250, height: 950 } });
    const record = { id: item.id, action: item.action, inputSha256: item.sha256, status: 'unmeasured', pageErrors: [] };
    page.on('pageerror', error => record.pageErrors.push(String(error)));
    try {
      await page.goto(url + (item.action === 'copy-classes' ? '/?classes=1' : '/'));
      await page.waitForFunction(() => !!window.editorDiagnostic, { timeout: 60000 });
      const bytes = await readFile(resolve(root, item.input));
      await page.evaluate(({ bytes, name, commit }) => {
        window.editorDiagnostic.ribbon.open(new Uint8Array(bytes), name + '.docx');
        document.getElementById('label').textContent = `${name} — Docxodus ${commit.slice(0, 8)}`;
      }, { bytes: [...bytes], name: item.id, commit: build.commit });
      await page.locator('[data-tab="review"]').click();
      if (item.action === 'revision-target') {
        record.targetText = await page.evaluate(() => {
          const editor = window.editorDiagnostic.ribbon.editor;
          const mark = editor.revisionElements()[0];
          const entry = editor.revisionAt(mark.cloneNode(true));
          if (entry) editor.acceptRevision(entry.id);
          return entry?.text ?? null;
        });
      } else if (item.action === 'caret') {
        await page.evaluate(() => {
          const p = window.editorDiagnostic.ribbon.surface.querySelector('[data-anchor][contenteditable="true"]');
          p.focus();
          const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
          for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            const start = node.textContent.indexOf('1.2');
            if (start >= 0) { window.getSelection().collapse(node, start + 3); return; }
          }
          throw new Error('Fixture prefix was not rendered');
        });
        await page.keyboard.press('ArrowRight');
        await page.keyboard.insertText('X');
        await page.evaluate(() => document.activeElement.blur());
      } else if (item.action.startsWith('copy')) {
        await page.evaluate(() => {
          const p = window.editorDiagnostic.ribbon.surface.querySelector('[data-anchor][contenteditable="true"]');
          p.focus();
          const selection = window.getSelection(), range = document.createRange();
          range.selectNodeContents(p);
          selection.removeAllRanges(); selection.addRange(range);
        });
        await page.keyboard.press('Control+c');
        await page.locator('#paste-plain').focus();
        await page.keyboard.press('Control+v');
        record.copiedPlain = await page.locator('#paste-plain').inputValue();
        const richTarget = page.frameLocator('#paste-rich').locator('#target');
        await richTarget.focus();
        await page.keyboard.press('Control+v');
        Object.assign(record, await richTarget.evaluate(target => {
          const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT), richRuns = [];
          for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            if (!node.textContent) continue;
            const style = getComputedStyle(node.parentElement);
            richRuns.push({ text: node.textContent, weight: style.fontWeight, style: style.fontStyle });
          }
          return { richText: target.textContent.replace(/\u00a0/g, ' '), richRuns,
            richFormatted: richRuns.length > 0 && richRuns.every(run => Number(run.weight) >= 600 && run.style === 'italic') };
        }));
      }
      record.badge = await page.locator('[data-dxr="revcount"]').textContent();
      const saved = Buffer.from(await page.evaluate(() => [...window.editorDiagnostic.ribbon.editor.save()]));
      await writeFile(resolve(output, item.id + '.docx'), saved);
      record.outputSha256 = sha(saved);
      record.status = 'observed';
    } catch (error) { record.error = String(error); }
    const png = await page.screenshot({ path: resolve(output, item.id + '.png'), fullPage: true });
    record.pngSha256 = sha(png);
    result.cases.push(record);
    await page.close();
  }
} catch (error) { result.error = String(error); }
finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
  await writeFile(resolve(output, 'observations.json'), JSON.stringify(result, null, 2) + '\n');
}
