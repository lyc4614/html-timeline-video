# -*- coding: utf-8 -*-
"""把顶部光束烘焙成一张 RGBA 位图 beam.png，替代 CSS 的两层渐变。

为什么：headless Chrome 是软件光栅、无 GPU，**全屏渐变逐帧 CPU 重算很贵**。
实测这层光束用 CSS radial-gradient 要 +0.066 s/帧（0.239 → 0.305），加了 blur(30px) 更是 +0.105。
烘焙成位图后只剩一次 blit —— 与背景底图同样的做法。

参数与原先的 CSS 一一对应（改设计时两边都要动）：
  .bsrc  : 元素 left:50%, top:-230px, 1080×520, radial closest-side
           → 圆心 (540, 30)，半径 260
           stops  0%:.20  46%:.076  78%:0
  .bcone : 元素 left:50%, top:-60px, 760×1180, radial 50% 100% at 50% 0%
           → 椭圆中心 (540, -60)，半径 x=380 y=1180
           stops  0%:.130  26%:.078  50%:.034  68%:.010  84%:0

用法：python gen_beam.py   （需要 numpy + Pillow，用系统 Python311）
"""
import os, sys
import numpy as np
from PIL import Image

# 画幅与输出都可配：VIDEO_W / VIDEO_H 环境变量；输出文件名走命令行第一个参数
W = int(os.environ.get('VIDEO_W', 1080))
H = int(os.environ.get('VIDEO_H', 1920))
OUT = sys.argv[1] if len(sys.argv) > 1 else 'beam.png'
RGB = (255, 243, 212)          # 暖白光（贴合金色品牌调）；冷光改 (232,240,255)
CX = W / 2.0

# ⚠ 下面的半径/中心都是**按 1080×1920 标定的绝对值**，换画幅时要按比例一起调，
#   否则横版会得到一束又窄又长的光。

yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)


def ramp(d, stops):
    """按 stop 列表线性插值；stops = [(pos, alpha), ...]，pos 升序，最后一项之后取末值"""
    a = np.full_like(d, stops[-1][1])
    for i in range(len(stops) - 1):
        p0, a0 = stops[i]
        p1, a1 = stops[i + 1]
        m = (d >= p0) & (d < p1)
        t = (d[m] - p0) / (p1 - p0)
        a[m] = a0 + (a1 - a0) * t
    a[d < stops[0][0]] = stops[0][1]
    return a


# ① 顶部光池：圆，中心 (540, 30)，半径 260
d_src = np.sqrt((xx - CX) ** 2 + (yy - 30.0) ** 2) / 260.0
a_src = ramp(d_src, [(0.0, .200), (0.46, .076), (0.78, 0.0)])

# ② 光锥：椭圆，中心 (540, -60)，半径 x=380 y=1180
d_cone = np.sqrt(((xx - CX) / 380.0) ** 2 + ((yy + 60.0) / 1180.0) ** 2)
a_cone = ramp(d_cone, [(0.0, .130), (0.26, .078), (0.50, .034), (0.68, .010), (0.84, 0.0)])

# 两层半透明叠加：1-(1-a1)(1-a2)
alpha = 1.0 - (1.0 - a_src) * (1.0 - a_cone)
alpha = np.clip(alpha, 0.0, 1.0)

out = np.zeros((H, W, 4), dtype=np.uint8)
out[..., 0] = RGB[0]
out[..., 1] = RGB[1]
out[..., 2] = RGB[2]
out[..., 3] = np.round(alpha * 255.0).astype(np.uint8)

Image.fromarray(out, 'RGBA').save(OUT)

# 自检：纵向剖面（画面中轴）与峰值
col = alpha[:, int(CX)]
pts = [0, 120, 300, 600, 900, 1200, 1600, 1900]
prof = ' → '.join('%.3f' % col[p] for p in pts)
print('%s 已生成  %dx%d' % (OUT, W, H))
print('  中轴纵向 alpha 剖面（y=0/120/300/600/900/1200/1600/1900）：')
print('   ' + prof)
print('  峰值 alpha = %.3f @ y=%d' % (alpha.max(), int(np.argmax(alpha.max(axis=1)))))
print('  视口尺寸 %d x %d' % (W, H))
