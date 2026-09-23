# -*- coding: utf-8 -*-
"""
深色底「文字对比度提亮」批处理器  —— html-timeline-video 技能配套工具
────────────────────────────────────────────────────────────────────
用途：成片已做完，用户反馈「很多文字颜色太浅、和背景区分度不够」时，
      一次性把全片所有过淡的文字色按层级上调，而不是逐处手改。

核心原则（踩过的）：
  · 对比度的正解是「提文字 + 加落影」，不是「压背景」。
    给内容层加 radial 压暗垫层会连网格骨架一起闷掉（网格 P50 亮度只有 3-4）。
  · 按「同一透明度值」批量处理，比拼字符串可靠得多。
    本轮 .62 一个值就命中 26 处。
  · 必须写成脚本 + 落盘前校验（锚点存在性 + 处理后计数为 0），
    并且先在原文件上 cp 一份备份 —— 改错了能立刻回滚重跑。

用法（在工程目录下跑，脚本自己找 index.html；也可传路径）：
  python bump_text_contrast.py --scan            # 列出所有 rgba 文字色的分布
  python bump_text_contrast.py --apply           # 按下面的映射表替换
  python bump_text_contrast.py --apply path/to/foo.html
"""
import io, os, re, sys, collections

# 显式传路径 > 当前工作目录的 index.html > 脚本同级目录的 index.html
def _resolve_target():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if args:
        return os.path.abspath(args[0])
    cwd_target = os.path.abspath(os.path.join(os.getcwd(), 'index.html'))
    if os.path.exists(cwd_target):
        return cwd_target
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')

P = _resolve_target()
BACKUP = os.path.join(os.path.dirname(P), 'index_precontrast.html')

# ─────────────────────────────────────────────────────────────
# 层级映射：左 = 原始值，右 = 提亮后
# 档位依据：正文/主标题 ≥ .94；次级文字（小标题/卡片名/轴标签）≥ .88；
#           品牌型小字（署名/来源）≈ .70；"被否定/退居背景"的文字 ≥ .76
# ─────────────────────────────────────────────────────────────
MAP = [
    # 次级文字：出现频次最高的一档，一次命中几十处
    ('rgba(226,216,190,.62)', 'rgba(228,220,198,.90)'),
    # 签名/来源行
    ('rgba(226,203,138,.42)', 'rgba(226,203,138,.72)'),
    ('rgba(214,206,186,.45)', 'rgba(214,206,186,.72)'),
    # 章节轨：未激活章号几乎隐形
    ('rgba(226,203,138,.24)', 'rgba(226,203,138,.52)'),
    # 被划掉的旧认知：可以暗，但不能糊
    ('rgba(214,206,186,.55)', 'rgba(214,206,186,.80)'),
    # 有色副标
    ('rgba(222,139,137,.62)', 'rgba(228,158,156,.90)'),
    ('rgba(147,214,180,.62)', 'rgba(163,224,196,.90)'),
]

# 结构性元素（背景条 / 描边 / SVG stroke）：不只提 alpha，还要换色相
# 未激活的白色底条 rgba(255,255,255,.09) 在白底下几乎不可见 → 换成金线色
STRUCT = [
    ('background:rgba(255,255,255,.09)', 'background:rgba(226,203,138,.20)'),
    ('stroke="rgba(255,255,255,.105)"', 'stroke="rgba(226,203,138,.22)"'),
]

# 需要补「落影」的类：单层 drop-shadow 挡不住穿过文字的网格线
SHADOW_PATCHES = [
    # (锚点片段, 替换片段)，按需自行增删
]

# 语义色整体提亮
COLOR_SWAPS = [
    ('.red{color:#DE8B89;}', '.red{color:#EE9A98;}'),
    ('.grn{color:#93D6B4;}', '.grn{color:#A3E0BE;}'),
]

# 字幕条：必须一眼读完的元素，不能只靠半透明底
SUB_PATCH = [
    ('background:rgba(0,0,0,.86)', 'background:rgba(0,0,0,.93)'),
    ('border:1px solid rgba(214,190,120,.30)', 'border:1px solid rgba(214,190,120,.42)'),
]


def scan(src):
    print('--- 所有 rgba 文字色分布（按出现次数）---')
    c = collections.Counter(re.findall(r'rgba\(\d+,\d+,\d+,\.[0-9]+\)', src))
    for k, v in c.most_common():
        # 计算在黑底上的视觉亮度，方便判断该不该提
        m = re.match(r'rgba\((\d+),(\d+),(\d+),(\.[0-9]+)\)', k)
        r, g, b, a = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
        lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) * a
        flag = '  <== 偏淡' if lum < 120 else ''
        print('  %-28s x%-3d  有效亮度 %6.1f%s' % (k, v, lum, flag))
    print()


def apply(src):
    n_total = 0
    for o, n in MAP + STRUCT + COLOR_SWAPS + SUB_PATCH:
        c = src.count(o)
        if c == 0:
            print('  [未命中] %s' % o)
            continue
        src = src.replace(o, n)
        n_total += c
        print('  %-28s -> %-28s : %d 处' % (o, n, c))
    for o, n in SHADOW_PATCHES:
        c = src.count(o)
        if c:
            src = src.replace(o, n)
            print('  [落影] %-24s : %d 处' % (o[:24], c))
    return src, n_total


def main():
    with io.open(P, 'r', encoding='utf-8') as f:
        src = f.read()
    orig = src

    if '--scan' in sys.argv:
        scan(src)
        return

    if '--apply' not in sys.argv:
        print(__doc__)
        print('请指定 --scan 或 --apply')
        return

    # 先备份
    if not os.path.exists(BACKUP):
        with io.open(BACKUP, 'w', encoding='utf-8') as f:
            f.write(orig)
        print('已备份 -> %s\n' % BACKUP)

    print('--- 替换明细 ---')
    src, n_total = apply(src)

    print('\n--- 落盘前校验 ---')
    checks = [
        ('未残留旧淡色值', all(src.count(o) == 0 for o, _ in MAP)),
        ('总替换数 > 0', n_total > 0),
    ] + [('语义色已换: ' + o[:16], n in src) for o, n in COLOR_SWAPS]
    ok = True
    for name, cond in checks:
        print(('  [OK]   ' if cond else '  [FAIL] ') + name)
        ok = ok and cond

    if not ok:
        print('\n校验未通过，已中止落盘（原文件未改动）')
        sys.exit(1)

    with io.open(P, 'w', encoding='utf-8') as f:
        f.write(src)
    print('\n已写入 %s（共替换 %d 处，%d -> %d 字符）' % (P, n_total, len(orig), len(src)))


if __name__ == '__main__':
    main()
