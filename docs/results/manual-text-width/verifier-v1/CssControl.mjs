import { createRequire } from 'node:module';
import { resolve } from 'node:path';
const { chromium } = createRequire(resolve(process.argv[2], 'npm-export/package.json'))('playwright-core');
const browser = await chromium.launch({ executablePath:'/usr/bin/google-chrome', chromiumSandbox:true });
try {
 for (const transformed of [false, true]) {
  const page = await browser.newPage();
  await page.setContent(`<style>@page{size:612pt 792pt;margin:72pt}body{margin:0}p{font:12pt/18pt 'Liberation Mono';margin:0}.box{display:inline-block;width:100pt}.inner{display:inline-block;transform-origin:left top;${transformed?'transform:scaleX(2)':''}}</style><p><span class=box><span class=inner>Jun</span></span><span class=box><span class=inner>iper</span></span></p>`);
  await page.evaluate(()=>document.fonts.ready);
  await page.pdf({ path:`${process.argv[3]}/css-${transformed ? "transformed" : "untransformed"}.pdf`,preferCSSPageSize:true });
  console.log(transformed,await page.locator('.inner').evaluateAll(es=>es.map(e=>({x:e.getBoundingClientRect().x*.75,width:e.getBoundingClientRect().width*.75}))));
  await page.close();
 }
} finally { await browser.close(); }
