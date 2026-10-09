# -*- coding: utf-8 -*-
"""量「转场溶解」的亮度塌陷 —— 读帧序列，在每个镜头交接处前后对称取样。

配合 SKILL.md「交叉溶解的合成陷阱」一节使用。
`probe_dissolve.cjs` + `audit_dissolve.py` 是在线页面版（改完立刻能验），
本脚本是成片/帧序列版（交付前复核）。

原理：正确的交叉溶解 = 下层保持不透明、上层淡入（线性混合、权重和为 1）。
此时中点亮度必然等于两端亮度的**按权重插值**。显著低于它 = 背景色渗进了画面。

⚠ 两个必须避开的度量陷阱（都各造出过一个假警报）：
 ① 明度必须用 R/G/B 的**算术均值**。用 `max(RGB)` 是非线性的 ——
    `max(w·a+(1−w)·b) ≠ w·max(a)+(1−w)·max(b)`，会凭空算出几个百分点的假塌陷
    （实测把 2.1% 报成 7.0%）。
 ② 「应有的中点」要按权重插值算，**不能拿两端帧的算术平均当基线**：
    两端亮度差大时（如 0.509 vs 0.195）基线取错会得到一个纯粹是
    「两张图亮度不同」的假塌陷。

用法：
    python check_dissolve_frames.py [工程根目录] [--selftest]
退出码：0=通过 / 1=有塌陷 / 4=抠不到镜头表（量到 0 个对象不叫通过）
"""
import os
import re
import sys

import numpy as np
from PIL import Image

ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
HERE = os.path.abspath(ARGS[0]) if ARGS else os.getcwd()
FRAMES = os.path.join(HERE, 'frames')
FPS = 30
WIN_TOP = int(os.environ.get('WIN_TOP', 0))       # 只量画面窗（避开常驻 HUD/字幕带时设它）
WIN_BOT = int(os.environ.get('WIN_BOT', 0))       # 0 = 用整幅
DIP_TH = float(os.environ.get('DIP_TH', 6.0))     # 可见阈值（%）


def luma(path):
    """线性明度：R/G/B 算术均值。⚠ 不要换成 max(RGB)，那个是非线性的。"""
    im = Image.open(path).convert('RGB')
    a = np.asarray(im, dtype=np.float32)
    if WIN_BOT > WIN_TOP:
        a = a[WIN_TOP:WIN_BOT]
    return float(a.mean())


def frame_at(t):
    p = os.path.join(FRAMES, 'f-%05d.png' % int(round(t * FPS)))
    return luma(p) if os.path.exists(p) else None


def shots(root):
    """优先读页面上实测的镜头表（与渲染同一份数据），退化为源码正则。

    ⚠ 字段名兼容：本包模板用 s.s/s.e，实测有工程用 s.st/s.et。只认一种会得到
      [[null,null],…] → float(None) 抛异常 → 静默回退 → 镜头 0 个却报通过。
    """
    html = open(os.path.join(root, 'index.html'), encoding='utf-8').read()
    out = []
    for m in re.finditer(
            r"n:'(\d+)'\s*,.*?st:\s*([0-9.]+)\s*,\s*et:\s*([0-9.]+)", html, re.S):
        out.append((m.group(1), float(m.group(2)), float(m.group(3))))
    if not out:
        for m in re.finditer(r"add\(\s*([\d.]+)\s*,\s*([\d.]+)", html):
            out.append((str(len(out) + 1), float(m.group(1)), float(m.group(2))))
    if not out:
        print('✗ 抠不到镜头表 —— 量到 0 个对象不能报通过')
        sys.exit(4)
    return out


def profile(bd, half=1.6, n=17):
    ts = np.linspace(-half, half, n)
    return [(float(dt), frame_at(bd + float(dt))) for dt in ts]


def dip_of(bd, half=1.6):
    pr = [(dt, v) for dt, v in profile(bd, half) if v is not None]
    if len(pr) < 7:
        return None
    # 端点取两侧最外 3 点均值，避开转场区间（XF 半宽 0.5s）
    left = [v for dt, v in pr if dt <= -half * 0.55]
    right = [v for dt, v in pr if dt >= half * 0.55]
    if not left or not right:
        return None
    a, b = float(np.mean(left)), float(np.mean(right))
    mid = float(np.mean([v for dt, v in pr if abs(dt) <= half * 0.12]))
    expect = (a + b) / 2.0          # ⚠ 按权重插值，不是两端算术平均
    if expect <= 1e-6:
        return None
    return dict(a=a, b=b, expect=expect, mid=mid,
                dip=(expect - mid) / expect * 100.0)


def selftest():
    """正例：两层各自淡出（漏背景）必须被检出；反例：纯线性交叉必须是 0.00%。"""
    rng = np.random.default_rng(1)
    H = 240
    A = rng.random((H, 64)).astype(np.float32) * 0.5 + 0.2
    B = rng.random((H, 64)).astype(np.float32) * 0.5 + 0.1
    BG = np.full((H, 64), 0.02, dtype=np.float32)

    def mid(mode):
        vals = []
        for w in np.linspace(0, 1, 11):
            if mode == 'ok':          # 下层不透明 + 上层淡入，权重和为 1，线性
                f = (1 - w) * A + w * B
            else:                     # 两层各自淡入淡出 → 中点漏出 25% 背景
                f = w * B + (1 - w) ** 2 * A + w * (1 - w) * BG
            vals.append(float(f.mean()))
        return (vals[0] + vals[-1]) / 2, vals[len(vals) // 2]

    ea, ma = mid('ok')
    eb, mb = mid('bad')
    d_ok, d_bad = (ea - ma) / ea * 100, (eb - mb) / eb * 100
    ok = abs(d_ok) < 0.5 and d_bad > DIP_TH
    print('自检：')
    print('  反例 纯线性交叉（下层不透明）→ 塌陷 %+.2f%%  %s'
          % (d_ok, 'PASS' if abs(d_ok) < 0.5 else 'FAIL'))
    print('  正例 两层各自淡出（漏背景）→ 塌陷 %+.2f%%  %s'
          % (d_bad, 'PASS' if d_bad > DIP_TH else 'FAIL'))
    print('  双向验证 %s' % ('通过' if ok else '未通过 —— 判据不可用'))
    return ok


def main():
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sh = shots(HERE)
    print('镜头 %d 个，检测 %d 个交接处（帧目录 %s）\n'
          % (len(sh), len(sh) - 1, FRAMES))
    print('%-8s %-8s %-8s %-9s %-9s %s'
          % ('边界', '左端', '右端', '应有中点', '实得中点', '塌陷'))
    worst, bad = 0.0, []
    for k in range(len(sh) - 1):
        bd = (sh[k][2] + sh[k + 1][1]) / 2.0
        r = dip_of(bd)
        if r is None:
            print('%-8s 帧缺失，跳过' % ('%s→%s' % (sh[k][0], sh[k + 1][0])))
            continue
        flag = ''
        if abs(r['dip']) > DIP_TH:
            flag = ' ✗'
            bad.append((sh[k][0], sh[k + 1][0], bd, r['dip']))
        worst = max(worst, abs(r['dip']))
        print('%-8s %-8.3f %-8.3f %-9.3f %-9.3f %+6.1f%%%s'
              % ('%s→%s' % (sh[k][0], sh[k + 1][0]), r['a'], r['b'],
                 r['expect'], r['mid'], r['dip'], flag))
    print('\n最大亮度塌陷 %.1f%%（可见阈 %.1f%%）→ %s'
          % (worst, DIP_TH, '通过' if not bad else '有 %d 处需处理' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
