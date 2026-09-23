"""
参考视频视觉规格采样器。

用途：用户丢一个参考视频过来要求「照着它的背景/卡片/文字重做」时，
先用这个脚本把参考的**真实规格**量出来（而不是靠肉眼估色），再落到 CSS。

用法：
    # 1) 先抽帧
    ffmpeg -ss 30 -i ref.mp4 -frames:v 1 -y ref_frames/r00.png
    # 2) 采样
    python sample_ref.py ref_frames/r00.png

量四样：底色 / 网格（间距+线亮度）/ 辉光（逐行衰减）/ 卡片（边框层次+卡面色）
依赖：pillow
"""
import sys
from PIL import Image


def lum(p):
    return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]


def hx(p):
    return "#%02X%02X%02X" % p[:3]


def scan_rows(im, rows, label, x_step=8):
    W, _ = im.size
    print("\n=== %s ===" % label)
    for y in rows:
        tot = [0, 0, 0]
        n = 0
        for x in range(0, W, x_step):
            p = im.getpixel((x, y))
            tot[0] += p[0]
            tot[1] += p[1]
            tot[2] += p[2]
            n += 1
        print("   y=%4d  avg=%s" % (y, hx((tot[0] // n, tot[1] // n, tot[2] // n))))


def grid_spacing(im, x, y0, y1, label):
    """取一段干净暗区做纵向亮度剖面，用峰值 55% 为阈值找亮线，算相邻中心距。"""
    prof = [(y, lum(im.getpixel((x, y)))) for y in range(y0, y1)]
    mx = max(v for _, v in prof)
    if mx < 6:
        print("\n=== %s === 该区域过于平坦，换一个坐标再试" % label)
        return
    hits = [y for y, v in prof if v > mx * 0.55]
    groups = []
    for y in hits:
        if groups and y - groups[-1][-1] <= 2:
            groups[-1].append(y)
        else:
            groups.append([y])
    centers = [sum(g) // len(g) for g in groups]
    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    print("\n=== %s ===" % label)
    print("   亮线中心:", centers[:14])
    print("   间距(px):", gaps[:12] or "样本不足")
    if gaps:
        s = sorted(gaps)
        print("   中位间距: %d px   线亮度 lum=%.0f  色值=%s"
              % (s[len(s) // 2], mx, hx(im.getpixel((x, centers[0])))))
    print("   → 换算到 1080 宽:%s"
          % ("" if not gaps else " %.0f px" % (sorted(gaps)[len(gaps) // 2] * 1080 / im.size[0])))


def edge_scan(im, label, axis, fixed, rng):
    """沿一条线扫过卡片边缘，打印所有较亮像素，用来识别「外框 / 间隔 / 内线」层次。"""
    print("\n=== %s ===" % label)
    for v in rng:
        p = im.getpixel((v, fixed)) if axis == "x" else im.getpixel((fixed, v))
        if lum(p) > 35:
            print("   %s=%4d %s  lum=%.0f" % (axis, v, hx(p), lum(p)))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    path = sys.argv[1]
    im = Image.open(path).convert("RGB")
    W, H = im.size
    print("=== 参考帧 %s  %dx%d ===" % (path, W, H))

    # 1) 底色：取最暗片区的众数
    dark = im.crop((0, int(H * 0.75), W, int(H * 0.98)))
    px = sorted(dark.getdata(), key=lum)
    print("   底色（暗区中位数）:", hx(px[len(px) // 2]), " 最暗:", hx(px[0]))

    # 2) 辉光：逐行均值看衰减
    scan_rows(im, range(0, 480, 40), "顶部辉光逐行衰减（越亮说明辉光越强）")

    # 3) 网格：在暗区找一个坐标扫
    grid_spacing(im, W // 14, int(H * 0.78), int(H * 0.95), "网格纵向剖面")
    grid_spacing(im, int(H * 0.86), 0, W, "网格横向剖面（第2参为 x 时下面这行的调用参数需相应调）") \
        if False else None

    # 4) 星点密度
    cnt = 0
    for yy in range(int(H * 0.62), int(H * 0.95), 2):
        for xx in range(0, W, 2):
            if lum(im.getpixel((xx, yy))) > 60:
                cnt += 1
    print("\n=== 星点 === 暗区亮像素采样计数(步长2): %d" % cnt)

    print("\n提示：卡片边框层次请手动指定一条扫过卡片边缘的线，调 edge_scan(im, label, axis, fixed, range) 查看。")


if __name__ == "__main__":
    main()
