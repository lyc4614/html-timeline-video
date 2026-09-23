# html-timeline-video

把一份文稿（SRT / 口播稿 / 分镜脚本）做成**信息图动效视频** —— 用「HTML/CSS 时间轴动效页 → 本机 Chrome 逐帧截图 → ffmpeg 编码」的链路，**不引入任何渲染框架**。

适用场景：数据密集的信息图动效、数字跳动、图表生长、章节卡切换、字幕烧录 —— 一切用 CSS 能画出来的动效，且需要**帧精确、可重放、改一版只重跑渲染**。

---

## 为什么是这条路

| 对比项 | 本方案 | Remotion / After Effects |
|---|---|---|
| 要装什么 | 本机已有的 Chrome + ffmpeg | Node 渲染框架 / 大型商业软件 |
| 渲染产物 | 帧精确、逐帧可复现 | 帧精确 |
| 上手成本 | 会写 HTML/CSS 就行 | 要学框架 API / 软件操作 |
| 改一版 | 改 CSS，重跑渲染 | 重新渲染 |
| 代价 | 复杂 3D / 实拍素材做不了 | — |

核心思路很朴素：视频本质上就是 `f(t) → 一帧画面`。所以把整支片子写成一个**由时间 `t` 完全驱动的单页 HTML**，剩下的只是循环截图。

```
index.html   一个 1080×1920 页面，导出 window.__render(t) / __duration / __fps
render.cjs   puppeteer-core 驱动本机 Chrome：for t in 0..DUR: __render(t) → screenshot → frames/f-00000.png
             ffmpeg -framerate 30 -i frames/f-%05d.png → out.mp4
check.cjs    定点抽帧到 check/，改视觉时先抽帧再全渲
```

---

## 快速开始

### 1. 探测环境

```bash
command -v ffmpeg
ls "/c/Program Files/Google/Chrome/Application/chrome.exe"
```

- 没有 Chrome 时可用 **Edge**（同为 Chromium 内核）顶替 `executablePath`。
- 不要用 `npx playwright install` 下载 Chromium —— 本机已有 Chrome，走 `puppeteer-core` 最省事。

### 2. 装依赖（隔离目录，不污染全局）

```bash
cd <你的 node workspace>
node <npm-cli.js> install puppeteer-core --no-audit --no-fund
```

运行脚本时设 `NODE_PATH` 指向该 `node_modules`。

### 3. 写页面

复制 `assets/index-template.html` 作为骨架，遵守三条契约：

```js
window.__render = render;   // (t: seconds) => void，幂等：对任意 t 调用都能还原该时刻画面
window.__duration = DUR;    // 总时长（秒）
window.__fps = FPS;
```

关键写法：
- 镜头用**绝对定位**叠在一起，`render(t)` 里只 `display:block/none` 当前可见的 1–2 个。
  **不要用 CSS `animation`/`transition`** —— 逐帧截图下它们不受控（截图时刻与动画时间轴对不齐）。
- 每个镜头一个 `fn(el, lt, t)`，`lt = t - 镜头起始时间`，所有动画都用 `lt` 算。
- 缓动函数自己写（`ease` / `lerp` / `clamp`），不依赖库。
- 字幕**硬烧**进画面（一个固定在底部的 `#sub`），不要另做 srt 软字幕。

### 4. 测速 → 抽帧质检 → 全片渲染

```bash
node render.cjs --test --noenc        # 散布采样 120 帧测速
node check.cjs 1.5 10 44 74 97 145    # 定点抽帧到 check/
node render.cjs                       # 全片渲染 + 编码
```

> ⚠️ **性能是这个方案唯一真正的坑**：headless Chrome 是软件光栅化、无 GPU 加速。
> 不遵守 `SKILL.md` 里的分层规则，渲染会**慢 4–5 倍**（实测 0.128 → 0.6+ s/帧）。

---

## 目录结构

```
SKILL.md                         完整方法论（1066 行）—— 真正的内容在这里
assets/
  index-template.html            页面骨架（#bg + #root + __render 契约）
  render.cjs                     逐帧截图 + ffmpeg 编码（--test 测速 / --noenc 只截图）
  check.cjs                      定点抽帧质检
  gen_bg.py / gen_bg_clean.py    烘焙背景底图（暗角/辉光/星点 → bg.png）
  sample_ref.py                  逆向采样参考视频的真实规格
  style-gold.css                 「高级金」风格 CSS 底座
  ring-progress-template.html    环形进度章节卡原型
  patch-template.py              批量改造补丁脚本骨架（锚点核对 + 落盘前校验）
  bump_text_contrast.py          全片文字对比度批量提亮
  scan_orphan_classes.py         找「HTML 在用、CSS 无定义」的孤儿 class
  scan_selector_mismatch.py      找「动画选择器选不中元素」导致的静默隐身
  check_overflow.cjs             DOM 几何检测：超界 / 贴边
  probe_styles.cjs               DOM 计算样式探针
  probe_shots.cjs                量各镜头内容占安全区多少（DOM 几何法）
  probe_by_dom.py                按 DOM 坐标采样元素明度（治「寡淡」）
  shoot_at.cjs                   按时间点抽静帧
  shoot_variants.cjs             一次渲染多个设计方案，便于横向评审
  shoot_storyboard.cjs           批量出静态分镜图
  make_compare_sheet.py          方案对比总览图
  make_specimen_sheet.py         字体候选样张
  fonts/                         思源宋体/黑体 + 优设标题黑（OFL / 免费商用）
```

脚本都通过**环境变量或命令行参数**取路径（`CHROME_PATH` / `PROJ_ROOT` / `VIDEO_ROOT`），
可直接拿到自己的工程里用，无需改源码。

---

## 这套方法论最值钱的几条

都是从真实事故里总结出来的，完整版见 `SKILL.md`。

**① 「寡淡」是可量化的，不要凭肉眼反复调色**

| 元素区域均值明度 | 结论 |
|---|---|
| `> 背景 + 0.15` | 立得住 |
| `背景 ~ 背景+0.15` | 偏淡，客户会说「寡淡」 |
| **`≤ 背景`** | **等于没画**（贴在纯黑上被吸掉） |

实测：`rgba(色,.06~.14)` 的卡面贴纯黑后明度只有 `0.023`，**比页面背景 `0.049` 还暗** —— 卡面等于没画。
修到 `.46 / .62→.34` 后，同一张卡明度从 `0.023` 升到 `0.366`（**16 倍**）。

**② 柱子绝不能「渐变到 transparent」**
`linear-gradient(180deg, 色.34, transparent)` 会让柱子下半截成为空腔，看起来像「透明玻璃管」。
改成 `.92 → .52` + `inset` 内辉光，整根柱子才是实体。

**③ 别目测标坐标，用 `getBoundingClientRect()`**
估偏了就采到背景上，读出的数全是假的。正确做法：拿元素真实 box，**向内缩 12%** 避开描边与四角花纹，再采样。

**④ 原型 ≠ 正片**
分镜原型和生产文件是两份独立文件。用户提的修改只改在原型上，正片里那条旧元素会**一直活到成片里**，而且渲染不报任何错。每改一条都要在正片文件里 `grep` 复核。

**⑤ 检查工具自己也会错**
任何「检查器 / 校验器 / 断言」都必须做**双向验证**：正片通过（退出码 0）**且**人为反例被抓到（退出码 1）。只做前者，你得到的可能是一个永远说「通过」的废工具。

**⑥ 批量改造必须走脚本**
每处替换都断言「期望 N 次 / 实际 N 次」，锚点失配立刻中止、一个字都不写盘；落盘前跑完整性校验，不过就 `sys.exit(1)`。手工改漏一处不会报错，要到成片里才发现。

**⑦ 背景网格要「慢」**
速度定在 `0.5–1px/s`（走完一格 60–150 秒），再叠一层 `sin` 周期的亮度呼吸（19s、±12%、两层错开半周期）。
快 = 闪 = 廉价；慢 = 高级。**这是唯一一处「慢了比快了好看」的地方**。

**⑧ 画面空，就换布局 —— 不要加大 padding**
「一行 N 张卡」在竖屏里天生占不满高度（实测只到 28%）。换成纵向铺开的排行条能到 72%。
加减 padding 是零和博弈（卡高了但元素没多，还是空）；**换布局 + 加信息**才是根治。

---

## 平台合规（发布到视频号 / 抖音前）

若客户要求规避平台审查风险：**只做视觉提示，不做动作引导**。
去掉所有二维码占位、`扫码` / `长按识别` / `去搜索` 类引导词；片尾可留品牌卡 + 呼吸闪烁。
有配套的合规词扫描脚本，**只扫可见文本**（SUBS 表 + `innerHTML`），否则会误伤 patch 脚本自身的注释。

---

## 环境要求

- **Chrome** 或 **Edge**（Chromium 内核，任选）
- **ffmpeg**（编 H.264）
- **Node.js** + `puppeteer-core`
- **Python 3** + `Pillow`（仅背景烘焙 / 采样类脚本需要）

跨平台：脚本以 Windows 为主环境编写（路径兼容反斜杠），Chrome / ffmpeg 均可通过环境变量指定，
macOS / Linux 下改 `CHROME_PATH` 即可。

---

## 许可

代码以 **MIT** 发布，见 `LICENSE`。
`assets/fonts/` 下的字体遵循各自许可（思源系列为 SIL OFL 1.1，优设标题黑为免费商用），
详见 `assets/fonts/README.md`。

`SKILL.md` 里的方法论与实测数值来自真实项目，欢迎参考；
如果对你有用，欢迎开 Issue 交流踩过的坑。
