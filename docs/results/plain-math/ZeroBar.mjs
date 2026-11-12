// Negative paint control derived only from this benchmark's retained authored HTML.
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
const [source, html, output] = process.argv.slice(2);
const { chromium } = createRequire(resolve(source, 'npm/package.json'))('playwright');
const browser = await chromium.launch({ executablePath: process.env.DOCXODUS_CHROMIUM_PATH || '/opt/google/chrome/chrome', chromiumSandbox: true });
try {
  const page = await browser.newPage({ javaScriptEnabled: false, offline: true });
  await page.setContent(await readFile(html, 'utf8'));
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => document.querySelector('mfrac').setAttribute('linethickness', '0'));
  await writeFile(output, await page.pdf({ preferCSSPageSize: true, printBackground: true }));
} finally { await browser.close(); }
