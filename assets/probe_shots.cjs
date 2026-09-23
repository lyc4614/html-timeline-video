/* 用 DOM 几何量「镜头内容」的真实占位 —— 不再靠像素扫描猜。
   对每个镜头，取 .stage 内所有可见子元素的 bounding rect 并集，
   排除常驻层（顶部 logo / 章节轨 / 字幕带 / 章节角标 / 进度条）。
   这是唯一可靠的方法：像素扫描分不清常驻层和内容。
   用法：CHROME_PATH=... node probe_shots.cjs <index.html 绝对路径>
   （SHOTS 时间窗与 SAFE_TOP/SAFE_BOT 按你自己的工程改） */
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const TARGET = process.argv[2] || path.resolve('index.html');

const CANDIDATES = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
].filter(Boolean);
const exe = CANDIDATES.find(p => fs.existsSync(p));
if (!exe) { console.error('找不到 Chrome，请设 CHROME_PATH 环境变量'); process.exit(2); }

const SHOTS = [
  [0.0, 3.1], [3.1, 5.6], [5.6, 12.0], [12.0, 17.6], [17.6, 23.6], [23.6, 31.7],
  [31.7, 35.5], [35.5, 40.9], [40.9, 48.9], [48.9, 57.1], [57.1, 61.2], [61.2, 67.0],
  [67.0, 71.6], [71.6, 81.1], [81.1, 85.2], [85.2, 88.5], [88.5, 96.0], [96.0, 100.7],
  [100.7, 111.7], [111.7, 114.9], [114.9, 119.1], [119.1, 128.1], [128.1, 134.0],
  [134.0, 140.3], [140.3, 147.9],
];
const SAFE_TOP = 196, SAFE_BOT = 1480, H = 1920;

(async () => {
  const browser = await puppeteer.launch({
    executablePath: exe, headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--force-device-scale-factor=1',
           '--hide-scrollbars', '--allow-file-access-from-files'],
    defaultViewport: { width: 1080, height: 1920, deviceScaleFactor: 1 },
  });
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('[PAGE ERROR]', e.message));
  await page.goto('file:///' + TARGET.replace(/\\/g, '/'),
                  { waitUntil: 'load', timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);

  const out = [];
  for (let k = 0; k < SHOTS.length; k++) {
    const [st, et] = SHOTS[k];
    const mid = st + (et - st) * 0.5;
    await page.evaluate(tt => window.__render(tt), mid);
    await new Promise(r => setTimeout(r, 180));
    const g = await page.evaluate(() => {
      const EXCL = ['#toplogo', '#rail', '#sub', '.chap', '#pbar'];
      const stages = [...document.querySelectorAll('.stage')];
      // 只取当前可见的 stage
      const vis = stages.filter(s => {
        const cs = getComputedStyle(s);
        return cs.opacity > 0.02 && s.getBoundingClientRect().height > 0;
      });
      if (!vis.length) return null;
      const s = vis[vis.length - 1];
      let y0 = Infinity, y1 = -Infinity, x0 = Infinity, x1 = -Infinity, n = 0;
      const kids = [...s.querySelectorAll('*')];
      for (const el of kids) {
        if (EXCL.some(sel => el.matches(sel) || el.closest(EXCL))) continue;
        const cs = getComputedStyle(el);
        if (cs.opacity < 0.03 || cs.display === 'none' || cs.visibility === 'hidden') continue;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) continue;
        y0 = Math.min(y0, r.top); y1 = Math.max(y1, r.bottom);
        x0 = Math.min(x0, r.left); x1 = Math.max(x1, r.right);
        n++;
      }
      const stageBox = s.getBoundingClientRect();
      return n ? { y0, y1, x0, x1, n,
                   stageTop: stageBox.top, stageBot: stageBox.bottom } : null;
    });
    out.push({ k: k + 1, mid, g });
  }
  await browser.close();

  console.log('镜'.padStart(4) + '时刻'.padStart(8) + '元素'.padStart(6) +
              '内容顶'.padStart(9) + '内容底'.padStart(9) + '内容高'.padStart(9) +
              '占安全区'.padStart(10) + '  诊断');
  const covs = [];
  for (const r of out) {
    if (!r.g) { console.log(String(r.k).padStart(4) + r.mid.toFixed(2).padStart(8) + '   —— 无可见内容'); covs.push(0); continue; }
    const { y0, y1, n } = r.g;
    const hgt = y1 - y0;
    const safeH = SAFE_BOT - SAFE_TOP;
    const cov = hgt * 100 / safeH;
    let diag = '';
    if (y0 < SAFE_TOP - 4) diag += ' 撞顶';
    if (y1 > SAFE_BOT + 4) diag += ' 溢出底';
    if (cov < 45) diag += ' 偏矮';
    covs.push(cov);
    console.log(String(r.k).padStart(4) + r.mid.toFixed(2).padStart(8) + String(n).padStart(6) +
                String(Math.round(y0)).padStart(9) + String(Math.round(y1)).padStart(9) +
                String(Math.round(hgt)).padStart(9) + (cov.toFixed(1) + '%').padStart(10) + '  ' + diag);
  }
  const s = covs.slice().sort((a, b) => a - b);
  console.log(`\n占安全区高度 中位 ${s[s.length >> 1].toFixed(1)}%  最低 ${s[0].toFixed(1)}%  最高 ${s[s.length - 1].toFixed(1)}%`);
  console.log('偏矮(<45%)镜头: ' + covs.map((c, i) => [i + 1, c]).filter(([, c]) => c < 45).map(([k, c]) => `${k}(${c.toFixed(0)}%)`).join(' '));
})();
