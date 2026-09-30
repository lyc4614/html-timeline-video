// 全片几何体检：用 getBoundingClientRect 量真实位置，不看图。
//   · 横向溢出画幅（x<0 或 x>1080）
//   · 压到右上角 logo 区 / 底部章节轨 / 底部字幕区
//
// 三条写检查器的硬规矩（都是踩出来的）：
//   1) 不能用宽度阈值屏蔽「整帧容器」。上版写的是 `if (r.width < 1050) 才报溢出`，
//      结果一行 1600px 宽的真溢出文字反而不报 —— 容器要按 class 白名单跳过。
//   2) 不能因为 opacity===0 就跳过元素。几何与透明度无关：
//      还没入场的元素一旦入过场就会溢出，照样要报。这版的做法是
//      「在每个镜头结束前 0.2s 测」——那时内容全入场，几何就是最终几何。
//   3) 必须双向验证：正片全通过不算数，要再喂一个已知溢出的人为反例，
//      确认它还看得见。（上版就是卡在这一步才暴露出上面两个洞。）
//
// 用法：node check_geometry.cjs [html相对ROOT的路径]
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const ROOT = __dirname.replace(/\\/g, '/').replace('/_tools', '');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TARGET = process.argv[2] || 'index.html';

// 画幅：默认竖版 1080×1920；横版传 VIDEO_W=1920 VIDEO_H=1080（视口与 X 溢出判据都跟着改）
const W = +(process.env.VIDEO_W || 1080);
const H = +(process.env.VIDEO_H || 1920);

// 整帧容器：它们按设计就该压满，跳过不代表没事，是不该参与溢出判定
const FRAME_CTN = ['wrap', 'stage', 'bands', 'cur', 'shot', 'root'];

// 禁区（右上 logo / 底部章节轨 / 底部字幕）
// 不要把 .chap/.sign 区设成禁区 —— 那正是它们该待的地方。
// ⚠ 下面这组是**竖版坐标**。横版的版式不是竖版的等比缩放，
//   禁区必须重新给（用 ZONES_JSON 传），否则这项检查等于没做。
const ZONES = process.env.ZONES_JSON
  ? JSON.parse(process.env.ZONES_JSON)
  : [
    { name: 'logo',     x0: 700, y0: 60,   x1: 1080, y1: 170 },
    { name: 'rail',     x0: 180, y0: 1500, x1: 900,  y1: 1580 },
    { name: 'subtitle', x0: 0,   y0: 1660, x1: 1080, y1: 1930 },
  ];
if (W > H && !process.env.ZONES_JSON) {
  console.log('!! 画幅是横版，但禁区还在用竖版默认坐标 —— 请用 ZONES_JSON 传入横版禁区，否则本项检查无效。');
}

// 从源码解析每个镜头的 [起,止]，避免手抄时刻表漏掉镜头
function parseShots(src) {
  const re = /add\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,/g;
  const out = []; let m;
  while ((m = re.exec(src))) out.push([parseFloat(m[1]), parseFloat(m[2])]);
  return out;
}

const clsOf = e => (e.className && e.className.baseVal !== undefined
  ? e.className.baseVal : (e.className || '')).toString().trim();

(async () => {
  const src = fs.readFileSync(path.join(ROOT, TARGET), 'utf8');
  const shots = parseShots(src);
  if (!shots.length) { console.log('ERROR 没解析到任何 add(s,e,...)'); process.exit(2); }

  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    userDataDir: path.join(ROOT, '.chrome-profile'),
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  await page.goto('file:///' + path.join(ROOT, TARGET).replace(/\\/g, '/'), { waitUntil: 'load' });
  await page.waitForFunction('typeof window.__render === "function"');

  let issues = 0;
  for (const [a, b] of shots) {
    const t = Math.max(a + 0.05, b - 0.2);          // 镜头结束前：内容全入场
    if (b - a < 0.45) continue;                      // 转场垫片镜头跳过
    await page.evaluate(tt => window.__render(tt), t);

    const bad = await page.evaluate((t, ZONES, FRAME_CTN, cfgW) => {
      const out = [];
      const clsOf = e => (e.className && e.className.baseVal !== undefined
        ? e.className.baseVal : (e.className || '')).toString().trim();
      for (const s of document.querySelectorAll('.shot')) {
        if (s.style.display !== 'block') continue;
        for (const e of s.querySelectorAll('*')) {
          const cs = clsOf(e);
          if (FRAME_CTN.some(c => cs.split(/\s+/).includes(c))) continue;
          const st = getComputedStyle(e);
          if (st.display === 'none' || st.visibility === 'hidden') continue;
          const r = e.getBoundingClientRect();
          if (r.width < 2 || r.height < 2) continue;
          const txt = (e.textContent || '').trim().slice(0, 26);

          // ① 横向溢出：左右任意一边超出画幅即报
          if (r.left < -2 || r.right > cfgW + 2) {
            out.push({ kind: 'X溢出', t, tag: e.tagName, cls: cs, txt,
                       box: [r.left, r.top, r.right, r.bottom].map(v => +v.toFixed(0)) });
          }
          // ② 禁区：只看真正有文字的叶子（看不见的东西压不住别人）
          if (!txt) continue;
          const hasKidText = [...e.children].some(c => (c.textContent || '').trim().length);
          if (hasKidText) continue;
          for (const z of ZONES) {
            if (r.left < z.x1 && r.right > z.x0 && r.top < z.y1 && r.bottom > z.y0) {
              if (parseFloat(st.opacity) < 0.05) continue;
              out.push({ kind: '压' + z.name, t, tag: e.tagName, cls: cs, txt,
                         box: [r.left, r.top, r.right, r.bottom].map(v => +v.toFixed(0)) });
            }
          }
        }
      }
      return out;
    }, t, ZONES, FRAME_CTN, W);

    const seen = new Set();
    for (const o of bad) {
      const k = o.kind + '|' + o.txt + '|' + o.box.join(',');
      if (seen.has(k)) continue;
      seen.add(k); issues++;
      console.log(`  [${o.kind}] t=${o.t.toFixed(1)}  <${o.tag} class="${o.cls}">  "${o.txt}"  ${JSON.stringify(o.box)}`);
    }
  }
  console.log('\n共 %d 个镜头，发现问题 %d 处', shots.length, issues);
  await browser.close();
  process.exit(issues ? 1 : 0);
})().catch(e => { console.log('ERROR', e && e.stack || e); process.exit(2); });
