# -*- coding: utf-8 -*-
"""从「编码后的成片」反抽帧验收：画幅守卫 + PSNR 保真 + 接触表 + 规格自检。

为什么要从成片反抽帧：只看渲染前的静帧等于没验收 ——
H.264 的色度下采样 / 量化可能吃掉渐变细节或放大噪点。

三个必须做对的点（都是实测踩过的）：
  1. 帧序列画幅守卫放在最前面：只要有一帧尺寸不对，ffmpeg 会按**首帧尺寸**把全片
     静默缩放成错误画幅，画面看着正常、规格却是错的。
  2. 帧号对齐：render.cjs 从 f-00000.png 开始（i 从 0），所以
     idx = round(t*fps)，**不要 +1**。image2 demuxer 默认 start_number=0。
  3. PSNR 必须允许 ±2 帧对齐取最大：ffmpeg 的 -ss 会差 1 帧，死磕同一帧号
     会从 41dB 假摔到 14dB。

用法：
  PROJ_ROOT=<工程根> FFMPEG=<ffmpeg路径> python verify_mp4.py [成片.mp4]
退出码：0 通过 / 1 PSNR 偏低 / 2 抽帧失败 / 4 帧序列画幅不一致
"""
import io
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = (os.environ.get('PROJ_ROOT') or os.getcwd()).replace('\\', '/')


def _find_ffmpeg():
    # 接受 FFMPEG 或 FFMPEG_PATH —— 两个名字都常见。
    # 踩过：只认 FFMPEG 时，设了 FFMPEG_PATH 的环境会走到 PATH 兜底，
    # 而 Windows 的 WinGet 会在 Links/ 下放一个**非 exe 的 shim**，
    # 执行时报 `WinError 193 %1 不是有效的 Win32 应用程序`，看不出是环境变量名的问题。
    for k in ('FFMPEG', 'FFMPEG_PATH'):
        v = os.environ.get(k)
        if v and os.path.exists(v):
            return v
    p = shutil_which('ffmpeg')
    # 兜底的候选也要**验真**：跑一次 -version，失败就继续找
    if p:
        try:
            subprocess.run([p, '-version'], capture_output=True, check=True, timeout=10)
            return p
        except Exception:
            pass
    # Windows WinGet 兜底（直接找包目录里的真 exe，绕开 Links shim）
    base = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WinGet', 'Packages')
    if os.path.isdir(base):
        for d in os.listdir(base):
            if 'FFmpeg' not in d:
                continue
            for v in os.listdir(os.path.join(base, d)):
                for exe in ('ffmpeg.exe', 'ffmpeg'):
                    p = os.path.join(base, d, v, 'bin', exe)
                    if os.path.exists(p):
                        return p
    raise SystemExit('找不到可执行的 ffmpeg，请设 FFMPEG 或 FFMPEG_PATH')


def shutil_which(name):
    for d in os.environ.get('PATH', '').split(os.pathsep):
        p = os.path.join(d, name + ('.exe' if os.name == 'nt' else ''))
        if os.path.exists(p):
            return p
    return None


FFMPEG = _find_ffmpeg()
# ffprobe 与 ffmpeg 同目录。**必须用 splitext + 同目录替换**：
# 直接对整条路径做 .replace('ffmpeg','ffprobe') 会把目录名
# （ffmpeg-9.0.2-full_build）一起改掉，得到一个不存在的路径 —— 实测踩过。
_FFDIR = os.path.dirname(FFMPEG)
_FFEXE = 'ffprobe.exe' if os.name == 'nt' else 'ffprobe'
FFPROBE = os.path.join(_FFDIR, _FFEXE)
if not os.path.exists(FFPROBE):
    raise SystemExit('ffprobe 不在 %s，请设 FFPROBE 环境变量' % _FFDIR)
FPS = float(os.environ.get('VIDEO_FPS', 30))
W = int(os.environ.get('VIDEO_W', 1080))
H = int(os.environ.get('VIDEO_H', 1920))

VID = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'out_silent.mp4')
OUT = os.path.join(ROOT, 'verify')
FRAMES = os.path.join(ROOT, 'frames')
os.makedirs(OUT, exist_ok=True)

# ---------- 0. 帧序列画幅守卫（必须在 PSNR 之前）----------
if not os.path.isdir(FRAMES):
    print('帧目录不存在:', FRAMES); sys.exit(2)
files = sorted(f for f in os.listdir(FRAMES) if f.startswith('f-') and f.endswith('.png'))
if not files:
    print('帧序列为空'); sys.exit(2)
bad = []
for fn in files:
    with Image.open(os.path.join(FRAMES, fn)) as im:
        if im.size != (W, H):
            bad.append((fn, im.size))
if bad:
    print('!! 帧序列画幅不一致：%d/%d 帧不是 %dx%d（如 %s %s）'
          % (len(bad), len(files), W, H, bad[0][0], bad[0][1]))
    print('   先修帧再比对，否则 PSNR 与规格全部不可信。')
    sys.exit(4)
print('帧序列画幅一致：全部 %d 帧 %dx%d' % (len(files), W, H))

# ---------- 1. 取镜头边界 + 字幕表 ----------
# 优先从页面里直接拿 window.__shots（与渲染走同一份数据，最可靠）；
# 拿不到才回退到正则。正则只匹配字面量数字的 add(S0, S1, ...)，
# **匹配不到 SCHOOLS.forEach 里的 add(S0, S1, ...)** —— 实测 13 个镜头只解析出 8 个。
html = io.open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
# ⚠ 不要用 json.loads(片段.replace("'", '"')) 解析字幕表 —— 两个必崩点：
#   ① 数组尾逗号（`[...],\n];`，非常常见的写法）→ JSONDecodeError，
#      整个验收脚本直接抛栈退出，任何尾逗号的工程都用不了；
#   ② 文案里出现直引号时 replace("'", '"') 会把字符串截断。
# 改成逐条正则取三元组，对两种引号、尾逗号、正文里的引号都免疫。
m = re.search(r'const SUBS\s*=\s*(\[.*?\n\]);', html, re.S)
subs = []
if m:
    for sm in re.finditer(r'\[\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*(["\'])(.*?)\3\s*\]', m.group(1), re.S):
        subs.append([float(sm.group(1)), float(sm.group(2)), sm.group(4)])

shots = []
shot_src = ''
try:
    import subprocess as _sp
    node = os.environ.get('NODE_BIN', '')
    if not node:
        # 从 puppeteer-core 已安装的位置反推 node（**不写死版本号** —— 运行时一升级就失效）。
        # ⚠ 基目录是**用户主目录**下的 .workbuddy，不是 %LOCALAPPDATA%（那是 AppData\Local）。
        #   这两处都会得到 node='' → subprocess 拿空字符串当可执行文件 → WinError 87，
        #   然后静默回退正则：验收范围从 15 镜缩到 10 镜，**而且照样报 ok**。（两种都踩过）
        import glob as _glob
        for c in sorted(_glob.glob(os.path.join(
                os.path.expanduser('~'), '.workbuddy', 'binaries', 'node',
                'versions', '*', 'node.exe'))):
            if os.path.exists(c):
                node = c
                break
    if not node:
        raise RuntimeError('找不到 node —— 请设环境变量 NODE_BIN 指过去')
    # ⚠ 用 `node -e` 传内联脚本要穿过 Python 转义 + shell 转义两层，
    #   实测 `\\\\/g` 到 node 手里会变成 `/\/g` → 语法错误 → node 退出但 stdout 为空
    #   → 不抛异常、静默拿到 0 个镜头。改成写临时 .cjs 文件再执行，绕开整类转义问题。
    import tempfile
    jsfile = os.path.join(tempfile.gettempdir(), 'html_timeline_dump_shots.cjs')
    with io.open(jsfile, 'w', encoding='utf-8') as f:
        f.write(
            "const p=require('puppeteer-core'),path=require('path');\n"
            "(async()=>{const b=await p.launch({executablePath:process.env.CHROME_PATH,headless:'new',\n"
            "  userDataDir:path.join(require('os').tmpdir(),'html-timeline-dump-profile'),\n"
            # ⚠ 用独立 profile 目录名：与 render.cjs 的 'html-timeline-chrome-profile' 共用的话，
            #   渲染期间跑验收会直接报 "The browser is already running for ..."。
            "  args:['--no-sandbox','--allow-file-access-from-files','--disable-gpu']});\n"
            "const g=await b.newPage();\n"
            "const url='file:///'+path.join(process.env.PROJ_ROOT||process.cwd(),'index.html').split(path.sep).join('/');\n"
            "await g.goto(url,{waitUntil:'load'});\n"
            "await g.waitForFunction('typeof window.__render === \"function\"');\n"
            # 字段兼容：模板用 s.s/s.e，实测有工程用 s.st/s.et。只认一种会静默拿到 null。
            "const d=await g.evaluate(()=>window.__shots.map(s=>[s.st!==undefined?s.st:s.s,s.et!==undefined?s.et:s.e]));\n"
            "console.log(JSON.stringify(d));await b.close();\n"
            "})().catch(e=>{console.error('DUMP_ERR '+e.message);process.exit(9);});\n")
    # Chrome 路径回退链：本机 Chrome **不在** LOCALAPPDATA（那里是 AppData\\Local），
    # 写死那一个路径会让 launch 直接失败。
    chrome = os.environ.get('CHROME_PATH') or ''
    if not chrome or not os.path.exists(chrome):
        for c in [os.path.join(os.environ.get('PROGRAMFILES', 'C:/Program Files'),
                               'Google', 'Chrome', 'Application', 'chrome.exe'),
                  os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)'),
                               'Google', 'Chrome', 'Application', 'chrome.exe'),
                  os.path.join(os.environ.get('LOCALAPPDATA', ''),
                               'Google', 'Chrome', 'Application', 'chrome.exe')]:
            if os.path.exists(c):
                chrome = c
                break
    r = _sp.run([node, jsfile], capture_output=True, text=True,
                env=dict(os.environ, PROJ_ROOT=ROOT, CHROME_PATH=chrome))
    line = [l for l in r.stdout.strip().split('\n') if l.startswith('[')]
    if line:
        shots = [(float(a), float(b)) for a, b in json.loads(line[-1])]
        shot_src = 'window.__shots（页面实测，与渲染同一份数据）'
    else:
        # 「node 跑了但没输出」以前是完全静默的（不抛异常 → 不进 except → 0 镜头还报 ok）。
        # 必须出声，并把 node 自己的 stderr 打出来。
        print('  ⚠⚠ 取 __shots：node 没有输出镜头表（exit=%s）' % r.returncode)
        if r.stderr.strip():
            print('     node stderr: ' + r.stderr.strip().split('\n')[-1][:200])
        print('     Chrome 路径用的是: %s' % (chrome or '(空)'))
except Exception as e:
    # 降级必须**出声**。正则只匹配字面量数字的 add(S0,S1,...)，
    # 匹配不到 SCHOOLS.forEach 里生成的镜头 —— 实测 15 镜只解析出 10 个。
    print('  ⚠⚠ 取 __shots 失败：%s' % e)
    print('      → 回退正则：镜头覆盖**会不全**（正则匹配不到 forEach 里生成的镜头）')

if not shots:
    shots = [(float(a), float(b)) for a, b in
             re.findall(r'add\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,', html)]
    shot_src = '正则 add()（可能漏掉 forEach 里的镜头）'

# ⚠ 硬守卫：镜头表为空 = 一个采样点都没有 = 什么都没验。
#   没有这道守卫时脚本会吐出「最低 PSNR 999.00 dB」并 exit 0 —— 假绿灯比报错危险得多。
if not shots:
    print('✗ 镜头表为空（__shots 与正则都没取到）→ 没有任何采样点，无法验收，已中止。')
    print('  别忽略这条：继续跑会输出 PSNR 999 dB 并报通过。')
    print('  检查 window.__shots 是否存在、字段名是否为 st/et（或 s/e）。')
    sys.exit(4)

print('镜头 %d 个（来源：%s） / 字幕 %d 条' % (len(shots), shot_src, len(subs)))
if not subs:
    print('⚠ 没解析到字幕表 → 取样点会退回「镜头中点」。')
    print('  按项目约定应取字幕中点（字幕中点才能保证那一帧有完整文字），')
    print('  若 index.html 的 SUBS 写法与正则不符，请改这里的解析而不是忽略这条警告。')

# 每个镜头取「落在本镜内、离中点最近」的那条字幕的中点
T = []
for st, et in shots:
    mid = (st + et) / 2
    cand = [s for s in subs if s[0] >= st and s[1] <= et] or \
           [s for s in subs if st <= (s[0] + s[1]) / 2 <= et]
    best = min(cand, key=lambda s: abs((s[0] + s[1]) / 2 - mid)) if cand else None
    T.append(round((best[0] + best[1]) / 2, 3) if best else round(mid, 3))

# ---------- 2. 反抽帧 ----------
cells = []
for i, t in enumerate(T, 1):
    p = os.path.join(OUT, 'enc_%02d_%.2f.png' % (i, t))
    r = subprocess.run([FFMPEG, '-y', '-ss', str(t), '-i', VID, '-frames:v', '1', p],
                       capture_output=True)
    if not os.path.exists(p):
        print('抽帧失败 t=%s: %s' % (t, r.stderr.decode('utf-8', 'ignore')[-200:]))
        sys.exit(2)
    cells.append((i, t, p))
print('已反抽 %d 帧 -> verify/' % len(cells))

# ---------- 3. PSNR：±2 帧对齐取最大 ----------
def psnr(a, b):
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', a, '-i', b, '-lavfi', 'psnr', '-f', 'null', '-'],
                       capture_output=True, text=True)
    mm = re.search(r'average:([\d.]+|inf)', r.stderr)
    if not mm:
        return -1.0
    return float('inf') if mm.group(1) == 'inf' else float(mm.group(1))

print('\n%-4s %-8s %-9s %s' % ('#', 't', 'PSNR', '对齐帧号'))
print('-' * 40)
worst = (999.0, None)
for i, t, p in cells:
    base = int(round(t * FPS))          # 注意：不要 +1
    best, bestj = -1.0, None
    for j in range(base - 2, base + 3):
        f = os.path.join(FRAMES, 'f-%05d.png' % j)
        if not os.path.exists(f):
            continue
        v = psnr(p, f)
        if v > best:
            best, bestj = v, j
    print('%s%-2d  %-8.2f %-9s f-%05d' % ('ok ' if best >= 30 else '!! ', i, t,
                                          '%.2f' % best if best < 999 else 'inf',
                                          bestj if bestj is not None else -1))
    if best < worst[0]:
        worst = (best, i)
print('\n最低 PSNR %.2f dB（第 %s 镜）' % worst)

# ---------- 4. 接触表（带标注，用户可自行核对）----------
CW, CH, GAP, LAB = W // 2, H // 2, 8, 20
for k in range(0, len(cells), 4):
    chunk = cells[k:k + 4]
    rows = (len(chunk) + 1) // 2
    sheet = Image.new('RGB', (CW * 2 + GAP, (CH + LAB) * rows + GAP), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    for mi, (idx, t, f) in enumerate(chunk):
        im = Image.open(f).convert('RGB').resize((CW, CH), Image.LANCZOS)
        x = (mi % 2) * (CW + GAP)
        y = (mi // 2) * (CH + LAB + GAP)
        d.text((x + 6, y + 4), 'shot %d  t=%s' % (idx, t), fill=(255, 220, 140))
        sheet.paste(im, (x, y + LAB))
    name = 'sheet_%02d.png' % (k // 4 + 1)
    sheet.save(os.path.join(OUT, name))
    print('  ->', name)

# ---------- 5. 规格自检 ----------
info = subprocess.run([FFPROBE, '-v', 'error', '-select_streams', 'v:0',
                       '-show_entries', 'stream=width,height,r_frame_rate,nb_frames',
                       '-show_entries', 'format=duration', '-of', 'default=nw=1', VID],
                      capture_output=True, text=True).stdout
print('\n成片规格:\n%s' % info.strip())
sys.exit(0 if worst[0] >= 30 else 1)
