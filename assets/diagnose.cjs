// diagnose.cjs —— 抓页面 JS 错误 + 关键状态
// 用途：render.cjs 报 "Waiting failed: window.__render" 时，先跑这个看真实异常。
// 用法：NODE_PATH=... node diagnose.cjs [index.html]
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

// 工程根：优先 VIDEO_ROOT（与 render.cjs / probe_card.cjs 同一套），缺省才是脚本所在目录。
// ⚠ 只锚 __dirname 时，横版工程的 index.html 根本传不进来（连绝对路径都会被拼错，见下）。
const ROOT = process.env.VIDEO_ROOT || __dirname;
const TARGET = process.argv[2] || 'index.html';
// 画幅也走环境变量：写死竖版会把横版工程以 1080×1920 打开，版式全错、
// 抽帧「看到的内容」整个不对，而脚本不报错。
const W = +(process.env.VIDEO_W || 1080);
const H = +(process.env.VIDEO_H || 1920);

function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const cands = [
    (process.env.LOCALAPPDATA || '') + '/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ];
  for (const p of cands) if (fs.existsSync(p)) return p;
  throw new Error('找不到 Chrome/Edge');
}

(async () => {
  // 绝对路径直接用 —— Windows 下 path.join(ROOT, 'C:/x/y') 会拼成 `assets\C:\x\y`，
  // 报「文件不存在」却看不出是拼接方式的问题。
  const file = path.isAbsolute(TARGET) ? TARGET : path.join(ROOT, TARGET);
  if (!fs.existsSync(file)) { console.log('文件不存在:', file); process.exit(1); }
  const browser = await puppeteer.launch({
    executablePath: findChrome(), headless: 'new',
    userDataDir: path.join(require('os').tmpdir(), 'html-timeline-chrome-profile'),
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files',
           '--disable-gpu', '--disable-dev-shm-usage']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });

  page.on('console', m => console.log('[console:' + m.type() + ']', m.text()));
  page.on('pageerror', e => console.log('[pageerror]', e.message, '\n', (e.stack || '').split('\n').slice(0, 4).join('\n')));
  page.on('requestfailed', r => console.log('[reqfail]', r.url().split('/').pop(), r.failure() && r.failure().errorText));

  await page.goto('file:///' + file.replace(/\\/g, '/'), { waitUntil: 'load' });
  await new Promise(r => setTimeout(r, 2500));

  console.log('--- 关键状态 ---');
  console.log('__render   =', await page.evaluate('typeof window.__render'));
  console.log('__duration =', await page.evaluate('window.__duration'));
  console.log('__fps      =', await page.evaluate('window.__fps'));
  console.log('.shot 数   =', await page.evaluate('document.querySelectorAll("#root .shot").length'));
  console.log('SUBS 条数  =', await page.evaluate('typeof SUBS!=="undefined"?SUBS.length:-1'));
  console.log('已加载字体  =', await page.evaluate('document.fonts.size'));
  const notLoaded = await page.evaluate(
    '[...document.fonts].filter(f=>f.status!=="loaded").map(f=>f.family+"/"+f.weight+":"+f.status).join(", ")');
  console.log('未 loaded   =', notLoaded || '(无)');

  if (await page.evaluate('typeof window.__render === "function"')) {
    console.log('--- 抽 3 帧看是否渲染出内容 ---');
    for (const t of [2, 45, 190]) {
      await page.evaluate(tt => window.__render(tt), t);
      const vis = await page.evaluate(() => {
        // 切镜头有两套写法：inline `display:block`（早期）与 `visibility`+`opacity`（主线，SKILL.md 用它）。
        // 只认 display 时，主线写法的正片会**恒返回空数组**，看着像「什么都没渲染出来」。
        const on = [...document.querySelectorAll('#root .shot')].filter(s => {
          const cs = getComputedStyle(s);
          return cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0.05;
        });
        return on.map(s => ({ op: s.style.opacity, txt: (s.textContent || '').trim().slice(0, 28) }));
      });
      console.log('  t=' + t + 's 可见镜头:', JSON.stringify(vis));
    }
  }
  await browser.close();
})().catch(e => { console.log('ERROR', e && e.stack || e); process.exit(1); });
