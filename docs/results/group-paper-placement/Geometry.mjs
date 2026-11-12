// Read delivered HTML only; compare its group frames with the independent source proof.
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';

const [sourceArg, captureArg] = process.argv.slice(2);
const source = resolve(sourceArg), folder = resolve(captureArg);
const capture = JSON.parse(await readFile(resolve(folder, 'capture.json'), 'utf8'));
const { chromium } = createRequire(resolve(source, 'npm-export/package.json'))('playwright-core');
const browser = await chromium.launch({ executablePath: '/opt/google/chrome/chrome', chromiumSandbox: true });
try {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 1600, height: 1200 } });
  await context.route('**/*', route => route.abort());
  const page = await context.newPage();
  await page.emulateMedia({ media: 'print' });
  for (const record of capture.cases.filter(c => c.status === 'delivered')) {
    const html = await readFile(resolve(folder, record.id, 'candidate.html'), 'utf8');
    await page.setContent(html);
    await page.evaluate(() => document.fonts.ready);
    const geometry = await page.evaluate(() => {
      const page = document.querySelector('.page-box');
      if (!page) throw new Error('Missing physical page');
      const physical = page.getBoundingClientRect();
      const paper = (page.querySelector('.page-markup-page') ?? page).getBoundingClientRect();
      const frames = {};
      for (const box of page.querySelectorAll('[data-docx-textbox]')) {
        const label = box.textContent.trim(), rect = box.getBoundingClientRect();
        if (!['SedgeNear', 'SedgeFar'].includes(label) || label in frames) throw new Error('Unexpected group story');
        frames[label] = [(rect.left - paper.left) * 612 / paper.width,
          (rect.top - paper.top) * 792 / paper.height, rect.width * 612 / paper.width, rect.height * 792 / paper.height];
      }
      return { framesPt: frames, sourcePaperOnPhysicalPt: [(paper.left - physical.left) * 612 / physical.width,
        (paper.top - physical.top) * 792 / physical.height, paper.width * 612 / physical.width, paper.height * 792 / physical.height] };
    });
    await writeFile(resolve(folder, record.id, 'group-geometry.json'), JSON.stringify({
      htmlSha256: createHash('sha256').update(html).digest('hex'), browserVersion: browser.version(), ...geometry,
    }, null, 2) + '\n');
  }
  await context.close();
} finally { await browser.close(); }
