# -*- coding: utf-8 -*-
"""合规词扫描（发布到视频号 / 抖音前）。

只扫「会显示出来的文本」—— SUBS 表 + 各镜头 innerHTML 的标签间文字。
**不扫源码整体**：否则会误伤注释与补丁脚本里的词
（实测踩过：注释「弧长按章号递增」里的「长按」被当成风险词）。

用法：python scan_compliance.py index.html
退出码：0=通过，1=命中风险词
"""
import io
import re
import sys

BAN = ['扫码', '长按', '二维码', '长按识别', '扫一扫', '去搜索',
       '点击下方', '主页', '私信', '加微信', '免费领']


def visible_text(src):
    """只取真正会显示出来的文字。"""
    out = []
    for m in re.finditer(r'\[\s*[\d.]+\s*,\s*[\d.]+\s*,\s*"((?:[^"\\]|\\.)*)"\s*\]', src):
        out.append(('SUBS', m.group(1)))
    for m in re.finditer(r'\.innerHTML\s*=\s*`([\s\S]*?)`', src):
        out.append(('innerHTML', re.sub(r'<[^>]+>', ' ', m.group(1))))
    return out


def main():
    p = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    src = io.open(p, encoding='utf-8').read()
    blocks = visible_text(src)
    hit = 0
    for w in BAN:
        for kind, t in blocks:
            if w in t:
                hit += 1
                print('  [X] %s  <-  %s: %s' % (w, kind, t.strip()[:90]))
    print('扫描可见文本块 %d 处，命中 %d 处' % (len(blocks), hit))
    if hit:
        print('结论：需处理（片尾不得出现二维码 / 扫码 / 搜索类引导词）')
        sys.exit(1)
    print('结论：通过（无平台风险词）')


if __name__ == '__main__':
    main()
