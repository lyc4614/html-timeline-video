"""字体候选对比总览图：把同一文案、同一金色渐变的多个字体版本拼成一张评审图。

用法：
    python make_specimen_sheet.py --src <截图目录> [--out <输出png>] \
        [--items "0_思源宋体Black.png|0 思源宋体 Black ★推荐|1,..."]

约定：截图同为 1080×1920，只裁标题区放大，便于比较笔画粗细。
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# 中文字体：按平台找一个可用的
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]

TW = 340                 # 每格缩略图宽
TH = round(TW * 1920 / 1080)
GAP = 20
LABEL_H = 52
PAD = 24
COLS, ROWS = 3, 2

# 只裁标题区（按 1080×1920 画布）—— 需要时按自己版面改
CROP = (0, 480, 1080, 1260)


def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='素材截图目录')
    ap.add_argument('--out', default=None, help='输出 png（默认写在 src 下）')
    ap.add_argument('--items', required=True,
                    help='"文件名|标签|是否推荐(1/0)" 用逗号分隔')
    a = ap.parse_args()

    items = []
    for chunk in a.items.split(','):
        parts = chunk.split('|')
        fn, label = parts[0], (parts[1] if len(parts) > 1 else parts[0])
        rec = (len(parts) > 2 and parts[2].strip() == '1')
        items.append((fn, label, rec))
    if not items:
        sys.exit('--items 为空')

    W = PAD * 2 + COLS * TW + (COLS - 1) * GAP
    H = PAD * 2 + ROWS * (TH + LABEL_H) + (ROWS - 1) * GAP + 44
    sheet = Image.new('RGB', (W, H), (8, 8, 8))
    d = ImageDraw.Draw(sheet)
    f_title = load_font(30)
    f_label = load_font(22)

    d.text((PAD, PAD - 6), '标题字体候选（同一文案、同一金色渐变）',
           font=f_title, fill=(226, 203, 138))
    top0 = PAD + 44

    for i, (fn, label, _rec) in enumerate(items):
        path = os.path.join(a.src, fn)
        if not os.path.exists(path):
            print('!! 缺 %s（跳过）' % path)
            continue
        r, c = divmod(i, COLS)
        x = PAD + c * (TW + GAP)
        y = top0 + r * (TH + LABEL_H + GAP)
        im = Image.open(path).convert('RGB').crop(CROP)
        im = im.resize((TW, round(TW * (CROP[3] - CROP[1]) / (CROP[2] - CROP[0]))), Image.LANCZOS)
        sheet.paste(im, (x, y))
        d.rectangle([x - 1, y - 1, x + TW, y + im.size[1]], outline=(70, 62, 40), width=1)
        col = (232, 214, 150) if '推荐' in label or '★' in label else (188, 184, 168)
        d.text((x + 4, y + im.size[1] + 14), label, font=f_label, fill=col)

    out = a.out or os.path.join(a.src, '_总览_字体候选.png')
    sheet.save(out)
    print('saved:', out, sheet.size)


if __name__ == '__main__':
    main()
