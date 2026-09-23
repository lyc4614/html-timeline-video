"""
参考「高级卡片」背景：纯黑 + 无雪花 + 极淡顶部暖光 + 强暗角
实测目标：顶部条(y=40..200) avg≈6.3 max≈38（含网格贡献）；底图辉光只需 avg≈5-6
四角必须压到 0-2
1080x1920 竖屏。网格由 CSS 叠层负责（可动），底图只管光。
"""
from PIL import Image, ImageDraw, ImageFilter, ImageChops

W, H = 1080, 1920

def soft(box, color, blur):
    lay = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(lay).ellipse(box, fill=color)
    return lay.filter(ImageFilter.GaussianBlur(blur))

def build(g1, g2, g3, vig_box, vig_blur):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    img = ImageChops.add(img, soft((-280, -660, W + 280, 520), g1, 300))
    img = ImageChops.add(img, soft((120, -460, W - 120, 320), g2, 240))
    img = ImageChops.add(img, soft((-220, H - 620, W + 220, H + 380), g3, 340))
    # 暗角：椭圆只覆盖中心，四周全黑
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse(vig_box, fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(vig_blur))
    return Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), vig)

def report(img, tag, save=None):
    s = [img.getpixel((x, y)) for y in range(40, 201, 4) for x in range(300, 781, 8)]
    n = len(s)
    top_avg = tuple(sum(c[i] for c in s)//n for i in range(3))
    corners = [img.getpixel(p) for p in [(5,5),(W-6,5),(5,H-6),(W-6,H-6)]]
    print(f"  {tag}\n    顶部 avg={top_avg} max={max(c[0] for c in s)}"
          f"\n    四角={corners}\n    中心(540,960)={img.getpixel((540,960))}"
          f"\n    上中(540,40)={img.getpixel((540,40))} 上中(540,200)={img.getpixel((540,200))}")
    if save: img.save(save, optimize=True)

# 网格基线约 3-5，底图辉光给 5 左右 → 合成后贴 6.3
IMG = build((30,28,19),(17,16,11),(7,8,11),(W*0.06,H*0.10,W*0.94,H*0.90),150)
report(IMG, "候选A: 辉光(9,8,5) 暗角收窄", "video/bg2.png")
