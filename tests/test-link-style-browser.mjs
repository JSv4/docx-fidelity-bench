// Observe authored link renderings with the independent inspector and replay the field-link cases'
// colour and decoration declarations through the Python contract (Docxodus #1870).
//
// The validate workflow has no browser, so this test also records what the observer saw in
// tests/link-style-observations.json, bound to the observer's source digest; test_html_style.py
// replays that record in CI and fails once the observer changes until this test records it again:
//   LINK_STYLE_RECORD=1 DOCXODUS_SOURCE_ROOT=... node --test tests/test-link-style-browser.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { inspectReadableHtml, LAUNCH_ARGS } from '../bench/html_browser.mjs';

const RECORD = new URL('./link-style-observations.json', import.meta.url);
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
// Text drawn as SVG, the way a renderer may draw a run: SVG text paints with its fill, and no HTML
// ancestor's underline reaches it.
const svgText = (label, fill = 'rgb(0, 0, 0)') => `<svg width="220" height="24" xmlns="http://www.w3.org/2000/svg">` +
  `<text x="0" y="18" style="font: 16px serif; fill: ${fill};"><tspan x="0">${label}</tspan></text></svg>`;
const entryChecks = properties => ['WisteriaGate', 'WisteriaTerrace', 'WisteriaCourt']
  .flatMap(label => properties.map(property => `${label} ${property}`));

const RED = 'text-decoration:underline;text-decoration-color:#ff0000';
const svgRed = (attributes, inner) => `<svg width="400" height="40" xmlns="http://www.w3.org/2000/svg" ${attributes}>${inner}</svg>`;
// Each probe paints any decoration line in red, never the text, so the screenshot shows whether a line reaches it.
const paintProbes = [
  ['inline child of an underlined link', `<p><a href="#x" style="color:#000;${RED}"><span style="text-decoration:none">WisteriaCourt</span></a></p>`, true],
  ['underlined paragraph around a link', `<p style="${RED}"><a href="#x" style="color:#000;text-decoration:none"><span>WisteriaCourt</span></a></p>`, true],
  ['underlined flex container', `<div style="display:flex;${RED}"><span>WisteriaCourt</span></div>`, true],
  ['underlined grid container', `<div style="display:grid;${RED}"><span>WisteriaCourt</span></div>`, true],
  ['inline block in an underlined link', `<p><a href="#x" style="color:#000;${RED}"><span style="display:inline-block">WisteriaCourt</span></a></p>`, false],
  ['inline table in an underlined paragraph', `<p style="${RED}"><span style="display:inline-table">WisteriaCourt</span></p>`, false],
  ['inline flex box in an underlined paragraph', `<p style="${RED}"><span style="display:inline-flex">WisteriaCourt</span></p>`, false],
  ['inline grid in an underlined paragraph', `<p style="${RED}"><span style="display:inline-grid">WisteriaCourt</span></p>`, false],
  ['float in an underlined paragraph', `<p style="${RED}"><span style="float:left">WisteriaCourt</span></p>`, false],
  ['float in an underlined flex container', `<div style="display:flex;${RED}"><span style="float:left">WisteriaCourt</span></div>`, false],
  ['absolutely positioned in an underlined paragraph', `<p style="${RED};position:relative;height:40px"><span style="position:absolute;left:0">WisteriaCourt</span></p>`, false],
  ['fixed in an underlined paragraph', `<p style="${RED}"><span style="position:fixed;left:20px;top:100px">WisteriaCourt</span></p>`, false],
  ['underlined link without a box', `<p><a href="#x" style="display:contents;color:#000;${RED}"><span>WisteriaCourt</span></a></p>`, false],
  ['blink line', '<p><span style="text-decoration:blink;color:#000">WisteriaCourt</span></p>', false],
  ['transparent line', '<p style="text-decoration:underline;text-decoration-color:transparent"><span>WisteriaCourt</span></p>', false],
  ['no decoration', '<p><a href="#x" style="color:#000;text-decoration:none"><span>WisteriaCourt</span></a></p>', false],
  ['SVG text in an underlined link', `<p><a href="#x" style="color:#f00;${RED}">${svgRed('', '<text x="0" y="28" style="font:24px serif;fill:#000"><tspan>WisteriaCourt</tspan></text>')}</a></p>`, false],
  ['underlined SVG text element', svgRed('', '<text x="0" y="28" style="font:24px serif;fill:#f00;text-decoration:underline"><tspan style="fill:#000">WisteriaCourt</tspan></text>'), true],
  ['underlined SVG root', svgRed('style="text-decoration:underline;fill:#f00"', '<text x="0" y="28" style="font:24px serif"><tspan style="fill:#000">WisteriaCourt</tspan></text>'), true],
  ['HTML in an SVG foreign object, in an underlined link', `<p><a href="#x" style="color:#000;${RED}">${svgRed('', '<foreignObject x="0" y="0" width="400" height="40"><div xmlns="http://www.w3.org/1999/xhtml" style="color:#000">WisteriaCourt</div></foreignObject>')}</a></p>`, false],
];
const colour = (equals, body, failed) => ({ declarations: [{ type: 'marker-computed-style', version: 1, marker: 'WisteriaCourt', property: 'color', equals }],
  body, failed: failed ? ['WisteriaCourt color'] : [] });

const CASES = [
  { name: 'correct contents', id: 'field-link-toc-complex-entries', body: entries() + lantern, failed: [] },
  { name: 'correct contents, control', id: 'field-link-toc-element-entries-control', body: entries() + lantern, failed: [] },
  // Colours in other notations are compared as the sRGB colour they paint.
  { name: 'correct contents in oklch() and color(srgb) notation', id: 'field-link-toc-simple-entries',
    body: entries('<a href="#_Toc90001" style="color:oklch(0 0 0);text-decoration:none">') +
      lantern.replace('color:#0563C1', 'color:color(srgb 0.0196078 0.388235 0.756863)'), failed: [] },
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
  { name: 'outside link drawn as black SVG text in a blue, underlined link', id: 'field-link-toc-complex-entries',
    body: entries() + `<p>See <a href="#_Toc90001" style="color:#0563C1;text-decoration:underline">${svgText('WisteriaLantern')}</a></p>`,
    failed: ['WisteriaLantern color', 'WisteriaLantern text-decoration-line'] },
  { name: 'correct simple fields', id: 'field-link-simple-hyperlink',
    body: arbor('<a href="https://example.com/wisteria-arbor" style="color:inherit;text-decoration:none">') + pergola, failed: [] },
  // A link's blue and underline reach none of the SVG text inside it: black SVG text in a default <a> is black, no line.
  { name: 'correct simple fields, WisteriaArbor as black SVG text in a default link', id: 'field-link-simple-hyperlink',
    body: `<p><a href="https://example.com/wisteria-arbor">${svgText('WisteriaArbor')}</a></p>` + pergola, failed: [] },
  { name: "review mutant (b'): WisteriaArbor as a link-blue underlined link", id: 'field-link-simple-hyperlink',
    body: arbor('<a href="https://example.com/wisteria-arbor">') + pergola,
    failed: ['WisteriaArbor color', 'WisteriaArbor text-decoration-line'] },
  { name: 'WisteriaArbor in the Hyperlink style', id: 'field-link-simple-hyperlink-control',
    body: arbor('<a href="https://example.com/wisteria-arbor" style="color:#0563C1;text-decoration:underline">') + pergola,
    failed: ['WisteriaArbor color', 'WisteriaArbor text-decoration-line'] },
  { name: 'WisteriaPergola as black SVG text in a blue, underlined link', id: 'field-link-simple-hyperlink',
    body: arbor('<a href="https://example.com/wisteria-arbor" style="color:inherit;text-decoration:none">') +
      `<p><a href="https://example.com/wisteria-pergola" style="color:#0563C1;text-decoration:underline">${svgText('WisteriaPergola')}</a></p>`,
    failed: ['WisteriaPergola color', 'WisteriaPergola text-decoration-line'] },
  { name: 'SVG text filled with the link colour', ...colour('rgb(5, 99, 193)',
    `<p><a href="#x" style="color:#0563C1">${svgText('WisteriaCourt', 'currentColor')}</a></p>`, false) },
  { name: 'SVG text filled with a gradient', ...colour('rgb(0, 0, 0)', '<svg width="300" height="30" xmlns="http://www.w3.org/2000/svg">' +
    '<defs><linearGradient id="g"><stop offset="0" stop-color="#000"/></linearGradient></defs>' +
    '<text x="0" y="20" style="font:16px serif;fill:url(#g)">WisteriaCourt</text></svg>', true) },
  { name: 'half-transparent text', ...colour('rgb(0, 0, 0)', '<p style="color:rgba(0, 0, 0, 0.5)">WisteriaCourt</p>', true) },
  ...paintProbes.map(([name, body, painted]) => ({ name, body, painted, failed: painted ? ['WisteriaCourt text-decoration-line'] : [],
    declarations: [{ type: 'marker-computed-style', version: 1, marker: 'WisteriaCourt', property: 'text-decoration-line', equals: 'none' }] })),
];

async function replay(browser, html, declarations) {
  const facts = await inspectReadableHtml(browser, html, declarations, 10000);
  const passed = execFileSync('python3', ['-c', 'import json,sys;from bench.html_artifacts import validate_declaration, computed_style_pass as p;' +
    'ds,os=json.load(sys.stdin);[validate_declaration(d) for d in ds];print(json.dumps([p(d,o,i) for i,(d,o) in enumerate(zip(ds,os))]))'],
    { input: JSON.stringify([declarations, facts.observations]), encoding: 'utf8' });
  return { facts, failed: JSON.parse(passed).flatMap((ok, i) => ok ? [] : [`${declarations[i].marker} ${declarations[i].property}`]) };
}

// Red pixels in a screenshot: the decoration colour of the paint probes, never the text's.
async function redPixels(browser, html) {
  const context = await browser.newContext({ viewport: { width: 640, height: 300 } });
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

test('link colour and painted decoration observations pass correct renderings, fail the review mutants and follow the paint', async () => {
  assert.ok(process.env.DOCXODUS_SOURCE_ROOT, 'Set DOCXODUS_SOURCE_ROOT to the built renderer');
  const { chromium } = createRequire(resolve(process.env.DOCXODUS_SOURCE_ROOT, 'npm/package.json'))('playwright');
  const browser = await chromium.launch({ headless: true, args: LAUNCH_ARGS,
    ...(process.env.DOCXODUS_CHROMIUM_PATH ? { executablePath: process.env.DOCXODUS_CHROMIUM_PATH } : {}) });
  const recorded = [];
  try {
    for (const c of CASES) {
      const declarations = c.declarations ?? styles(c.id);
      if (c.id) assert.equal(declarations.length, c.id.includes('simple-hyperlink') ? 4 : 8, c.id);
      const html = page(c.body);
      const { facts, failed } = await replay(browser, html, declarations);
      assert.deepEqual(failed, c.failed, c.name);
      if (c.painted !== undefined) {
        assert.equal((await redPixels(browser, html)) > 20, c.painted, c.name + ': painted red line');
      }
      recorded.push({ name: c.name, ...(c.id ? { id: c.id } : {}), declarations, html, failed: c.failed,
        ...(c.painted !== undefined ? { painted: c.painted } : {}), observations: facts.observations });
    }
    const inspectorSha256 = createHash('sha256').update(readFileSync(new URL('../bench/html_browser.mjs', import.meta.url))).digest('hex');
    if (process.env.LINK_STYLE_RECORD) {
      writeFileSync(RECORD, JSON.stringify({ schema: 1, inspectorSha256, browserVersion: browser.version(), cases: recorded }, null, 2) + '\n');
    } else {
      // The committed record must come from this observer and hold these cases.
      const committed = JSON.parse(readFileSync(RECORD, 'utf8'));
      assert.equal(committed.inspectorSha256, inspectorSha256, 'Record the observations again: LINK_STYLE_RECORD=1');
      const strip = cases => cases.map(({ observations, ...rest }) => rest);
      assert.deepEqual(strip(committed.cases), strip(recorded), 'Record the observations again: LINK_STYLE_RECORD=1');
    }
  } finally { await browser.close(); }
});
