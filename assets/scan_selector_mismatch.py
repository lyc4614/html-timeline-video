# -*- coding: utf-8 -*-
"""scan_selector_mismatch.py —— 扫描「动画选择器选不中元素」的隐性 bug

背景（真实踩坑）：
  改 HTML 结构时把 <div class="tag"> 换成不带类名的 div，
  但入场动画仍在写 st.querySelectorAll('#s12c .tag').forEach(...)
  → 匹配 0 个元素 → 那些元素的 opacity 永远停在 0 → **整块内容不可见**。
  渲染日志不报错、控制台不报错、文本内容校验也通过，
  只有肉眼看截图才发现「怎么什么都没有」。

  ⚠ 这类 bug 的共同特征：元素带初始 opacity:0（或 transform 位移），
    依赖 JS 在动画里把它改成 1。一旦选择器失配，元素就永久隐身。

用法：
  python scan_selector_mismatch.py index.html
  python scan_selector_mismatch.py index.html --verbose

退出码：0 = 通过，1 = 发现可疑点。
"""
import re
import sys
import io


def load(p):
    return io.open(p, encoding="utf-8").read()


def find_shot_spans(src):
    """按 /* Sxx 注释切分镜头，返回 [(id, start, end)]

    ⚠ 只认「镜头代码块」的注释，不认 CSS 段里的注释。
    踩坑：在 <style> 里写 `/* S12 新校卡：... */` 解释样式，
    会被旧版一并当成镜头段 —— 那段没有 JS 动画，于是误报
    「S12 有 opacity:0 但没有动画」。修法：要求注释后紧跟镜头代码特征。
    """
    marks = []
    for m in re.finditer(r"/\* (S\d+) ", src):
        tail = src[m.start():m.start() + 260]
        # 镜头块一定以 IIFE 或相机初始化开头；CSS 注释不会
        if ("(function(){" in tail) or re.search(r"\bconst d\s*=\s*build", tail):
            marks.append((m.group(1), m.start()))
    spans = []
    for i, (sid, st) in enumerate(marks):
        en = marks[i + 1][1] if i + 1 < len(marks) else len(src)
        spans.append((sid, st, en))
    return spans


def class_tokens_in(html_seg):
    """把一个 HTML 片段里所有 class 属性拆成 token 集合。
    同时解析模板里可能动态拼出的类名，如 class="ncard s-${sem}"。"""
    tokens = set()
    for m in re.finditer(r'class\s*=\s*"([^"]*)"', html_seg):
        raw = m.group(1)
        # 把 ${...} 展开成一个占位符，保留前缀/后缀的静态部分
        for part in raw.split():
            if "${" in part:
                # s-${sem} -> 记录前缀 "s-"，用于后续前缀匹配
                prefix = part.split("${")[0]
                if prefix:
                    tokens.add(prefix + "\x00")   # \x00 标记「这是动态前缀」
            else:
                tokens.add(part)
    return tokens


def token_matches(tokens, cls):
    """判断 tokens 里是否存在与 cls 对应的类名（含动态前缀匹配）"""
    if cls in tokens:
        return True
    for t in tokens:
        if t.endswith("\x00"):
            prefix = t[:-1]
            if cls.startswith(prefix):
                return True
    return False


def scan(src, verbose=False):
    problems = []
    ok_count = 0

    # ---- 1. querySelectorAll('#container .cls') / ('#container > tag') 命中检查 ----
    # 真实写法用单引号。四种形态都要覆盖：
    #   '#s12c .ncard'    后代 + 类选择器（**类名前的点号必须显式匹配**）
    #   '#s23v > .vscard' 子代 + 类选择器（**曾漏判：把 .vscard 当标签名找**）
    #   '#s15c > div'     子代 + 标签选择器
    #   '#s1c div'        后代 + 标签选择器
    # 踩坑记录：comb 判定若先于 is_class 判定，`> .cls` 会被误当标签选择器。
    #           必须 **先判 is_class**，再判 comb。
    call_re = re.compile(
        r"""querySelectorAll\(\s*['"][#](?P<cid>[\w-]+)\s*"""
        r"""(?P<comb>>|\s)\s*"""
        r"""(?P<dot>\.)?(?P<sel>[\w-]+)['"]\s*\)"""
    )
    calls = list(call_re.finditer(src))
    if not calls:
        problems.append(
            "未匹配到任何 `querySelectorAll('#id .cls')` 调用 —— "
            "若正片确实有这类调用，说明本脚本的正则失效了（工具自身问题）")
    elif verbose:
        print(f"  （匹配到 {len(calls)} 个容器选择器调用）")

    for m in calls:
        container = m.group("cid")
        comb = m.group("comb")
        is_class = m.group("dot") == "."
        sel = m.group("sel")

        ci = src.find(f'id="{container}"')
        if ci < 0:
            problems.append(f"容器 #{container} 在 HTML 里不存在（选择器写错？）")
            continue

        # 右边界：下一个镜头注释，避免扫到隔壁
        right = ci + 3000
        nxt_shot = src.find("/* S", ci)
        if nxt_shot > 0:
            right = min(right, nxt_shot)
        seg = src[ci:right]

        if is_class:
            # 类选择器（后代 `#id .cls` 或子代 `#id > .cls` 都一样查类名）
            tokens = class_tokens_in(seg)
            hit = token_matches(tokens, sel)
            label = f"#{container} {comb} .{sel}"
        elif comb == ">":
            # 子元素标签选择器：找 <tag  且该标签在容器直接子级
            hit = re.search(rf"<{re.escape(sel)}[\s>]", seg) is not None
            label = f"#{container} > {sel}"
        else:
            # 后代 + 标签选择器
            hit = re.search(rf"<{re.escape(sel)}[\s>]", seg) is not None
            label = f"#{container} {sel}"

        if hit:
            ok_count += 1
            if verbose:
                print(f"  [OK]   '{label}'")
        else:
            extra = ""
            if is_class:
                found = sorted(t for t in class_tokens_in(seg) if not t.endswith("\x00"))
                extra = f"（该容器下实际 class：{found[:8]}）"
            problems.append(f"'{label}' 无对应元素 → 该组元素将永久隐身{extra}")

    # ---- 2. 带 opacity:0 的元素是否都有动画点亮 ----
    for sid, st, en in find_shot_spans(src):
        body = src[st:en]
        n_init0 = len(re.findall(r"opacity:0", body))
        if n_init0 == 0:
            continue
        has_anim = ("forEach" in body and "opacity" in body) or \
                   re.search(r"\.style\.opacity\s*=", body)
        if not has_anim:
            problems.append(
                f"{sid}: 有 {n_init0} 处 opacity:0 初始态，但镜头内未发现 opacity 动画 → 可能永久不可见")
        else:
            ok_count += 1

    return problems, ok_count


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        sys.exit(2)
    path = args[0]
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    src = load(path)

    print(f"扫描 {path}（{len(src)} 字符）")
    print("-" * 62)

    problems, ok_count = scan(src, verbose)

    if problems:
        print(f"\n发现 {len(problems)} 个可疑点：\n")
        for p in problems:
            print(f"  [FAIL] {p}")
        print("\n提示：这类 bug 不会报错，只会让内容静默消失。")
        print("      修法：给元素加回可选中类名，或让选择器与新结构对齐。")
        sys.exit(1)
    else:
        print(f"  [OK] {ok_count} 处检查全部通过")
        print("\n没有发现选择器失配或永久隐身的元素。")


if __name__ == "__main__":
    main()
