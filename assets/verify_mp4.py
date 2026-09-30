# -*- coding: utf-8 -*-
"""从「编码后的成片」反抽帧：拼接触表 + 与渲染前静帧做 PSNR 保真比对。

为什么必须做：H.264 的色度下采样 / 量化 / 去条带都可能吃掉细节或放大噪点，
只看渲染前的静帧等于没验收。

两个坑：**抽帧时刻**与**帧对齐**。
- 抽帧时刻一律取自内嵌 SUBS 表的**字幕中点**（不凭印象取整）。
- 比对帧号用 `i = round(t*FPS)`，并允许 **±2 帧对齐取最大 PSNR** ——
  ffmpeg 的 `-ss` 定位可能差 1 帧，死磕同一个帧号会假摔到 14dB。

用法：
  PROJ_ROOT=<工程根> python verify_mp4.py out_silent.mp4
环境变量：PROJ_ROOT / VIDEO_W / VIDEO_H / VIDEO_FPS / FFMPEG
"""
import io
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = (os.environ.get('PROJ_ROOT') or os.getcwd()).replace('\\', '/')
FFMPEG = os.environ.get('FFMPEG') or (
    r'C:\Users\%s\AppData\Local\Microsoft\WinGet\Packages'
    r'\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe'
    r'\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe' % os.environ.get('USERNAME', ''))
FFPROBE = FFMPEG.replace('ffmpeg.exe', 'ffprobe.exe')

FPS = float(os.environ.get('VIDEO_FPS', 30))
W = int(os.environ.get('VIDEO_W', 1080))
H = int(os.environ.get('VIDEO_H', 1920))

VID = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'out_silent.mp4')
OUT = os.path.join(ROOT, 'verify')
FRAMES = os.path.join(ROOT, 'frames')
os.makedirs(OUT, exist_ok=True)

# ---------- 1. 从 index.html 取镜头边界 + 字幕表 ----------
html = io.open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
shots = [(float(a), float(b)) for a, b in
         re.findall(r'data-st="([\d.]+)" data-et="([\d.]+)"', html)]
if not shots:   # 兼容 add(s,e,...) 风格的分镜源码
    shots = [(float(a), float(b)) for a, b in
             re.findall(r'add\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,', html)]
m = re.search(r'(?:const|var|let)\s+SUBS\s*=\s*(\[\[.*?\]\]);', html, re.S)
subs = json.loads(m.group(1)) if m else []
print('镜头 %d 个 / 字幕 %d 条' % (len(shots), len(subs)))

# 每个镜头取「落在本镜内、且离镜头中点最近」的那条字幕的中点
T = []
for st, et in shots:
    mid = (st + et) / 2
    cand = [s for s in subs if s[0] >= st and s[1] <= et] or \
           [s for s in subs if st <= (s[0] + s[1]) / 2 <= et]
    best = min(cand, key=lambda s: abs((s[0] + s[1]) / 2 - mid)) if cand else None
    T.append(round((best[0] + best[1]) / 2, 3) if best else round(mid, 3))
print('取样时刻:', T)

# ---------- 2. 反抽帧 ----------
# 先卡住「帧序列画幅」这一关：只要有一帧尺寸不对，ffmpeg 编码会按**首帧尺寸**
# 把全片静默缩放成错误画幅 —— 片子看起来正常，规格却是错的。
# （真实翻车：局部重渲脚本的默认画幅是竖版，写进横版序列后整片变 1080×1920，
#   而且 PSNR 从 41 掉到 33 才发现。所以这个守卫必须放在比对之前。）
bad_size = []
for fn in sorted(os.listdir(FRAMES)):
    if not fn.startswith('f-') or not fn.endswith('.png'):
        continue
    with Image.open(os.path.join(FRAMES, fn)) as im:
        if im.size != (W, H):
            bad_size.append((fn, im.size))
if bad_size:
    print('!! 帧序列画幅不一致：%d 帧不是 %dx%d（如 %s %s）'
          % (len(bad_size), W, H, bad_size[0][0], bad_size[0][1]))
    print('   先修帧再比对，否则 PSNR 与规格全部不可信。')
    sys.exit(4)
print('帧序列画幅一致：全部 %dx%d' % (W, H))

cells = []
for i, t in enumerate(T, 1):
    p = os.path.join(OUT, 'enc_%02d_%.2f.png' % (i, t))
    subprocess.run([FFMPEG, '-y', '-ss', str(t), '-i', VID, '-frames:v', '1',
                    '-vf', 'scale=%d:%d' % (W, H), p], capture_output=True, check=True)
    cells.append((i, t, p))
print('已反抽 %d 帧 -> verify/' % len(cells))


# ---------- 3. PSNR：±2 帧对齐取最大 ----------
def psnr(a, b):
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', a, '-i', b,
                        '-lavfi', 'psnr', '-f', 'null', '-'],
                       capture_output=True, text=True)
    mm = re.search(r'average:([\d.]+|inf)', r.stderr)
    if not mm:
        return -1.0
    return float('inf') if mm.group(1) == 'inf' else float(mm.group(1))


print('\n%-4s %-8s %-7s %s' % ('#', 't', 'PSNR', '对齐帧号'))
print('-' * 46)
worst = (999.0, None)
for i, t, p in cells:
    base = int(round(t * FPS))
    best, bestj = -1.0, None
    for j in range(base - 2, base + 3):
        f = os.path.join(FRAMES, 'f-%05d.png' % j)
        if not os.path.exists(f):
            continue
        v = psnr(p, f)
        if v > best:
            best, bestj = v, j
    print('%s%-2d  %-8.2f %-7.2f f-%05d' % ('ok ' if best >= 30 else '!! ', i, t, best,
                                            bestj if bestj is not None else -1))
    if best < worst[0]:
        worst = (best, i)
print('\n最低 PSNR %.2f dB（第 %s 镜）' % worst)

# ---------- 4. 接触表 ----------
CW = W // 2
CH = H // 2
GAP = 8
files = [c[2] for c in cells]
for k in range(0, len(files), 4):
    chunk = files[k:k + 4]
    sheet = Image.new('RGB', (CW * 2 + GAP, (CH + 20) * 2 + GAP), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    for mi, f in enumerate(chunk):
        im = Image.open(f).convert('RGB').resize((CW, CH), Image.LANCZOS)
        x = (mi % 2) * (CW + GAP)
        y = (mi // 2) * (CH + 20 + GAP)
        d.text((x + 6, y + 4), 't=%s' % T[k + mi], fill=(255, 220, 140))
        sheet.paste(im, (x, y + 20))
    name = 'sheet_%02d.png' % (k // 4 + 1)
    sheet.save(os.path.join(OUT, name))
    print('  ->', name)

# ---------- 5. 规格自检 ----------
info = subprocess.run([FFPROBE, '-v', 'error', '-select_streams', 'v:0',
                       '-show_entries', 'stream=width,height,r_frame_rate,nb_frames',
                       '-show_entries', 'format=duration', '-of', 'default=nw=1', VID],
                      capture_output=True, text=True).stdout
print('\n成片规格:\n%s' % info.strip())
