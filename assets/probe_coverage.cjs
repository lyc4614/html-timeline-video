// probe_coverage.cjs —— 量各镜头内容占安全区多少（DOM 几何法）
//
// 为什么必须用 DOM 几何而不是像素扫描：像素扫描分不清「镜头内容」和「常驻层」
// （顶部 logo / 章节轨 / 字幕带），位置随版式变化，靠猜阈值永远对不上。
// SKILL.md 记录了三次像素扫描全部出假数据的实录。
//
// 三条写检查器的硬规矩（都是踩出来的）：
//   1) 整帧容器必须按 class 白名单跳过 —— .shot/.wrap/.stage 按设计就压满，
//      把它们算进 y 区间，任何镜头都会报 151%。**不能用「宽度大就跳过」**。
//   2) 不能因为 opacity===0 就跳过元素：几何与透明度无关，
//      这里在每镜的「入场完成时刻」测，那时该出现的都已出现。
//   3) 必须双向验证：正片通过不算数，要再喂一个已知偏空的人为反例，
//      确认它还看得见（--selftest 模式）。
//
// 用法：
//   node probe_coverage.cjs              自动取每镜「入场完成」时刻
//   node probe_coverage.cjs 12 45 90      指定时间点
//   node probe_coverage.cjs --selftest   双向验证（正片 + 人为反例）
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const ROOT = process.env.VIDEO_ROOT || __dirname;
const W = +(process.env.VIDEO_W || 1080);
const H = +(process.env.VIDEO_H || 1920);
// 安全区默认值与原正片 .stage 的 padding 一致，**随画幅派生**。
// ⚠ 写死竖版会出两个错：① 横版工程连页都打不开（ROOT 锚在脚本目录）
//   ② 就算打开了，横版内容横向能到 1810，会被竖版的 x1=1016 全部误判成「横向溢出」。
const LAND = W > H;
const DEF = LAND ? { top: 150, bot: 875, x: 96, x1: 1824 }
                 : { top: 196, bot: 1468, x: 64, x1: 1016 };
const SAFE_TOP = +(process.env.SAFE_TOP || DEF.top);
const SAFE_BOT = +(process.env.SAFE_BOT || DEF.bot);
const SAFE_X   = +(process.env.SAFE_X   || DEF.x);
const SAFE_X1  = +(process.env.SAFE_X1  || DEF.x1);
const EXCL = ['#toplogo', '#rail', '#sub', '#pbar', '#brand'];
// 整帧容器：按设计就该压满，跳过不代表没事，是不该参与「内容占多少」的统计
const FRAME_CTN = ['shot', 'wrap', 'stage', 'root', 'rows', 'list', 'quad', 'cmp'];

const SELFTEST = process.argv.includes('--selftest');
const DUMP = process.argv.includes('--dump');   // 打印溢出元素明细

function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const c = [(process.env.LOCALAPPDATA || '') + '/Google/Chrome/Application/chrome.exe',
             'C:/Program Files/Google/Chrome/Application/chrome.exe',
             'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
             'C:/Program Files/Microsoft/Edge/Application/msedge.exe'];
  for (const p of c) if (fs.existsSync(p)) return p;
  throw new Error('找不到 Chrome/Edge');
}

const probe = (page, t) => page.evaluate((tt) => {
  window.__render(tt);
  const EXCL = ['#toplogo', '#rail', '#sub', '#pbar', '#brand'];
  const FRAME_CTN = ['shot', 'wrap', 'stage', 'root', 'rows', 'list', 'quad', 'cmp'];
  const on = [...document.querySelectorAll('#root .shot')]
    .filter(s => getComputedStyle(s).display !== 'none' && +getComputedStyle(s).opacity > 0.35);
  if (!on.length) return null;
  const s = on[on.length - 1];
  let y0 = Infinity, y1 = -Infinity, x0 = Infinity, x1 = -Infinity, n = 0, skipped = 0;
  for (const el of s.querySelectorAll('*')) {
    if (EXCL.some(sel => el.matches(sel) || el.closest(sel))) continue;
    if (FRAME_CTN.some(c => el.classList.contains(c))) { skipped++; continue; }
    const cs = getComputedStyle(el);
    if (cs.opacity < 0.03 || cs.display === 'none') continue;
    const rc = el.getBoundingClientRect();
    if (rc.width < 2 || rc.height < 2) continue;
    y0 = Math.min(y0, rc.top); y1 = Math.max(y1, rc.bottom);
    x0 = Math.min(x0, rc.left); x1 = Math.max(x1, rc.right);
    n++;
  }
  return n ? { y0, y1, x0, x1, n, skipped } : null;
}, t);

(async () => {
  const browser = await puppeteer.launch({
    executablePath: findChrome(), headless: 'new',
    userDataDir: path.join(require('os').tmpdir(), 'html-timeline-chrome-profile'),
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files',
           '--disable-gpu', '--disable-dev-shm-usage']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });

  if (SELFTEST) {
    // === B. 人为反例：给所有内容加 font-size:10px，内容必然缩到很小 ==
    console.log('=== 双向验证 · B 人为反例（内容压到最小）===');
    await page.goto('file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/'), { waitUntil: 'load' });
    await page.waitForFunction('typeof window.__render === "function"');
    await page.addStyleTag({ content: '#root .shot *{font-size:10px !important;padding:0 !important;}' });
    const r = await probe(page, 7.1);
    const cov = (r.y1 - r.y0) * 100 / (SAFE_BOT - SAFE_TOP);
    console.log('  t=7.1  内容高 %d px  占安全区 %s', (r.y1 - r.y0).toFixed(0), cov.toFixed(0) + '%');
    if (cov < 45) { console.log('  ✓ 反例被判为「偏空」—— 尺子有效'); }
    else { console.log('  ✗ 反例没被抓到 —— 尺子失效，别信下面的数据'); process.exit(1); }
    await browser.close();
    return;
  }

  await page.goto('file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/'), { waitUntil: 'load' });
  await page.waitForFunction('typeof window.__render === "function"');
  // 字体 + 图片都要等：只等字体的话，<img> 素材（品牌 logo）尺寸算成 0，
  // 几何统计会漏掉它，覆盖率读数偏低。
  // onerror 也必须 resolve，否则路径写错会让 Promise 永不 resolve、脚本卡死。
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
  await new Promise(r => setTimeout(r, 400));

  // 镜头表：优先 window.__shots（与渲染同一份数据）；老工程没有这个契约时回退 DOM 的
  // data-st / data-et，否则会直接报「拿不到镜头表」——明明页面是完整的。
  const shots = await page.evaluate(() => {
    const a = (window.__shots || []).map(s =>
      Array.isArray(s) ? [s[0], s[1]] : [s.s != null ? s.s : s.start, s.e != null ? s.e : s.end]);
    if (a.length) return a;
    return [...document.querySelectorAll('.shot[data-st]')]
      .map(el => [+el.dataset.st, +el.dataset.et]).filter(x => isFinite(x[0]) && isFinite(x[1]));
  });
  let times = process.argv.slice(2).map(Number).filter(n => !isNaN(n));
  if (!times.length) {
    if (!shots.length) { console.log('拿不到镜头表，请显式给时间点'); await browser.close(); return; }
    // 取每镜「入场完成」时刻：s + 4.2s（盖住最慢的入场），但不越过镜尾
    times = shots.map(([s, e]) => Math.min(s + 4.2, e - 0.4));
  }

  console.log('安全区 y ∈ [%d, %d]  高 %d px   x ∈ [%d, %d]', SAFE_TOP, SAFE_BOT, SAFE_BOT - SAFE_TOP, SAFE_X, SAFE_X1);
  console.log('（口径 = .stage 内容带，即设计意图。要查「是否真的撞到 HUD / 压住字幕」请换视觉安全线：');
  console.log('  横版实测 SAFE_TOP=122 SAFE_BOT=924 —— 同一批内容在两条线下会得出不同结论，别混用）\n');
  const pad = (s, n) => String(s).padEnd(n);
  console.log(pad('t', 8) + pad('上沿', 8) + pad('下沿', 8) + pad('占安全区', 10) + pad('横向', 8) + '判定');
  console.log('-'.repeat(62));

  const rows = [];
  for (const t of times) {
    const r = await probe(page, t);
    if (!r) { console.log(pad(t.toFixed(1), 8) + '(该时刻无可见镜头)'); continue; }
    const cov = (r.y1 - r.y0) * 100 / (SAFE_BOT - SAFE_TOP);
    const overY = Math.max(0, SAFE_TOP - r.y0, r.y1 - SAFE_BOT);
    const overX = Math.max(0, SAFE_X - r.x0, r.x1 - SAFE_X1);
    const judge = cov < 45 ? '偏空·换布局或补信息'
      : overY > 1 ? '⚠超出内容带' + overY.toFixed(0) + 'px'
      : overX > 1 ? '⚠横向溢出' + overX.toFixed(0) + 'px' : 'OK';
    console.log(pad(t.toFixed(1), 8) + pad(r.y0.toFixed(0), 8) + pad(r.y1.toFixed(0), 8) +
      pad(cov.toFixed(0) + '%', 10) + pad((overX > 1 ? overX.toFixed(0) + 'px' : '-'), 8) + judge);
    rows.push({ t, cov, overY, overX, y0: r.y0, y1: r.y1 });

    if (DUMP && (overX > 1 || overY > 1)) {
      const bad = await page.evaluate((tt, SF) => {
        window.__render(tt);
        const on = [...document.querySelectorAll('#root .shot')]
          .filter(s => getComputedStyle(s).display !== 'none' && +getComputedStyle(s).opacity > 0.35);
        const s = on[on.length - 1];
        const out = [];
        for (const el of s.querySelectorAll('*')) {
          const rc = el.getBoundingClientRect();
          if (rc.width < 2) continue;
          if (rc.left < SF.x || rc.right > SF.x1 || rc.top < SF.top || rc.bottom > SF.bot) {
            out.push({ cls: (el.className || el.tagName).toString().slice(0, 26),
              L: +rc.left.toFixed(0), R: +rc.right.toFixed(0), T: +rc.top.toFixed(0), B: +rc.bottom.toFixed(0),
              txt: (el.textContent || '').trim().slice(0, 18) });
          }
        }
        return out.slice(0, 5);
      }, t, { top: SAFE_TOP, bot: SAFE_BOT, x: SAFE_X, x1: SAFE_X1 });
      bad.forEach(b => console.log('        ↳ ' + JSON.stringify(b)));
    }
  }
  await browser.close();

  const covs = rows.map(r => r.cov).sort((a, b) => a - b);
  const med = covs[covs.length >> 1];
  console.log('\n中位占比 %s%%   区间 %s%% – %s%%', med.toFixed(0), covs[0].toFixed(0), covs[covs.length - 1].toFixed(0));
  const bad = rows.filter(r => r.cov < 45);
  if (bad.length) console.log('%d 个偏空(<45%%): %s', bad.length,
    bad.map(r => 't=' + r.t.toFixed(1) + '(' + r.cov.toFixed(0) + '%)').join(', '));
  const of = rows.filter(r => r.overY > 1 || r.overX > 1);
  if (of.length) console.log('⚠ %d 个超出内容带: %s', of.length, of.map(r => 't=' + r.t.toFixed(1)).join(', '));
})().catch(e => { console.log('ERROR', e && e.stack || e); process.exit(1); });
