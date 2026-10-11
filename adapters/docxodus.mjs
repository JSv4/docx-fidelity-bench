// Original protocol adapter. The renderer is separately built and provisioned.
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

let source = '';
for await (const chunk of process.stdin) source += chunk;
const request = JSON.parse(source);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
try {
  if (request.protocol !== 1) throw new Error('Unknown request protocol');
  const modulePath = process.env.DOCXODUS_EXPORT_MODULE;
  const root = process.env.DOCXODUS_SOURCE_ROOT;
  if (!modulePath || !root) throw new Error('Set DOCXODUS_EXPORT_MODULE and DOCXODUS_SOURCE_ROOT to a clean pinned build');
  const git = (...args) => {
    const result = spawnSync('git', ['-C', root, ...args], { encoding: 'utf8' });
    if (result.status !== 0) throw new Error(result.stderr);
    return result.stdout.trim();
  };
  const commit = git('rev-parse', 'HEAD');
  if (commit !== request.candidate || git('status', '--porcelain', '--untracked-files=no')) throw new Error('Candidate identity or clean source check failed');
  const build = JSON.parse(await readFile(resolve(root, '.docx-bench-build.json'), 'utf8'));
  if (build.schema !== 1 || build.commit !== commit || build.tree !== git('rev-parse', 'HEAD^{tree}') || build.node !== process.version || resolve(modulePath) !== resolve(root, 'npm-export/dist/index.js')) throw new Error('Build identity is stale or does not match the requested renderer');
  if (build.recipeSha256 !== hash(await readFile(new URL('../bench/build.py', import.meta.url)))) throw new Error('Build recipe changed; rebuild the renderer');
  for (const [name, digest] of Object.entries(build.files)) {
    if (hash(await readFile(resolve(root, name))) !== digest) throw new Error('Build artifact digest mismatch: ' + name);
  }
  const { convertDocxToPdf, checkExportEnvironment } = await import(pathToFileURL(modulePath));
  const environment = await checkExportEnvironment();
  if (!environment.ok) {
    const error = new Error(JSON.stringify(environment.findings));
    error.code = 'ENVIRONMENT_INELIGIBLE';
    throw error;
  }
  const bytes = await readFile(request.input);
  if (hash(bytes) !== request.inputSha256) throw new Error('Input digest mismatch');
  const result = await convertDocxToPdf(new Uint8Array(bytes), {
    reviewProfile: request.profile.review,
    commentProfile: request.profile.comments,
    timeoutMs: request.timeoutMs,
    fontDirectories: request.fontDirectories,
    strictFonts: true,
  });
  const observed = result.renderReport.environment?.observed;
  if (result.renderReport.environment?.verification !== 'nodeVerified' || result.renderReport.environment?.fidelityTier !== 'releaseBaselined' || !observed?.browserBuild) {
    const error = new Error('Production output is not from the verified pinned export runtime');
    error.code = 'ENVIRONMENT_INELIGIBLE';
    throw error;
  }
  const runtime = Object.fromEntries(['playwrightVersion', 'browserProduct', 'browserBuild', 'executableSha256', 'launchFlags', 'operatingSystem', 'architecture'].map(key => [key, observed[key]]));
  await writeFile(request.output, result.pdf, { flag: 'wx' });
  await writeFile(request.report, JSON.stringify(result.renderReport, null, 2) + '\n', { flag: 'wx' });
  process.stdout.write(JSON.stringify({ protocol: 1, status: 'ok', pdfSha256: hash(result.pdf), renderer: { name: 'docxodus', commit, node: process.version, runtime, build }, productionReport: request.report }));
} catch (error) {
  process.stdout.write(JSON.stringify({ protocol: 1, status: error.code === 'ENVIRONMENT_INELIGIBLE' ? 'unmeasured' : 'failed', error: { code: error.code ?? 'ADAPTER_FAILURE', message: error.message } }));
}
