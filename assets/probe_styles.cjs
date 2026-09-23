const puppeteer = require('puppeteer-core');
const path = require('path');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
(async () => {
  const b = await puppeteer.launch({ executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox','--hide-scrollbars','--allow-file-access-from-files'] });
  const p = await b.newPage();
  await p.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
  await p.goto('file:///' + path.join(__dirname, 'index.html').replace(/\\/g,'/'), { waitUntil: 'load' });
  await p.evaluate('document.fonts.ready');
  await p.evaluate(() => window.__render(98.5));
  await new Promise(r => setTimeout(r, 300));
  const out = await p.evaluate(() => {
    const q = (sel) => {
      const e = document.querySelector(sel);
      if (!e) return [sel, 'MISSING'];
      const cs = getComputedStyle(e);
      const r = e.getBoundingClientRect();
      return [sel, {
        color: cs.color, fill: cs.webkitTextFillColor,
        bg: cs.backgroundImage.slice(0, 46),
        clip: cs.webkitBackgroundClip,
        rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]
      }];
    };
    const res = [q('.ruler .rd'), q('.ruler'), q('#s18f'), q('#s18c .vscard .v')];
    // 再找 S5 的两个环
    const rings = [...document.querySelectorAll('.rings svg circle')].map(c => c.getAttribute('stroke'));
    const ringVals = [...document.querySelectorAll('.ringval')].map(e => [e.textContent, getComputedStyle(e).color, getComputedStyle(e).webkitTextFillColor]);
    return { res, rings, ringVals };
  });
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
