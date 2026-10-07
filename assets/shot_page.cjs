#!/usr/bin/env node
/* ============================================================================
   shot_page.cjs — 给任意 HTML 拍全页图（含字体 + 图片等待）

   为什么单独做一个：正片用 check.cjs（按时刻抽帧），但「卡片实验台」这类静态页
   没有 __render 契约。任何启动 Chrome 的脚本都必须等字体和图片 ——
   不等就会拍到回退字体 / 空白 logo（踩过两次）。

   用法：
     node shot_page.cjs card_lab.html card_lab.png
     node shot_page.cjs card_lab.html out.png --width 1080 --ready window.__ready
     node shot_page.cjs page.html out.png --clip 0 2400      只取 y∈[0,2400)
   ========================================================================== */
'use strict';
const fs = require('fs');
const path = require('path');

let puppeteer;
try { puppeteer = require('puppeteer-core'); }
catch (e) {
  console.error('缺少 puppeteer-core。请先 export NODE_PATH 指向已安装目录。');
  process.exit(3);
}

const ROOT = process.env.VIDEO_ROOT || process.cwd();
const W = +(process.env.VIDEO_W || 1080);
const H = +(process.env.VIDEO_H || 1920);

function findChrome() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const cands = [
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe'),
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
  ].filter(Boolean);
  const hit = cands.find(p => fs.existsSync(p));
  if (!hit) { console.error('找不到 Chrome/Edge，请设 CHROME_PATH'); process.exit(3); }
  return hit;
}

const argv = process.argv.slice(2);
const page_file = argv[0];
const out_file = argv[1];
const getOpt = (n, d) => { const i = argv.indexOf('--' + n); return i >= 0 ? argv[i + 1] : d; };
const width = +getOpt('width', W);
const readyExpr = getOpt('ready', null);
const clipArg = (() => { const i = argv.indexOf('--clip'); return i >= 0 ? [+argv[i + 1], +argv[i + 2]] : null; })();
const fullPage = argv.includes('--full') || !clipArg;

if (!page_file || !out_file) {
  console.error('用法: node shot_page.cjs <input.html> <output.png> [--width 1080] [--clip y0 y1] [--full]');
  process.exit(1);
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: findChrome(), headless: 'new',
    userDataDir: path.join(ROOT, '.chrome-profile'),
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none',
           '--allow-file-access-from-files', '--disable-gpu', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width, height: H, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.log('[pageerror]', e.message));
  page.on('requestfailed', r => console.log('[reqfail]', r.url().split('/').pop()));

  const abs = path.isAbsolute(page_file) ? page_file : path.join(ROOT, page_file);
  await page.goto('file:///' + abs.replace(/\\/g, '/'), { waitUntil: 'load' });
  if (readyExpr) {
    try { await page.waitForFunction(readyExpr, { timeout: 8000 }); }
    catch (e) { console.log('⚠ 等待 ' + readyExpr + ' 超时，继续截图'); }
  }
  // 字体 + 图片都要等（图片未加载会让内容盒尺寸偏小）
  await page.evaluate(() => {
    const pend = [];
    if (document.fonts && document.fonts.ready) pend.push(document.fonts.ready);
    [].slice.call(document.images).forEach(im => {
      if (im.complete && im.naturalWidth) return;
      pend.push(new Promise(r => { im.onload = r; im.onerror = r; }));
    });
    return Promise.all(pend);
  });
  await new Promise(r => setTimeout(r, 400));

  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  // ⚠ screenshot 必须传 path —— 不传只返回 Buffer，零字节落盘，
  //   而后面读文件会报 ENOENT，报错完全指不到真因（这个坑踩过一次了）
  const shot = { type: 'png', path: out_file };
  if (clipArg) shot.clip = { x: 0, y: clipArg[0], width, height: clipArg[1] - clipArg[0] };
  else shot.fullPage = fullPage;
  const buf = await page.screenshot(shot);
  await browser.close();

  // puppeteer 的 fullPage 截图在极长页面上会超过 Chrome 的纹理上限，
  // 必须校验落盘图的实际尺寸 —— 不能只看「没报错」
  const iw = buf.readUInt32BE(16), ih = buf.readUInt32BE(20);
  console.log(`${out_file}  ${iw}×${ih}  （页面高 ${h}）`);
  if (fullPage && ih < 40) { console.error('✗ 截图为空白，尺寸异常'); process.exit(4); }
  process.exit(0);
})().catch(e => { console.error('shot_page 异常：', e); process.exit(1); });
