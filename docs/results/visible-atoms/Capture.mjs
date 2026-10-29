import { readdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

// Arguments: pinned Playwright module, generated HTML folder, PNG destination.
const { chromium } = await import(pathToFileURL(resolve(process.argv[2])).href);
const input = resolve(process.argv[3]), output = resolve(process.argv[4]);
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1100, height: 620 }, offline: true });
  const page = await context.newPage();
  const files = (await readdir(input)).filter(n => n.endsWith('.html')
    && !n.endsWith('-accepted.html') && !n.endsWith('-rejected.html')).sort();
  for (const name of files) {
    await page.goto(pathToFileURL(resolve(input, name)).href);
    for (const frame of page.frames()) await frame.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: resolve(output, name.replace('.html', '.png')), fullPage: true });
  }
} finally { await browser.close(); }
