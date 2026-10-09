# -*- coding: utf-8 -*-
"""读 _motion/ 小图序列，找「画面真的没动」的段落。

静止跑段 = 观众看到的就是一张静置的图。这正是用户会反馈的
「从 X 秒到 Y 秒有 8 秒空场」。

用法：python check_motion.py [_motion] [step_s] [--selftest]

──────────────────────────────────────────────────────────────────
⚠ 判据必须是「滞后窗口内的可见变化量」，不能是「相邻帧瞬时差」。

踩过的坑（2026-10-09，深圳中考低公办片）：第一版用相邻帧平均绝对差
（MAE），阈值自标定为 1.8× 中位数。结果报出「静止总时长 94.6%、
15 段需补内容」—— 但同一批帧做逐字节 MD5 比对，**513 对相邻帧
100% 各不相同，没有一段是冻结的**。

根因：本片运镜是「缓慢但连续」的，每 0.5s 的位移本来就小于背景呼吸
的量级，瞬时差法在原理上无法把「慢运镜」和「真冻结」分开；而且
1.8×中位数 这个自标定假设分布是双峰的（呼吸 vs 真运动），单峰时
会把过半样本判成静止。**一个假警报比没有检查更糟** —— 它会让人去改
本来没问题的镜头。

正解：比较**相隔 LAG 帧（默认 2s）**的两帧，并只看产生「可见变化」
（>4 个灰阶）的像素占比。
  · 真冻结：2s 后画面几乎逐像素相同 → 占比 ≈ 0
  · 慢运镜：位移累积 2s 后普遍越过 4 灰阶 → 占比到达百分之几
    实测本片最安静处（镜 01 起手）仍有 5.0% 像素可见变化，
    而判据阈值 0.5% —— 相差一个数量级，区分力充足。
"""

import glob
import os
import sys

import numpy as np
from PIL import Image

# ── 参数 ────────────────────────────────────────────────────────────
ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
SELFTEST = '--selftest' in sys.argv
D = ARGS[0] if len(ARGS) > 0 else '_motion'
STEP = float(ARGS[1]) if len(ARGS) > 1 else 0.5          # 帧间隔（秒）
LAG_S = float(ARGS[2]) if len(ARGS) > 2 else 2.0          # 滞后窗口（秒）
GRAY_EPS = 4.0 / 255.0        # 「可见变化」的灰阶门限：4/255
FROZEN_FRAC = 0.005           # 可见变化像素占比 < 0.5% 视为冻结
MIN_DUR = 2.0                 # 冻结段最短时长（秒）


def load(paths):
    return [np.asarray(Image.open(p).convert('L'), dtype=np.float32) / 255.0
            for p in paths]


def visible_frac(aps, lag):
    """滞后 lag 帧的两帧之间，变化超过 GRAY_EPS 的像素占比。"""
    out = []
    for i in range(len(aps) - lag):
        out.append(float((np.abs(aps[i + lag] - aps[i]) > GRAY_EPS).mean()))
    return np.array(out, dtype=np.float64)


def find_runs(frac, lag, step, th, min_dur):
    low = frac < th
    runs = []
    i = 0
    while i < len(low):
        if low[i]:
            j = i
            while j + 1 < len(low) and low[j + 1]:
                j += 1
            dur = (j - i + 1 + lag) * step
            if dur >= min_dur:
                runs.append((i * step, (j + 1 + lag) * step, dur))
            i = j + 1
        else:
            i += 1
    return runs


def report(aps, step, lag_s):
    lag = max(1, int(round(lag_s / step)))
    frac = visible_frac(aps, lag)
    n, total = len(aps), len(aps) * step
    print('帧 %d 个 / 帧间隔 %.2fs / 滞后窗口 %.1fs（%d 帧）' % (n, step, lag * step, lag))
    print('判据：滞后窗口内变化 >4 灰阶 的像素占比 < %.1f%% 视为冻结\n' % (FROZEN_FRAC * 100))

    print('可见变化占比分布：')
    print('   最小 %.2f%%   1%%分位 %.2f%%   中位 %.2f%%   95%%分位 %.2f%%'
          % (frac.min() * 100, np.percentile(frac, 1) * 100,
             np.median(frac) * 100, np.percentile(frac, 95) * 100))
    k = min(6, len(frac))
    idx = np.argsort(frac)[:k]
    print('   最安静的 %d 个时点：' % k)
    for i in sorted(idx):
        print('      t=%7.1fs   仅 %5.2f%% 像素有可见变化' % (i * step, frac[i] * 100))

    runs = find_runs(frac, lag, step, FROZEN_FRAC, MIN_DUR)
    print()
    if not runs:
        print('✓ 无冻结段。全片最安静的时段也有 %.2f%% 像素在动（判据 %.1f%%），'
              '相差 %.0f 倍。' % (frac.min() * 100, FROZEN_FRAC * 100,
                                 frac.min() / FROZEN_FRAC))
    else:
        runs.sort(key=lambda r: -r[2])
        print('✗ 冻结段 %d 处（画面真的没动，需要补内容）：' % len(runs))
        print('%-4s %-22s %10s' % ('#', '时间区间', '冻结时长'))
        for k2, (a, b, d) in enumerate(runs[:15], 1):
            print('%-4d %6.1fs → %6.1fs %9.1fs' % (k2, a, b, d))
        tot = sum(r[2] for r in runs)
        print('\n冻结合计 %.1fs / 全片 %.1fs = %.1f%%' % (tot, total, tot / total * 100))
    return runs, frac


# ── 双向自检 ────────────────────────────────────────────────────────
def _runs(aps, step, lag_s):
    lag = max(1, int(round(lag_s / step)))
    frac = visible_frac(aps, lag)
    return find_runs(frac, lag, step, FROZEN_FRAC, MIN_DUR), frac


def selftest():
    """正例：真冻结必须被检出；反例：缓慢位移必须不被误判。"""
    rng = np.random.default_rng(0)
    H = W = 96
    base = rng.random((H, W)).astype(np.float32)
    step, lag_s = 0.5, 2.0

    # 正例 1：完全冻结 10s（20 帧，画面逐像素不变）
    frozen = [base.copy() for _ in range(20)]
    r1, _ = _runs(frozen, step, lag_s)
    ok1 = len(r1) >= 1 and max(r[2] for r in r1) >= 8.0

    # 正例 2：只加极弱噪声（幅度 1 灰阶，低于可见门限）→ 仍应视为冻结
    weak = [base + rng.integers(-1, 2, (H, W)).astype(np.float32) / 255.0
            for _ in range(20)]
    r2, _ = _runs(weak, step, lag_s)
    ok2 = len(r2) >= 1

    # 反例：缓慢平移（每 0.5s 移 1px，2s 累积 4px）→ 不得报冻结
    pan = [np.roll(base, i, axis=1) for i in range(20)]
    r3, f3 = _runs(pan, step, lag_s)
    ok3 = len(r3) == 0

    print('自检：')
    print('  正例1 完全冻结 10s          → %s（检出 %d 段）' % ('PASS' if ok1 else 'FAIL', len(r1)))
    print('  正例2 弱噪声(<1 灰阶)       → %s（检出 %d 段）' % ('PASS' if ok2 else 'FAIL', len(r2)))
    print('  反例  每 0.5s 移 1px 慢摇   → %s（误报 %d 段）' % ('PASS' if ok3 else 'FAIL', len(r3)))
    ok = ok1 and ok2 and ok3
    print('  双向验证 %s' % ('通过' if ok else '未通过 —— 判据不可用'))
    return ok


def main():
    if SELFTEST:
        sys.exit(0 if selftest() else 1)
    paths = sorted(glob.glob(os.path.join(D, '*.png')))
    if not paths:
        print('✗ %s 下没有帧 —— 先跑 check_motion.cjs 生成序列（量到 0 个对象不能报通过）' % D)
        sys.exit(4)
    aps = load(paths)
    runs, _ = report(aps, STEP, LAG_S)
    sys.exit(1 if runs else 0)


if __name__ == '__main__':
    main()
