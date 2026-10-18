import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
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

test('markup presentation reaches the public export API and absent settings stay absent', () => {
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
      export async function convertDocxToPdf(bytes, options) { return {
        pdf: Buffer.from(JSON.stringify(options)), renderReport: { environment: {
          verification: 'nodeVerified', fidelityTier: 'releaseBaselined', observed: { browserBuild: 'contract-only' }
        } }
      }; }`;
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
    for (const markupPresentation of [undefined, 'word']) {
      const profile = { review: 'markup', comments: 'hidden', ...(markupPresentation ? { markupPresentation } : {}) };
      const output = join(root, `output-${markupPresentation ?? 'default'}.pdf`);
      const result = request({ protocol: 1, candidate, input, inputSha256: hash('protocol input'), output,
        report: output + '.json', profile, fontDirectories: [], timeoutMs: 120000 },
        { DOCXODUS_SOURCE_ROOT: root, DOCXODUS_EXPORT_MODULE: modulePath });
      assert.equal(result.status, 'ok', JSON.stringify(result.error));
      const options = JSON.parse(readFileSync(output, 'utf8'));
      assert.equal(options.reviewProfile, 'markup');
      assert.equal(options.markupPresentation, markupPresentation);
      assert.equal(Object.hasOwn(options, 'markupPresentation'), markupPresentation !== undefined);
    }
  } finally { rmSync(root, { recursive: true, force: true }); }
});
