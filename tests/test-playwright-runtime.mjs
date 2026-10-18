// Integration contract: run after building the separately provisioned renderer.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

test('installed renderer dependencies distinguish the Chromium installer from its API', () => {
  assert.ok(process.env.DOCXODUS_SOURCE_ROOT, 'Set DOCXODUS_SOURCE_ROOT to the built renderer');
  const root = resolve(process.env.DOCXODUS_SOURCE_ROOT, 'npm-export');
  const require = createRequire(resolve(root, 'package.json'));
  const lock = JSON.parse(readFileSync(resolve(root, 'package-lock.json'), 'utf8'));
  const installer = require('@playwright/browser-chromium');
  const { chromium } = require('playwright-core');
  // These are real installed packages, not the protocol test's doubles.
  assert.equal(installer.chromium, undefined);
  assert.equal(typeof chromium.executablePath, 'function');
  assert.equal(typeof chromium.launch, 'function');
  const versions = ['@playwright/browser-chromium', 'playwright-core'].map(name => {
    const installed = require(`${name}/package.json`).version;
    assert.equal(installed, lock.packages[`node_modules/${name}`].version);
    return installed;
  });
  assert.equal(versions[0], versions[1], 'The installer and browser API must match');
  assert.ok(chromium.executablePath());
});
