// icon-library.js —— 内联 SVG 图标库（线性风格，24×24 viewBox）
//
// 为什么用内联 SVG 而不是 emoji / 图标字体：
//   ① emoji 在 Win/Mac/Linux 是三套字形，且**无法用 CSS 染色**，做不了语义变体
//   ② 图标字体要额外加载 woff，逐帧渲染下多一次字体解析
//   ③ 内联 SVG 零加载成本、可被 CSS 的 stroke 直接染色、任意缩放不糊
//
// 用法：
//   1) <script src="icon-library.js"></script> 或在页面里内联本文件内容
//   2) 调用 ico(name, cls, tone) 生成图标圆牌
//        cls : 'ic'(44px) | 'ni'(62px) | 'hi'(84px)
//        tone: ''(金) | 'up'(红) | 'td'(青绿) | 'wr'(橙)
//   3) 引入配套 CSS（见文件末）
//
// 两条硬规则：
//   ① svg 必须显式写宽高 —— 没自己的 viewBox 时 height:auto 会退回默认 150px，图标被拉成飘带
//   ② 描边色只写在 CSS 里，不在 SVG 上写 stroke="…" —— 写死了就没法做语义变体
//
// 图标语义映射（一图标一义，和配色一样不能乱用）：
//   target 靶心=目标/重点   chart 柱状=数据/排名    scale 天平=对比/分界
//   seat 座位=名额/计划     users 人群=竞争/观望    rank 排行=校内排名
//   school 校舍=学校        campus 四格=校区        bulb 灯泡=原因/洞察
//   warn 三角=注意/风险     check 对勾=可行/赢      close 叉=不可行/输
//   flag 旗=起点/统招线     trend 折线=趋势/波动    window 窗口=时间窗口
//   key 钥匙=前提条件       doc 文档=数据/查询      layers 层=分差/层级
//   coin 硬币=费用/价值     arrowR 箭头=指向/下一步
const ICON = {
  /* 数据类 */
  target:  '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  chart:   '<path d="M4 20V9M10 20V4M16 20v-7M22 20H2"/>',
  scale:   '<path d="M12 4v16M7 8h10M6 8l-3 6h6zM18 8l-3 6h6z"/>',
  /* 名额 / 分配 */
  seat:    '<rect x="3" y="5" width="18" height="6" rx="1.6"/><rect x="3" y="13" width="8" height="6" rx="1.6"/><rect x="13" y="13" width="8" height="6" rx="1.6"/>',
  users:   '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.4 2.7-5.6 6-5.6s6 2.2 6 5.6"/><circle cx="17.5" cy="9.5" r="2.4"/><path d="M15.5 14.6c2.9.3 5.5 2.2 5.5 5.4"/>',
  rank:    '<path d="M4 6h10M4 12h7M4 18h10"/><path d="M17 4v7M20.5 8 17 11 13.5 8"/>',
  /* 学校 / 建筑 */
  school:  '<path d="M12 3 2 8l10 5 10-5z"/><path d="M5 10v6.5c0 1.4 3.1 3 7 3s7-1.6 7-3V10"/><path d="M21 8.5V15"/>',
  campus:  '<rect x="3" y="4" width="7" height="7" rx="1"/><rect x="14" y="4" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  /* 结论 / 提示 */
  bulb:    '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.3 1 2.1h5c0-.8.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
  warn:    '<path d="M12 3 2 20h20z"/><path d="M12 9v5M12 17.2v.2"/>',
  check:   '<circle cx="12" cy="12" r="8.5"/><path d="m8.2 12.2 2.6 2.6 5-5.4"/>',
  close:   '<path d="M6 6l12 12M18 6 6 18"/>',
  flag:    '<path d="M5 21V4"/><path d="M5 5h11l-1.8 3.4L16 12H5z"/>',
  /* 价值 / 机会 */
  trend:   '<path d="M3 17 9.5 10.5l4 4L21 7"/><path d="M15 7h6v6"/>',
  coin:    '<ellipse cx="12" cy="7" rx="7" ry="3"/><path d="M5 7v10c0 1.7 3.1 3 7 3s7-1.3 7-3V7"/><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
  window:  '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M9 21V9"/>',
  key:     '<circle cx="8" cy="12" r="4"/><path d="M12 12h9M18 12v3.4M15.5 12v2.4"/>',
  arrowR:  '<path d="M4 12h15M13 6l6 6-6 6"/>',
  doc:     '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
  layers:  '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
  plus:    '<path d="M12 5v14M5 12h14"/>'
};

// 生成一个图标圆牌。tone 空字符串=金色基调
function ico(name, cls, tone) {
  return `<div class="${cls}${tone ? ' ' + tone : ''}"><svg viewBox="0 0 24 24" fill="none">${ICON[name] || ''}</svg></div>`;
}

/* ============================ 配套 CSS ============================
.ic,.ni,.hi{display:flex;align-items:center;justify-content:center;flex:0 0 auto;
  border-radius:14px;position:relative;
  background:linear-gradient(160deg,rgba(255,242,206,.14),rgba(255,255,255,.03));
  border:1px solid rgba(226,203,138,.40);
  box-shadow:inset 0 1px 0 rgba(255,242,206,.26),0 0 20px rgba(214,190,120,.10);}
.ic{width:44px;height:44px;}                        .ic svg{width:24px;height:24px;}
.ni{width:62px;height:62px;border-radius:18px;}      .ni svg{width:34px;height:34px;}
.hi{width:84px;height:84px;border-radius:22px;}      .hi svg{width:46px;height:46px;}

// 线性图标统一描边 —— 颜色不写在 SVG 里，交给 CSS 才能做语义变体
.ic svg,.ni svg,.hi svg{stroke:#E8D9A8;fill:none;stroke-width:2;
  stroke-linecap:round;stroke-linejoin:round;}

// 语义变体：同一个图标在不同语义卡里自动换色
.ic.up,.ni.up,.hi.up{border-color:rgba(224,80,78,.58);
  background:linear-gradient(160deg,rgba(224,80,78,.22),rgba(224,80,78,.05));
  box-shadow:inset 0 1px 0 rgba(255,190,186,.30),0 0 22px rgba(224,80,78,.18);}
.ic.td,.ni.td,.hi.td{border-color:rgba(62,158,138,.58);
  background:linear-gradient(160deg,rgba(62,158,138,.22),rgba(62,158,138,.05));
  box-shadow:inset 0 1px 0 rgba(190,255,240,.30),0 0 22px rgba(62,158,138,.18);}
.ic.wr,.ni.wr,.hi.wr{border-color:rgba(227,154,56,.58);
  background:linear-gradient(160deg,rgba(227,154,56,.22),rgba(227,154,56,.05));
  box-shadow:inset 0 1px 0 rgba(255,232,190,.30),0 0 22px rgba(227,154,56,.18);}
.ic.up svg,.ni.up svg,.hi.up svg{stroke:#FF9189;}
.ic.td svg,.ni.td svg,.hi.td svg{stroke:#7FE0C8;}
.ic.wr svg,.ni.wr svg,.hi.wr svg{stroke:#FFD79A;}

// 「禁用/未达成」态：空心灰，用于对比里的输方
.ic.off,.ni.off{border-color:rgba(255,255,255,.13);background:rgba(255,255,255,.05);
  box-shadow:none;}
.ic.off svg,.ni.off svg{stroke:rgba(240,228,198,.55);}

// ⚠️ 一屏里图标不要超过 4 种形态；同一档尺寸只配一个语义，否则成了「贴纸墙」
=================================================================== */
