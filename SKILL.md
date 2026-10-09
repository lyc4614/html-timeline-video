---
name: html-timeline-video
description: |
  用「HTML/CSS 时间轴动效页 → 本机 Chrome 逐帧截图 → ffmpeg 编码」产出竖屏/横屏信息图动效视频。
  当用户要把一份文稿（srt / 口播稿 / 分镜脚本）做成**信息图动效视频、数据动画视频、数字跳动卡片视频**时触发；
  也适用于没有 Remotion/AfterEffects、只有本机 Chrome + ffmpeg 时要做帧精确可控的动效视频。
  优势：不用下载 Chromium、不用装渲染框架、帧精确、任何 CSS 动画都能用、改一版只重跑渲染。
  关键坑：headless 下**全屏渐变元素逐帧重绘会让渲染慢 4–5 倍**，必须按本 skill 的分层规则写页面。
license: MIT
agent_created: true
---

# HTML 时间轴动效 → 视频（Chrome 逐帧 + ffmpeg）

> 这是 `html-timeline-video` 技能的方法论主体。仓库总览与快速开始见 [README.md](./README.md)。
> 配套脚本、页面骨架与字体在 [`assets/`](./assets/)。

## 何时用 / 不用

**用**：数据密集的信息图动效、数字跳动、图表生长、章节卡切换、字幕烧录 —— 一切「用 CSS 能画出来的动效」，且需要**帧精确可重放**的场合。
**不用**：需要真人/实拍素材（改用「静态分镜图 + SRT 合成」的路线）、复杂 3D、逐帧手绘的地方。已经有 Remotion / After Effects 工程的地方也不要重做 —— 本方案的价值是「不引入渲染框架」。

## 核心思路

video 本质上 = `f(t) → 一帧画面`。所以只要把整支片子写成一个**由时间 t 完全驱动的单页 HTML**，剩下的就是循环截图。

```
index.html   一个 1080×1920 页面，导出 window.__render(t) / __duration / __fps
render.cjs   puppeteer-core 驱动本机 Chrome，for t in 0..DUR: __render(t) → screenshot → frames/f-00000.png
             最后 ffmpeg -framerate 30 -i frames/f-%05d.png → out_silent.mp4
check.cjs    定点抽帧到 check/，改视觉时先抽帧再全渲
```

`assets/` 里可直接复制的工具：

| 文件 | 用途 |
|---|---|
| `index-template.html` | 页面骨架（全局 `#bg` + `#root` + `__render` 契约 + 花字/卡片 class） |
| `render.cjs` | 逐帧截图 + ffmpeg 编码；`--test` 散布采样测速，`--noenc` 只截图。**渲染前显式预热全部 @font-face 并硬断言**（`await document.fonts.ready` 是空转的，见 8.12），不过就 exit 5；`--test` 写 `frames_test/`，不污染正式帧序列。 |
| `check.cjs` | 定点抽帧质检（`node check.cjs 1.5 10 44 145`） |
| `gen_bg.py` | 烘焙背景底图（底色+辉光+暗角+星点 → bg.png），参数按参考视频标定 |
| `sample_ref.py` | 逆向采样参考视频的真实规格（底色/网格间距/辉光/星点密度） |
| `bump_text_contrast.py` | 全片文字对比度批量提亮：`--scan` 先列出所有 rgba 色的有效亮度分布（自动标出偏淡项），`--apply` 按层级映射表批量替换并带落盘前校验。用户说「文字太浅/区分度不够」时直接上这个。 |
| `scan_orphan_classes.py` | **换 CSS 底座后必跑**：找出「HTML 在用、CSS 无定义」的孤儿 class。这类元素会静默退回 16px 默认样式，在竖屏上小到看不见（`.delta` 就是这么漏的）。 |
| `style-gold.css` | 「高级金」风格 CSS 底座（金色渐变衬线字 / 细金线卡片 / 环形进度） |
| `card-library.html` | **典藏卡片库**：横竖两画幅 + 四种卡片形态（单卡 / 1大2小扇开 / 横排数据卡 / 竖版适配）。含卷草纹与四角花纹 `<symbol>`、立体菱形鳞片背景、双层描边与金属厚度的完整实现。见「典藏卡片库」一节。 |
| `ring-progress-template.html` | 环形进度章节卡原型（数字 01–05 + 5 节点 + 弧长按章号递增） |
| `patch-template.py` | 批量改造的补丁脚本骨架（锚点核对 + 落盘前完整性校验 + 中止保护） |
| `shoot_at.cjs` | 按时间点调 `window.__render(t)` 抽静帧（带字体加载断言） |
| `check_overflow.cjs` | DOM 几何检测：找出超界 / 贴边 / 块间距异常的节点 |
| `probe_styles.cjs` | DOM 计算样式探针（确认 CSS 类真的生效，而非被 inline 或优先级盖掉） |
| `probe_shots.cjs` | **量各镜头内容占安全区多少**。DOM 几何法（非像素扫描），显式排除**常驻层**（顶部 logo / 章节轨 / 字幕带 / 章节角标）。用来定位「画面空」的镜头，见「画面太空」一节。 |
| `scan_selector_mismatch.py` | 扫「**JS 选择器**选不中元素」导致内容静默隐身。**改 HTML 结构后必跑**，且必须做双向验证（见该节）。 |
| `scan_css_layout.py` | 扫「**CSS 规则本身不生效**」与「元素被内容撑破」。三件事：① 孤儿 class ② **后代选择器的祖先类不在 HTML 里**（`.step .sn` 而 HTML 无 `.step` → 规则整体失效，66px 圆点实测塌成 9×24px）③ nowrap 文案 + 卡片缺 `max-width:100%` 的撑破风险。带自检，退出码 0/1/3。与 `scan_selector_mismatch.py` 互补：那个查 JS 侧，这个查 CSS 侧。 |
| `shoot_variants.cjs` | 一次渲染多个设计方案，便于横向评审 |
| `make_compare_sheet.py` / `make_specimen_sheet.py` | 方案对比总览 / 字体候选样张 |
| `check_geometry.cjs` | 全片几何体检：逐镜头（自动从 `add(s,e,...)` 解析时刻表）在**镜头结束前**量 `getBoundingClientRect`，报横向溢出与压禁区。跳过 `opacity:0` 是错的（几何与透明度无关），容器按 class 白名单跳过、不能用宽度阈值。**必须双向验证**（把某行字号改大 + `white-space:nowrap` 做人为反例）。 |
| `check_idle.py` | 静态空转估算：解析 `add()` 函数体里的 `lt-N` 偏移。**有已知漏算**（`-i*B` 顺序入场、连续动画），只作初筛，见「空转诊断的三层递进」。 |
| `check_motion.cjs` + `check_motion.py` | 帧间差实测：每 0.5s 渲染一帧缩到 270×480（`deviceScaleFactor:0.25`，CSS 布局不变），Python 找「画面真的没动」的段落。**判据必须是「滞后窗口内的可见变化量」，不能是相邻帧瞬时差** —— 见「空转诊断的三层递进」。|
| `check_dissolve_frames.py` | **量转场溶解的亮度塌陷**（含 `--selftest`）。读 `frames/`，在每个镜头交接处前后对称取样，比「实得中点亮度」与「按权重插值的应有中点」。**明度必须用 R/G/B 算术均值**（`max(RGB)` 非线性会造假塌陷）。判据 <6%。见「交叉溶解的合成陷阱」。 |
| `scan_compliance.py` | 合规词扫描，**两路分开标注**：① 字幕（静态取 SUBS，**用户稿件不擅改，仅提示**）② 画面文案（驱动 Chrome 渲染后读**实际可见文本**，**必须改**）。发布前必跑 + `--selftest`（往 body 注入「扫码」必须被抓到）。**旧版只扫源码 `innerHTML` 模板串 → 画面文案写在数据字面量里时一个字都扫不到却报「通过」**，见「假绿灯」一节。`--static` 可在无 node 环境只扫字幕（但画面文案就没验）。退出码 0/1/2/3/4。 |
| `probe_cards.cjs` | **主力验收工具（几何 + 明度二合一）**。跑一次出三样：① 卡片类 rect（越界判定 + 供明度脚本消费）② 文本问题 —— 水平被裁（`scrollWidth`）与**竖向被挤出所属卡片** ③ 每个时刻一对截图 A（正常）/ B（只留背景）供「卡片 vs 背景 Δ>0.15」量化。画幅与安全线全部走环境变量（`VIDEO_W/H`、`SAFE_X/SAFE_TOP/SAFE_BOT`）。 |
| `verify_mp4.py` | **从编码后的成片反抽帧**：取样时刻自动取内嵌 SUBS 的**字幕中点**，与渲染前静帧做 PSNR 比对并允许 **±2 帧对齐取最大值**（`-ss` 会差 1 帧，死磕同一帧号会假摔到 14dB），最后拼接触表 + 打 `ffprobe` 规格。**发布前必跑**。 |
| `contact_sheet.py` | 把 `check/t*.png` 拼成联系表整体扫读（找可疑用，判定回原尺寸）。 |
| `icon-library.js` | **内联 SVG 图标库**（21 个线性图标，24×24 viewBox）。含 `ico(name,cls,tone)` 生成函数、三档尺寸（`.ic 44` / `.ni 62` / `.hi 84`）、四套语义变体的完整 CSS，以及**图标语义映射表**。用内联 SVG 而非 emoji/图标字体：零加载、可被 CSS `stroke` 染色、语义变体自动换色。见「图标怎么做」一节。 |
| `diagnose.cjs` | **页面级错误捕获**。`render.cjs` 只报「Waiting failed: `window.__render` 超时」——只说契约没建立，**不告诉你为什么**。本脚本挂 `pageerror`/`console`/`requestfailed` 三个监听，打印真实异常 + 契约状态 + 字体 loaded 情况 + 抽 3 帧看可见镜头。**`__render` 一 timeout 就先跑这个**，别去猜。 |
| `probe_coverage.cjs` | **量各镜头内容占安全区多少 + 横向溢出**，DOM 几何法。内置双向验证（`--selftest`：把字号灌到 10px，反例必须被判「偏空」），**尺子可信再用它的数据**。`--dump` 打印越界元素明细。判据：`<45%` 偏空、`>1px` 越界。 |
| `probe_card.cjs` | **卡片 / 边框体检**。逐卡报「角花深入量 L/R/T/B vs 内容内缩 L/R/T/B → 安全余量」，并列出重叠元素与 px²。内置①角花定位解析器自检（4 种写法，不过就退出码 7）②容器规格指纹比对（同屏不同容器的 border/radius/padding 是否一套语言）。`--url` 可量任意静态页（实验台/反例页），`--dump` 打印计算样式与内容盒。判据：重叠=0 且余量 ≥8px。**它自己也曾给出假通过**（`calc()` 的 background-position 被裸切），所以必须配反例页。 |
| `shot_page.cjs` | 给任意 HTML 拍全页图（含字体 + 图片等待）。静态页没有 `__render` 契约，用这个而不是 `check.cjs`。`--clip y0 y1` 只取一段。**必须传 `path`** —— 不传只返回 Buffer，零字节落盘后报 ENOENT，完全指不到真因。 |
| `probe_card_selftest.html` | `probe_card.cjs` 的**反例页**（负向对照）：两个故意违规的卡片（inline padding 绕开约束 / 角花放大到 60px）。判据是**必须被抓到并退出码 6**；若在这里报「无重叠」说明尺子坏了。 |
| `card_lab.html` + `card-system.css` | **卡片实验台**。整页列出所有边框档位、角花档位、语义色、排行条、真实用例复刻，供用户在改版前一次性评审规格。`card-system.css` 是**单一真源**：正片内联它、实验台 link 它，改一处两边同时变 —— 实验台不是「另做一套」，它就是正片的样式。 |

## 画幅：竖屏 9:16 与横版 16:9

**默认竖屏 1080×1920**（视频号 / 抖音竖版信息流）。
**横版 1920×1080** 用于官网嵌入、B站 / 公众号内嵌、会议投屏、PPT 补充素材。

渲染时只切环境变量，**源码一行都不用改**：

```bash
VIDEO_W=1920 VIDEO_H=1080 node render.cjs     # 横版
node render.cjs                               # 竖版（默认）
```

### 两套画幅的版式参数

| 维度 | 竖屏 1080×1920 | 横版 1920×1080 |
|---|---|---|
| 安全区 | 上 96 / 下 320（留给字幕）/ 左右 0 | 上 62 / 下 76 / **左右各 96** |
| 主标题 | 96–132px | 132–176px |
| 正文 / 标签 | 34–44px | 38–52px |
| **单个卡片最大高度** | 画幅高的 ~78% | **≤ 62%** ← 最容易忘 |
| 元素排布 | 纵向单列 | 横向 2–4 列，或 1 大 2 小扇开 |
| 底部字幕 | 居中，2 行 | 居中，1–2 行（横向更长，别整段铺满整行） |
| 章节轨 | 底部居中 | 底部居中短条，或左上角 chip |
| **单卡 `--card-w`** | 560px（约占画幅宽 52%） | 470px（约占画幅宽 24.5%） |

**把竖屏版式原样搬到横屏 = 上下大片空白。** 横屏纵向只有 1080px，卡片一高就顶满画幅、失去呼吸。
正确解法是**把内容横向摊开**（2–4 列 / 卡片组 / 左图右文），不是把竖屏的卡片放大。

### 卡片必须「画幅无关」

所有卡片尺寸走 **`--w` 单参数**派生，绝不写死 px。
再往上一层设一个 **`--card-w` 总入口**，换画幅只改它一个值：

```css
:root{ --W:1920px; --H:1080px; --card-w:470px; }   /* 换画幅改这三个 */
.card{
  --w:var(--card-w);
  width:var(--w); height:calc(var(--w)*1.81);
  border-radius:calc(var(--w)*.068); padding:calc(var(--w)*.10);
}
.card .title{ font-size:calc(var(--w)*.80/var(--n,4)); }   /* --n = 标题字数 */
/* 派生卡（组里的小卡、横排矮卡）也从 --card-w 派生，不要另写死值 */
.group .side{ --w:calc(var(--card-w) * .745); }
.dcard     { --w:calc(var(--card-w) * .723); }
```

同一套卡片，竖屏里 `--card-w:560`、横屏里 `--card-w:470`，视觉密度自动一致。
可直接复制 `assets/card-library.html` —— 一页里同时给了横竖两种画幅的四种卡片形态。

### ⚠️ 从竖版派生横版工程：最容易漏的是「脚本里的视口」

`index.html` 的画幅好改（`--W/--H` + 安全区 padding），
但**渲染与质检脚本里的字面量必须同步改，漏一个就会用错的视口干活**：

| 文件 | 必改项 |
|---|---|
| `render.cjs` | `ROOT`、`setViewport({width,height})`、截图 `clip` |
| `check.cjs` | `setViewport` |
| `probe.cjs` | `setViewport`、`clip`、**越界判据的横竖方向** |

**单点定义，别散落字面量**：

```js
const VW = +(process.env.VIDEO_W || 1080);
const VH = +(process.env.VIDEO_H || 1920);
await page.setViewport({ width: VW, height: VH, deviceScaleFactor: 1 });
await page.screenshot({ clip: { x: 0, y: 0, width: VW, height: VH } });
```

**实测的两个翻车**：
① `check.cjs` 的 `clip` 已用 `VIDEO_W/H`、`setViewport` 却还写死竖版 →
视口 1080 宽 / clip 1920 宽，puppeteer 直接报 `clip area is outside of the viewport`。
② `probe.cjs` 更隐蔽：`VW/VH` **压根没定义**（一跑就 ReferenceError），
而越界判据还留着竖版的 `x<70 || x+w>1010 || y<60 || y+h>1580` ——
横版下**每个元素都会报越界**，等于这项检查直接废掉。

**第三轮翻车（2026-10-08，后加的那批工具又踩了一遍）**：`probe_coverage.cjs` /
`diagnose.cjs` / `probe_card.cjs` 是后来补的，加的时候没跟着这张清单走：

| 症状 | 根因 |
|---|---|
| `probe_coverage.cjs` 报 `ERR_FILE_NOT_FOUND .../assets/index.html` | `ROOT = __dirname`，没读 `VIDEO_ROOT` → 横版工程的页根本打不开 |
| 就算打开了也不可信 | `SAFE_TOP/BOT/X/X1` 写死竖版 196/1468/64/1016 → 横版内容（x 能到 1810）**全被误判成横向溢出** |
| `diagnose.cjs` 传绝对路径也报「文件不存在」 | `path.join(ROOT, 'C:/x/y')` 在 Windows 上拼成 `assets\C:\x\y`，看不出是拼接方式的问题 |
| `diagnose.cjs` 抽帧恒显示「可见镜头 []」 | 只认 inline `style.display==='block'`，而主线用的是 `visibility`+`opacity` |

→ **新增任何一个检查工具，先过这张自查表**：

1. 读 `VIDEO_ROOT`（别锚 `__dirname`），路径解析用 `path.isAbsolute()` 分流；
2. 视口与安全区走 `VIDEO_W/H`，**默认值按画幅派生**（横版安全区与竖版不是一套数）；
3. 不要假设显隐写法（`display` 与 `visibility`+`opacity` 两种都要认）；
4. **镜头表要有回退链**：`window.__shots` → DOM 的 `.shot[data-st]`。老工程没有 `__shots`
   契约，若把 `!shots.length` 也当作「静态页」判据，会让动态页不调 `__render`、
   停在初始态 → **量到 0 张卡却报「✓ 无角花压内容」**（工具要防的假通过，自己又犯了一次）；
5. **「量到 0 个对象」必须报错，不能报通过**。工具最容易骗人的不是算错，而是
   **什么都没量到却输出 ✓**。`probe_card.cjs` 现在 `allCards.length === 0` 时 `exit 6` 并给三条排查线索。

### ⚠️ 局部重渲（只重跑改动的几秒）时，画幅默认值必须与 render.cjs 一致

改一处版式不必重渲全片 —— 写个 `rerender_range.cjs` 只重跑受影响的帧号区间，
其余帧沿用磁盘上的旧图，再重新编码即可（全片 7049 帧里改 331 帧，35 分钟压到 2 分钟）。

现成实现见 `assets/rerender_range.cjs`，**双向验证过**：

```bash
node rerender_range.cjs --check-size              # 只跑尺寸守卫自检
node rerender_range.cjs 41.7 51.0                 # 重跑 41.7s–51.0s 内的帧 + 重新编码
node rerender_range.cjs 1251 1512 --frames        # 直接给帧号，省掉秒↔帧换算
node rerender_range.cjs 41.7 51.0 --noenc         # 只截图不编码
```

> **改这个脚本时先做语法自检**：`node --check rerender_range.cjs`
> 实测加 `--frames` 分支时漏改了一处旧变量引用（`b` 改成 `i1/FPS` 时漏了一行），
> 每段都跑到一半才 `ReferenceError`。**语法自检 1 秒，能省掉 5 次 Chrome 启动**。
>
> ⚠️ `node -c "new Function(require('fs').readFileSync(...))"` **不能用** ——
> Node 会把整串当成模块名，报 `Cannot find module`。用 `node --check <file>`。

**它内建四道守卫**（每道都是一次真实事故）：

| 守卫 | 作用 | 触发时的退出码 |
|---|---|---|
| 重渲**前**逐帧查尺寸 | 现有帧与 `VIDEO_W/H` 不符就中止 | 4 |
| 重渲**后**再查一次 | 这批帧是本次新写的，视口配错要在这里拦住 | 4 |
| 首帧单独提示 | 直接指出「大概率是本脚本画幅默认值与 render.cjs 不同」 | 4 |
| **落盘守卫** | 比对首帧 mtime，帧没被改写就中止 | 5 |

⚠️ **落盘守卫是必须的，不是可选的**：`page.screenshot()` **不传 `path` 时只返回 Buffer，
一个字节都不写盘**。症状极其恶劣：

> 跑完 1054 帧、打印「重渲完成」、尺寸守卫全绿、耗时正常 ——
> **但零帧落盘**。旧帧继续留在盘上，编码出来的成片完全正常，
> 只有内容还是上一版的。我是靠「帧 mtime 还是上一次全片渲染的时间」发现的，
> ��� SKILL.md 之前反复强调的「源码 MD5 == 备份 MD5」同一类问题：
> **改动没进成片，且没有任何一处报错。**

```js
// ✗ 只返回 Buffer，零字节落盘，看起来完全成功
await page.screenshot({ type: 'png', clip: {...} });
// ✓ 必须显式给 path
const file = path.join(FRAMES, 'f-' + String(i).padStart(5, '0') + '.png');
await page.screenshot({ type: 'png', path: file, clip: { x: 0, y: 0, width: W, height: H } });
```

```js
// 落盘守卫：渲完比 mtime
const mtimeBefore = fs.statSync(probeFile).mtimeMs;
for (...) { /* 截图到 probeFile */ }
const mtimeAfter = fs.statSync(probeFile).mtimeMs;
if (mtimeAfter <= mtimeBefore) { log('✗ 帧没有被改写'); process.exit(5); }
```

尺寸检查只读 PNG 头部 24 字节（不解码整图），6874 帧秒级完成 —— 用 PIL 逐张 open 会慢几十倍。

**怎么算区间**（比凭感觉挑范围可靠）：

```python
# 只重跑受影响的字幕/元素所覆盖的帧，边界要留 PAD
FPS, PAD = 30, 0.20
i0 = max(0, int((start - PAD) * FPS))
i1 = int((end + PAD) * FPS)
```

- **帧号 = `round(t*fps)`，从 0 开始**（`render.cjs` 写的是 `f-00000.png`）。**不要 +1**。
- 边界留 `PAD`：字幕切换用 `if(idx!==lastSub)` 判定，**切换那一帧写的是新句子**，
  旧句子的最后一帧也必须一起重渲，否则会看到两句话重叠。
- 间隔小的多个区间要**合并**（`< 1s` 合成一段），省掉重复启动 Chrome 的开销。
- 实测：7 条字幕分散在 0–145s，合并成 5 段共 1054 帧，
  **50 分钟全片重渲 → 8 分钟局部重渲**。

> **局部重渲后必须重跑 `verify_mp4.py`**。改过源码就意味着源码 MD5 变了，
> 「源码 MD5 == 备份 MD5」那条一致性校验正是为这种情况准备的。
>
> **更要紧的是：反抽帧看的那一帧，必须落在你重渲过的区间里。**
> 我第一轮修完字幕 bug、重渲完、重新编码、验收全绿（13 镜 PSNR 43–45 dB）——
> 但验收图里 `<br>` 还在。原因是那一帧的 mtime 是上一次全片渲染的，
> **落盘根本没发生**，而 PSNR 恰恰因为「渲染帧与成片完全一致」给出了漂亮的 45 dB。
>
> **这是 PSNR 判据的一个盲区**：它衡量的是「成片 vs 当前帧序列」的一致性，
> **不衡量「帧序列 vs 你想要的画面」**。所以它必须配一个「帧确实被改写了」的前置守卫，
> 以及「反抽帧要看修改过的那个时刻」的人工确认。

**但它会踩一个非常隐蔽的坑**：如果它的画幅默认值写成了另一种画幅
（照抄竖版模板 → `VIDEO_W || 1080`），这 331 帧会以**竖版尺寸**写进横版序列。
ffmpeg 读 image2 序列时按**首帧尺寸**统一缩放 —— **整片静默变成 1080×1920**，
画面看着「没问题」（内容被等比缩放了），只有规格是错的。
本次是靠 PSNR 从 41 dB 掉到 33 dB 才察觉。

两道守卫都要有：
1. 重渲脚本的画幅默认值**与 render.cjs 完全一致**；
2. 编码 / 反抽帧前**逐帧检查尺寸**（见 `assets/verify_mp4.py`，尺寸不符直接 `exit 4`）。

### 越界判据：用「视觉安全线」，不要用 `.stage` 的 padding 框

横版 1080 里，顶部 HUD（栏目条 / logo）和底部字幕框都是**固定定位**的。
判据按它们的**实测外沿**算，别照抄 padding：

```
HUD 文字底 ≈ 98px · 字幕框顶 ≈ 933px  →  内容安全带 y ∈ [122, 924]
```

用 padding 框（150 / 875）太严：内容只轻微溢出框、但离 HUD 和字幕都还差 30px 的镜头
会被误报成越界，逼你去做没必要的压扁。

**两套口径并存，别混用**：

| 口径 | 数值（横版） | 回答什么问题 | 用在哪 |
|---|---|---|---|
| **视觉安全线** | y ∈ [122, 924] | 会不会真撞到 HUD / 压住字幕 | 卡发布 |
| `.stage` 内容带（padding 框） | y ∈ [150, 875] | 内容占设计带的多少 | 诊断「偏空 / 过挤」 |

`probe_coverage.cjs` 默认用后者（它答的是「覆盖率」，用设计带才自洽），
所以会报「⚠超出内容带 Npx」——**看到这个先别改版式**，换口径复核：
`SAFE_TOP=122 SAFE_BOT=924` 再跑一次。
实测：横版 13 镜里 4 镜「超出内容带」4–14px，换视觉安全线后全部 91–94%，完全正常。

### 横版真正的紧约束是「内容总高」，不是宽度

竖版那套版式（大标题 + 主卡 + 三张数字卡 + 结论条）搬到横版，
一镜内容轻松到 **960px**，而可用高只有 725px（1080 − 上 150 − 下 205）。
症状：`justify-content:center` 把溢出**上下平分** → 顶部撞 HUD、底部压字幕。

**先量再改**：把该镜所有可见元素的 y 区间并集算出来（`getBoundingClientRect`）。
**要压就压「最高的那一列」**，而且用**局部类**，别动全局节奏：

```css
.stage.tight{gap:16px}             /* 只给这一镜 */
.trio .ncard{padding:10px 18px}
.trio .ncard .num{font-size:70px}  /* 三卡叠放时数字必须比单卡小一号 */
```

实测：某镜右列三张 112px 数字卡把行高顶到 736px。数字 112→70、内边距 24→10、
间距 16→8 后右列降到 511px，行高改由**主卡**（530px）决定，整镜 964 → 716px，收进安全区。

### 两行标签的坐标轴：让相邻标签「交替上下」

一根轴上钉 7 个数值，标签必然重叠。把 `.pin` 拆成 `.up` / `.down` 两个变体，
**相邻两钉一定不在同一层**，从根上消除重叠：

```css
.axwrap{position:relative;height:204px}      /* = 2×单侧内容高(96) + 轴线(10) */
.axwrap .pin.up  {bottom:calc(100% - 97px)}  /* 底边落在轴线上 */
.axwrap .pin.down{top:107px}                 /* 顶边落在轴线下 */
```

⚠ 钉的 DOM 顺序要跟着翻：`.up` 写 `<span>标签</span><b>数值</b><i></i>`，
`.down` 写 `<i></i><b>数值</b><span>标签</span>` —— `i` 是那根竖直小刻度，必须紧贴轴线。

⚠ 轴上的数值位置**必须与刻度线性对应**（刻度下限 → 0%、上限 → 100%），
否则标签与刻度互相打架。落点算 `(值 − 刻度下限) / 量程`，最多再做 ±0.5~1% 的避让微调。

### 对比条：轨道定宽，否则两条不可比

`flex:1` 的轨道在两条文案长短不同时**宽度也不同** ——
观众会把「条的长度」读成比例，两条轨道不等宽就直接误导。
定宽轨道 + 数值移到条外，两个问题一次解决：

```css
.cmpr .track{flex:0 0 720px}                  /* 两条同宽才可比 */
.cmpr .val{flex:0 0 auto;white-space:nowrap}  /* 数值在条外，短条也压不掉它 */
```

顺带：条内原本用来放数值的 `padding-left` 记得删掉，否则短条里会留一块空洞。

## 步骤

### 1. 探测环境（不要假设）

```bash
command -v ffmpeg
ls "/c/Program Files/Google/Chrome/Application/chrome.exe"
```

- Chrome 常见位置：`C:\Program Files\Google\Chrome\Application\chrome.exe`、`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`。Edge 是 Chromium 内核，没有 Chrome 时可直接用 Edge 顶替 `executablePath`。
- ffmpeg 常见位置：`C:\Users\<用户>\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*/ffmpeg-*/bin/ffmpeg.exe`。
- 不要用 `npx playwright install` 下载 Chromium —— 本机已有 Chrome，走 `puppeteer-core` 最省事。

### 2. 装依赖（隔离目录，不污染用户环境）

```bash
NPMDIR="C:/Users/<用户>/.workbuddy/binaries/node/versions/<版本>"
cd "/c/Users/<用户>/.workbuddy/binaries/node/workspace" \
  && "$NPMDIR/node.exe" "$NPMDIR/node_modules/npm/bin/npm-cli.js" install puppeteer-core --no-audit --no-fund
```

运行脚本时设 `NODE_PATH` 指向该 workspace 的 `node_modules`。
**注意**：托管 node 目录里没有 `npm` 可执行文件，必须用 `node.exe <npm-cli.js>` 的方式调。

### 3. 写 index.html

见 `assets/index-template.html`。必须遵守的契约：

```js
window.__render = render;   // (t: seconds) => void，幂等：对任意 t 调用都能还原该时刻画面
window.__duration = DUR;    // 总时长（秒）
window.__fps = FPS;
```

关键写法：

- **镜头用绝对定位 `.shot` 叠在一起**，`render(t)` 里只 `display:block/none` 当前可见的 1–2 个。不要用 CSS `animation`/`transition` —— 逐帧截图下它们不受控（截图时刻与动画时间轴对不齐）。
- **每个镜头一个 `fn(el, lt, t)`**，`lt = t - 镜头起始时间`，所有动画都用 `lt` 算，实现帧精确可重放。
- 缓动函数自己写（`ease`、`ease4`、`clamp`、`lerp`），不要依赖库。
- **改 DOM 只在值真的变了才改**（如字幕：`if(idx!==lastIdx)`），否则每帧重排会拖慢渲染。
- 字幕用硬字幕烧进画面（一个固定在底部的 `#sub`），不要另做 srt 软字幕。
- **总时长 = SRT 最后一句的结束时间**；口播节奏按 4 字/秒 反算，超出就删字不删镜。
- **字幕表 `const SUBS=[[start,end,"文本"],...]` 直接内嵌在正片 HTML 里**，
  而不是另存一份 `.srt`。好处：出片只需一个文件。
  代价：**写抽帧 / 预览脚本时别去磁盘找 `.srt`**（会找不到，因此返工过一次），
  直接从 HTML 解析：

  ```python
  i = src.find("const SUBS=["); j = src.find("];", i)
  subs = [( float(a), float(b), txt ) for a, b, txt in
          re.findall(r'\[\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*"((?:[^"\\]|\\.)*)"\s*\]',
                     src[i:j])]
  ```

  解析完必须断言条数（`assert len(subs) > 20`），否则正则失配会静默抽 0 帧。
  抽帧时间点取**每条字幕的中点** `start + (end-start)*0.5`，不凭印象取整。

### 4. 【最重要】性能规则 —— 不遵守会慢 4–5 倍

headless Chrome 是**软件光栅化、无 GPU 加速**。以下每条都是实测结论（同一页 120 帧散布采样）：

| 写法 | s/帧 |
|---|---|
| 纯色底 + 独立分层的光晕/暗角/网格 | **0.086** |
| 让 `.dark` 元素自己扛 3 层全屏径向渐变（底色+双光晕） | 0.388 |
| 把渐变背景烘焙成 bg.png 再 cover（但仍每镜头一份、含动态网格） | 0.355 |
| 加 `will-change` 强制分层 | 0.38 |
| 光晕/暗角拆成独立 div（各自 `will-change:transform`），底元素保持纯色 | 0.23 |
| **背景整体提升为全局单层 `#bg`（`#root` 的兄弟节点），底图含辉光/暗角/星点全部烘焙进一张 PNG** | **0.128** ← 最佳 |

**硬规则：**

1. **【首选】背景不要放进镜头里，提升成全局单层。** 在 `<body>` 下放一个 `#bg` 作为 `#root` 的**兄弟节点**（不是子节点），里面只有「一张烘焙好的底图」+「一个动态网格」。镜头内容全部放在 `#root` 里。这样：
   - 镜头之间的 opacity 交叉淡入**完全不会触及背景层**（同级、无父子关系）；
   - 底图上的辉光/暗角/星点（原本最贵的三样）烘焙成一张 PNG，每帧只做 blit；
   - 实测 0.25 → **0.128 s/帧**，全片 4438 帧从 18.5 分钟降到 9.5 分钟。
   镜头侧收尾很省事：让 `buildDark()` 只返回内容容器，把原来逐镜头的网格调用统一挪到 `render(t)` 里驱动一次（用一个 `const GRID_STUB={style:{}}` 返回给旧调用点，可零改动兼容既有的 `d.g.style.transform=...`）。
2. **绝不让同一个元素既扛全屏渐变、又逐帧变化。** 全屏渐变放元素自身 `background` 上会每帧重算。
3. **内容容器必须与背景层分离**，且**必须显式写 `color:#fff`**。背景层拆出去后内容不再继承原文字色，会掉成黑色（踩过）。
4. **底图用 Pillow 烘焙，不要用 Chrome 截屏烘焙。** 径向渐变 + 暗角 + 星点全部能在 Python 里几行画出来（`ImageDraw.ellipse` + `GaussianBlur` + `ImageChops.multiply` 做暗角），比启一个 Chrome 再截图省事得多。
5. **不要对 `.shot` 整体做 `transform: scale()` 入场推进** —— 会把背景层一起逐帧重栅格化。要转场就用 `opacity` 淡入，或只对内容块做缩放。
6. **逐帧动网格不要改 `background-position`**，改成 `transform:translate3d()`，并按图案周期取模（`translate3d(${(t*13)%38}px, ...)`）—— 周期一致看不出跳变。
   **但速度一定要回头看一遍**：`13px/s` 走完一个 76px 周期只要 1.4 秒，肉眼观感是「网格在闪/抖」，不是「在流动」。背景网格的正确量级是 **0.5–1px/s**（走完一格 60–150 秒），静态看几乎不动。真正提供「呼吸感」的应该是**亮度的缓慢起伏**（如 `opacity` 走 `sin` 周期 19s、幅度 ±12%；两层错开半周期形成一涨一落），位移只负责不死板。用户原话：「格子闪烁的太快了，只要微微的动有呼吸感就好」。
7. **慎用 `backdrop-filter: blur()`**，软件光栅化下大片模糊很贵（全屏每帧一次高斯会让全片渲染翻两三倍）。深色卡片用「实色卡面 + 描边 + 多层 box-shadow 环」即可（见下）。**同理慎用「整层压暗垫层」来提对比度**：给内容层加 `radial-gradient(rgba(0,0,0,.34)...)` 会连网格骨架一起闷掉 —— 网格 P50 亮度本身只有 3–4，压过头就成糊底。真要用，系数控制在 `.16/.10/.02` 这一档，只做「让线从文字后让开」，别指望它解决对比度。
8. **对比度的正解是「提文字 + 加落影」，不是「压背景」。** 深色底 + 网格的场景下，文字对比度问题 90% 出在文字自身透明度太低。做法：
   - 次级文字（小标题/卡片名/轴标签）透明度 **≥ .88**；`.62` 这类值纸面算下来能过 WCAG，但手机竖屏看一眼就发灰（实测踩过，用户直接截图指出）；
   - 署名/来源这类「品牌资产型小字」提到 **.70** 左右 —— 要看得清，但必须退居背景；
   - 27–30px 的极小字（如章节轨章号）额外放大到 30px 并加 `text-shadow`，小字在网格上最容易糊；
   - 金色渐变字（`background-clip:text`）的落影用三层 `drop-shadow`（`0 0 3px rgba(0,0,0,1)` + `0 5px 18px .95` + `0 2px 5px 1`），单层挡不住穿过来的网格线；
   - 字幕条底色 `.86 → .93`、描边 `.30 → .42`：字幕是「必须一眼读完」的元素，不能只靠底色半透明。
   改的时候按「同一透明度值批量 grep 计数」推进（一次处理 26 处），并写成脚本 + 落盘前校验，比逐处手改可靠。
9. **慎用大半径 `text-shadow` / `box-shadow` 光晕**（如 `0 0 130px`）。想要发光就用小半径（`0 0 28px`）或独立背景光斑。
10. 小面积静态渐变（如 520×470 的图表刻度网）可以接受，但**必须放在变动元素的兄弟节点上**。
11. 别指望 GPU：`--disable-gpu` 开或关实测无差别，headless 一路软件光栅化。

### 5. 测速 —— 必须散布采样

`render.cjs --test --noenc` 会**均匀抽 120 帧覆盖全片**做测速。
**不要只测前 120 帧** —— 前 120 帧通常落在封面/章节卡段，那里的元素最简单，会给出虚高的速度结论（踩过：只测前段得 0.12s/帧，实际全片 0.47s/帧）。

判据：`s/帧 × 总帧数` 是否可接受。0.25s/帧 → 4438 帧 ≈ 18.5 分钟，可接受。

### 6. 质检 —— 先抽帧，再全渲

```bash
node check.cjs 1.5 10 44 74 97 145     # 定点抽帧到 check/
```

- **改任何视觉都先跑 check**，不要直接全片重渲。
- 抽帧要覆盖**每类镜头至少一个**，不要只抽 2–3 张就宣布通过。
- 镜头有动画时，注意抽到的可能是**动画中间态**（元素还没出来，看着像"空场"其实不是 bug）。**要抽动画完成时刻**（起始时间 + 动画时长 + 余量）才是真状态。
- 全片渲完后，用 ffmpeg 从**成片 mp4** 再抽一轮帧（`-ss <秒> -frames:v 1`）—— 验证编码后的实际画面，而不是只信源页面。

### 7. 编码

```bash
ffmpeg -y -framerate 30 -i frames/f-%05d.png \
  -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p \
  -r 30 -movflags +faststart out_silent.mp4
```

静音成片（画面+烧录字幕），配音另做后 `-i voice.mp3 -c:v copy` 混流。

### 8. 交付

- 版本化命名（`..._v1浅色版.mp4` / `_v2深色版.mp4`），旧版保留对照，别覆盖。
- 结束时清理调试噪音（spread_*.log / speedtest*.log / test.mp4 / 废弃的烘焙资源），但**保留** `render.cjs`、`check.cjs`、`index.html`（下一版还要用）。

## 【高频需求】照着参考视频重做视觉

用户常丢一个参考视频过来，说「参考它的背景 / 卡片 / 文字样式」。**不要靠肉眼估色**，抽帧后用 Pillow 采样出真实规格再落地。

### 逆向流程

```bash
# 1. 抽帧（-ss 放在 -i 前面才是快速定位；放到后面是逐帧解码，慢得多）
ffmpeg -ss <秒> -i ref.mp4 -frames:v 1 -y ref_frames/r_<n>.png     # 每 3-4 秒一张
```
> Windows 上 ffmpeg 写不进 `/tmp`，输出目录要用工程内路径。

```python
# 2. 采样规格（Pillow）。要量的四样：
#    底色 / 网格（间距 + 线亮度）/ 辉光（逐行均值衰减曲线）/ 卡片（边框层次 + 卡面色）
#    网格间距：取一段干净暗区做纵向亮度剖面，取峰值的 55% 为阈值找亮线，算相邻中心距
#    辉光强度：逐行取全行均值，得到"参考的最强叠加值"，生成底图时按这个值标定
```

**卡片规格必量的三项**（决定卡片走哪条路线，量错整套都白做）：

```python
# ① 卡面 vs 页面背景的明度 —— 决定「抬亮卡面」还是「让卡发光」
import colorsys
def V(rgb): return colorsys.rgb_to_hsv(*[x/255 for x in rgb])[2]
V(卡内)  vs  V(背景)     # 卡面 > 背景 + 0.15 → 路线① 抬亮卡面
                        # 卡面 ≤ 背景        → 路线② 深黑面 + 边框发光（更高级）
# ② 金色笔画的实际 RGB（不是猜色号）
pixels = a[(a[:,:,0]>200) & (a[:,:,1]>180) & (a[:,:,2]<180)]
pixels.mean(0)          # 实测 (225,206,145) —— 暖白金，不是饱和黄
# ③ 网格线亮度范围（卡外干净区的逐行 min/max）
```

**实测样本（2026-10，某 1080×1920 教育类参考片）**：

| 项 | 实测值 | 结论 |
|---|---|---|
| 卡面明度 | V = **0.008 – 0.024** | 比背景还暗 |
| 页面背景明度 | V = **0.043 – 0.047** | — |
| 金色笔画 | RGB **(225, 206, 145)** | 暖白金 |
| 网格线亮度 | **1 – 39** | 很暗但清晰 |

→ 卡面比背景暗 = **必须走路线②**（深黑面 + 断角金线 + 硬边厚度），
**不要照搬「抬亮卡面到背景+0.15」那条**。这就是"看着不像，但量化一看确实更高级"的原因：

```css
.card{
  background-color:#0A0908;             /* 卡面几乎纯黑 */
  border-radius:20px;
  background-image:
    radial-gradient(120% 90% at 50% 8%,rgba(255,242,206,.070) 0%,rgba(255,255,255,0) 62%),
    repeating-linear-gradient(118deg,rgba(255,255,255,.026) 0 1px,transparent 1px 13px),
    linear-gradient(168deg,#121110 0%,#0B0A09 52%,#080807 100%);
  /* 硬边厚度：右下偏移的实心阴影（列表靠前的绘制在上） */
  box-shadow:7px 8px 0 0 rgba(214,190,120,.34),
             9px 10px 0 0 #100E0B,
             14px 16px 0 0 rgba(0,0,0,.86),
             0 18px 44px rgba(0,0,0,.60),
             inset 0 1px 0 rgba(255,242,206,.20);}
/* 四角断角金线：8 条短线段拼出来，不是完整闭合的框 */
.card::before{content:'';position:absolute;inset:0;border-radius:20px;
  background-image:repeating-linear-gradient(/* 8 条… */);
  background-size:44px 2px,2px 44px, /* …×4 组… */;
  background-position:1px 1px,1px 1px,calc(100% - 45px) 1px, /* … */;}
```

**为什么断角线比闭合框高级**：闭合框把卡片"关"起来，像表格；
四角断开的短线只做**角部提点**，卡片的边界感仍由明度与厚度提供，呼吸感更强。

⚠ 断角线有个必查项：**卡高 < 约 240px 时会侵入内容**（见第 ⑧ 节 8.10）。

### 先出分镜图，别直接全片重渲

当用户是**在评审视觉方向**（换风格、大改版、说"先把样式改好"）时，**不要直接渲染全片** —— 全片动辄 10 分钟渲染，方向被否就是白干。

做法：主工程旁建一个 `v5_proto.html`，把要评审的几类镜头各写一个静态版本（封面 / 章节卡 / 卡片并列 / 大数字 / 榜单），用 URL 参数切换：

```js
const qs=new URLSearchParams(location.search);
const which=parseInt(qs.get('shot')||'0',10);
const gridT=parseFloat(qs.get('gt')||'0');   // 网格另一个相位，证明「网格能动」
shots.forEach((s,i)=>{ s.wrap.style.display=(i===which)?'block':'none'; });
```
```bash
node shoot_v5.cjs   # 循环 goto(base+'?shot='+i+'&gt='+i*11) 各截一张
```
- 分镜图存成 `分镜图_v5/01_封面.png …`，**用 `present_files` 一次性交付整个批次**。
- 附一张**参考片 vs 新版**的上下拼接对比图，说服力远高于单看新版。
- 用 `gt`（网格相位）参数在同一张分镜里就证明了「网格可动」，用户不用脑补。

### ⚠️ 原型 ≠ 正片：每条修改都要在正片文件里复核一次

**这是最容易漏、后果最直接的一条。** 分镜原型（`v5_proto.html`）和生产文件（`index.html`）是**两份独立文件**。用户评审时提的修改，如果只改在原型上，正片里那条旧元素会一直活到成片里 —— 而且渲染不会报任何错。

真实事故：用户说「右上角的数字没看懂，不要保留」。我在原型里删掉了时间码，
但正片 `index.html` 里 `add(...)` 还在渲染 `.chapct` 元素，成片右上角**照旧显示时间码**，
一直到从成片反抽帧复核时才发现。等于用户提的意见被整条漏掉。

**防漏流程（每次用户提修改都走一遍）：**

1. 用户提的每一条修改，**写成一个 checklist**，逐条对照**正片文件**，不是原型文件。
2. 在正片里 `grep` 一遍关键词确认，例：
   ```bash
   grep -n "chapct\|时间码\|壹\|贰" index.html     # 逐条确认真的没了
   ```
3. 把修改写成**带断言的补丁脚本**（`fix_*.py`），落盘前做完整性校验，
   校验不过就 `raise` 不写盘 —— 别用 sed 一把梭：
   ```python
   def sub(old, new, tag, count=1):
       n = html.count(old)
       assert n == count, f'[{tag}] 期望 {count} 处，实际 {n} 处 —— 已中止，不写盘'
       html = html.replace(old, new)
   # 落盘前校验清单（示例）
   checks = [
       ('时间码渲染已移除', html.count("appendChild(el('div','chapct'") == 0),
       ('镜头数未变',       html.count('st.innerHTML=') == orig.count('st.innerHTML=')),
   ]
   if any(not ok for _, ok in checks): sys.exit(1)   # 不写盘
   ```
4. **改动结构后必须重抽静帧复核**，抽帧脚本要和正式渲染走同一条 `window.__render(t)` 路径。

**另一条同类陷阱：同一套视觉语言分散在多个组件里，改一处要全局扫。**
例：章节编号从汉字「壹贰叁肆伍」改成数字「01–05」时，真正用它的有 3 个地方 ——
章节转场卡、封面五小卡、底部常驻章节轨。只改章节卡就会留下两套编号并存的破绽。
判断方法：改之前先 `grep` 一遍要废弃的那个值，把所有命中点列出来逐一看。

### 三个可直接复用的签名样式

**① 花字标题（中文综艺字）** —— 白填充 + 亮色粗描边 + 深色外圈

```css
.hz{color:#fff;
  -webkit-text-stroke:22px #FAF82B;   /* 描边色 */
  paint-order:stroke fill;            /* 关键：填充压在描边之上，否则字被描边糊掉 */
  text-shadow:                        /* 关键：八向偏移做最外层的深色圈 */
    8px 0 0 #07080A,-8px 0 0 #07080A,0 8px 0 #07080A,0 -8px 0 #07080A,
    6px 6px 0 #07080A,-6px -6px 0 #07080A,6px -6px 0 #07080A,-6px 6px 0 #07080A;}
```
- **`paint-order:stroke fill` 是这套做法的命门**，缺了它描边会盖住填充，字变成一坨。Chrome 对 HTML 文本支持良好。
- `-webkit-text-stroke` 是**居中描边**（一半在填充内、一半在外）。配 `paint-order` 后填充盖住内侧，**视觉描边宽 ≈ 设定值的一半**，所以取值要给到目标的约 2 倍。
- 分档（按字号给不同描边，粗字形千万别用大描边，会糊）：
  `.hz` 22px / 用于 250–300px 的大数字与大字 · `.hz-m` 14px / 60–130px 标题 · `.hz-s` 9px / 36–60px 结论行
- 描边色当强调色用（黄绿 `#FAF82B`）；**只把一种更醒目的色（如橙 `#FF6B2C`）留给全片 1–2 处最强记忆点**，稀缺才有力度。
- 想改某一小段的描边色，用 `-webkit-text-stroke-color` 覆盖（不是 `-webkit-text-stroke:0`，那样会变成实心块）。

**② 双层描边卡片** —— 外浅灰框 → 深灰间隔 → 亮色内线 → 深灰卡面

```css
.card{
  background:#3B3B3B;                      /* 卡面 */
  border:5px solid #12B8C4;                /* 内层亮线 */
  border-radius:18px;
  box-shadow:
    0 0 0 5px #262626,                     /* 间隔：spread-only 阴影 = 同心环 */
    0 0 0 10px #7E8085,                    /* 外层浅灰框 */
    0 18px 46px rgba(0,0,0,.66);}          /* 投影 */
```
- 用**多层 `0 0 0 Npx` 的 spread-only box-shadow 画同心环**，不用嵌套 div，既好写又对既有 HTML 零侵入（只改 CSS 就能给所有已有卡片换装）。
- **同心环会向外扩张**，所以横向排布的卡片要相应加大 `gap`（否则环会重叠）：环外扩 X px → 卡片间距至少要 > 2X。
- `border-radius:999px` 配 box-shadow 环可以做出「胶囊 + 描边」效果。

**③ 黄绿胶囊副标题** —— 每个内容镜头的固定小标题

```css
.sublabel{display:inline-block;background:#FAF82B;color:#14140A;font-weight:800;
  border-radius:999px;padding:15px 44px;}
```
- 胶囊是**参考视频里最好复制的识别特征**：位置固定、每镜头都出现，一次改完全片气质就对了。
- 注意容器是 `flex-direction:column; align-items:center` 时，胶囊用 `display:inline-block` 会自动收缩到内容宽，不会拉满屏宽。

### 配色分工（三色各司其职，别互相打架）

对标重做时给每个色定死职责，否则画面会花：

| 色 | 职责 | 用在哪 |
|---|---|---|
| 主强调（如黄绿 `#FAF82B`） | 常规强调 | 标题描边 / 副标题胶囊 / 章节序号 / 卡片内数字 |
| 结构色（如青 `#12B8C4`） | 只做结构 | 卡片内描边 / 刻度线 / 章节标签竖条 / 进度轨 |
| 亮点色（如橙 `#FF6B2C`） | 稀缺，1–2 处 | 全片最强的反常识反差（最大数字 / 关键对比） |

语义色（风险红 / 机会绿）保留，但降到与配色同一饱和度，别让它们抢主强调。

### 风格 B：高级金（暗调奢牌感）—— 当用户说「太村」「不够高级」时切这套

上面那套「白填充 + 亮色粗描边」的花字在综艺/知识区很抓眼，但在教育、地产、金融类内容里**用户常直接说它"村"**。此时不要微调，整套换成下面这套。两套是**互斥**的，别混用。

实测参考（一条 1920×1080 的样片）采样结论：

| 元素 | 实测值 |
|---|---|
| 底色 / 四角 | 纯黑 `#000000`，四角 RGB(0,0,0) |
| 网格 | 极暗：区均值 6.3 / P95 = 22 / P99 = 27 / 最大 38（满值 255） |
| 雪点噪点 | **无**。孤立亮点（比邻域均值亮 30+）计数 = 0 |
| 金色字 | 字面均值 RGB(215,215,170)，高光 (255,255,215) —— 是**暖白偏金**，不是饱和黄 |
| 卡片面 | `#0A0A0A` → `#1C1A17` 深炭渐变 |
| 卡片线框 | 1px，`rgba(214,190,120,.58)` |
| 环形进度色 | 暗调绿 `#4FB88A` 系 / 暗调红 `#C0494A` 系（不是高饱和） |

**① 金色渐变字（替掉花字）**

```css
.gold{
  background:linear-gradient(178deg,#FFFDF2 0%,#FFF6CE 26%,#EEDFA0 52%,#D8C078 72%,#C0A85E 100%);
  -webkit-background-clip:text;background-clip:text;
  color:transparent;-webkit-text-fill-color:transparent;
  filter:drop-shadow(0 5px 16px rgba(0,0,0,.9)) drop-shadow(0 2px 4px rgba(0,0,0,.95));}
/* 巨字才加极细金描边；小字号描边会糊成一团 */
.gold-xl{-webkit-text-stroke:.8px rgba(186,158,86,.62);paint-order:stroke fill;}
```
- **必须换成衬线字**：`font-family:"Source Han Serif SC","Noto Serif SC","Songti SC",serif`。雅黑配金色渐变会非常土，衬线是这套风格高级感的一半。
- `color:transparent` + `-webkit-text-fill-color:transparent` **两个都要写**，只写一个在部分 Chrome 版本下会回退成黑字。
- 白色数字（参考片里的大数字）**不要**做金色，保持纯白 + 柔光 `drop-shadow(0 0 26px rgba(255,255,255,.30))`——金白对比才是参考片的层次。
- **想给某处渐变字换一档颜色时，只能写 `background-image`，绝不能写 `background` 简写**。`background` 会把 `background-clip` 一起重置回 `border-box`，而文字本身是 `color:transparent` 看不见的 —— 结果就是画面上凭空出现一块**实心金砖**。踩过一次：本来只想把「几乎没变」换成暖橙金做区分，渲染出来是金色色块。

**② 细金线卡（替掉双层描边卡）**

卡面**必须有斜向细纹**（`repeating-linear-gradient`），纯平渐变会显廉价。四角金线花纹是参考片的签名特征，但**不要用额外 DOM 去画** —— 一部 25 个镜头的成片里卡片有十几处，逐个加 `<i class="corner">` 又慢又容易漏。用 8 条 `background-image` 把四角拼出来，**一个类全站生效**：

```css
.card5{
  position:relative;border-radius:20px;
  border:1px solid rgba(214,190,120,.58);
  background-color:#0E0D0C;
  background-image:
    /* 8 条短线 = 四角 × (横 + 竖)，用 background-size 把渐变缩成短线 */
    linear-gradient(rgba(226,203,138,.72),rgba(226,203,138,.72)),  /* ① TL 横 */
    linear-gradient(rgba(226,203,138,.72),rgba(226,203,138,.72)),  /* ② TL 竖 */
    linear-gradient(rgba(226,203,138,.72),rgba(226,203,138,.72)),  /* ③ TR 横 */
    linear-gradient(rgba(226,203,138,.72),rgba(226,203,138,.72)),  /* ④ TR 竖 */
    linear-gradient(rgba(226,203,138,.72),rgba(226,203,138,.72)),  /* ⑤ BL 横 */
    linear-gradient(rgba(226,203,138,.72),rgba(226,203,138,.72)),  /* ⑥ BL 竖 */
    linear-gradient(rgba(226,203,138,.72),rgba(226,203,138,.72)),  /* ⑦ BR 横 */
    linear-gradient(rgba(226,203,138,.72),rgba(226,203,138,.72)),  /* ⑧ BR 竖 */
    /* 卡面两层：必须排在最后，否则会盖住角线 */
    linear-gradient(150deg,rgba(255,255,255,.055) 0%,rgba(255,255,255,0) 34%),
    linear-gradient(168deg,#1C1A17 0%,#121110 46%,#0A0A0A 100%);
  background-size:
    38px 1.6px,1.6px 38px, 38px 1.6px,1.6px 38px,
    38px 1.6px,1.6px 38px, 38px 1.6px,1.6px 38px,
    100% 100%,100% 100%;
  background-position:
    12px 12px,12px 12px,
    calc(100% - 50px) 12px,calc(100% - 13px) 12px,
    12px calc(100% - 13px),12px calc(100% - 50px),
    calc(100% - 50px) calc(100% - 13px),calc(100% - 13px) calc(100% - 50px),
    0 0,0 0;
  background-repeat:no-repeat;
  box-shadow:0 0 0 1px rgba(0,0,0,.9), 0 0 34px rgba(214,190,120,.13),
             0 26px 60px rgba(0,0,0,.80), inset 0 1px 0 rgba(255,236,180,.10);}
/* 卡内斜向细纹 */
.card5::before{content:'';position:absolute;inset:1px;border-radius:19px;
  background:repeating-linear-gradient(118deg,rgba(255,255,255,.028) 0 1px,transparent 1px 13px);}
/* 内圈细金线 */
.card5::after{content:'';position:absolute;inset:9px;border-radius:12px;
  border:1px solid rgba(196,170,102,.20);}
```

位置换算就看这一条：右上「横线」的左上角 x = `100% - 12px(边距) - 38px(线长)` = `calc(100% - 50px)`；右上「竖线」的 x = `100% - 12px - 1.6px(线宽)` ≈ `calc(100% - 13px)`。下边同理，把 y 换成 `calc(100% - …)`。

- 卡片小于约 **62px** 时角线会互相撞上（12+38+12），小卡片要单独把 `background-size` 的线长缩到 24px 左右。
- 胶囊类（`border-radius:999px`）**不要**带四角花纹，单独定义一个不带角线的类。
- `inset 0 1px 0 rgba(255,236,180,.10)` 是顶部高光内阴影，给卡片「厚度」。

**③ 金色胶囊徽章**（对应风格 A 的黄绿胶囊）

```css
.pillg{display:inline-block;color:#141208;
  background:linear-gradient(180deg,#F2E39C,#D9C173);
  border-radius:999px;padding:11px 34px;}
```

**背景处理（两套风格通用）**

- 网格用**双层错位**做出「瓷砖缝」质感：主网格 + 细网格不同 `background-size` 和不同方向平移速度。
- 网格四周一定要有 `radial-gradient` 暗场收边，让四角回到纯黑 —— 参考片四角是实打实的 RGB(0,0,0)，网格铺满全屏会廉价。
- **不要自己加雪点/星点**。除非参考片里实测确实有，否则它就是「脏」的来源，用户会直接点出来。
- **速度定在「呼吸」量级**：主网格约 `0.9px/s`、细网格反向 `0.6px/s`（周期分别 85s / 63s），再叠一层 `sin` 周期的亮度呼吸（19s、±12%、两层错开半周期）。这是唯一一处「慢了比快了好看」的地方 —— 快 = 闪，慢 = 高级。参考实现：

```js
// render(t) 里，每帧调用一次
const bx=(t*0.9)%76, by=(t*0.62)%76;        // 主网格位移（近静止）
const sx=(-t*0.6)%38, sy=(-t*0.42)%38;      // 细网格反向位移
gridEl.style.transform =`translate3d(${bx.toFixed(3)}px,${by.toFixed(3)}px,0)`;
grid2El.style.transform=`translate3d(${sx.toFixed(3)}px,${sy.toFixed(3)}px,0)`;
// 亮度呼吸才是「有生命」的来源；两层相位差 90°，形成一涨一落
gridEl.style.opacity =(1+0.12*Math.sin(t*2*Math.PI/19)).toFixed(4);
grid2El.style.opacity=(1+0.12*Math.sin(t*2*Math.PI/19+Math.PI*0.5)).toFixed(4);
```

  自检口径：`t=0` 与 `t=1` 的位移差应在 **1px 量级**（若差 10px 以上就是"在闪"）；呼吸值域应落在 `0.88–1.12`。

## 改造已有成片：重定义 class，不要重写镜头

当用户拿一条已经做完的长片（25 个镜头、几百行）说「换个风格」而不是从零做时，正确做法是**只换 CSS 底座，不动镜头结构和时间轴**：

1. **把旧 class 全部重新定义成新外观**，而不是逐个镜头改 HTML。旧片用 `.hz`（花字）/ `.kw`（青边卡）/ `.tag`（胶囊）/ `.bignum`（描边大数字）铺满全片 —— 只要在 CSS 里把这几个类重新定义成「金色渐变字」「细金线卡」，**全片立刻换脸，镜头代码一行都不用动**。25 个镜头里真正需要改 HTML 的通常只有 3–5 处。
2. **只有结构真的变了的地方才动 HTML**：章节卡从「巨型汉字」换成「环形进度 + 数字」、封面字号定档、那些把 `border`/`box-shadow` 直接写在 `style=""` 里的卡片。
3. **批量替换前先备份**：`cp index.html index_v4_backup.html`。出事能立刻回滚重跑，比逐行排查快十倍。
4. **换底座后必须做一次「孤儿 class」扫描** —— 这是最容易漏的一步。用正则把全片 `class=\"...\"` 用到的类名收集起来，取差集找出「CSS 里没有定义、但 HTML 在用的类」。这类元素会**静默退回浏览器默认样式（16px / 继承色）**，在 1080×1920 的竖屏上小到几乎看不见，而且不报任何错。
   真实事故：某次 v4→v5 换 CSS 底座时，一个「增量徽章」类（`+20` / `+18` 这类小数字）整个丢了定义，3 处调用一直吃默认 **16px**，一路带到下一版才被用户截图指出「这些字也太小了根本看不清楚」。同批漏掉的还有一条底部轨道的底条元素。
   扫描脚本见 `assets/scan_orphan_classes.py`；注意把 `rc`/`ttl` 这类**只作 JS 钩子或 SVG 元素**的类名加进白名单。

### 层叠陷阱：金色渐变字上再挂一个设了 color 的类

`background-clip:text` 的金色渐变字，**依赖于 `color:transparent` + `-webkit-text-fill-color:transparent`**。这两个属性和 `background-clip` 一样都是**可继承**的，于是有两类意外：

**① 同类叠加，靠后者赢。** 两个同为单类选择器的规则分别设了 `color`：样式表靠后的那个会赢过前面那个的 `color:transparent` —— `background-clip:text` 随即失效，文字被填成近不透明的暖色、叠在深色渐变底上，最终显出**一片暗灰**（实测：一整行结论句几乎读不出来）。
修法：给共存组合显式补回透明填充。

```css
.concl.hz-s,.concl.gold{color:transparent;-webkit-text-fill-color:transparent;text-shadow:none;}
```

**② 子元素继承到 transparent / text-clip。** 在渐变字里放一个带背景色的 `<span>`（例如给 `≠` 加红色方块），如果不显式重置，会同时踩两个坑：红底被 `background-clip:text` **裁成字形**，而 span 又继承了 `transparent` 填充 —— 结果就是「一块红的，但看不到字」。
修法三条一起上：

```css
.neqbadge{display:inline-block;
  background-clip:border-box;-webkit-background-clip:border-box;  /* 必须重置 */
  background:linear-gradient(178deg,#C8555A,#9E3438);
  color:#FFF4F2;-webkit-text-fill-color:#FFF4F2;}                 /* 必须重置 */
```

**通用自检**：任何「金色类 + 另一个设 color 的类」共存的组合都要人工过一遍。用 `probe_styles.cjs` 打计算样式，看 `color` / `-webkit-text-fill-color` 是否已经是 `transparent`；若被覆盖，`background-clip` 就不会是 `text`。

### 批量改造的三条安全网（每条都是踩出来的）

**① 正则必须落到「元素级」，绝不能用跨元素的宽松匹配。**

下面这种写法会**静默吞掉后面好几个镜头** —— 它要找 `</div></div>`;`，而「卡片容器结束 + 镜头字符串结束」这个形状在**后面每一个镜头**的尾部都成立，`.*?` 会一路吃到那里去。渲染时不会报错，一直到播放到被吃掉的镜头才抛 `Cannot read properties of null`：

```python
# ✗ 危险：S19 之后的 S20~S23 全被吞掉
re.search(r'<div id="s19c">.*?</div>\s*</div>`;', html, re.S)
# ✓ 安全：范围收到单个元素内部（style 属性里不会出现 >，所以 [^>]* 不会越界）
re.search(r'<div style="width:392px;[^>]*>学校分数表</div>', html)
```

**② 落盘前做完整性校验，不过就 `raise SystemExit`，一个字都不要写。**

```python
MUST = ['id="s19f"', 'id="s21a"', 'id="s24c"', 'id="s25card"',
        'chapRing(1,', 'chapRing(5,', 'const shots=[]', 'window.__render']
missing = [k for k in MUST if k not in html]
if missing: raise SystemExit(f'结构缺失 {missing}，已中止，未写盘')
if html.count('st.innerHTML=') != 25: raise SystemExit('镜头数不对')
```

`st.innerHTML=` 的出现次数 = 镜头数，这一条最能直接抓出「被吞掉 N 个镜头」。

**③ 改完先抽静帧，别直接上全片。** 全片渲染十几分钟，抽 20 帧只要二十秒。用 `window.__render(t)` 逐点抽帧（与正式渲染走同一条路径，所以看到的就是成片那一帧），覆盖每一类镜头，确认没问题再全量。

### 章节卡：环形进度 + 环内数字（可直接复用）

```js
function chapRing(n, title){          // n = 第几章（1..5）
  const R=198, C=2*Math.PI*R;
  let dots='';
  for(let i=0;i<5;i++){
    const a=(-90+i*72)*Math.PI/180;              // 12 点起，顺时针均分
    const x=(228+R*Math.cos(a)).toFixed(1), y=(228+R*Math.sin(a)).toFixed(1);
    const on=(i<n);                              // 已过的章节点亮
    dots+=`<circle cx="${x}" cy="${y}" r="${on?9:7}" fill="${on?'#F2E0A0':'#0A0A0A'}"
      stroke="rgba(214,190,120,${on?1:.45})" stroke-width="${on?0:2}"/>`;
  }
  return `<div style="position:relative;width:456px;height:456px;">
    <svg width="456" height="456" style="transform:rotate(-90deg);">
      <circle cx="228" cy="228" r="198" fill="none" stroke="rgba(255,255,255,.105)" stroke-width="5"/>
      <circle cx="228" cy="228" r="198" fill="none" stroke="rgba(216,192,122,.92)" stroke-width="7"
        stroke-linecap="round" stroke-dasharray="${C.toFixed(0)}"
        stroke-dashoffset="${(C*(1-n/5)).toFixed(0)}"/>
    </svg>
    <svg width="456" height="456" style="position:absolute;left:0;top:0;">${dots}</svg>
    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;">
      <div class="gold gold-xl" style="font-size:275px;font-weight:900;line-height:1;letter-spacing:9px;
        text-indent:9px;font-variant-numeric:lining-nums tabular-nums;transform:translateY(-3px);">0${n}</div>
    </div>
  </div>
  <div style="height:56px;"></div>
  <div class="gold" style="font-size:64px;font-weight:900;letter-spacing:3px;line-height:1.5;
    text-align:center;">${title}</div>`;
}
```

- 环内**别放汉字**（`壹`），放数字 `01`–`05` 更现代；但数字墨量小，要放大到约 **1.5 倍**（275px）+ 900 字重才追得回视觉重量。
- 环底线 alpha 给 `.105`；低于 `.09` 看不到完整的圆，弧线会像一根孤立的斜撇，不像进度环。
- 「5 个节点 + 点亮已过节点」比单纯靠弧长好读得多，两者一起用。
- 环内已经有编号了，环下**不要再写一遍 `01 / 05`** —— 那是重复信息，删掉版面立刻干净。

## 字体：用 @font-face 自带，不要依赖系统已装

**先查系统有没有，没有就下载字体文件放进工程用 `@font-face` 引** —— 这比让用户去装字体可靠得多，而且 Chrome headless 配 `--allow-file-access-from-files` 能直接读本地字体文件。

系统的中文字体通常只有：微软雅黑 / 宋体 / 黑体 / 楷体 / 仿宋 / 等线（+ 偶有思源黑体）。**用户点名的那些设计字体（得意黑、优设标题黑、旁门正道、胡晓波、站酷…）基本都没装。**

```python
# 查系统字体（Windows）
# C:\Windows\Fonts\  和  %LOCALAPPDATA%\Microsoft\Windows\Fonts\
# 用 Pillow 读字体真名，别靠文件名猜：
from PIL import ImageFont
ImageFont.truetype(path, 40).getname()   # -> ('Noto Sans SC', 'Thin')
```

可直接下载的免费商用字体（实测可用源）：

| 字体 | 源 | 说明 |
|---|---|---|
| 思源宋体 Bold/Black | `cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc/files/noto-serif-sc-chinese-simplified-{700,900}-normal.woff2` | **「高级金」风格首选**，衬线 + 有粗字重，约 1.4–1.6MB |
| 思源黑体 Bold/Black | 同上，把包名换成 `noto-sans-sc` | 干净粗黑，约 1.1MB |
| 得意黑 | `github.com/atelier-anchor/smiley-sans/releases` | 倾斜、窄、潮流向；无粗字重，大字会显轻 |
| 优设标题黑 | `cdn.jsdelivr.net/gh/callmeyyzx/FontsForWeb/YouSheBiaoTiHei.woff2` | 免费商用（优设官方声明）；倾斜 8°，带货感强 |
| 站酷系列 | `@fontsource/zcool-kuaile` / `zcool-qingke-huangyou` / `zcool-xiaowei` | 标题向 |

```css
@font-face{font-family:'SrcSerifSC';font-weight:900;
  src:url('./fonts/NotoSerifSC-Black.woff2') format('woff2');}
```
- **fontsource 的 woff2 是分包的，路径必须带 `/files/`**：`.../noto-serif-sc/files/noto-serif-sc-chinese-simplified-900-normal.woff2`。少了 `/files/` 会 404。
- `fonts.google.com/download?family=` 这种直链在国内代理下容易 502，改用 jsDelivr。
- 截分镜图前要 `await page.evaluate('document.fonts.ready')`，否则会截到回退字体。**这是最容易踩的坑**：字体没加载完，截图看着像字体没生效。稳妥做法是 `fonts.ready` 之后再 `setTimeout` 400ms，然后**再断言一次**。
- 断言「字体是否真的用上了」时有个**已知误报**：如果两个字重（如 600 和 700）指向同一份 woff2，浏览器只加载一次，没被任何元素用到的那条 FontFace 会一直停在 `unloaded`。所以 `[...document.fonts]` 里出现 `unloaded` 不等于失败 —— 判断依据是**实际用到的字重是否 loaded**，不是要求全部 loaded。

### 中文排版五个高频翻车点

1. **数字和汉字的间隙**：文案写「5 个启示」时，那个**空格**加上 `letter-spacing` 会叠出一大块空白，用户会直接说「5 和 个 之间空白太多」。去掉空格 + `letter-spacing:0`，再用 `margin-left:-14px` 吃掉数字右侧的字面留白。
2. **同级字号不等于同级视觉重量**：数字（`01`）的墨量远小于汉字（`壹`）。同字号下数字显轻，要放大到约 1.2 倍并加粗才追得回。放进环形/圆形里时倍率更高：环内 `壹` 184px → 换 `01` 要 **275px（≈1.5 倍）+ 900 字重**；到 305px 就撑满内圈、衬线贴到环线了。
3. **字号放大时字距要「反向收」**：一套稿子定好的 `letter-spacing` 是按原字号调的，放大字号后不能按比例跟着放。典型值：眉标/kicker 44px 配 12px 字距（0.27em）是合理的，放大到 70px 若仍照比例就是 19px，整行散开、断气。**统一收到 0.13em** 才有紧凑标签的整体感。
4. **衬线数字必须加字距**：衬线体的 `0` 和 `1` 字形本身就贴合，`01` 在字距 < 6px 时会糊成一个色块。给到 **9px** 才有编号的编辑感；同时用 `text-indent:9px` 补偿末位多出的一格，否则整组数字的视觉重心会偏左。
5. **换字体后必须重跑一次横向安全区检测**。衬线字的字面宽普遍大于无衬线，同一段文案在微软雅黑下刚好放得下，换成思源宋体就会顶到画布边缘。实测踩过：一行 20 字 56px 的结论句，换字体后横跨 1000px、左右只剩 32/43px 边距，视觉上已经贴边。修法是缩字号（56→50px）并给容器加 `padding:0 60px`，同时把这半句的 alpha 从 .42 提到 .55（原本太暗，手机小屏读不清）。

### 版面对位不要靠眼睛，写脚本量

审稿图（封面、章节卡）出来之后，用 Pillow 扫亮像素行分布，直接读出每个元素的 y 区间和块间距：

```python
# 按行统计亮像素数，间隔 > 44px 视为元素分块
for y in range(0, h, 2):
    n = sum(1 for x in range(0, w, 3) if px[x, y] > 115)   # 阈值要高于网格线亮度
# 输出：内容总高 / 上留白 / 下留白 / 每个块的 y 区间与块间距
```

这能一次性回答三件事：内容是否真居中（拿内容中心对比画布中心）、哪两块间距过松过紧、放大字号后整体被推高了多少。比肉眼看准，也是改完再复核的标准手法。
阈值取 **115** 左右能滤掉网格线（网格线约 40–70）；如果网格相位不同导致某些线过亮，往上提到 150。

**但亮像素法查「横向溢出」不可靠，要用 DOM 几何。** 两个都会骗你：

- **误报**：双层网格的**交点**亮度能到 108（两层 `.24` alpha 叠加 ≈ 42% → 107），高于网格线本身（61）。用阈值 100 去扫边缘，会把网格交点当成文字，报出一堆假溢出。
- **漏报**：低透明度文字扫不到。`rgba(214,206,186,.42)` 在黑底上只有 ~90 亮度，低于网格交点。一行 20 字、字号 56px 的句子实际横跨 1000px（左右只剩 32/43px 边距），但亮像素检测**完全看不见**它。

正确做法是直接读元素盒子，绕开所有像素层面的干扰：

```js
// 在页面里 evaluate，遍历当前镜头的文本叶子元素
const bad = [];
document.querySelectorAll('#root *').forEach(el => {
  if (el.children.length > 0) return;              // 只看叶子，容器盒子是全屏必然误报
  const txt = (el.textContent || '').trim(); if (!txt) return;
  let p = el;                                       // 排除常驻结构层（进度条/章节轨/字幕）
  while (p) { if (p.id && ['pbar','rail','sub','bg'].includes(p.id)) return; p = p.parentElement; }
  const r = el.getBoundingClientRect(); if (!r.width) return;
  const L = r.left, R = 1080 - r.right;
  if (L < 46 || R < 46) bad.push({ txt: txt.slice(0,26), L, R });
});
```

一个残留的假阳性要知道：`position:absolute;left:0;right:0;text-align:center` 这种**容器全宽、文字居中**的元素，盒子左右都是 0 —— 文字其实在正中间。看 `L`/`R` 报 0 而 `txt` 明显居中时，忽略它。

`assets/check_overflow.cjs` 就是这个检测的成品，逐时间点跑一遍即可。

### 缩略图只用来「找可疑」，判定必须回原尺寸

成片终检时把几十帧拼成缩略总览图（`_总览_全部镜头.png`）很高效，但**不要用它下结论**。

真实误判：6×4 的缩略总览里，后半段镜头几乎看不到网格，看着像「网格消失了」。差点去改网格参数。量化一测 —— 固定空带实测 P50=3–4 / P90=7–16 / max 65–121，**24 帧完全一致，网格一直在**。原因是 1.4px 的网格线缩到 200px 宽的缩略图里只剩 0.26px，物理上必然消失。

所以流程是：**缩略图发现可疑 → 回到 1:1 原尺寸 + 像素度量 → 才动手改。** 遵循这个顺序，避免了一次无谓的大改。

顺带一条：改动前先确认「当前值是不是用户已经批准的那个」。曾核对出正片网格参数（主 `.24` / 细 `.085` / 76px+38px）与用户已批准的分镜图**字符级一致**，于是决定不动 —— 已经过审的东西不要顺手"优化"。

### 语义强调色：换色不如换归属

用户否掉旧版常因为「某个强调元素太村」。**先分清是「形态」土还是「颜色」土**，不要整个删掉。

例：`差 35 分` 原来是**实心亮红胶囊 + 红光晕**。参考片本身就用**实心胶囊徽章**（它用黄绿），所以胶囊这个「形态」是参考片的语言，该保留；真正要换的是**颜色归属**。改成实心金底 + 深色字（`#1A1005`），既保住记忆点的分量，又不往金黑体系里插一块亮红。

判断口诀：**形态跟参考片，颜色跟本片体系。** 两者都推倒重来，往往会丢掉参考片的设计感。

### 排查「文字看不见 / 变成实心块」：直接查计算样式

`-webkit-text-fill-color` 和 `background-clip` 都**可以继承**。任何金色渐变字（`.gold` 系）的子元素都会继承 `transparent` 填充色 —— 结果是子元素文字不可见、只剩父元素的渐变透出来；如果子元素自己还有背景，就会变成一块实心色块。

不要靠看图猜，直接问浏览器：

```js
const cs = getComputedStyle(el);
cs.color; cs.webkitTextFillColor; cs.webkitBackgroundClip;   // 这三个值一起看
```

已知的触发写法：给渐变字元素单独写 `background:linear-gradient(...)`（**简写**会连带把 `background-clip:text` 重置回 `border-box`）。覆盖渐变字颜色时必须写 `background-image`，或把 `-webkit-background-clip:text` 再声明一次。

在此基础上还有两个更阴的变体（2026-09 实测翻车，DOM 查不出、必须看渲染帧）：

**① 渐变父级包动画子元素 = 子元素的 opacity 被无视。**
`background-clip:text` 的裁切只认「字形」，不认字形所属元素的颜色/透明度。所以：

```html
<div class="gold gold-xl">
  <div id="line1" style="opacity:0">差的不是 20 所学校</div>   <!-- 看不见它 -->
  <div id="line2" style="opacity:0">是整套志愿填报的空间</div> <!-- 的 opacity -->
</div>
```

`line1/line2` 的计算样式明明是 `opacity:0`，但它们的字形照样把父级的金渐变裁出来 —— **画面从镜头第一帧起就显示全部文字**，所有分阶段揭示全部失效。修法：**每行各自持有 `.gold`**（渐变、clip、opacity 都在同一个元素上），不要让渐变元素当「容器」。

**② 实底类 + 渐变类组合 = 字消失、底还在。**
`<span class="chip gold">冲</span>`：`.chip.gold` 的 `background` 简写把 clip 重置回 border-box（胶囊是实底 ✓），但 `.gold` 的 `-webkit-text-fill-color:transparent` 没人覆盖 → **字被涂成透明**，只剩一颗空心胶囊。修法：每个 chip 变体显式写 `-webkit-text-fill-color`（0,2,0 特异度压过 `.gold` 的 0,1,0）。

**通用检测法（两个陷阱都抓得住）**：把时间设到镜头刚开始、所有元素应为 `opacity:0` 的时刻截图 —— 此时画面应该是「空的」。只要有任何内容可见，就存在 clip/opacity 类陷阱。光查 `getComputedStyle().opacity` 查不出来（值是 0，照样画）。

```js
await page.evaluate(t => window.__render(t), shotStart + 0.2);   // 一切应不可见
await page.screenshot({ path: 'neg.png' });                       // 若非全黑 → 有陷阱
```

### 环形进度（环形 + 节点）三个参数

- **环底线亮度低于 `.09` 时几乎不可见**，未完成的弧线看着像一根孤立的「斜撇」，不像进度环。提到 `.105` 才读得出完整的圆。
- 弧宽 **≥ 6px** 才看得出比例；配合「5 个节点 + 点亮已过节点」，比单纯靠弧长好读得多。
- **环内 + 环下不要重复同一信息**：环上 5 个节点已表达「共 5 章」、环内 `01` 已表达「第 1 章」，环下再写一行 `01 / 05` 是纯重复。删掉后标题上提、版面立刻干净 —— 「少即是多」在这里是可操作的减法判断。

## 自查清单

- [ ] `__render(t)` 对任意 t 幂等，不依赖调用顺序
- [ ] 背景是**全局单层**（`#root` 的兄弟节点），不在镜头内部
- [ ] 全屏渐变与逐帧变化在不同元素上；辉光/暗角/星点已烘焙进底图 PNG
- [ ] `.wrap` 写了 `color`
- [ ] `.shot` 没有整体 scale
- [ ] 网格用 `translate3d` 且按图案周期取模，**且速度在 0.5–1px/s 的「呼吸」量级**（不是 10px/s 的「闪」）
- [ ] 网格有缓慢的亮度呼吸（sin 周期 15–25s、幅度 ±10–15%、两层相位错开）
- [ ] **跑过 `scan_orphan_classes.py`，没有孤儿 class**（换过 CSS 底座的话这一步必做）
- [ ] 主容器没有 `backdrop-filter` / 大半径阴影
- [ ] 花字若用了 `-webkit-text-stroke`，必须同时有 `paint-order:stroke fill`
- [ ] 金色渐变字若用了 `-webkit-background-clip:text`，`color` 与 `-webkit-text-fill-color` 都置 `transparent`，**且没有被另一个同类选择器的 `color` 覆盖**（查计算样式确认）
- [ ] 渐变字里面若嵌了带背景色的元素（徽章、`≠` 之类），子元素显式重置了 `background-clip:border-box` 与填充色
- [ ] 用了「高级金」风格时字体是**衬线**，不是雅黑
- [ ] 需要设计字体时已用 `@font-face` 自带字体文件（不依赖系统安装），且截图前 `document.fonts.ready` 过
- [ ] **跑过 `scan_selector_mismatch.py`，没有「动画选择器选不中元素」的隐性 bug**
- [ ] **跑过 `scan_css_layout.py`，没有「后代选择器祖先类缺失」的静默失效**，卡片类都有 `max-width:100%`
- [ ] **用了 `<img>` 素材的话，就绪等待里已包含图片加载**（只等字体 → 截图空白且不报错）
- [ ] **查过文字溢出**（`scrollWidth > clientWidth`），没有「外框在界内但文字被裁」的元素
- [ ] **计数数字真的在滚动**（不是停在初始值 0），且不依赖 class 进动画列表
- [ ] **质检脚本本身做过双向验证**（正片通过 + 人为反例被抓到），不是「只会说通过」的废工具
- [ ] **验收脚本先在「测试片」上跑通过**（已知结果），且采不到数据时 `exit` 非 0 —— 「量到 0 个对象」绝不报通过
- [ ] **转场是「下层恒 opacity 1、只让上层淡入」**，且已用 `check_dissolve_frames.py` 量过塌陷 < 6%
- [ ] **「静止段」是用滞后 2s 窗口 + 可见变化像素占比判的**，不是相邻帧瞬时差（后者会给出 94% 的假警报）
- [ ] **渲染完成后：逐帧 PNG 头画幅一致 + 成片反抽帧 PSNR + 塌陷 + 冻结 四项都有数字**（见「成片闭环验收四项」）
- [ ] **合规扫描是扫「渲染后的实际可见文本」**，不是扫源码里的 `innerHTML` 模板串（后者会漏掉全部写在数据字面量里的画面文案）
- [ ] **合规扫描的「字幕」与「画面文案」分开标注**（字幕是用户稿件不擅改、画面文案必须改），且 DOM 扫描已排除字幕层避免重复计数
- [ ] **卡片「浮不浮」是全分辨率裁图 + 明度量化判定的**，不是看缩略图（缩到 340px 宽 1px 描边会消失）
- [ ] **内容自适应宽度的卡片检查过「最宽行有没有把别的行挤折行」**（有就给它显式 `width:100%;max-width:Npx`）
- [ ] **落盘前校验里的断言值都是「先 print 实测、再写死」**，不是凭记忆填的
- [ ] 配色**不是单一色相的不同明度**（「颜色单调」的真实成因，见下节）
- [ ] 每个镜头的**空转秒数**已算过，>4s 的已补内容（见「画面太空怎么诊断」）
- [ ] **镜头内部每句口播都有视觉落点**（不只是尾部空转 —— 22 秒的镜头塞 8 句口播只给 6 个元素，
      会让 13 秒画面静止却不被尾部空转诊断发现。见 8.11）
- [ ] **相邻口播落点帧的像素差 > 0.8**（同镜头内抽第 1/中/末句落点帧实测）
- [ ] **数据对比条量过实际宽度**，差值与被表达的数值差成比例
      （`flex-basis` 会盖掉 `width`，让两条永远等长 —— 见 8.9）
- [ ] **高度 < 240px 的卡片用了 `.sm` 变体**（否则四角装饰线会横穿卡内文字 —— 见 8.10）
- [ ] **图标是内联 SVG**（不是 emoji / 图标字体），颜色由 CSS `stroke` 控制、svg 有显式宽高
- [ ] **data URI SVG 的颜色解码后是合法值**（`stroke='#XXXXXX'`，不是 `%23XXXXXX`）——
      手写 `%23` 再交给 quote 会双重编码，浏览器不报错、只是不画（见 9.1）
- [ ] **SVG 的 `transform` 挂在元素上**（在 `<g ` 之后），不是拼在标签外（见 9.2）
- [ ] **装饰图形渲染出来看过一眼**（字符串自检覆盖不到"图形有没有画出来" —— 见 9.3）
- [ ] **四角装饰逐个放大确认在角上**，不是"附近"（百分比定位是边缘对齐语义 —— 见 9.4）
- [ ] **固定尺寸装饰没有被 `background-size` 拉伸**（见 9.5）
- [ ] **装饰尺寸按容器短边分档**（48 / 34 / 22），不是一套用到底（见 9.6）
- [ ] **同屏同类容器用同一套装饰**（`.card` 有、`.rrow` 没有 → 看起来是两套语言 —— 见 9.7）
- [ ] **所有启动 Chrome 的脚本都等了图片**（换 `<img>` 素材后 grep 一遍 —— 见 9.8）
- [ ] **常驻层的 y 区间两两不重叠**，间距 ≥ 40px（算，不要目测 —— 见 9.9）
- [ ] **品牌 logo 用位图原色**，没套会染色印章的滤镜（见 9.10）
- [ ] **用 DOM 几何量过各镜头占安全区多少**（别用像素扫描，会误判常驻层）
- [ ] 「一行 N 张卡」的镜头若占不满高度，已考虑换成纵向铺开的布局（排行条/多行卡）
- [ ] 片头/章节页/总结页/片尾品牌卡的留白**是设计的一部分**，没有被硬填
- [ ] 对比卡上的「−2 / ↓6 / ↑230」等差额由数值派生，不是手写
- [ ] 带「年份 + 数值」的镜头，年份由数值派生，不存在失配窗口
- [ ] 加过内容的镜头回看过截图，卡片没顶到章节轨 / 字幕带
- [ ] 数字与汉字之间没有多余空格叠加 letter-spacing 产生的空隙
- [ ] 同字号下数字的视觉重量与汉字匹配（不够就放大加粗；环内换数字按 1.5 倍算）
- [ ] 放大过的字号，其 `letter-spacing` 已反向收紧（不是按比例跟着放大）
- [ ] 衬线数字（`01`）给了 ≥6px 字距，并用 `text-indent` 补偿末位空格
- [ ] 用脚本量过版面：内容中心 ≈ 画布中心，块间距没有明显失衡
- [ ] 环形进度的环底线亮度 ≥ .105，弧宽 ≥ 6px
- [ ] 环内与环下没有重复同一信息（章节号 / 总章数只说一遍）
- [ ] 背景网格没有超出暗场收边区，四角回到纯黑
- [ ] **没有自己加雪点/星点**（除非参考片实测有）
- [ ] 双层描边卡片的同心环外扩量与卡片间距匹配，环没有互相压住
- [ ] 散布采样测速过，全片耗时可接受
- [ ] 抽帧覆盖每类镜头，含动画完成态
- [ ] **用户提过的每一条修改，都在正片文件里 grep 复核过**（原型改了 ≠ 正片改了）
- [ ] **同一套视觉语言（编号/配色/字体）在所有用到它的地方都统一了**（章节卡 + 封面 + 常驻章节轨…）
- [ ] 覆盖渐变字颜色时写的是 `background-image`，不是 `background` 简写
- [ ] 没有残留的旧风格元素（上版的花字/亮色胶囊/时间码/装饰）
- [ ] 从成片 mp4 反抽帧复核过
- [ ] **字幕若含 `<br>` 断行，赋值用的是 `innerHTML` 而不是 `textContent`**（否则画面上 literally 显示 `<br>`）
- [ ] **字幕里没有尖括号残留**（反抽帧放大字幕条看一眼，这是唯一能抓到的地方）
- [ ] 验收脚本的镜头表来自 `window.__shots`（与渲染同一份），不是正则解析 `add(数字,数字,…)` ——
      正则匹配不到 `add(S0,S1,…)` 这种变量入参，会**静默少验几个镜头**却报告「全部 ok」
- [ ] 局部重渲前后都跑过尺寸守卫（`rerender_range.cjs --check-size`），
      且守卫做过双向验证（谎报画幅必须被抓到并返回退出码 4）
- [ ] **语义卡/柱体量过明度：元素区域 ≥ 页面背景**（否则等于没画，客户会说「寡淡」）
- [ ] **柱体没有渐变到 `transparent`**（下半截空 = 「透明玻璃管」）
- [ ] **源码 MD5 == 备份 MD5**（证明成片确实出自当前源码，不是旧文件）
- [ ] 反抽帧复核做成了**带标注的总览图**，用户可自行核对
- [ ] 抽帧时间点按字幕表对齐，不是凭印象取整
- [ ] 敏感内容（数据、二维码、品牌）没有占位/假造未标注
- [ ] **平台合规词扫描**：成片里没有 `扫码` / `长按` / `识别` / `搜索` / `二维码` 等引导词
      （若客户要求规避平台审查风险）
- [ ] 合规词扫描只扫**可见文本**，不要把 patch 脚本自身的注释一起扫进去

### 平台合规词扫描（发布到视频号 / 抖音前）

当客户说「规避平台审查风险」「不要出现扫码/搜索」时，原则是：
**只做视觉提示，不做动作引导**。片尾可留品牌卡 + 呼吸闪烁，但去掉所有
二维码占位框、`二维码` 字样、`扫码` / `长按识别` / `去搜索` 类引导词。

扫描时按下面的方式取可见文本（**别扫整个 HTML 源码**）：

```python
def visible_text(src):
    """只取真正会显示出来的文字：SUBS 表 + 各镜头 innerHTML 的标签间文本。"""
    out = []
    for m in re.finditer(r'\[\s*[\d.]+\s*,\s*[\d.]+\s*,\s*"((?:[^"\\]|\\.)*)"\s*\]', src):
        out.append(m.group(1))
    for m in re.finditer(r'\.innerHTML\s*=\s*`([\s\S]*?)`', src):
        out.append(re.sub(r'<[^>]+>', ' ', m.group(1)))
    return "\n".join(out)
```

两个实测踩过的坑：

1. **别把源码整体当扫描对象**。第一次扫出「扫码」×1、「长按」×2 —— 全是我自己
   patch 脚本注释里的词（如「弧长按章号递增」）。只扫可见文本后归零。
2. **先删 DOM 再扫**。待删的旧元素（虚线二维码框、提示文字）还在源码里时，
   扫描必然命中，别误判成「改失败了」。

配套的 `brightness` 呼吸幅度参考：`1 + 0.06*sin(2πt/2.6)`（±6% / 2.6s 周期）
在竖屏手机上肉眼可辨又不闹；金线脉动可同相用 `scaleX(0.62 + 0.38*breath)`
与亮度联动，看起来像卡片自己在「呼吸」。

## 【高频需求】「颜色太单调」怎么改：建语义色板，不是加装饰

客户说「颜色元素可以多一些」时，**不要理解为「多加点金色装饰」**。
先去数一下自己的配色：如果所有彩色元素的色相都相同（比如全片只有一支金，
普通元素和强调元素只是同一支金的 `.42` 与 `.90` 两档透明度），
那就是**单色相问题** —— 观众无法靠颜色区分「哪根柱子是重点」，只能靠高度。

正确解法是建立**语义色板**：一个色相 = 一个含义。

```css
:root{
  /* 注意 --*-bg 是「贴纯黑底的实色量级」.46，不是 .13 —— 见下文「寡淡」一节 */
  --up:   #E0504E;  --up-t:   #FFEDEA;  --up-bd:   rgba(224,80,78,.90);   --up-bg:   rgba(224,80,78,.46);
  --down: #3E9E8A;  --down-t: #E3F7F1;  --down-bd: rgba(62,158,138,.90);  --down-bg: rgba(62,158,138,.46);
  --gold: #DCC276;  --gold-t: #FFF6CE;  --gold-bd: rgba(214,190,120,.92); --gold-bg: rgba(214,190,120,.46);
  --warn: #E39A38;  --warn-t: #FFF2DC;  --warn-bd: rgba(227,154,56,.90);  --warn-bg: rgba(227,154,56,.46);
  --cool: #8E83D8;  --cool-t: #F0EDFF;  --cool-bd: rgba(142,131,216,.90); --cool-bg: rgba(142,131,216,.48);
  --nu:   #9A968C;  --nu-t:   #E4E0D8;  --nu-bd:   rgba(214,190,120,.62);  --nu-bg:   rgba(214,190,120,.30);
}
```

两个关键设计决策：

1. **红涨绿跌 vs 红涨青跌**。做中国市场内容时，「涨/利好」用暖红、「跌/利空」用青绿
   （贴着国内股市直觉）。若客户在欧美语境则反过来。**开工前先问清楚**。
2. **金色保留，但降级为「中性数据色」**。品牌主色不宜废掉，但要把它从
   「唯一的颜色」变成「只负责中性数值」，把「好坏判断」让给 up/down 两色。
   这样既保住视觉 DNA，又让颜色开始承载信息。

接线时**务必真的把语义类挂到元素上**，只定义变量等于没做：

```python
'<div class="bar o up">'    # 强调 + 利好
'<div class="bar nu">'      # 中性对照
'<div class="chip up">+18</div>'
```

### 语义卡的强度：暗场里要给足

**先看一个实测教训。** 下面这组值（`.20/.07`）依然是不够的 ——
成片实测卡面明度只有 `0.023`，**比页面背景 `0.049` 还暗**，等于没画。
客户的原话是「底色太淡了，寡淡」。

```css
/* ❌ 不够：暗场里等于没画 */
.s-up{ background:linear-gradient(178deg,rgba(224,80,78,.20),rgba(224,80,78,.07)) !important; }

/* ✅ 够用量级 */
.s-up{ border:1.5px solid rgba(224,80,78,.90) !important;
       background:linear-gradient(178deg,rgba(224,80,78,.62),rgba(224,80,78,.34)) !important;
       box-shadow:0 0 38px rgba(224,80,78,.30), inset 0 1px 0 rgba(255,190,186,.24); }
```

边框 1.5px 而非 1px、色值透明度给到 `.90` 以上 —— 暗场里 1px / `.6` 是看不见的。

### ⚠️ 「寡淡」是可量化的：给元素一个明度下限

**不要凭肉眼反复调色**。这是本 skill 最有价值的一条沉淀：

| 元素区域均值明度 | 结论 |
|---|---|
| `> 背景 + 0.15` | 立得住 |
| `背景 ~ 背景+0.15` | 偏淡，客户会说「寡淡」/「区分不开」 |
| **`≤ 背景`** | **等于没画**（贴在纯黑上被吸掉） |

诊断口径：从**编码后的成片**抽帧，量元素区域与页面背景的 HSV 明度均值并比较。

**注意这是"元素 vs 背景"的差值判据，不是元素的绝对明度。**
元素绝对明度够亮也可能失败 —— 如果背景同样亮。详见下文
「卡片和背景区分不开」一节的**两类失败**对照表。

实测对照（同一次修改前后）：

| 区域 | 改前明度 | 改后明度 | 提升 |
|---|---|---|---|
| 对比柱·红 | 0.176 | 0.646 | 3.7× |
| 对比柱·中性 | 0.044 | 0.422 | **9.6×** |
| meta 小卡·中性 | 0.023 | 0.366 | **16×** |
| meta 小卡·青绿 | 0.023 | 0.317 | 13.8× |

**推荐的透明度量级**（贴纯黑底时）：

| 用途 | 透明度 |
|---|---|
| 语义变量 `--*-bg` | **`.46`**（不是 `.12`） |
| 语义卡渐变 | **`.62 → .34`** |
| 中性/对照 `--nu-bg` | **`.30`**（可弱，但不可低于此） |
| 描边 `--*-bd` | **`.90`** |

### ⚠️ 柱子绝不能「渐变到 transparent」

非常常见的写法，也是客户最容易一眼指出来的问题：

```css
/* ❌ 柱子下半截是空的，像玻璃管 —— 客户会说「不要透明」 */
.bar.o.up{ background:linear-gradient(180deg,rgba(224,80,78,.34),transparent); }

/* ✅ 实心柱：顶端亮、底端仍是实体 */
.bar.o.up{ background:linear-gradient(180deg,rgba(224,80,78,.92),rgba(224,80,78,.52));
           box-shadow:0 0 40px rgba(224,80,78,.42), inset 0 0 40px rgba(255,150,146,.18); }
```

底端保留 `.52` 左右；再加 `inset` 内辉光给柱体体积感。
**`transparent` 只该用于「淡出边缘」，不该用于「数据实体」。**

### 采样定位：别目测标坐标，用 `getBoundingClientRect()`

想量某张卡的实际像素，**不要看着截图估坐标** —— 估偏了就采到背景上，
读出的数全是假的（第一次采样两张小卡得 0.079 / 0.073，全是背景值）。

正确做法：先 `getBoundingClientRect()` 拿到元素真实 box，
**再向内缩 12%**（避开描边与四角花纹），然后才采样：

```js
const r = e.getBoundingClientRect();
const m = Math.min(r.width, r.height) * 0.12 + 12;
// 采样框 = (r.x+m, r.y+m, r.x+r.width-m, r.y+r.height-m)
```

`assets/probe_by_dom.py` 已把这套流程封装好，可直接复用。

**这条要反复强调 —— 它一共骗过我两次。** 第二次是量卡片分层时：
我按截图目测「排行榜在 y≈300–455、对比卡在 y≈400–560」，
实际是 **`y=434–1228` 和 `y=596–1043`**。
结果采出来的全是背景值，得出一组和截图**明显矛盾**的假数据
（截图里卡面清清楚楚，数据说 `0.024`）。当时差点据此得出「改了没用」的错误结论。

> 教训：**任何时候，只要量化结果和肉眼看到的对不上，先怀疑坐标，别怀疑眼睛。**
> 先跑一次 `getBoundingClientRect()` 取真实 box，再谈采样。

## 「卡片和背景区分不开」：工作马卡片最容易漏（四件套）

客户说「很多卡片和背景还是区分不开」时，**先分清是两类失败中的哪一类**：

| 失败类型 | 症状 | 解法 |
|---|---|---|
| **元素太暗** | 元素本身明度接近 0，被纯黑吸掉 | 抬元素明度（上一节） |
| **差值不够** | 元素够亮，但**背景也亮**，两者只差 0.03 | 抬元素 **且** 压背景（本节） |

**实测教训**：上一轮只改了**语义卡** `.s-*` 和柱子 —— 它们是"有颜色的卡"，
改动时自然会注意到。而 `.card5` / `.tag` / `.rrow` 这类**"工作马"卡片**
（无彩色、靠中性色打底）被整体漏掉，成片里卡面明度仅 `0.044~0.049`，
而页面背景 `0.012~0.016` —— 只差 `0.03`，远低于 `> 背景 + 0.15` 的判据，
**等于没画**。客户的原话正是「很多卡片的和背景还是区分不开」。

> **通用规则**：改卡片强度时，必须把**全部卡片类**列一遍，
> 包括无色中性卡、胶囊 tag、排行条、品牌卡。别只改"有颜色的那些"。

**让卡片真的"浮起来"的四件套**（缺一件都会显得扁）：

```css
/* 共享底座：一处改，全片 20+ 张卡受益 */
.card5,.glass,.kw,.brandcard,.ncard{
  position:relative;border-radius:20px;
  /* ① 双层描边：外圈暗（把卡从背景里"切"出来）+ 内圈亮金线 */
  border:1px solid rgba(226,203,138,.72);
  background-color:#181614;
  background-image:
    /* ② 卡面抬明度到能看清的炭灰（#2A2723 → #171512），明度约 0.13→0.10 */
    linear-gradient(160deg,rgba(255,255,255,.085) 0%,rgba(255,255,255,0) 38%),
    linear-gradient(168deg,#2A2723 0%,#201D1A 48%,#171512 100%);
  background-repeat:no-repeat;
  /* ③ 大投影（双层）+ ④ 顶部受光内高光 + 底部内暗边（厚度） */
  box-shadow:0 0 0 1px rgba(0,0,0,.95),          /* 外暗圈 */
             0 0 30px rgba(214,190,120,.10),      /* 极淡金晕 */
             0 20px 44px rgba(0,0,0,.62),         /* 近投影 */
             0 40px 90px rgba(0,0,0,.55),         /* 远投影：撑体积 */
             inset 0 2px 0 rgba(255,240,200,.16), /* 顶部受光 */
             inset 0 -2px 12px rgba(0,0,0,.45);   /* 底部厚度 */
}
```

四个手段的分工：**① 描边负责"边"、② 卡面负责"面"、③ 投影负责"离地"、④ 内高光负责"受光"**。
只做 ① 得到一张"描了边的空框"，只做 ② 得到一块"没边界的色块"，都要靠后面两个才立体。

**配套必做的两件事**：

1. **同类元素同步抬**。卡面抬亮后，`.tag` 胶囊 / `.rrow` 排行条 / `.ncard` 如果不动，
   会变成新的一批"陷在背景里"的元素。给它们配同一套投影：
   ```css
   .rrow{ box-shadow:0 0 0 1px rgba(0,0,0,.95),
                      0 14px 30px rgba(0,0,0,.58),0 28px 62px rgba(0,0,0,.48),
                      inset 0 2px 0 rgba(255,240,200,.15),inset 0 -2px 10px rgba(0,0,0,.42); }
   ```
2. **网格线退让**。卡面抬亮后网格线会和卡面"抢"视觉，把主网格 `.24 → .19`、
   细网格 `.085 → .070`。**背景元素的强度要随前景抬升而相对下降**。

**验收数值**（改前 → 改后，元素区域 vs 背景的 HSV 明度均值差）：

| 元素 | 改前差值 | 改后差值 |
|---|---|---|
| 排行条 1–4 | +0.119 ~ +0.134 | **+0.179 ~ +0.192** |
| 对比卡 左/右 | +0.170 / +0.142 | **+0.215 / +0.191** |
| 片尾品牌卡 | +0.164 | **+0.210** |

全部越过 `0.15` 判据线。**注意改前并不都是"没画"** —— 排行条 `+0.12` 是"勉强过线但偏弱"，
真实表述应是「临界偏弱被推到明确过线」，**别夸大问题**，客户会核对。

## 典藏卡片库：深黑卡面靠什么脱离背景（第二条路线）

上一节「四件套」是**第一条路线：抬亮卡面**（卡面明度抬到背景 +0.15 以上）。
当**背景本身很暗**（近黑 + 纹理）时，还有**第二条路线：让卡片「发光」** ——
深黑卡面不抬亮，靠描边与光晕从暗背景里浮起来。暗场里这条路更高级、更「典藏」。

完整实现见 `assets/card-library.html`（一页含四种卡片形态 + 横竖两画幅）。核心六件事：

| # | 手段 | 具体值 |
|---|---|---|
| ① | 卡外柔光晕 | `0 0 52px rgba(206,176,104,.17)` + 一层 `0 0 110px` 更淡的 |
| ② | 双层描边 | 外 `1px solid rgba(226,203,138,.72)` + **内缩 3.8% 再一圈** `.34` 淡金线 |
| ③ | 硬边厚度 | 右下偏移的实心 `box-shadow`（见下，别用伪元素） |
| ④ | 卡面内受光 | `inset 0 1px 0 rgba(255,242,206,.24)` + 上中部径向提亮 `.055` |
| ⑤ | 卷草纹 + 四角花纹 | 金色渐变 SVG，宽占卡宽 56% / 19.5% |
| ⑥ | 中英双层标题 | 中文黑体 900 金渐变 `.80w/n` + 英文衬线宽字距 `.062w` |

两种路线可以叠加：背景暗 → 走 ②；背景亮或灰 → 走抬卡面。

### ⚠ 厚度用 box-shadow 做，不要用负 z-index 的伪元素

想让卡片右下露出一条「金属断面」，直觉是加一个 `::after{ z-index:-1 }`。
**这会失败** —— 负 z-index 的元素绘制在**所有无 z-index 的绝对定位背景层之下**，
背景层把它整个盖住，看起来「厚度根本没画」（排查了很久才定位到）。

正确写法：**用元素自身的实心 box-shadow**。外阴影天然绘制在卡面之下，不会被自己盖住：

```css
.gcard{
  box-shadow:
    6px 7px 0 0 rgba(206,178,116,.50),   /* 金：列表第一层，绘制在最上 */
    7px 8px 0 0 #0B0A08,                 /* 内暗 */
    12px 14px 0 0 rgba(0,0,0,.90),       /* 外暗，偏移最大 */
    /* …其余柔光晕与大投影… */;
}
```
列表**靠前的绘制在上**：金边放前面、暗面放后面且偏移更大，露出的才是「外暗 + 内金」的金属断面。

### 背景：立体菱形鳞片

比「细线网格」有实物感得多的做法：**SVG `<pattern>` + `patternTransform="rotate(45)"`**，
每个方块「左上受光 + 右下暗边」，用两条 1.4px 的亮/暗细条实现凹凸：

```svg
<pattern id="tileP" width="54" height="54" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <rect width="54" height="54" fill="#0B0A09"/>                                      <!-- 缝隙 -->
  <rect x="1.2" y="1.2" width="51.6" height="51.6" fill="url(#tileG)"/>              <!-- 块面 -->
  <rect x="1.2" y="1.2" width="51.6" height="1.5" fill="rgba(255,248,228,.095)"/>    <!-- 上受光 -->
  <rect x="1.2" y="1.2" width="1.5" height="51.6" fill="rgba(255,248,228,.070)"/>    <!-- 左受光 -->
  <rect x="1.2" y="51.3" width="51.6" height="1.5" fill="rgba(0,0,0,.92)"/>          <!-- 下暗边 -->
  <rect x="51.3" y="1.2" width="1.5" height="51.6" fill="rgba(0,0,0,.92)"/>          <!-- 右暗边 -->
</pattern>
```
再叠一层 `radial-gradient` 明暗（中央提亮 `.065` + 边缘压深 `.78`），背景就「有光」了。
律动仍按老规矩：位移 0.9px/s + 19 秒亮度呼吸 —— 快 = 闪 = 廉价。

### ⚠ `<use href="#symbol">` 必须显式写 height

饰纹抽成 `<symbol>` 复用是对的，但外层 `<svg>` **没有自己的 viewBox** 时，
`height:auto` **不会**按宽高比算，而是退回 SVG 的默认 150px ——
饰纹被纵向拉长成「飘带 / 翅膀」（一度以为是自己 path 画错了）。

```css
/* ✗ 实际渲染成 150px 高，被拉长 */
.gcrest{ width:calc(var(--w)*.56); height:auto; }
/* ✓ 显式写；卷草 symbol 的 viewBox 是 300×46 */
.gcrest{ width:calc(var(--w)*.56); height:calc(var(--w)*.56*46/300); }
```
**自查法**：给本该是正方形的元素（如四角花纹）写个探针量 `getBoundingClientRect()`，
宽高不是 1:1 就是中招了 —— 肉眼只会觉得「花纹画得不像」，很难想到是尺寸问题。

### ⚠ 渐变标题必须 nowrap + 按字数自适应字号

`background-clip:text` 的金渐变标题，在卡内宽的**临界点会断成「3+1」两行**。
两个约束要一起加：

```css
.gcn{ white-space:nowrap; font-size:calc(var(--w) * .80 / var(--n,4)); }
```
`--n` 由外部传（`style="--n:5"`）：n=4 时字号 `.20w`，4 字总宽恰好卡在内宽 `.82w` 之内。
用固定字号，5 / 6 字标题必定横向溢出。

## 「背景不够高级」：暗场要有光，不是要更多装饰

客户说「背景不够高级」时，**不要加金线、加花纹、加粒子**。
暗场显廉价通常只有一个原因：**背景是一块均匀的死黑，没有光。**

正确的解法是做**四层光照结构**（`assets/gen_bg.py` 是参数化实现）：

| 层 | 作用 | 参数（1080×1920 参考值） |
|---|---|---|
| **A 炭基底** | 定整体基调，**不要纯黑** | `BASE=4` |
| **B 顶部主暖光** | 画面的"光源"，呼应品牌金 | `WARM_PEAK=13`，余弦平方衰减，宽而柔 |
| **C 中部极淡冷调** | 冷暖对比 + 空气感 | `COOL_PEAK=5`，极淡，只为"有空气" |
| **D 四角强暗角** | 回近纯黑，把注意力压向中心 | `VIGNETTE_FLOOR=0.03`，**乘性** |

```
关键：亮部用「加法」（光打在底上），暗角用「乘性」（光衰减到 0）。
     全程乘性会压不黑；全程加法四角会发灰。
```

**实测输出剖面**（必须逐行核对）：
`y=0: 1.9 → y=320: 7.9（峰值）→ y=960: 4.0 → y=1760: 0.5 → 四角 (0,0,0) → 中央 4.1`

**⚠️ 暗渐变必然产生 banding（同心环），必须专门消除。**

8-bit 量化在暗渐变里会出现肉眼可见的阶梯环。三步缺一不可：

```python
im = im.filter(ImageFilter.GaussianBlur(10))                        # ① 强模糊：先把阶梯抹平
arr = np.asarray(im).astype(np.float32) + rng.uniform(-0.9,0.9,a.shape)  # ② 亚 1 灰阶抖动：打散量化
im = Image.fromarray(np.clip(arr,0,255).astype(np.uint8))
im = im.filter(ImageFilter.GaussianBlur(1.6))                       # ③ 极轻模糊：消掉噪点
```

① 单独用会留环；② 单独用会把噪点交给 H.264 放大成"脏"（客户会判定「画面脏」）；
**必须 ② 之后再 ③**，这是三步里最容易省掉、也最不能省的一步。

**验证方法**：把底图 **6× 增益**后看，环和条带会放大到肉眼可辨。
1× 下看不出来不代表没有。

### ⚠️ 别用 PIL 的 `ImageDraw` + `ImageChops` 画光照

第一版这么写，输出全错：`R 均值 91`（目标 5）、四角 `(82,56,36)` 根本没变黑。两个坑：

1. `ImageDraw.ellipse` 的 box 给负坐标 → **几何反转**
2. `ImageChops.multiply` 对极低值图像**几乎不起压暗作用**

改法：**全程用 numpy 向量化**。`radial()` 做余弦平方径向衰减、光照用加法叠加、
暗角用乘性且系数作用在**归一化全量程**上。改完一次就对。

## 「画面太空」怎么诊断：数空转秒数，不是看截图感觉

竖屏内容密度低是通病（实测某条竖屏成片，每帧非背景像素只有 **8.6%**，一屏 91% 是空的）。
但**不要一上来就换画幅** —— 16:9 投竖版信息流会被上下加黑边，可视面积反而变小。
先量化，再决定。

可靠诊断法：解析每个镜头的 `add(st, et, ...)` 时间窗，取该镜头内所有
`lt-N` 偏移的**最大值**（≈最后元素的入场时刻），镜头时长减掉它 = **空转秒数**。

```python
offs = [float(x) for x in re.findall(r'lt-([\d.]+)', shot_body)]
idle = (et - st) - (max(offs) if offs else 0)
```

空转 > 4s 的镜头就是「画面空」的元凶。实测某条成片：

| 镜头 | 时长 | 最后元素 | 空转 |
|---|---|---|---|
| S22 对比柱 | 9.07s | 1.2s | **7.9s** |
| S14 四关键词 | 9.47s | 0.5s | **9.0s** |
| S12 新校 chips | 5.87s | 0.4s | **5.5s** |

### 补密度的原则：加信息，不加装饰

空转的修法**不是**加飘动光点（客户会判定「脏」），而是：

1. **给列表项加解释性副标题**。只有「管理团队」四个字 → 加「看校长任期与班子是否稳定」。
   看完知道该做什么，价值密度也上去了。
2. **给图表补数值标签**。柱子只有高度没有数字，补上 `410 / 330`。
3. **入场后加轻微呼吸**（`brightness` ±4.5% / 3.2s，逐项错开相位），
   避免「铺满后彻底静止」的呆板感。
4. **收紧时序**：把后段元素入场提前，空窗自然缩短。

### 空转诊断的三层递进：静态扫描 → 帧间差实测 → 口播对齐

静态 `lt-N` 扫描有**两类系统性漏算**（都实测踩过）：

1. **顺序入场写 `(lt-1.6-i*1.5)` 时**，正则只能拿到基数 1.6；
   若有 5 条 band，最后一条实际在 `1.6+4×1.5=7.6` —— 低估 6 秒。
2. **连续动画**（曲线逐点生长 `cur.apply(lt,...)`）根本没有 `lt-N`，全部漏算。

第二层是**画面运动实测**：每 0.5s 渲染一帧缩到 270×480，找「画面真的没动」的段落。

**⚠️ 判据绝对不能用「相邻帧瞬时差（MAE）」—— 这是一个会把人带进沟里的假警报。**
实测踩坑（2026-10-09）：旧版用相邻帧 MAE + 自标定阈值 `1.8×全片中位数`，报出
「静止 94.6%、15 段需补内容」。但拿同一批帧做**逐字节 MD5 比对**：
513 对相邻帧 **100% 各不相同，没有一段是冻结的** —— 15 段全是误报。

根因两条，缺一不可：
1. **原理性缺陷**：本片运镜是「缓慢但连续」的，0.5s 内的位移本就与背景呼吸同量级。
   瞬时差法**在原理上分不开「慢运镜」和「真冻结」**，再怎么调阈值都没用。
2. **自标定假设不成立**：`1.8×中位数` 隐含「帧差分布是双峰（呼吸 vs 真运动）」。
   单峰分布时它会机械地把过半样本判成静止。

**正解：判据必须建立在「滞后窗口」上。** 比较**相隔 LAG 帧（默认 2s）**的两帧，
只看发生**可见变化**（`|Δ| > 4/255` 灰阶）的像素占比：

```python
lag  = round(LAG_S / STEP)                       # 2.0s / 0.5s = 4 帧
frac = (np.abs(aps[i+lag] - aps[i]) > 4/255).mean()
frozen = frac < 0.005                            # 0.5% 像素可见变化，且连续 ≥2s
```

- 真冻结：2s 后画面几乎逐像素相同 → `frac ≈ 0`
- 慢运镜：位移累积 2s 后普遍越过 4 灰阶 → `frac` 到百分之几

实测本片最安静处（镜 01 起手）仍有 **5.03%** 像素在动，判据是 0.5% —— **相差一个数量级**，
区分力充足。`check_motion.py --selftest` 做三向验证：完全冻结 10s 必须检出、
弱噪声（<1 灰阶）必须检出、每 0.5s 移 1px 的慢摇**不得**误报。

> **一条比工具本身更重要的原则：一个假警报比没有检查更糟。**
> 假警报会让人去改本来没问题的镜头，浪费时间还破坏已经过审的节奏。
> 任何检查工具在报出「需要修改」之前，先用一个**正交的、不可能错的判据**
> （这里就是逐字节 MD5）交叉验证一次。

- **帧间差是面积加权的**：几个小标签入场（占画面 ~2%）根本不触发阈值，
  会把「其实有内容变化」误报成 6.5s 静止。它适合抓大块空场，
  **不适合**证明「这段没做动画」。

第三层才是判定标准：**把镜头尾部每句口播的起始时间列出来，
确认每句话都有一个对应的视觉落点**。口播是唯一不可协商的时序基准 ——
一个 14s 的镜头，口播在 lt=9.2/13.0/15.1 还有三句话，
画面却在 lt=6.0 就全亮完了，这就是真空场（哪怕帧间差说它「有微动」）。
修完抽 3 帧（第一句落点前 / 中 / 后）人工确认揭示顺序，比任何指标都可靠。

### 卡片铺满后要回检安全区

加内容后卡片会变高，容易顶到常驻章节轨或字幕带。
`.stage` 若有 `padding-bottom`（如 150px）且 `box-sizing:border-box`，
可用宽度会被压缩，`min-width` 的 flex 换行结果可能突然从两列变一列。
**布局改动后必须回看截图确认列数**，不要只信算式。

### 量「内容占多少」要用 DOM 几何，不要像素扫描

**踩坑实录**：为了量各镜头内容占安全区多少，我写了三版像素扫描脚本，**三次结果全是假的**：

| 版本 | 阈值 | 假象 | 根因 |
|---|---|---|---|
| v1 | 亮度 > 34 | 所有镜头跨度 92~99% | 背景网格线亮度 40+，被当成内容 |
| v2 | 逐行 ≥6% 像素 > 20 | 所有镜头都「溢出底、过满」 | 字幕带（y1674）被算成内容 |
| v3 | 排除 y>1680 | 仍然全假 | 排除区间拍脑袋，常驻层位置没量准 |

**根因**：像素扫描分不清「镜头内容」和「常驻层」（顶部 logo、章节轨、字幕带）。
它们的位置随版式变化，靠猜阈值永远对不上。

**正确做法**：用 `getBoundingClientRect()` 直接问浏览器要几何，
显式排除常驻层选择器。这才是可靠数据源。

```js
// 常驻层选择器按你自己的页面改：这里列出的是「顶部 logo / 章节轨 / 字幕带 / 章节角标 / 进度条」
const EXCL = ['#toplogo', '#rail', '#sub', '.chap', '#pbar'];
const s = [...document.querySelectorAll('.stage')]
  .filter(x => getComputedStyle(x).opacity > 0.02).pop();
let y0 = Infinity, y1 = -Infinity;
for (const el of s.querySelectorAll('*')) {
  if (EXCL.some(sel => el.matches(sel) || el.closest(sel))) continue;
  const cs = getComputedStyle(el);
  if (cs.opacity < 0.03 || cs.display === 'none') continue;
  const r = el.getBoundingClientRect();
  if (r.width < 2 || r.height < 2) continue;
  y0 = Math.min(y0, r.top); y1 = Math.max(y1, r.bottom);
}
const cov = (y1 - y0) * 100 / (SAFE_BOT - SAFE_TOP);   // 占安全区高度
```

同时把 `.stage` 从「全屏居中」改成**明确的纯安全区**，这是根治「内容只占中间 1/4」的关键：

```css
/* 改前：top:0/bottom:0 + padding-bottom:150 → 内容中心被推到 y≈885 */
/* 改后：直接圈出安全区，25 个镜头一起受益 */
.stage{position:absolute;left:0;right:0;top:196px;bottom:440px;
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;box-sizing:border-box;}
```

### 布局真正的病根：「一行四卡」在竖屏里天生占不满高度

量化后发现，**能长期占满安全区的镜头都用了纵向铺开的布局**（排行条 / 多行卡），
而「一行 N 张卡」的镜头卡在 40% 左右 —— 横向铺开在 1080×1920 里是浪费。

**修法是换布局，不是加 padding**。实测对比：

| 镜头 | 原布局 | 占安全区 | 改后布局 | 占安全区 |
|---|---|---|---|---|
| 四卡对比 | 一行四卡 | 28% | **每项一行的排行条** | **72%** |
| 两方案对比 | 裸文字 | 38% | 卡面容器 + 差额行 | 61% |
| 分值差结论 | 裸文字 | 37% | 卡面容器 + 差额行 | 61% |
| 趋势对比 | 三行字 | 25% | 数据卡（两个大数 + 结论） | 56% |

**加减 padding 是零和博弈**（卡高了但元素没多，还是空）；
**换布局 + 加信息**才是根治。参考实现（每校一行，四层信息）：

```css
.ranks{display:flex;flex-direction:column;gap:26px;width:880px;}
.rrow{display:flex;align-items:center;padding:34px 40px;border-radius:16px;}
.rrow .rno{width:64px;font-size:38px;color:rgba(214,190,120,.72);}  /* 序号 */
.rrow .rnm{width:250px;font-size:50px;font-weight:900;}             /* 校名 */
.rrow .rsc{margin-left:auto;font-size:76px;font-weight:900;}        /* 分数 */
.rrow .rdif{margin-left:38px;min-width:132px;text-align:right;}     /* 分差 */
```

### 差额/分差一律从数值派生，不要手写

排行条/对比卡上的「−2」「↓6」「↑230」如果手写，改了主数值就会不一致。
声明成一组数据、差额自动算：

```js
const A=592, B=586, gap=A-B;
const top=Math.max(...four.map(x=>+x[1]));
const diff=v => v===top ? '最高' : `−${top-v}`;
```

### 该停手的地方：片头 / 章节页 / 片尾品牌卡

不是所有偏矮镜头都要补。**片尾品牌卡（合规留白）、总结页（大字节奏）、
章节过渡页**天生就该留白 —— 硬填会毁掉节奏。判断标准：

- **内容型镜头**（在讲具体信息/数据）→ 偏矮必须补
- **节奏型镜头**（片头/章节/总结/片尾）→ 留白是设计的一部分

### 交付前 1 秒成本的一致性校验：源码 MD5 == 备份 MD5

「改了源码，但渲染的是旧文件」这类事故**极难从画面上看出来** —— 你看的静帧
可能就是改之前的，于是误判「改动没生效」或「改动已生效」。

成本 1 秒的确定性答案：

```bash
md5sum index.html index_vXX_backup.html   # 两者必须完全一致
```

改完盘后立刻 `cp index.html index_vXX_backup.html`，渲染完成后再对一次。
一致才说明成片确实出自当前源码。（实测：两个 MD5 相同 → 成片可信。）

### 交付总览图：把「反抽帧复核」做成一张图，而不是一串数据点

反抽帧复核如果只输出「12 个点全部符合」这句话，用户无法验证。
做法：从**编码后的成片**抽 12 个关键镜头，拼成一张带标注的总览图，
每格写「镜头号 + 这轮改了什么 + 时间点」。

产出效果：用户一眼就能核「我要的那几处到底进片了没有」，
比给一串时间戳和数据点有说服力得多。用 PIL 拼即可（4 列 × N 行，格间加金色细框）。

**注意抽帧源必须是编码后的成片**，不是 `__render(t)` 的渲染结果 ——
前者才能证明「压进 H.264 之后仍然正确」（比如渐变是否被色度采样糊掉）。

### 做编码前后 PSNR 比对时，先确认帧对齐

拿「渲染帧 PNG」和「成片反抽帧 PNG」逐像素比对（PSNR）是量化编码损耗的好办法，
但**两个坑会让结论完全反过来**：

1. **抽帧时刻 ≠ 帧号**。`ffmpeg -ss <t>` 抽出的帧与 `frames/f-NNNNN.png` 的对应关系要换算：
   `idx = int(round(t * fps)) + 1` —— image2 的 `f-%05d.png` **从 1 开始**，别少加这个 1，
   更别把文件名里的**镜号**（`v-08_57.8.png` 的 `08`）当成帧号用（我这么错过一次，
   全片 PSNR 从 41 dB 假摔到 14.5 dB，看起来像「编码烂了」）。
2. **运动中的画面差 1 帧就差很多**。元素正在入场/位移的那一秒，
   即使对齐正确也可能只有 25–33 dB。**判定前先做 ±3 帧对齐搜索**：

```python
best = max((psnr_at(base+off), base+off) for off in range(-3, 4))
```

若最佳对齐能到 40 dB 以上，就是帧偏差而非编码劣化。
静态画面（动画已停）用基准对齐即可得到 40–43 dB 的良好值。

## 交付前的「成片闭环验收」四项（每一项都必须从**成片或帧序列**复测）

渲染前把页面质量问题修干净只是上半场。渲染完成、编码出 mp4 之后，
还必须对这四件事各给一个数字 —— **它们全都在「渲染前静帧」里看不出来**：

| # | 检查 | 工具 | 判据 | 实测（256s 竖版片） |
|---|---|---|---|---|
| 1 | **逐帧画幅一致** | 读 PNG 头（见下） | 全部帧 = 目标画幅 | 7696/7696 = 1080×1920 |
| 2 | **成片反抽帧 PSNR** | `verify_mp4.py` | > 33 dB | 15 镜 41.0~42.4 dB |
| 3 | **转场溶解塌陷** | `check_dissolve_frames.py` | < 6% | 14 处最大 2.1% |
| 4 | **冻结段** | `check_motion.py` | 无「2s 内可见变化 <0.5%」段 | 无（最安静处 5.03%） |

### 1. 逐帧画幅校验：编码前必须挡住「整片静默变形」

这是本类项目**最贵的一课**：局部重渲工具的画幅默认值若与 `render.cjs` 不一致，
331 帧会以**竖版尺寸**写进**横版**序列，ffmpeg 按首帧统一缩放 →
**整片静默变成竖版**。画面看着正常，只有规格错；PSNR 从 41 dB 掉到 33 dB 才露出马脚。

**不要依赖 ffmpeg 报的首帧尺寸**（它只读第一帧）。独立读每个 PNG 的文件头：

```python
import struct, glob
sizes = {}
for p in sorted(glob.glob('frames/f-*.png')):
    with open(p, 'rb') as f:
        w, h = struct.unpack('>II', f.read(24)[16:24])
    sizes[(w, h)] = sizes.get((w, h), 0) + 1
assert len(sizes) == 1, '画幅不一致: %s' % sizes      # 多于一种尺寸就地失败
```

两道守卫配合：① 局部重渲脚本的画幅默认值与 `render.cjs` **同源**（单点定义 `VW`/`VH`）；
② 编码前跑上面这段**逐帧校验**。只有一道都可能在某个组合下漏过去。

### 2~4 的顺序与取样点

- 抽帧取样点**从 SUBS 表取字幕中点**，不要凭印象取整 —— 与 `verify_mp4.py` 的取样一致。
- **必须从编码后的成片反抽帧**，不能只看渲染前的静帧：前者才能证明「压进 H.264 之后仍然正确」。
- 塌陷与冻结这两项读的是 `frames/` 帧序列（编码器输入），改完立刻能验，不必等成片。

> 一句话：**「渲染跑完了」不等于「片子对了」**。
> 四项里任何一项没有数字，就不能说这一片交付了。

## 「每次转场画面都暗一下」：交叉溶解的合成陷阱（2026-10 实测，本类问题最贵）

多图层交叉溶解（cross-dissolve）时，最自然的写法是「相邻两层各自做淡入淡出」：
前一层 `opacity` 从 1 降到 0，后一层从 0 升到 1。看上去两层权重相加恒为 1，
**但合成不是相加**。设上层权重 x、下层 1−x，画面窗底色的透出量是：

```
合成结果 = x·B + (1−x)²·A + x(1−x)·背景色
```

中点 `x = 0.5` 时，**有 25% 的画面窗底色从两层之间透出来**。
背景通常比画面暗得多，于是每次转场中途画面都会「暗一下」——
一次两次看不出来，15 处转场反复发生就变成一种说不出的廉价感。

**实测**（不是推断）：画面窗平均明度，两侧平台 0.373 → 溶解中点 **0.278**，
**塌陷 25.5%**。改成正确写法后中点回到 0.356，成片复测 14 处交接**最大 2.1%**。

### 正确写法：下层恒不透明，只让上层淡入

后入场的镜头在 DOM 里本来就在上层（`z-index` 递增），所以：

```js
// ✓ 下层恒 opacity=1，只有上层在淡入 —— 合成即 x·B + (1−x)·A，严格线性
L.style.opacity = isTop ? x.toFixed(4) : '1';
```

如果画面窗有底色/底图垫底，两层透明度相加为 1 也不会漏 —— **但前提是底层那层必须真的存在且不透明**。
多层（≥3 层）叠加时逐层回推同一公式，**每一层都只有最上面那层在动**。

### 连带要改的一件事：「当前是哪一镜」不能用权重 argmax

改成「下层恒 1」之后，若还用 `argmax(权重)` 判断「当前镜头」来决定标题/数据带显示什么，
argmax 会在转场期间**停留在旧镜**（因为旧镜恒为 1），表现是**标题晚半秒才换**。
判据要改成**「已经开播的最新一镜」**（按 `st` 找最新的已入场镜头）。

### 怎么量（`check_dissolve_frames.py --selftest`）

不能靠看。判据是：溶解中点亮度应等于**两端按权重插值的期望值**，低于它才叫塌陷。

```python
# 在边界的 st/et 交接时刻前后对称取样（窗口 1.6s，避开 XF 区间）
expect = (v_left + v_right) / 2
dip    = (expect - v_mid) / expect * 100      # > 6% 就算肉眼可见
```

**两个必须避开的度量陷阱**（我两条都踩过，各造出一个假警报）：

1. **明度必须用 R/G/B 的算术均值**。用 `max(RGB)` 是非线性的 ——
   `max(w·a + (1−w)·b) ≠ w·max(a) + (1−w)·max(b)`，会凭空算出几个百分点的假塌陷
   （实测把 2.1% 报成 7.0%）。
2. **「应有的中点」要按权重插值算，不能拿两端帧的算术平均当基线**。两者只在
   权重恰为 0.5 且两端亮度相等时才一致；两端亮度差大时（如 0.509 vs 0.195）
   基线取错会得到一个纯粹是「两张图亮度不同」的假塌陷。

双向自检要覆盖这两点：正例（两层各自淡出）必须被检出 ~26%，
反例（纯线性交叉）必须是 **0.00%** —— 反例不归零就说明尺子坏了。

`probe_dissolve.cjs` + `audit_dissolve.py` 是改前/改后的**在线页面**版本
（不依赖渲染完，改完立刻能验证），`check_dissolve_frames.py` 是**成片/帧序列**版本，
两者配合：一个用于迭代，一个用于交付前复核。

## 改 HTML 结构后必查：动画选择器还选得中吗

最阴险的一类 bug —— **元素永久隐身，但没有任何报错**。

场景：把 `<div class="tag">` 换成不带类名的 `<div style="...">`，
但入场动画仍在写 `st.querySelectorAll('#s12c .tag').forEach(...)`。
选择器匹配 0 个元素，那些元素的 `opacity:0` 初始态**永远不会被改成 1**
→ 整块内容不显示。渲染不报错、控制台不报错、连「文本内容存在」的校验都会通过。

症状识别：**某镜头只剩标题，列表/卡片全不见**。

已沉淀为 `assets/scan_selector_mismatch.py`，改结构后跑一次：

```bash
python scan_selector_mismatch.py index.html --verbose
```

修法二选一：给元素加回可选中类名（推荐，改动小），或让选择器与新结构对齐。
**预防**：改 HTML 结构时把「结构」与「选择器」当一对耦合的东西一起改。

### ⚠️ 检查工具自己也会错：必须用人为反例做双向验证

这个脚本在一个项目里**连续暴露三处 bug**，每处都会给出虚假的安全感或虚假的警报：

| # | bug | 表现 | 根因 |
|---|---|---|---|
| 1 | 正则 `\#` 是非法转义 | 只匹配到 4/16 个调用 | Python 字符串里 `\#` 无意义 |
| 1b | 兜底规则过宽 | **任何容器都判通过** | 判定逻辑写成了「容器名看起来对就行」 |
| 2 | 字符类 `[> ]` 含空格 | `#id .cls`（空格版）匹配不上 | 字符类里 `>` 和空格被当成同一类 |
| 3 | CSS 注释被当镜头段 | 正片误报「有 opacity:0 但无动画」 | `<style>` 里写 `/* S12 xxx */` 撞上了镜头切分规则 |
| 4 | `> .cls` 被当标签选择器 | 正片误报 `#s23v > .vscard` 不存在 | 分支判断先判 `comb` 后判 `is_class` |

**教训**：任何「检查器 / 校验器 / 断言」都必须做**双向验证** ——

```bash
# A. 正片必须通过、退出码 0
python scan_selector_mismatch.py index.html; echo $?

# B. 人为造一个反例，必须被抓到、退出码 1
python -c "
import io; s=io.open('index.html',encoding='utf-8').read()
b=s.replace(\"#s23v > .vscard\", \"#s23v > .zzz\"); io.open('_neg.html','w',encoding='utf-8').write(b)"
python scan_selector_mismatch.py _neg.html; echo $?
```

只做 A 不做 B，你得到的可能是一个**永远说「通过」的废工具**（bug #1b 就是这样）。
修完 bug 后必须重跑 A + B，两边都符合预期才算修好。

同理适用于 `check_overflow.cjs`、`probe_styles.cjs` 等所有质检脚本。

### ⚠️ 验收脚本要「先在测试片上跑通再信它」—— `verify_mp4.py` 上挖出 7 个假绿灯

双向验证还不够：**验收脚本本身要先在一个已知结果的「测试片」上跑通**。
本轮我在正式交付前拿一个 4 秒的测试片试跑 `verify_mp4.py`，一下暴露 7 个缺陷 ——
**每一个都会让验收给出「通过」，而实际上什么都没验**：

| # | 缺陷 | 表现 | 修法 |
|---|---|---|---|
| 1 | 字幕表用 `json.loads(片段.replace("'",'"'))` 解析 | 遇到**数组尾逗号**（`[…],\n];`，极常见写法）抛 JSONDecodeError → 整个验收脚本用不了 | 改逐条正则取三元组（对两种引号、尾逗号、正文里的引号都免疫） |
| 2 | 镜头表字段写死 `s.s` / `s.e` | 工程用 `s.st` / `s.et` → `[[null,null],…]` → 抛异常 → 静默回退正则 → **镜头 0 个，却照样 exit 0 报通过（最低 PSNR 显示 999 dB）** | 两种字段名都认：`s.st!==undefined?s.st:s.s` |
| 3 | `node -e` 内联脚本传参 | `\\\\/g` 穿过 Python + shell 两层后到 node 变成非法转义 → 语法错误、stdout 为空、**不抛异常** | JS 写成临时 `.cjs` 文件再执行，绕开整类转义问题 |
| 4 | Chrome 默认路径写成 `%LOCALAPPDATA%\Google\Chrome\…` | 本机 Chrome 在 `C:\Program Files\Google\Chrome\…`（`LOCALAPPDATA` 是 `AppData\Local`，**是两回事**）→ launch 直接失败 | `PROGRAMFILES → PROGRAMFILES(X86) → LOCALAPPDATA` 回退链 |
| 5 | Chrome `userDataDir` 与 `render.cjs` 共用 | **渲染期间跑验收必失败**：`browser is already running for …` | 每个脚本用自己专用的 profile 目录名 |
| 6 | node 进程跑了但没输出 | 不进 except、不报警、静默跳过 | 出声 + 打 node 的 stderr + 回显实际用的 Chrome 路径 |
| 7 | 镜头表为空没有守卫 | 0 个样本 = 一个点都没采样 = 什么都没验，却报通过 | **硬守卫：镜头表为空直接 `exit 4`** |

**可迁移的三条**：

1. **「量到 0 个对象」必须报错，不能报通过。** 这是最坑的一类假绿灯 —— 它伪装成
   「全部合格」。所有采样型脚本都要加这条守卫（`probe_cards.cjs` 也踩过：
   判据含 `!shots.length` → 老工程没有 `window.__shots` → 被当静态页 → 停在初始态量到 0 张卡仍报 ✓）。
2. **退出码要分级**，让调用方能区分「没通过」和「没跑起来」：
   `0` 通过 / `1` 有不合格项 / `2` 输入不足（如测试片太短）/ `4` 采不到必需数据（**不是通过**）。
3. **内联 `node -e` 是系统性坑**（转义两层 + 静默失败），一律改写成 `.cjs` 文件。

> 同一条原则也适用于**渲染前置检查**：`render.cjs` 只报「`__render` 超时」，
> 不告诉你为什么 —— 所以才有 `diagnose.cjs`（见工具表）。

### ⚠️ 静默失效的七类：CSS 侧、撑破、文字裁剪、测不准、图片未就绪、竖向挤出

上面那个脚本查的是 **JS 侧**。还有四类同样不报错、只让画面悄悄变差的坑，
已沉淀为 `assets/scan_css_layout.py`（前两类，静态）+ 下面的 DOM 检查（后两类）。

**1. 后代选择器的祖先类不存在 → 整条 CSS 规则失效**

```css
.step .sn{width:66px;height:66px;border-radius:50%}   /* ← HTML 里没有 .step */
```
HTML 那些容器走的是**内联 flex**（`style="display:flex..."`），从没写过 `class="step"`。
结果：规则一条都没应用，金色圆点塌成默认 16px 文本 ——
`getBoundingClientRect()` 实测 **9×24px**，而肉眼在 50% 缩略图里只会觉得「圆点好像小了点」。

**判据**：任何 `.A .B` 形态的规则，`.A` 必须能在 HTML 的 class 里找到。
注意 `<style>` 里的注释要先剥掉，否则 `/* 不能写成 .step .sn */` 这种说明文字
会被正则当成选择器，产生假警报。

**2. flex column + `align-items:center` 下，`nowrap` 文案会把卡片撑破安全区**

`.stage` 是 `flex-direction:column; align-items:center` 时，子项宽度由**内容**决定。
一条 `white-space:nowrap` 的长文案 + 卡片 padding，就会让卡片比安全区更宽：

```
实测：卡宽 944px，安全区只有 904px → 左边缘跑到 x=68（应 ≥88）
```

肉眼看不出「差 20px」，但截图时会发现卡片贴到屏幕边上。
**修法双保险**：① 卡片类统一 `max-width:100%`（防御性，一次性加给 `.card/.rrow/.grp/.tag`）
② 收短 nowrap 文案。

**3. 元素外框在界内，但内部文字被裁 —— 几何边界查不出来**

`.card` 的 rect 完全合法，里面那行字却顶到边框甚至被切掉。
必须单独查文字溢出：

```js
el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2
```

对 `.fx/.t1/.t2/.t3/.h1/.h2/.h3/.cn/.sub/.v/.rval/.num/.chip/.lb` 逐个扫。
典型症状：`入口位次 − 加工位次 = 低进高出指数` 五段挤在一行，
最后一个「数」字贴着卡片右边框 —— 拆成两行就好了。

**4. 用 A/B 双图测「卡片 vs 背景」明度时，不能用 `visibility:hidden`**

判据是「元素区域 HSV 明度均值 > 同期背景 + 0.15」。
做法：拍一张正常画面 A，再拍一张只留背景的 B，逐点比。
但隐藏 `#root` 时**不能用 `visibility:hidden`** ——
`__render` 每帧会给 `.shot` 写内联 `visibility:visible`，
**内联值会覆盖祖先的 `hidden`**，于是 B 图跟 A 图一模一样，
所有 Δ 恒等于 **+0.000**，看起来像「卡片毫无对比度」，其实是测量失效。

正确做法：`display:none`。并且**必须加自检**：

```python
if rows and all(abs(d) < 1e-9 for d in deltas):
    print('测量失效：A/B 逐点相同，结论不可信'); sys.exit(2)
```

**5. 数字滚动元素不要依赖 class 进动画列表**

把 `data-cnt="570"` 挂在 `.num` 上、`.an` 挂在父级 `.duo` 上，
`querySelectorAll('.an')` 就采不到那个数字 → 数字永远停在初始值 `0`。
**修法**：计数元素单独收集，延迟自动向上找最近的 `.an`：

```js
function nearestDelay(node){
  let p = node.parentElement;
  while (p && p !== document.body){
    if (p.classList.contains('an')) return +(p.dataset.d || 0) + 0.30;
    p = p.parentElement;
  }
  return 0.30;
}
```

**6. 用了 `<img>` 素材后，必须把「图片加载完成」并入就绪等待**

只等 `document.fonts.ready` 是不够的：

```js
/* index.html 末尾 */
var __pend = [];
if (document.fonts && document.fonts.ready) __pend.push(document.fonts.ready);
[].slice.call(document.images).forEach(function (im) {
  if (im.complete && im.naturalWidth) return;
  __pend.push(new Promise(function (r) { im.onload = r; im.onerror = r; }));
});
Promise.all(__pend).then(function () { window.__fontsReady = true; });
```

症状：**该位置是空白**，其他元素都正常 —— 而且不报任何错。
`page.goto(url, { waitUntil: 'load' })` 也**不足以**保证图片 decode 完成。
两个细节不能省：① `if (im.complete && im.naturalWidth) return;` 跳过已缓存的，
② `im.onerror = r` —— 路径写错时 Promise 永不 resolve，整个渲染会卡到超时。
`{ timeout: 20000 }` 是最后一道保险。

素材路径用**相对路径**（`crest/school-a.png`）即可，
`file://` 下会正确解析；渲染参数里已有 `--allow-file-access-from-files`。

这样以后新增数字卡不必记得补 class，也就不会再漏。

**7. 外框在界内、文字也没被水平裁掉，却被「竖向」挤出所属卡片**

`justify-content:center` + 卡片被 flex 拉伸（`align-items:stretch`）时，
内部内容可能超出卡片上下边界。第 3 条的 `scrollWidth > clientWidth` 查不到它 ——
那是**横向**的判据。要拿文字 rect 和最近的卡片祖先 rect 直接比：

```js
const card = el.closest('.card,.ncard,.chip');
if (card && card !== el) {
  const rc = card.getBoundingClientRect(), re = el.getBoundingClientRect();
  const dTop = rc.top - re.top, dBot = re.bottom - rc.bottom;   // >2 即越界
}
```

**双向验证要选对反例**（这条差点骗过我）：
把 `.t3` 字号从 31px 灌到 190px **测不出这一项** —— 卡片会自己长高，
结果报的是「外框越界」。必须**给卡片固定高度**（`height:60px`）才会真正触发，
实测报 `top=-14 bot=+65`，这才证明判据有效。

## ⑧ 从零起手一个新项目：最容易踩的那些坑（2026-10 实测）

前面七类是「改造已有成片」的坑。以下九条是**从 SRT 起步、再到改视觉**时才会遇到的，
症状隐蔽得多 —— 首版渲染完全正常，只是「看着有点怪」或「数据在骗人」。

### 8.1 IIFE 结尾的 `})();` 和 `});` 不是一回事

```js
(function(){ ... })();   // ✅ IIFE 立即执行，结尾是 }); + 加上 ();  = ")();"
(function(){ ... })      // ⚠️ 语法对，但下一个 ( 会接上来
arr.forEach((x,i)=>{     // ⚠️ 若上一行没分号，这里被解析成「调用 forEach 的返回值」
  ...
})();                   // ❌ 多了一个 ()，报错 forEach(...) is not a function
});                      // ✅ forEach 正确的收尾是 });（闭合箭头函数 + 闭合调用 + 分号）
```

**报错信息完全指不到真因**：`SCHOOLS.forEach(...) is not a function` 会让人以为是数据问题，
去查 SCHOOLS 本身 —— 但它完全正常。

**怎么快速定位**（比逐行读快十倍）：

```bash
# 1. 先证明语法没问题（排除解析错误）
node -e "const fs=require('fs');new Function(fs.readFileSync('index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1]);console.log('语法OK')"
# 2. 语法 OK 但运行时报错 → 就是分号/IIFE 收尾问题
```

配套的**页面级错误捕获脚本**（比 render.cjs 的一句 `waitForFunction` 超时有用得多）：
必须挂 `pageerror` / `console` / `requestfailed` 三个监听，再打印 `typeof window.__render`。
`Waiting failed: 30000ms exceeded` 只说明契约没建立，**不告诉你为什么**。

### 8.2 `SCHOOLS.forEach` 里用 `add()` 建镜头 → 镜头表在源码里只有 1 个调用点

用循环批量生成同构镜头（5 所学校各一个）是正确做法，但要注意：
**`add(` 的字符串计数不等于镜头数**。真实关系是「调用点数 + forEach 展开数」。

落盘前校验若写成 `html.count('add(') == 13`，会因为只有 10 处 `add(`（9 个调用 + 1 个函数定义）
而**永远失败**；写成 `== 10` 又是把 forEach 展开数写死了，换个学校数量就失效。

**正确写法**：用正则数**调用点**，并把展开关系写进断言描述：

```python
calls = len(re.findall(r'^\s*add\(', h, re.M))   # 调用点数
# 断言写成：调用点 9 个（其中 1 个在 forEach 内，展开为 5 个镜头 → 实际 13 镜头）
```

### 8.3 `flex-direction:column` + `align-items:center` 下，`width:100%` 不等于父宽

这是横向溢出最常见的根因，而且**量出来的是 36–38px 这种「看起来无所谓」的小溢出**，
很容易放过。

```css
.stage{display:flex;flex-direction:column;align-items:center}
/* 下面这张卡会溢出右侧 38px： */
.card{width:100%;padding:28px 32px 28px 42px}   /* content-box：100% + 左右 padding 74px */
```

**`width:100%` 在 flex 子项上按 content-box 算，padding 加在宽度之外**。
`align-items:center` 又让宽度由内容决定，于是「最宽行 + padding」一起撑破。

**双保险修法**（两个都要）：

```css
.card{box-sizing:border-box;max-width:100%;min-width:0}
```

再给 flex 容器里的卡片**显式 `max-width`**（= 容器内容宽，不含 padding）。
只加 `box-sizing` 不够 —— 内容过长时卡片仍会顶到 `max-width:100%` 的边界，
而 `max-width` 显式值能把溢出量精确收住。

> 这条与上文「自适应宽度卡片的『最宽行决定宽度』陷阱」是**同一个病根的两种表现**：
> 卡片宽度由内容决定。加 `box-sizing` 是通用兜底，锁 `max-width` 是精确控制。

### 8.4 常驻章节轨的语义必须与镜头内容对齐

底部章节轨是最容易「数据对、语义错」的地方 —— 数值全对，但高亮的章节和画面内容无关。

真实事故：5 所学校用 5 个轨位，`CHAP_SPAN` 最后一段写成 `[158.6, 229.1]`，
结果「规律总结」「第一件事校内排名」「结尾对比」三个语义段全被归到第 5 章（学校段）。
数据核对完全看不出问题，只有把帧和轨位放一起看才发现。

**修法**：轨位数 = **语义段数**，不是「学校数」；两者不是同一个维度就要拆开。

```js
const CHAP_SPAN = [                       // 7 段，与 7 个轨位一一对应
  [33.3, 68.6],      // 学校 1
  [68.6, 95.0],      // 学校 2
  [95.0, 117.1],     // 学校 3
  [117.1, 137.933],  // 学校 4
  [137.933,158.633], // 学校 5
  [158.633, 180.7],  // 规律总结
  [180.7, 229.133]   // 行动建议 + 结尾
];
```

轨位加到 7 个后要**同步收窄**（竖屏宽度吃紧）：

```css
#rail .ri{width:92px;flex:0 0 92px}      /* 7×92 + 6×gap14 = 728px，留足边距 */
#rail .ri .rb{width:92px}                 /* 底条宽度必须跟着改，否则与章号不对齐 */
```

**自查**：抽一帧**不属于任何学校**的镜头（比如总结段），看轨位高亮落在哪。
落在「最后一个学校」上就是错的。

### 8.5 字幕里放 `<br>` 断行 → `textContent` 会把它当纯文本渲染出来

**症状**：画面上 literally 显示 `相差93分<br>它可以理解成…`，肉眼一看就知道坏了。

**根因**：`subEl.textContent = SUBS[idx][2]` —— `textContent` **不解析 HTML**。
我为了解决「长字幕在竖屏随机折行、末行只剩 1–2 字」而往 SUBS 里插了 `<br>`，
两条路刚好互相打架。

**修法**：`innerHTML` + **先转义再放行自己的 `<br>`**（别直接插，防注入）：

```js
subEl.innerHTML = SUBS[idx][2]
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/&lt;br\/?&gt;/g, '<br>');
```

**为什么这一条特别值得记**：
它是**「反抽帧验收」唯一抓到的 bug**。渲染阶段所有检查全绿 ——
覆盖率 48%、横向溢出 0、空转 0s、语法 OK、契约完整、字体 loaded。
只有把成片 mp4 反抽帧、放大看字幕条，才看见 `<br>` 三个字符躺在画面上。

> **教训**：`<br>` 断行是「渲染前看不出、成片里一眼看见」的典型。
> 验收必须从**编码后的成片**抽帧，抽 `__render(t)` 的结果不算验收。

### 8.6 从成片反抽帧时，ffprobe 路径不能用字符串 replace 推导

```python
# ✗ 错：路径里含 "ffmpeg" 字样（ffmpeg-9.0.2-full_build），
#   .replace('ffmpeg','ffprobe') 会把**目录名**一起改掉
FFPROBE = FFMPEG.replace('ffmpeg.exe','ffprobe.exe').replace('ffmpeg','ffprobe')
# → .../ffprobe-9.0.2-full_build/bin/ffprobe.exe  ← 不存在

# ✓ 对：ffprobe 就在同目录
FFPROBE = os.path.join(os.path.dirname(FFMPEG),
                       'ffprobe.exe' if os.name == 'nt' else 'ffprobe')
if not os.path.exists(FFPROBE): raise SystemExit('请设 FFPROBE')
```

这个 bug 表现为 `FileNotFoundError: [WinError 2]`，
**发生在 PSNR 全部算完之后**，很容易让人以为前面的数据也不可信。
顺手把 `if not os.path.exists(FFPROBE): raise` 放在**函数顶部**，别等到最后一步才炸。

### 8.7 验收脚本自己也要用「与渲染同一份数据」拿镜头表

反抽帧要按镜头取样，而**镜头表不能只靠正则解析 `add(数字, 数字, ...)`** ——
用 `SCHOOLS.forEach` 批量生成的镜头调用的是 `add(S0, S1, ...)`（变量），
正则一个都匹配不到。实测 13 个镜头只解析出 8 个，**且不报任何错**。

**正确做法**：从页面里直接读，与渲染走同一份数据。

```js
// index.html 里暴露一份（比正则可靠得多）
window.__shots = shots;      // [{s, e, ...}, ...]
```

```python
# verify_mp4.py 里用 puppeteer 读一次
r = subprocess.run([node, '-e', js], capture_output=True, text=True, env=...)
shots = [(float(a), float(b)) for a, b in json.loads(json.loads(r.stdout.strip().split('\n')[-1]))]
print('镜头 %d 个（来源：window.__shots）' % len(shots))
```

**加一条断言**：`len(shots)` 要与页面上 `.shot` 的实际数量一致。
不一致说明解析器漏了镜头，**宁可中止也不能用不完整的镜头表做验收** ——
少验 5 个镜头却报告「全部 ok」，比不验更危险。

### 8.8 顺带一条：落盘校验的断言值不要凭记忆填

写「`max-width:880px` 恰好 4 处」时，**真实数量可能已经是 8**（前一轮脚本部分落盘、
或同一值在多处复用）。断言写成 `== 4` 会让脚本永远失败，而人会去改断言迁就脚本。

**正确做法**：数值型断言先 `print` 实际值再决定用 `==` 还是 `>=`；
结构型断言（镜头数、SUBS 条数、契约字段是否存在）才用精确 `==`。
判据是「**这个数字错了会不会导致成片出错**」—— 会，才值得精确断言。

### 8.9 `flex-basis` 会盖掉 `width` —— 数据对比条永远等长

**这是数据可视化里最难发现的一类 bug：视觉上完全像模像样，只有量长度才发现。**

```html
<!-- ❌ 两条都是 720px，两个悬殊的数值看起来一样长 -->
<div class="bar" style="flex:0 0 720px;width:${tw}px"></div>
<!-- ✅ flex-basis 用实际条宽 -->
<div class="bar" style="flex:0 0 ${tw}px"></div>
```

`flex` 简写的第二三个值就是 `flex-basis`，**它的优先级高于 `width`**。
写 `flex:0 0 720px` 的同时写 `width:420px`，浏览器取 720px。

**为什么特别危险**：崩的不是"看起来不对"，而是"看起来对"——
两条柱子都有正确的颜色、圆角、渐变、高光，长度也"差不多"，
**唯一的问题是它们的长度不表达数值**。对比条的全部意义就此归零。

**自查**（写数据条后必做）：

```js
// 量两条的实际宽度，差值应该与数值差成比例
const bs = [...document.querySelectorAll('.bar')].map(b => b.getBoundingClientRect().width);
console.assert(Math.abs(bs[0] - bs[1]) > 20, '两条对比条宽度几乎相同 —— 检查 flex-basis 是否盖掉了 width');
```

实测：修前 720 / 720 px，修后 **625 / 489 px** —— 按量程换算后的应有宽度。

### 8.10 卡片高度不足时，四角装饰线会**侵入内容区**

SKILL.md 前面记过「卡片小于约 62px 时角线会互相撞上」—— 那是**宽度**方向。
高度方向同样会出事，而且更隐蔽：

```
镜14 的三张数据卡：宽 283px，高 192px，角线长 44px
→ 「左下角横线」落在距卡底 45px 处，而卡内文字正好在这个高度
→ 一条金线横穿「录取数据」四个字
```

**判据**：角线长度 > 卡片高 × 0.22 时就会侵入内容。**卡高 < 约 240px 就该缩短角线。**

```css
/* 紧凑卡片变体：横排 flex:1 的小卡用它 */
.card.sm::before{background-size:24px 1.6px,1.6px 24px, /* …8 条同比缩小… */;
  background-position:1px 1px,1px 1px,
    calc(100% - 25px) 1px,calc(100% - 2.6px) 1px,
    1px calc(100% - 25px),1px calc(100% - 2.6px),
    calc(100% - 25px) calc(100% - 25px),calc(100% - 2.6px) calc(100% - 2.6px);}
.card.sm::after{inset:8px;border-radius:9px;}   /* 内圈线也要同步收 */
```

**自查**：抽一帧，在卡片区域裁 3–4 倍放大看。1× 下那条线只有 1.6px，
会被当成"卡片的装饰线"而不是 bug —— **必须放大看**。

### 8.11 镜头内「口播句数 vs 视觉事件数」必须配比（比尾部空转更隐蔽）

前面「画面太空怎么诊断」那节讲的是**镜头尾部空转**（最后元素入场到镜头结束的空白）。
但还有一类更隐蔽的问题：**镜头内部**，口播在讲，画面却没动。

真实事故：某镜 22 秒、覆盖 **8 句口播**，但我只放了 6 个元素。
后果是 `[167.4 → 180.7]` 这 **13.3 秒（4 句话）画面完全静止** ——
镜头尾部没有空转（最后一个元素在镜头末尾附近），所以旧诊断查不出来。

**正确判据（三层，缺一不可）**：

| 层 | 检查什么 | 怎么查 |
|---|---|---|
| 1 | 镜头尾部空转 | 最后一个元素的入场时刻 vs 镜头结束 |
| 2 | **镜头内部口播落点** | **镜头内每句口播的起始时刻，画面是否都有变化** |
| 3 | 帧间差实测 | 在同一镜头的「第 1/中/末句落点」各抽一帧，算像素差 |

第 2 层是这次新补的，实现很简单 —— 把镜头内的口播句起始时间列成表，
逐条问自己「这时候画面变了什么」：

```python
# 镜头内每句口播的落点帧
for a, b, txt in subs_in_shot:
    t_luodian = a + 0.6          # 口播起点后 0.6s（元素入场需要一点时间）
    # 抽这一帧，与上一句的落点帧对比
```

第 3 层的判据：**相邻落点帧的平均绝对差 > 0.8（0–255 量程）**。
实测本次 15 镜全部 > 0.8（区间 1.94 – 10.71），修复前的镜 9 有连续 13 秒查不出变化。

**修法**：拆镜头。本次把一个 22 秒的镜头拆成 3 个（5.7s / 10.7s / 13s），
每个镜头内部再按口播句起始时刻错开元素入场 —— 让「每句话都落在一个视觉事件上」。

```js
// 镜头 10：三句口播对应三行入场，T 就是口播相对镜头的起始时刻
// 口播落点（相对 164.333）：167.40→lt=3.07 / 170.33→lt=6.00 / 172.40→lt=8.07
const T = [3.0, 5.9, 7.95];
rows.forEach((r, i) => {
  const u = cl((lt - T[i]) / 0.55);
  r.style.opacity = u;
  r.style.transform = `translateY(${(1 - u) * 28}px)`;
});
```

> **顺带一条经验**：拆镜头时**先算口播边界，再设计元素数量** ——
> 「这一段有几句口播」比「我想画几个卡片」更该是起点。
> 本次两处错配（镜 9 的 8 句配 6 个元素、镜 13 前 6.4 秒讲查询却画对比卡）
> 都是先画了画面、没对口播造成的。

### 8.12 `await document.fonts.ready` 是**空转的** —— 首帧会截到回退字体

`render.cjs` 里原来写的是：

```js
await page.evaluate(() => document.fonts.ready);   // ❌ 什么都没等到
await new Promise(r => setTimeout(r, 400));
```

**`document.fonts.ready` 在「没有任何 pending 字体请求」时会立刻 resolve。**
页面刚加载、所有镜头还都隐藏（opacity 0 / display:none）时没有任何字形被请求 ——
它就是一个立即完成的空 promise。

实测同一个页面（只读 `status`，不调 `check()`）：

| 时刻 | 4 个 @font-face 的状态 |
|---|---|
| 刚加载完 | 全 `unloaded` |
| **抄完上面那段等待（ready + 400ms）** | **仍全 `unloaded`** |
| 渲染第 1 帧后 | 仍全 `unloaded` |
| 显式 `document.fonts.load(...)` 后 | **全 `loaded`** |

后果：文本首次可见的那几帧被以回退字体渲染（`font-display` 默认行为是 block → 甚至直接空白），
**之后**浏览器才发现要加载字体。而且**验收查不出来** —— PSNR 比的是「成片 vs 当前帧序列」，
两边错得一模一样，分数照样漂亮。

正确写法 —— 用每个声明的 face 主动 load 一次：

```js
await page.evaluate(async () => {
  await Promise.all([...document.fonts].map(f =>
    document.fonts.load(`${f.weight} 64px "${f.family}"`, '测试文字0123456789').catch(() => {})));
  await document.fonts.ready;
});
```

> ⚠ **写这个诊断脚本时，我的第一版探针把结论搞反了。**
> 我在测量前调了 `document.fonts.check()` / `canvas.measureText()` ——
> 而**这两个调用本身就会触发字体加载**，于是测出「等待后已加载」，看起来一切正常。
> **测量工具改变了被测对象。**
> 教训：量「某资源有没有加载」时只能用**只读手段**（读 `status`），
> 任何会触发加载的 API 必须放到最后一次再测。

断言要**硬失败**：预热后还有 face 没 loaded 就 `exit 5`。
旧版判据扫的是 `#root *` 里**所有**元素（含未入场的隐藏镜头），必然报一堆假警告 ——
**警告久了就没人看。要么硬失败，要么别报。**

### 8.13 渲染前必须做的三件事（顺序不能换）

```bash
$NODE diagnose.cjs                 # ① 页面有没有抛异常（契约没建立时先跑它）
$NODE render.cjs --test --noenc    # ② 测速 + 顺带验证字体断言通过，估算总时长
md5sum index.html > source.md5     # ③ 记住源码指纹，事后能证明成片出自这份源码
```

② 不只是为了估算 —— 它会在正式渲之前把字体/图片就绪断言跑一遍。
**几十分钟的渲染，宁可在这里多花 1 分钟。**

## 卡片语言：把「商务感」拿掉（图标驱动配方）

客户说「卡片有点商务」时，通常不是配色问题，是**这五条同时反着来**。
逐条改，缺一条就还是商务味：

| 项 | 商务感（改掉） | 图标驱动（改成） |
|---|---|---|
| 描边 | 金色/金属重描边 `.6~.9` | **中性淡白 `rgba(255,255,255,.13)`** |
| 内层线 | `::before` 内缩一圈的「框中框」 | **删掉**（单层边即可） |
| 卡面 | 暖褐/暖炭（`#2A2723` 系） | **冷调中性深灰（`#252A33 → #14171C`）** |
| 圆角 | 22–26 | **28–30（大圆角是主要观感来源）** |
| 顶光 | 暖色 `rgba(255,240,200,.16)` | **中性白 `rgba(255,255,255,.17)`** |

**符号侧要「图标驱动」**：把金属渐变圆牌换成**真实图标/校徽容器**
（圆角方形、深底 `#0D1016`、`object-fit:cover`），尺寸分档：

```
.ci 46px/圆角14（胶囊内）  .gi 62/18（组头前）
.ni 84/24（数字卡内）     .hc 116/34（大标题旁）
```

**语义色不要砍，改走「左侧色条」** —— 整卡彩描边才是商务感的元凶，
但直接删色相又会丢掉「一色一义」。折中：`::before` 做 9px 竖条 + 发光，
卡面只留极淡色晕（顶端 `.24 → 透明`）：

```css
.card::before{display:none}                 /* 原内层金线删掉，腾给语义卡 */
.s-up::before{content:'';position:absolute;left:0;top:26px;bottom:26px;
  width:9px;border-radius:0 6px 6px 0;
  background:linear-gradient(180deg,#FF9189,#D64743);
  box-shadow:0 0 22px rgba(224,80,78,.5)}
```

**暗场里不能照搬浅底参考图**：参考图是「浅灰底 + 白卡」，白卡自带强对比；
暗场里把描边降到 `.085` 后卡片会**看起来塌进背景**（缩略图尤其明显）。
`.13` + `inset 0 1px 0 rgba(255,255,255,.17)` 是暗场下的等价物：
靠**面的明度差 + 上边缘受光**浮起，而不是靠描边。

⚠ **别用缩略图判断卡片「浮不浮」** —— 缩到 340px 宽后 1px 描边直接消失，
会误判成「卡片没对比度」。**必须全分辨率裁图 + 明度量化**（判据 Δ > 0.15）。

### 图标怎么做：内联 SVG，不要 emoji / 图标字体

客户说「多用点图标让画面更好看」时，**不要用 emoji 或图标字体**：

| 方案 | 为什么不选 |
|---|---|
| emoji | 各系统渲染三套字形（Win/Mac/Linux），且**无法用 CSS 染色**，做不了语义变体 |
| 图标字体（woff） | 要额外加载一个字体文件，逐帧渲染下多一次解析；且改色只能靠 `color` |
| **内联 SVG** ✅ | 零加载成本、可被 CSS 的 `stroke` 直接染色、语义变体自动换色、任意缩放不糊 |

```js
/* 图标库：24×24 viewBox，只存路径，颜色交给 CSS */
const ICON = {
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  chart:  '<path d="M4 20V9M10 20V4M16 20v-7M22 20H2"/>',
  seat:   '<rect x="3" y="5" width="18" height="6" rx="1.6"/><rect x="3" y="13" width="8" height="6" rx="1.6"/><rect x="13" y="13" width="8" height="6" rx="1.6"/>',
  /* … */
};
function ico(name, cls, tone) {      // cls: ic(44) / ni(62) / hi(84)，tone: up/td/wr
  return `<div class="${cls}${tone ? ' ' + tone : ''}"><svg viewBox="0 0 24 24" fill="none">${ICON[name] || ''}</svg></div>`;
}
```

```css
.ic,.ni,.hi{display:flex;align-items:center;justify-content:center;flex:0 0 auto;
  border-radius:14px;
  background:linear-gradient(160deg,rgba(255,242,206,.14),rgba(255,255,255,.03));
  border:1px solid rgba(226,203,138,.40);
  box-shadow:inset 0 1px 0 rgba(255,242,206,.26),0 0 20px rgba(214,190,120,.10);}
.ic{width:44px;height:44px;}  .ic svg{width:24px;height:24px;}
.ni{width:62px;height:62px;border-radius:18px;} .ni svg{width:34px;height:34px;}
.hi{width:84px;height:84px;border-radius:22px;} .hi svg{width:46px;height:46px;}
/* 线性图标统一描边 —— 颜色不在 SVG 里写死，交给 CSS */
.ic svg,.ni svg,.hi svg{stroke:#E8D9A8;fill:none;stroke-width:2;
  stroke-linecap:round;stroke-linejoin:round;}
/* 语义变体自动换色：同一个图标在不同语义卡里自己变色 */
.ic.up svg{stroke:#FF9189;} .ni.up svg{stroke:#FF9189;} .hi.up svg{stroke:#FF9189;}
.ic.td svg{stroke:#7FE0C8;} /* …td / wr 同理… */
```

**两条硬规则**：

1. **`svg` 必须显式写宽高**。和前面 `<use href="#symbol">` 那条坑同源 ——
   SVG 没自己的 viewBox 时 `height:auto` 会退回默认 **150px**，图标被拉成飘带。
2. **描边色只写在 CSS 里，不在 SVG 上写 `stroke="…"`**。
   写死了就没法做语义变体，同一个图标在红色卡和青色卡里只能一个颜色。

**图标语义映射表**（一图标一义，和配色一样不能乱）：

| 概念 | 图标 | 概念 | 图标 |
|---|---|---|---|
| 目标 / 重点 | `target` 靶心 | 原因 / 洞察 | `bulb` 灯泡 |
| 数据 / 排名 | `chart` 柱状 | 注意 / 风险 | `warn` 三角 |
| 对比 / 分界 | `scale` 天平 | 可行 / 赢 | `check` 对勾 |
| 名额 / 计划 | `seat` 座位 | 不可行 / 输 | `close` 叉 |
| 竞争 / 观望 | `users` 人群 | 起点 / 统招线 | `flag` 旗 |
| 校内排名 | `rank` 排行 | 趋势 / 波动 | `trend` 折线 |
| 学校 | `school` 校舍 | 时间窗口 | `window` 窗口 |
| 校区 | `campus` 四格 | 前提条件 | `key` 钥匙 |
| 数据 / 查询 | `doc` 文档 | 分差 / 层级 | `layers` 层 |

**图标怎么放**（不是随便撒，而是给视线一个落点）：

- **数字块前面**必须有图标 —— 纯数字没有视觉起点，加了圆牌视线才有地方落（`.ni` 档）
- **每个列表项左侧**一个 `.ic`，右侧配序号徽章 —— 左侧图标表意、右侧徽章表序
- **镜头标题左侧**一个 `.hi` —— 让每个镜头的开头有统一的视觉锚
- **输赢对比**用 `check`（实心金）/ `close`（空心灰）——比写「✓」「✕」字符更立得住

> 一屏里图标不要超过 4 种形态。**同一档尺寸只配一个语义**，
> 否则就成了"贴纸墙"，反而更乱。

## ⑨ 装饰性图形（角花 / 图标 / data URI SVG）—— 一整类「不报错但不显示」的坑

用户说「框线边角都是错误的」「卡片角上加个花纹」时，这类需求看着简单，
实际是**最容易产出"渲染不报错、画面就是没有"的一类**。
以下每条都是 2026-10 实测踩出来的，全部表现为「浏览器不报错，只是不画」。

### 9.1 data URI 的编码只能做一次，且必须交给编码函数统一做

```python
# ❌ 手写 %23，再交给 quote → % 被二次编码成 %25 → 双重编码
COL = '%23E2CB8A'
urllib.parse.quote(svg)          # → stroke='%2523E2CB8A'
# 浏览器拿到 '%2523E2CB8A'，不是合法颜色 → **描边整条不渲染**

# ✅ 源字符串写原始 #，让 quote 去编码（# → %23）
COL = '#E2CB8A'
urllib.parse.quote(svg, safe="/:='<>")
```

**症状极具欺骗性**：SVG 解析没报错、背景图加载成功、`getComputedStyle` 能读到
`background-image` 有值 —— **就是看不见东西**。

**校验必须解码后再判断**（编码形态下的 `stroke='%23E2CB8A'` 是**正确**的）：

```python
back = urllib.parse.unquote(uri[len('url("data:image/svg+xml,'):-2])
assert "stroke='#E2CB8A'" in back, '颜色不是合法 # 值'
```

### 9.2 SVG 的 `transform` 必须是元素的属性，不能拼在标签外

```python
# ❌ transform 落在 <g> 标签**外面** → 不是任何元素的属性 → 被解析器忽略
svg = "<svg ...>" + " transform='scale(-1,1)'" + "<g fill='none'>…</g></svg>"

# ✅ 挂在元素上
svg = "<svg ...><g transform='scale(-1,1)' fill='none'>…</g></svg>"
```

**为什么特别难发现**：我做的四角角花是**沿对角线对称的叶形**，
翻转失效后四片叶子长得几乎一样，肉眼扫过去「角上都有花」就以为对了。
只有**盯着每个角看叶尖朝向**才发现方向没翻。

**自查**：`svg.index('transform=') > svg.index('<g ')` —— transform 必须在 `<g` 之后。

### 9.3 定义了图形但没拼进 SVG —— 只做字符串自检抓不到

```python
outline = "<path d='M4 4 Q … Z'/>"     # 叶形轮廓
parts = [<主脉>, <叶脉>…]
inner = "".join(parts)                   # ❌ outline 忘了放进去
```

结果：画面上只有主脉 + 三条横向叶脉，看起来是**一个 X 交叉线**，
完全没有叶子轮廓。而我的自检当时只检查了「颜色是否合法」，全部通过。

**教训：生成任何图形后，必须渲染出来看一眼。**
字符串层面的自检（颜色合法、path 条数对）覆盖不到「图形有没有画出来」。

```python
# 补一条结构自检：数 path 条数
assert back.count('<path') == 5, '期望 5 条 path（轮廓1+主脉1+叶脉3）'
assert ' Z' in back, '叶形轮廓（闭合 path）缺失'
```

**最快的验证方式**：写一个 8 行的小测试页，把图形放大 2× 渲染截图。
见 `assets/` 里的做法 —— 用 `fetch('index.html')` 把真实 CSS 规则抽出来套到测试盒上，
**避免手抄一份导致测的不是同一个东西**。

### 9.4 CSS 百分比 `background-position` 是「边缘对齐」语义

```
background-position: calc(100% - 8px) 8px
```
意思是**图片右边缘距容器右边缘 8px**，不是「图片左上角在 (100%-8px, 8px)」。

**这条搞反的后果**：我上一版用 8 条 `linear-gradient` 画直线段角标时，
把底部**横线**的 y 写成 `calc(100% - 25px)`（悬在距底 23px 的半空）、
**竖线**的 y 写成 `calc(100% - 2.6px)`（24px 长度全跑到卡外被裁掉）——
底部两角只剩一条悬空横线，用户截图直接圈出来「框线边角都是错误的」。

**自查**：把四个角的装饰分别放大看，**逐个确认它们在角上而不是"附近"**。

### 9.5 固定尺寸的装饰不能靠 `background-size` 拉伸

角花、花纹、徽章这类装饰**必须保持原始宽高比**。
用 `background-size:100% 100%` 铺满会让它们随卡片比例变形
（宽卡上被拉扁、高卡上被拉长）。

```css
/* ✅ 固定尺寸 + 每角定位 */
background-size:48px 48px;
background-position:8px 8px, calc(100% - 8px) 8px,
  8px calc(100% - 8px), calc(100% - 8px) calc(100% - 8px);
```

### 9.6 装饰尺寸要按「容器短边」定档，不是一套用到底

实测：`30px` 的角花放在 `480×520` 的卡上刚好，放到 `880×62` 的排行条上就**挤成一团**
（占了条高的近一半，还和左侧内容图标视觉重叠）。

| 容器短边 | 角花尺寸 | 例子 |
|---|---|---|
| ≥ 400px | 48px | 主卡 |
| 180–400px | 34px | 横排小卡（`flex:1`） |
| < 120px | 22px | 排行条 / 数据条 |

判据：**角花尺寸 ≈ 容器短边 × 0.10–0.12**。

```css
.card::before     {background-size:48px 48px; …}   /* 主卡 */
.card.sm::before  {background-size:34px 34px; …}   /* 紧凑卡 */
.rrow::before     {background-size:22px 22px; …}   /* 排行条 */
```

### 9.7 同一屏里的同类容器要给**同一套**装饰

`.card` 有角花、`.rrow` 没有 → 同屏看起来像两套设计语言。
用户的原话是「很多框线边角都是错误的」，其中一半是这种**不一致**而非位置错。

**做法**：把角花的 4 个 SVG data URI 抽成一份，`.card` / `.rrow` / `.card.sm`
各写一条 `::before`，**只覆盖 `background-size` 与 `background-position`**，
`background-image` 复用同一套。

> 代价：data URI 会在 CSS 里重复出现（本次 8 处引用 / 4 个唯一 URI）。
> 这是可接受的 —— 换来的是「改一处颜色要改 8 个地方」的风险，
> 所以**改色时用脚本批量替换并断言替换次数**。

### 9.8 换上 `<img>` 素材后，**所有**抽帧脚本都要等图片

SKILL.md 前面记过「用了 `<img>` 要把图片加载并入就绪等待」——
但当时只改了 `render.cjs`。这次换上 logo 后，`check.cjs` 抽帧**拍到空白 logo**，
因为它的等待逻辑里只有字体。

**规则**：项目里**每一个**启动 Chrome 的脚本（`render.cjs` / `check.cjs` /
`rerender_range.cjs` / `probe_*.cjs`）都要有同一段「字体 + 图片」等待。
新增素材类型时，grep 一遍所有 `.cjs` 确认没有漏的。

```js
await page.evaluate(() => {
  var pend = [];
  if (document.fonts && document.fonts.ready) pend.push(document.fonts.ready);
  [].slice.call(document.images).forEach(function (im) {
    if (im.complete && im.naturalWidth) return;
    pend.push(new Promise(function (r) { im.onload = r; im.onerror = r; }));
  });
  return Promise.all(pend);
});
```

### 9.9 常驻层之间的位置冲突：用 y 区间算，不要目测

片尾品牌卡（`bottom:236px`）和字幕带（`bottom:150px`）看起来"离得挺远"，
实际算下来：

```
字幕：高 93px（44px 字 × 1.46 行高 + 上下 padding）→ y ∈ [1677, 1770]
品牌卡内容底 = 1920 - 236 = 1684                          → 重叠 7px
```

**做法**：给每个常驻层列出 `y 区间`，确认两两不重叠且留 ≥ 40px 呼吸。
改一个 `bottom` 值就要重算一遍。

### 9.10 品牌 logo 用位图原色，不要套金色滤镜

深色片子里想让 logo 统一成金色很诱人：

```css
/* ❌ 会把 logo 里的红色印章一起染金，丢掉品牌辨识度 */
#toplogo img{filter:sepia(1) saturate(2) hue-rotate(5deg);}
```

品牌资产的价值在**识别**，不在配色统一。原色放上去，必要时只加
`drop-shadow` 让它从背景里浮起来。若 logo 与片子色系冲突，改的是**卡片底色**，不是 logo。

## ⑩ 卡片 / 边框系统：把「角花不能压内容」变成一条可验证的约束

用户的反馈是「边框花纹不能影响里面内容」。这类问题的麻烦在于 ——
**它不报错、不崩溃，而且整体看着「还挺好看」**。翻帧找是不可靠的：
同一张卡在某几句口播时元素还没入场，看着是好的；入场了就压上了。

所以做法是：**先把约束写成数字，再让尺子去验，最后才动样式。** 三步。

### 10.1 尺子：`probe_card.cjs` —— 把「压到了」变成 px²

它逐卡输出四个数：**角花深入量 L/R/T/B、内容内缩 L/R/T/B、安全余量**。

```
t        选择器          卡高   角花  角花深入 L/R/T/B  内容内缩 L/R/T/B   安全余量
202.98   card.s-tu       112    48    56/56/56/56      28/406/24/24      -32px  ✗ 重叠
            ↳ TL 角压住「ni up」 28×32px = 896px²
            ↳ BL 角压住「ni up」 28×24px = 672px²
```

⚠️ **判据必须用「深入量」而不是「角花尺寸」**。24px 的角花画在内缩 5px 处，
实际占掉 29px —— 用尺寸当包络会低估 5px，把本来压住的判成通过。
深入量 = 内缩 + 尺寸，且**要按边分类**：不分类的话右侧角花会被算进左侧，
输出「深入 880px」这种明显荒唐的数（我第一次就写错了）。

⚠️ **尺子自己也要有反例页**：`probe_card_selftest.html` 里放了两个故意违规的卡片
（inline padding 绕开约束 / 角花放大到 60px）。判据是**它必须被抓到并退出码 6**。
如果它在这里报「✓ 无重叠」，说明尺子坏了，正片的结论一律不能信。

> **这条是有血的**：第一版 `probe_card.cjs` 用 `str.split(/\s+/)` 拆
> `background-position`。Chrome 对 `calc()` 返回的是**字符串**，
> `calc(100% - 5px) calc(100% - 5px)` 被拆成
> `['calc(100%','-','5px)','calc(100%','-','5px)']` —— 右下角花被算成 `(856,0)`。
> 于是「右下角压内容」永远查不出来，正片报了个漂亮的「✓ 无重叠」，**是假通过**。
> 修法：按**括号深度**切分。并在脚本里内置 4 个写法的自检
> （`5px 5px` / `calc(100% - 5px) calc(100% - 5px)` / 右上 / 左下），
> 自检不过就退出码 7，不输出任何结论。

### 10.2 约束：三个数写在同一行，就不可能对不上

```
角花边长 O / 内缩 F / 内容边距 P  →  P ≥ O + F + 6
```

写成同一条规则，不从两个地方各改一个数：

```css
/* 档位     O 角花   F 内缩   P 内容边距 = O+F+6 */
.card      {padding:37px 38px;}                    /* 24 + 5 + 8 */
.card.fl-lg{padding:50px 54px;}                    /* 36 + 8 + 6 */
.card.plain{padding:24px 30px;} .card.plain::before{content:none;}  /* 明确不要角花 */
.card::before{background-size:24px 24px;
  background-position:5px 5px, calc(100% - 5px) calc(100% - 5px);}
```

**推论：卡片的 padding 绝对不能写 inline。** 上一版 24 处 inline padding
（`padding:22px 26px` / `30px 16px 26px` / `26px 14px 24px`…）各自绕开了这条约束，
角花就压上了内容。**类决定 padding，inline 一律清除** ——
清除时别用「相邻两属性」的正则（`class="..." ` 紧跟 `style="..."`），
实际标签长这样：`class="card s-gold" id="nt${i}" style="..."`，
`id` 夹在中间会漏。**要按整个标签判断**（我第一次漏了 7 处，第二遍才清干净）。

### 10.3 装不下就不画 —— 「统一」靠边框语言，不靠复制装饰

上一版为了让排行条「和卡片是一套语言」，把四角角花也复制到了 84px 高的 `.rrow` 上。
结果条条压内容：84px 高的行里 2 行文字就占掉大半，四角永远有冲突。

**正确做法**：`.card` 与 `.rrow` 共用**同一套边框语言**（闭合 1px 金边 +
内圈细线 + 右下硬边厚度 + 顶部受光），区别只有圆角、padding 和**有没有角花**。
角花是「大面板」的特权，不是「统一」的手段。

### 10.4 内圈细线用 `box-shadow`，不要用 `::after`

```css
/* ❌ ::after 的 inset 是固定 px，卡片一矮就横穿内容（108px 高的卡被金线穿字） */
.card::after{content:'';position:absolute;inset:11px;border:1px solid rgba(196,170,102,.14);}
/* ✅ box-shadow 的 inset 自动跟随 border-radius，永远贴边、不需要额外元素 */
.card{box-shadow: inset 0 0 0 1px rgba(196,170,102,.11), ...;}
```

顺带：`.card` 如果**根本没写 `border`**，那些 `.s-tu{border-color:...}` 全是**死代码** ——
语义卡的彩边一条都画不出来。语义卡只写 `border-color`（不写 `border-width`）时，
必须在基础类里有 `border:1px solid <fallback>`。

### 10.5 检查项

- [ ] `probe_card.cjs` 正片 **0 重叠、0 余量不足**（退出码 0）
- [ ] `probe_card_selftest.html` **必须被抓到**（退出码 6）—— 尺子双向验证过
- [ ] 卡片 **没有任何 inline padding**（`grep 'class="[^"]*card[^"]*"[^>]*style="[^"]*padding:'` 为 0）
- [ ] 同类容器共用同一套边框语言（`.card` 与 `.rrow` 的 border / radius / 阴影栈一致，只有角花不同）
- [ ] 卡片实验台 `card_lab.html` 已过一眼（所有档位 / 语义色 / 真实用例复刻）

### 10.6 标记区替换会把「注释闭合」一起吃掉 —— 整段规则静默消失

用「标记区 + 正则替换」往 CSS 里注入生成内容（纹样 URI、主题色）时，如果标记长这样：

```css
:root{
  /* <<ORN>> 纹样由生成器填充（可重复运行） */   ← 注意这行末尾的 */
  --orn-grain:none;
  /* <<ORN-END>> */
}
```

正则 `(<<ORN>>)[\s\S]*?(<<ORN-END>>)` 会把**中间的 `*/` 一起消费掉**，
替换后变成：

```css
  /* <<ORN>>
  --orn-grain:url("...");      ← 这三行全在注释里！
  --orn-scroll:url("...");
  /* <<ORN-END>> */
```

**无报错、无异常、CSS 完全合法** —— 只是那几个变量不存在了，
引用它们的 `background-image: var(--orn-div), ...` 整条声明在计算值阶段失效 → `none`。
而同一 `:root` 里**写在注释之前**的变量（`--line` 等）照常生效，
所以「别的变量好用、就这几个不行」，极难定位。

**修法**：替换时把注释闭合补回来 ——
`lambda m: m.group(1) + ' */\n' + block + '\n  /* ' + m.group(2)`。
**防法**：改完立即量一次 `getComputedStyle(root).getPropertyValue('--orn-div')`，
为空就是掉进注释了。

定位这类问题的方法（值得记住）：不要盯着 CSS 文件猜，直接到浏览器里量——

```js
getComputedStyle(document.documentElement).getPropertyValue('--orn-div')   // → "" 说明变量没定义
getComputedStyle(card, '::before').backgroundImage                          // → "none" 说明整条声明失效
```

（顺带排除一个嫌疑：`var()` 引用含 data URI 的变量**本身是可行的**，
半编码 URI 也没问题 —— 我做了三组对照实验才排除它，别在这上面浪费时间。）

### 10.7 度量判据必须跟着纹样形态走

10.1 的「角花深入量 L/R/T/B vs 内容内缩」只对**贴角小纹样**成立。
v5 把纹样改成了**水平通栏**（顶部花饰 620px 居中、底部卷草居中）后，
同一把尺子按四边内缩算，`need.L` 高达 740px → 报了 32 次「余量不足」，全是**误报**
（纹样在顶部带、内容在中部，矩形根本不相交）。

正确判据：**纹样矩形与内容矩形的最近距离**。

```
dx = max(纹样L − 内容R, 内容L − 纹样R)     负值 = x 轴交叠
dy = max(纹样T − 内容B, 内容T − 纹样B)     负值 = y 轴交叠
两轴都交叠 → 重叠；否则间距 = max(dx, dy)
```

这一条对贴角纹样和通栏纹样都成立。**换纹样形态时必须重看判据**，
否则尺子会用旧判据制造一堆假警报（或者更糟：漏报）。

### 10.8 卡面质感配方（对标参考片实测）

「高级感」的三要素，缺一个就显廉价：

| 要素 | 实现 | 说明 |
|---|---|---|
| 颗粒 | SVG `feTurbulence` + `feComponentTransfer/discrete` 阈值 | 真噪声。**阈值化**让只有最亮一档透出 → 稀疏金尘；不阈值化会把黑底洗成灰 |
| 织纹 | 两向 `repeating-linear-gradient`（45°/−45°，1px/4px）交叠 | 透明度 ≤.03，叠出布纹 |
| 边框+辉光 | `border:1px solid rgba(gold,.55)` + `0 0 22px` 与 `0 0 64px` 双层辉光 | 暗金 .30 在暗场里看不见，参考片是**清晰可见的亮金** |

再叠「顶部受光 + 边缘压暗（radial vignette）」让卡面中心微微浮起。
**纯平渐变卡面 = 廉价感的来源**，这一条比换什么颜色都重要。

卷草纹样本身：**对称靠镜像**（只写左半，右半 `transform='translate(W,0) scale(-1,1)'`），
螺旋用「小圆弧串、半径逐段衰减」逼近（比手写贝塞尔可控），
顶部与底部用**同一个参数化花饰**（宽高 / 是否垂直翻转 / 是否加密叶片）——
一套语言上下呼应，比各画各的精致。

## ⚠️ 自适应宽度卡片的「最宽行决定宽度」陷阱

`.stage` 是 flex column + `align-items:center` 时，卡片宽度**由内容决定**。
于是卡内**最宽的那一行会把卡片宽度钉死**，其他行被迫折行：

```
公式卡三行：
  行1 甲位次 − 乙位次      ← 最宽，447px，钉死卡片 ≈ 559px
  行2 = 综合指数
  行3 位次 | 名次 | 差值越大越好   ← 每栏只剩 165px → 折行！
```

症状是「明明每栏字数不多，偏偏最后几个字换行」。
**修法：给卡片显式宽度，别去缩文案**（缩文案会丢语义）：

```html
<div class="card" style="width:100%;max-width:780px">
```

推论：**任何内容自适应宽度的卡片，都要检查「最宽行有没有把别的行挤折行」**。
`probe.cjs` 的文字溢出检查（`scrollWidth > clientWidth`）抓的是元素级裁切，
**抓不到折行** —— 折行得靠 `getBoundingClientRect()` 比对行数或直接看渲染帧。

## 年份/口径类文案：必须跟着数值一起动

带「年份 + 数值」的镜头，若数值在滚动而年份标签按固定时刻切换，
会出现**短暂但真实的口径矛盾** —— 数字已滚到 591，年份还写「2025 年」，
家长截图就会看到「2025 年 591 分」这个不存在的组合。

```js
/* 错：数值与年份各走各的时间轴，中间有一段失配 */
n.textContent = fmt(lp(574, 592, u));
if (lt < 2.7) y.textContent = '2025 年'; else y.textContent = '2026 年';

/* 对：年份由「数值是否到达终点」决定，天然同步 */
const val = Math.round(lp(574, 592, u));
n.textContent = fmt(val);
y.textContent = (val >= 592) ? '2026 年' : '2025 年';
```

做教育/数据类内容时这条尤其重要 —— 这种矛盾会被逐条核对的家长抓到。
**通用规则**：任何「标签描述数值状态」的组合，标签都要从数值派生，而不是独立计时。

## 等距立体场景（3D 等距信息图元素）—— 纯 CSS 3D，不引模型/WebGL

用户甩一张「3D 等距校园/生态模型」参考图问「这种图形元素你能做吗」时：**能**，而且就在现有链路里做。
**不要**上 three.js / 文生 3D 模型 —— `render.cjs` 带 `--disable-gpu`，WebGL 会退回 SwiftShader，
逐帧 4000+ 张的风险和耗时都不划算。CSS 3D 变换走 Skia 软渲染，照常出图、不报错。

现成资产：`assets/iso-scene.html`（圆盘车削基座 + 建筑群 + 玻璃穹顶 + 碟形天线 + 画幅自适应）。
要改就改这份，别从零写。

### 核心几何：两套旋转配方（矩阵推导，别靠试）

世界层 `rotateX(58deg) rotateZ(θ)` 把平面压成俯视等距地面，此时 **+Z = 向上**。体块每个面：

| 面 | 元素尺寸 | transform（`transform-origin: 0 0`） |
|---|---|---|
| 顶面 | w × d | `translateZ(h)` |
| 沿 X 展开的两片墙（在 y=0 / y=d 处） | w × h | `rotateX(90deg)` |
| 沿 Y 展开的两片墙（在 x=0 / x=w 处） | d × h | `rotate3d(1,1,1,120deg)` |

- `rotateX(90deg)` 的映射：X→X，Y→+Z，Z→−Y
- `rotate3d(1,1,1,120deg)` 的映射：X→Y，Y→Z，Z→X（绕 (1,1,1) 转 120° = 轮换置换）

四面墙都建、别只建两面：背面墙被遮挡是正常的，只建两面会在摆动时露空。

### ⚠️ 墙体元素的「上下是反的」

元素 local +Y 映射到世界 +Z，所以**元素的顶边在 3D 里是墙脚，元素的底边才是墙顶**：

- 墙脚压暗 → `linear-gradient(180deg, 暗色, transparent 34%)`
- 檐口亮边 → `linear-gradient(0deg, 亮色, transparent 4%)`

写反了会得到「上暗下亮」的反物理照明，一眼假。

### 窗带纹理（五层叠加，顺序即层次）

```css
background-image:
  linear-gradient(0deg, rgba(210,240,255,.62), transparent 4%),            /* 檐口亮边 */
  linear-gradient(180deg, rgba(3,6,11,.72), transparent 34%),              /* 墙脚压暗 */
  repeating-linear-gradient(90deg, rgba(5,9,16,.88) 0 2px, transparent 2px 16px),        /* 竖框 */
  repeating-linear-gradient(0deg, transparent 0 42px, rgba(6,10,18,.62) 42px 63px),      /* 每 3 层灭 1 层 */
  repeating-linear-gradient(0deg, #FFD79A 0 6px, rgba(16,26,40,.86) 6px 21px);           /* 亮窗带 */
```

- **墙脚压暗别超过 ~34%**：压到 55% 会把矮楼的窗带全吃掉，体块退化成一块「桌面」。
- 必须加「每 3 层灭 1 层」这条，否则四面都是等距金条纹 = 发光蛋糕，很廉价。

### 盘面：多层下沉椭圆 = 车削厚度

CSS 没有圆柱侧面。用 9 层同心椭圆沿 −Z 逐层下沉、半径逐层递减、颜色逐层变暗，
就得到带倒角、有厚度的车削基座。起手参数：层距 12px、半径递减 3.4px。

### 画幅自适应（竖版居中 / 横版靠左留字区）

```js
const LAND = W > H;
const SCALE = LAND ? (1.02 * H) / 955 : (0.92 * W) / 955;   // 955 = 设计稿基准下的元素像素宽
world.style.left = LAND ? '34%' : '50%';
stage.style.perspectiveOrigin = LAND ? '34% 50%' : '50% 42%';
```

- **横版 ≠ 把竖版放大**：横版里元素只占短边（高）的 ~55%、占宽约 54%，右侧整片留给文案。
- 只改 `VIDEO_W/VIDEO_H` 重渲即可，scale 由脚本按画幅算，源码不用改。
- 位移/呼吸写 `translateZ(bob) rotateX(58deg) rotateZ(rot) scale(s)`，
  **scale 放最右**（先缩放局部、后整体位移），这样 `bob` 仍是真实像素。

### 摆动不要转整圈

`rotateZ` 在 −38° ± 13° 正弦摆动 + `translateZ` 11px 呼吸，**周期对齐片长**（PERIOD = 片长），
一镜一个完整循环。转整圈会让天线、连廊、背面墙反向露出破绽。

## 复用现成 3D 图标素材：深蓝聚焦式竖屏方案

> **本节已独立成技能 `icon-spotlight-video`（含模板、15 个抠好的元素、抠图脚本、量化工具链）。**
> 已开源：https://github.com/lyc4614/icon-spotlight-video
> 要做这套版式直接用那个技能，这里只留两条与主链路共享的结论：
>
> - **暗角必须分两层**：重暗角在内容【之下】压背景，轻收边在内容【之上】（≤ .28）。
>   整层盖在内容上时卡片实测明度从 0.266 被压到 0.129，对背景只剩 **+0.062**
>   （判据要 >0.15），卡片直接糊进背景 —— 肉眼发现不了，必须量化。
> - **带羽化透明边的 3D 元素，量化时只取中心 ~52% 的「芯」**。
>   四周半透明像素会把均值拖低，实测把 +0.197 误报成 +0.070。判据按元素类型分：
>   实体卡片 → 全矩形；带羽化元素 → 中心芯；黑底字幕条 → 不判定（靠描边和文字对比立住）。
>
> 详细版式决策、素材抠图的四种失败判据、量化脚本用法见该技能文档。

<details><summary>（已归档的原始章节全文）</summary>

用户给一批「3D 渲染图标」素材片（AI 生成的幻灯片截图也算）时走这条 —— 比每张图都现场生成
更省、风格更统一。素材通常是一张 16:9 图里放一个 3D 元素 + 若干标注文字。

- 模板：`icon-spotlight-video/assets/template.html`（竖屏 1080×1920，深蓝底 + 顶部一束光聚焦）
- 素材准备：`icon-spotlight-video/assets/grid_sheet.py`（网格验片）+ `extract_3d.py`（抠图换底色）

### 版式：两条形态，按内容选

| 形态 | 什么时候用 | 结构 |
|---|---|---|
| A `bullets` | 内容是一条条说明、没有可对比的数字 | 图标 + 下方逐条字幕（左侧圆形序号）|
| B `cards` | 有可对比 / 可量化的数字 | 图标 + 底部数据卡片（沿用既有卡片语言）|

封面另设一档 `hero`：只有大标题 + 元素 + 底部字幕条。两种形态可以在一支片子里混排。

### 背景：深蓝底 + 顶部一束光

- 底色 `linear-gradient(180deg,#16273A,#0F1A28 30%,#0F1A28 72%,#0A101A)`，
  **中部必须有一段是平地纯色**（`#0F1A28`）—— 抠图时把素材底色烘焙成这个值，接缝才看不见。
- 光束用**顶部径向辉光**：`radial-gradient(ellipse 46% 100% at 50% 0%)` + `blur(30px)` + `screen`。
  ⚠️ 不要用 `clip-path` 梯形 —— blur 之后仍留直边，看着像一块实心三角板，不像光。

### ⚠️ 暗角必须分两层（这条最贵）

- `.vig` 放**内容之下**（压背景，可以压到 .86）
- `.vig2` 放**内容之上**（只做四角轻收边，≤ .28）

一整层暗角盖在内容上时，卡片实测明度从 0.29 被压到 0.153，对背景只剩 **+0.08**
（判据要 > 0.15），卡片直接糊进背景看不见。改完必须回测量化，别只靠肉眼。

### 素材抠图：底色替换用「常量偏移」，别做曲面拟合

素材片底色是「上亮下暗 + 顶部集中辉光」的非多项式形状：

- 二次曲面拟合 → 中下部被抬高，底边过度扣除（实测 22–46% 像素被截断）
- IRLS 迭代重拟合 → **下行失控**：拟合面越降越低，最后塌到 ≈0，残差图全亮，判据全废
- 正确做法：`out = img − 外圈环带均值 + 目标底色`（有界、不失控）+ 径向羽化收到纯底色

### ⚠️ 元素裁框：自动定位对这类素材不可靠，用「带坐标网格的验片」人工读

四种自动判据全败，别再试：

1. 亮区行 / 列投影 → 行只要有任何亮点就被计入，标题让主峰从窗口顶就成立，框顶死
2. 亮度阈值 + 连通域 → 顶部辉光整片 > 0.26，和元素连成同一个巨连通域，框吃掉整张片
3. Sobel 梯度 + 连通域 → **标题文字的边缘梯度比 3D 元素更强**（文字是硬边、3D 是软光），先选中标题
4. 按面积 + 中心度打分 → 只能缓解，不能根治

所以：先出一张 **5% 坐标网格的放大验片**（4 张/片，带百分比标注），自己读框写进 `OVERRIDES`。
**这一步别省，比反复调自动算法快得多。**

经验值：元素本体多在中心窗口内；标注气泡常紧贴元素、甚至压在元素上 —— 能收就收，
收不掉的靠外层 mask 羽化淡掉。**不要为了去掉标注去硬裁**，裁掉的是元素本体。

### 宽幅素材要额外放大（`hs`）

从 16:9 片子里切出来的元素多是 2:1 以上的宽幅，竖屏里宽度先被吃满、高度只剩 300–400px，
压不住画面。给每镜一个 `hs`（1.15–1.35）放大到出血，边缘由 mask 羽化 → 不会露硬边。
窄高型素材（如 1800×2009）保持 1。

### 性能：这条链路明显更慢

1080×1920 实测 **0.507 s/帧**（是普通动效的 ~3 倍）。原因：`mix-blend-mode:screen` +
大半径 blur + 1800px 大图解码。3 分钟的片子 ≈ 45 分钟渲染。
把素材先降到 ~1200px 宽再进项目，能省一部分解码开销。

</details>

## 内容侧安全线（做教育/数据类视频时）

- **绝不用程序随机生成的"像二维码的方块"冒充二维码** —— 扫不出来，属于假东西。要么用真实码，要么做明确的虚线占位并标注"上线前替换"。
- 若客户为规避平台审查而不放二维码，**不要自作主张塞回替代引导**（如"去搜索小程序"）——
  那同样会让平台判定为引流话术。只做品牌露出 + 视觉提示，让观众自己判断。
- 画面上的每个数字都要能对得上原始文稿；同一所学校在不同口径下（本部/分校、住宿/走读）必须标全名，否则观众会误读。
- 落版 CTA 不能只说"数据来源"，要给出下一步动作（领资料/留言/互动提问）。
  **例外**：客户明确要求规避审查时可只留品牌卡 —— 此时与已交付物料（如 PDF 里的领取方式）
  不要产生矛盾，否则观众会觉得内容不一致。
