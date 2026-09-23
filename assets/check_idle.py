# -*- coding: utf-8 -*-
"""空场诊断：每个镜头的时长 vs 最后一个动画动作的时间。

算法：取 add(s,e,...) 函数体原文，找所有 `lt-N` 形式的偏移量，
再减去每个 fading 的时长 *.6 —— 用「最后一步开始时间」近似等于
「内容铺满的时刻」。(e-s) - last_start = 空转秒数。
>4s 必须补内容（用户原话：「有8秒空场」这类一定要能定位）。

输出按空转秒数降序，方便直接看最该补的是哪几个。
"""
import io, re, sys

def parse(path):
    src = io.open(path, encoding='utf-8').read()
    # 镜头范围 + 函数体（用括号配平抓取 add( ... ) 的第 5 个实参那个回调）
    out = []
    for m in re.finditer(r'add\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*\{[^}]*\}\s*,\s*\(', src):
        s = float(m.group(1)); e = float(m.group(2))
        # 函数体要从箭头函数的 `{` 起配平 —— 若从 `(root,lt,t)` 的括号起算，
        # depth 会在参数表闭合那一步就归零，body 只有 11 个字符，
        # 结果全片每个镜头都报「最后动作 0.00」这种假数据。
        k = src.index('{', src.index('=>', m.end() - 1)) if '=>' in src[m.end() - 1:m.end() + 80] \
            else src.index('=>', m.end() - 1)
        depth = 0
        for j in range(k, len(src)):
            if src[j] == '{': depth += 1
            elif src[j] == '}':
                depth -= 1
                if depth == 0: break
        body = src[k:j + 1]
        out.append((s, e, body))
    return out

def last_action(body):
    """返回最后一步动画的「开始时间」估计。"""
    best = 0.0
    # 形态：(lt-X.Y)/Z  或 (lt-X.Y)
    for m in re.finditer(r'\(lt\s*-\s*([\d.]+)\)', body):
        best = max(best, float(m.group(1)))
    # 形态：lt/X.Y - N  或 i*X.Y 的节奏（如 (lt-1.7-i*0.85)）
    for m in re.finditer(r'\(lt\s*-\s*([\d.]+)\s*-\s*[a-z]\s*\*\s*([\d.]+)\)', body):
        best = max(best, float(m.group(1)))
    return best

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    rows = []
    for s, e, body in parse(path):
        last = last_action(body)
        idle = (e - s) - last
        rows.append((s, e, e - s, last, idle))
    rows.sort(key=lambda r: -r[4])
    print('%-4s %-16s %7s %8s %9s  %s' % ('#', '镜头区间', '时长', '最后动作', '空转', '判定'))
    total = 0
    for i, (s, e, dur, last, idle) in enumerate(rows, 1):
        flag = 'OK'
        if idle > 6: flag = '✗ 严重空转'
        elif idle > 4: flag = '⚠ 偏空'
        if idle > 4: total += 1
        print('%-4d %6.2f→%-7.2f %7.2f %8.2f %9.2f  %s' % (i, s, e, dur, last, idle, flag))
    print()
    print('镜头总数 %d，空转 >4s 的 %d 个' % (len(rows), total))

main()
