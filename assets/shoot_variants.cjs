/* 通用评审图渲染器
   用法：
     node shoot_gen.cjs <html文件名> <输出目录> <URL参数名> "<名1|名2|名3>" [断言字体族]
   例：
     node shoot_gen.cjs v5_cover_v3.html 封面字号档_v5 size "58|70|84"
   会依次渲染 ?size=0 / ?size=1 / ... 并保存为 名1.png / 名2.png ...
*/
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const ROOT = process.env.PROJ_ROOT || process.cwd();
const VIDEO = path.join(ROOT, 'video');
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const [html, outName, param, nameList, wantFont] = process.argv.slice(2);
if (!html || !outName || !param || !nameList) {
  console.error('用法: node shoot_gen.cjs <html> <outdir> <param> "名1|名2" [字体族]');
  process.exit(1);
}
const OUT = path.join(ROOT, outName);
const NAMES = nameList.split('|');

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none',
           '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
  const base = 'file:///' + path.join(VIDEO, html).replace(/\\/g, '/');

  for (let i = 0; i < NAMES.length; i++) {
    await page.goto(`${base}?${param}=${i}&gt=${i * 11}`, { waitUntil: 'load' });
    // 字体必须真正就绪，否则会静默回退到系统字体，截图看着没问题其实是假的
    await page.evaluate('document.fonts.ready');
    await new Promise(r => setTimeout(r, 420));

    if (wantFont) {
      const info = await page.evaluate((want) => {
        const list = [...document.fonts].map(f => ({ family: f.family, status: f.status }));
        const hits = list.filter(f => f.family.replace(/["']/g, '') === want);
        const allLoaded = hits.length > 0 && hits.every(f => f.status === 'loaded');
        return { n: hits.length, allLoaded, st: hits.map(f => f.status).join(',') };
      }, wantFont);
      if (!info.allLoaded) {
        console.log(`  !! ${wantFont} 未全部 loaded (n=${info.n}, status=${info.st}) —— 截图可能是回退字体`);
      } else {
        console.log(`  ok ${wantFont} loaded (${info.n} 个字重)`);
      }
    }

    await page.screenshot({
      type: 'png',
      path: path.join(OUT, NAMES[i] + '.png'),
      clip: { x: 0, y: 0, width: 1080, height: 1920 }
    });
    console.log('shot', i, NAMES[i]);
  }
  await browser.close();
  console.log('DONE ->', OUT);
})().catch(e => { console.error('ERR', (e && e.stack) || e); process.exit(1); });
