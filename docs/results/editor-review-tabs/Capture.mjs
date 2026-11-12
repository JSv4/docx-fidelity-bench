import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

// Args: before run, after run, installed pinned Playwright module, output folder.
const beforeDir = resolve(process.argv[2]), afterDir = resolve(process.argv[3]), output = resolve(process.argv[5]);
const { chromium } = await import(pathToFileURL(resolve(process.argv[4])).href);
const read = async (folder, name) => JSON.parse(await readFile(resolve(folder, name), 'utf8'));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const before = await read(beforeDir, 'result.json'), after = await read(afterDir, 'result.json');
const observations = [await read(beforeDir, 'observations.json'), await read(afterDir, 'observations.json')];
const builds = [await read(beforeDir, 'build.json'), await read(afterDir, 'build.json')];
if (!before.summary.complete || !after.summary.complete || after.summary.passed !== 10
  || JSON.stringify(before.cases.map(c => c.id)) !== JSON.stringify(after.cases.map(c => c.id))
  || JSON.stringify(builds[0].harnessSources) !== JSON.stringify(builds[1].harnessSources)
  || builds[0].manifestSha256 !== builds[1].manifestSha256) throw new Error('Runs do not share a complete diagnostic contract');
await mkdir(output, { recursive: true });
const binding = { schema: 1, suite: after.suite, commits: [before.commit, after.commit],
  captures: [], sourceRuns: [] };
for (const folder of [beforeDir, afterDir]) {
  const files = {};
  for (const name of ['result.json', 'observations.json', 'build.json', 'input-validation.json'])
    files[name] = sha(await readFile(resolve(folder, name)));
  binding.sourceRuns.push(files);
}
const escape = text => text.replaceAll('&', '&amp;').replaceAll('<', '&lt;');
const executablePath = chromium.executablePath();
const browser = await chromium.launch({ headless: true, executablePath });
binding.captureBrowser = { version: browser.version(), executableSha256: sha(await readFile(executablePath)) };
binding.captureScriptSha256 = sha(await readFile(new URL(import.meta.url)));
try {
  const context = await browser.newContext({ viewport: { width: 2540, height: 1200 }, offline: true });
  const page = await context.newPage();
  for (let i = 0; i < after.cases.length; i++) {
    const id = after.cases[i].id, panels = [], record = { id, observations: [] };
    for (const [index, folder] of [beforeDir, afterDir].entries()) {
      const observed = observations[index].cases[i];
      const png = await readFile(resolve(folder, id + '.png'));
      const saved = await readFile(resolve(folder, id + '.docx'));
      if (observed.id !== id || sha(png) !== observed.pngSha256 || sha(saved) !== observed.outputSha256)
        throw new Error('Observation binding changed: ' + id);
      const result = (index ? after : before).cases[i];
      record.observations.push({ inputSha256: observed.inputSha256, pngSha256: sha(png), outputSha256: sha(saved),
        checks: result.checks, passed: result.passed, pageErrors: observed.pageErrors });
      const nativeOutput = Object.fromEntries(result.checks.filter(check =>
        ['text', 'tabs', 'insertions', 'rangeMarkers'].includes(check.name)).map(check => [check.name, check.actual]));
      const fields = { badge: observed.badge, nativeOutput, selectedRevisionText: observed.targetText,
        pastedPlain: observed.copiedPlain, pastedRich: observed.richText, allRichRunsFormatted: observed.richFormatted };
      panels.push(`<section><h2>${index ? 'Candidate' : 'Baseline'} ${observations[index].commit.slice(0, 8)} — ${result.passed ? 'PASS' : 'FAIL'}</h2><pre>${escape(JSON.stringify(fields, null, 2))}</pre><img src="data:image/png;base64,${png.toString('base64')}"></section>`);
    }
    const html = '<!doctype html><meta charset="utf-8"><style>body{font:17px Arial;margin:16px;color:#14273b}h1{font-size:25px}main{display:flex;gap:12px}section{width:1250px;border:1px solid #bac7d5}h2,pre{margin:12px}pre{white-space:pre-wrap}img{display:block;width:100%}</style><h1>' + id + '</h1><p>Actual shipped-ribbon browser actions, real clipboard, independently checked saved OOXML. Unweighted diagnostic; no PDF/redline score.</p><main>' + panels.join('') + '</main>';
    const htmlFile = resolve(afterDir, id + '-sheet.html');
    await writeFile(htmlFile, html);
    await page.goto(pathToFileURL(htmlFile).href);
    const sheet = await page.screenshot({ path: resolve(output, id + '.png'), fullPage: true });
    record.htmlSha256 = sha(Buffer.from(html)); record.pngSha256 = sha(sheet);
    binding.captures.push(record);
  }
} finally { await browser.close(); }
await writeFile(resolve(output, 'capture.json'), JSON.stringify(binding, null, 2) + '\n');
