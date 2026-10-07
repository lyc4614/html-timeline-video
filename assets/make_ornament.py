# -*- coding: utf-8 -*-
"""生成卡片纹样（花饰分隔线 / 卡面颗粒），写回 card-system.css 的 <<ORN>> 标记区。

设计决定：
  · 顶部与底部用**同一个参数化花饰**（宽度/高度/是否翻转/是否加密 可调）——
    一套语言上下呼应，比各画各的精致得多。
  · 底部 = 顶部花饰**垂直翻转** + 加两片叶。翻转靠 SVG 组变换实现（一行），
    不是手写第二份坐标 —— 手写两份必然漂移（v3 踩过）。
  · 卷草的灵魂是螺旋：用「一连串小圆弧、半径逐段衰减」逼近，参数直接可调。

用法：
  python make_ornament.py            生成并写回 card-system.css（幂等，可反复跑）
  python make_ornament.py --preview  另存 ornament_preview.html（3 倍放大，快速看形）
"""
import io, math, re, sys, urllib.parse

GOLD = '#E8D9A8'          # 纹样主色（与图标描边同色，一套语言）
SW = 1.15                 # 主线宽
SW2 = 0.8                 # 细节线宽

# ---------------------------------------------------------------- 几何工具
def spiral(cx, cy, r0, a0_deg, total_deg, sweep=1, step=22, decay=0.90):
    """内卷螺旋：小圆弧串，半径每段 ×decay^(step/30)。
    a0：起始角（度，0=右，90=下；SVG y 轴向下）。sweep=1 顺时针。"""
    a = math.radians(a0_deg); r = r0
    x, y = cx + r*math.cos(a), cy + r*math.sin(a)
    d = [f"M{x:.1f} {y:.1f}"]
    for _ in range(max(1, int(round(total_deg/step)))):
        a2 = a + math.radians(step)*sweep
        r2 = r * (decay ** (step/30.0))
        x2, y2 = cx + r2*math.cos(a2), cy + r2*math.sin(a2)
        d.append(f"A{max(r,1.0):.1f} {max(r,1.0):.1f} 0 0 {sweep} {x2:.1f} {y2:.1f}")
        a, r = a2, r2
    return " ".join(d)

def leaf(x, y, L, ang, width=0.40):
    """叶片：从 (x,y) 沿 ang 方向长 L 的水滴叶（两条对称贝塞尔闭合）。"""
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    tx, ty = x+ux*L, y+uy*L
    mx, my = x+ux*L*0.5, y+uy*L*0.5
    w = L*width
    return (f"M{x:.1f} {y:.1f} "
            f"C{mx+nx*w:.1f} {my+ny*w:.1f} {tx+nx*w*.16:.1f} {ty+ny*w*.16:.1f} {tx:.1f} {ty:.1f} "
            f"C{tx-nx*w*.16:.1f} {ty-ny*w*.16:.1f} {mx-nx*w:.1f} {my-ny*w:.1f} {x:.1f} {y:.1f} Z")

def dot(x, y, r):
    return f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{r:.1f}' fill='{GOLD}' stroke='none'/>"

def uri(svg):
    # data URI 编码只能做一次，且必须交给编码函数统一做。
    # ⚠ 空格也要编码 —— 在 HTML 属性里裸空格会截断取值。
    return 'url("data:image/svg+xml,%s")' % urllib.parse.quote(svg, safe="/:=',()")

# ---------------------------------------------------------------- 参数化花饰
# 结构（左半，右半靠镜像）：细线 → 菱形端头 → 内曲线 → 卷须螺旋 → [加密叶] → 点 → 中央菱形半边
def flourish_uri(W, H, flip=False, dense=False):
    cy = H / 2.0
    xe = W * 0.352                       # 细线终点
    x1 = W * (0.390 if dense else 0.412)  # 曲线终点 = 螺旋起点（加密档外移，给中央菱形留气口）
    dh = 9.0 if dense else 11.0          # 中央菱形半高
    e = []
    # ① 外侧细线 + 菱形端头
    e.append(f"<path d='M4 {cy:.1f} H{xe:.1f}' stroke='{GOLD}' stroke-width='{SW}' stroke-linecap='round'/>")
    e.append(f"<path d='M12 {cy-3.6:.1f} L15.6 {cy:.1f} L12 {cy+3.6:.1f} L8.4 {cy:.1f} Z' "
             f"fill='none' stroke='{GOLD}' stroke-width='{SW2}'/>")
    # ② 内曲线 → 卷须螺旋（螺旋圆心偏 +9，保证起点正好接在曲线终点上）
    e.append(f"<path d='M{xe:.1f} {cy:.1f} C{xe+14:.1f} {cy:.1f} {x1-12:.1f} {cy-2.0:.1f} {x1:.1f} {cy-4.0:.1f}' "
             f"fill='none' stroke='{GOLD}' stroke-width='{SW}' stroke-linecap='round'/>")
    e.append(f"<path d='{spiral(x1+9.0, cy-4.0, 9.0, 180, 250, sweep=1)}' "
             f"fill='none' stroke='{GOLD}' stroke-width='{SW}' stroke-linecap='round'/>")
    # ③ 加密档：两片叶 + 一点（底部用）
    if dense:
        e.append(f"<path d='{leaf(x1-20, cy-2.5, 16, -122)}' fill='none' stroke='{GOLD}' stroke-width='{SW2}'/>")
        e.append(f"<path d='{leaf(x1-9, cy+3.5, 12, 118)}' fill='none' stroke='{GOLD}' stroke-width='{SW2}'/>")
        e.append(dot(x1+30, cy-9.0, 1.6))
    # ④ 菱形两侧的点
    e.append(dot(W*0.452, cy-8.0, 1.6) + dot(W*0.460, cy+8.0, 1.6))
    # ⑤ 中央菱形的左半（镜像后合成完整菱形）
    e.append(f"<path d='M{W/2:.1f} {cy-dh:.1f} L{W/2-dh:.1f} {cy:.1f} L{W/2:.1f} {cy+dh:.1f}' "
             f"fill='none' stroke='{GOLD}' stroke-width='{SW}' stroke-linejoin='round'/>")
    half = "".join(e)
    g = (f"<g fill='none'>{half}</g>"
         f"<g fill='none' transform='translate({W},0) scale(-1,1)'>{half}</g>")
    if flip:                             # 底部：整组垂直翻转
        g = f"<g transform='translate(0,{H}) scale(1,-1)'>{g}</g>"
    return uri(f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' "
               f"viewBox='0 0 {W} {H}'>{g}</svg>")

# ---------------------------------------------------------------- 卡面颗粒
# feTurbulence 真噪声 + discrete 阈值：只有最亮一档透出来 → 稀疏金尘，不会把黑底洗灰。
def grain_uri(size=150):
    tbl = " ".join(["0"]*15 + ["0.5"])
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}'>"
           f"<filter id='g' x='0' y='0' width='100%' height='100%'>"
           f"<feTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='2' stitchTiles='stitch'/>"
           f"<feColorMatrix type='matrix' values='0 0 0 0 0.91  0 0 0 0 0.85  0 0 0 0 0.66  0 0 0 0.9 0'/>"
           f"<feComponentTransfer><feFuncA type='discrete' tableValues='{tbl}'/></feComponentTransfer>"
           f"</filter>"
           f"<rect width='{size}' height='{size}' filter='url(#g)'/></svg>")
    return uri(svg)

# ---------------------------------------------------------------- 落盘
def main():
    div = flourish_uri(620, 34, flip=False, dense=False)     # 顶部
    scr = flourish_uri(240, 40, flip=True,  dense=True)      # 底部（翻转 + 加密）
    grain = grain_uri()
    p = 'card-system.css'
    css = io.open(p, encoding='utf-8').read()
    # 写进 :root 的标记区（幂等：可反复运行）。
    # ⚠ 两个坑都踩过：
    #   ① 用 lambda 做替换 —— URI 里含 % 字符，直接当 repl 会被转义吃掉；
    #   ② 标记区首行是「/* <<ORN>> ... */」，正则从 <<ORN>> 匹配到 <<ORN-END>>
    #      会把中间的 **注释闭合 */ 一起消费掉** —— 补回 ' */' 和 ' /* '，
    #      否则三个变量整段掉进注释里，无报错、纹样就是不出来。
    block = "  --orn-grain:%s;\n  --orn-div:%s;\n  --orn-scroll:%s;" % (grain, div, scr)
    new, k = re.subn(r'(<<ORN>>)[\s\S]*?(<<ORN-END>>)',
                     lambda m: m.group(1) + ' */\n' + block + '\n  /* ' + m.group(2), css)
    assert k == 1, '标记区替换失败（匹配 %d 处）' % k
    io.open(p, 'w', encoding='utf-8', newline='\n').write(new)
    print('✓ 纹样已写入 card-system.css（div %d / scroll %d / grain %d 字符）'
          % (len(div), len(scr), len(grain)))

    if '--preview' in sys.argv:
        def raw(u): return urllib.parse.unquote(u[len('url("data:image/svg+xml,'):-2])
        io.open('ornament_preview.html', 'w', encoding='utf-8').write(
            f"""<!doctype html><meta charset="utf-8">
<body style="margin:0;background:#0B0B0D;padding:40px;font-family:sans-serif">
<div style="color:#888;font-size:13px;margin:8px 0">顶部花饰分隔线（2.5×，620×34）</div>
<img src="data:image/svg+xml,{urllib.parse.quote(raw(div), safe="/:=',()")}" style="width:1550px;display:block">
<div style="color:#888;font-size:13px;margin:24px 0 8px">底部卷草（3×，240×40，垂直翻转 + 加密）</div>
<img src="data:image/svg+xml,{urllib.parse.quote(raw(scr), safe="/:=',()")}" style="width:720px;display:block">
</body>""")
        print('✓ ornament_preview.html')

if __name__ == '__main__':
    main()
