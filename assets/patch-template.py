# -*- coding: utf-8 -*-
"""
批量改造补丁脚本的**骨架模板** —— 复制这个文件改内容，不要直接跑。

为什么必须走脚本而不是手工改 / `sed` 一把梭：
  · 手工改漏一处不会报错，要到成片里才发现（用户截图打脸）；
  · 每处替换都断言「期望出现 N 次，实际 N 次」，锚点失配立刻中止、一个字都不写盘；
  · 落盘前跑一遍完整性校验（结构锚点、镜头数、元素计数），不过就 `sys.exit(1)`。

下面的三段替换是**示例**（真正做什么随你的项目变），保留它们的价值在于
示范三种典型改造：
  1. 删除一个元素 —— 连同调用点一起清理，别留「看起来还在生效」的死参数；
  2. 全站统一一处编号 —— 同一套视觉语言分散在多个组件里，改之前先 grep 出所有命中点；
  3. 换元素的配色归属 —— 形态跟参考片、颜色跟本片体系（见 SKILL.md）。

顺带提醒两条踩过的坑：
  · 改 CSS 用**整块精确字符串替换**，不要写「聪明」的通用正则 ——
    `!important` 前的对齐空格、小数位后的空格都会让 `\\s*` 失配；
  · `div` 开闭计数在含 JS 模板字符串的页面里天然不平衡（会有裸 `</div>`），
    所以这类校验要**和备份文件比较**，不能断言 `== 0`。
"""
import io, sys, os, re

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
html = io.open(SRC, encoding='utf-8').read()
orig = html
log = []


def sub(old, new, tag, count=1):
    """精确替换，要求出现次数正好 count 次，否则报错不写盘。"""
    global html
    n = html.count(old)
    assert n == count, f'[{tag}] 期望匹配 {count} 处，实际 {n} 处 —— 已中止，不写盘'
    html = html.replace(old, new)
    log.append(f'  ok  {tag}')


# ---------- 示例 1) 删除一个元素，并清理失效的调用参数 ----------
# 注意：删元素时连调用点一起改，否则参数留着，下一个人会以为它还在生效。
sub(
    "  if(ct){node.w.appendChild(el('div','chapct',ct));}\n",
    "  /* 该元素已按需求移除（callsite 仍传 ct，这里直接忽略） */\n",
    '移除元素 .chapct',
)

calls_before = len(re.findall(r",'[^']*','\d+:\d+\.\d+ [–-] \d+:\d+\.\d+'\)", html))
html = re.sub(r",'[^']*','\d+:\d+\.\d+ [–-] \d+:\d+\.\d+'\)", ")", html)
log.append(f'  ok  清理 {calls_before} 处已失效的实参')
assert calls_before >= 15, f'只找到 {calls_before} 处，疑似正则失效'

# ---------- 示例 2) 全站统一一处编号 ----------
NUM = ['01', '02', '03', '04', '05']

rail_old = (
    '  <div class="ri"><div class="rn">壹</div><div class="rb"></div></div>\n'
    '  <div class="ri"><div class="rn">贰</div><div class="rb"></div></div>\n'
    '  <div class="ri"><div class="rn">叁</div><div class="rb"></div></div>\n'
    '  <div class="ri"><div class="rn">肆</div><div class="rb"></div></div>\n'
    '  <div class="ri"><div class="rn">伍</div><div class="rb"></div></div>'
)
rail_new = '\n'.join(
    f'  <div class="ri"><div class="rn">{n}</div><div class="rb"></div></div>' for n in NUM
)
sub(rail_old, rail_new, '底部章节轨 壹贰叁肆伍 → 01–05')

# 同一编号的另一处（封面五小卡）——这就是「改一处要全局扫」的实例
sub(
    "${['壹','贰','叁','肆','伍'].map(x=>`<div class=\"card5\" style=\"width:104px;height:104px;"
    "display:flex;align-items:center;justify-content:center;opacity:0;\">"
    "<span class=\"gold\" style=\"font-size:44px;font-weight:900;\">${x}</span></div>`).join('')}",
    "${['01','02','03','04','05'].map(x=>`<div class=\"card5\" style=\"width:104px;height:104px;"
    "display:flex;align-items:center;justify-content:center;opacity:0;\">"
    "<span class=\"gold\" style=\"font-size:34px;font-weight:900;letter-spacing:1px;"
    "text-indent:1px;\">${x}</span></div>`).join('')}",
    '封面五小卡 壹贰叁肆伍 → 01–05（字号 44→34 容纳两位）',
)

# 换成两位数字后要收字距 + 用等宽数字，否则数字跳动会晃
sub(
    '  #rail .ri .rn{font-size:30px;font-weight:900;letter-spacing:2px;\n',
    '  #rail .ri .rn{font-size:27px;font-weight:900;letter-spacing:1px;\n'
    '    font-variant-numeric:lining-nums tabular-nums;\n',
    '章节轨数字字距/等宽数字',
)

for old_c, new_c in [
    ('/* S2 chapter 壹 */', '/* S2 chapter 01 */'),
    ('/* S7 chapter 贰 */', '/* S7 chapter 02 */'),
    ('/* S11 chapter 叁 */', '/* S11 chapter 03 */'),
    ('/* S16 chapter 肆 */', '/* S16 chapter 04 */'),
    ('/* S20 chapter 伍 */', '/* S20 chapter 05 */'),
]:
    sub(old_c, new_c, f'镜头注释 {old_c} → {new_c}')

# ---------- 示例 3) 换元素的配色归属（保留形态） ----------
sub(
    "  .ruler .rd{position:absolute;left:50%;top:2px;transform:translateX(-50%);\n"
    "    font-size:58px;font-weight:900;line-height:1;color:#1A0605;\n"
    "    background:linear-gradient(178deg,#E8A09C,#C0494A);border-radius:999px;padding:16px 44px;white-space:nowrap;\n"
    "    box-shadow:0 0 40px rgba(192,73,74,.5),0 12px 30px rgba(0,0,0,.5);}",
    "  /* 胶囊徽章的「形态」来自参考片（它用亮色实心胶囊），这里只换「颜色归属」：\n"
    "     实心金底 + 深色字，既保住记忆点的分量，又不往本片体系里插进一块异色。 */\n"
    "  .ruler .rd{position:absolute;left:50%;top:2px;transform:translateX(-50%);\n"
    "    font-size:58px;font-weight:900;line-height:1;color:#1A1005;letter-spacing:2px;\n"
    "    background:linear-gradient(178deg,#FFF8DA 0%,#F2E0A0 42%,#DCC376 76%,#C0A85E 100%);\n"
    "    border-radius:999px;padding:16px 46px;white-space:nowrap;\n"
    "    box-shadow:0 0 46px rgba(226,203,138,.34),0 12px 30px rgba(0,0,0,.55);}",
    '红胶囊 → 金胶囊',
)

# ---------- 落盘前完整性校验 ----------
checks = [
    ('元素渲染已移除', html.count("appendChild(el('div','chapct'") == 0),
    ('失效实参已清零', len(re.findall(r"'\d+:\d+\.\d+ [–-] \d+:\d+\.\d+'", html)) == 0),
    ('编号汉字不再出现在渲染内容里',
     ("['壹','贰','叁','肆','伍']" not in html)
     and all(f'>{c}<' not in html for c in '壹贰叁肆伍')
     and all(f'chapter {c}' not in html for c in '壹贰叁肆伍')),
    ('旧配色已移除', '#E8A09C' not in html),
    ('镜头数未变', html.count('add(') >= 25),
    ('st.innerHTML 数量不变', html.count('st.innerHTML=') == orig.count('st.innerHTML=')),
    # div 计数天然不平衡（JS 模板串里有裸 </div>），所以与基线比较，不断言 == 0
    ('div 计数与基线一致',
     (html.count('<div') - html.count('</div>')) == (orig.count('<div') - orig.count('</div>'))),
]
bad = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(('  ok  ' if ok else '  XX  ') + name)
if bad:
    print('\n校验未通过：', bad, '\n已中止，未写盘。')
    sys.exit(1)

io.open(SRC, 'w', encoding='utf-8').write(html)
print()
for l in log:
    print(l)
print(f'\n已写盘 {SRC}  ({len(orig)} → {len(html)} 字符)')
