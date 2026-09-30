# -*- coding: utf-8 -*-
"""
第二步：自动定位每个 3D 元素主体的边界框（避开标题与标注文字），再抠图。

⚠️ 走过四条弯路，别回头：
  A) 单次二次曲面拟合背景 → 素材顶部有集中辉光，曲面在中下部被抬高，底边被过度扣除。
  B) IRLS 迭代重拟合       → 「下行失控」：拟合面越降越低，最后塌到 ≈0，残差图全亮，判据失效。
  C) 亮区行/列投影取主峰   → 行只要有任何亮点就被计入，标题让主峰从窗口顶就成立，框顶死。
  D) 亮度阈值 + 连通域     → 顶部辉光整片 >0.26，和元素连成同一个巨连通域，框吃掉整张片。
  结论：用**梯度**当判据 —— 辉光是平滑的（梯度≈0），元素本体才有强梯度。
  Sobel 幅值 → 阈值 → 膨胀桥接元素内部缝隙 → 连通域 → 按「面积大 + 质心靠中心」选主。
"""
import os, sys, json, glob
import numpy as np
import cv2
from PIL import Image, ImageDraw
from scipy import ndimage

SRC = os.environ.get('SRC') or (sys.argv[1] if len(sys.argv) > 1 else '.')   # 素材片目录（命令行第 1 个参数或 env SRC）
OUT = os.path.dirname(os.path.abspath(__file__))
TARGET = np.array([0x0F, 0x1A, 0x28], dtype=np.float32) / 255.0

PROBE_W = 1400
WIN = (0.08, 0.16, 0.92, 0.99)
GRAD_THR = 0.055                 # Sobel 幅值阈值
BRIDGE = 15                      # 桥接膨胀半径（px @ PROBE_W）
PAD = 0.055
OUT_W = 1800
# 人工核定框（读「网格验片_1~4.png」的 5% 网格读出）。自动定位对这类素材不可靠：
# 标题文字的边缘梯度比 3D 元素更强，任何纯图像判据都会先选中标题。别再去试自动了。
OVERRIDES = {
    '01': (0.04, 0.03, 0.54, 0.34),   # 玻璃晶体 + 圆盘（下沿收到 0.34，切掉源片标题顶部）
    '02': (0.30, 0.13, 0.82, 0.79),   # 三级平台
    '03': (0.10, 0.24, 0.52, 0.76),   # 传送带 + 书堆
    '04': (0.53, 0.16, 0.88, 0.76),   # 玻璃箱 + 锁
    '05': (0.06, 0.10, 0.50, 0.68),   # 书堆 / X / 蓝色大脑
    '06': (0.30, 0.06, 0.90, 0.74),   # 红蓝玻璃面板（面板内文字属图形本体）
    '07': (0.04, 0.34, 0.54, 0.84),   # 传送带 + 透镜 + 卫星天线
    '08': (0.08, 0.20, 0.54, 0.92),   # 暖色机械装置
    '09': (0.05, 0.21, 0.51, 0.53),   # ∞ 有效闭环（收掉上下标注气泡）
    '10': (0.28, 0.155, 0.82, 0.78),  # 玻璃球 + 人形（上沿下移，避开源片标题）
    '11': (0.05, 0.16, 0.54, 0.88),   # 炮管 + 齿轮
    '12': (0.28, 0.20, 0.72, 0.88),   # 扇面能量图（收掉右侧标注）
    '13': (0.12, 0.04, 0.52, 0.84),   # 光柱方盒
    '14': (0.24, 0.28, 0.90, 0.90),   # S 型金色赛道
    '15': (0.02, 0.38, 0.84, 0.88),   # 按钮 + 箭头（避开压在图上的标题）
}


def ring_offset(img, ring=0.07):
    H, W, _ = img.shape
    m = max(2, int(min(H, W) * ring))
    edge = np.concatenate([img[:m].reshape(-1, 3), img[-m:].reshape(-1, 3)])
    return edge.mean(0)


def locate(img):
    H, W, _ = img.shape
    g = np.clip(img, 0, 1).max(2).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=5)
    mag = np.sqrt(gx * gx + gy * gy)
    wx0, wy0, wx1, wy1 = int(WIN[0]*W), int(WIN[1]*H), int(WIN[2]*W), int(WIN[3]*H)
    win = np.zeros((H, W), bool)
    win[wy0:wy1, wx0:wx1] = True
    m = (mag > GRAD_THR) & win
    if m.sum() < 50:
        return WIN
    lab, n = ndimage.label(ndimage.binary_dilation(m, np.ones((BRIDGE, BRIDGE), bool)))
    objs = ndimage.find_objects(lab)
    coms = ndimage.center_of_mass(m, lab, range(1, n + 1))
    size = np.array([(m[o] & (lab[o] == i + 1)).sum() for i, o in enumerate(objs)], float)
    cy, cx = H / 2, W / 2
    score = np.array([size[i] / (1 + 5 * (((coms[i][0]-cy)/H)**2 + ((coms[i][1]-cx)/W)**2))
                      for i in range(n)])
    k = int(score.argmax())
    o = objs[k]
    b = [o[1].start, o[0].start, o[1].stop, o[0].stop]
    mx, my = (b[2] - b[0]) * 0.06, (b[3] - b[1]) * 0.06
    for i in range(n):
        y, x = coms[i]
        if size[i] < size[k] * 0.004:
            continue
        if b[0] - mx <= x <= b[2] + mx and b[1] - my <= y <= b[3] + my:
            oo = objs[i]
            b = [min(b[0], oo[1].start), min(b[1], oo[0].start),
                 max(b[2], oo[1].stop), max(b[3], oo[0].stop)]
    px, py = (b[2] - b[0]) * PAD, (b[3] - b[1]) * PAD
    return (max(0.0, b[0] - px) / W, max(0.0, b[1] - py) / H,
            min(W, b[2] + px) / W, min(H, b[3] + py) / H)


def main():
    global SRC
    if not os.path.isdir(SRC):
        raise SystemExit('请把素材片目录作为第 1 个参数，或设环境变量 SRC')
    files = sorted(glob.glob(os.path.join(SRC, '*.png')))
    boxes, sheet_rows = {}, []
    for f in files:
        n = os.path.basename(f).split('_')[-1].replace('.png', '')
        im = Image.open(f).convert('RGB')
        W, H = im.size
        p = im.resize((PROBE_W, int(H * PROBE_W / W)), Image.LANCZOS)
        box = OVERRIDES.get(n) or locate(np.asarray(p).astype(np.float32) / 255.0)
        boxes[n] = [round(v, 4) for v in box]

        x0, y0, x1, y1 = int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)
        c = im.crop((x0, y0, x1, y1))
        cw = OUT_W
        ch = int(c.height * cw / c.width)
        c = c.resize((cw, ch), Image.LANCZOS)
        a = np.asarray(c).astype(np.float32) / 255.0
        off = ring_offset(a)
        a = a - off + TARGET
        # 底色软过渡：外圈 12% 用径向羽化压到纯底色，便于在视频里用 mask 融进背景
        yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]].astype(np.float32)
        r = np.sqrt(((xx / a.shape[1] - .5) * 2) ** 2 + ((yy / a.shape[0] - .5) * 2) ** 2)
        k = np.clip((r - 0.72) / 0.46, 0, 1)[..., None]
        out = np.clip(a * (1 - k) + TARGET * k, 0, 1)
        Image.fromarray((out * 255).round().astype(np.uint8)).save(
            os.path.join(OUT, 'elem_%s.png' % n))
        print('elem_%s  源框 x%.3f-%.3f y%.3f-%.3f  →  %dx%d' % (n, box[0], box[2], box[1], box[3], cw, ch))
        sheet_rows.append((n, im.resize((300, int(H * 300 / W)), Image.LANCZOS), box))

    json.dump(boxes, open(os.path.join(OUT, 'crop_boxes.json'), 'w'), ensure_ascii=False, indent=1)

    # 双栏验片：左=检测框落在原片上的位置，右=抠出的元素
    cols, cw, chh = 5, 300, 190
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cw, rows * (chh + 22)), (12, 14, 20))
    d = ImageDraw.Draw(sheet)
    for i, (n, thumb, box) in enumerate(sheet_rows):
        x, y = (i % cols) * cw, (i // cols) * (chh + 22)
        sheet.paste(thumb, (x, y))
        tw, th = thumb.size
        d.rectangle([x + box[0] * tw, y + box[1] * th, x + box[2] * tw, y + box[3] * th],
                    outline=(255, 90, 90), width=2)
        e = Image.open(os.path.join(OUT, 'elem_%s.png' % n)).convert('RGB')
        e.thumbnail((cw - 8, chh - 26), Image.LANCZOS)
        sheet.paste(e, (x + (cw - e.width) // 2, y + 16 + (chh - 26 - e.height) // 2))
        d.text((x + 6, y + 2), 'elem_%s' % n, fill=(255, 220, 120))
    sheet.save(os.path.join(OUT, '定位验片.png'))
    print('\n验片 -> 定位验片.png（红框=自动检测的元素范围）')


if __name__ == '__main__':
    main()
