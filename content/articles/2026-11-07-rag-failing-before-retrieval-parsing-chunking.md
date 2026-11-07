---
title: 'Your RAG May Be Failing Before Retrieval Even Starts'
slug: 2026-11-07-rag-failing-before-retrieval-parsing-chunking
author: 'Ramchandra Regmi'
date: '2026-11-07T09:00:00+08:00'
source_url: 'https://medium.com/@rregmi1993/your-rag-may-be-failing-before-retrieval-even-starts-f7ecb2f93493'
status: processed
image: covers/2026-11-07-rag-failing-before-retrieval-parsing-chunking.svg
excerpt: >-
  「知识在检索开始前就被切错了」：解析决定什么信息存活、分块决定什么能被一起取回——六种分块策略对比与「百万文档变千万向量」的运营账，FDE 的真问题不是 chunk size。
---

<!-- REWRITE_START -->

# 你的 RAG 可能还没开始检索就已经在失败了

> 原文：[Your RAG May Be Failing Before Retrieval Even Starts](https://medium.com/@rregmi1993/your-rag-may-be-failing-before-retrieval-even-starts-f7ecb2f93493) — Ramchandra Regmi

---

## 一个简单的例子

考虑一份排障指南：

```
Alarm: LINK_DOWN
Possible Cause: Optical receive power is below threshold.
Recommended Action: Check Rx power and inspect the fiber connection.
```

在人眼里，这是一条信息：

```
LINK_DOWN
|
+ — Cause
|
+ — Recommended Action
```

但假设文档被这样解析、分块：

```
Chunk 1: Alarm: LINK_DOWN + Possible Cause: ...
Chunk 2: Recommended Action: Check Rx power...
```

现在想象用户问：「LINK_DOWN 发生时我该检查什么？」

检索器可能找到 Chunk 1——但真正的动作在 Chunk 2。**LLM 没有问题，向量数据库没有问题。知识在检索开始之前就被切错了。**

## 解析不是文本提取

文档不只是文本。一份技术 PDF 可能包含标题、子标题、表格、图片、图注、列表、代码块、多栏、页眉页脚、页码引用——**这些元素之间的关系，往往与文本本身承载一样多的含义。**

比如「5.2 Session Timeout」这个标题告诉我们它下面的段落讲什么。解析器提取了段落、丢了标题——文本看起来仍然有效，但我们已经丢了有用的上下文。表格同理：

```
Version | Timeout | Retry Count
4.1     | 300s    | 3
4.2     | 600s    | 5
4.3     | 600s    | 7
```

有用的信息不是「4.2 | 600 | 5」，而是这层关系：

```
Version 4.2
|
+ — Timeout: 600 seconds
|
+ — Retry Count: 5
```

**好的解析应该保住这层关系。**

## 数据源决定解析策略

作者不会对每个数据源用完全相同的解析逻辑——源的结构本身就在告诉我们信息如何关联：

- **产品手册**：Document → Chapter → Section → Subsection
- **客服工单**：Problem → Symptoms → Investigation → Root Cause → Resolution
- **API 文档**：Endpoint → Parameters → Request → Response → Errors
- **代码**：Repository → Module → Class → Function

把一切拍平成一个大文本文件、每 500 token 切一刀，是在建索引之前就扔掉有用信息。实践中的五种解析策略：

1. **版式感知解析（Layout-Aware）**：适合标题、栏、表格、图注、页面结构承载含义的 PDF 与文档。目标是保住阅读顺序与文档层级，而非返回扁平文本流。
2. **结构感知解析（Structure-Aware）**：适合本身就有逻辑层级的来源——技术手册、政策、wiki、API 文档。这个结构之后可以变成元数据、也可以引导分块边界。
3. **表格感知解析（Table-Aware）**：行列关系重要时使用。解析器应让列头始终与值绑定，使被取回的一行独立看仍然有意义。
4. **OCR/扫描件解析**：无文本层的图像 PDF、扫描手册、表单。**OCR 输出必须校验**——产品名、告警码、CLI 命令、数字的识别错误会直接影响检索。
5. **领域感知解析（Domain-Aware）**：某些企业数据的最佳结构来自业务工作流本身——把工单的各逻辑字段保存为分开但关联的单元，而不是当作一段长对话。

所以 FDE（一线部署工程师）的决策从来不是「哪个解析器流行」，而是：**「哪些信息关系必须在这个用例中穿过解析存活下来？」**

## 分块不是找完美数字

RAG 的常见问题是：「我的 chunk size 该多大？500？800？1000？」

作者认为更好的问题是：**「哪些信息必须留在一起才能仍然有意义？」**

- 对告警示例：Alarm + Cause + Recommended Action 大概应该留在一起。
- 对 API：Endpoint + Parameters + Response + Errors 可能需要留在一起。
- 对客服工单：Problem + Root Cause + Resolution 可能比「在任意 token 边界切开对话」更有用。

Chunk size 仍然重要——但它应该排在「理解信息结构」**之后**。

### 六种分块策略

正确解析之后，下一个决策是把结构化内容转成可检索单元的方式。应该**比较以下策略**而不是为所有文档类型全局选一个：

- **固定尺寸（Fixed-size）**：弱结构文本的简单基线。
- **递归（Recursive）**：先保住更大的自然边界，必要时才细切。
- **结构感知/按标题（Heading-based）**：用文档节作为主检索单元。
- **语义（Semantic）**：主题变化处切开，而不是只看 token 数。
- **父子（Parent-child）**：检索小块，返回更大的父级上下文。
- **领域感知（Domain-aware）**：用业务概念——Alarm+Cause+Remedy、Problem+RCA+Resolution。

**1. 固定尺寸是基线，不是最终设计。**500 token + 100 重叠易于实现、适合第一个实验，但切分器不理解文档。一个固定边界可能落在「The timeout can be changed using…」与它的下一节之间——或者更糟，把两个不同节的部分塞进同一个 chunk，**向量于是代表了不止一个主题**，这可能降低检索精度。

**2. 递归分块**适合文档有自然边界但单节可能过大的情形：Section → Paragraph → Sentence → Token Limit 的递进——节放得下就整节保留；太大就按段切，再按句切，最后才按 token。它比固定尺寸保住更多结构、又不需要语义处理，是强的通用基线。

**3. 结构感知分块**：对结构化文档，作者倾向先看文档层级——`Section 5.1 → Chunk`、`Section 5.2 → Chunk`……每个 chunk 已经代表一个有意义的概念。还可以附元数据：

```
document: Router-X Administration Guide
product: Router-X
version: 4.2
chapter: Session Management
section: 5.2
heading: Session Timeout
page: 84
```

**文本给内容，元数据告诉位置**——这在之后的过滤与排序里极其有用。

**4. 父子分块解决一个有趣的取舍**：小块提升检索精度，大块给 LLM 更多上下文。父子分块两者兼得——**检索小块（精确），命中后返回父级节（上下文）**：

```
Small Chunk → Precise Retrieval → Parent Section → More Context → LLM
```

当一个技术操作横跨几段时特别有用。

**5. 语义分块有用，但不免费**：标题不够用时（一个长节里逐渐换主题），语义分块能检测主题变化、产出更连贯的块——但它引入额外的处理与成本。**作者不会因为它听起来更高级就用它；只有评估显示结构感知或递归不够时才用。**

**6. 领域感知分块**：很多企业系统里，最好的 chunk 边界来自业务含义而非分词器——电信排障的 Alarm+Cause+Impact+Recommended Action、工单的 Problem+Investigation+Root Cause+Resolution、API 文档的五段式。这些单元对用户有意义，常比任意 token 窗口做出更好的检索块。**这正是 FDE 介入价值最大的地方：理解客户的领域能直接改进分块架构。**

## 重叠有代价

分块重叠有用——它保护边界附近的信息（Chunk 1 含 A B C D，Chunk 2 含 C D E F，C 与 D 都保住了）。但重叠也意味着：

**更多文本 → 更多 chunk → 更多嵌入 → 更大索引 → 更多存储 → 潜在的重复检索。**

几千份文档时这可能无所谓；**到百万级记录，它成为一个架构决策。**

## 一百万份文档可以变成一千万个向量

分块在这里变成扩容问题。假设来源有 1,000,000 份文档：

- 每份平均 8 个 chunk → 8,000,000 个嵌入
- 另一种策略每份 15 个 → 15,000,000 个嵌入

**源数据没变，分块策略变了。但我们几乎翻倍了：嵌入工作量、向量存储、索引大小、索引时间、重建索引时间。**

这就是为什么作者绝不会只看检索准确率来评估分块——**运营影响同样重要。**

## 策略怎么比

一个简单的取舍速览：

```
Fixed-size   → 最简单，但结构感知最弱
Recursive    → 好的通用基线
Heading-based→ 对结构化文档很强
Semantic     → 主题连贯性强，处理成本更高
Parent-child → 精确检索 + 更宽的生成上下文
Domain-aware → 业务结构显式时最强
```

没有通用赢家。策略应该对着真实文档与真实用户问题来选。

## 我会怎么选

在做出生产决策之前，先建一个小基准。假设有 150 个有代表性的用户问题，对每个问题标注：期望文档、期望节、期望产品、期望版本。然后比较策略——A（固定 500+100 重叠）vs B（递归）vs C（按标题）vs D（父子检索）。

检索指标要比：Recall@K、Precision@K、MRR、Hit Rate。但**还要比**：chunk 数量、平均 chunk 大小、索引大小、嵌入成本、检索延迟、上下文 token 数。

**最好的架构不一定是检索分数最高的那个，而是在可接受的运营成本下给出可接受检索质量的那个。**如果简单实现表现一样好，就保持简单——复杂度必须自己挣得它在架构里的位置。

## FDE 的问题不一样

在客户发现（discovery）阶段，作者不会问「你想要多大的 chunk size」，他会问：

- 你的信息是怎么结构的？
- 哪些信息必须留在一起？
- 一个正确答案通常需要什么？
- 用户搜索用的是精确标识符还是自然语言？
- 产品版本重要吗？表格重要吗？
- 答案通常来自一节还是几节？

**这些问题引出分块策略；技术在它之后。**

## 一个实用的起始架构

对结构化企业文档，作者通常这样起步：需要更宽上下文时——`Retrieved Child → Parent Section → LLM Context`。然后把它与更简单的固定尺寸实现做基准对比。

## 关键点

人们很容易把时间花在比较向量数据库与嵌入模型上。但如果在摄入时发生了这个——原文的 Alarm+Cause+Recommended Action 变成了 Chunk 1 只有 Alarm、Chunk 2 只有 Cause、Chunk 3 只有 Recommended Action——**检索问题就已经被制造出来了。**

换向量数据库修不了它。加大 LLM 上下文窗口修不了它。换更大的模型修不了它。**第一个要求是：让知识以「它实际会被需要的形式」可被检索。**

结论：在 RAG 里，最终答案的质量起步得比 LLM 早得多——**解析决定什么信息在摄入中存活，分块决定什么信息能被一起检索，元数据保住信息周围的上下文。**这些决策直接影响：检索质量 → 索引大小 → 嵌入成本 → 上下文质量 → 生成质量。

对 FDE，最有用的问题因此不是「最好的 chunk size 是多少」，而是：

**「哪些信息必须留在一起，系统才能按用户实际的提问方式取回正确的证据？」**

一旦清楚了这一点，chunk size 就成了一个实现细节。

<!-- REWRITE_END -->

<!-- SPROUT_START -->

# 《Your RAG May Be Failing Before Retrieval Even Starts》的发芽报告

## 材料核心

用 LINK_DOWN 排障指南被切进两个 chunk 的最小例子证明：LLM 与向量库都没错，知识在检索开始前就被切错。框架三层：**解析**（五种策略——版式/结构/表格/OCR/领域感知，源的结构本身就是答案，「编造页坐标式」的统一解析会先扔掉信息关系）→ **分块**（六种策略对比——固定/递归/结构感知/语义/父子/领域感知，先问「哪些信息必须留在一起」再问 chunk size）→ **运营账**（重叠与策略选择会放大嵌入量：一百万文档 × 8 vs 15 chunks = 八百万 vs 一千五百万向量，索引/存储/重建时间近乎翻倍）。评估要同时比检索指标（Recall@K/MRR）与运营指标（索引大小/成本/延迟）；FDE 的 discovery 问题不是「要多大 chunk」而是「信息怎么结构、什么必须留在一起」——技术在其之后。

## 发芽 01：「检索前的失败」是 RAG 故障的第一嫌疑

### 种子

用户问 LINK_DOWN 该检查什么，检索器命中了 Chunk 1（告警+原因），动作在 Chunk 2——换向量库、加大上下文、换更大的模型都修不了它。

### 故事

这与 11-03 站内已译的版式分析文（Raggae SDK 工具实战）构成同一命题的两面：那篇讲「怎么实现保留结构」，这篇讲「为什么要保留、保留什么、怎么选策略」。两层结论同构：RAG 的质量上限在摄入时刻就被锁定，检索与生成只是在花这笔遗产。修复顺序永远是：先定位证据关系→再提取→再决定归属。

### Aha 瞬间

**「答案就在文档里但模型没用上」这类故障，第一嫌疑人不是检索器也不是模型，而是摄入阶段对信息关系的破坏。**排查顺序应该反过来走：从 chunk 的切法开始倒查，而不是从模型参数开始正调。

## 发芽 02：从「数字崇拜」到「关系清单」——chunk size 问题的降格

### 种子

RAG 社区最常问「500 还是 800 还是 1000」；作者把问题降格为「哪些信息必须留在一起才能仍然有意义」，chunk size 变成「实现细节」。

### 故事

支撑这个降格的是六策略对比与运营账：固定尺寸只是弱结构的基线，语义分块「有用但不免费」——只有评估显示更便宜的手段不够时才值得上；而策略选择会直接放大嵌入与索引规模（8 vs 15 chunks/文档≈一千万向量的差距）。所以决策输入是两组指标的和：检索质量（Recall@K/MRR/Hit Rate）+ 运营成本（索引大小/嵌入成本/延迟/上下文 token）。「最好的架构是可接受成本下可接受质量的那个」——复杂度必须自己挣位置。

### Aha 瞬间

**把「调参数」升格为「列关系清单」：凡是你能写出「A+B+C 必须留在一起」的地方，分块策略就自动确定了；写不出来的地方，才轮到基准实验说话。**参数是清单的下游产物。

## 发芽 03：discovery 问题清单——FDE 的领域访谈模板

### 种子

作者在客户发现阶段不问「你要多大 chunk size」，改问七个问题：信息怎么结构、什么必须留在一起、正确答案需要什么、用户用精确标识符还是自然语言搜、版本重要吗、表格重要吗、答案来自一节还是几节。

### 故事

这七个问题每个都直指一个后续架构选择：结构→解析策略；必须同组→分块边界；精确标识符→检索方式（关键词混合）；版本重要→元数据 schema；表格重要→表格感知解析；单节 vs 多节→chunk 粒度与父子检索。领域知识由此变成可执行的架构参数——「理解客户的领域能直接改进分块架构」是 FDE 介入价值的正名。

### Aha 瞬间

**「你的信息是怎么结构的」是所有数据密集系统访谈的第一问——它同时决定解析、分块、元数据与检索四层设计。**拿这七个问题当模板，任何 RAG/搜索项目的需求会前从玄学变成结构化清单。

<!-- SPROUT_END -->
