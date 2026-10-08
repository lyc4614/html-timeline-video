// render.cjs —— HTML 时间轴动效页 → 逐帧截图 → ffmpeg 编码
// 用法：
//   node render.cjs              全片渲染 + 编码
//   node render.cjs --test       散布采样 120 帧测速（不编码）
//   node render.cjs --test --noenc
// 环境变量（都可省，有默认值/自动探测）：
//   VIDEO_ROOT   工程目录（含 index.html），默认脚本所在目录
//   CHROME_PATH  浏览器可执行文件，默认自动探测 Chrome → Edge
//   FFMPEG_PATH  ffmpeg 可执行文件，默认 from PATH
//   VIDEO_W      画布宽，默认 1080（竖屏）。横版传 1920
//   VIDEO_H      画布高，默认 1920（竖屏）。横版传 1080
//   VIDEO_FPS    帧率，默认 30
//   VIDEO_CRF    H.264 质量，默认 16（越小越清、文件越大；成片交付常用 18~21）
//
// 横版示例（PowerShell）：$env:VIDEO_W=1920; $env:VIDEO_H=1080; node render.cjs
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = process.env.VIDEO_ROOT || __dirname;
const TEST = process.argv.includes('--test');
// --test 写 frames_test/ 而不是 frames/：否则「全渲→测速→编码」这个顺序
// 会用散布时刻的画面覆盖前 N 帧，成片错乱且不报错（ffmpeg 按首帧尺寸统一缩放，
// 画面看着正常，内容已经不对）。这是我给上游仓库提的 S2 缺陷。
const FRAMES = path.join(ROOT, TEST ? 'frames_test' : 'frames');
const W = +(process.env.VIDEO_W || 1080);
const H = +(process.env.VIDEO_H || 1920);
const FPS = +(process.env.VIDEO_FPS || 30);
const CRF = String(process.env.VIDEO_CRF || 16);
const NOENC = process.argv.includes('--noenc');

function firstExisting(list) {
  for (const p of list) if (p && fs.existsSync(p)) return p;
  return null;
}
function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const cands = [
    (process.env.LOCALAPPDATA || '') + '/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
  ];
  const hit = firstExisting(cands);
  if (!hit) throw new Error('找不到 Chrome/Edge，请设 CHROME_PATH');
  return hit;
}
function findFfmpeg() {
  if (process.env.FFMPEG_PATH) return process.env.FFMPEG_PATH;
  try {
    const p = execFileSync(process.platform === 'win32' ? 'where' : 'which', ['ffmpeg'], { encoding: 'utf8' })
      .split(/\r?\n/).map(s => s.trim()).filter(Boolean)[0];
    if (p && fs.existsSync(p)) return p;
  } catch (_) {}
  // Windows WinGet 安装路径兜底
  const base = path.join(process.env.LOCALAPPDATA || '', 'Microsoft/WinGet/Packages');
  if (fs.existsSync(base)) {
    for (const d of fs.readdirSync(base)) {
      if (!/FFmpeg/i.test(d)) continue;
      const sub = path.join(base, d);
      for (const v of fs.readdirSync(sub)) {
        const p = path.join(sub, v, 'bin', process.platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg');
        if (fs.existsSync(p)) return p;
      }
    }
  }
  throw new Error('找不到 ffmpeg，请设 FFMPEG_PATH');
}

const log = (m) => process.stdout.write(m + '\n');

(async () => {
  if (!fs.existsSync(FRAMES)) fs.mkdirSync(FRAMES, { recursive: true });
  const CHROME = findChrome();

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    // 必须给独立 userDataDir：本机 Chrome 若正在运行，共用默认 profile 时
    // headless 会「启动即退」，报错只有一句空泛的 connect 失败（踩过）。
    userDataDir: path.join(require('os').tmpdir(), 'html-timeline-chrome-profile'),
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files',
           '--disable-gpu', '--disable-dev-shm-usage']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });

  const url = 'file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/');
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction('typeof window.__render === "function"');

  // 字体预热 —— 不能只等 document.fonts.ready。
  // ⚠ fonts.ready 在「没有任何 pending 请求」时会**立刻 resolve**：实测照抄下面这段
  //   「push(ready) → await → 等 400ms」之后，4 个 @font-face 仍然全是 unloaded。
  //   后果是文本首次可见的那几帧被以回退字体截走（font-display 默认 block → 直接空白），
  //   而且不报错、验收也查不出来（PSNR 只比成片与帧序列，两边一样错）。
  // 正确做法：用每个声明的 face 主动 load 一次，再断言。
  await page.evaluate(async () => {
    await Promise.all([...document.fonts].map(f =>
      document.fonts.load(`${f.weight} 64px "${f.family}"`, '测试文字0123456789').catch(() => {})));
    await document.fonts.ready;
    // <img> 也要等；onerror 也要 resolve，否则路径写错会卡到超时
    const pend = [].slice.call(document.images)
      .filter(im => !(im.complete && im.naturalWidth))
      .map(im => new Promise(r => { im.onload = r; im.onerror = r; }));
    await Promise.all(pend);
  });
  await new Promise(r => setTimeout(r, 300));
  // 断言：预热之后每个 face 都必须是 loaded。**不通过就中止** ——
  // 字体没生效会毁掉整片，而这是几十分钟的渲染，宁可早停。
  // （旧版的判据是「只查实际用到的 family/weight」，但它扫的是 #root * 里**所有**元素，
  //   含尚未入场的隐藏镜头 → 必然报一堆假警告，警告久了就没人看。）
  const fontCheck = await page.evaluate(() => ({
    total: document.fonts.size,
    loaded: [...document.fonts].filter(f => f.status === 'loaded').length,
    bad: [...document.fonts].filter(f => f.status !== 'loaded').map(f => `${f.family}/${f.weight}`),
  }));
  log(`fonts: ${fontCheck.loaded}/${fontCheck.total} loaded` +
      (fontCheck.bad.length ? '  未加载: ' + fontCheck.bad.join(', ') : ''));
  if (fontCheck.total > 0 && fontCheck.bad.length) {
    log('✗ 字体未就绪 —— 继续渲会得到回退字体的画面，已中止');
    process.exit(5);
  }

  const DUR = await page.evaluate('window.__duration');
  let total = Math.round(DUR * FPS);
  let times = null;
  if (TEST) {
    // 关键：散布采样覆盖全片。只测前 N 帧会被最简单的封面段带偏。
    const n = 120, step = DUR / n;
    times = Array.from({ length: n }, (_, i) => i * step);
    total = n;
  }
  log(`duration=${DUR}s fps=${FPS} totalFrames=${total}`);

  const t0 = Date.now();
  for (let i = 0; i < total; i++) {
    const t = times ? times[i] : i / FPS;
    await page.evaluate((tt) => window.__render(tt), t);
    const file = path.join(FRAMES, 'f-' + String(i).padStart(5, '0') + '.png');
    await page.screenshot({ type: 'png', path: file, clip: { x: 0, y: 0, width: W, height: H } });
    if (i % 100 === 0 || i === total - 1) {
      log(`frame ${i + 1}/${total} t=${t.toFixed(2)}s elapsed=${((Date.now() - t0) / 1000).toFixed(1)}s`);
    }
  }
  await browser.close();
  const secs = ((Date.now() - t0) / 1000);
  log(`screenshots done in ${secs.toFixed(1)}s (${(secs / total).toFixed(3)}s/frame)`);

  if (NOENC) { log('skip encode'); return; }

  const out = path.join(ROOT, TEST ? 'test.mp4' : 'out_silent.mp4');
  log('encoding -> ' + out);
  execFileSync(findFfmpeg(), [
    '-y', '-framerate', String(FPS), '-i', path.join(FRAMES, 'f-%05d.png'),
    '-c:v', 'libx264', '-crf', CRF, '-preset', 'medium', '-pix_fmt', 'yuv420p',
    '-r', String(FPS), '-movflags', '+faststart', out
  ], { stdio: 'inherit' });
  log('DONE ' + out);
})().catch(e => { log('ERROR ' + (e && e.stack || e)); process.exit(1); });
