const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');
const ROOT = process.env.PROJ_ROOT || process.cwd();
const OUT = path.join(ROOT, '..', 'storyboard');
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
      '--disable-lcd-text', '--font-render-hinting=none', '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
  const base = 'file:///' + path.join(ROOT, 'proto.html').split(path.sep).join('/');
  const NAMES = ['01_封面', '02_三卡并列', '03_章节卡', '04_大数字', '05_四校榜单'];
  for (let i = 0; i < NAMES.length; i++) {
    await page.goto(base + '?shot=' + i + '&gt=' + (i * 11), { waitUntil: 'load' });
    await new Promise(r => setTimeout(r, 320));
    await page.screenshot({
      type: 'png', path: path.join(OUT, NAMES[i] + '.png'),
      clip: { x: 0, y: 0, width: 1080, height: 1920 }
    });
    console.log('shot', i, NAMES[i]);
  }
  await browser.close();
  console.log('DONE ->', OUT);
})().catch(e => { console.error('ERR', e && e.stack || e); process.exit(1); });
