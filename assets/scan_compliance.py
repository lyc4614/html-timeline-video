# -*- coding: utf-8 -*-
"""合规词扫描（发布到视频号 / 抖音前）。

分两路扫，**分开标注来源**，因为处置方式不同：

| 来源 | 取法 | 处置 |
|---|---|---|
| **字幕** | 静态取源码里的 SUBS 数组 | 这是**用户稿件**，不擅改，只提示 |
| **画面文案** | 驱动 Chrome 渲染后读**实际可见**文本 | 这是本片新增的，**必须改** |

用法：
    python scan_compliance.py [index.html]            # 两路都扫（默认）
    python scan_compliance.py index.html --static     # 只扫字幕（无 node 环境时）
    python scan_compliance.py index.html --selftest   # 自检：注入违规词必须被抓到

退出码：0=通过 / 1=画面文案命中（须改）/ 2=字幕命中（仅提示）/ 3=自检失败 / 4=采不到必需数据

──────────────────────────────────────────────────────────────────
⚠ 为什么必须扫「渲染后的 DOM」，不能只扫源码：

旧版只扫 `SUBS` + `innerHTML = \\`…\\`` 模板串。但工程把画面文案写在
**数据字面量**里（`SHOTS = [{ tt:'…', tc:'…', note:'…' }]`）时，模板串一个都匹配不到
→ 扫描器报「通过」，而实际上镜 15 的品牌卡注释里就有导流词「主页」。
**这是最典型的假绿灯：扫描器什么都没扫到，却报合格。**

同理，`innerText` 而不是 `innerHTML`：后者会把 `display:none` 的隐藏层、
CSS 注释、`<style>` 里的字符串全部当成正文，既漏又误伤
（实测踩过：注释「弧长按章号递增」里的「长按」被当成风险词）。
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile

BAN = ['扫码', '长按', '二维码', '扫一扫', '去搜索', '点击下方', '点击主页',
       '主页', '私信', '加微信', '免费领', '加群', '关注我']

HERE = os.path.dirname(os.path.abspath(__file__))
NODE_CANDIDATES = [
    os.path.join(os.path.expanduser('~'), '.workbuddy', 'binaries', 'node',
                 'versions', '22.12.0', 'node.exe'),
    'node',
]
CHROME_CANDIDATES = [
    os.path.join(os.environ.get('PROGRAMFILES', r'C:\Program Files'),
                 'Google', 'Chrome', 'Application', 'chrome.exe'),
    os.path.join(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)'),
                 'Google', 'Chrome', 'Application', 'chrome.exe'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome',
                 'Application', 'chrome.exe'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Edge',
                 'Application', 'msedge.exe'),
]


# ── 第一路：字幕（静态，用户稿件）────────────────────────────────────
def subs_text(src):
    """SUBS 数组里的字幕，返回 [(st, et, text), ...]。兼容两种引号与数组尾逗号。"""
    m = re.search(r'const\s+SUBS\s*=\s*\[([\s\S]*?)\n\s*\];', src)
    if not m:
        return []
    body = m.group(1)
    out = []
    for mm in re.finditer(
            r'\[\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*["\']((?:[^"\'\\]|\\.)*)["\']', body):
        out.append((float(mm.group(1)), float(mm.group(2)), mm.group(3)))
    return out


# ── 第二路：画面文案（渲染后 DOM）────────────────────────────────────
DOM_JS = r'''
const p = require('puppeteer-core'), path = require('path'), os = require('os');
const ROOT = process.env.PROJ_ROOT || process.cwd();
const SELFTEST = process.env.PROBE_SELFTEST === '1';
(async () => {
  const b = await p.launch({
    executablePath: process.env.CHROME_PATH,
    headless: 'new',
    userDataDir: path.join(os.tmpdir(), 'html-timeline-compliance-profile'),
    args: ['--no-sandbox', '--allow-file-access-from-files', '--disable-gpu']});
  const g = await b.newPage();
  await g.setViewport({ width: +(process.env.VIDEO_W || 1080),
                        height: +(process.env.VIDEO_H || 1920) });
  await g.goto('file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/'),
               { waitUntil: 'load' });
  await g.waitForFunction('typeof window.__render === "function"');

  // 只取「真的会显示出来」的文字：跳过 display:none / visibility:hidden，
  // 并把祖先 opacity 累乘，opacity≈0 的层不算。innerText 做不到这点（它认 opacity:0）。
  //
  // ⚠ 必须再把**字幕层**排除掉：字幕的文字来自 SUBS，已由 Python 侧路径①扫过。
  //   不排除的话，会看到 DOM 里也有那句字幕 → 把「用户原稿」误报成「本片新增的画面文案」，
  //   两路重复计数，报告自相矛盾。工程把字幕容器命名成什么，就用 SKIP_SEL 传进来。
  // ⚠ g.evaluate(fn) 会把 fn **序列化**后丢进页面执行，闭包变量取不到 ——
  //   Node 侧定义的任何变量在页面里都是 undefined（我在这里栽过两次：
  //   window.__shots、以及这个 SKIP_SEL）。要传值只能走 evaluate 的第二个参数。
  const SKIP_SEL = process.env.SKIP_SEL || '';
  const readVisible = (skipSel) => {
    const out = [];
    const walk = (el, op) => {
      if (skipSel && el.matches && el.matches(skipSel)) return;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      const o = op * parseFloat(cs.opacity || '1');
      if (o < 0.02) return;
      for (const n of el.childNodes) {
        if (n.nodeType === 3) { const t = n.textContent.trim(); if (t) out.push(t); }
        else if (n.nodeType === 1) walk(n, o);
      }
    };
    walk(document.body, 1);
    return out.join(' ');
  };

  // 取样时刻：每镜入场后 1.6s + 每个数据带状态入场后 1.6s
  // ⚠ 镜头表必须从页面里取（g.evaluate），不能写成 Node 侧的 window.__shots ——
  //   那是 Node 作用域，会直接 "window is not defined"。
  const shots = await g.evaluate('window.__shots || []');
  if (!shots.length) { console.error('NO_SHOTS'); await b.close(); process.exit(4); }
  const g0 = (s, k) => (s[k] !== undefined ? s[k] : s[k === 'st' ? 's' : 'e']);
  const times = [];
  for (const s of shots) {
    times.push(+(g0(s, 'st') + 1.6).toFixed(3));
    // dz 在不同工程里既可能是数字数组 [0, 3.2, …]，也可能是对象数组 [{at:0,…}, …]
    for (const d of (s.dz || [])) {
      const at = (typeof d === 'object' && d !== null) ? d.at : d;
      if (typeof at === 'number' && at > 0.3) times.push(+(g0(s, 'st') + at + 1.6).toFixed(3));
    }
  }
  const uniq = [...new Set(times)].sort((a, b2) => a - b2);

  // 再叠加由 Python 传进来的字幕中点（PROBE_TIMES）——
  // 只按「镜头入场 + 数据带入场」采样会漏掉**镜头后段才入场**的元素
  // （例如第 8 秒才推入的卡片），那种文案永远扫不到。
  // 字幕中点天然把整条时间轴铺满（89 条字幕 / 256s ≈ 每 2.9s 一个点）。
  let extra = [];
  try { extra = JSON.parse(process.env.PROBE_TIMES || '[]'); } catch (e) { extra = []; }
  const all = [...new Set(uniq.concat(extra.map(x => +(+x).toFixed(3))))]
    .filter(t => isFinite(t) && t >= 0).sort((a, b2) => a - b2);

  const samples = [];
  let chars = 0;
  for (const t of all) {
    await g.evaluate((tt) => window.__render(tt), t);
    if (SELFTEST && samples.length === 0) {
      // 自检：注入一个**确定可见**的节点。别去 document.querySelectorAll('*') 里找
      // 「第一个叶子元素」—— 那可能落在 <head>（<title>/<style>），body 外的节点
      // 不会被 walk() 遍历到，自检会假失败（我这么错过一次）。
      await g.evaluate(() => {
        const d = document.createElement('div');
        d.id = '__compliance_probe';
        d.textContent = '记得扫码关注';
        document.body.appendChild(d);
      });
    }
    const txt = await g.evaluate(readVisible, SKIP_SEL);
    chars += txt.length;
    samples.push([t, txt]);
  }
  console.log(JSON.stringify({ shots: shots.length, chars, samples }));
  await b.close();
})().catch(e => { console.error('JS_ERR ' + (e && e.message || e)); process.exit(5); });
'''


def _node():
    for c in NODE_CANDIDATES:
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            return c
    return 'node'


def _chrome():
    for c in CHROME_CANDIDATES:
        if c and os.path.exists(c):
            return c
    return ''


def dom_scan(root, selftest=False, probe_times=None, skip_sel=''):
    """返回 (samples, err)。samples = [(t, text), ...]，采不到则 err 非空。"""
    js_path = os.path.join(tempfile.gettempdir(), 'compliance_scan.cjs')
    io.open(js_path, 'w', encoding='utf-8').write(DOM_JS)
    env = dict(os.environ)
    env.update(PROJ_ROOT=root, CHROME_PATH=_chrome(),
               PROBE_SELFTEST='1' if selftest else '0',
               PROBE_TIMES=json.dumps(probe_times or []),
               # 字幕容器：其文字已由路径①静态扫过，这里必须排除，否则两路重复计数
               SKIP_SEL=skip_sel or os.environ.get(
                   'SKIP_SEL', '.subz,.sub,.subtitle,#subz,#sub'),
               NODE_PATH=os.environ.get('NODE_PATH', ''))
    try:
        r = subprocess.run([_node(), js_path], capture_output=True, text=True,
                           env=env, timeout=900, cwd=root)
    except Exception as e:
        return None, 'launch failed: %s' % e
    line = [l for l in r.stdout.strip().split('\n') if l.startswith('{')]
    if not line:
        return None, 'node 无输出。stderr: %s' % (r.stderr.strip()[-400:] or '(空)')
    d = json.loads(line[-1])
    if not d['samples']:
        return None, '采样到 0 个时刻'
    return [(t, txt) for t, txt in d['samples']], None


def scan(texts, label):
    hits = []
    for w in BAN:
        for t, txt in texts:
            i = txt.find(w)
            if i >= 0:
                hits.append((w, t, txt[max(0, i - 20):i + 22]))
    return hits


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    static_only = '--static' in sys.argv
    selftest = '--selftest' in sys.argv
    p = args[0] if args else 'index.html'
    root = os.path.dirname(os.path.abspath(p)) or '.'
    src = io.open(p, encoding='utf-8').read()

    # ① 字幕（用户稿件）
    subs = subs_text(src)
    print('① 字幕（用户稿件，静态）：%d 条' % len(subs))
    if not subs:
        print('   ⚠ 没取到 SUBS —— 若本片确实无字幕可忽略，否则说明解析失败')
    sub_hits = scan([((s + e_) / 2, x) for s, e_, x in subs], 'sub')

    if static_only:
        dom_hits, dom_err, n_char = [], '（--static 跳过）', 0
    else:
        # ② 画面文案（渲染后 DOM），采样点 = 镜头入场 + 数据带入场 + 字幕中点
        subs_mid = sorted({round((s + e_) / 2.0, 3) for s, e_, _ in subs})
        samples, dom_err = dom_scan(root, selftest, probe_times=subs_mid)
        if dom_err:
            print('\n② 画面文案：✗ 采不到 —— %s' % dom_err)
            print('   采不到数据不叫通过（假绿灯最常见的形式）。'
                  '可加 --static 只扫字幕，但画面文案就没验。')
            sys.exit(4)
        n_char = sum(len(t) for _, t in samples)
        print('\n② 画面文案（渲染后 DOM）：%d 个时刻，共 %d 字' % (len(samples), n_char))
        dom_hits = scan(samples, 'dom')

    # ── 自检：注入的违规词必须在 DOM 里被抓到 ──
    if selftest and not static_only:
        caught = any(w == '扫码' for w, _, _ in dom_hits)
        print('\n自检：注入「扫码」到可见元素 → %s' % ('PASS（已抓到）' if caught else 'FAIL（漏了 —— 扫描器不可信）'))
        if not caught:
            sys.exit(3)
        print('（自检模式下画面文案的命中是人为注入的，不是真问题）')
        sys.exit(0)

    # ── 报告 ──
    print('\n' + '=' * 62)
    print('画面文案命中 %d 处（本片新增，必须处理）' % len(dom_hits))
    for w, t, ctx in dom_hits:
        print('  ✗ t=%-7s [%s]  …%s…' % (t, w, ctx))
    print('字幕命中 %d 处（用户稿件，按约定不擅改，仅提示）' % len(sub_hits))
    for w, t, ctx in sub_hits:
        print('  ⚠ [%s]  …%s…' % (w, ctx[:60]))

    print('=' * 62)
    if dom_hits:
        print('结论：画面文案需处理（片尾不得出现二维码 / 扫码 / 主页 / 搜索类引导词）')
        sys.exit(1)
    if sub_hits:
        print('结论：画面文案干净；字幕有 %d 处导流词，属用户原稿，请内容方决定' % len(sub_hits))
        sys.exit(2)
    print('结论：通过（画面文案与字幕均无风险词）')
    sys.exit(0)


if __name__ == '__main__':
    main()
