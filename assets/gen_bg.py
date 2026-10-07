# -*- coding: utf-8 -*-
"""烘焙背景底图 bg.png —— 四层光照结构，全程 numpy 向量化。

关键教训（来自 SKILL.md）：
  1. 绝不能用 PIL 的 ImageDraw.ellipse + ImageChops.multiply 画光照
     —— 负坐标 box 会几何反转，且 multiply 对极低值图像几乎不起压暗作用。
  2. 暗渐变必然 banding（同心环），必须三步消除：
     强模糊 10px → 亚 1 灰阶抖动 → 再轻模糊 1.6px。第三步最容易被省。
  3. 亮部用加法、暗角用乘性。全程乘性压不黑，全程加法四角发灰。
"""
import numpy as np
from PIL import Image, ImageFilter

W, H = 1080, 1920
rng = np.random.default_rng(20261005)

# ---- 四层参数 ----
BASE = 4.0          # A 炭基底，不要纯黑
WARM_PEAK = 13.0    # B 顶部主暖光（呼应品牌金）
COOL_PEAK = 5.0     # C 中部极淡冷调（冷暖对比 / 空气感）
VIG_FLOOR = 0.03    # D 四角强暗角，乘性

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

# ---- B 顶部主暖光：宽而柔的余弦平方衰减 ----
wy = np.clip(1.0 - yy / (H * 0.55), 0, 1)
wx = np.clip(1.0 - np.abs(xx - W / 2) / (W * 0.72), 0, 1)
warm = (wy ** 2) * (wx ** 1.4) * WARM_PEAK

# ---- C 中部极淡冷调 ----
cy = np.clip(1.0 - np.abs(yy - H * 0.50) / (H * 0.50), 0, 1)
cx = np.clip(1.0 - np.abs(xx - W / 2) / (W * 0.60), 0, 1)
cool = (cy ** 2) * (cx ** 2) * COOL_PEAK

# ---- 合成：BASE + 加法光照 ----
img = BASE + warm + cool

# ---- D 暗角：乘性，作用在归一化全量程上 ----
r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
r /= r.max()
vig = VIG_FLOOR + (1 - VIG_FLOOR) * np.clip(1.15 - 0.95 * r ** 1.6, 0, 1) ** 1.5
img *= vig

# ===== 消 banding 三步 =====
# 三步的量程必须统一在**最终 8-bit 量程**：抖动的作用是把量化误差随机化成高频噪声，
# 抖幅要 ≈1 个灰阶才有效。在放大 N 倍的量程里抖，降回后只剩 1/N 等于没抖（实测 6× 下环照旧）。
# ① 预平滑：核半径要覆盖等值线的尺度（几百 px），blur(10) 只把台阶边缘变锐，磨不掉带。
im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), 'L').convert('RGB')
im = im.filter(ImageFilter.GaussianBlur(40))                       # ① 强模糊抹平阶梯
arr = np.asarray(im).astype(np.float32) + rng.uniform(-0.95, 0.95, np.asarray(im).shape)
im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))       # ② 亚 1 灰阶抖动
im = im.filter(ImageFilter.GaussianBlur(1.6))                      # ③ 再轻模糊消噪点

im.save('bg.png')

# ---- 自检：逐行剖面 + 四角 ----
o = np.asarray(im.convert('L')).astype(np.float32)
prof = [float(o[y, W // 2]) for y in (0, 160, 320, 640, 960, 1400, 1760, H - 1)]
print('纵向剖面(y=0/160/320/640/960/1400/1760/1919):', ' → '.join('%.1f' % v for v in prof))
print('四角:', [tuple(np.asarray(im)[y, x]) for (x, y) in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1))])
print('中央:', '%.1f' % float(o[H // 2, W // 2]))

# 6× 增益图（1× 下看不出 banding，必须放大验证）
g = np.clip(np.asarray(im).astype(np.float32) * 6, 0, 255).astype(np.uint8)
Image.fromarray(g).save('bg_gain6x.png')
print('已输出 bg.png 与 bg_gain6x.png（后者用于验证 banding）')
