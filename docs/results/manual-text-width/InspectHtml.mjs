// Measure the retained offline export independently of the renderer implementation.
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
const [source, run] = process.argv.slice(2);
const { chromium } = createRequire(resolve(source, 'npm-export/package.json'))('playwright-core');
const browser = await chromium.launch({ executablePath:'/usr/bin/google-chrome', chromiumSandbox:true });
const manifest = JSON.parse(await readFile(resolve(run, 'manifest.json'), 'utf8'));
const records = [];
try {
  for (const entry of manifest.cases) {
    const path = resolve(run, 'candidate', entry.id, 'candidate.html');
    const page = await browser.newPage();
    await page.goto(pathToFileURL(path).href); await page.emulateMedia({ media:'print' });
    await page.evaluate(() => document.fonts.ready);
    const groups = await page.locator('[data-docx-fit-text-group]').evaluateAll(elements => elements.map(outer => {
      const inner = outer.firstElementChild, range = document.createRange();
      range.selectNodeContents(inner);
      return { text:outer.textContent, carrierWidthPt:outer.getBoundingClientRect().width*.75,
        paintedWidthPt:range.getBoundingClientRect().width*.75 };
    }));
    const variant = entry.id.replace('manual-text-width-', '');
    const texts = variant === 'control' ? [] : variant === 'separate-100' ? ['Jun', 'iper'] : ['Juniper'];
    const width = variant === 'single-20' ? 20 : 100;
    const passed = groups.length === texts.length && groups.every((group, i) => group.text === texts[i]
      && Math.abs(group.carrierWidthPt-width) <= .1 && Math.abs(group.paintedWidthPt-width) <= .1);
    records.push({ id:entry.id, htmlSha256:createHash('sha256').update(await readFile(path)).digest('hex'),
      expectedTexts:texts, expectedWidthPt:width, tolerancePt:.1, groups, passed });
    await page.close();
  }
} finally { await browser.close(); }
await writeFile(resolve(run, 'candidate-html-widths.json'), JSON.stringify(records,null,2)+'\n');
if (records.some(record => !record.passed)) throw new Error('Offline HTML carrier or glyph width failed');
console.log(`Verified ${records.length} offline HTML documents`);
