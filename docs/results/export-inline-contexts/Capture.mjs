// Capture original benchmark inputs through a separately built public renderer.
// This is explicitly diagnostic: a borrowed sandboxed system browser does not qualify
// as the benchmark adapter's pinned runtime. No score or reference registration is made.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [sourceArg, manifestArg, outputArg, environmentArg] = process.argv.slice(2);
if (!sourceArg || !manifestArg || !outputArg || !environmentArg) throw new Error('Usage: Capture.mjs SOURCE MANIFEST OUTPUT ENVIRONMENT');
const source = resolve(sourceArg), output = resolve(outputArg);
const git = (...args) => {
  const result = spawnSync('git', ['-C', source, ...args], { encoding: 'utf8' });
  if (result.status) throw new Error(result.stderr);
  return result.stdout.trim();
};
if (git('status', '--porcelain', '--untracked-files=no')) throw new Error('Tracked renderer sources must be clean');
const commit = git('rev-parse', 'HEAD');
const build = JSON.parse(await readFile(resolve(source, '.docx-bench-build.json'), 'utf8'));
if (build.commit !== commit || build.tree !== git('rev-parse', 'HEAD^{tree}')) throw new Error('Stale build identity');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
for (const [name, digest] of Object.entries(build.files)) {
  if (hash(await readFile(resolve(source, name))) !== digest) throw new Error(`Changed build asset: ${name}`);
}
const manifest = JSON.parse(await readFile(manifestArg, 'utf8'));
const environment = JSON.parse(await readFile(environmentArg, 'utf8'));
const { renderDocxArtifacts } = await import(pathToFileURL(resolve(source, 'npm-export/dist/index.js')));
const { chromium } = createRequire(resolve(source, 'npm-export/package.json'))('playwright-core');
const browserPath = process.env.DOCXODUS_CHROMIUM_PATH || '/opt/google/chrome/chrome';
const browser = await chromium.launch({ executablePath: browserPath, chromiumSandbox: true });
const record = {
  schema: 1, status: 'unscored-public-api-diagnostic', candidate: commit,
  sourceTree: build.tree, buildIdentitySha256: hash(await readFile(resolve(source, '.docx-bench-build.json'))),
  manifestSha256: hash(await readFile(manifestArg)), browserVersion: browser.version(),
  executableSha256: hash(await readFile(browserPath)), sandbox: true, fontContract: environment.contract.fonts,
  note: 'Borrowed system Chromium; no pinned-runtime qualification or rendering fidelity score.', cases: [],
};
await mkdir(output, { recursive: true });
await writeFile(resolve(output, 'manifest.json'), await readFile(manifestArg));
try {
  for (const entry of manifest.cases) {
    const folder = resolve(output, entry.id);
    await mkdir(folder, { recursive: true });
    const bytes = await readFile(resolve(entry.input));
    if (hash(bytes) !== entry.sha256) throw new Error(`Changed input: ${entry.id}`);
    const result = { id: entry.id, inputSha256: entry.sha256 };
    try {
      const delivered = await renderDocxArtifacts(new Uint8Array(bytes), {
        browser, outputs: ['pdf'], reviewProfile: entry.profile.review, commentProfile: entry.profile.comments,
        timeoutMs: 120000, strictFonts: true, fontDirectories: environment.fontDirectories,
      });
      await writeFile(resolve(folder, 'candidate.pdf'), delivered.pdf);
      const reportJson = JSON.stringify(delivered.renderReport, null, 2) + '\n';
      await writeFile(resolve(folder, 'production.json'), reportJson);
      Object.assign(result, { status: 'delivered', pages: delivered.pageCount, pdfSha256: hash(delivered.pdf),
        renderReportSha256: hash(reportJson), warningCodes: delivered.renderReport.warnings.map(warning => warning.code),
        unsupportedContentCount: delivered.renderReport.unsupportedContent.length });
    } catch (error) {
      Object.assign(result, { status: 'failed', code: error.code, phase: error.phase, message: error.message });
    }
    record.cases.push(result);
    await writeFile(resolve(output, 'capture.json'), JSON.stringify(record, null, 2) + '\n');
    process.stdout.write(`${entry.id}: ${result.status}\n`);
  }
} finally { await browser.close(); }
