// check.cjs —— 定点抽帧质检
// 用法：node check.cjs 1.5 10 44 74 97 145
// 输出到 <VIDEO_ROOT>/check/t-<秒>.png
// 提醒：镜头有动画时，要抽「动画完成时刻」而不是刚进镜头的时刻，
//       否则会拍到元素还没出来的中间态，误判成"空场"。
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const ROOT = process.env.VIDEO_ROOT || __dirname;
const OUT = path.join(ROOT, 'check');
const W = +(process.env.VIDEO_W || 1080);
const H = +(process.env.VIDEO_H || 1920);

function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const cands = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/chromium',
  ];
  for (const p of cands) if (fs.existsSync(p)) return p;
  throw new Error('找不到 Chrome/Edge，请设 CHROME_PATH');
}

const times = process.argv.slice(2).map(Number).filter(n => !isNaN(n));
if (!times.length) { process.stdout.write('用法: node check.cjs <秒> [秒...]\n'); process.exit(1); }

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: findChrome(), headless: 'new',
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  await page.goto('file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/'), { waitUntil: 'load' });
  await page.waitForFunction('typeof window.__render === "function"');

  for (const t of times) {
    await page.evaluate((tt) => window.__render(tt), t);
    const f = path.join(OUT, 't-' + String(t).replace('.', '_') + '.png');
    await page.screenshot({ type: 'png', path: f, clip: { x: 0, y: 0, width: W, height: H } });
    process.stdout.write('shot t=' + t + ' -> ' + f + '\n');
  }
  await browser.close();
})().catch(e => { process.stdout.write('ERROR ' + (e && e.stack || e) + '\n'); process.exit(1); });
