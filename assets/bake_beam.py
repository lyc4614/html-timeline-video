# -*- coding: utf-8 -*-
"""把 beam.png 的光束**并进 bg.png**，让光束不再是一层独立的全屏合成。

为什么必须并进去（实测记录）：
  · 无光束                     0.239 s/帧
  · 光束 = CSS radial-gradient 0.305 s/帧
  · 光束 = CSS + filter:blur   0.344 s/帧
  · 光束 = 独立 PNG 图层       0.335 s/帧   ← 换位图并没有救回来
结论：贵的不是「渐变 vs 位图」，而是**多了一层全屏 alpha 合成** ——
headless 无 GPU，每帧都要把 1080×1920 再遍历混合一遍。
并进底图后，光束随底图那一次 blit 一起完成，成本归零。

⚠️ 本脚本会覆盖 bg.png。原图备份为 bg_plain.png，可随时回退。
⚠️ 若重新运行 gen_bg.py 生成底图，光束会丢 —— 必须再跑一次本脚本。
   顺序：gen_bg.py → gen_beam.py → bake_beam.py

用法：python bake_beam.py   （需要 numpy + Pillow，用系统 Python311）
"""
import os, shutil
import numpy as np
from PIL import Image

MARGIN = int(os.environ.get('BLEED', 140))    # #bg 的 inset:-140px 出血偏移
BG    = os.environ.get('BG', 'bg.png')
BEAM  = os.environ.get('BEAM', 'beam.png')
PLAIN = os.environ.get('BG_PLAIN', 'bg_plain.png')

if not os.path.exists(PLAIN):
    shutil.copyfile(BG, PLAIN)
    print('已备份原始底图 → %s' % PLAIN)
elif os.path.exists(PLAIN):
    # 从"无光束"的原图重新合成，保证可重复运行（不会把光束叠两次）
    shutil.copyfile(PLAIN, BG)

bg = np.array(Image.open(BG).convert('RGB'), dtype=np.float32)
bm = np.array(Image.open(BEAM).convert('RGBA'), dtype=np.float32)
H, W = bm.shape[:2]
assert bg.shape[0] >= MARGIN + H and bg.shape[1] >= MARGIN + W, \
    '底图 %s 装不下光束 %dx%d + 出血 %d' % (bg.shape, H, W, MARGIN)

sub = bg[MARGIN:MARGIN + H, MARGIN:MARGIN + W]
alpha = bm[..., 3:4] / 255.0
sub[:] = sub * (1.0 - alpha) + bm[..., :3] * alpha
bg[MARGIN:MARGIN + H, MARGIN:MARGIN + W] = sub

Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).save(BG)

# 自检：并进去之后，画面中轴上下应该明显变亮，且往下衰减
out = np.array(Image.open(BG).convert('RGB'), dtype=np.float32)
col = out[:, MARGIN + W // 2, :].mean(axis=1)
pts = [0, 120, 300, 600, 900, 1200, 1600, 1900]
prof = ' → '.join('%.1f' % col[MARGIN + p] for p in pts)
print('光束已并入 %s（%dx%d）' % (BG, bg.shape[1], bg.shape[0]))
print('  中轴亮度剖面（视口 y=0/120/300/600/900/1200/1600/1900）：')
print('   ' + prof)
print('  y=0 相对 y=1900 的提亮：+%.1f' % (col[MARGIN + 0] - col[MARGIN + 1900]))
