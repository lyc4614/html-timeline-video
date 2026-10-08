// 实测画面运动量：每 STEP 秒渲染一帧并缩到小图，交给 Python 做帧间差。
// 为什么不用静态估算 `lt-N`：
//   · 顺序入场写成 (lt-1.6-i*1.5)，静态扫只能拿到基数 1.6，
//      实际最后一条在 1.6+4×1.5=7.6，误差 6 秒。
//   · 连续动画（曲线逐点生长 cur.apply(lt,...)）根本没有 lt-N。
// 帧间差才是「画面到底动没动」的真值。
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const ROOT = __dirname.replace(/\\/g, '/').replace('/_tools', '');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TARGET = process.argv[2] || 'index.html';
const STEP = parseFloat(process.argv[3] || '0.5');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    userDataDir: path.join(require('os').tmpdir(), 'html-timeline-chrome-profile'),
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  // deviceScaleFactor 0.25：输出 270×480 小图，CSS 布局完全不变
  await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 0.25 });
  await page.goto('file:///' + path.join(ROOT, TARGET).replace(/\\/g, '/'), { waitUntil: 'load' });
  await page.waitForFunction('typeof window.__render === "function"');

  const DUR = await page.evaluate('window.__DUR || (typeof DUR!=="undefined"?DUR:0)');
  const out = path.join(ROOT, '_motion');
  fs.rmSync(out, { recursive: true, force: true });
  fs.mkdirSync(out, { recursive: true });

  const end = DUR || 202.366;
  let n = 0;
  for (let t = 0; t <= end; t += STEP) {
    await page.evaluate(tt => window.__render(tt), t);
    await page.screenshot({ path: path.join(out, 'm' + String(n).padStart(4, '0') + '.png') });
    n++;
  }
  console.log('输出 %d 帧到 _motion/，步长 %.2fs，总时长 %.2fs', n, STEP, end);
  await browser.close();
})().catch(e => { console.log('ERROR', e && e.stack || e); process.exit(1); });
