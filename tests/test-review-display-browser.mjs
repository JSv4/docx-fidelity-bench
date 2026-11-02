// Independent observer contract, using the separately provisioned browser dependency.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { inspectReadableHtml, LAUNCH_ARGS } from '../bench/html_browser.mjs';

test('review display observations detect each changed family and leftover markup containers', async () => {
  assert.ok(process.env.DOCXODUS_SOURCE_ROOT, 'Set DOCXODUS_SOURCE_ROOT to the built renderer');
  const require = createRequire(resolve(process.env.DOCXODUS_SOURCE_ROOT, 'npm/package.json'));
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ headless: true, chromiumSandbox: true, args: LAUNCH_ARGS,
    ...(process.env.DOCXODUS_CHROMIUM_PATH ? { executablePath: process.env.DOCXODUS_CHROMIUM_PATH } : {}) });
  const expected = { formatBalloons: 1, commentBalloons: 1, insertions: 1, deletions: 1, areas: 1, layers: 1 };
  const declaration = { type: 'review-display', version: 1, marker: 'HazelCurrent', expected,
    requiredTokens: { HazelCurrent: 1, HazelNote: 1 }, forbiddenTokens: ['HazelDeleted'] };
  const fragments = {
    formatBalloons: '<div class="page-balloon"><b>Formatted: Bold</b></div>',
    commentBalloons: '<div class="page-balloon"><b>Commented [HR]:</b> HazelNote</div>',
    insertions: '<ins>HazelNew</ins>', deletions: '<del>HazelOld</del>',
    areas: '<div class="page-markup-area"></div>', layers: '<div class="page-markup-layer"></div>',
  };
  const observe = async (parts, d = declaration, marker = '<p>HazelCurrent</p>') => {
    const facts = await inspectReadableHtml(browser, '<body>' + marker + Object.values(parts).join('') + '</body>', [d], 10000);
    return execFileSync('python3', ['-c', 'import json,sys;from bench.html_artifacts import review_display_pass;d,o=json.load(sys.stdin);print(review_display_pass(d,o,0))'],
      { input: JSON.stringify([d, facts.observations[0]]), encoding: 'utf8' }).trim();
  };
  try {
    assert.equal(await observe(fragments), 'True');
    assert.equal(await observe({ ...fragments, commentBalloons: fragments.commentBalloons.replace('HazelNote', '') }), 'False', 'empty comment balloon');
    assert.equal(await observe({ ...fragments, commentBalloons: fragments.commentBalloons.replace('HazelNote', '<span hidden>HazelNote</span>') }), 'False', 'hidden comment text');
    for (const key of Object.keys(fragments)) {
      assert.equal(await observe({ ...fragments, [key]: '' }), 'False', 'missing ' + key);
      assert.equal(await observe({ ...fragments, [key]: fragments[key].repeat(2) }), 'False', 'duplicate ' + key);
    }
    const hidden = { ...declaration, requiredTokens: { HazelCurrent: 1 }, forbiddenTokens: ['HazelNote', 'HazelDeleted'], expected: Object.fromEntries(Object.keys(expected).map(key => [key, 0])) };
    assert.equal(await observe({}, hidden), 'True');
    assert.equal(await observe({ leak: '<p>HazelNote</p>' }, hidden), 'False', 'hidden comment leaked as plain text');
    assert.equal(await observe({ areas: fragments.areas }, hidden), 'False', 'empty retained area');
    assert.equal(await observe(fragments, declaration, '<p hidden>HazelCurrent</p>'), 'False', 'hidden source marker');
  } finally { await browser.close(); }
});
