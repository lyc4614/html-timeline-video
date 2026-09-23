# -*- coding: utf-8 -*-
"""用 DOM 几何拿到元素真实 box，再采样像素明度 —— 不靠目测标坐标。

为什么必须这样做：看着截图估坐标，估偏了就采到背景上，读出的数全是假的
（真实踩坑：第一次采样两张小卡得 0.079 / 0.073，全是页面背景值）。

用法：
    python probe_by_dom.py --html video/index.html --frames _check --jobs jobs.json

jobs.json（时间点 → 选择器 → 显示名 → 该时间点的截图文件名）：
[
  {"t": 17.3,  "shot": "t17.png", "sel": "#s4meta > div",   "names": ["总分卡", "得分率卡"]},
  {"t": 131.5, "shot": "t131.png","sel": "#s23v > .vscard", "names": ["左卡", "右卡"]},
  {"t": 127.0, "shot": "t127.png","sel": "#s22c .bar",      "names": ["左柱", "右柱"]}
]

截图自己先抽好（或复用 check 目录里的），本脚本只负责「拿 box + 量明度」。

判据（见 SKILL.md「寡淡」一节）：元素区域均值明度 > 背景 + 0.15 才立得住；
≤ 背景 等于没画。
"""
import argparse, json, os, subprocess, sys, tempfile
import colorsys

from PIL import Image

CHROME_CANDIDATES = [
    os.environ.get('CHROME_PATH'),
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
]
CHROME = next((p for p in CHROME_CANDIDATES if p and os.path.exists(p)), None)

NODE_SCRIPT = r'''
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const [HTML, CHROME, JOBS, OUT] = process.argv.slice(2);
(async () => {
  const b = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--allow-file-access-from-files'],
  });
  const p = await b.newPage();
  await p.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
  await p.goto('file:///' + HTML, { waitUntil: 'load' });
  await p.waitForFunction('typeof window.__render === "function"');
  await new Promise(r => setTimeout(r, 1000));          // 等字体
  const out = [];
  for (const job of JSON.parse(JOBS)) {
    await p.evaluate(t => window.__render(t), job.t);
    await new Promise(r => setTimeout(r, 200));
    const rects = await p.evaluate(sel => {
      const res = [];
      document.querySelectorAll(sel).forEach(e => {
        const r = e.getBoundingClientRect();
        res.push([Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]);
      });
      return res;
    }, job.sel);
    out.push({ t: job.t, shot: job.shot, sel: job.sel, names: job.names, rects });
  }
  await b.close();
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
})().catch(e => { console.error(e); process.exit(1); });
'''


def hsv(p):
    return colorsys.rgb_to_hsv(p[0] / 255, p[1] / 255, p[2] / 255)


def mean_v(im, box):
    """区域均值明度 + 平均 RGB。"""
    crop = im.crop(box)
    px = list(crop.getdata())
    if not px:
        return None
    n = len(px)
    return (sum(p[0] for p in px) / n, sum(p[1] for p in px) / n, sum(p[2] for p in px) / n,
            sum(hsv(p)[2] for p in px) / n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True, help='index.html 路径')
    ap.add_argument('--frames', required=True, help='截图所在目录（shot 文件名相对它）')
    ap.add_argument('--jobs', required=True, help='JSON 任务描述文件')
    ap.add_argument('--bg', type=float, default=None,
                    help='页面背景明度；给了就自动判定「立得住/偏淡/等于没画」')
    a = ap.parse_args()

    if not CHROME:
        sys.exit('找不到 Chrome，请设 CHROME_PATH 环境变量')

    jobs = json.load(open(a.jobs, encoding='utf-8'))
    tmp = tempfile.mkdtemp(prefix='probe_by_dom_')
    runner = os.path.join(tmp, 'run.cjs')
    rects_file = os.path.join(tmp, 'rects.json')
    with open(runner, 'w', encoding='utf-8') as f:
        f.write(NODE_SCRIPT)

    node = os.environ.get('NODE_BIN', 'node')
    r = subprocess.run(
        [node, runner, os.path.abspath(a.html).replace('\\', '/'), CHROME,
         json.dumps(jobs), rects_file],
        capture_output=True, text=True, cwd=tmp,
        env=dict(os.environ, NODE_PATH=os.environ.get('NODE_PATH', '')))
    if r.returncode != 0:
        print('node 失败：\n' + r.stderr[-1500:])
        raise SystemExit(1)

    data = json.load(open(rects_file, encoding='utf-8'))
    for job in data:
        shot = os.path.join(a.frames, job['shot'])
        if not os.path.exists(shot):
            print('!! 缺截图 %s（跳过）' % shot)
            continue
        im = Image.open(shot).convert('RGB')
        print('=== %s  @%.1fs  %s ===' % (job['shot'], job['t'], job['sel']))
        for i, (x, y, w, h) in enumerate(job['rects']):
            if w < 2 or h < 2:
                continue
            # 内侧缩 12% + 12px：避开描边、圆角与四角花纹
            m = int(min(w, h) * 0.12) + 12
            box = (x + m, y + m, x + w - m, y + h - m)
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            mv = mean_v(im, box)
            if mv is None:
                continue
            mr, mg, mb, v = mv
            label = job['names'][i] if i < len(job['names']) else '#%d' % i
            verdict = ''
            if a.bg is not None:
                if v <= a.bg:
                    verdict = '  <- 等于没画'
                elif v <= a.bg + 0.15:
                    verdict = '  <- 偏淡'
                else:
                    verdict = '  OK'
            print('  %-20s box=%-28s RGB=(%5.1f,%5.1f,%5.1f) 明度%.3f%s'
                  % (label, box, mr, mg, mb, v, verdict))


if __name__ == '__main__':
    main()
