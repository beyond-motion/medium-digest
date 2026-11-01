---
title: 'Claude Code Now Reads AGENTS.md — But Not the Way Most Teams Think'
slug: 2026-11-01-claude-code-agents-md-fallback
author: 'EdibleByte'
date: '2026-11-01T09:00:00+08:00'
source_url: 'https://medium.com/ai-architecture-and-engineering/claude-code-now-reads-agents-md-but-not-the-way-most-teams-think-25714f96b87b'
status: processed
image: covers/2026-11-01-claude-code-agents-md-fallback.svg
excerpt: >-
  Claude Code 原生支持 AGENTS.md 是回退而非平级格式：树上任何一处残留 CLAUDE.md 都会让整棵树的 AGENTS.md 被静默忽略——发布 6 天后的数据显示 57% 的仓库正踩中这条规则。
---

<!-- REWRITE_START -->

# Claude Code 现在会读 AGENTS.md 了——但不是大多数团队以为的那种读法

> 原文：[Claude Code Now Reads AGENTS.md — But Not the Way Most Teams Think](https://medium.com/ai-architecture-and-engineering/claude-code-now-reads-agents-md-but-not-the-way-most-teams-think-25714f96b87b) — EdibleByte

---

2026 年 9 月 18 日，Anthropic 发布 Claude Code v2.1.277，原生支持 AGENTS.md——这个开放的跨工具项目说明格式在过去一年里已成为「告诉编码智能体这个代码库怎么运转」的事实标准。所有媒体的头条都很简单：**Claude Code 终于和 Cursor、Copilot、Codex 以及二十多个工具读同一个文件了。**

头条下面的细节才是真正该读的部分：Claude Code 的支持是一种**回退（fallback）而非平级格式**，而 governing 这个回退的优先级规则比大多数团队目前以为的更严格。发布六天后的一项研究发现：**当下超过一半携带 AGENTS.md 的仓库，正被 Claude Code 静默忽略这个文件。** 不是降级优先级，是忽略。

「在 CLAUDE.md 旁边加一个 AGENTS.md」不是迁移——那是发布一个没人读的文件。

## AGENTS.md 是怎么成为标准的

每个 AI 编码工具都带着自己的「这个项目怎么跑」约定来：Claude Code 有 CLAUDE.md，Cursor 有 .cursorrules，Gemini CLI 有 GEMINI.md，GitHub Copilot 有 copilot-instructions.md。对同时使用多个工具的团队——2026 年这已是多数团队——这意味着维护几份近乎重复的说明文件，而且几周内就会漂移失同步，因为没有谁记得每次构建命令变了要更新四个文件。

AGENTS.md 是 OpenAI 的答案：2025 年 8 月作为开放规范发布，Google、Cursor、Factory 参与其中。设计刻意极简——所谓「标准」其实只是一个文件名约定，外加「内容是纯文本 markdown、覆盖构建命令/测试命令/代码风格/人类贡献者也需要的架构上下文」这一共识。没有私有物，不锁定任何一家工具。

2025 年 12 月，OpenAI 把规范捐给了 Linux Foundation 新成立的 Agentic AI Foundation（AAIF）——同一机构还锚定着 Model Context Protocol 和 goose 智能体框架。这次移交比听起来的更重要：它把格式的治理权从一家对跨工具采用有明显商业利益的公司，移到了中立基金会——这也是竞争厂商们愿意采用一个起源于直接竞争对手的格式的重要原因。到 2026 年 5 月，AAIF 会员已达 190 个组织；到 Claude Code 加入支持时，超过 6 万个开源仓库已带着 AGENTS.md，被至少 25 个工具原生读取——Codex CLI、Cursor、GitHub Copilot、Gemini CLI、Windsurf、Sourcegraph Amp、Aider、Zed、Google Jules、JetBrains Junie、Devin 等等。

Anthropic 坚持得比大多数厂商久，原因不是惯性——CLAUDE.md 比 AGENTS.md 更早出现，而且做了 AGENTS.md 那种扁平单文件设计没有明显复制的东西：**子目录作用域层级**。Claude Code 会从你所在位置沿目录树向上走，加载全局 ~/.claude/CLAUDE.md、仓库根文件、以及途中每一层嵌套的 CLAUDE.md，合并时最具体的规则权重最后。对大型 monorepo 这是真有用的：packages/api/ 里放 API 层约定、tests/ 里放测试约定，互不渗漏。单扁平文件给不了这个，放弃它不是一笔小交易。

## Claude Code 2.1.277 实际做了什么

回退行为（Anthropic 的 Thariq 在发布公告里直接确认过）说起来简单、读起来容易误读：**某文件夹里没有 CLAUDE.md 时，Claude Code 会检查并改用 AGENTS.md。** 该行为在 /config 里可开关。CLAUDE.md 没有被弃用——它存在的地方默认仍然优先；且截至发布，该特性在 Bedrock、Vertex、Foundry 部署上还不可用——如果贵组织经由这些通道跑 Claude Code，这就要紧了。

快速读过那句话，听起来像一个对称的层级：每个目录独立地「有 CLAUDE.md 用 CLAUDE.md，否则用 AGENTS.md」，和现有 CLAUDE.md 嵌套的工作方式一样。**它不是对称的。** 真实规则是单一的整树开关：如果当前目录路径的上方任何位置存在 CLAUDE.md——仓库根、全局 ~/.claude/CLAUDE.md、或某个 CLAUDE.local.md——那么**整棵树里的每一个 AGENTS.md 都会被忽略**，包括好几层目录深处、自己身边根本没有任何 CLAUDE.md 的嵌套文件。

嵌套的 AGENTS.md 确实会得到逐目录处理，和 CLAUDE.md 嵌套一贯的工作方式一致——但前提是**整棵树从根到底完全没有 CLAUDE.md**。顶部残留的一个旧文件，就让整个项目的回退失效——静默地，无任何警告。

## 为什么这已经在咬人

2026 年 9 月 24 日（Claude Code 发布后六天）发表的一项研究检查了 283 个携带 AGENTS.md 的公开仓库：其中 161 个——**57%**——Claude Code 仍在读某个 CLAUDE.md，因为树上某处存在一个。对这每一个仓库，AGENTS.md 的工作对 Claude Code 专门不可见，尽管接触该代码库的所有其他工具都读得正确无误。

这是最常见迁移模式的可预测结局：团队加一个 AGENTS.md 来统一多工具说明，但把现有 CLAUDE.md 留在原地「以防万一」；或者迁移了根文件，却忘了早期配置留下的 .claude/CLAUDE.md；或者队友为个人偏好建过一个 CLAUDE.local.md 从没删。**每一个都足以单独让整个仓库的回退失效。**

## 按你的配置，实际改变的是什么

**单工具 Claude Code 用户**：今天对你什么都没变。CLAUDE.md 照常工作，没有任何动手的压力。

**多工具团队**（Claude Code 搭配 Cursor、Copilot 或 Gemini CLI）才是 AGENTS.md 为之而生的真正整合场景：一个文件替代三四个说法各异的同类。关键是**迁移必须一次做完整，不能增量**——在同一次变更里找出并改名仓库中的每一个 CLAUDE.md（根文件、每个嵌套子目录文件、.claude/CLAUDE.md、任何 CLAUDE.local.md）。部分迁移不是完整迁移的更安全分阶段版；它是让你的部分说明没人读的方法。

**开源维护者**越来越把 AGENTS.md 当作礼貌的默认——贡献者带着自己顺手的任何工具来。同样的全有或全无规则适用：先过规则，才能声称 Claude Code 贡献者被覆盖了。

**想让两种格式共存的团队**（无论什么理由，包括混合过渡期）有两个真选项，而不是「两个都留然后祈祷」：把 CLAUDE.md 做成指向 AGENTS.md 的符号链接（一个文件两个名字），或用社区工具如 claude-agentsmd Claude Code 插件自动保持两者同步。两者都胜过维护两个最终会打架的文件。

**Bedrock、Vertex、Foundry 企业用户**：暂时什么都得不到。回退截至发布还没上这些部署通道，CLAUDE.md 仍是那里 Claude Code 唯一会读的格式，仓库里放什么别的都没用。

## 真实的迁移清单

→ 在**整个仓库**搜索每一个 CLAUDE.md、.claude/CLAUDE.md、CLAUDE.local.md——不只根目录

→ 在**同一次变更**里把它们全部改名为 AGENTS.md，不分批跨 PR

→ 不在改名范围内的文件**删除而不是留原地**——任何位置的一个孤儿 CLAUDE.md 都会废掉它下方所有 AGENTS.md

→ 到 /config 确认回退已启用——它是开关，不是默认开启

→ 在 Bedrock、Vertex 或 Foundry 上，暂时把 CLAUDE.md 当唯一格式——回退还没到那里

→ 重跑你验证迁移成功的那个检查——树上任何一处漏掉一个文件都足以让它静默失败

这些都不难。只是它们不是「Claude Code 现在读 AGENTS.md 了」第一眼听起来的那个意思——而六天前的数据说，试过的大多数团队已经做错了。

<!-- REWRITE_END -->

<!-- SPROUT_START -->

# 《Claude Code Now Reads AGENTS.md》的发芽报告

## 材料核心

Claude Code v2.1.277 对 AGENTS.md 的支持是「回退」而非「平级」：真实规则不是每目录独立选择，而是一棵树一个开关——当前目录上方任何位置（仓库根、全局 ~/.claude/CLAUDE.md、任何 CLAUDE.local.md）存在一个 CLAUDE.md，整棵树的所有 AGENTS.md 就被静默忽略。发布六天后的实测：283 个带 AGENTS.md 的公开仓库里 57% 正中此规则。最常见的死法是「留下旧文件以防万一」的部分迁移。解法是一次性完整改名（或 symlink/同步插件），并在 /config 确认开关、重跑验证——Bedrock/Vertex/Foundry 通道暂时完全没有此特性。

## 发芽 01：「回退」与「平级」一字之差，语义天壤之别

### 种子

「Claude Code 支持 AGENTS.md」这句话里藏着一个未声明的实现细节：支持的方式是 fallback（没有首选时才用）还是 peer（与首选平权）？两种读法都合理，行为却完全不同。

### 故事

多数团队的迁移决策建立在「平级」读法上：加上新文件、留着旧文件，以为每个目录会就近选择。而实际实现是「树上任何优先格式存在即全树禁用回退」——一个残留文件废掉全部努力，且静默无警告。57% 的失败率不是用户粗心，是文档语法的模糊性在规模化收割。

### Aha 瞬间

**兼容性声明的工程含义藏在优先级规则里，不在支持列表里。** 读发布说明时，「支持什么」只是第一层；「和谁同时存在时谁赢」「静默还是报错」才是决定迁移策略的那一层——问一句「它是个开关还是个层级」，能省掉一次全组织的静默失败。

## 发芽 02：静默失败是迁移的天敌——「以防万一」的代价

### 种子

最常见的迁移死法不是做错，而是做了一半：「根文件迁了，.claude/ 里的旧文件以防万一留着」。系统不报错、不警告，只是安静地忽略新文件。

### 故事

文中列举的三种残留（旧根文件、早期配置的 .claude/CLAUDE.md、队友的 CLAUDE.local.md）每一个都足以单独失效整个仓库。这就是为什么清单要求「同一次变更、不分批 PR」：分阶段迁移在回退语义下不是渐进，是持续的静默失败期。验证步骤同样关键——重跑那个「确认迁移成功」的检查，因为漏一个文件 = 全部白做。

### Aha 瞬间

**渐进式迁移的前提是系统允许「新旧并存」；当规则是全有或全无时，渐进就是失败的同义词。** 判断一个迁移能不能分阶段，先问目标系统的裁决语义——是按文件就近裁决，还是全树一票否决。

## 发芽 03：一个文件格式是怎么赢的——治理权先于技术

### 种子

AGENTS.md 的设计毫无技术惊艳之处——一个文件名约定加「内容是纯文本 markdown」的共识。它赢的方式值得拆解：先开源规范，再捐给中立基金会。

### 故事

时间线本身就是教材：2025-08 OpenAI 发布规范（Google/Cursor/Factory 参与）→ 2025-12 捐给 Linux Foundation 的 AAIF（同一机构还锚定 MCP 和 goose）→ 2026-05 有 190 个组织会员 → 6 万仓库、25+ 工具原生读取 → 连最大的竞争者 Anthropic 也最终加入。把治理权从有商业利益的单一公司移到中立基金会，是竞争厂商愿意接受的先决条件——连 Anthropic 坚持 CLAUDE.md 的理由（子目录作用域）也是技术性的而非政治性的。

### Aha 瞬间

**标准的胜负手常常不在规范里，在治理结构里。** 「谁拥有这个格式」决定了竞争对手敢不敢用——把格式捐给基金会不是姿态，是让直接竞争对手也能安心采用的必要条件。做开发者生态的人该把这页抄进 playbook。

<!-- SPROUT_END -->
