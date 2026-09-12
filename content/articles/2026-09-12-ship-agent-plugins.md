---
title: 'Stop Shipping Individual MCP Servers. Start Shipping Agent Plugins'
slug: 2026-09-12-ship-agent-plugins
author: Andrii Tkachuk
date: '2026-09-12T09:00:00+08:00'
source_url: 'https://medium.com/@andrii_tkachuk/stop-shipping-individual-mcp-servers-start-shipping-agent-plugins'
status: processed
image: covers/2026-09-12-ship-agent-plugins.svg
excerpt: >-
  MCP 解决「能连什么」，Skill 解决「怎么干活」，2026 年 8 月公开的 Agent Plugins 1.0 规范把两者打包成可分发的完整能力——agent 能力正在变得可组合、可版本化、可分发、且日益可移植。
---

<!-- REWRITE_START -->
# 别再单独发布 MCP Server 了，开始发布 Agent Plugin

> 原文：[Stop Shipping Individual MCP Servers. Start Shipping Agent Plugins](https://medium.com/@andrii_tkachuk/stop-shipping-individual-mcp-servers-start-shipping-agent-plugins)

---

## 一条演进的逻辑线

过去几年，我们装备 AI agent 的方式走过了一条出奇合乎逻辑的序列：先要把模型连接到真实系统，然后要教 agent 正确地使用这些系统，现在，我们开始把这两块打包到一起。2026 年 8 月，「打包」这件事不再是各家厂商的私有模式，而成了开放规范。作者开宗明义：这不是又一篇「明天就该推倒重来」的鼓吹——插件不是革命性的 MCP 替代品，行业也不需要又一个时髦词。他关注它的理由很实际：**插件正在成为 agent 能力的分发层。**

## MCP 回答：「agent 能连接到什么？」

2024 年 11 月 Anthropic 推出 Model Context Protocol 时，核心问题是碎片化：每个 AI 应用都要为数据库、SaaS、内部系统、文件存储、开发工具做定制集成。MCP 给了 AI 客户端与外部工具/数据之间的标准接口：agent 对话 MCP 客户端，客户端对话 MCP server，server 暴露背后的一切——Salesforce、Postgres、Google Drive、内部 API。这是实实在在的进步：系统通过 MCP 暴露一次，所有兼容客户端都能用。

但连接只是问题的一半。给 agent 一个 `search_documents` 工具，不等于它知道什么时候该用、如何与其他工具组合、什么顺序安全、或者你的组织认为什么算正确的工作流。**MCP 告诉 agent 它能调用什么，不教它工作该怎么干。**

## Skills 回答：「agent 应该怎么执行工作？」

Agent Skills 补上了这个缺口。Anthropic 在 2025 年推出它：装着指令、脚本和资源的文件夹，agent 按需发现与加载，后来格式公开发布为跨平台的开放标准。一个 Skill 可以编码你们怎么做架构评审、怎么调查事故、部署前必须过哪些检查、agent 必须遵守哪些内部约定——比如：

```
skills/
└── architecture-review/
    ├── SKILL.md
    ├── references/
    │   └── architecture-checklist.md
    └── scripts/
        └── validate_diagram.py
```

区别在于：MCP server 可能暴露 `search_knowledge`、`get_customer`、`create_ticket`、`update_opportunity`；Skill 用平实的指令解释——准备客户调研报告时，先搜内部知识、再到 Salesforce 验证数据、标记冲突信息、每个实质论断都要引用来源、研究阶段绝不回写 Salesforce、用批准的模板生成报告。**工具保持通用，Skill 描述工作流。** 这才更接近生产级 agent 真正的运行方式。

## 然后，下一个问题变得显而易见

想象你想让同事复用你手上现成的 agent 能力。实际操作是：递给他一个 MCP server、另一个 MCP server、三个 Skill、两个配置文件、几个环境变量、一段 agent 指令、也许一个 hook、也许一个专用 sub-agent，外加一份二十步的 README。技术上，一切都可复用；操作上，依然烦得要命——这就是插件开始解决的问题。

## Agent Plugin 是什么

最简单地说，插件是 agent 能力的包。目前各家支持的特性不一：Anthropic 的 Claude 插件捆绑 Skills、连接器与 sub-agents，Claude Code 插件额外支持 hooks 和 MCP 配置等客户端机制；OpenAI 在 ChatGPT 与 Codex 里同样把插件当作「可复用指令+已连接应用」的打包工作流。

更重要的节点是 2026 年 8 月 6 日：**Agent Plugins 1.0 规范公开**——一个开放、厂商中立的包格式，由 Vercel 发起，Amazon、Anysphere（Cursor 母公司）、Microsoft、OpenAI 共同开发，Google 随后加入核心维护者。可移植的 v1 核心刻意只含两种组件——Agent Skills 与 MCP server：

```
customer-research/
├── plugin.json
├── skills/
│   └── customer-research/
│       ├── SKILL.md
│       └── references/
│           └── report-template.md
└── mcp.json
```

manifest 标识包，skills/ 装过程知识，mcp.json 描述所需 server。8 月 12 日 GitHub 在 VS Code、Copilot CLI 与 Copilot app 里发布了支持；月底，ChatGPT、Codex、Cursor、Kiro 都在同一批首发客户端名单上。一个小想法，大架构后果。

## 为什么它比「又一个插件系统」更有意思

软件行业有插件几十年了——那不是重点。重点是**被打包的是什么**。一个 agent 能力日益由两个维度构成：行动的能力，与如何行动的知识。在现有原语里，那就是 MCP 加 Skill。与其分发「一个 MCP server、另一个 MCP server、两个 Skill 和一堆安装说明」，不如分发一个 `customer-research-plugin`——这个包代表的是一件真正要做的活，而不只是一个集成。

这接上了作者反复回到的更大的模式：agent 不应该主要围绕底层命令（`salesforce.search_accounts`、`postgres.query`）做推理，而应该围绕**稳定的操作（capabilities）**——`research_customer`、`prepare_rfi`、`investigate_incident`——每个能力内部可能需要一个 Skill 定流程、几个 MCP server 供数据，而用户不应该每次都亲手把它们拼起来。插件恰好给了这个组装一个自然的打包边界。

## 一个实操例子

假设明天要给咨询顾问演示：一个能用内部知识与 Salesforce 调研客户、并生成结构化报告的 agent。传统响应往往长过需求本身——新 UI、认证、聊天记录、部署、又一个仓库、又一个服务。但也许这些都不必要：公司已经在用 Claude、Codex 或 Copilot 之类的 agent 环境，你只需打包一个插件——Skill 知道查哪些源、什么顺序、需要什么证据、哪些动作只读、报告怎么组织；底下的 MCP server 提供内部知识、Salesforce、文档存储的访问。装上包，对 agent 说「调研 Acme Corp，按我们的标准模板出客户报告」——第一个可用版本就这么多。没有自定义聊天 UI，没有专门的 agent 应用，除非工作流真的需要，也没有新的编排服务。

这也是作者当初对 MCP 感兴趣的同一个理由：**一个能力够用时，不要造一个应用。** 插件只是把这个理念推高一层。但用了段时间 MCP 后另一个问题浮现：裸 MCP server 往往太底层，不配当分发的最终单元——同一个内部知识 MCP（`search_expertise`、`get_project`、`find_case_study`）完全可复用，但售前工作流要的是搜索、验证相关性、排序证据、写客户摘要；RFI 工作流要的是搜索、把证据映射到具体问题、标记缺失覆盖、生成结构化回答。同一个 MCP，每次需要的操作知识都不同。这就是为什么 Skill 和 MCP 要打包在一起：**MCP 成为基础设施，插件成为可分发的能力。**

## 实际怎么发布与安装

把插件文件夹推到一个 Git 仓库，在旁边放一个小小的市场清单——Claude Code 用 `.claude-plugin/marketplace.json`，GitHub Copilot 用 `.github/plugin/marketplace.json`，其他客户端同理。清单只列插件的名字、版本、plugin.json 的位置（同仓库或单独仓库固定到 tag）。推送、打 release，**仓库本身就是市场**——不需要单独的托管或 Web 应用。接收端，同事把客户端指向那个仓库一次（Claude Code 里 `claude plugin marketplace add your-org/your-repo`，VS Code 或 Azure SRE Agent 里用仓库 URL「Add Marketplace」），然后按名字安装（如 `claude plugin install customer-research@your-org`）。客户端自己拉取 Skill 文件与 MCP 配置——同事永远不需要手动拷贝 SKILL.md 或手工接线，而这个手动步骤正是包所移除的东西。

## 插件并不是神奇地可移植

这一段很要紧，因为「插件」容易制造错觉：好像写一个 Claude 插件，就能在 Claude、Codex、Copilot 和一切未来 agent 里装同一个包。并非自动成立。各家插件系统的能力依然不同——hooks、自定义 agent、UI 表面、权限模型、命令、分发机制，不会因为我们管包叫插件就瞬间可移植。Anthropic 自家的 Claude 插件格式就没在 8 月的首发客户端名单里，它仍在用自己的布局。Agent Plugins 1.0 有意思的地方恰在于此：它不假装所有平台一样，而是定义了一个很小的**可移植性下限**——Agent Skills 加 MCP 配置——其余都留给客户端，并提供扩展命名空间让厂商加私有功能而不污染可移植核心：

```
my-plugin/
├── plugin.json          # 可移植
├── skills/              # 可移植
├── mcp.json             # 可移植
└── com.vendor.client/   # 厂商专属扩展
    └── hooks/
```

比「一口气标准化所有 agent 特性」现实得多。

## 作者会在生产中用的模型

不让厂商专属的插件本身当架构中心：核心能力（Skill 加 MCP）尽可能可移植，插件包作为其上的分发层，厂商扩展放在边缘、只给需要的客户端用。这样，一个团队用 Claude Code、另一个团队用 Codex 时，不必从零重建能力——复用同一核心，只适配目标客户端需要的部分。同一个内部能力（如 architecture-review，带检查清单和指向架构仓库、知识库、安全发现的 mcp.json）定义一次，Copilot 用户、Claude 用户、Codex 用户都能触达同样的过程知识与底层系统——底下变的只是运行时适配器。

## 发现不等于授权

有一条安全原则值得贯穿始终：**可发现、已安装、已授权、已启用、可执行是五种不同的状态，满足其中一种对其他种什么也说明不了。** 一个插件可以已安装、用户对底层系统已授权，而 agent 策略仍然禁用某个具体操作——比如一个客户调研 agent 连着的 Salesforce 连接在技术上允许删除 opportunity，但它永远不被允许那么做。插件简化分发，绝不能坍缩治理边界。

这也意味着一个插件值得你用审视任何其他依赖的眼光来审视：谁拥有它、连接哪些 MCP server、是否执行本地代码、需要什么权限、哪些 Skill 能影响行为、能否执行写操作。GitHub 已经把 Agent Plugin 治理接进企业插件设置与 MCP allowlist；Anthropic 明确警告插件可以包含以本机权限运行的本地 MCP server；OpenAI 把插件安装与底层已连接应用的授权分开。这个分离完全正确——便利的打包不应暗含默认信任。

## 那 MCP 和 Skills 何去何从

MCP 作为产品边界的重要性下降，作为基础设施的重要性上升——作者认为这是好事。成功的插件生态不替代 MCP，反而让 MCP 更有用：插件能带上让 MCP 集成即插即用的指令。与其装一个裸的 Jira MCP server 然后自己琢磨拿它干嘛，不如装一个事故响应插件——它已经知道怎么调查事故、写复盘、创建跟进工单，并接好了 Jira、Datadog 和内部 runbook。用户买的不是集成，是一份运营能力——好得多的抽象。

Skills 的重要性一分未减，甚至更好解释了：Skill 不是「另一种工具」，它是关于如何执行工作的知识。**MCP 说「这里有一个部署工具」；Skill 说「这是我们公司安全部署的方法」；Plugin 说「这里是完整的部署能力」。** 这是作者找到的三者最简心智模型。

## 作者不会做的事

不会因为 Agent Plugins 存在就重写成熟的生产平台；不会强推所有工作流进插件；不会把关键业务逻辑挪进厂商专属的清单；也不会假设装一个包就解决了身份、策略、可观测性或治理——它解决不了。有些工作流真的需要持久状态、复杂事件处理、事务保证、丰富的 UX 或严格的运行时隔离，插件不会让这些要求消失。有用的问题始终很窄：**它究竟是一个新应用，还是一个能在我们已有的 agent 环境里跑的能力？** 若是后者，打包成插件值得考虑。

## 更大的转变：从工具市场到能力市场

多年来，集成市场围绕产品组织——Slack、Salesforce、Jira、GitHub；MCP 市场大多延续同一模式：Slack MCP、Salesforce MCP、Jira MCP。有用，但仍是集成中心。agent 原生的市场可以围绕**结果**组织：调查一起生产事故、准备客户调研、评审一个架构、规划一次发布——每项内部可能依赖多个系统，而这更接近人类真正委派工作的方式：我不会对工程师说「用 Jira、Datadog 和 GitHub」，我说「去把事故查清楚」。GitHub 最近让 MCP server、插件、Skill 和画布从 Copilot app 的同一个 Customize 入口可被发现——UI 本身不重要，底下的信号重要：用户越来越不在乎某样东西是 MCP server、Skill、插件还是工作流实现的，他们在乎 agent 能做什么。这指向一个能力注册表而非每种实现原语各一个目录——注册表描述能力、拥有者、风险等级、审批状态，让平台决定如何为 Claude、Codex 或内部 agent 具体化它，而能力本身在实现演进中保持稳定。

## 一条有用的时间线

2024 年，MCP 标准化了工具与数据的访问；2025 年，Agent Skills 打包了过程知识；2026 年，Agent Plugins 把可复用的能力打包分发。没有一项应读作替代——MCP 没过时，Skills 没取代 MCP，Plugins 也没取代 Skills。**层是组合的**：插件可以包含 Skills，可以引用 MCP server，那些 Skills 教 agent 怎么用底下的 MCP 工具。时间线的重点不是替代，是渐进式组合。

## 尾声

作者写这篇不是要大家这周就开始造插件，而是因为这个抽象值得理解：我们先标准化了 agent 如何连接系统，然后标准化了如何给它们过程知识，现在正在标准化这些能力如何被打包与分发。如果你也倾向于「除非应用真的必要，否则不造又一个 AI 应用」，这条演进路线就有用——有时更好的解法真的就是 MCP 加 Skill 加一个包，让现有的 agent 运行时干剩下的活。重要的不是「插件」这个词，而是：**agent 能力正在变得可组合、可版本化、可分发，而且日益可移植。** 这是值得盯的方向——而且与很多 agent 炒作不同，这一个已经具体到可以用。
<!-- REWRITE_END -->

<!-- SPROUT_START -->
# 《Stop Shipping Individual MCP Servers. Start Shipping Agent Plugins》的发芽报告

## 材料核心

作者梳理 agent 装备的三段演进：MCP（2024）标准化工具与数据的访问、Agent Skills（2025）打包过程知识、Agent Plugins（2026）把两者打包成可分发的能力——2026 年 8 月 6 日 Agent Plugins 1.0 开放规范公开（Vercel 发起，Amazon/Cursor 母公司/微软/OpenAI 共建，Google 加入），可移植核心只有 Skills 加 MCP 配置两个组件。核心论点：裸 MCP server 太底层不配当分发单元（同一个 MCP，售前与 RFI 工作流要的操作知识不同），插件才是「能力」的自然打包边界；但插件不是神奇可移植，分发不能坍缩治理边界（可发现/已安装/已授权/已启用/可执行是五种状态），终局是从工具市场走向围绕结果组织的能力市场。

## 发芽 01：连接、知识、打包——能力抽象的三次上移

### 种子

时间线的关键不是三个新东西，而是三次标准化各自回答的问题不同：MCP 答「能连什么」，Skill 答「怎么干活」，Plugin 答「怎么把两者递到别人手里」——而且层是组合的，没有一层替代前一层。

### 故事

文章用一个递进的真实场景串起三次上移：给 agent 一个 search_documents 工具不等于它会用（MCP 的边界）；给 Skill 教会流程之后，复用要递「两个 MCP server、三个 Skill、两个配置、若干环境变量和二十步 README」（打包的缺口）；直到 `customer-research-plugin` 一次安装、一句「调研 Acme Corp 出标准报告」就能跑。

### Aha 瞬间

判断一个抽象是否成熟，看它把「技术上的可复用」变成「操作上的可复用」没有——分发成本不清零，可复用性就只是存在、而非可用。

## 发芽 02：同一个工具，不同工作流要的知识不同

### 种子

裸 MCP server 之所以不配当分发单元，作者的论据是：内部知识 server 的 `search_expertise`/`get_project`/`find_case_study` 完全可复用，但售前工作流要搜索、验证相关性、排序证据、写客户摘要；RFI 工作流要搜索、把证据映射到具体问题、标记缺失覆盖、生成结构化回答——「同一个 MCP，每次需要的操作知识都不同」。

### 故事

这解释了为什么 Skill 与 MCP 必须捆在一起卖：MCP 降格为基础设施，插件升格为可分发的能力。作者因此建议 agent 围绕稳定操作（research_customer、prepare_rfi、investigate_incident）推理，而不是围绕底层命令——每个能力内部自己组合 Skill 与若干 server。

### Aha 瞬间

「可复用的工具」与「可复用的能力」之间隔着一层工作流知识，而工作流知识是随场景变化的——所以正确的分发单元不是最小的共享件（工具），而是围绕一个任务闭环的最小完整组合（能力）。

## 发芽 03：五种状态互不蕴含——分发便利不能替换单独的授权

### 种子

「可发现、已安装、已授权、已启用、可执行是五种不同的状态，满足其中一种对其他种什么也说明不了」——插件简化分发，绝不能坍缩治理边界。

### 故事

文章给了具体画面：一个客户调研 agent 连着技术上允许删除 opportunity 的 Salesforce 连接，但策略上永远不被允许删除。作者由此要求插件接受依赖级的审视——谁拥有、连哪些 server、是否跑本地代码、要什么权限、哪些 Skill 能影响行为、能否写——并引三家厂商的实践佐证：GitHub 的企业插件设置与 MCP allowlist、Anthropic 对本地权限 MCP server 的警告、OpenAI 把插件安装与底层应用授权分开。

### Aha 瞬间

分发机制的便利天然携带「装了就能用」的暗示，而安全恰恰要求把「能装」与「能干」拆开成独立的闸门——任何新分发层的首要设计题，都是它是否悄悄把原来分开的状态合并了。
<!-- SPROUT_END -->
