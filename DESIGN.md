# AI-Job-Consultant High-End Frontend Design Standard

本文件是 AI-Job-Consultant 前端视觉、交互和响应式设计的唯一规范来源。所有新页面、组件重构和视觉修改必须遵守本规范；如产品需求确实需要例外，必须在对应 Issue 或 PR 中说明原因。

# 1. Product Vision

AI-Job-Consultant 不是普通聊天机器人，也不是装饰性的“AI 展示页”。它是一套帮助用户理解职业位置、完善简历、匹配岗位并进行面试训练的 **Career Intelligence Console（职业智能控制台）**。

整体艺术方向命名为 **Precision Aurora**：

- 高端、精密、可信，具有明确的科技感和空间层次。
- 通过深色材质、冷色光谱、克制的辉光和清晰的数据结构建立冲击力。
- AI 被表现为有响应、有依据的智能能力，而不是无处不在的装饰。
- 重要数据、报告和建议必须清楚、可追踪、可阅读。
- 视觉张力集中在入口、首页和关键结果时刻；高频工作区保持低干扰。

设计强度：

| 维度 | 目标 |
|---|---:|
| Design variance | 7 / 10 |
| Motion intensity | 5 / 10 |
| Information density | 6 / 10 |
| Material depth | 6 / 10 |
| Decorative noise | 2 / 10 |

## 1.1 Three Experience Zones

不同页面不能使用相同强度的视觉效果。

### Impact Zone

适用于 WelcomePage、登录入口和产品首次呈现。

- 允许大面积深色背景、受控 Aurora 渐变、抽象光场和非对称构图。
- 可以使用一处主视觉动效，但内容在无动画时也必须完整。
- 重点是品牌印象、产品定位和唯一主行动。

### Command Zone

适用于 Dashboard、全局导航和任务入口。

- 使用更清晰的控制台结构、分层表面和少量高亮光感。
- 一页只能有一个视觉主焦点。
- 快捷任务、状态和最近工作按优先级组织，不能堆成同权重卡片墙。

### Focus Zone

适用于 ChatWindow、表单、会话列表、知识库和分析报告。

- 以可读性、操作效率和稳定反馈为第一目标。
- 辉光、玻璃和渐变只能用于选中状态、智能生成状态或关键结果。
- 长文本和 AI 输出使用文档式排版，不使用大面积发光聊天气泡。

## 1.2 Non-goals

以下表现不属于本产品：

- 加密货币、游戏 HUD 或赛博朋克仪表盘风格。
- 满屏霓虹、持续闪烁、扫描线或无意义粒子。
- 所有容器都使用玻璃拟态。
- 多个渐变按钮同时争夺注意力。
- 为了画面完整而虚构评分、统计、公司 Logo 或用户案例。
- 把每一块内容都包装成悬浮卡片。
- 依赖动画才能理解或访问的内容。

# 2. Experience Principles

## 2.1 Task clarity

- 每个页面必须有一个明确任务和一个主行动。
- 导航、会话、知识库和求职工具必须在结构上区分。
- 复杂工作如编辑 JD、查看报告和分析简历应进入主工作区或专用面板，不能全部塞进窄侧栏。
- 用户切换页面时保留当前会话、文档和输入上下文。

## 2.2 Trust and evidence

- AI 建议必须表现为可阅读的报告、结构化结论或带来源的回答。
- 未获取到的数据必须显示“暂无数据”或“暂不可用”，不能显示伪造的 0。
- 加载、成功、警告、错误和空状态必须有不同表现。
- 阻塞性错误必须出现在相关内容附近，并给出恢复操作。
- Toast 只用于短暂确认，不能承载唯一的错误解释。

## 2.3 Accessibility

- 正文对比度至少达到 WCAG AA 4.5:1。
- 大文字、图标和重要边界至少达到 3:1。
- 所有交互支持键盘操作和可见焦点。
- 图标按钮必须有 aria-label；含义不明显时提供 Tooltip。
- 状态不能只依赖颜色表达。
- 动效必须支持 prefers-reduced-motion。
- 半透明材质必须为 prefers-reduced-transparency 或不支持模糊的环境提供纯色回退。

# 3. Color and Light System

组件只能使用语义令牌，不得引入一次性颜色。深色模式是品牌签名呈现，浅色模式保持同等完整性。主题优先使用用户已保存选择；没有保存值时可跟随系统偏好。

## 3.1 Core surfaces

| Token | Light | Dark | Usage |
|---|---|---|---|
| --color-canvas | #F4F7FB | #070A12 | 应用背景 |
| --color-canvas-deep | #EAF0F8 | #05070D | 强调背景与入口底色 |
| --color-surface | #FFFFFF | #0E1320 | 主内容表面 |
| --color-surface-subtle | #F7F9FC | #121929 | 次级分组 |
| --color-surface-elevated | #FFFFFF | #171F32 | 菜单、抽屉、浮层 |
| --color-surface-glass | rgba(255,255,255,.72) | rgba(14,19,32,.72) | 有限玻璃表面 |
| --color-surface-hover | #EDF3FA | #1B253A | Hover 和选中行 |
| --color-border | rgba(15,23,42,.10) | rgba(148,163,184,.16) | 默认边界 |
| --color-border-strong | rgba(15,23,42,.18) | rgba(148,163,184,.28) | 强边界 |
| --color-text-primary | #0A1020 | #F7F9FC | 标题与正文 |
| --color-text-secondary | #3C4A61 | #C4CDDC | 次级正文 |
| --color-text-muted | #64748B | #91A0B7 | 元数据 |
| --color-text-disabled | #94A3B8 | #64748B | 禁用文本 |

## 3.2 Signature spectrum

主品牌光谱由 Violet、Electric Blue 和 Cyan 组成：

| Token | Value | Usage |
|---|---|---|
| --color-primary | #6D5DFB | 主行动、选中状态 |
| --color-primary-hover | #5A4BE7 | Hover |
| --color-primary-pressed | #493BCB | Pressed |
| --color-primary-soft | rgba(109,93,251,.14) | 柔和选中背景 |
| --color-electric-blue | #3B82F6 | 数据强调、交互辅助 |
| --color-cyan | #19C3E6 | 智能生成、实时状态 |
| --color-on-primary | #FFFFFF | 主色上的内容 |

签名 Aurora：

    linear-gradient(135deg, #6D5DFB 0%, #3B82F6 52%, #19C3E6 100%)

允许使用的位置：

- WelcomePage 的主视觉光场。
- 页面中唯一的主行动。
- AI 正在生成、关键进度或最终结果的有限强调。
- Dashboard 的一处主任务区域。

禁止使用的位置：

- 普通卡片背景。
- 长文本容器。
- 每个按钮、Tag、头像或导航项。
- 错误、警告和成功状态。

## 3.3 Status colors

| Status | Foreground | Soft background |
|---|---|---|
| Success | #16A36A | rgba(22,163,106,.13) |
| Warning | #E69A24 | rgba(230,154,36,.14) |
| Danger | #EA5B65 | rgba(234,91,101,.14) |
| Information | #3B82F6 | rgba(59,130,246,.13) |

状态色只表达真实状态，不能作为替代品牌色。

## 3.4 Light effects

- Glow 只围绕主行动、当前 AI 状态或关键数值出现。
- 单个页面最多保留两处明显光源。
- Glow 不得降低文字对比度，不得覆盖表单和长文本。
- 背景光场应使用伪元素或静态背景，不为装饰引入大图。
- 可选噪点纹理不透明度不得超过 3%，且不得影响内容清晰度。

# 4. Typography

默认使用系统优先字体，不加载未经确认授权和性能评估的远程字体。

## 4.1 Font stacks

UI Sans：

    ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif

Technical Mono：

    ui-monospace, SFMono-Regular, "Cascadia Code", "JetBrains Mono", Consolas, monospace

Mono 仅用于模型状态、文件类型、时间、版本和短技术标签，不能用于正文。

## 4.2 Type scale

| Role | Size / Line height | Weight |
|---|---|---:|
| Display | 48 / 56 | 700 |
| Page title | 30 / 38 | 700 |
| Section title | 21 / 30 | 600 |
| Component title | 16 / 24 | 600 |
| Body large | 16 / 26 | 400 |
| Body | 14 / 22 | 400 |
| Label | 13 / 20 | 500 |
| Caption | 12 / 18 | 400 |
| Metric large | 36 / 42 | 650 |

- WelcomePage 可使用 Display；登录后的工作区不得使用超过 36px 的标题。
- AI 报告正文宽度不超过 70ch。
- 数值使用 tabular-nums。
- 中文标题不使用装饰性宽字距。
- 不使用小于 12px 的可读文本。

# 5. Spacing, Shape and Depth

## 5.1 Spacing

使用 4px 基础单位：

    4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96

- Desktop 页面边距：32px。
- Tablet 页面边距：24px。
- Mobile 页面边距：16px。
- 页面主区块间距：32px 或 40px。
- 相关组件间距：12px、16px 或 24px。
- 控件组间距：8px 或 12px。

## 5.2 Radius

| Token | Value | Usage |
|---|---:|---|
| --radius-control | 8px | 输入、按钮 |
| --radius-card | 14px | 主要内容卡片 |
| --radius-panel | 18px | 浮动面板 |
| --radius-dialog | 20px | Dialog |
| --radius-pill | 999px | Tag、状态胶囊 |

不要在同一区域混用多种相近圆角。

## 5.3 Borders and shadows

- 普通表面使用 1px 半透明边界。
- 卡片默认只使用边界和色差，不使用重阴影。
- Elevated 表面可使用：

    0 18px 60px rgba(2, 6, 23, .18)

- Popover 可使用：

    0 12px 36px rgba(2, 6, 23, .16)

- 光晕不是阴影替代品；普通列表项不得发光。

## 5.4 Glass

玻璃材质只允许用于：

- WelcomePage 主容器。
- Sticky Topbar。
- 浮动工具条和临时覆盖层。

玻璃表面必须同时具备：

- 可辨识的纯色底。
- 1px 半透明边界。
- 最大 18px backdrop blur。
- 在不支持 blur 时仍可阅读的回退背景。

# 6. Layout System

## 6.1 Application shell

Desktop，宽度不小于 1280px：

- Sidebar：280px。
- Topbar：64px。
- 主内容最大宽度：1200px。
- 聊天阅读列：最大 920px。
- 报告抽屉：600px。

Tablet，768px 至 1279px：

- Navigation rail：76px。
- 会话和知识库在覆盖面板中展开。
- 不重复挂载多份 Sidebar。

Mobile，小于 768px：

- Topbar：56px。
- Sidebar 转为全高抽屉。
- 主内容不允许横向滚动。
- 主要触控目标至少 44 × 44px。

应用外壳使用 min-height: 100dvh，不使用固定 100vh。

## 6.2 Composition

- 页面级布局优先使用 CSS Grid。
- 局部控件组使用 Flexbox。
- Dashboard 允许非对称布局：一处主任务 Spotlight，加上次级快捷入口和最近内容。
- Focus Zone 使用稳定阅读宽度，不让正文铺满超宽屏幕。
- 数据密集页面使用对齐、分组和留白，不依赖装饰性容器。

# 7. Component Standards

## 7.1 WelcomePage

- 使用非对称双栏或层叠构图。
- 品牌区允许 Aurora 光场、抽象网格和有限的空间动效。
- 表单区保持实色或高可读玻璃表面。
- 只能有一个主提交按钮。
- 不使用虚构的公司 Logo、用户数量或成功率。
- Mobile 转为单列，品牌信息缩短但不能完全消失。

## 7.2 AppTopbar

- Sticky，使用轻度玻璃或 Elevated 表面。
- 显示当前页面标题和必要上下文。
- Mobile 显示导航按钮。
- 用户信息保持低调，退出操作放入账户菜单。
- 不在 Topbar 堆叠多个高饱和按钮。

## 7.3 Sidebar and navigation

- 结构顺序：品牌、主导航、最近会话、知识库、账户与设置。
- Active 项使用 Primary soft 背景、左侧光标或边界强调。
- 低频操作进入上下文菜单。
- JD 编辑、文档详情等复杂任务转移至主工作区或专用面板。
- 服务状态使用文字加状态点，不使用持续脉冲。

## 7.4 Dashboard

- 顶部使用一个明确的 Career Command Spotlight。
- 三项核心能力保持存在：简历分析、岗位匹配、模拟面试。
- 快捷入口不能使用三张同权重彩色卡片。
- 有真实数据时才显示进度、趋势和建议；没有数据时使用引导型空状态。
- 重点数值可使用 Aurora 边界或柔和光感，但每屏不超过一组。

## 7.5 ChatWindow

- AI 回答使用文档式布局和宽松行距。
- 用户消息可使用 Primary 色块，但面积与辉光必须克制。
- 来源以可访问的 Citation chips 或列表呈现。
- 输入区固定在可用区域底部，使用 Elevated 材质。
- Streaming 状态使用光标、进度线或低强度呼吸光，不使用大面积闪烁。
- 必须包含空状态、连接中、生成中、失败和可重试状态。

## 7.6 Reports and analytics

- 报告抽屉使用 600px Desktop 宽度，Mobile 全宽。
- Header 固定，包含标题、上下文、关闭和最多一个主行动。
- 指标使用清晰层级、对齐数字和真实状态色。
- 图表使用 Neutral + Primary + Cyan，避免彩虹配色。
- 图表颜色必须同时提供文本、图例或形状辅助。
- 未解析到评分时显示破折号，不填充默认评分。

## 7.7 Cards

卡片用于：

- 一个独立任务、文档、报告摘要或有明确操作边界的实体。
- Dashboard 的主 Spotlight 和少量次级入口。

卡片不用于：

- 每个页面区块。
- 每个指标。
- 每条 AI 回复。
- 普通导航项。

默认卡片：

- Surface 或 Surface subtle。
- 1px Border。
- 14px Radius。
- 默认无阴影；Hover 最多上移 2px。

## 7.8 Buttons

层级：

1. Primary：每个任务区域一个。
2. Secondary：辅助操作。
3. Tertiary：文本或图标操作。
4. Danger：与主行动分离。

- Primary 可以使用 Aurora，但同一可视区域最多一个 Aurora 按钮。
- 默认高度 38px，主要表单 42px，触控区域至少 44px。
- 必须定义 Default、Hover、Focus-visible、Active、Disabled 和 Loading。
- 图标使用 @element-plus/icons-vue，不使用 Emoji 作为界面图标。

## 7.9 Forms

- Label 永远显示，Placeholder 不替代 Label。
- 错误紧邻字段出现。
- Focus 使用 Primary 边界和柔和光环。
- Disabled 状态保持可读，不能只降低透明度。
- 长 JD 和面试回答使用自增长 Textarea。
- 阻塞错误保持显示直到用户处理。

## 7.10 Tags and status

- Tag 用于分类、状态和来源，不用于装饰。
- 状态胶囊必须配合文字。
- 避免同时出现多个高饱和 Tag。
- 文件类型和模型状态可使用 Mono 字体。

# 8. Iconography and Imagery

- 使用 @element-plus/icons-vue 作为唯一默认图标族。
- 同一上下文保持一致线宽和尺寸。
- 默认尺寸：16px；主导航：18px；关键行动：20px。
- Emoji 仅允许出现在用户生成内容和 AI 对话正文中。
- 不伪造产品截图、头像、品牌 Logo 或客户证明。
- 没有合适图片时，优先使用真实 UI 预览、图表或抽象 CSS 光场。

# 9. Motion System

动效用于反馈、层级和状态，不用于持续吸引注意力。

## 9.1 Timing

| Type | Duration |
|---|---:|
| Control feedback | 120–160ms |
| Content transition | 180–240ms |
| Drawer / dialog | 240–320ms |
| Welcome entrance | 420–600ms |

标准 easing：

    cubic-bezier(.22, 1, .36, 1)

## 9.2 Allowed motion

- WelcomePage 一次性主视觉进入。
- Dashboard 主要区域轻度顺序进入。
- Drawer、Popover 和导航展开。
- Streaming、上传和分析进度反馈。
- Hover 使用边界、亮度和最多 2px 位移。

## 9.3 Forbidden motion

- 登录后页面的循环背景动画。
- 大面积视差、磁性指针和鼠标追踪光。
- 长时间旋转或闪烁装饰。
- 同时运行多套动画系统。
- 动画 width、height、top、left 等高成本布局属性。
- 让内容只能在滚动动画完成后出现。

## 9.4 Reduced motion

prefers-reduced-motion: reduce 时：

- 取消视差、Stagger、呼吸光和大幅位移。
- 保留必要的显示/隐藏状态变化。
- 单次过渡缩短至接近即时。

# 10. Data Visualization

- 图表背景透明，与所在 Surface 融合。
- 网格线使用低对比 Border 色。
- 主序列使用 Primary，实时或对比序列使用 Cyan。
- Success、Warning、Danger 只表达对应语义。
- Tooltip 使用 Elevated 表面和清晰边界。
- 数值不能只通过颜色区分。
- 图表必须响应容器尺寸变化。
- ECharts 按需加载；不要同时使用 CDN 和包依赖。

# 11. Responsive and Interaction States

每个页面必须验证：

- 375px：单列、无横向滚动、触控目标合格。
- 768px：导航轨和任务面板逻辑正确。
- 1024px：内容层级和抽屉宽度合理。
- 1440px：内容不会过度拉伸。

每个异步区域必须设计：

- Initial。
- Loading。
- Empty。
- Success。
- Error。
- Retry。
- Disabled 或 unavailable。

每个交互控件必须设计：

- Default。
- Hover。
- Focus-visible。
- Active。
- Disabled。
- Loading（如果异步）。

# 12. Element Plus Integration

- Element Plus 通过语义 Token 映射，不在单个组件中大量覆盖硬编码颜色。
- Drawer、Dialog 和 Popover 使用 Surface elevated。
- Input 使用 Surface subtle，Focus 使用 Primary + Focus ring。
- Primary Button 使用 Primary 或有限 Aurora。
- Danger Button 不使用 Aurora。
- ElMessage 仅用于短暂反馈；阻塞错误必须进入页面状态。
- 全局覆盖集中在 element-plus.css，不散落到业务组件。

# 13. Performance Guardrails

- WelcomePage 的材质和光场优先用 CSS 实现。
- backdrop-filter 只用于小范围固定层。
- 默认不引入 GSAP；简单动效使用 CSS 或 Vue Transition。
- 如未来使用 GSAP，必须限制在独立入口或营销页面，并提供完整 Reduced Motion 回退。
- 报告、ECharts 和低频面板异步加载。
- 不加载未经使用的字体、图片和动画库。
- 避免在滚动事件中逐帧更新 Vue 状态。
- 所有动画优先使用 transform 和 opacity。

# 14. Migration Priorities

实施顺序：

1. 重建语义 Token 和 Element Plus 映射。
2. 重构 App shell、Topbar、Sidebar 和响应式导航。
3. 重构 WelcomePage，建立品牌第一印象。
4. 重构 Dashboard，建立 Career Command Center。
5. 重构 ChatWindow 和 Streaming 状态。
6. 重构 Analytics、ResumeReport 和 JobMatchPanel。
7. 清除 Emoji 图标、内联样式、旧色值和重复暗色样式。
8. 完成性能、可访问性与多视口验证。

每一步必须保持现有 API、数据契约和用户流程可用。

# 15. Compliance Checklist

## Visual direction

- [ ] 页面符合 Precision Aurora，而不是通用紫色 AI 模板。
- [ ] 视觉冲击集中在入口、主行动和关键结果。
- [ ] Focus Zone 没有多余光效和持续动画。
- [ ] 同一页面明显光源不超过两处。

## Structure

- [ ] 页面只有一个主目标和主行动。
- [ ] 导航、会话、知识库和求职工具层级清晰。
- [ ] 内容宽度、间距和表面层级符合规范。
- [ ] 没有无意义卡片墙。

## Components

- [ ] 组件使用语义 Token，无一次性颜色。
- [ ] 使用 Element Plus 图标，无 UI Emoji。
- [ ] 按钮、表单和状态具备完整交互状态。
- [ ] AI 输出和报告保持文档式可读性。

## Accessibility

- [ ] 键盘可完成主要流程。
- [ ] Focus-visible 清楚可见。
- [ ] 文本和关键边界达到对比度要求。
- [ ] 状态不只依赖颜色。
- [ ] Reduced Motion 和透明度回退有效。

## Responsive

- [ ] 已检查 375、768、1024、1440px。
- [ ] 无横向溢出和内容裁切。
- [ ] Mobile 触控目标至少 44px。
- [ ] Drawer、Topbar 和导航行为正确。

## Performance

- [ ] 无不必要的全局动画和大范围模糊。
- [ ] ECharts 和低频面板按需加载。
- [ ] 无重复 CDN 与包依赖。
- [ ] Build、Lint、Test 和浏览器控制台检查通过。

# 16. Final Design Statement

AI-Job-Consultant 的高级感来自 **精密层级、可信数据、受控光感和流畅反馈**，而不是视觉特效的数量。

入口应该令人印象深刻，首页应该像职业智能控制台，聊天和报告应该让用户愿意长时间阅读与工作。任何装饰如果损害清晰度、性能、可访问性或信任感，都必须被削弱或移除。
