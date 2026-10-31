// Integration contract: use the separately provisioned renderer's browser dependencies.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { inspectReadableHtml, LAUNCH_ARGS } from '../bench/html_browser.mjs';

test('checkbox observations reject missing paint, wrong state, size, and alignment', async () => {
  assert.ok(process.env.DOCXODUS_SOURCE_ROOT, 'Set DOCXODUS_SOURCE_ROOT to the built renderer');
  const require = createRequire(resolve(process.env.DOCXODUS_SOURCE_ROOT, 'npm/package.json'));
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ headless: true, args: LAUNCH_ARGS,
    ...(process.env.DOCXODUS_CHROMIUM_PATH ? { executablePath: process.env.DOCXODUS_CHROMIUM_PATH } : {}) });
  const outline = '<rect x=".5" y=".5" width="15" height="15"/>';
  const cross = '<path d="M2 2L14 14M14 2L2 14"/>';
  const cases = [
    { name: 'unchecked', checked: false, drawing: outline, pass: true },
    { name: 'checked', drawing: outline + cross, pass: true },
    { name: 'blank', drawing: '' },
    { name: 'hidden child', drawing: outline + cross, graphicStyle: 'visibility:hidden' },
    { name: 'wrong painted state', drawing: outline },
    { name: 'wrong accessible state', checked: false, drawing: outline + cross },
    { name: 'white paint', drawing: outline + cross, graphicStyle: 'color:white' },
    { name: 'undersized', drawing: outline + cross, size: 8 },
    { name: 'oversized', drawing: outline + cross, size: 24 },
    { name: 'displaced', drawing: outline + cross, style: 'position:relative;top:10px' },
    { name: 'horizontally displaced', drawing: outline + cross, style: 'position:relative;left:250px' },
    { name: 'solid fill', drawing: '<rect width="16" height="16" fill="black"/>' },
    { name: 'only one diagonal', drawing: outline + '<path d="M2 2L14 14"/>' },
  ];
  try {
    for (const c of cases) {
      const declaration = { type: 'named-checkbox', version: 1, marker: 'ElmBox', checked: c.checked ?? true,
        sizePt: 12, caption: 'Caption' };
      const html = `<body style="margin:20px;background:white;color:black;font:14px serif"><p style="display:flex;align-items:center;gap:4px;margin:0;height:24px"><span>Caption</span><span role="checkbox" aria-label="ElmBox" aria-checked="${declaration.checked}" style="display:inline-block;width:${c.size ?? 16}px;height:${c.size ?? 16}px;${c.style ?? ''}"><svg width="100%" height="100%" viewBox="0 0 16 16" fill="none" stroke="currentColor" style="${c.graphicStyle ?? ''}">${c.drawing}</svg></span></p></body>`;
      const facts = await inspectReadableHtml(browser, html, [declaration], 10000);
      const passed = execFileSync('python3', ['-c', 'import json,sys;from bench.html_artifacts import checkbox_pass;d,o=json.load(sys.stdin);print(checkbox_pass(d,o,0))'],
        { input: JSON.stringify([declaration, facts.observations[0]]), encoding: 'utf8' }).trim();
      assert.equal(passed, c.pass ? 'True' : 'False', c.name);
    }
  } finally { await browser.close(); }
});
