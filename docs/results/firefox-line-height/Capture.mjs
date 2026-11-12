// Source-bound browser observation of the PDF-track #1424 reproducer/control pair.
// Usage: node Capture.mjs SOURCE FULL_SHA OUTPUT (after bench build-docxodus).
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { resolve, dirname, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const source = resolve(process.argv[2]), commit = process.argv[3], output = resolve(process.argv[4]);
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const json = async path => JSON.parse(await readFile(path, 'utf8'));
const run = (exe, args) => execFileSync(exe, args, { encoding: 'utf8' }).trim();
const git = (...args) => run('git', ['-C', source, ...args]);
const production = await json(resolve(source, '.docx-bench-build.json'));
const manifest = await json(resolve(root, 'fixtures/manifest.json'));
const cases = manifest.cases.filter(c => c.id.startsWith('paragraph-firefox-'));
if (cases.length !== 2) throw new Error('Expected one reproducer and one control');
const verify = async () => {
  if (!/^[0-9a-f]{40}$/.test(commit) || git('rev-parse', 'HEAD') !== commit || production.commit !== commit
      || git('status', '--porcelain', '--untracked-files=no') || git('rev-parse', 'HEAD^{tree}') !== production.tree
      || production.recipeSha256 !== sha(await readFile(resolve(root, 'bench/build.py'))))
    throw new Error('Source/build identity changed');
  const assets = await json(resolve(source, 'npm/dist/export-assets.json'));
  for (const [name, hash] of Object.entries(production.files))
    if (sha(await readFile(resolve(source, name))) !== hash) throw new Error('Build artifact changed: ' + name);
  for (const asset of assets.assets)
    if (sha(await readFile(resolve(source, 'npm/dist', asset.path))) !== asset.sha256)
      throw new Error('Runtime changed: ' + asset.path);
  for (const item of cases)
    if (sha(await readFile(resolve(root, item.input))) !== item.sha256) throw new Error('Input changed');
};
await verify();
run('npm', ['--prefix', resolve(source, 'npm'), 'run', 'build:editor-bundle']);
const bundle = resolve(source, 'npm/dist/editor.bundle.js');
const bundleHash = sha(await readFile(bundle));
await mkdir(output, { recursive: false });
const { chromium, firefox } = await import(pathToFileURL(resolve(source, 'npm/node_modules/playwright/index.mjs')).href);
const framework = resolve(source, 'npm/dist/wasm/_framework');
const server = createServer(async (req, res) => {
  try {
    const path = new URL(req.url, 'http://localhost').pathname;
    let file;
    if (path === '/') file = resolve(root, 'docs/editor/host.html');
    else if (path === '/editor.bundle.js') file = bundle;
    else if (path.startsWith('/_framework/')) {
      file = resolve(framework, path.slice('/_framework/'.length));
      if (!file.startsWith(framework + sep)) throw new Error('Invalid runtime path');
    } else { res.writeHead(404).end(); return; }
    res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : file.endsWith('.wasm') ? 'application/wasm' : 'text/html');
    res.end(await readFile(file));
  } catch { res.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const font = run('fc-match', ['-f', '%{file}', 'Liberation Serif']);
const result = { schema: 1, commit, production, editorBundleSha256: bundleHash,
  scriptSha256: sha(await readFile(fileURLToPath(import.meta.url))),
  hostSha256: sha(await readFile(resolve(root, 'docs/editor/host.html'))),
  manifestSha256: sha(await readFile(resolve(root, 'fixtures/manifest.json'))),
  font: { path: font, sha256: sha(await readFile(font)) },
  scope: 'Browser line geometry, not a PDF fidelity score or Word observation', browsers: [] };
try {
  for (const [name, type] of Object.entries({ chromium, firefox })) {
    const executablePath = name === 'chromium' && process.env.DOCXODUS_CHROMIUM_PATH || type.executablePath();
    const browser = await type.launch({ headless: true, executablePath });
    const record = { name, version: browser.version(), executableSha256: sha(await readFile(executablePath)), cases: [] };
    try {
      for (const item of cases) {
        const page = await browser.newPage({ viewport: { width: 1100, height: 1400 } });
        const errors = [];
        page.on('pageerror', e => errors.push(String(e)));
        await page.goto(`http://127.0.0.1:${server.address().port}/`);
        await page.waitForFunction(() => !!window.editorDiagnostic, { timeout: 90000 });
        await page.evaluate(async ({ bytes, label }) => {
          document.getElementById('label').textContent = label;
          document.getElementById('host').style.height = '1200px';
          document.querySelectorAll('textarea, #paste-rich').forEach(e => e.remove());
          window.editorDiagnostic.ribbon.open(new Uint8Array(bytes), 'pine.docx');
          await window.editorDiagnostic.ribbon.editor.setPaginated(true);
          await document.fonts.ready;
        }, { bytes: [...await readFile(resolve(root, item.input))], label: `${item.id} | ${name} | ${commit.slice(0, 12)}` });
        const observed = await page.locator('#pagination-container .page-content').evaluateAll(pages => {
          const paragraphs = pages.flatMap(p => [...p.querySelectorAll('p')]);
          const canvas = document.createElement('canvas').getContext('2d');
          return paragraphs.map(p => {
            const boxes = [], walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
            for (let n = walker.nextNode(); n; n = walker.nextNode()) {
              if (!n.textContent.trim()) continue;
              const range = document.createRange(); range.selectNodeContents(n);
              const rects = [...range.getClientRects()].filter(r => r.width > 0);
              if (!rects.length) continue;
              if (rects.length !== 1) throw new Error('Fixture text unexpectedly wrapped');
              const style = getComputedStyle(n.parentElement);
              canvas.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
              const metrics = canvas.measureText(n.textContent);
              const marker = document.createElement('span');
              marker.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline;margin:0;padding:0;border:0';
              n.after(marker);
              const baseline = marker.getBoundingClientRect().top;
              const measured = range.getBoundingClientRect();
              marker.remove();
              const r = rects[0];
              if (['top', 'left', 'width', 'height'].some(key => Math.abs(measured[key] - r[key]) > 1 / 64))
                throw new Error('Baseline marker moved the text it measures');
              boxes.push({ text: n.textContent, top: baseline - metrics.actualBoundingBoxAscent,
                bottom: baseline + metrics.actualBoundingBoxDescent, left: r.left, right: r.right,
                fontBoxTop: r.top, fontBoxBottom: r.bottom });
            }
            return { text: p.innerText, fontSize: getComputedStyle(p).fontSize, lineHeight: getComputedStyle(p).lineHeight, boxes };
          });
        });
        const boxes = observed.flatMap(p => p.boxes), overlaps = [];
        const tokens = {};
        for (const word of observed.map(p => p.text).join(' ').split(/[\s\u200e]+/).filter(Boolean))
          tokens[word] = (tokens[word] || 0) + 1;
        const inventory = Object.fromEntries(Object.entries(tokens).sort(([a], [b]) => a.localeCompare(b)));
        const completeText = Object.keys(inventory).length === Object.keys(item.tokens).length
          && Object.entries(item.tokens).every(([word, count]) => inventory[word] === count);
        const visibleLines = boxes.length === 7 && boxes.every(b =>
          [b.top, b.bottom, b.left, b.right].every(Number.isFinite) && b.bottom > b.top && b.right > b.left);
        for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
          const a = boxes[i], b = boxes[j];
          if (Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1
              && Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1) overlaps.push([a.text, b.text]);
        }
        const png = await page.screenshot({ path: resolve(output, `${name}-${item.id}.png`), fullPage: true });
        record.cases.push({ id: item.id, inputSha256: item.sha256, observed, inventory, completeText, visibleLines, overlaps, errors,
          passed: completeText && visibleLines && overlaps.length === 0 && errors.length === 0, pngSha256: sha(png) });
        await page.close();
      }
    } finally { await browser.close(); }
    result.browsers.push(record);
  }
  await verify();
  if (sha(await readFile(bundle)) !== bundleHash) throw new Error('Editor runtime changed during observation');
} finally { await new Promise(resolve => server.close(resolve)); }
await writeFile(resolve(output, 'capture.json'), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result.browsers.map(b => ({ browser: b.name, cases: b.cases.map(c => ({ id: c.id, passed: c.passed, overlaps: c.overlaps })) }))));
process.exitCode = result.browsers.every(b => b.cases.every(c => c.passed)) ? 0 : 1;
