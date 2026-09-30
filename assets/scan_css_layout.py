# -*- coding: utf-8 -*-
"""scan_css_layout.py —— 扫描「CSS 规则静默失效」与「元素被内容撑破」两类 bug

背景（真实踩坑）：
  1) CSS 写 `.step .sn{width:66px;height:66px;border-radius:50%}`
     但 HTML 里这些容器走的是**内联 flex**，根本没有 `.step` 类
     → 后代选择器整体失配 → 圆点塌成默认 16px 文本，实测 **9×24px**。
     不报错、不影响其它元素，只有量 getBoundingClientRect 才发现。
     注意：这和 `scan_selector_mismatch.py` 不同 ——
     那个查的是 **JS 选择器选不中**，这个查的是 **CSS 规则本身不生效**。

  2) `.stage` 是 `flex-direction:column` + `align-items:center` 时，
     子项宽度由内容决定 + 文案 `white-space:nowrap` → 卡片会被撑到超出安全区
     （实测 944px > 904px 安全区，左边缘跑到 x=68）。
     修法：卡片类统一 `max-width:100%`（防御性），并收短 nowrap 文案。

用法：
  python scan_css_layout.py index.html
  python scan_css_layout.py index.html --verbose

退出码：0 = 通过，1 = 发现可疑点，3 = 工具自检失败。
"""
import io
import re
import sys

SAFE_SELECTOR_HINT = ('shot', 'stage', 'an', 'grid', 'html', 'body')


def load(p):
    return io.open(p, encoding='utf-8').read()


def split_css_body(src):
    """返回 (css 文本, html 正文)。去注释后的 CSS 用于选择器分析。"""
    if '</style>' not in src:
        return '', src
    css, body = src.split('</style>', 1)
    if '<style' in css:
        css = css.split('<style', 1)[1]
        css = css.split('>', 1)[1] if '>' in css else css
    return css, body


def html_classes(body):
    out = set()
    for m in re.finditer(r'class\s*=\s*"([^"]*)"', body):
        for c in m.group(1).split():
            out.add(c)
    # 内联 style 里不会有 class；但模板拼接的 class="a ${x}" 已由上面的 split 覆盖
    return out


def strip_comments(css):
    return re.sub(r'/\*[\s\S]*?\*/', ' ', css)


def desc_ancestors(css):
    """列出所有「后代选择器」及其祖先类。
    跳过带 > + ~ 的组合器（那些是另一类问题）、@ 规则、伪类。"""
    rules = []
    for m in re.finditer(r'([^{}]+)\{', css):
        group = m.group(1).strip()
        if not group or group.startswith('@') or group.startswith('from') or group.startswith('to'):
            continue
        for sel in group.split(','):
            sel = sel.strip()
            if not sel or any(ch in sel for ch in '>+~'):
                continue
            parts = sel.split()
            if len(parts) < 2:
                continue
            ancestors = []
            for p in parts[:-1]:
                ancestors.extend(re.findall(r'\.([\w-]+)', p))
            if ancestors:
                rules.append((sel, ancestors))
    return rules


def scan(src, verbose=False):
    css_raw, body = split_css_body(src)
    css = strip_comments(css_raw)
    used = html_classes(body)
    defined = set(re.findall(r'\.([A-Za-z][\w-]*)', css))

    problems = []
    ok = 0

    # ---- 1. 孤儿 class：HTML 在用、CSS 没定义 ----
    orphan = sorted(c for c in used if c not in defined)
    if orphan:
        problems.append('孤儿 class（用了但没定义，会静默退回 16px 默认样式）: %s' % orphan)
    else:
        ok += 1

    # ---- 2. 后代选择器的祖先类不存在 ----
    rules = desc_ancestors(css)
    miss = []
    for sel, ancestors in rules:
        for a in ancestors:
            if a not in used:
                miss.append((sel, a))
    if miss:
        for sel, a in miss:
            problems.append('后代选择器 `%s` 的祖先类 .%s 不在 HTML 中 → 整条规则不生效' % (sel, a))
    else:
        ok += 1

    # ---- 3. nowrap 文案 + 卡片是否做了 max-width 防御 ----
    nowrap = re.findall(r'white-space:\s*nowrap', body)
    cards = len(re.findall(r'class="[^"]*\b(card|rrow|grp|tag)\b', body))
    maxw = len(re.findall(r'max-width:\s*100%', src))
    if nowrap and cards and maxw == 0:
        problems.append(
            '有 %d 处 nowrap 文案 + %d 个卡片类，但全文件没有 max-width:100% —— '
            'flex column + align-items:center 下卡片会被文案撑破安全区' % (len(nowrap), cards))
    else:
        ok += 1

    if verbose:
        print('  HTML class %d / CSS class %d / 后代选择器 %d / nowrap %d / max-width %d'
              % (len(used), len(defined), len(rules), len(nowrap), maxw))

    return problems, ok, used, css


def self_test(css):
    """双向验证：注入一条必然失配的规则，检查必须能抓到，否则工具本身不可信。

    ⚠ desc_ancestors 返回的是 (选择器, 祖先类列表)，第二项是 **list**。
      写 `any(a == 'xxx' for _, a in rules)` 会拿 list 和 str 比，恒为 False ——
      自检永远「抓不到」，工具就成了摆设。必须用 `in` 判成员。
    """
    probe = strip_comments(css + '\n.zzz-absent .probe-y{color:red}')
    return any('zzz-absent' in ancs for _, ancs in desc_ancestors(probe))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if not args:
        print(__doc__)
        sys.exit(2)
    path = args[0]
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    src = load(path)

    print('扫描 %s（%d 字符）' % (path, len(src)))
    print('-' * 62)

    problems, ok, used, css = scan(src, verbose)

    if not self_test(css):
        print('  [FAIL] 工具自检失败：注入的失配规则未被抓到，本工具结论不可信。')
        sys.exit(3)
    print('  [OK] 自检通过（注入 .zzz-absent .probe-y 已被抓到）')

    if problems:
        print('\n发现 %d 个可疑点：\n' % len(problems))
        for p in problems:
            print('  [FAIL] %s' % p)
        print('\n提示：这类 bug 不报错，只让样式静默失效或元素被撑出安全区。')
        sys.exit(1)
    print('  [OK] %d 项静态检查全部通过' % ok)


if __name__ == '__main__':
    main()
