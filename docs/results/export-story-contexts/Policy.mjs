// Independent default-warning/strict-policy diagnostics for original authored inputs.
// This does not change the benchmark adapter or its PDF scoring contract.
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const [sourceArg, manifestArg, captureArg, environmentArg, rulesArg, outputArg] = process.argv.slice(2);
if (!outputArg) throw new Error('Usage: Policy.mjs SOURCE MANIFEST CAPTURE_DIR ENVIRONMENT RULES OUTPUT_JSON');
const source = resolve(sourceArg), captureDir = resolve(captureArg);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const json = async path => JSON.parse(await readFile(path, 'utf8'));
const git = (...args) => {
  const result = spawnSync('git', ['-C', source, ...args], { encoding: 'utf8' });
  if (result.status) throw new Error(result.stderr);
  return result.stdout.trim();
};
if (git('status', '--porcelain', '--untracked-files=no')) throw new Error('Dirty tracked renderer source');
const buildPath = resolve(source, '.docx-bench-build.json');
const build = await json(buildPath), commit = git('rev-parse', 'HEAD');
if (build.commit !== commit || build.tree !== git('rev-parse', 'HEAD^{tree}')) throw new Error('Stale build identity');
for (const [name, digest] of Object.entries(build.files)) {
  if (hash(await readFile(resolve(source, name))) !== digest) throw new Error(`Changed build asset: ${name}`);
}
const manifest = await json(manifestArg), captured = await json(resolve(captureDir, 'capture.json'));
const rules = await json(rulesArg), environment = await json(environmentArg);
const fontFiles = [];
for (const [name, declaration] of Object.entries(environment.contract.fonts)) {
  const matches = [];
  for (const folder of environment.fontDirectories) {
    try { matches.push({ path: resolve(folder, name), sha256: hash(await readFile(resolve(folder, name))) }); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  if (matches.length !== 1 || matches[0].sha256 !== declaration.sha256) throw new Error('Changed or ambiguous font: ' + name);
  fontFiles.push({ name, ...declaration });
}
const verifyFonts = report => {
  if (!Array.isArray(report.fonts) || !report.fonts.length) throw new Error('Missing resolved font evidence');
  for (const font of report.fonts) {
    if (!fontFiles.some(file => file.sha256 === font.fileSha256 && file.family === font.resolvedFamily)
        || !font.verified || font.faceMatch !== 'exact' || font.source !== 'configured'
        || font.glyphCoverage !== 'complete') throw new Error('Font report differs from pinned files');
  }
  return report.fonts.map(({ resolvedFamily, resolvedFace, fileSha256 }) => ({ resolvedFamily, resolvedFace, fileSha256 }));
};
if (captured.candidate !== commit || captured.buildIdentitySha256 !== hash(await readFile(buildPath))
    || captured.manifestSha256 !== hash(await readFile(manifestArg))) throw new Error('Default capture has a different source or contract');
if (JSON.stringify(captured.fontContract) !== JSON.stringify(environment.contract.fonts)) throw new Error('Changed font contract');
const inputs = new Map(manifest.cases.map(item => [item.id, item]));
const defaults = new Map(captured.cases.map(item => [item.id, item]));
if (rules.schema !== 1 || new Set(rules.cases.map(item => item.id)).size !== rules.cases.length) throw new Error('Invalid policy cases');
const { renderDocxArtifacts } = await import(pathToFileURL(resolve(source, 'npm-export/dist/index.js')));
const { chromium } = createRequire(resolve(source, 'npm-export/package.json'))('playwright-core');
const browserPath = process.env.DOCXODUS_CHROMIUM_PATH || '/opt/google/chrome/chrome';
const browser = await chromium.launch({ executablePath: browserPath, chromiumSandbox: true });
const record = { schema: 1, status: 'unscored-warning-and-strict-policy-diagnostics', candidate: commit,
  sourceTree: build.tree, buildIdentitySha256: captured.buildIdentitySha256,
  manifestSha256: captured.manifestSha256, rulesSha256: hash(await readFile(rulesArg)),
  browserVersion: browser.version(), executableSha256: hash(await readFile(browserPath)), sandbox: true,
  fontContract: environment.contract.fonts, verifiedFontFiles: fontFiles,
  captureToolSha256: hash(await readFile(fileURLToPath(import.meta.url))),
  note: 'Default PDF content is checked separately. These assertions inspect declared warning counts and strict-policy outcomes; they produce no fidelity score.', cases: [] };
try {
  if (record.browserVersion !== captured.browserVersion || record.executableSha256 !== captured.executableSha256)
    throw new Error('Strict-policy browser differs from the default capture');
  for (const rule of rules.cases) {
    const input = inputs.get(rule.id), baseline = defaults.get(rule.id);
    if (!input || !baseline || !['delivered', 'rejected'].includes(rule.strict)
        || !Number.isInteger(rule.warningCount) || rule.warningCount < 0) throw new Error('Unknown or invalid policy input');
    const bytes = await readFile(resolve(input.input));
    if (hash(bytes) !== input.sha256 || baseline.inputSha256 !== input.sha256) throw new Error('Changed input: ' + rule.id);
    const item = { id: rule.id, inputSha256: input.sha256, expectedWarning: rule.warning,
      expectedWarningCount: rule.warningCount, expectedStrict: rule.strict, defaultStatus: baseline.status };
    if (baseline.status === 'delivered') {
      const reportBytes = await readFile(resolve(captureDir, rule.id, 'production.json'));
      if (hash(reportBytes) !== baseline.renderReportSha256) throw new Error('Changed default report: ' + rule.id);
      item.defaultRenderReportSha256 = baseline.renderReportSha256;
      const report = JSON.parse(reportBytes.toString('utf8'));
      item.defaultVerifiedFonts = verifyFonts(report);
      item.warningCodes = report.warnings.map(warning => warning.code);
      item.warningCheckPassed = item.warningCodes.length === rule.warningCount
        && item.warningCodes.every(code => code === rule.warning);
    } else item.warningCheckPassed = false;
    try {
      const result = await renderDocxArtifacts(new Uint8Array(bytes), { browser, outputs: ['pdf'],
        reviewProfile: input.profile.review, commentProfile: input.profile.comments,
        timeoutMs: 120000, strictFonts: true, fontDirectories: environment.fontDirectories,
        unsupportedContent: 'strict' });
      await writeFile(resolve(captureDir, rule.id, 'strict.pdf'), result.pdf);
      item.strictResult = { status: 'delivered', pages: result.pageCount, pdfSha256: hash(result.pdf),
        verifiedFonts: verifyFonts(result.renderReport) };
      item.strictCheckPassed = rule.strict === 'delivered';
    } catch (error) {
      item.strictResult = { status: 'rejected', code: error.code, phase: error.phase, message: error.message };
      item.strictCheckPassed = rule.strict === 'rejected' && error.code === 'resource_policy_failure'
        && error.phase === 'output_verification';
    }
    item.passed = item.warningCheckPassed && item.strictCheckPassed;
    record.cases.push(item);
    await writeFile(outputArg, JSON.stringify(record, null, 2) + '\n');
    process.stdout.write(`${rule.id}: ${item.passed ? 'pass' : 'fail'}\n`);
  }
} finally { await browser.close(); }
