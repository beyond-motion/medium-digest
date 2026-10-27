---
title: 'SoPhi Harness — A Black Box That Can''t Crash the Plane: Teaching an Agent to Learn Without Touching Its Controls'
slug: 2026-10-27-sophi-harness-flight-recorder
author: Shukri Shukriev
date: '2026-10-27T09:00:00+08:00'
source_url: 'https://medium.com/towards-artificial-intelligence/sophi-harness-a-black-box-that-cant-crash-the-plane-teaching-an-agent-to-learn-without-touching-2c4a771e6b9e'
status: processed
image: covers/2026-10-27-sophi-harness-flight-recorder.svg
excerpt: >-
  Kotlin 智能体框架 SoPhi 给自己装航空黑匣子：只记录不回放、观察者永不反哺控制流、记录器故障也不能弄垮一次 turn——以及三个真实教训：总线信号会撒谎、并发计数器会丢增量、被拔掉的黑匣子和安静航程长得一模一样。
---

<!-- REWRITE_START -->
# SoPhi Harness：一台不会坠机的黑匣子

> 原文：[SoPhi Harness — A Black Box That Can't Crash the Plane: Teaching an Agent to Learn Without Touching Its Controls](https://medium.com/towards-artificial-intelligence/sophi-harness-a-black-box-that-cant-crash-the-plane-teaching-an-agent-to-learn-without-touching-2c4a771e6b9e)
> 作者：Shukri Shukriev（Building SoPhi 系列第 9 篇）｜12 min read

---

## 黑匣子的三条规则

每架客机尾舱都有一个飞行员从不照着飞的盒子。它接在与驾驶舱仪表相同的数据总线上，写下一切：高度、油门、每个被扳动的开关。但它有三条比内容更重要的规则：**绝不向操纵系统回传任何信号；绝不要求机组做任何事；它自己坏了，飞机照样落地**。一个能把飞机搞下来的记录仪，才是机上最危险的东西。

SoPhi 是一个 Kotlin 智能体框架：它靠调用工具干活——读文件、跑命令、抓网页——而每一次调用都值得记录。它的学习系统从记录仪起步，第一个惊喜是**线路早已在机体里**：插件系统出厂就带两个沉睡的挂载点（sophi-extensions 里的 HookPoint.BEFORE_TOOL 与 AFTER_TOOL），从没人触发过；而 AgentLoop 本来就在广播每次工具调用——因为终端要为每次调用画个转圈动画。总线一直在跑，只是没人往上面插记录仪。

2026-07-09 的 ADR-008 为学习系统四个阶段定下赌注：**学习逻辑住在独立的 sophi-learning 模块里，通过插件系统观察智能体，绝不进主循环**。同日的 ADR-009 定下另一半：记录什么、智能体被允许读回什么。本文讲第一阶段——它几乎不算什么聪明活，任务就是把记录仪接上线，同时不让它碰到操纵杆。

## 一根接到正在运行的总线上的线

AgentLoop 通过 onEvent 回调广播 TurnEvent：文本增量、工具调用开始、工具调用结束。终端画它们，SophiRuntime 过去把它们扔掉。激活沉睡挂载点不需要新事件系统，只需要一个从一条流到另一条流的适配器。整个 TurnEventBridge.kt 的要点在返回类型：bridge 就是一个 `suspend (TurnEvent) -> Unit`，与循环本来就接受的 onEvent 同形，宿主把它与自己的处理器组合后传入。**AgentLoop 根本不知道插件注册表的存在**，sophi-core 依旧不依赖 sophi-extensions；循环本体唯一的改动，是给既有事件补上两个手里已有的字段。

被否掉的替代方案是在循环里放一个 LearningInterceptor、在分发代码里直接调学习存储——第一天就能跑通，但会让每个嵌入 sophi-core 的人背上不想要的学习逻辑，而且把记录仪的线路装进了操纵系统，正是黑匣子规则要禁止的耦合。ADR-008 的第一条理由就否了它：core 保持最小。

## 记录器只和总线一样诚实

那行后来补上的 `failed = failed || result.startsWith("Error: ")` 是个有用的教训。7 月时 isError 只在工具抛异常或被拒绝时为真，而 SoPhi 大多数内置工具从不抛异常——它们校验输入后返回 "Error: path is outside the workspace" 这样的字符串，模型读到后会自行恢复。**记录仪把这些调用全记成了成功。三周里没人发现**，直到有人追一个不相干的竞态时顺带揪出来。留下的注释才是真教训：记录仪的诚实度上限是总线信号的诚实度。桥没接错，是总线悄悄搞错了哪些调用失败了。

## 只记录，不回放

记录仪需要会话文件里没有的东西。ADR-009 之前，AgentLoop 只存用户输入和助手回答，中间的工具轮次（哪个工具、什么参数、返回了什么）活过一个 turn 就没了——而第二阶段的会话末评估器和第四阶段的训练导出都需要它们，事后无法重建。

天真地保存会弄坏别的东西：PromptBuilder 把每条会话条目变成下次请求的消息，持久化的工具轮次会搭车进每个后续 prompt——每轮多烧 token，还有格式坏掉的真实风险（供应商要求每个工具调用与结果严格配对）。解法是给条目打个标记而非开新文件：工具轮次作为真实条目追加，metadata 标 `replay=false`；PromptBuilder 在出口处一行 filter 把它们丢掉。**这就是飞行记录仪第一条规则的代码形态：盒子挂在总线上，驾驶舱永远不读它。**ADR-009 把这个保证写成测试：改动前后，从会话构建出的 prompt 必须逐字节相同。

规则成立的前提是每个读者都遵守——第一次评审就抓到一个不遵守的。会话过长触发压缩时，ContextCompactor 直接遍历 session.branch()，把原始工具输出带进了发给模型的总结 prompt，总结又回到对话里：一个本不该再见到工具结果的会话，下一轮读到了它们的转述。修复与 PromptBuilder 同款 filter。同一段注释里还藏着更隐蔽的 bug：keepRecentCount=4 本意是「保留对话最后四条消息」，算上工具轮次后，一个繁忙的 turn 能用工具调用填满全部四个槽位，把用户真正的问题挤进总结。

三个月后压缩器又回来了——这次是故意的。纯对话总结保得住大意、丢得了细节：改过哪些文件、哪条命令失败过。十月中旬的一轮上下文管理改造给压缩器配了 WorkingSet，**专门从它被告知忽略的 replay=false 条目里提取事实**（读写过哪些文件、跑过哪些命令、退出码），对话文本仍然只装对话。用黑匣子的话说：机组依然听不到录音带，但现在拿到一份据录音带填好的检查单。这不是破坏规则，是精化规则。

这个标记还捎带了一个作者没规划的特性。十月新加的停止按钮要保存一个在工具调用中途被打断的 turn——供应商拒绝没有结果的工具调用，于是 saveStopped 写入一条「Stopped by ...」的合成结果，打上同样的标记：记录对评估器和导出保持完整，prompt 永远不知道合成结果的存在。没有设计任何新机制，7 月的规则已经覆盖了它。月末 /undo 与文件检查点复用了同一条通道：turn 死于网络错误但工具已经改了文件时，undo 需要那轮调用在盘上，于是同一个函数以同一标记保存「Stopped by an error」。

## 每盘带子都要有航班号

无法归因的记录只是噪音。第四阶段要把会话变成训练样本，而缺少「产生它的模型」和「它运行时的系统 prompt」的训练样本毫无用处——这两样都是每 turn 的 AgentConfig 值，过去从不落盘。ADR-009 把它们放进前一篇文章引入的 `<id>.meta.json` sidecar，永不写入 JSONL 条目格式；sidecar 以 ignoreUnknownKeys 读取，所以 7 月之前的每个旧会话照常加载；SessionManager 给出 no-op 默认实现（内存型会话管理器干脆不记录快照）；CLI、Web 宿主与 SophiRuntime 各自在会话开始时调用一次，全部用 runCatching 包裹。

## 不能坠机的记录仪

**能搞垮被观察系统的观察者，比没有观察者更糟。**ADR-008 把它写成约束，LearningPlugin 在两处强制执行：每个 hook 体包进吞掉自身异常的 wrapper，每次写存储都过一个 runCatching 的 append 助手。存储本身遵循 ADR-005 的 append-only 设计：~/.sophi/learning/ 下每行一个 JSON 对象，每条记录带 scope 标签（工作目录），教训可按项目过滤、也可跨项目召回；写入中途崩溃最多留下被读者跳过的半行。

光有意图不够，评审证明了这个纪律必须靠机制。AgentLoop 用 async 并发跑一个 turn 的工具调用，同一会话的 AFTER_TOOL hook 会从多个协程同时触发——第一版用普通 Int 统计调用数与错误数，在这个负载下**静默丢失增量**：无异常、无崩溃，只是记录仪写错数字。修复是原子计数器加 @Synchronized。

同一轮评审还发现了「从不抱怨的记录仪」的二阶代价：**它没接上时，什么都不会抱怨**。SophiRuntime.turn() 会广播 AFTER_TURN，但 CLI 经自己的 TurnController 驱动 AgentLoop、从不广播——CLI 会话只录到工具事件、没有 turn 结局。更大的一版同类缺口持续了两个月：八月加入的桌面伴生进程从不调 recordSessionEnd，伴生会话从未被评估过；九月初的修复把会话结束接线统一收进 SophiRuntime.recordSessionEnd 供两个宿主调用。**被拔掉的黑匣子，和录下一段平静航程的黑匣子，看起来一模一样。**fail-silent 规则没错，但它意味着每个宿主的接线都必须直接测试——缺失的记录仪不产生任何可注意的错误。

recordSessionEnd 本身展示了「便宜、机械、永远在线」这个理念走了多远：它先返回机械结果再跑可选的 LLM 评估，只要成功信号的调用方无需等待、无需依赖模型。这个返回值如今被记忆系统的遗忘逻辑用来判断哪些被召回的记忆值得召回；planningNote 字段随八月的 /goal 而来——都是第一阶段定义的字段，被第一阶段想不到会存在的系统填上。

## 读带子，从计数开始

记录仪接好后，第一阶段合上了最小的环。ToolStatsStore 把工具事件日志折叠成 per-scope、per-tool 的数字：尝试数、失败数、当前连败次数、最近几条错误摘录；从文件重建至多每分钟一次，**零 LLM 调用，纯计数**。ToolReliabilitySection 把这些数字变成系统 prompt 里的一条备注——且只在必要时：「一条总是触发的警告就是噪音」，所以门槛有两部分：至少 5 次尝试才够格被评判，然后要么失败率过半、要么连败 3 次。大多数会话什么都不注入；当 fetch_url 对着不稳定的内网超时了一上午，模型在重试前会读到「fetch_url：最近 6 次失败 4 次。最后的错误：……」。

它刻意不雄心勃勃：职责是在任何更聪明的东西架上去之前，把管线端到端打通（事件、桥、hook、存储、折叠、prompt）。它后来还多干了一份活：八月到来的自我改进编排器（ADR-027/029）决定在哪里提议改动时，读的正是 ToolStatsStore.stats() 这个同款折叠——只是换了个新消费者。

## 仪表先行

上一篇文章让每个子代理运行在 sidecar 里留下可追溯的记录，使一次委派能回溯到产生它的那个 turn；第一阶段是同一个本能作用于整个智能体：**把发生的事写下来，写在一个无法改变后续走向的地方**。这里面没有任何聪明东西——桥二十行，replay 规则是一条 filter 用在两处，可靠性备注是个阈值检查。让它成立的是约束本身：循环不知道自己被观察，prompt 看不见记录，记录仪弄不垮一个 turn。后面每个阶段都依赖这三件事同时为真。

飞行记录仪是在飞行之后才挣饭吃的——等调查员坐下听带子。第一阶段故意把那个座位空着；下一篇文章会填上它：本阶段刻意没做的唯一一次 LLM 调用——每次会话结束时的复盘，读记录、决定什么值得记住。

<!-- REWRITE_END -->

<!-- SPROUT_START -->
# SoPhi Harness — A Black Box That Can't Crash the Plane（发芽报告）

## 材料核心

SoPhi（Kotlin 智能体框架）的学习系统第一阶段是一次「把黑匣子装上飞机」的工程：复用终端画转圈动画时就在广播的 TurnEvent 总线，用一个二十行的桥接进插件系统的 BEFORE_TOOL/AFTER_TOOL 挂载点，铁律是记录侧永不反哺控制流——工具轮次持久化但标 replay=false，prompt 构建器逐字节地看不见它们；记录仪自己的每个异常都被吞掉，绝不能弄垮一次 turn。文章的全部智慧在三个真实教训里：总线信号会撒谎（"Error: " 字符串约定让失败被记成成功三周）、并发计数器会静默丢增量、以及 fail-silent 的终极代价——被拔掉的黑匣子和录下平静航程的黑匣子一模一样，所以每条宿主接线都必须直接测试。

## 发芽 01：观察者纪律——「只记录、不回放」是一个可测试的架构契约

### 种子

给系统加可观测性时，最常见的腐烂路径是「顺手」：日志里多带一点上下文、prompt 里多塞一条历史，每一步都合理，直到观察通道反过来改变了被观察系统的行为。

### 故事

SoPhi 把边界做成了机器可验证的东西：replay=false 的条目持久化在会话 DAG 里、对评估器和训练导出可见，但 PromptBuilder 和压缩器的对话视图一律跳过，并有「改动前后 prompt 逐字节相同」的测试守着。有趣的是规则的两次精化——压缩器的 WorkingSet 从被忽略的条目里提取「事实」（文件、命令、退出码）而非文本，停止按钮用同一标记保存合成结果——都在不破坏契约的前提下扩展了系统的能力。

### Aha 瞬间

**边界不是一条线，而是一份谁都要签的契约。**第一个评审就抓到 ContextCompactor 直接遍历分支绕过了过滤——规则只约束写的人没用，必须约束每个读的人。把「观察不改变被观察者」写成逐字节测试，是把架构哲学翻译成 CI 能执行的语言，这一步比写出哲学本身难得多。

## 发芽 02：fail-silent 的账单——安静不等于健康

### 种子

「学习模块绝不能弄垮 turn」显然正确，SoPhi 用 runCatching 包住每个 hook 和每次写盘来兑现它。但文章最锋利的观察是这笔决定的二阶账单：一个从不抱怨的组件，在它根本没被接上时，同样一声不吭。

### 故事

CLI 宿主用自己的 TurnController 驱动循环、不广播 AFTER_TURN，CLI 会话于是只录到工具事件、没有 turn 结局——没有任何报错；桌面伴生进程忘了调 recordSessionEnd，两个月的会话从未被评估——也没有任何报错。两处都不是学习模块的代码有 bug，而是「接线」这个没人测的环节出了缺口。修复方式是收拢：把会话结束接线统一到 SophiRuntime.recordSessionEnd，让两个宿主无法各写各的。

### Aha 瞬间

**「被拔掉的黑匣子和录下平静航程的黑匣子一模一样」适用于一切静默降级的基础设施。**监控、埋点、审计日志这类「永远不该出声」的组件，唯一可靠的验证方式是反向测试——专门验证「它确实在记录」，而不是等着业务错误暴露它的缺席。为接线写测试听起来琐碎，但 SoPhi 的两个月缺口证明了它的价格标签。

<!-- SPROUT_END -->
