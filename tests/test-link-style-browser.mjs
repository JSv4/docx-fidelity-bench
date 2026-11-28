// Observe authored link renderings with the independent inspector and replay the field-link cases'
// colour and decoration declarations through the Python contract (Docxodus #1870).
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { inspectReadableHtml, LAUNCH_ARGS } from '../bench/html_browser.mjs';

const manifest = JSON.parse(readFileSync(new URL('../fixtures/manifest.json', import.meta.url), 'utf8'));
const styles = id => manifest.cases.find(c => c.id === id).htmlAssertions.filter(d => d.type === 'marker-computed-style');
const page = body => `<!doctype html><html><body style="margin:20px;background:white;color:black;font:16px serif">${body}</body></html>`;
// Authored renderings only. Plain <a> takes the browser's link colour (0000EE) and underline.
const entry = (label, link = '<a href="#_Toc90001" style="color:#000000;text-decoration:none">') =>
  `<p>${link}<span>${label} </span><span>&#9;</span><span>1</span></a></p>`;
const lantern = '<p>See <a href="#_Toc90001" style="color:inherit;text-decoration:none"><span style="color:#0563C1;text-decoration:underline">WisteriaLantern</span></a></p>';
const entries = link => ['WisteriaGate', 'WisteriaTerrace', 'WisteriaCourt'].map(label => entry(label, link)).join('');
const arbor = link => `<p>${link}<span>WisteriaArbor</span></a></p>`;
const pergola = '<p><a href="https://example.com/wisteria-pergola" style="color:inherit;text-decoration:none"><span style="color:#0563C1;text-decoration:underline">WisteriaPergola</span></a></p>';

async function replay(browser, html, declarations) {
  const facts = await inspectReadableHtml(browser, html, declarations, 10000);
  const passed = execFileSync('python3', ['-c', 'import json,sys;from bench.html_artifacts import validate_declaration, computed_style_pass as p;' +
    'ds,os=json.load(sys.stdin);[validate_declaration(d) for d in ds];print(json.dumps([p(d,o,i) for i,(d,o) in enumerate(zip(ds,os))]))'],
    { input: JSON.stringify([declarations, facts.observations]), encoding: 'utf8' });
  return { facts, failed: JSON.parse(passed).flatMap((ok, i) => ok ? [] : [`${declarations[i].marker} ${declarations[i].property}`]) };
}

// Red pixels in a screenshot: the decoration colour of the propagation cases below, never the text's.
async function redPixels(browser, html) {
  const context = await browser.newContext({ viewport: { width: 640, height: 200 } });
  try {
    const tab = await context.newPage();
    await tab.setContent(html);
    const png = (await tab.screenshot()).toString('base64');
    return await tab.evaluate(async data => {
      const image = new Image(); image.src = 'data:image/png;base64,' + data; await image.decode();
      const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
      const context = canvas.getContext('2d'); context.drawImage(image, 0, 0);
      const pixels = context.getImageData(0, 0, image.width, image.height).data;
      let red = 0;
      for (let i = 0; i < pixels.length; i += 4) if (pixels[i] > 200 && pixels[i + 1] < 90 && pixels[i + 2] < 90) red++;
      return red;
    }, png);
  } finally { await context.close(); }
}

test('link colour and painted decoration observations pass a correct rendering and fail the review mutants', async () => {
  assert.ok(process.env.DOCXODUS_SOURCE_ROOT, 'Set DOCXODUS_SOURCE_ROOT to the built renderer');
  const { chromium } = createRequire(resolve(process.env.DOCXODUS_SOURCE_ROOT, 'npm/package.json'))('playwright');
  const browser = await chromium.launch({ headless: true, args: LAUNCH_ARGS,
    ...(process.env.DOCXODUS_CHROMIUM_PATH ? { executablePath: process.env.DOCXODUS_CHROMIUM_PATH } : {}) });
  const entryChecks = properties => ['WisteriaGate', 'WisteriaTerrace', 'WisteriaCourt']
    .flatMap(label => properties.map(property => `${label} ${property}`));
  const cases = [
    { name: 'correct contents', id: 'field-link-toc-complex-entries', body: entries() + lantern, failed: [] },
    { name: 'correct contents, control', id: 'field-link-toc-element-entries-control', body: entries() + lantern, failed: [] },
    // (a) Black entries under an <a> that keeps its default underline: each label's own element
    // computes text-decoration-line "none", but the link's underline is painted through it.
    { name: 'review mutant (a): black, underlined entries', id: 'field-link-toc-complex-entries',
      body: entries('<a href="#_Toc90001" style="color:#000000">') + lantern, failed: entryChecks(['text-decoration-line']) },
    { name: 'review mutant (b): entries in the link blue, underlined', id: 'field-link-toc-simple-entries',
      body: entries('<a href="#_Toc90001">') + lantern, failed: entryChecks(['color', 'text-decoration-line']) },
    { name: 'underline from the paragraph', id: 'field-link-toc-complex-entries',
      body: entries('<a href="#_Toc90001" style="color:#000000;text-decoration:none">').replaceAll('<p>', '<p style="text-decoration:underline">') + lantern,
      failed: entryChecks(['text-decoration-line']) },
    { name: 'outside link drawn black', id: 'field-link-toc-complex-entries',
      body: entries() + lantern.replace('color:#0563C1;', 'color:#000000;'), failed: ['WisteriaLantern color'] },
    { name: 'correct simple fields', id: 'field-link-simple-hyperlink',
      body: arbor('<a href="https://example.com/wisteria-arbor" style="color:inherit;text-decoration:none">') + pergola, failed: [] },
    { name: "review mutant (b'): WisteriaArbor as a link-blue underlined link", id: 'field-link-simple-hyperlink',
      body: arbor('<a href="https://example.com/wisteria-arbor">') + pergola,
      failed: ['WisteriaArbor color', 'WisteriaArbor text-decoration-line'] },
    { name: 'WisteriaArbor in the Hyperlink style', id: 'field-link-simple-hyperlink-control',
      body: arbor('<a href="https://example.com/wisteria-arbor" style="color:#0563C1;text-decoration:underline">') + pergola,
      failed: ['WisteriaArbor color', 'WisteriaArbor text-decoration-line'] },
  ];
  try {
    for (const c of cases) {
      const declarations = styles(c.id);
      assert.equal(declarations.length, c.id.includes('simple-hyperlink') ? 4 : 8, c.id);
      const { failed } = await replay(browser, page(c.body), declarations);
      assert.deepEqual(failed, c.failed, c.name);
    }
    // What the observer reports is what the browser paints: a red underline on an ancestor reaches
    // an inline child whose own value is "none", and stops at an inline block.
    const decoration = [{ type: 'marker-computed-style', version: 1, marker: 'WisteriaCourt', property: 'text-decoration-line', equals: 'none' }];
    for (const [name, body, painted] of [
      ['inline child of an underlined link', '<p><a href="#x" style="color:#000;text-decoration:underline;text-decoration-color:#ff0000"><span style="text-decoration:none">WisteriaCourt</span></a></p>', true],
      ['inline block in an underlined link', '<p><a href="#x" style="color:#000;text-decoration:underline;text-decoration-color:#ff0000"><span style="display:inline-block">WisteriaCourt</span></a></p>', false],
      ['no decoration', '<p><a href="#x" style="color:#000;text-decoration:none"><span>WisteriaCourt</span></a></p>', false],
      ['underlined paragraph around a link', '<p style="text-decoration:underline;text-decoration-color:#ff0000"><a href="#x" style="color:#000;text-decoration:none"><span>WisteriaCourt</span></a></p>', true],
      ['underlined link without a box', '<p><a href="#x" style="display:contents;color:#000;text-decoration:underline;text-decoration-color:#ff0000"><span>WisteriaCourt</span></a></p>', false],
    ]) {
      const { facts, failed } = await replay(browser, page(body), decoration);
      assert.deepEqual(facts.observations[0].computedStyle['text-decoration-line'], [painted ? 'underline' : 'none'], name);
      assert.deepEqual(failed, painted ? ['WisteriaCourt text-decoration-line'] : [], name);
      assert.equal((await redPixels(browser, page(body))) > 20, painted, name + ': painted red underline');
    }
  } finally { await browser.close(); }
});
