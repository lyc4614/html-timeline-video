# 字体文件与许可

本目录下的 `.woff2` 是**可直接随工程分发的开源中文字体**，用 `@font-face` 引入即可，
不需要用户预装（Chrome headless 配 `--allow-file-access-from-files` 能直接读本地字体文件）。

| 文件 | 字体 | 许可 |
|---|---|---|
| `NotoSerifSC-Bold.woff2` | 思源宋体 Bold | SIL Open Font License 1.1 |
| `NotoSerifSC-Black.woff2` | 思源宋体 Black | SIL Open Font License 1.1 |
| `NotoSansSC-Bold.woff2` | 思源黑体 Bold | SIL Open Font License 1.1 |
| `NotoSansSC-Black.woff2` | 思源黑体 Black | SIL Open Font License 1.1 |
| `YouSheBiaoTiHei.woff2` | 优设标题黑 | 优设官方声明免费商用 |

- 思源系列（Noto CJK）由 Google / Adobe 发布，OFL 1.1 允许**自由使用、修改、再分发，
  包括商用**；再分发时保留许可声明即可。
- 优设标题黑由优设（UISDC）发布并声明免费商用。
- **「高级金」风格请用思源宋体（衬线）**；金色渐变配无衬线（雅黑一类）会明显廉价。
- 想换字体时的下载源见上层 `SKILL.md` 的「字体」一节。

> 注意：字体文件较大（每个 0.6–1.6MB）。若你的仓库不想带二进制文件，
> 可删掉本目录，让使用者按 `SKILL.md` 里的 jsDelivr 链接自行下载。
