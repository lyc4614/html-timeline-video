"""
参考视频风格背景底图生成器（1080x1920 竖屏）。

用途：把「底色 + 顶部辉光 + 暗角 + 星点」这四样最贵的静态元素烘焙成一张 PNG，
让 headless 逐帧渲染时只做位图 blit，而不是每帧 CPU 重算全屏渐变。
实测这样能把渲染从 0.25s/帧 降到 0.13s/帧。

用法：
    python gen_bg.py [输出路径]

标定方法（照着参考视频重做时）：
    抽一帧参考图，用 PIL 逐行取全行均值，看顶部最强叠加是 #RRGGBB，
    再调下面的 PEAK_* 参数直到生成图的逐行均值与之接近。
    参考实测：某抖音模板顶部 y=0 行均值 #200805（约 11-13% 橙红叠加）。

依赖：pillow
"""
import os
import sys
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1080, 1920
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bg.png")

# ---------------------------------------------------------------- 配色 / 强度
BASE = (0, 0, 0)                 # 底色。参考视频多为纯黑 #000000

# 顶部暖辉光带（橙红 → 品紫 → 青绿），peak 为 0-1 的峰值不透明度
SKY_GLOWS = [
    # (cx, cy, rx, ry, color, peak)
    (190, -230, 760, 520, (238, 96, 42), 0.190),    # 橙红（主，偏左更集中）
    (780, -300, 760, 450, (176, 64, 152), 0.130),   # 品紫
    (1130, 150, 580, 400, (34, 152, 142), 0.070),   # 青绿（右角）
    (540, -30, 990, 330, (255, 152, 72), 0.060),    # 画面中轴暖补光
]

# 底部极淡冷光，避免下半区死黑一片
BOTTOM_GLOWS = [
    (180, 2130, 880, 560, (30, 96, 130), 0.032),
    (980, 2190, 800, 500, (120, 60, 150), 0.028),
]

# 暗角：中心亮、四角暗。VIG_FLOOR 是角落保留的亮度比例
VIG_FLOOR = 0.29

# 星点
STAR_COUNT = 240        # 细星数量
STAR_BRIGHT_COUNT = 16  # 亮星数量（带柔光）
STAR_SEED = 20260922


def add_glow(base, cx, cy, rx, ry, color, peak, blur_k=0.55):
    """在 base 上叠一层软椭圆光。peak 为 0-1 的峰值不透明度。"""
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=int(peak * 255))
    mask = mask.filter(ImageFilter.GaussianBlur(min(rx, ry) * blur_k))
    base.paste(Image.new("RGB", (W, H), color), (0, 0), mask)
    return base


def build_stars():
    random.seed(STAR_SEED)
    stars = Image.new("RGB", (W, H), (0, 0, 0))
    sd = ImageDraw.Draw(stars)
    for _ in range(STAR_COUNT):
        x, y = random.uniform(0, W), random.uniform(0, H)
        r = random.uniform(1.0, 2.9)
        # 越靠上星点略亮（参考里上半区星点更密更亮）
        a = random.uniform(0.16, 0.80) * (1.0 - 0.25 * (y / H))
        v = int(255 * a)
        sd.ellipse([x - r, y - r, x + r, y + r], fill=(v, v, v))
    for _ in range(STAR_BRIGHT_COUNT):
        x, y = random.uniform(0, W), random.uniform(0, H * 0.92)
        r = random.uniform(2.6, 4.2)
        sd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))
    return stars.filter(ImageFilter.GaussianBlur(0.45))


def apply_vignette(img):
    """中心保留原亮度，四角压到 VIG_FLOOR。用一张模糊椭圆当乘数掩膜。"""
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * 0.42, -H * 0.26, W * 1.42, H * 1.26], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(250))
    floor = int(VIG_FLOOR * 255)
    vig = vig.point(lambda v: int(floor + (255 - floor) * (v / 255.0)))
    return ImageChops.multiply(img, Image.merge("RGB", (vig, vig, vig)))


def report(img, rows=(0, 40, 80, 120, 160, 200, 280, 400)):
    print("=== 生成图顶部行均值（对照参考标定）===")
    for y in rows:
        tot = [0, 0, 0]
        n = 0
        for x in range(0, W, 8):
            p = img.getpixel((x, y))
            tot[0] += p[0]
            tot[1] += p[1]
            tot[2] += p[2]
            n += 1
        print("   y=%3d  avg=#%02X%02X%02X" % (y, tot[0] // n, tot[1] // n, tot[2] // n))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    bg = Image.new("RGB", (W, H), BASE)
    for g in SKY_GLOWS + BOTTOM_GLOWS:
        bg = add_glow(bg, *g)
    bg = apply_vignette(bg)
    bg = ImageChops.add(bg, build_stars())
    bg.save(out, optimize=True)
    print("已生成: %s  (%.0f KB)" % (out, os.path.getsize(out) / 1024))
    report(bg)


if __name__ == "__main__":
    main()
