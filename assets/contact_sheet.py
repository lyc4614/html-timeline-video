# -*- coding: utf-8 -*-
"""把 check/ 下的抽帧拼成联系表，用于整体扫读（找可疑，不用于判定）。"""
import glob
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

SRC = sys.argv[1] if len(sys.argv) > 1 else 'check'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'check/_sheet.jpg'
COLS = int(sys.argv[3]) if len(sys.argv) > 3 else 5

fs = sorted(glob.glob(os.path.join(SRC, 't*.png')),
            key=lambda p: float(re.search(r't([\d.]+)\.png', p).group(1)))
if not fs:
    print('no frames in', SRC)
    sys.exit(1)

CW = 340
CH = round(CW * 1920 / 1080)
GAP, PAD, LBL = 12, 20, 40
rows = (len(fs) + COLS - 1) // COLS
W = PAD * 2 + COLS * CW + (COLS - 1) * GAP
H = PAD + rows * (CH + LBL + GAP)

font_paths = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"]
def font(sz):
    for p in font_paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

sheet = Image.new('RGB', (W, H), (16, 15, 14))
d = ImageDraw.Draw(sheet)
f = font(22)

for i, p in enumerate(fs):
    r, c = divmod(i, COLS)
    x = PAD + c * (CW + GAP)
    y = PAD + r * (CH + LBL + GAP)
    im = Image.open(p).convert('RGB').resize((CW, CH), Image.LANCZOS)
    sheet.paste(im, (x, y))
    d.rectangle([x - 1, y - 1, x + CW, y + CH], outline=(90, 86, 78), width=1)
    d.text((x + 2, y + CH + 8), re.search(r'(t[\d.]+)\.png', p).group(1), font=f, fill=(235, 220, 170))

sheet.save(OUT, quality=88)
print('saved:', OUT, sheet.size, 'frames=%d' % len(fs))
