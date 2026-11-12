// Observe authored HTML with the independent inspector and replay its Python contract.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { inspectReadableHtml } from '../bench/html_browser.mjs';

test('MathML structure rejects swaps, flattening, duplicates, and hidden formulas', async () => {
  assert.ok(process.env.DOCXODUS_SOURCE_ROOT, 'Set DOCXODUS_SOURCE_ROOT to the built renderer');
  const { chromium } = createRequire(resolve(process.env.DOCXODUS_SOURCE_ROOT, 'npm/package.json'))('playwright');
  const browser = await chromium.launch({ chromiumSandbox: true,
    ...(process.env.DOCXODUS_CHROMIUM_PATH ? { executablePath: process.env.DOCXODUS_CHROMIUM_PATH } : {}) });
  const fraction = '<mfrac><mn>27.5</mn><mn>9</mn></mfrac>';
  const root = '<mroot><mn>125</mn><mn>3</mn></mroot>';
  const formula = body => `<math xmlns="http://www.w3.org/1998/Math/MathML">${body}</math>`;
  const cases = [
    { name: 'fraction', body: fraction, pass: true },
    { name: 'harmless grouping', body: '<mrow><mfrac><mrow><mn>27.5</mn></mrow><mn>9</mn></mfrac></mrow>', pass: true },
    { name: 'swapped fraction', body: '<mfrac><mn>9</mn><mn>27.5</mn></mfrac>' },
    { name: 'flattened fraction', body: '<mrow><mn>27.5</mn><mn>9</mn></mrow>' },
    { name: 'duplicate', html: formula(fraction).repeat(2) },
    { name: 'CSS block display', html: `<math style="display:block math">${fraction}</math>` },
    { name: 'missing bar', body: fraction.replace('<mfrac>', '<mfrac linethickness="0">') },
    { name: 'hidden operand', body: fraction.replace('<mn>', '<mn style="visibility:hidden">') },
    { name: 'missing', html: '27.5 / 9' },
    { name: 'hidden', html: `<div style="display:none">${formula(fraction)}</div>` },
    { name: 'indexed root', body: root, root: true, pass: true },
    { name: 'swapped index/base', body: '<mroot><mn>3</mn><mn>125</mn></mroot>', root: true },
  ];
  try {
    for (const value of cases) {
      const declaration = { type: 'math-expression', version: 1, marker: 'MapleFormula', display: 'inline',
        tree: value.root ? ['mroot', ['mn', '125'], ['mn', '3']] : ['mfrac', ['mn', '27.5'], ['mn', '9']] };
      const facts = await inspectReadableHtml(browser, value.html ?? formula(value.body), [declaration], 10000);
      const passed = execFileSync('python3', ['-c',
        'import json,sys;from bench.html_artifacts import math_expression_pass;d,o=json.load(sys.stdin);print(math_expression_pass(d,o,0))'],
      { input: JSON.stringify([declaration, facts.observations[0]]), encoding: 'utf8' }).trim();
      assert.equal(passed, value.pass ? 'True' : 'False', value.name);
    }
  } finally { await browser.close(); }
});
