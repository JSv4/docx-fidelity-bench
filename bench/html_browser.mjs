// Original DOM observer. It reads the delivered artifact in a separate, script-disabled page;
// it does not call the renderer's layout or diagnostic helpers.
import { createHash } from 'node:crypto';
export const VERSION = 1;
export const VIEWPORT = { width: 1280, height: 1024 };
export const LAUNCH_ARGS = ['--force-color-profile=srgb', '--font-render-hinting=none'];
export const needsBrowser = declarations => declarations.some(d => d.type !== 'marker-attribute');

export function collectReadableFacts(declarations) {
  const rectangle = r => [r.left, r.top, r.right, r.bottom];
  const portRectangle = element => {
    const r = element.getBoundingClientRect();
    const sx = element.offsetWidth ? r.width / element.offsetWidth : 1;
    const sy = element.offsetHeight ? r.height / element.offsetHeight : 1;
    const left = r.left + element.clientLeft * sx, top = r.top + element.clientTop * sy;
    return [left, top, left + element.clientWidth * sx, top + element.clientHeight * sy];
  };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const segments = [];
  let text = '', previousBlock = null, node;
  while ((node = walker.nextNode())) {
    if (segments.length > 100000) throw new Error('Delivered HTML exceeds the observer node limit');
    let hidden = false;
    for (let parent = node.parentElement; parent; parent = parent.parentElement) {
      const style = getComputedStyle(parent);
      if (parent.matches('script,style,template,head,[hidden]') || style.display === 'none' ||
          style.visibility === 'hidden' || Number(style.opacity) === 0 || parseFloat(style.fontSize) === 0) {
        hidden = true; break;
      }
    }
    if (hidden) continue;
    const block = node.parentElement?.closest('p,div,section,aside,li,td,h1,h2,h3,h4,h5,h6');
    if (block !== previousBlock) text += '\n';
    previousBlock = block;
    segments.push({ node, start: text.length, end: text.length + node.data.length });
    text += node.data;
  }
  const normalized = text.replace(/\s+/g, ' ').trim();
  const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const observations = [];
  for (let index = 0; index < declarations.length; index++) {
    const declaration = declarations[index];
    if (declaration.type === 'marker-attribute') continue;
    if (declaration.type !== 'marker-readable') throw new Error('Unknown browser HTML assertion');
    const pattern = new RegExp('(?<![\\p{L}\\p{N}_])' + escape(declaration.marker) + '(?![\\p{L}\\p{N}_])', 'gu');
    const matches = Array.from(text.matchAll(pattern));
    const facts = { index, marker: declaration.marker, matches: matches.length, text: normalized, ports: [] };
    if (matches.length !== 1) { observations.push(facts); continue; }
    const start = matches[0].index, end = start + declaration.marker.length;
    const first = segments.find(s => s.start <= start && s.end > start);
    const last = segments.find(s => s.start < end && s.end >= end);
    if (!first || !last) throw new Error('Marker offsets do not map to delivered text nodes');
    let block = first.node.parentElement;
    while (block?.parentElement && !['block', 'flow-root', 'flex', 'grid', 'list-item', 'table-cell'].includes(getComputedStyle(block).display)) {
      block = block.parentElement;
    }
    // Use the same visible-node inventory as the marker search. textContent would
    // count a hidden middle word as readable even when only the final word paints.
    facts.blockText = segments.filter(s => block?.contains(s.node)).map(s => s.node.data)
      .join('').replace(/\s+/g, ' ').trim();
    const range = document.createRange();
    range.setStart(first.node, start - first.start); range.setEnd(last.node, end - last.start);
    const ports = [];
    for (let parent = first.node.parentElement; parent; parent = parent.parentElement) {
      const style = getComputedStyle(parent);
      if (['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowY) ||
          ['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowX)) {
        ports.push({ element: parent, overflowY: style.overflowY, overflowX: style.overflowX });
      }
    }
    // Move only user-scrollable ports below. scrollIntoView could silently scroll a
    // hidden-overflow ancestor and make clipped content appear user-accessible.
    facts.before = rectangle(range.getBoundingClientRect());
    for (const port of ports) {
      const element = port.element, r = range.getBoundingClientRect(), clip = portRectangle(element);
      const outer = element.getBoundingClientRect();
      const sy = element.offsetHeight ? outer.height / element.offsetHeight : 1;
      const sx = element.offsetWidth ? outer.width / element.offsetWidth : 1;
      const observation = { overflowY: port.overflowY, overflowX: port.overflowX,
        before: rectangle(r), clipBefore: clip, scrollHeight: element.scrollHeight, clientHeight: element.clientHeight };
      let top = element.scrollTop, left = element.scrollLeft;
      if (['auto', 'scroll'].includes(port.overflowY)) {
        if (r.bottom > clip[3]) top += (r.bottom - clip[3]) / sy;
        else if (r.top < clip[1]) top += (r.top - clip[1]) / sy;
      }
      if (['auto', 'scroll'].includes(port.overflowX)) {
        if (r.right > clip[2]) left += (r.right - clip[2]) / sx;
        else if (r.left < clip[0]) left += (r.left - clip[0]) / sx;
      }
      element.scrollTo({ top, left, behavior: 'instant' });
      facts.ports.push(observation);
    }
    const final = range.getBoundingClientRect();
    window.scrollBy({ top: final.bottom > innerHeight ? final.bottom - innerHeight : Math.min(0, final.top),
      left: final.right > innerWidth ? final.right - innerWidth : Math.min(0, final.left), behavior: 'instant' });
    facts.after = rectangle(range.getBoundingClientRect());
    facts.viewport = [0, 0, document.documentElement.clientWidth, document.documentElement.clientHeight];
    facts.ports.forEach((observation, i) => { observation.clipAfter = portRectangle(ports[i].element); });
    observations.push(facts);
  }
  return observations;
}

export async function inspectReadableHtml(browser, html, declarations, timeoutMs) {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new Error('No HTML observation budget remains');
  let context, timer;
  const work = (async () => {
    context = await browser.newContext({ viewport: VIEWPORT, javaScriptEnabled: false, offline: true });
    const page = await context.newPage();
    page.setDefaultTimeout(timeoutMs);
    await page.emulateMedia({ media: 'screen' });
    await page.setContent(html, { waitUntil: 'load', timeout: timeoutMs });
    await page.evaluate(() => document.fonts.ready);
    return { schema: VERSION, htmlSha256: createHash('sha256').update(html).digest('hex'),
      policy: { viewport: VIEWPORT, javaScriptEnabled: false, offline: true, media: 'screen' },
      observations: await page.evaluate(collectReadableFacts, declarations) };
  })();
  const expired = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error('HTML observation exceeded the shared conversion budget')), timeoutMs);
  });
  try { return await Promise.race([work, expired]); }
  finally { clearTimeout(timer); if (context) await context.close(); }
}
