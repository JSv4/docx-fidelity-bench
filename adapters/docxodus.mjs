// Original protocol adapter. The renderer is separately built and provisioned.
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { inspectReadableHtml, needsBrowser, LAUNCH_ARGS } from '../bench/html_browser.mjs';

let source = '';
for await (const chunk of process.stdin) source += chunk;
const request = JSON.parse(source);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
let phase = 'setup';
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
  const renderer = await import(pathToFileURL(modulePath));
  const { convertDocxToPdf, checkExportEnvironment } = renderer;
  const environment = await checkExportEnvironment();
  if (!environment.ok) {
    const error = new Error(JSON.stringify(environment.findings));
    error.code = 'ENVIRONMENT_INELIGIBLE';
    throw error;
  }
  const bytes = await readFile(request.input);
  if (hash(bytes) !== request.inputSha256) throw new Error('Input digest mismatch');
  phase = 'conversion';
  const profileOptions = profile => ({
    reviewProfile: profile.review,
    commentProfile: profile.comments,
    ...(profile.markupPresentation === undefined ? {} : { markupPresentation: profile.markupPresentation }),
  });
  const sharedOptions = {
    timeoutMs: request.timeoutMs,
    fontDirectories: request.fontDirectories,
    strictFonts: true,
  };
  const options = { ...sharedOptions, ...profileOptions(request.profile) };
  const runtimeOf = report => {
    const observed = report.environment?.observed;
    if (report.environment?.verification !== 'nodeVerified' || report.environment?.fidelityTier !== 'releaseBaselined' || !observed?.browserBuild) {
      const error = new Error('Production output is not from the verified pinned export runtime');
      error.code = 'ENVIRONMENT_INELIGIBLE';
      throw error;
    }
    return Object.fromEntries(['playwrightVersion', 'browserProduct', 'browserBuild', 'executableSha256', 'launchFlags', 'operatingSystem', 'architecture'].map(key => [key, observed[key]]));
  };
  const deadline = performance.now() + request.timeoutMs;
  const result = await convertDocxToPdf(new Uint8Array(bytes), options);
  const runtime = runtimeOf(result.renderReport);
  phase = 'artifact';
  await writeFile(request.output, result.pdf, { flag: 'wx' });
  await writeFile(request.report, JSON.stringify(result.renderReport, null, 2) + '\n', { flag: 'wx' });
  let htmlArtifact;
  if (request.htmlOutput) {
    try {
      if (typeof renderer.convertDocxToStandaloneHtml !== 'function' || !request.htmlReport)
        throw new Error('The declared standalone HTML output is unavailable');
      const remaining = Math.floor(deadline - performance.now());
      if (remaining <= 0) throw new Error('No conversion time remains for the declared HTML output');
      const htmlProfile = request.htmlProfile ?? request.profile;
      const html = await renderer.convertDocxToStandaloneHtml(new Uint8Array(bytes), {
        ...sharedOptions, ...profileOptions(htmlProfile), timeoutMs: remaining,
      });
      if (typeof html.html !== 'string' || JSON.stringify(runtimeOf(html.renderReport)) !== JSON.stringify(runtime))
        throw new Error('Delivered HTML does not match the verified PDF runtime');
      await writeFile(request.htmlOutput, html.html, { flag: 'wx' });
      await writeFile(request.htmlReport, JSON.stringify(html.renderReport, null, 2) + '\n', { flag: 'wx' });
      htmlArtifact = { status: 'ok', sha256: hash(html.html), profile: htmlProfile };
      if (needsBrowser(request.htmlAssertions ?? [])) {
        if (!request.htmlObservations) throw new Error('The declared browser HTML observation path is missing');
        const budget = Math.floor(deadline - performance.now());
        if (budget <= 0) throw new Error('No conversion time remains for HTML observation');
        const provisioned = createRequire(resolve(root, 'npm-export/package.json'))('@playwright/browser-chromium');
        const executablePath = provisioned.chromium.executablePath();
        const executableSha256 = hash(await readFile(executablePath));
        if (executableSha256 !== runtime.executableSha256)
          throw new Error('The HTML observer browser differs from the verified renderer browser');
        const browser = await provisioned.chromium.launch({ executablePath, chromiumSandbox: true,
          args: LAUNCH_ARGS, timeout: budget });
        try {
          const observationBudget = Math.floor(deadline - performance.now());
          const facts = await inspectReadableHtml(browser, html.html, request.htmlAssertions, observationBudget);
          facts.inspectorSha256 = hash(await readFile(new URL('../bench/html_browser.mjs', import.meta.url)));
          facts.executableSha256 = executableSha256;
          const encoded = JSON.stringify(facts, null, 2) + '\n';
          await writeFile(request.htmlObservations, encoded, { flag: 'wx' });
          htmlArtifact.browserFactsSha256 = hash(encoded);
        } finally { await browser.close(); }
      }
    } catch (error) {
      htmlArtifact = { status: 'unmeasured', error: error.message };
    }
  }
  process.stdout.write(JSON.stringify({ protocol: 1, status: 'ok', pdfSha256: hash(result.pdf), renderer: { name: 'docxodus', commit, node: process.version, runtime, build }, productionReport: request.report, ...(htmlArtifact ? { htmlArtifact } : {}) }));
} catch (error) {
  process.stdout.write(JSON.stringify({ protocol: 1, status: error.code === 'ENVIRONMENT_INELIGIBLE' || phase !== 'conversion' ? 'unmeasured' : 'failed', error: { code: error.code ?? 'ADAPTER_FAILURE', phase, message: error.message } }));
}
