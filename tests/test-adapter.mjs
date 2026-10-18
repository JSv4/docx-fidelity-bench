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
    const module = `export async function checkExportEnvironment() { return { ok: true }; }
      export async function convertDocxToPdf(bytes, options) {
        if (options.commentProfile === 'endnotes') await new Promise(resolve => setTimeout(resolve, 25));
        return {
        pdf: Buffer.from(JSON.stringify(options)), renderReport: { environment: {
          verification: 'nodeVerified', fidelityTier: 'releaseBaselined', observed: { browserBuild: 'contract-only' }
        } }
      }; }
      export async function convertDocxToStandaloneHtml(bytes, options) {
        if (options.commentProfile === 'inline') throw new Error('HTML fixture failure');
        if (options.commentProfile === 'endnotes' && options.timeoutMs >= 100) throw new Error('Conversion budget was reset');
        return { html: '<span title="Bold added">FormatLabel</span>', renderReport: { environment: {
          verification: 'nodeVerified', fidelityTier: options.commentProfile === 'margin' ? 'experimental' : 'releaseBaselined',
          observed: { browserBuild: 'contract-only' }
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
    for (const [name, markupPresentation, comments, htmlStatus] of [
      ['default', undefined, 'hidden', undefined], ['word', 'word', 'hidden', 'ok'],
      ['html-failure', 'word', 'inline', 'unmeasured'], ['html-unverified', 'word', 'margin', 'unmeasured'],
      ['shared-budget', 'word', 'endnotes', 'ok'],
    ]) {
      const profile = { review: 'markup', comments, ...(markupPresentation ? { markupPresentation } : {}) };
      const output = join(root, `output-${name}.pdf`);
      const result = request({ protocol: 1, candidate, input, inputSha256: hash('protocol input'), output,
        report: output + '.json', profile, fontDirectories: [], timeoutMs: name === 'shared-budget' ? 100 : 120000,
        ...(htmlStatus ? { htmlOutput: output + '.html', htmlReport: output + '.html.json' } : {}) },
        { DOCXODUS_SOURCE_ROOT: root, DOCXODUS_EXPORT_MODULE: modulePath });
      assert.equal(result.status, 'ok', JSON.stringify(result.error));
      const options = JSON.parse(readFileSync(output, 'utf8'));
      assert.equal(options.reviewProfile, 'markup');
      assert.equal(options.markupPresentation, markupPresentation);
      assert.equal(Object.hasOwn(options, 'markupPresentation'), markupPresentation !== undefined);
      assert.equal(options.commentProfile, comments);
      if (htmlStatus) {
        assert.equal(result.htmlArtifact.status, htmlStatus);
        if (htmlStatus === 'ok') {
          assert.equal(result.htmlArtifact.sha256, hash(readFileSync(output + '.html')));
          assert.match(readFileSync(output + '.html', 'utf8'), /title="Bold added"/);
          assert.ok(existsSync(output + '.html.json'));
        } else assert.equal(existsSync(output + '.html'), false);
      } else assert.equal(Object.hasOwn(result, 'htmlArtifact'), false);
    }
  } finally { rmSync(root, { recursive: true, force: true }); }
});
