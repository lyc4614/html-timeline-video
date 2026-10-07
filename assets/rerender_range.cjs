// rerender_range.cjs —— 只重跑受影响的帧号区间，其余帧沿用磁盘上的旧图
//
// 为什么需要：全片 6874 帧要 50 分钟。改一版只影响几十秒的帧号区间时，
// 全片重渲是纯浪费（实测 7049 帧里改 331 帧，35 分钟 → 2 分钟）。
//
// ⚠⚠ 两个必须做对的守卫（都是真实翻车过的事故）⚠⚠
//
// 1) 画幅默认值必须与 render.cjs **完全一致**。
//    本脚本若照抄竖版模板写成 `VIDEO_W || 1080`，而主片是横版，
//    那批帧会以**竖版尺寸**写进横版序列。
//    ffmpeg 读 image2 序列时按**首帧尺寸**统一缩放 —— 整片静默变成 1080×1920，
//    画面看着「没问题」（内容被等比缩放了），只有规格是错的。
//    本次是靠 PSNR 从 41 dB 掉到 33 dB 才察觉。
//
// 2) 重渲前**逐帧检查现有帧的尺寸**，尺寸不符立刻中止。
//    见「尺寸守卫」一节。宁可停下来，也不能出一版规格错的成片。
//
// 用法：
//   node rerender_range.cjs <起始秒> <结束秒>      重跑 [start, end] 内的帧
//   node rerender_range.cjs <起始秒> <结束秒> --noenc   只截图不重编码
//   node rerender_range.cjs --check-size                只做尺寸守卫自检
//
// 画幅来自环境变量，与 render.cjs 同一套。
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = process.env.VIDEO_ROOT || __dirname;
const FRAMES = path.join(ROOT, 'frames');
// ⚠ 守卫 1：画幅默认值必须与 render.cjs 逐字一致。改这里之前先改那边。
const W = +(process.env.VIDEO_W || 1080);
const H = +(process.env.VIDEO_H || 1920);
const FPS = +(process.env.VIDEO_FPS || 30);
const CRF = String(process.env.VIDEO_CRF || 16);
const NOENC = process.argv.includes('--noenc');
const CHECK_ONLY = process.argv.includes('--check-size');

const log = (m) => process.stdout.write(m + '\n');

function firstExisting(list) {
  for (const p of list) if (p && fs.existsSync(p)) return p;
  return null;
}
function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  return firstExisting([
    (process.env.LOCALAPPDATA || '') + '/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/chromium',
  ]) || (() => { throw new Error('找不到 Chrome/Edge，请设 CHROME_PATH'); })();
}
function findFfmpeg() {
  if (process.env.FFMPEG_PATH) return process.env.FFMPEG_PATH;
  try {
    const p = execFileSync(process.platform === 'win32' ? 'where' : 'which', ['ffmpeg'], { encoding: 'utf8' })
      .split(/\r?\n/).map(s => s.trim()).filter(Boolean)[0];
    if (p && fs.existsSync(p)) return p;
  } catch (_) {}
  const base = path.join(process.env.LOCALAPPDATA || '', 'Microsoft/WinGet/Packages');
  if (fs.existsSync(base)) {
    for (const d of fs.readdirSync(base)) {
      if (!/FFmpeg/i.test(d)) continue;
      for (const v of fs.readdirSync(path.join(base, d))) {
        const p = path.join(base, d, v, 'bin', process.platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg');
        if (fs.existsSync(p)) return p;
      }
    }
  }
  throw new Error('找不到 ffmpeg，请设 FFMPEG_PATH');
}

// ---------- 尺寸守卫 ----------
// 只读 PNG 头部 24 字节拿宽高，不解码整图 —— 6874 帧要秒级完成
function pngSize(file) {
  const fd = fs.openSync(file, 'r');
  try {
    const b = Buffer.alloc(24);
    fs.readSync(fd, b, 0, 24, 0);
    // PNG 签名 8 字节 + IHDR：width 在 16..19，height 在 20..23
    return [b.readUInt32BE(16), b.readUInt32BE(20)];
  } finally { fs.closeSync(fd); }
}

function checkFrameSizes() {
  if (!fs.existsSync(FRAMES)) { log('帧目录不存在：' + FRAMES); return 0; }
  const files = fs.readdirSync(FRAMES).filter(f => /^f-\d+\.png$/.test(f)).sort();
  if (!files.length) { log('帧序列为空'); return 0; }
  const bad = [];
  const first = pngSize(path.join(FRAMES, files[0]));
  if (first[0] !== W || first[1] !== H) {
    log(`✗ 画幅不一致：环境变量是 ${W}×${H}，但首帧 ${files[0]} 是 ${first[0]}×${first[1]}`);
    log('  多数情况是本脚本的画幅默认值与 render.cjs 不同 —— 检查两处 VIDEO_W/H 默认值。');
    return -1;
  }
  for (const f of files) {
    const [w, h] = pngSize(path.join(FRAMES, f));
    if (w !== W || h !== H) bad.push(`${f} ${w}×${h}`);
  }
  if (bad.length) {
    log(`✗ ${bad.length}/${files.length} 帧尺寸不符，如：${bad.slice(0, 3).join(', ')}`);
    log('  ffmpeg 会按首帧尺寸统一缩放整片 —— 继续下去会出一版规格错的成片。已中止。');
    return -1;
  }
  log(`✓ 尺寸守卫通过：全部 ${files.length} 帧 ${W}×${H}`);
  return files.length;
}

(async () => {
  const n = checkFrameSizes();
  if (n < 0) process.exit(4);          // 退出码 4 = 画幅守卫失败（与 verify_mp4.py 一致）
  if (CHECK_ONLY) return;
  if (!n) process.exit(2);

  // 两种入参：秒（41.7 51.0）或帧号（1251 1512，加 --frames 显式指定）。
  // 帧号入参省掉「秒↔帧」换算的浮点误差，也方便脚本间对接。
  const FRAMES_MODE = process.argv.includes('--frames');
  let i0, i1;
  if (FRAMES_MODE) {
    i0 = parseInt(process.argv[2], 10);
    i1 = parseInt(process.argv[3], 10);
    if (isNaN(i0) || isNaN(i1) || i1 < i0) {
      log('用法: node rerender_range.cjs <起始帧号> <结束帧号> --frames [--noenc]');
      process.exit(1);
    }
  } else {
    const a = parseFloat(process.argv[2]);
    const b = parseFloat(process.argv[3]);
    if (isNaN(a) || isNaN(b) || b <= a) {
      log('用法: node rerender_range.cjs <起始秒> <结束秒> [--noenc]');
      log('      node rerender_range.cjs <起始帧号> <结束帧号> --frames [--noenc]');
      process.exit(1);
    }
    // 帧号 = round(t*fps)。render.cjs 从 f-00000.png 开始（i 从 0），**不要 +1**。
    i0 = Math.max(0, Math.floor(a * FPS));
    i1 = Math.ceil(b * FPS);
  }
  i0 = Math.max(0, i0);
  i1 = Math.min(n - 1, i1);
  const cnt = i1 - i0 + 1;
  log(`重渲帧区间 f-${String(i0).padStart(5, '0')} … f-${String(i1).padStart(5, '0')}  共 ${cnt} 帧` +
      `（${(i0 / FPS).toFixed(2)}s – ${(i1 / FPS).toFixed(2)}s，画幅 ${W}×${H}）`);

  const browser = await puppeteer.launch({
    executablePath: findChrome(), headless: 'new',
    userDataDir: path.join(ROOT, '.chrome-profile'),
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files',
           '--disable-gpu', '--disable-dev-shm-usage']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  await page.goto('file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/'), { waitUntil: 'load' });
  await page.waitForFunction('typeof window.__render === "function"');
  // 字体就绪（与 render.cjs 同一套，见 SKILL.md「字体：用 @font-face 自带」）
  await page.evaluate(() => {
    var pend = [];
    if (document.fonts && document.fonts.ready) pend.push(document.fonts.ready);
    [].slice.call(document.images).forEach(function (im) {
      if (im.complete && im.naturalWidth) return;
      pend.push(new Promise(function (r) { im.onload = r; im.onerror = r; }));
    });
    return Promise.all(pend);
  });
  await new Promise(r => setTimeout(r, 400));

  const DUR = await page.evaluate('window.__duration');
  if (i1 / FPS > DUR + 0.5) log(`⚠ 结束 ${(i1 / FPS).toFixed(2)}s 超过片长 ${DUR.toFixed(2)}s，已按片长封顶`);

  const t0 = Date.now();
  // 落盘守卫：记下第一帧重渲前的 mtime，渲完再比。
  // 「跑完 N 帧、尺寸守卫全绿、但零字节落盘」是最难发现的失败 ——
  // page.screenshot() 不传 path 时只返回 Buffer 不写文件，看起来一切正常。
  const probeFile = path.join(FRAMES, 'f-' + String(i0).padStart(5, '0') + '.png');
  const mtimeBefore = fs.existsSync(probeFile) ? fs.statSync(probeFile).mtimeMs : 0;
  for (let i = i0; i <= i1; i++) {
    const t = i / FPS;
    await page.evaluate((tt) => window.__render(tt), t);
    // ⚠️ path 参数不能省！page.screenshot() 不传 path 时**只返回 Buffer，不写文件** ——
    // 局部重渲会「跑完 1054 帧、尺寸守卫全绿、零字节落盘」，看起来完全成功。
    // （实测踩过：帧时间戳还是上一次全片渲染的旧时间）
    const file = path.join(FRAMES, 'f-' + String(i).padStart(5, '0') + '.png');
    await page.screenshot({ type: 'png', path: file, clip: { x: 0, y: 0, width: W, height: H } });
    if ((i - i0) % 50 === 0 || i === i1) {
      log(`  f-${String(i).padStart(5, '0')}  t=${t.toFixed(2)}s  ` +
          `${((Date.now() - t0) / 1000).toFixed(1)}s`);
    }
  }
  await browser.close();
  const secs = (Date.now() - t0) / 1000;
  log(`\n重渲完成：${cnt} 帧 / ${secs.toFixed(1)}s（${(secs / cnt).toFixed(3)}s/帧）`);

  // 落盘守卫：确认帧真的被改写了
  const mtimeAfter = fs.existsSync(probeFile) ? fs.statSync(probeFile).mtimeMs : 0;
  if (mtimeAfter <= mtimeBefore) {
    log(`✗ 帧没有被改写（f-${String(i0).padStart(5, '0')} 的 mtime 未变）`);
    log('  几乎一定是 page.screenshot() 漏了 path 参数 —— 只返回 Buffer 不写文件。');
    log('  旧帧会继续留在盘上，编码后成片看起来正常但内容是上一版的。');
    process.exit(5);
  }
  log(`✓ 落盘守卫通过：f-${String(i0).padStart(5, '0')} 已改写`);

  // 重渲后**立刻再验一次尺寸**：这批帧是本次新写的，若画幅不对必须在这里就拦住
  if (checkFrameSizes() < 0) {
    log('\n✗ 重渲后的帧尺寸不一致，已中止编码。请检查 CHROME 视口与 VIDEO_W/H 是否一致。');
    process.exit(4);
  }

  if (NOENC) { log('skip encode（--noenc）'); return; }

  const out = path.join(ROOT, 'out_silent.mp4');
  log('重新编码 -> ' + out);
  execFileSync(findFfmpeg(), [
    '-y', '-framerate', String(FPS), '-i', path.join(FRAMES, 'f-%05d.png'),
    '-c:v', 'libx264', '-crf', CRF, '-preset', 'medium', '-pix_fmt', 'yuv420p',
    '-r', String(FPS), '-movflags', '+faststart', out
  ], { stdio: 'inherit' });
  log('DONE ' + out);
})().catch(e => { log('ERROR ' + (e && e.stack || e)); process.exit(1); });
