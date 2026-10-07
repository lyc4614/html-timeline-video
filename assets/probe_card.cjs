#!/usr/bin/env node
/* ============================================================================
   probe_card.cjs — 卡片 / 边框体检（数字版，不靠肉眼）

   回答三个问题：
     A. 角花（.card/.rrow 的 ::before 四角装饰）是否压住了卡内内容？
        → 报告每个角的重叠面积（px²），并给出内容最小内缩 vs 角花包络的余量
     B. 同屏不同容器（.card / .card.sm / .rrow）的规格是否一致？
        → border / 圆角 / padding / 背景层数 / 阴影 逐项比对
     C. 卡内内容的「安全内缩」够不够？
        → 判据：内容内缩 ≥ 角花包络 + GAP(8px)

   为什么必须量而不看：
     · 48px 角花画在 8px 内缩处 → 包络 56px。卡片 padding 28px 时
       **图标会被角花盖住 28px**，但整体看着「还挺好看」，肉眼扫过去容易漏。
     · 重叠只在卡片足够矮/内容足够靠边时出现，靠翻每一帧找是不可靠的。

   用法：
     node probe_card.cjs                 每镜取「结尾前 0.35s」（元素已全部入场）
     node probe_card.cjs --t 186 196     指定时刻
     node probe_card.cjs --dump 186      额外打印该时刻所有卡片的计算样式
   退出码：0 = 无重叠；6 = 检测到重叠
   ========================================================================== */
'use strict';
const fs = require('fs');
const path = require('path');

let puppeteer;
try { puppeteer = require('puppeteer-core'); }
catch (e) {
  console.error('缺少 puppeteer-core。请设置 NODE_PATH 指向已安装目录，例如：');
  console.error('  export NODE_PATH="<puppeteer-core 所在的 node_modules 目录>"');
  process.exit(3);
}

const ROOT = process.env.VIDEO_ROOT || __dirname;
const W = +(process.env.VIDEO_W || 1080);
const H = +(process.env.VIDEO_H || 1920);
const GAP = +(process.env.CARD_SAFE_GAP || 8);   // 内容与角花之间要求的最小间隙

function findChrome() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const cands = [
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe'),
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
  ].filter(Boolean);
  const hit = cands.find(p => fs.existsSync(p));
  if (!hit) { console.error('找不到 Chrome/Edge，请设 CHROME_PATH'); process.exit(3); }
  return hit;
}

const argv = process.argv.slice(2);
const argT = (() => { const i = argv.indexOf('--t'); return i >= 0 ? argv.slice(i + 1).filter(a => !a.startsWith('--')).map(Number) : null; })();
const argDump = (() => { const i = argv.indexOf('--dump'); return i >= 0 ? Number(argv[i + 1]) : null; })();
// --url <file.html> 换页面量。用于在落地前先量「卡片实验台」，
// 保证新样式是被同一把尺子验证过的，而不是靠看。
const argUrl = (() => { const i = argv.indexOf('--url'); return i >= 0 ? argv[i + 1] : null; })();
// 静态页（实验台）没有 __render / __shots，走「整页量一次」模式
const STATIC_MODE = !!argUrl;

/* ---------- 页面内执行的取数逻辑（字符串化后注入） ---------- */
function pageProbe(t, doDump) {
  const px = v => parseFloat(v) || 0;

  // 有效不透明度：祖先链相乘（父级 opacity:0 时子元素也看不见）
  const effOpacity = el => {
    let o = 1, n = el;
    while (n && n !== document.documentElement) {
      o *= px(getComputedStyle(n).opacity);
      if (o < 0.02) return 0;
      n = n.parentElement;
    }
    return o;
  };

  // 把 background-position 的一项解析成「相对卡片左上角的 px 坐标」
  // ⚠ 必须按括号深度切分：Chrome 对 calc() 返回的是**字符串**，
  //   `calc(100% - 5px) calc(100% - 5px)` 按空格裸切会变成
  //   ['calc(100%','-','5px)','calc(100%','-','5px)'] —— 右下角花会被算成 (856,0)，
  //   于是「右下角压内容」永远查不出来（假通过）。这条骗过我一次。
  const splitTop = (str, sep) => {          // 按顶层分隔符切（忽略括号内）
    const out = []; let depth = 0, cur = '';
    for (const ch of String(str)) {
      if (ch === '(') depth++;
      else if (ch === ')') depth--;
      if (ch === sep && depth === 0) { out.push(cur); cur = ''; } else cur += ch;
    }
    out.push(cur);
    return out.map(s => s.trim()).filter(s => s !== '');
  };
  const oneAxis = (s, box, img) => {
    if (s.includes('100%')) {
      const off = px((s.match(/-\s*([\d.]+)px/) || [0, 0])[1]);
      return box - img - off;               // 百分比定位是「边缘对齐」语义
    }
    if (s === 'center') return (box - img) / 2;
    return px(s);
  };
  const posToXY = (tok, bw, bh, iw, ih) => {
    const ax = splitTop(tok, ' ');          // ← 按空格切，但忽略 calc() 内的空格
    const x = oneAxis(ax[0], bw, iw);
    const y = ax[1] != null ? oneAxis(ax[1], bh, ih) : (bh - ih) / 2;
    return [x, y];
  };

  // 尺子自检：解析器错会让「重叠」漏报，必须先证明它是对的再信它的输出
  const SELFTEST = (() => {
    const cases = [
      // [输入, 容器W, 容器H, 图W, 图H, 期望x, 期望y, 说明]
      ['5px 5px', 880, 136, 24, 24, 5, 5, '左上'],
      ['calc(100% - 5px) calc(100% - 5px)', 880, 136, 24, 24, 851, 107, '右下'],
      ['calc(100% - 8px) 8px', 880, 200, 36, 36, 836, 8, '右上'],
      ['8px calc(100% - 8px)', 880, 200, 36, 36, 8, 156, '左下'],
    ];
    const bad = [];
    for (const [tok, w, h, iw, ih, ex, ey, name] of cases) {
      const [x, y] = posToXY(tok, w, h, iw, ih);
      if (Math.abs(x - ex) > 0.5 || Math.abs(y - ey) > 0.5) {
        bad.push(`${name}: ${tok} → (${x.toFixed(0)},${y.toFixed(0)}) 期望 (${ex},${ey})`);
      }
    }
    return bad;
  })();

  const rectOf = el => {
    const r = el.getBoundingClientRect();
    return { L: +r.left.toFixed(1), T: +r.top.toFixed(1), R: +r.right.toFixed(1), B: +r.bottom.toFixed(1),
             w: +r.width.toFixed(1), h: +r.height.toFixed(1) };
  };

  const shots = (window.__shots || []).map(s =>
    Array.isArray(s) ? { s: s[0], e: s[1] } : { s: s.s != null ? s.s : s.start, e: s.e != null ? s.e : s.end });

  // 静态页（实验台）没有 __render / __shots —— 直接量整页
  const isStatic = typeof window.__render !== 'function' || !shots.length;

  let scope;
  if (isStatic) {
    scope = document.body;
  } else {
    window.__render(t);
    scope = [...document.querySelectorAll('#root .shot')].filter(s => {
      const cs = getComputedStyle(s);
      return cs.display !== 'none' && px(cs.opacity) > 0.35;
    }).pop();
    if (!scope) return { t, err: '该时刻没有可见镜头' };
  }

  const cards = [...scope.querySelectorAll('.card, .rrow')].filter(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 40 || r.height < 30) return false;
    const cs = getComputedStyle(el);
    return cs.display !== 'none' && effOpacity(el) > 0.55;
  });

  const out = [];
  for (const el of cards) {
    const cr = rectOf(el);
    const cs = getComputedStyle(el);
    const pcs = getComputedStyle(el, '::before');

    // ---- 角花包络 ----
    let orns = [];
    if (pcs.content !== 'none' && pcs.backgroundImage && pcs.backgroundImage !== 'none') {
      const sizes = pcs.backgroundSize.split(',').map(s => s.trim().split(/\s+/).map(px));
      const poss = pcs.backgroundPosition.split(',').map(s => s.trim());
      const n = Math.min(sizes.length, poss.length);
      for (let k = 0; k < n; k++) {
        const [iw, ih] = [sizes[k][0], sizes[k][1] || sizes[k][0]];
        const [x, y] = posToXY(poss[k], cr.w, cr.h, iw, ih);
        orns.push({ k, x: +x.toFixed(1), y: +y.toFixed(1), w: iw, h: ih,
                    L: +(cr.L + x).toFixed(1), T: +(cr.T + y).toFixed(1),
                    R: +(cr.L + x + iw).toFixed(1), B: +(cr.T + y + ih).toFixed(1) });
      }
    }
    // 角花的「深入量」：不是角花尺寸，而是它从卡边往内伸了多远（内缩 + 尺寸）。
    // 判据必须用这个量 —— 用尺寸会低估（24px 角花画在内缩 5px 处，实际占了 29px）。
    const need = { L: 0, R: 0, T: 0, B: 0 };
    for (const o of orns) {
      // 先判断这枚角花贴在哪个边 —— 不分类会把右侧角花算进左侧，得出「880px」这种假数
      const onLeft   = (o.L - cr.L) < cr.w / 2;
      const onRight  = (cr.R - o.R) < cr.w / 2;
      const onTop    = (o.T - cr.T) < cr.h / 2;
      const onBottom = (cr.B - o.B) < cr.h / 2;
      if (onLeft)   need.L = Math.max(need.L, o.R - cr.L);
      if (onRight)  need.R = Math.max(need.R, cr.R - o.L);
      if (onTop)    need.T = Math.max(need.T, o.B - cr.T);
      if (onBottom) need.B = Math.max(need.B, cr.B - o.T);
    }
    const env = Math.max(need.L, need.R, need.T, need.B);

    // ---- 内容元素（叶子级：文本块 / 图标 / 胶囊 / 柱体） ----
    const content = [];
    for (const c of el.querySelectorAll('*')) {
      if (c.matches('.card,.rrow')) continue;
      const r = c.getBoundingClientRect();
      if (r.width < 5 || r.height < 5) continue;
      const ccs = getComputedStyle(c);
      if (ccs.display === 'none' || ccs.visibility === 'hidden') continue;
      if (effOpacity(c) < 0.55) continue;
      const isLeaf = c.children.length === 0 ||
        ['svg', 'img'].includes(c.tagName.toLowerCase()) ||
        c.matches('.ic,.ni,.hi,.pillg,.bar,.dbadge');
      if (!isLeaf) continue;
      content.push({ cls: (c.className && String(c.className)) || c.tagName.toLowerCase(),
                     txt: (c.textContent || '').trim().slice(0, 14), ...rectOf(c) });
    }
    // 内容整体包围盒 → 安全内缩
    let inset = null;
    if (content.length) {
      const L = Math.min(...content.map(c => c.L)), R = Math.max(...content.map(c => c.R));
      const T = Math.min(...content.map(c => c.T)), B = Math.max(...content.map(c => c.B));
      inset = { L: +(L - cr.L).toFixed(1), R: +(cr.R - R).toFixed(1),
                T: +(T - cr.T).toFixed(1), B: +(cr.B - B).toFixed(1) };
    }

    // ---- 重叠 / 最近间距 ----
    // 纹样有两种形态：贴角的（小）和水平通栏的（居中铺开）。
    // 「四边内缩」对通栏纹样必然是负数 —— 正确判据是**纹样与内容的最近距离**：
    //   dx/dy 分别是两矩形在 x/y 轴上的间隔（负值 = 该轴交叠）。
    //   两轴都交叠 → 真重叠；否则最近距离 ≥ max(dx,dy)（取大者作为下界，保守）。
    const hits = [];
    let safe = null;
    for (const o of orns) {
      for (const c of content) {
        const dx = Math.max(o.L - c.R, c.L - o.R);
        const dy = Math.max(o.T - c.B, c.T - o.B);
        if (dx < 1 && dy < 1) {
          const ox = Math.min(o.R, c.R) - Math.max(o.L, c.L);
          const oy = Math.min(o.B, c.B) - Math.max(o.T, c.T);
          hits.push({ corner: ['TL', 'TR', 'BL', 'BR'][o.k] || ('#' + o.k),
                      w: +ox.toFixed(0), h: +oy.toFixed(0), area: +(ox * oy).toFixed(0),
                      el: c.cls, txt: c.txt });
        } else {
          const gap = Math.max(dx, dy);
          safe = safe == null ? gap : Math.min(safe, gap);
        }
      }
    }

    out.push({
      sel: el.className, h: cr.h, w: cr.w,
      rect: cr,
      ornCount: orns.length,
      ornSize: orns.length ? orns[0].w : 0,
      ornInset: orns.length ? Math.min(orns[0].x, orns[0].y) : 0,
      ornRects: orns.map(o => ({ x: o.x, y: o.y, w: o.w, h: o.h })),
      rawSize: pcs.backgroundSize,
      rawPos: pcs.backgroundPosition,
      env,
      inset,
      need,
      minInset: inset ? Math.min(inset.L, inset.R, inset.T, inset.B) : null,
      // 安全余量 = 纹样与内容整体包围盒的最近距离（通栏纹样/贴角纹样都适用）
      safe,
      hits,
      content,
      // 规格指纹：用于「同屏容器是否一套语言」的比对
      spec: {
        border: cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor,
        radius: cs.borderTopLeftRadius,
        padding: cs.padding,
        bgLayers: cs.backgroundImage === 'none' ? 0 : cs.backgroundImage.split('url').length + (cs.backgroundImage.includes('gradient') ? 1 : 0),
        bgImage: cs.backgroundImage === 'none' ? 'none' : cs.backgroundImage.slice(0, 46),
        shadow1: cs.boxShadow.split('),')[0].slice(0, 60),
        afterContent: getComputedStyle(el, '::after').content,
      },
    });
  }
  return { t, shot: isStatic ? '(静态页)' : scope.className, selftest: SELFTEST, cards: out };
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: findChrome(),
    headless: 'new',
    userDataDir: path.join(ROOT, '.chrome-profile'),
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none',
           '--allow-file-access-from-files', '--disable-gpu', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.log('[pageerror]', e.message));
  const target = argUrl
    ? (path.isAbsolute(argUrl) ? argUrl : path.join(ROOT, argUrl))
    : path.join(ROOT, 'index.html');
  await page.goto('file:///' + target.replace(/\\/g, '/'), { waitUntil: 'load' });
  if (!STATIC_MODE) await page.waitForFunction('typeof window.__render === "function"');
  // 字体 + 图片都要等 —— 图片没加载会让内容盒尺寸偏小，重叠判断失真
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

  let times = argT;
  if (!times) {
    if (STATIC_MODE) {
      times = [0];   // 静态页：整页量一次
    } else {
      const shots = await page.evaluate(() => (window.__shots || []).map(s =>
        Array.isArray(s) ? [s[0], s[1]] : [s.s != null ? s.s : s.start, s.e != null ? s.e : s.end]));
      // 取每镜「结尾前 0.35s」：此刻该镜所有元素都已入场，布局是最终形态
      times = shots.map(([, e]) => Math.max(0, +(e - 0.35).toFixed(2)));
    }
  }

  const pad = (s, n) => String(s).padEnd(n);
  console.log('\n角花 vs 内容 逐卡体检（判据：安全余量 = 内容最小内缩 − 角花包络 ≥ ' + GAP + 'px）');
  console.log('='.repeat(112));
  console.log(pad('t', 9) + pad('选择器', 22) + pad('卡高', 7) + pad('角花', 7) +
              pad('角花深入 L/R/T/B', 20) + pad('内容内缩 L/R/T/B', 22) + '安全余量');
  console.log('-'.repeat(112));

  let bad = 0, allCards = [], selfChecked = false;
  for (const t of times) {
    const res = await page.evaluate(pageProbe, t, false);
    if (res.err) { console.log(pad(t, 9) + res.err); continue; }
    // 尺子自检不通过就立刻停 —— 解析器坏掉时「没查出重叠」是假通过
    if (!selfChecked) {
      selfChecked = true;
      if (res.selftest && res.selftest.length) {
        console.log('\n✗ 角花定位解析器自检失败 —— 结果不可信，已中止：');
        res.selftest.forEach(s => console.log('   · ' + s));
        await browser.close();
        process.exit(7);
      }
      console.log('\n尺子自检：角花定位解析 4/4 通过（左上/右上/左下/右下四种写法）');
    }
    for (const c of res.cards) {
      allCards.push({ t, ...c });
      const shortSel = c.sel.split(' ').slice(0, 3).join('.').slice(0, 21);
      const ins = c.inset ? [c.inset.L, c.inset.R, c.inset.T, c.inset.B].map(v => Math.round(v)).join('/') : '-';
      const need = c.need ? [c.need.L, c.need.R, c.need.T, c.need.B].map(v => Math.round(v)).join('/') : '无';
      const safeStr = c.safe == null ? '-' : c.safe.toFixed(0) + 'px';
      const flag = c.hits.length ? '  ✗ 重叠' : (c.safe != null && c.safe < GAP ? '  ⚠ 余量不足' : '');
      console.log(pad(t, 9) + pad(shortSel, 22) + pad(Math.round(c.h), 7) +
                  pad(c.ornSize || '无', 7) + pad(need, 20) + pad(ins, 22) + safeStr + flag);
      if (c.hits.length) {
        bad += c.hits.length;
        for (const h of c.hits) {
          console.log(pad('', 9) + `   ↳ ${h.corner} 角压住「${h.txt || h.el}」 ${h.w}×${h.h}px = ${h.area}px²`);
        }
      }
    }
  }

  // ---- 规格一致性：同屏出现的容器是否一套语言 ----
  const bySel = {};
  for (const c of allCards) {
    const k = c.sel.split(/\s+/).filter(s => /^(card|rrow|s-\w+|sm|sem)$/.test(s)).join('.') || c.sel;
    (bySel[k] = bySel[k] || []).push(c.spec);
  }
  console.log('\n' + '='.repeat(112));
  console.log('容器规格指纹（同屏不同容器应当共用同一套边框语言）');
  console.log('-'.repeat(112));
  const seen = new Set();
  for (const [k, v] of Object.entries(bySel)) {
    const fp = JSON.stringify(v[0]);
    console.log(pad(k.slice(0, 26), 27) + pad(v[0].radius, 8) + pad(v[0].border.slice(0, 34), 35) + v[0].padding);
    if (v.length > 1 && JSON.stringify(v[1]) !== fp) {
      console.log(pad('', 27) + '⚠ 同类容器规格不一致：' + fp.slice(0, 60));
      console.log(pad('', 27) + '                          ' + JSON.stringify(v[1]).slice(0, 60));
    }
    seen.add(fp);
  }

  // ---- 可选：完整样式 dump ----
  if (argDump != null) {
    const res = await page.evaluate(pageProbe, argDump, true);
    console.log('\n' + '='.repeat(112));
    console.log(`t=${argDump} 全部卡片计算样式`);
    for (const c of res.cards) {
      console.log('\n■ ' + c.sel + `   ${Math.round(c.w)}×${Math.round(c.h)}` +
        `   位置 x ${Math.round(c.rect.L)}–${Math.round(c.rect.R)}  y ${Math.round(c.rect.T)}–${Math.round(c.rect.B)}`);
      console.log('   border   ' + c.spec.border);
      console.log('   radius   ' + c.spec.radius + '   padding ' + c.spec.padding);
      console.log('   bg       ' + (c.spec.bgImage || 'none'));
      console.log('   shadow   ' + c.spec.shadow1);
      console.log('   ::after  content=' + c.spec.afterContent);
      console.log('   角花     ' + c.ornCount + ' 个，尺寸 ' + c.ornSize + 'px，包络 ' + c.env + 'px，内容安全余量 ' + c.safe + 'px');
      console.log('   raw size ' + c.rawSize);
      console.log('   raw pos  ' + c.rawPos);
      console.log('   解析后   ' + JSON.stringify(c.ornRects) + `  （卡 ${Math.round(c.w)}×${Math.round(c.h)}）`);
      console.log('   内容     ' + c.content.slice(0, 6).map(x =>
        `${x.txt || x.cls}[${Math.round(x.L)},${Math.round(x.T)}→${Math.round(x.R)},${Math.round(x.B)}]`).join('  '));
    }
  }

  await browser.close();
  console.log('\n' + '='.repeat(112));
  if (bad) {
    console.log(`✗ 检出 ${bad} 处「角花压内容」—— 修到 0 再出片`);
    process.exit(6);
  }
  console.log('✓ 无角花压内容');
  process.exit(0);
})().catch(e => { console.error('probe_card 异常：', e); process.exit(1); });
