---
title: 'From Code Generation to Controlled Execution: Building an AI Coding Agent with AutoGen and Docker'
slug: 2026-10-10-ai-coding-agent-autogen-docker
author: Mustafa Necati Özdoğan
date: '2026-10-10T09:00:00+08:00'
source_url: 'https://medium.com/@mustafanecatiozdogan/from-code-generation-to-controlled-execution-building-an-ai-coding-agent-with-autogen-and-docker-799d53e3e011'
status: processed
image: covers/2026-10-10-ai-coding-agent-autogen-docker.svg
excerpt: >-
  用 Microsoft AutoGen 搭一个人在回路的多智能体工作流：AssistantAgent 生成 Python 代码、approval_func 强制每次执行前人工批准、DockerCommandLineCodeExecutor 容器内隔离运行、执行反馈驱动迭代纠错——并用三种终止条件（成功/用户拒绝/最多 3 次失败 + MAX_TURNS）堵死无限纠错循环。附 AutoGen 0.7.5 的一个实现取舍与五条工程原则。
---

<!-- REWRITE_START -->
# 从代码生成到受控执行：用 AutoGen 和 Docker 打造 AI 编码智能体

> 原文：[From Code Generation to Controlled Execution: Building an AI Coding Agent with AutoGen and Docker](https://medium.com/@mustafanecatiozdogan/from-code-generation-to-controlled-execution-building-an-ai-coding-agent-with-autogen-and-docker-799d53e3e011)
> 作者：Mustafa Necati Özdoğan
> 改写式翻译，保留原文结构与全部数据；署名与原文链接如上。

---

大语言模型能在几秒内按自然语言指令生成 Python 代码，但生成只是问题的一部分：生成的代码错了怎么办？它应该自动执行吗？用户如何在执行前审查代码？智能体工作流如何从失败中恢复、又不陷入无限的纠错循环？

这些问题催生了作者的项目 **AI Python Code Builder & Executor**（Microsoft AutoGen + Python + Docker）。目标是探索一个受控的迭代工作流，把 AI 生成代码、人类监督、容器化执行和反馈驱动纠错组合起来。核心思想一句话：**生成 → 审查 → 执行 → 修复 → 再审查 → 再执行。**（源码在作者 GitHub：AI Python Code Builder & Executor。）

## 1. 工作流设计：四个组件，各管一摊

架构刻意保持小巧，每个组件职责清晰：

- **AssistantAgent**：生成 Python 代码，执行失败时产出修正版。
- **Human approval**：用户对每次执行批准或拒绝。
- **CodeExecutorAgent**：协调批准与代码执行。
- **DockerCommandLineCodeExecutor**：在 Docker 容器内运行已批准的代码。

智能体用 AutoGen 的 **RoundRobinGroupChat** 编排。架构上把「代码生成」与「代码执行」分离：助手专注推理与纠错，执行器专注执行流程——这也让系统在不引入多余智能体的前提下易于理解和扩展。

## 2. 人在回路：执行前的强制批准

最重要的设计决策之一：生成的代码必须经**显式人工批准**才能运行。CodeExecutorAgent 支持 `approval_func`，作者用它向用户请求批准。批准函数展示代码预览（如生成阶乘函数并打印 `factorial(10)` 的片段），询问「Execute this code? [y] Yes / [n] No」。批准则执行；拒绝则工作流直接终止、代码不运行。

关键约束：**每个修正版都必须重新获批——批准了旧版本不等于授权执行新版本。**

### 为什么用 approval_func 而不是 UserProxyAgent？

AutoGen 提供了多种人类参与方式。UserProxyAgent 适合人类需要参与对话、回答问题、补充信息的场景；但本项目里人类的职责更窄：只决定「生成的代码能否执行」。用 `approval_func` 把这个职责保持得显式而具体，不用为了执行批准额外引入一个对话参与者。这背后是更普遍的工程原则：**选择满足实际需求的最小抽象。**

## 3. 用 Docker 执行代码

让 AI 生成的代码直接跑在应用自己的 Python 进程里，会把执行与宿主环境紧耦合。作者改用 AutoGen 的 **DockerCommandLineCodeExecutor**（`work_dir=CODE_WORK_DIR`），在团队运行前启动、结束后停止——生命周期管理很重要，工作流结束时应当清理执行资源。

Docker 在生成程序与宿主 Python 进程之间提供了额外的隔离边界。**但 Docker 不应被视为绝对安全保证**：实际安全水平取决于容器配置、权限、资源限制、网络等运行时控制。本项目是开发学习项目，不是执行任意敌意代码的加固沙箱；生产级实现还需要 CPU/内存限制、执行超时、网络封锁、只读文件系统、非 root 运行及更多沙箱手段。

## 4. 为什么执行器不需要模型客户端

另一个刻意决策：创建 CodeExecutorAgent 时不给它模型客户端。职责切分如下：

| 组件 | 职责 |
|---|---|
| AssistantAgent | 生成并修正 Python 代码 |
| CodeExecutorAgent | 取得批准并执行代码 |
| Docker | 提供执行环境 |

助手负责 LLM 推理，执行器负责协调执行。给两者都配模型客户端，会引入这个工作流并不需要的额外推理能力。这个决定让架构保持聚焦，智能体的角色也更容易推理。

## 5. 反馈驱动的纠错

代码生成很少一次完美：可能缺变量、表达式错误或运行时错误。工作流用执行反馈支持迭代修正——比如助手生成了引用未定义变量的代码，执行结果返回给助手，助手产出修正版，用户再批准修正版后才执行：

```
生成代码 → 人工批准 → Docker 执行
    ├─ 成功 → 结束
    └─ 失败 → 返回错误 → 生成修正 → 再次请求批准
```

这个反馈循环把一个简单的代码生成示例变成了真正有用的智能体工作流——同时也带来一个重要约束：**系统必须知道何时停止。**

## 6. 用终止条件控制工作流

不设边界的迭代智能体会反复生成并执行修正。项目组合了成功检测、拒绝处理和最大失败次数：

```python
successful_execution = FunctionalTermination(is_executor_result_successful)
rejection_termination = FunctionalTermination(is_executor_result_rejected)
max_failures_termination = MaxExecutionFailuresTermination(
    max_failed_executions=MAX_FAILED_EXECUTIONS)
termination = (successful_execution | rejection_termination
               | max_failures_termination)
```

另用 `MAX_TURNS` 作为整体对话上限。四个控制各司其职：成功执行（结果视为成功即结束）、用户拒绝（拒-execution 即停）、最大失败次数（默认 **3**，防无限重试）、最大轮数（对话整体边界）。

### AutoGen 0.7.5 的一个实现取舍

由于 CodeExecutorAgent 不带模型客户端，工作流处理的是执行器的 TextMessage 输出，而非 CodeExecutionEvent.result.exit_code 这类结构化结果。一个小适配器解释执行器消息并归类为成功/失败/拒绝。这很轻量，但有局限：**从消息文本推断执行状态，不如消费结构化执行结果健壮**——输出格式变化或未处理过的错误类型可能导致误分类。未来迭代可用结构化执行事件或自定义执行器接口，更可靠地区分程序错误、超时、资源耗尽与容器故障。这个取舍说明：智能体系统需要的不只是「模型 + 工具调用」，编排逻辑还必须处理失败与生命周期。

## 7. 配置与测试

项目用环境变量配置 `OPENAI_API_KEY`、`OPENAI_MODEL`、`CODE_WORK_DIR`、`CODE_PREVIEW_MAX_LINES`、`MAX_FAILED_EXECUTIONS`、`MAX_TURNS`，避免把环境相关设置硬编码进应用。还为自定义的执行失败终止逻辑写了测试——这一点尤其重要，因为状态误分类要么让重试失效、要么让工作流在错误的时刻终止。智能体应用的测试不应只覆盖快乐路径，还要覆盖拒绝、连续失败、重置行为和意外的执行结果。

## 8. 五条经验

1. **代码生成与代码执行是不同的职责**——模型写出「看起来对」的代码，不代表它正确或可安全执行。
2. **人工批准应该一开始就进工作流设计**，而不是先做了自动执行再补的补丁。
3. **智能体工作流需要显式停止条件**——重试能改善结果，但必须有界。
4. **工具输出需要可靠的解释**——工作流的可靠性取决于解释执行结果并决定下一步的逻辑。
5. **隔离与批准应对的是不同的风险**——人工批准提供决策点，Docker 提供执行边界，两者都不能替代恰当的安全控制。
<!-- REWRITE_END -->

<!-- SPROUT_START -->
# 《From Code Generation to Controlled Execution: Building an AI Coding Agent with AutoGen and Docker》的发芽报告

## 材料核心

这篇文章把「AI 写代码」从演示推进到受控生产雏形：AutoGen 的 RoundRobinGroupChat 编排四个组件，用 approval_func 把人类批准做成每次执行的强制关卡（修正版必须重新获批），用 DockerCommandLineCodeExecutor 把执行搬出宿主进程，用执行反馈驱动纠错循环，再用三个 FunctionalTermination/MaxExecutionFailuresTermination 加 MAX_TURNS 堵死循环。作者还坦白了一个 0.7.5 的取舍：从 TextMessage 文本推断执行状态不如结构化事件健壮。

## 发芽 01：批准是关卡，不是开关

### 种子

「批准了旧版本不等于授权执行新版本」——每次修正版都要走一遍完整的批准流程。

### 故事

很多 human-in-the-loop 实现把批准做成一次性授权：用户点了一次「允许」，之后系统就默认永远允许。这篇文章的设计里，批准绑定的是「这一份具体的代码」，代码变一个字符，授权就作废。配合「拒绝即终止整个工作流」，人类的意志在每一轮都保持最高优先级。

### Aha 瞬间

人类监督的强度不取决于「有没有人点头」，而取决于「每次变更是否都要重新点头」。把批准从开关改成关卡，人在回路的「在」才是真的在。

## 发芽 02：最小抽象原则的三次落地

### 种子

用 approval_func 而非 UserProxyAgent；执行器不配模型客户端；架构只在必要时引入新智能体。

### 故事

同一个原则在文中出现了三次：人类的职责只是「批准/拒绝」，就不引入能闲聊的对话代理；执行器只负责「拿批准、跑代码」，就不给它推理能力；分离生成与执行就够了，就不加第四个智能体。每一次克制都让系统的角色更容易推理、行为更容易测试。

### Aha 瞬间

智能体系统里最贵的往往不是缺能力，而是多出来的能力——每个多余的模型客户端都是一条需要解释、测试和维护的随机性来源。「能加」不是「该加」的理由。

## 发芽 03：终止条件是智能体工作流的刹车系统

### 种子

成功检测、用户拒绝、最大失败次数（默认 3）、MAX_TURNS 四层终止，外加对终止逻辑本身的专项测试。

### 故事

反馈纠错循环是智能体的价值所在，也是失控的入口：失败→修正→再失败可以永远转下去。这篇文章把「何时停」当成和「怎么跑」同级别的一等设计问题，甚至因为状态误分类会导致「该停不停、不该停乱停」而为终止判定专门写测试。

### Aha 瞬间

评估一个智能体工作流的成熟度，别只看它能把任务做成的上限，要看它停下来的条件写得有多明确——刹车系统的规格，比引擎马力更能说明这是一辆能上路的车。
<!-- SPROUT_END -->
