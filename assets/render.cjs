// render.cjs —— HTML 时间轴动效页 → 逐帧截图 → ffmpeg 编码
// 用法：
//   node render.cjs              全片渲染 + 编码
//   node render.cjs --test       散布采样 120 帧测速（不编码）
//   node render.cjs --test --noenc
// 环境变量（都可省，有默认值/自动探测）：
//   VIDEO_ROOT   工程目录（含 index.html），默认脚本所在目录
//   CHROME_PATH  浏览器可执行文件，默认自动探测 Chrome → Edge
//   FFMPEG_PATH  ffmpeg 可执行文件，默认 from PATH
//   VIDEO_W      画布宽，默认 1080
//   VIDEO_H      画布高，默认 1920
//   VIDEO_FPS    帧率，默认 30
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = process.env.VIDEO_ROOT || __dirname;
const FRAMES = path.join(ROOT, 'frames');
const W = +(process.env.VIDEO_W || 1080);
const H = +(process.env.VIDEO_H || 1920);
const FPS = +(process.env.VIDEO_FPS || 30);
const TEST = process.argv.includes('--test');
const NOENC = process.argv.includes('--noenc');

function firstExisting(list) {
  for (const p of list) if (p && fs.existsSync(p)) return p;
  return null;
}
function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const cands = [
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
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });

  const url = 'file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/');
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction('typeof window.__render === "function"');

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
    '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-pix_fmt', 'yuv420p',
    '-r', String(FPS), '-movflags', '+faststart', out
  ], { stdio: 'inherit' });
  log('DONE ' + out);
})().catch(e => { log('ERROR ' + (e && e.stack || e)); process.exit(1); });
