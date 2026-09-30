// 几何 + 明度二合一探针（本 skill 的主力验收工具）。
//
// 一次跑出三样东西：
//   ① 卡片类元素的 getBoundingClientRect（越界判定 + 供明度脚本消费）
//   ② 文本问题：水平被裁（scrollWidth）与**竖向被挤出所属卡片**
//   ③ 每个采样时刻一对截图 A（正常画面）/ B（只留背景）→ 供「卡片 vs 背景 Δ>0.15」量化
//
// 用法：
//   node probe_cards.cjs 4.2 20.1 87.5 ...
// 环境变量：
//   PROJ_ROOT   工程根目录（含 index.html），默认当前工作目录
//   VIDEO_W/H   画幅，默认 1080×1920
//   CHROME_PATH Chrome 路径
//   SAFE_X/SAFE_TOP/SAFE_BOT  越界判据（视觉安全线，不是 .stage 的 padding 框）
//
// ⚠ 两条硬规矩（都翻过车）：
//   1) 隐藏正片只能用 display:none。用 visibility:hidden 会被 __render 写的
//      内联 visibility:visible 覆盖 → A/B 两图完全相同 → Δ 恒为 0，看着像
//      「卡片没对比度」，其实是测量失效。脚本末尾有自检，Δ 全 0 会报错退出。
//   2) 越界判据要用「视觉安全线」：先实测 HUD 文字底 / 字幕框顶，再留 20px 空隙。
//      照抄 .stage 的 padding 框会太严，把只是轻微溢出框、肉眼完全没碰
//      HUD 与字幕的镜头误报成越界。
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const ROOT = (process.env.PROJ_ROOT || process.cwd()).replace(/\\/g, '/');
const OUT = path.join(ROOT, 'probe');
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const VW = +(process.env.VIDEO_W || 1080);
const VH = +(process.env.VIDEO_H || 1920);
const LAND = VW > VH;
const SAFE_X = +(process.env.SAFE_X || (LAND ? 110 : 46));
const SAFE_TOP = +(process.env.SAFE_TOP || (LAND ? 122 : 200));
const SAFE_BOT = +(process.env.SAFE_BOT || (LAND ? 924 : 1616));

const TIMES = process.argv.slice(2).map(Number).filter((n) => !isNaN(n));
if (!TIMES.length) { console.log('用法: node probe_cards.cjs 4.2 20.1 ...'); process.exit(1); }

// 卡片类：明度统计 + 越界。改卡片强度时这一组必须逐个过一遍
const SEL = '.card,.ncard,.tag,.chip,.rrow,.grp,.stamp,.sn,.medal,.big';
// 几何组：再补上「没有卡面」的元素，只做越界判定，不进明度统计
const SEL_GEO = SEL + ',.pin,.val,.bar,.lb,.axis,.axwrap,.axticks';

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
      '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: VW, height: VH, deviceScaleFactor: 1 });
  const url = 'file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/');
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction('typeof window.__render === "function"');
  await page.waitForFunction('window.__fontsReady === true', { timeout: 20000 });

  const report = { times: [], overflow: [], shots: [] };

  report.shots = await page.evaluate(() =>
    [...document.querySelectorAll('.shot')].map((s) => [+s.dataset.st, +s.dataset.et]));

  const rectProbe = (sel) => {
    const out = [];
    document.querySelectorAll(sel).forEach((el) => {
      const shot = el.closest('.shot');
      if (shot && getComputedStyle(shot).visibility === 'hidden') return;
      if (parseFloat(getComputedStyle(el).opacity) < 0.55) return;
      const r = el.getBoundingClientRect();
      if (r.width < 6 || r.height < 6) return;
      out.push({
        cls: el.className.toString().slice(0, 44),
        x: Math.round(r.left), y: Math.round(r.top),
        w: Math.round(r.width), h: Math.round(r.height)
      });
    });
    return out;
  };

  for (const t of TIMES) {
    await page.evaluate((tt) => window.__render(tt), t);
    const clip = { x: 0, y: 0, width: VW, height: VH };
    await page.screenshot({ type: 'png', path: path.join(OUT, 'A_' + t + '.png'), clip });

    const rects = await page.evaluate(rectProbe, SEL);
    const georects = await page.evaluate(rectProbe, SEL_GEO);
    report.times.push({ t, rects });

    // 文本问题：① 水平被裁 ② 竖向被挤出所属卡片（scrollWidth 查不到后者）
    const tclip = await page.evaluate(() => {
      const SEL2 = '.t1,.t2,.t3,.h1,.h2,.h3,.kick,.num,.cap,.unit,.nm,.st,.lb,.val,.sn,.chip,.gold';
      const out = [];
      document.querySelectorAll(SEL2).forEach((el) => {
        const shot = el.closest('.shot');
        if (shot && getComputedStyle(shot).visibility === 'hidden') return;
        if (parseFloat(getComputedStyle(el).opacity) < 0.55) return;
        if (el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2) {
          out.push({ kind: '文字溢出', cls: el.className.toString().slice(0, 40),
            txt: (el.textContent || '').trim().slice(0, 24),
            sw: el.scrollWidth, cw: el.clientWidth });
        }
        const card = el.closest('.card,.ncard,.chip');
        if (card && card !== el) {
          const rc = card.getBoundingClientRect(), re = el.getBoundingClientRect();
          const dTop = Math.round(rc.top - re.top), dBot = Math.round(re.bottom - rc.bottom);
          if (dTop > 2 || dBot > 2) {
            out.push({ kind: '超出卡片', cls: el.className.toString().slice(0, 40),
              txt: (el.textContent || '').trim().slice(0, 24),
              sw: 'top+' + dTop, cw: 'bot+' + dBot });
          }
        }
      });
      return out;
    });
    if (tclip.length) report.overflow.push(...tclip.map((c) => ({ t, ...c })));

    // 只留背景再拍一张 —— 必须 display:none，理由见文件头
    await page.evaluate(() => { document.querySelector('#root').style.display = 'none'; });
    await page.screenshot({ type: 'png', path: path.join(OUT, 'B_' + t + '.png'), clip });
    await page.evaluate(() => { document.querySelector('#root').style.display = 'block'; });

    for (const r of georects) {
      if (r.x < SAFE_X - 6 || r.x + r.w > VW - SAFE_X + 6 ||
          r.y < SAFE_TOP || r.y + r.h > SAFE_BOT) {
        report.overflow.push({ t, cls: r.cls, x: r.x, y: r.y, w: r.w, h: r.h });
      }
    }
    console.log('probe t=' + t + '  卡片 ' + rects.length + '  几何 ' + georects.length +
                '  文本问题 ' + tclip.length);
  }

  fs.writeFileSync(path.join(OUT, 'rects.json'), JSON.stringify(report, null, 1));
  console.log('\n镜头边界:', JSON.stringify(report.shots));
  console.log('越界/溢出总数:', report.overflow.length);
  report.overflow.forEach((o) => console.log('   !! t=' + o.t + ' ' + (o.kind || '越界') + ' ' +
    o.cls + (o.sw !== undefined ? '  sw=' + o.sw + ' cw=' + o.cw : '') +
    (o.x !== undefined ? '  [' + o.x + ',' + o.y + ' ' + o.w + 'x' + o.h + ']' : '') + '  ' + (o.txt || '')));
  console.log('\n画幅 ' + VW + '×' + VH + '  越界判据 x∈[' + (SAFE_X - 6) + ',' + (VW - SAFE_X + 6) +
              '] y∈[' + SAFE_TOP + ',' + SAFE_BOT + ']');
  await browser.close();
})().catch((e) => { console.log('ERROR ' + (e && e.stack || e)); process.exit(1); });
