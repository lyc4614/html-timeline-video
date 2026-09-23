/* 按时间点抽静帧，用于逐镜头质检
   用法: node shoot_at.cjs <输出目录> "<t1|t2|t3>" "<名1|名2|名3>"
   对每个 t 调用页面的 window.__render(t) 再截图 —— 与正式渲染走同一条渲染路径，
   所以静帧看到的就是成片里的那一帧。
   工程根目录：优先取环境变量 PROJ_ROOT，否则取当前工作目录。 */
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const ROOT = process.env.PROJ_ROOT || process.cwd();
const VIDEO = path.join(ROOT, 'video');
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const [outName, tList, nameList] = process.argv.slice(2);
const OUT = path.join(ROOT, outName);
const TS = tList.split('|').map(Number);
const NAMES = nameList.split('|');
if (TS.length !== NAMES.length) { console.error('时间点与名称数量不一致'); process.exit(1); }

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
  page.on('pageerror', e => console.log('  PAGE ERROR:', e.message));

  const url = 'file:///' + path.join(VIDEO, 'index.html').replace(/\\/g, '/');
  await page.goto(url, { waitUntil: 'load' });
  await page.evaluate('document.fonts.ready');
  await new Promise(r => setTimeout(r, 600));

  // 字体断言：实际用到的两个字重必须 loaded
  const finfo = await page.evaluate(() => {
    const used = new Set();
    document.querySelectorAll('.gold,.bignum,.vscard .v,.glass .sc,.brandname,.hz-m,.hz-s,.hz-o')
      .forEach(el => used.add(getComputedStyle(el).fontWeight));
    const list = [...document.fonts].map(f => ({ family: f.family, weight: f.weight, status: f.status }));
    return { used: [...used], list };
  });
  console.log('  用到的字重:', finfo.used.join(', '));
  finfo.list.forEach(f => console.log(`    FontFace ${f.family} ${f.weight} -> ${f.status}`));

  for (let i = 0; i < TS.length; i++) {
    await page.evaluate((t) => window.__render(t), TS[i]);
    await new Promise(r => setTimeout(r, 260));
    await page.screenshot({ type: 'png', path: path.join(OUT, NAMES[i] + '.png'),
      clip: { x: 0, y: 0, width: 1080, height: 1920 } });
    console.log(`  t=${TS[i]}s -> ${NAMES[i]}.png`);
  }
  await browser.close();
  console.log('DONE ->', OUT);
})().catch(e => { console.error('ERR', (e && e.stack) || e); process.exit(1); });
