"""通用评审对比总览图
用法：python make_compare_sheet.py <目录> "<标签1|标签2|...>" <输出文件名> ["标题"]
按文件名排序取该目录下所有 png，裁掉上下空白后横排拼一张对比图。
"""
import sys, os, glob
from PIL import Image, ImageDraw, ImageFont

DIR = sys.argv[1]
LABELS = sys.argv[2].split('|')
OUTNAME = sys.argv[3]
TITLE = sys.argv[4] if len(sys.argv) > 4 else None

FONT_PATHS = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simhei.ttf"]

def load_font(size):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

files = sorted(glob.glob(os.path.join(DIR, "*.png")))
files = [f for f in files if not os.path.basename(f).startswith("_")]
assert len(files) == len(LABELS), f"图片 {len(files)} 张，标签 {len(LABELS)} 个，不匹配"

CROP = (0, 320, 1080, 1620)      # 竖屏稿的内容安全区
COL_W = 400
GAP = 22
PAD = 30
LABEL_H = 56

imgs = []
for f in files:
    im = Image.open(f).convert("RGB").crop(CROP)
    r = COL_W / im.width
    imgs.append(im.resize((COL_W, int(im.height * r)), Image.LANCZOS))

col_h = imgs[0].height
top = PAD + (LABEL_H + 14 if TITLE else 0)
W = PAD * 2 + COL_W * len(imgs) + GAP * (len(imgs) - 1)
H = top + LABEL_H + col_h + PAD

canvas = Image.new("RGB", (W, H), (13, 13, 13))
d = ImageDraw.Draw(canvas)
f_title = load_font(34)
f_label = load_font(28)

y = PAD
if TITLE:
    d.text((PAD, y), TITLE, font=f_title, fill=(238, 216, 158))
    y += LABEL_H + 14

for i, im in enumerate(imgs):
    x = PAD + i * (COL_W + GAP)
    d.text((x + 2, y), LABELS[i], font=f_label, fill=(200, 200, 205))
    canvas.paste(im, (x, y + LABEL_H))
    # 细边框，区分相邻稿
    d.rectangle([x - 1, y + LABEL_H - 1, x + COL_W, y + LABEL_H + col_h],
                outline=(58, 58, 62), width=1)

out = os.path.join(DIR, OUTNAME)
canvas.save(out, optimize=True)
print("已输出", out, canvas.size)
