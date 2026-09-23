# -*- coding: utf-8 -*-
"""读 _motion/ 小图序列，算相邻帧平均绝对差，输出「静止跑段」排行。

静止跑段 = 连续若干帧的运动量都低于阈值 → 观众看到的就是一张静置的图。
这正是用户会反馈的那种「从 X 秒到 Y 秒有 8 秒空场」。
"""
import glob
import os
import sys

from PIL import Image
import numpy as np

STEP = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
D = (sys.argv[1] if len(sys.argv) > 1 else '_motion')
# 阈值必须自标定，不能写死。
# 踩过的坑：第一版写死 0.006，结果恰好落在全片中位数 0.00479 附近，
# 等于把一半片子判成「静止」—— 静止占比 34.8%，改完内容反而升到 35.8%，
# 看起来「改了没用」，其实是尺子错了。
# 正确做法：先算出全片帧差中位数（那是背景呼吸的本底噪声），
# 再取 1.8× 中位数当作「确实有新东西出现」的门限。
TH_AUTO = True
TH_FLOOR = 0.005

fs = sorted(glob.glob(os.path.join(D, '*.png')))
prev = None
diffs = []
for f in fs:
    a = np.asarray(Image.open(f).convert('L'), dtype=np.float32) / 255.0
    if prev is None:
        diffs.append(0.0)
    else:
        diffs.append(float(np.abs(a - prev).mean()))
    prev = a

# 自标定阈值：中位数是本底（背景呼吸），1.8 倍视作「有新东西出现」
med = sorted(diffs)[len(diffs) // 2]
TH = max(TH_FLOOR, med * 1.8) if TH_AUTO else TH_FLOOR
print('帧差中位数 %.5f → 采用阈值 %.5f（%.2f× 中位数）' % (med, TH, TH / med if med else 0))

# 找静止跑段
runs = []
i = 0
while i < len(diffs):
    if diffs[i] < TH:
        j = i
        while j + 1 < len(diffs) and diffs[j + 1] < TH:
            j += 1
        dur = (j - i + 1) * STEP
        if dur >= 2.0:
            runs.append((i * STEP, (j + 1) * STEP, dur))
        i = j + 1
    else:
        i += 1

runs.sort(key=lambda r: -r[2])
print('阈值 %s，共 %d 帧，静止跑段（≥2s）%d 段' % (TH, len(fs), len(runs)))
print()
print('%-4s %-20s %8s' % ('#', '时间区间', '静止时长'))
for k, (a, b, d) in enumerate(runs[:15], 1):
    flag = ' ✗ 需补内容' if d > 4 else (' ⚠' if d > 3 else '')
    print('%-4d %6.1fs → %6.1fs   %7.1fs%s' % (k, a, b, d, flag))

tot = sum(r[2] for r in runs)
print()
print('静止总时长 %.1fs / 全片 %.1fs = %.1f%%' % (tot, len(fs) * STEP, tot / (len(fs) * STEP) * 100))
