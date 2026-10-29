import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

// Args: installed pinned Playwright module, generated HTML directory, output directory.
const { chromium } = await import(pathToFileURL(resolve(process.argv[2])).href);
const input = resolve(process.argv[3]), output = resolve(process.argv[4]);
const binding = JSON.parse(await readFile(resolve(input, 'capture.json'), 'utf8'));
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1800, height: 950 }, offline: true });
  const page = await context.newPage();
  for (const record of binding.cases) {
    await page.goto(pathToFileURL(resolve(input, record.id + '.html')).href);
    await page.evaluate(() => document.fonts.ready);
    const png = await page.screenshot({ path: resolve(output, record.id + '.png'), fullPage: true });
    record.pngSha256 = createHash('sha256').update(png).digest('hex');
  }
} finally { await browser.close(); }
await writeFile(resolve(output, 'capture.json'), JSON.stringify(binding, null, 2) + '\n');
