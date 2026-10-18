import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

function request(value, overrides = {}) {
  const env = { ...process.env };
  delete env.DOCXODUS_SOURCE_ROOT;
  delete env.DOCXODUS_EXPORT_MODULE;
  const result = spawnSync(process.execPath, [fileURLToPath(new URL('../adapters/docxodus.mjs', import.meta.url))], { input: JSON.stringify(value), env: { ...env, ...overrides }, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

test('missing renderer provisioning is unmeasured', () => {
  const result = request({ protocol: 1 });
  assert.equal(result.status, 'unmeasured');
  assert.equal(result.error.phase, 'setup');
});

test('unknown protocol is unmeasured', () => {
  assert.equal(request({ protocol: 2 }).status, 'unmeasured');
});

test('invalid renderer source cannot become a zero fidelity score', () => {
  const root = mkdtempSync(join(tmpdir(), 'docx-adapter-contract-'));
  try {
    const result = request({ protocol: 1, candidate: '0'.repeat(40) }, { DOCXODUS_SOURCE_ROOT: root, DOCXODUS_EXPORT_MODULE: join(root, 'missing.js') });
    assert.equal(result.status, 'unmeasured');
    assert.equal(result.error.phase, 'setup');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('public profiles and optional delivered HTML retain verified artifact identity', () => {
  const root = mkdtempSync(join(tmpdir(), 'docx-profile-contract-'));
  const hash = value => createHash('sha256').update(value).digest('hex');
  const git = (...args) => {
    const result = spawnSync('git', ['-C', root, ...args], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    return result.stdout.trim();
  };
  try {
    mkdirSync(join(root, 'npm-export', 'dist'), { recursive: true });
    const modulePath = join(root, 'npm-export', 'dist', 'index.js');
    // Protocol-only fake: its output records the public options, never a fidelity result.
    const browserPath = join(root, 'protocol-browser');
    writeFileSync(browserPath, 'protocol browser');
    const browserSha = hash('protocol browser');
    mkdirSync(join(root, 'npm-export/node_modules/@playwright/browser-chromium'), { recursive: true });
    writeFileSync(join(root, 'npm-export/package.json'), '{}');
    writeFileSync(join(root, 'npm-export/node_modules/@playwright/browser-chromium/index.js'), `
      exports.chromium = { executablePath: () => ${JSON.stringify(browserPath)},
        launch: async options => {
          if (!options.chromiumSandbox || options.timeout <= 0) throw new Error('Invalid observer launch');
          return { close: async () => {}, newContext: async options => {
            if (options.javaScriptEnabled || !options.offline) throw new Error('Observer policy changed');
            return { close: async () => {}, newPage: async () => ({
              setDefaultTimeout() {}, emulateMedia: async () => {}, setContent: async () => {},
              evaluate: async (fn, declarations) => declarations ? [{ index: 0, marker: 'FormatLabel', matches: 1 }] : undefined
            }) };
          } };
        } };
    `);
    const module = `export async function checkExportEnvironment() { return { ok: true }; }
      export async function convertDocxToPdf(bytes, options) {
        if (options.commentProfile === 'endnotes') await new Promise(resolve => setTimeout(resolve, 25));
        return {
        pdf: Buffer.from(JSON.stringify(options)), renderReport: { environment: {
          verification: 'nodeVerified', fidelityTier: 'releaseBaselined', observed: { browserBuild: 'contract-only', executableSha256: '${browserSha}' }
        } }
      }; }
      export async function convertDocxToStandaloneHtml(bytes, options) {
        if (options.commentProfile === 'inline') throw new Error('HTML fixture failure');
        if (options.commentProfile === 'endnotes' && options.timeoutMs >= 100) throw new Error('Conversion budget was reset');
        return { html: '<span title="Bold added">FormatLabel</span>', renderReport: { publicOptions: options, environment: {
          verification: 'nodeVerified', fidelityTier: options.commentProfile === 'margin' ? 'experimental' : 'releaseBaselined',
          observed: { browserBuild: 'contract-only', executableSha256: '${browserSha}' }
        } } };
      }`;
    writeFileSync(modulePath, module);
    writeFileSync(join(root, 'package.json'), JSON.stringify({ type: 'module' }));
    git('init', '-q'); git('add', '.');
    git('-c', 'user.name=Fixture Author', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Protocol fixture');
    const candidate = git('rev-parse', 'HEAD');
    writeFileSync(join(root, '.docx-bench-build.json'), JSON.stringify({
      schema: 1, commit: candidate, tree: git('rev-parse', 'HEAD^{tree}'), node: process.version,
      recipeSha256: hash(readFileSync(new URL('../bench/build.py', import.meta.url))),
      files: { 'npm-export/dist/index.js': hash(module) },
    }));
    const input = join(root, 'input.docx'); writeFileSync(input, 'protocol input');
    for (const [name, markupPresentation, comments, htmlStatus, htmlProfile, observe] of [
      ['default', undefined, 'hidden', undefined], ['word', 'word', 'hidden', 'ok'],
      ['html-failure', 'word', 'inline', 'unmeasured'], ['html-unverified', 'word', 'margin', 'unmeasured'],
      ['shared-budget', 'word', 'endnotes', 'ok'],
      ['html-override', 'word', 'inline', 'ok', { review: 'final', comments: 'hidden' }],
      ['html-css', 'word', 'hidden', 'ok', { review: 'final', comments: 'hidden', additionalCss: 'p > span {font-size:32px}' }],
      ['reader', 'word', 'hidden', 'ok', undefined, 'observe'],
      ['style-reader', 'word', 'hidden', 'ok', undefined, 'style'],
      ['reader-no-path', 'word', 'hidden', 'unmeasured', undefined, 'missing'],
    ]) {
      const profile = { review: 'markup', comments, ...(markupPresentation ? { markupPresentation } : {}) };
      const output = join(root, `output-${name}.pdf`);
      const result = request({ protocol: 1, candidate, input, inputSha256: hash('protocol input'), output,
        report: output + '.json', profile, ...(htmlProfile ? { htmlProfile } : {}),
        ...(observe ? { htmlAssertions: [observe === 'style' ? { type: 'marker-computed-style', version: 1, marker: 'FormatLabel', property: 'font-size', equals: '13.6px' } : { type: 'marker-readable', version: 1, marker: 'FormatLabel', tokens: ['FormatLabel'] }],
          ...(['observe', 'style'].includes(observe) ? { htmlObservations: output + '.observations.json' } : {}) } : {}),
        fontDirectories: [], timeoutMs: name === 'shared-budget' ? 100 : 120000,
        ...(htmlStatus ? { htmlOutput: output + '.html', htmlReport: output + '.html.json' } : {}) },
        { DOCXODUS_SOURCE_ROOT: root, DOCXODUS_EXPORT_MODULE: modulePath });
      assert.equal(result.status, 'ok', JSON.stringify(result.error));
      const options = JSON.parse(readFileSync(output, 'utf8'));
      assert.equal(options.reviewProfile, 'markup');
      assert.equal(options.markupPresentation, markupPresentation);
      assert.equal(Object.hasOwn(options, 'markupPresentation'), markupPresentation !== undefined);
      assert.equal(options.commentProfile, comments);
      assert.equal(options.additionalCss, undefined);
      if (htmlStatus) {
        assert.equal(result.htmlArtifact.status, htmlStatus);
        if (htmlStatus === 'ok') {
          assert.equal(result.htmlArtifact.sha256, hash(readFileSync(output + '.html')));
          assert.match(readFileSync(output + '.html', 'utf8'), /title="Bold added"/);
          assert.ok(existsSync(output + '.html.json'));
          const htmlOptions = JSON.parse(readFileSync(output + '.html.json')).publicOptions;
          assert.equal(htmlOptions.reviewProfile, htmlProfile?.review ?? profile.review);
          assert.equal(htmlOptions.commentProfile, htmlProfile?.comments ?? profile.comments);
          assert.equal(htmlOptions.markupPresentation, htmlProfile ? undefined : profile.markupPresentation);
          assert.deepEqual(result.htmlArtifact.profile, htmlProfile ?? profile);
          assert.equal(htmlOptions.additionalCss, htmlProfile?.additionalCss);
          if (['observe', 'style'].includes(observe)) {
            const facts = JSON.parse(readFileSync(output + '.observations.json'));
            assert.equal(result.htmlArtifact.browserFactsSha256, hash(readFileSync(output + '.observations.json')));
            assert.equal(facts.htmlSha256, result.htmlArtifact.sha256);
            assert.equal(facts.executableSha256, browserSha);
            assert.equal(facts.inspectorSha256, hash(readFileSync(new URL('../bench/html_browser.mjs', import.meta.url))));
            assert.equal(facts.observations[0].marker, 'FormatLabel');
          }
        } else {
          assert.equal(existsSync(output + '.html'), observe === 'missing');
          if (observe === 'missing') assert.match(result.htmlArtifact.error, /observation path is missing/);
        }
      } else assert.equal(Object.hasOwn(result, 'htmlArtifact'), false);
    }
  } finally { rmSync(root, { recursive: true, force: true }); }
});
