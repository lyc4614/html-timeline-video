/* DOM 几何检测：找出所有超出安全区的文本元素
   比读图可靠 —— 图上网格线/卡片边框都会干扰判断，直接读元素盒子才准。
   用法: node check_overflow.cjs "<t1|t2|...>" "<名1|名2|...>"
   安全区默认左右各 46px（画布 1080）。
   工程根目录：优先取环境变量 PROJ_ROOT，否则取当前工作目录。 */
const puppeteer = require('puppeteer-core');
const path = require('path');

const ROOT = process.env.PROJ_ROOT || process.cwd();
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const SAFE = 46, W = 1080;

const ts = (process.argv[2] || '').split('|').map(Number);
const names = (process.argv[3] || '').split('|');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: 1920, deviceScaleFactor: 1 });
  const url = 'file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/');
  await page.goto(url, { waitUntil: 'load' });
  await page.evaluate('document.fonts.ready');
  await new Promise(r => setTimeout(r, 600));

  let anyBad = false;
  for (let i = 0; i < ts.length; i++) {
    await page.evaluate((t) => window.__render(t), ts[i]);
    await new Promise(r => setTimeout(r, 160));

    const bad = await page.evaluate((SAFE) => {
      const out = [];
      const SKIP = new Set(['pbar', 'rail', 'sub', 'bg']);
      document.querySelectorAll('#root *').forEach(el => {
        // 只看承载文本的叶子元素；容器（.stage/.wrap）会返回全屏盒子，必然误报
        if (el.children.length > 0) return;
        const txt = (el.textContent || '').trim();
        if (!txt) return;
        // 祖先里如果有被排除的结构层，跳过
        let p = el;
        while (p) { if (p.id && SKIP.has(p.id)) return; p = p.parentElement; }
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height) return;
        const L = r.left, R = 1080 - r.right;
        if (L < SAFE || R < SAFE) {
          out.push({ txt: txt.slice(0, 26), cls: (el.className || '').toString().slice(0, 24),
                     L: Math.round(L), R: Math.round(R) });
        }
      });
      return out;
    }, SAFE);

    if (bad.length) {
      anyBad = true;
      console.log(`t=${ts[i]}s  ${names[i]}`);
      bad.forEach(b => console.log(`    L${String(b.L).padStart(4)} R${String(b.R).padStart(4)}  [${b.cls}] ${b.txt}`));
    }
  }
  if (!anyBad) console.log('全部镜头均在安全区内（左右各 ' + SAFE + 'px）');
  await browser.close();
})().catch(e => { console.error('ERR', (e && e.stack) || e); process.exit(1); });
