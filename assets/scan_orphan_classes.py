# -*- coding: utf-8 -*-
"""
孤儿 class 扫描 —— html-timeline-video 技能配套工具
────────────────────────────────────────────────────────────────────
用途：**换 CSS 底座之后必跑**。

换底座（把旧一套 class 全部重新定义成新外观）最容易出的事故不是「改错了」，
而是「漏了」：某个类在 HTML 里还在用，但 CSS 里已经没有它的定义了。
这类元素会静默退回浏览器默认样式（16px / 继承色），不报任何错，
在 1080×1920 的竖屏上小到几乎看不见 —— 往往一直到用户截图指出才发现。

真实事故：`.delta`（增量徽章 +20 / +18 / 比去年 +6,000）在 v4→v5 换底座时
整个丢了定义，3 处调用一直吃默认 16px，一路带到 v6 才被用户发现。
同批漏掉的还有 `#rail` 的底条。

用法：
  python scan_orphan_classes.py                    # 扫当前目录 index.html
  python scan_orphan_classes.py path/to/index.html
"""
import io, os, re, sys

# 这些类名在 HTML 里出现但不需要 CSS 定义（JS 钩子 / SVG 元素 / 结构性容器）
WHITELIST = {
    'rc',      # SVG circle 的 JS 选择器钩子
    'ttl',     # 章节卡标题的语义标记（样式走 .gold）
    'stage', 'wrap', 'shot',
}

def resolve_target():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if args:
        return os.path.abspath(args[0])
    cwd = os.path.abspath(os.path.join(os.getcwd(), 'index.html'))
    if os.path.exists(cwd):
        return cwd
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')


def main():
    p = resolve_target()
    if not os.path.exists(p):
        print('找不到文件：%s' % p)
        sys.exit(1)
    with io.open(p, 'r', encoding='utf-8') as f:
        src = f.read()

    # 1) 收集 HTML 里用到的所有 class
    used = set()
    for m in re.finditer(r'class="([^"]*)"', src):
        for c in m.group(1).split():
            used.add(c)

    # 2) 收集 CSS 里定义过的所有 class（只看 <script> 之前的部分）
    cut = src.index('<script>') if '<script>' in src else len(src)
    css = src[:cut]
    defined = set(re.findall(r'\.([A-Za-z_][\w-]*)', css))

    # 3) 取差集
    orphans = sorted(c for c in used if c not in defined and c not in WHITELIST)

    print('文件：%s' % p)
    print('HTML 用到的 class 数：%d' % len(used))
    print('CSS  定义过的 class 数：%d' % len(defined))
    print()
    if not orphans:
        print('✅ 没有孤儿 class —— 所有在用的类都有样式定义。')
    else:
        print('⚠️  发现 %d 个「HTML 在用、但 CSS 无定义」的类：' % len(orphans))
        for c in orphans:
            # 找出它出现的上下文，方便判断是不是漏样式
            hits = re.findall(r'.{0,70}class="[^"]*\b' + re.escape(c) + r'\b[^"]*".{0,40}', src)
            print('\n  .%s   （出现 %d 处）' % (c, len(hits)))
            for h in hits[:2]:
                print('     … %s' % h.replace('\n', ' ').strip()[:135])
        print('\n处置：这些元素会退回浏览器默认样式（通常 16px + 继承色），')
        print('      在 1080×1920 竖屏上会小到看不见。逐个补 CSS 定义，')
        print('      或者确认它只是 JS 钩子/语义标记后加进 WHITELIST。')
        print('      （改完务必用 probe_styles.cjs 复检计算样式）')


if __name__ == '__main__':
    main()
