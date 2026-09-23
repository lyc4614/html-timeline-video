"""
暗调背景底图生成器（默认 1080x1920 竖屏）—— 把"背景"当成一个有光的环境来画。

用途：把「基底 + 主光源 + 冷调托底 + 暗角」这四层静态元素烘焙成一张 PNG，
让 headless 逐帧渲染时只做位图 blit，而不是每帧 CPU 重算全屏渐变。
实测能把渲染从 0.25s/帧 降到 0.13s/帧。

================================ 为什么是四层 ================================
客户说「背景不够高级」时，**不要加金线/花纹/粒子**。
暗场显廉价通常只有一个原因：背景是一块均匀的死黑，没有光。
四层的分工：

    A. 基底        定整体基调，**不要纯黑**（纯黑 = 没有环境）
    B. 顶部主暖光  画面的"光源"，色相应呼应品牌主色
    C. 中部冷调    极淡，制造冷暖对比与"空气感"
    D. 四周暗角    压回近纯黑，把注意力压向中心

关键原则（踩坑换来的）：
  · **亮部用加法，暗角用乘性**。全程乘性会压不黑；全程加法四角会发灰。
  · 背景整体必须**明显暗于卡片**，卡片才有"浮起来"的余地。
    目标：中部行均值 ≈ 8~14（V≈0.035~0.055），这样卡面做到 V 0.16+ 时对比度拉得开。
  · 四角必须回到近纯黑（0~4），否则网格铺满会显得廉价。
  · **不要雪点/星点** —— 会被判定为"脏"（多支参考片实测孤立亮点为 0）。

============================ 暗渐变必然 banding ============================
8-bit 量化在暗渐变里会产生肉眼可见的同心环。三步缺一不可，顺序也不能换：

    ① GaussianBlur(10)     先把阶梯抹平
    ② 亚 1 灰阶抖动        打散残留量化台阶
    ③ GaussianBlur(1.6)    消噪（**最容易被省、也最不能省**）
       —— 少了 ③ 噪点会被 H.264 放大成"脏"

验证：把底图 **6× 增益**后看，环和条带会放大到肉眼可辨。
1× 下看不出来不代表没有。

============================ 别用 PIL 的 ImageDraw 画光照 ============================
`ImageDraw.ellipse` 给负坐标会几何反转；`ImageChops.multiply` 对极低值图像
几乎不起压暗作用（第一版这么写，输出 R 均值 91 / 目标 5，四角根本没变黑）。
**全程用 numpy 向量化**：径向衰减用余弦平方，光照用加法，暗角用乘性。

用法：
    python gen_bg.py [输出路径，默认 bg.png] [宽] [高]

依赖：numpy, pillow
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bg.png")
W = int(sys.argv[2]) if len(sys.argv) > 2 else 1080
H = int(sys.argv[3]) if len(sys.argv) > 3 else 1920

# ------------------------------ 可调参数 ------------------------------
# 调参方法：先跑一次看「逐行均值」自检输出，再对着下面这组目标值微调。
BASE = 4                      # A. 基底灰度（0=纯黑，建议 3~6）
VGRAD_TOP, VGRAD_BOT = 3, -2  #   垂直缓变：上略亮、下略暗
WARM_PEAK = 13                # B. 顶部主暖光峰值（加到 R 通道）
COOL_PEAK = 5                 # C. 中部冷调峰值（加到 B 通道）
VIGNETTE_FLOOR = 0.03         # D. 四角保留比例（越小角越黑，0.02~0.05）
# ---------------------------------------------------------------------


def radial(cx, cy, rx, ry, peak):
    """以 (cx,cy) 为中心、半径 (rx,ry) 的径向衰减。

    用余弦平方而非高斯：衰减在边缘处更"实"，不会拖出无边的灰雾。
    """
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    d = np.clip(d, 0, 1)
    return peak * (np.cos(d * np.pi) * 0.5 + 0.5) ** 2


def main():
    img = np.zeros((H, W, 3), np.float32)
    img[:, :, :] = BASE

    # ---------- 垂直缓变：上略亮、下略暗 ----------
    t = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    vg = VGRAD_TOP + (VGRAD_BOT - VGRAD_TOP) * t
    img[:, :, 0] += vg
    img[:, :, 1] += vg * 0.96
    img[:, :, 2] += vg * 1.02

    # ---------- B. 顶部主暖光（画面的"光源"）----------
    warm = radial(W * 0.5, H * 0.16, W * 0.95, H * 0.52, WARM_PEAK)
    img[:, :, 0] += warm
    img[:, :, 1] += warm * 0.62
    img[:, :, 2] += warm * 0.30

    # 更窄的暖核，做出"光源中心"的实感（只加宽会变成一片发灰的雾）
    core = radial(W * 0.5, H * 0.10, W * 0.52, H * 0.26, WARM_PEAK * 0.55)
    img[:, :, 0] += core
    img[:, :, 1] += core * 0.66
    img[:, :, 2] += core * 0.34

    # ---------- C. 中部冷调托底（冷暖对比 + 空气感）----------
    cool = radial(W * 0.5, H * 0.72, W * 1.05, H * 0.58, COOL_PEAK)
    img[:, :, 0] += cool * 0.42
    img[:, :, 1] += cool * 0.56
    img[:, :, 2] += cool

    # ---------- D. 四周暗角：四角回近纯黑 ----------
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = (xx - W * 0.5) / (W * 0.62)
    dy = (yy - H * 0.5) / (H * 0.58)
    r = np.sqrt(dx ** 2 + dy ** 2)
    vig = np.clip(1.0 - 0.92 * np.clip(r, 0, 1.35) ** 1.7, VIGNETTE_FLOOR, 1.0)
    img *= vig[:, :, None]

    img = np.clip(img, 0, 255).astype(np.uint8)
    out = Image.fromarray(img, "RGB")

    # ---------- banding 三步（顺序不可换，③ 不可省）----------
    out = out.filter(ImageFilter.GaussianBlur(10))            # ① 抹平阶梯
    arr = np.asarray(out, np.float32)
    rng = np.random.default_rng(20260923)
    arr += rng.uniform(-0.9, 0.9, arr.shape)                  # ② 亚 1 灰阶抖动
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    out = out.filter(ImageFilter.GaussianBlur(1.6))           # ③ 消噪

    out.save(OUT)
    print("saved:", OUT, out.size)

    # ------------------------------ 自检 ------------------------------
    px = out.load()
    step = max(1, H // 12)
    print("\n逐行均值（每 %dpx 一行）：" % step)
    for y in range(0, H, step):
        s = sum(px[x, y][0] for x in range(0, W, 12)) / len(range(0, W, 12))
        print("  y=%-5d  R均值 %5.1f  %s" % (y, s, "#" * int(s * 3)))
    print("\n四角（必须 0~4）:", [tuple(px[x, y]) for x, y in
                                 [(4, 4), (W - 5, 4), (4, H - 5), (W - 5, H - 5)]])
    mid_lo, mid_hi = int(H * 0.49), int(H * 0.58)
    vals = [px[x, y][0] for y in range(mid_lo, mid_hi, 20) for x in range(200, 880, 40)]
    print("中央区（y%d~%d 行均值）: %.1f" % (mid_lo, mid_hi, sum(vals) / len(vals)))
    print("\n目标：峰值行 8~14 / 四角 0~4 / 中央区 3~6")


if __name__ == "__main__":
    main()
