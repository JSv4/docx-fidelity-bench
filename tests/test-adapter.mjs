import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdtempSync, rmSync } from 'node:fs';
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
