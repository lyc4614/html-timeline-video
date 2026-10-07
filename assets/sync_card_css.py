# -*- coding: utf-8 -*-
"""把「样式单一真源」内联进正片 index.html。

为什么需要这一步：
  实验台（card_lab.html）用 <link> 引样式，正片为了零请求把样式**内联**进 <style>。
  两处各存一份就会漂移 —— 所以约定：**只改 card-system.css，再跑本脚本内联**。
  实验台与正片因此永远同源。

为什么要断言：
  内联是「整段替换」，锚点一失配就可能把不该动的东西切掉，而且**不一定报错**。
  所以替换前后都做结构校验，任何一项不过就**一个字都不写盘**。

用法：
  python sync_card_css.py            # 就地内联
  python sync_card_css.py --check    # 只校验，不写盘

改造到自己项目时：改 CSS_FILE / PAGE / 标记，以及 PROJECT_CHECKS（你的业务锚点）。
"""
import io, re, sys

CSS_FILE = 'card-system.css'
PAGE = 'index.html'
# 正片里包裹样式的注释标记：从 START 所在注释块的起头，到 END 标记为止，整段替换
START_HINT = '卡片 / 边框系统'          # START 标记所在注释块里的一小段特征文字
END = '/* ============ 常驻结构层'     # 卡片层结束、下一段开始的位置

# 项目自定义校验：锚点失配 = 切错了地方。改成你自己的业务锚点。
PROJECT_CHECKS = [
    ('卡片层只剩一份 .card{', lambda h: h.count('.card{border-radius:') == 1),
    ('.rrow 只剩一份定义', lambda h: len(re.findall(r'^\.rrow\{', h, re.M)) == 1),
    ('纹样/主题变量已内联', lambda h: '--orn-div:url("data:image/svg+xml' in h),
    ('页面契约四项在', lambda h: all(x in h for x in
        ['window.__render', 'window.__duration', 'window.__fps', 'window.__shots'])),
    ('常驻层完整', lambda h: all(x in h for x in
        ['#pbar{', '#rail{', '#sub{', '#toplogo{', '#brand{'])),
]

PRE_CHECKS = [
    ('纹样已生成', lambda c: '--orn-div:url("data:image/svg+xml' in c),
    ('无占位符残留', lambda c: '__GRAIN__' not in c and '__DIV__' not in c),
    ('标记区存在', lambda c: '<<ORN>>' in c and '<<ORN-END>>' in c),
]

css = io.open(CSS_FILE, encoding='utf-8').read()
ok = True
print('— 样式源校验（%s）—' % CSS_FILE)
for name, fn in PRE_CHECKS:
    g = fn(css)
    print(('  ✓ ' if g else '  ✗ ') + name)
    ok = ok and g
if not ok:
    print('先跑 make_ornament.py 生成纹样'); sys.exit(1)

h = io.open(PAGE, encoding='utf-8').read()
k = h.index(START_HINT)
i0 = h.rindex('/* =', 0, k)      # 注释块的起点
i1 = h.index(END)                # 注释块的终点
old = i1 - i0
assert old > 1000, '定位到的旧样式层太短(%d) —— 锚点大概失效，中止' % old
new_h = h[:i0] + css.rstrip() + '\n\n' + h[i1:]

print('— 替换后结构校验（%s）—' % PAGE)
for name, fn in PROJECT_CHECKS:
    g = fn(new_h)
    print(('  ✓ ' if g else '  ✗ ') + name)
    ok = ok and g
print('  · 旧样式层 %d 字符 → 新 %d 字符' % (old, len(css)))
if not ok:
    print('中止，未写盘'); sys.exit(1)

if '--check' in sys.argv:
    print('\n✓ 校验通过（--check，未写盘）'); sys.exit(0)
io.open(PAGE, 'w', encoding='utf-8', newline='\n').write(new_h)
print('\n✓ 已内联进 %s' % PAGE)
