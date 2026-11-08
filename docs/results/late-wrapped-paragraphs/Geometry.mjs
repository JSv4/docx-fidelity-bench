// Measure every delivered picture in physical page coordinates, independently of PageMap.
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';

const [source, folder] = process.argv.slice(2).map(p => resolve(p));
const { chromium } = createRequire(resolve(source, 'npm-export/package.json'))('playwright-core');
const capture = JSON.parse(await readFile(resolve(folder, 'capture.json')));
const browser = await chromium.launch({ executablePath: process.env.DOCXODUS_CHROMIUM_PATH || '/opt/google/chrome/chrome', chromiumSandbox: true });
try {
  const page = await browser.newPage();
  for (const record of capture.cases.filter(c => c.status === 'delivered')) {
    const html = await readFile(resolve(folder, record.id, 'candidate.html'));
    if (createHash('sha256').update(html).digest('hex') !== record.htmlSha256) throw new Error('Changed HTML');
    await page.setContent(html.toString(), { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    const pictures = await page.locator('.page-box').evaluateAll(pages => pages.flatMap((page, index) => {
      const box = page.getBoundingClientRect();
      return [...page.querySelectorAll('img')].map(image => {
        const rect = image.getBoundingClientRect();
        return { page: index + 1, rect: [rect.left - box.left, rect.top - box.top, rect.right - box.left, rect.bottom - box.top].map(v => v * .75) };
      });
    }));
    await writeFile(resolve(folder, record.id, 'pictures.json'), JSON.stringify({
      htmlSha256: record.htmlSha256, browserVersion: browser.version(), pictures,
    }, null, 2) + '\n');
  }
} finally { await browser.close(); }
