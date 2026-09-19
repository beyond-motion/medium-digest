---
title: 'DESIGN.md: Give Your AI a Design System It Can''t Ignore'
slug: 2026-09-19-design-md-give-your-ai-a-design-system-it-cant-ignore
author: John Narus
date: '2026-09-19T09:00:00+08:00'
source_url: 'https://medium.com/@john.narus/design-md-give-your-ai-a-design-system-it-cant-ignore-d8e23ff29358'
status: processed
image: covers/2026-09-19-design-md-give-your-ai-a-design-system-it-cant-ignore.svg
excerpt: >-
  让 AI 编码工具建三个页面，你会得到三种深浅不一的「你的」蓝。解法是 DESIGN.md——Google Labs 2026 年 4 月开源的格式：上半 YAML 给机器可读的精确值，下半固定小节的散文讲清「为什么」，还能像代码一样 lint 和 diff。
---

<!-- REWRITE_START -->
# DESIGN.md：给你的 AI 一套它无法忽视的设计系统

> 原文：[DESIGN.md: Give Your AI a Design System It Can't Ignore](https://medium.com/@john.narus/design-md-give-your-ai-a-design-system-it-cant-ignore-d8e23ff29358)

---

## 问题：一个没有品牌记忆的工程师

让 AI 编码工具建三个页面，你常常会拿到三种深浅不一的「你的」蓝。这不是它瞎猜——而是从来没有任何东西告诉过它你的品牌到底是什么。

每个用 Claude Code、Cursor 或同类 AI 编码工具的团队都撞见过同一个问题：**AI 是一个能干的工程师，却没有关于你品牌的任何记忆。**今天让它做设置页、明天做仪表盘，它每次都现编一套配色——不是因为它粗心，而是 prompt 里没有任何东西告诉它不该这样。

DESIGN.md 就是解药，而且它不是某人上周发明的边缘约定。Google Labs 在 2026 年 4 月开源了这个格式——它原本是 Stitch 设计工具的内部引擎，现在以 Apache 2.0 许可证向所有人开放。

## 它到底是什么

DESIGN.md 是一个纯文本 markdown 文件，分两层。顶部的 YAML 块给 AI agent 精确的、机器可读的值——十六进制色号、字体名、间距单位、圆角半径。下面是按固定小节顺序组织的 markdown 散文，解释理由：Overview、Colors、Typography、Layout、Elevation & Depth、Shapes、Components、Do's and Don'ts。

没有 DESIGN.md，AI 每次都现编一种新蓝；有了它，AI 用你的蓝——**而且知道为什么**。写得好的 Do's and Don'ts 读起来是具体指令，不是氛围：「不要全大写标题」「CTA 不要叠超过两个」「卡片不要用投影，我们用描边」。

它也不只是文档。Google 的开源附带了一个 CLI 工具，这是它超越「约定俗成」的关键：这个 CLI 能对文件做结构正确性 lint、diff 两个版本捕捉设计回退、把 design token 直接导出成 Tailwind 配置或 W3C Design Tokens 格式。

## 优势在哪

最直观的收益是一致性：读过你 DESIGN.md 的 agent 按你的品牌构建，而不是每个新屏幕都现挑一套配色和圆角。但更有用的收益是**这个文件变得可检查，就像代码一样**。官方 CLI 带十一个 lint 规则，覆盖失效的 token 引用、对比度、孤儿 token、小节顺序——无障碍不再是一种愿望，而是一条 agent 可能不通过的规则。

因为它是纯 markdown，它也像代码一样 diff。如果某次提交悄悄改了主色，它会作为一个可见、可评审的变更出现——而不是三个 sprint 之后才发现品牌已经漂了。

它的可移植性也是私有风格指南比不了的：同一份文件在 Claude Code、Cursor、Kiro、Windsurf 里都能用，因为它是 markdown，不是绑定单一工具的插件。它还能以同一种方式完成新成员和新 AI 会话的入职：指一下文件，而不是每次靠记忆重新解释品牌。

最好的 DESIGN.md 读起来像资深设计师给新人的第一天 brief：产品是什么、个性是什么、我们永远不做什么。

## 免费资源

- **官方 spec 与 CLI**（Google Labs GitHub）：格式本身、小节顺序、校验规则的权威来源，Apache 许可。想先理解格式再借鉴别人的，从这里开始。
- **designmd.app**：759 份现成 DESIGN.md，风格从极简到蒸汽朋克，外加真实品牌的文档化版本，开箱适配 Claude Code、Cursor、Kiro、Windsurf。
- **designmd.ai**：社区画廊，可浏览下载真实项目示例——比如一个为小企业做的深色电力监控仪表板，MIT 许可。
- **designmd.co**：第三个免费目录，前两个找不到近似匹配时值得一看。

## 付费资源

- **Refero**：单份 DESIGN.md 示例免费，但更大的 UI/UX 灵感库（真实产品界面与流程，web 与 iOS）全量访问要 $120/年。想要规模化、结构化的灵感时值得。
- **Aura**：AI 建站工具，建站过程中自动生成 DESIGN.md——适合「描述产品、拿回一份起步设计系统」而不是手写。

付费只在两种情况下有意义：你想要比免费目录大得多的精选库，或者你想要一个能从 prompt、URL 或截图生成初稿的工具。两者都不占，上面的免费资源覆盖同样的地面。

## 一份真实 DESIGN.md 的拆解

designmd.ai 上那份为小企业与家庭设计的深色电力监控仪表板，是一个真正具体、真正有态度的例子，而不是泛泛模板：

- **主题**：深色，「技术可靠性与掌控感」——面向数据密集屏幕的 Power BI 式美学
- **强调色**：青色 #00E5FF——对深色背景高对比，用于实时读数与告警
- **字体**：Inter 全字重——为密集仪表盘上的小字号可读性而选
- **布局**：12 列栅格 + 明确的间距标准——让几十个实时指标保持对齐
- **许可**：MIT——可自由复用、修改、上线

价值不在色值本身——**在于有人已经为一个数据密集的技术产品做过这些决定，并且写下了为什么**。借用这套推理，比对着空白的 Colors 小节发呆快得多。

## 怎么把它引进你的工作流

1. **从模板起手，别从白纸起手。**从免费画廊挑最接近的，或用生成 prompt 从产品描述起草。一版能用的初稿花一个下午，不是一轮设计 sprint。
2. **和团队一起写，不是替他们写。**散文部分只有在捕捉了真实理由时才有价值——而理由只来自做决定的人。让工程和设计一起在场起草，别写成一篇事后转交的个人作业。
3. **放进项目根目录，让 agent 指向它。**告诉 Claude Code、Cursor 或你在用的任何工具：生成任何 UI 之前先读 DESIGN.md。然后像 lint 代码一样 lint 它——作为评审的常规环节，而不是一次就忘的初始化步骤。

## 参考资源一览

| 资源 | 费用 | 最适合 |
| — | — | — |
| google-labs-code/design.md | 免费 | 官方 spec 与 CLI——lint、diff、token 导出 |
| designmd.app | 免费 | 浏览 759 份现成系统，横跨风格与真实品牌 |
| designmd.ai | 免费 | 具体、真实的项目示例社区画廊 |
| designmd.co | 免费 | 第三个免费目录，前两个没中时看 |
| Refero | 免费增值——全库 $120/年 | 规模化的 UI/UX 灵感，不止 DESIGN.md |
| Aura | 付费（SaaS） | 自动生成初稿 DESIGN.md，而非手写 |

这是作者 AI、产品管理与领导力系列的一部分，会持续更新拆解。

John Narus · AI, Product & Leadership · 在 Medium 关注 · 在 LinkedIn 连接
<!-- REWRITE_END -->

<!-- SPROUT_START -->
# 《DESIGN.md: Give Your AI a Design System It Can't Ignore》的发芽报告

## 材料核心

AI 编码工具没有品牌记忆，每个屏幕都现编一套视觉语言。DESIGN.md 用「YAML 精确值 + 固定小节散文」两层结构把设计决策写进仓库，让 agent 用你的蓝并且知道为什么；配套 CLI 让它像代码一样被 lint、diff、导出 token。这个格式由 Google Labs 于 2026 年 4 月开源（Apache 2.0，Stitch 工具的内部引擎）。

## 发芽 01：约束文件化，上下文才可复用

### 种子

AI 不是粗心，是没有任何东西告诉它你的品牌——每次生成都从零猜起。

### 故事

文章的解法不是更长的 prompt，而是一份住进项目根目录的版本化文件：机器可读的 YAML 层给精确值，散文层给理由和禁忌（「卡片不要用投影，我们用描边」）。每个新会话、每个新成员都指到同一份文件，而不是靠人重新解释。

### Aha 瞬间

这和「评审反馈应改变下一次生成的环境」是同一原理：反复出现的错误，正确归宿是一份持久化的约定文件，而不是每场对话里的口头纠正。凡是 AI 反复猜错的东西，都值得问一句——它有对应的 DESIGN.md 吗？

## 发芽 02：设计从品味问题变成了可 lint 的规则

### 种子

官方 CLI 带十一个 lint 规则：失效 token 引用、对比度、孤儿 token、小节顺序——无障碍从愿望变成一条 agent 可能不通过的检查。

### 故事

文件的第二层收益由此浮现：因为它是结构化纯文本，它可以 diff——某次提交悄悄改了主色，会作为一个可见、可评审的变更出现，而不是三个 sprint 后才发现品牌漂移；它还能导出成 Tailwind 配置或 W3C Design Tokens。

### Aha 瞬间

「可检查」是约定得以存活的机制：没有 lint 的规范靠自觉，有 lint 的规范靠流程。把一个领域的隐性品味转成显式规则并配上机器检查，是人类团队和 AI 团队都受益的同一笔投资——规范的生命力不在文档里，在 CI 里。

## 发芽 03：借用推理比借用色值快

### 种子

文章拆解的示例（深色电力监控仪表板：青色 #00E5FF、Inter、12 列栅格、MIT）的价值不在色值本身。

### 故事

作者的判语：有人已经为一个数据密集的技术产品做过这些决定，并且写下了为什么——强调色选高对比青色是为了深色背景上的实时读数，选 Inter 是为了密集小字号的可读性。借用这套推理，比对着空白的 Colors 小节发呆快得多。

### Aha 瞬间

模板的真正价值不是给出答案，而是给出「答案 + 理由」的配对结构：你可以换掉每个色值，但保留「每个决定附一条理由」的格式。一份只有值没有为什么的规范，换一个产品就作废；一份带为什么的规范，永远可以从理由出发重新推导。
<!-- SPROUT_END -->
