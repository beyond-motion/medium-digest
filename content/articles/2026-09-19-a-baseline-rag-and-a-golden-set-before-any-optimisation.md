---
title: 'A Baseline RAG and a Golden Set Before Any Optimisation'
slug: 2026-09-19-a-baseline-rag-and-a-golden-set-before-any-optimisation
author: Nadeem Khan (NK)
date: '2026-09-19T09:00:00+08:00'
source_url: 'https://medium.com/learnwithnk/a-baseline-rag-and-a-golden-set-before-any-optimisation-c0c45de5847b'
status: processed
image: covers/2026-09-19-a-baseline-rag-and-a-golden-set-before-any-optimisation.svg
excerpt: >-
  修好 6 个回答同时弄坏 3 个的改动，报表上只显示「+3」。作者给出 RAG 优化的前置三件套：一条刻意朴素的基线管线、一份带证据 span 的黄金问题集、一张能逐题对比两次运行的记分卡——全部冻在同一个版本下。
---

<!-- REWRITE_START -->
# 做任何优化之前，先有基线 RAG 和黄金集

> 原文：[A Baseline RAG and a Golden Set Before Any Optimisation](https://medium.com/learnwithnk/a-baseline-rag-and-a-golden-set-before-any-optimisation-c0c45de5847b)

---

## TL;DR

- **逐题对比两次运行。**一个修好六个回答、同时弄坏三个的改动，在总数上显示为「+3」，而那三个被弄坏的就此无人在目地上线。
- **基线 = 能把问题送到答案的最少阶段，且每个设置都写下来。**检索用精确搜索，意味着某段没召回就是嵌入模型的锅，永远赖不到索引头上。
- **黄金条目的来源匹配靠引用原文措辞，不靠 chunk id。**语料重新切块的那一瞬，所有 chunk id 全部作废。
- **先写问题，再去看段落。**看着段落写问题会复用它的词，让检索看起来比真实用户遇到的更好。
- **不可答问题必须贴着主题、并且语料里躺着一个貌似合理的错误答案。**没有这类问题，缺内容看起来和系统正常一模一样。
- **正确、错误、弃答分开计分，并用零检索跑一遍全集。**一个准确率数字既分不清拒答和答错，也分不清检索和模型的记忆。

一条 RAG 管线总是一段一段地调：chunk 大小、嵌入模型、召回多少段、prompt 里怎么排序。每一次调整都重跑整个系统，所以一次改动可以修好一些回答、弄坏另一些。凭记忆攒下的一小把问题，只能覆盖这些问题碰巧覆盖的地方。要正确评价一次改动，需要一条固定的管线和一组固定的问题，逐题打分。本文构建这个参照点，分三部分：一条刻意朴素的管线、一个把问题和答案及来源配对的黄金集、以及让两次运行可比的最小记分卡。三者冻结在同一个版本下。**它们不追求好，只追求不动。**全文的贯穿示例是一个内部支持知识库：支持团队写的帮助文章，加上它们链接的产品手册。

## 为什么改动需要一个固定的参照点

### 一次改动同时移动所有问题

新的 chunk 大小、不同的嵌入模型、重排召回结果的 reranker——没有一样只作用于单个问题，它们作用于全部。所以「修好六个、弄坏三个」是普通结局而非罕见意外：总数只报了三个变好的，没人去看那三个变坏的。

### 没人复问的回归是隐形的

凭记忆想起的问题，恰恰是那些已经失败过的问题——它们被反复问，只因为有人记得它们。这让问题集偏向「已知坏掉的」，而**当前正常工作的那些问题，才是改动可能悄悄弄坏的**。它们唯一的保护是被写下来并被重跑。

## 第一部分：一条朴素的管线

基线是把一个问题送到一个答案所需的最少阶段，每个阶段都取一个普通值。所有设置写下来，后面的改动才有具体的东西可比。

### 五个阶段

1. **Parse（解析）**：每篇文章和手册转纯文本。版式和表格结构会丢失，而且这个损失被故意保留。
2. **Chunk（切块）**：固定 400 token 窗口、零重叠，用嵌入模型自带的 tokenizer 计数。
3. **Embed（嵌入）**：一个模型，每 chunk 一个向量，存进 Postgres + pgvector。
4. **Retrieve（检索）**：按余弦距离取最近 5 段，全表逐一比较，无索引无过滤。没有近似，所以某段没回来，就是嵌入把它排得太低，赖不到索引。
5. **Generate（生成）**：五段材料，各标注文档与章节，指令是只根据它们回答，否则就说找不到。

这么朴素的基线很容易被打败——**这正是它的意义**。之后所有数字都以它为基准；任何被并进基线的「改进」，都是后续运行永远无法再展示的改进。

## 第二部分：黄金集

一条黄金条目 = 一个问题 + 系统应给的答案 + 答案在语料中的位置。第三样东西让它成为检索测试。

### 一条条目里有什么

先看语料，因为条目只有对着语料才有意义。知识库有几百篇文章，其中三篇用了同样五个词：

```text
整个知识库中的三篇文章
returns-policy    被退回的设备将隔离保存 10 个工作日，
                  之后重新入库或报废。
shipping-times    偏远地址配送需 10 个工作日。
warranty-terms    保修申请在收到后 10 个工作日内完成评估。
```

只有第一篇能回答「退回的设备隔离多久？」——另外两篇只是围绕别的事重复同一个数字。

一条条目记录问题和正确运行应产出的一切：

```json
{
  "id": "q017",
  "question": "How long does a returned device stay in quarantine?",
  "answer": "10 working days",
  "answerable": true,
  "evidence": [
    {"doc_id": "returns-policy",
     "version": "2026-04-11",
     "span": "held in quarantine for 10 working days"}
  ],
  "tags": ["numeric", "policy"]
}
```

- **answer** 是系统该告诉用户的答案。
- **answerable** 表示语料到底能不能回答这个问题。它把集合切成「需要答案」和「需要拒答」两半。
- **tags** 按问题形状分组。一次改动可能帮了数字题、伤了步骤题，总数上抵消为零——tags 让两种效应都读得出来。
- **evidence** 对答案依赖的每个文档记一条。

evidence 的每条内部又有三个字段：**doc_id 和 version** 指明文档与答案成立的修订版，文档一变条目就要复查；**span** 是从文档里逐字抄下来的措辞，不是摘要——运行时拿它去召回段落里找。

### 当答案需要两个文档

有些答案是拼装出来的，不是找到的，任何单一文档都不持有它。「保修申请收到后多久，退回设备就可以报废？」需要保修条款里的评估窗口和退货政策里的隔离期：各 10 个工作日，答案是 20——**而没有任何一个文档写了 20**。

```json
{
  "id": "q052",
  "question": "How soon after a warranty claim is received "
              "can a returned device be scrapped?",
  "answer": "20 working days",
  "answerable": true,
  "evidence": [
    {"doc_id": "warranty-terms",
     "version": "2026-02-03",
     "span": "assessed within 10 working days of receipt"},
    {"doc_id": "returns-policy",
     "version": "2026-04-11",
     "span": "held in quarantine for 10 working days"}
  ],
  "tags": ["numeric", "policy", "multi-document"]
}
```

条目只在**每个 span 都回来**时才算满足，两个回来一个是失分。这比看上去严格，而严格就是重点：如果只到了保修那一段，模型读到 10 个工作日就答 10 个工作日——答案错了一倍，而且**错在貌似合理的方向上**，响应里没有任何迹象表明少了一份文档。

### 从错误文档里来的正确答案

假设检索只回了 shipping-times 那段，从没回退货政策。模型读到那里的「10 working days」就答「10 working days」——答案检查通过，检索检查失败（没有任何段落包含「held in quarantine for 10 working days」）。系统是碰巧对的：它从一篇讲配送的文章里找到了一个碰巧匹配的数字，下一题就没这个运气了。记分卡上一个数字会把它记成成功；两道检查把它记录为「答案对、检索错」——这才是一次改动需要改进的那一对。这也是 span 要比答案长的原因：只匹配「10 working days」的话，配送那段也会命中，来源就会被记成「已检索到」。

### 为什么记措辞，不记 id

条目必须记录答案住在哪里，运行才能检查检索有没有把它带回来。有三种记法，两个显然的都以相反的方式坏掉：

- **文档 id 太松。**退货政策还讲补货费和购买凭证，检索可以只带回那些 chunk 而不带隔离那句话。检查 doc_id 会记成命中，尽管模型从没见过它需要的那一行。
- **chunk id 太脆。**400 token 时隔离那句话住在一个 chunk 里；改成 256，同一句话落进新 chunk、拿到新 ID。旧 id 现在指向别的文字，或什么都不指。而这一坏就是全集一起坏——弄坏它的恰恰是 chunk 大小调整，**正是黄金集要度量的那种改动**。

span 在两者之间：像 chunk id 一样精确到段落，又因为它是文本本身而非「文本住址的名字」，重切不坏。

### 构建这个集

50 到 100 条，混合各种问题形状，混入一些语料根本答不了的，整体冻结在一个版本下——一个人几天的工作量。手写，最好的素材是用户已经问过的问题：支持工单、搜索日志、人们排队去问的那个队列。

模型只能在边缘帮忙，不能碰中心。它可以把一个月的工单归类成重复出现的问题，或者把一条条目改写三种说法让集合不那么单一口吻。但它不能决定正确答案：**一个答案由模型写的集合，记录的是那个模型对语料的看法**；之后每次运行都是系统在跟自己的一个副本比对，它们共享的错误会被计为通过。

先写问题，再去找证据。写作者会让段落与问题产生人为的大幅词汇重叠（论文 arXiv:1906.00300 实证），让模型从 chunk 生成问题也一样：那些问题复用了段落原词，检索轻松命中；第一个真实用户换个说法，同一系统就脱靶了。

书写时混着来：手册里的一个数字、文章里的一道流程、点名产品版本的问题、几道需要两个文档的。每写一条 span 都现场核对：如果一个 span 在索引里任何 chunk 中都匹配不上（不只是没进 top 5），那是解析器或切块器在入库时就丢了这段文字——**在用户问出口之前就找到了缺失的内容**。

### 语料答不了的问题

大约五分之一的条目应该在语料中无解。没有它们，缺失内容看起来和系统正常一模一样——因为每个问题都有答案、总有东西回来。好的不可答问题要贴着主题，而且附近躺着一个类型正确的貌似错误答案。自动生成的不可答问题（论文 arXiv:1806.03822 指出）一眼就能被识别，正是因为它们做不到这两点。

**弱的：语料里什么都不挨着。**问设备配对，而知识库从不覆盖设备设置——毫不相似，系统毫无诱惑地拒答，这条目什么也没证明：

```json
{
  "id": "q038",
  "question": "How do I pair the device with my phone?",
  "answer": null,
  "answerable": false,
  "evidence": [],
  "tags": ["procedure"]
}
```

**强的：语料里躺着一个貌似合理的错误答案。**问「退回的配件隔离多久」，而退货政策只写设备——「10 working days」就在那儿，类型正确，只差一个名词。拒答的系统是顶住了诱惑：

```json
{
  "id": "q041",
  "question": "How long does a returned accessory stay in quarantine?",
  "answer": null,
  "answerable": false,
  "evidence": [],
  "tags": ["numeric", "policy"]
}
```

q038 拒答零成本，这就是五分之一该长得像 q041 的原因。q041 刻意挨着 q017：同一语料、同一形状、只差一个名词。对两个问题都答「10 个工作日」的系统，一题得分一题失分——只有这一对能把它照出来。标记任何条目不可答之前，把冻结语料清单里的每个文档搜一遍，并记录检查的是哪份清单。

## 第三部分：记分卡

记分卡是一次运行留下的东西：每题一行，加上产出这些结果的配置。它存在的意义是让「那次改动到底有没有用」有一个不需要靠信任的答案。卡上每个数字都能打开还原成背后的问题。

### 一次运行记录什么

一次运行把黄金集的每题送进冻结管线，再把返回与条目声称应有的返回比对。**只有 question 跨过管线边界**；答案、span、文档 id、版本是评分标准，留在打分一侧。这条边界很容易被无意破坏：把预期答案放进 prompt、或用 doc_id 过滤检索让正确文档必然归来——两者都会产出一张「生产环境里根本不存在的系统」的记分卡。

记录什么取决于条目是否可答，这是评分循环的第一个分支。不可答条目没有东西可检索，只记录一件事：**它拒答了吗？**可答条目记两件事，分开记：

- **检索找到了答案吗？**evidence 里每个文档都要回来，每个 span 都要在返回的段落里出现。
- **答案对吗？**由人对照 answer 记 correct / incorrect / abstained。correct 的定义：预期答案出现，且响应中没有与之矛盾的内容——额外的准确细节不扣分，多出来的第二个不同隔离期不行。

两道检查互不设门，成对出现才携带诊断：

- **检索到了、答案错了**：文字摆在面前还是错了——修 prompt 或模型，不是检索。
- **检索没到、答案错了**：修检索。
- **检索没到、答案却对**：碰巧对，下一题不会——就是 shipping 那段的案例。

答案判定是运行中唯一由人决定的部分，所以它的规则和其他一切一样写下来：规则在多次运行间漂移的话，度量的就是评分者而不是系统。「10 working days」必须始终匹配「ten working days」、始终不匹配「10 days」。

### 花一次运行之前，先检查集合

有两样东西错的是集合而不是系统：文档在条目写下之后变了；或者 span 在语料里不唯一。两者都是「集合对语料」的属性，不需要模型、检索器或一个 token。打分前先扫一遍语料：

```python
def validate(golden_set, corpus):
  faults = []
  for item in golden_set:
    for entry in item["evidence"]:
      doc = corpus.get(entry["doc_id"])
      if doc is None:
        faults.append((item["id"], "document is not in the corpus"))
        continue
      if doc["version"] != entry["version"]:
        faults.append((item["id"], "source document has changed"))
      if entry["span"] not in doc["text"]:
        faults.append((item["id"], "span is not in the document"))
      others = [d for d in corpus.values()
                if d["doc_id"] != entry["doc_id"]
                and entry["span"] in d["text"]]
      if others:
        faults.append((item["id"], "span is not unique to its source"))
  return faults
```

每条 evidence 按 doc_id 各自查：双文档条目有两条，第二个 span 合法地住在另一个文档里。一处缺陷在这里花一次语料扫描就能发现；同样的缺陷在评分时发现，代价是一百次模型调用，而且只在检索碰巧返回的那些条目上浮出。**运行前修完所有缺陷。**从漂移的集合产出的记分卡与任何东西都不可比——包括它自己。

## 评分循环

```python
for item in golden_set:
  result = pipeline.answer(item["question"])  # 只有 question 跨过边界
  # 不可答条目没有 evidence，所以没有东西可找
  doc_found = evidence_found = None
  spans_found = spans_required = None
  if item["answerable"]:
    outcome = grade(result["answer"], item["answer"])  # correct/incorrect/abstained
    returned = {p["doc_id"] for p in result["passages"]}
    spans_required = len(item["evidence"])
    spans_found = sum(
      any(entry["span"] in p["content"] for p in result["passages"])
      for entry in item["evidence"]
    )
    doc_found = all(entry["doc_id"] in returned
                    for entry in item["evidence"])
    evidence_found = spans_found == spans_required  # 全部 span，不是一部分
  else:
    # 没有可检索、可匹配的东西，唯一的问题是它拒了没有
    outcome = "refused" if declined(result["answer"]) else "answered anyway"
  write_line(
    item_id=item["id"],
    answerable=item["answerable"],
    outcome=outcome,
    doc_found=doc_found,
    spans_found=spans_found,
    spans_required=spans_required,
    evidence_found=evidence_found,
    returned_docs=[p["doc_id"] for p in result["passages"]],
    tokens_in=result["tokens_in"],
    latency_ms=result["latency_ms"],
  )
```

`answerable` 上的分支不是细节：不可答条目没有 span 可找，评分问题整个变了。两个分支**故意不共享词汇**——correct 和 refused 都是成功，abstained 在可答题上是失败、在不可答题上是目标。分开的词阻止后来的总数把它们加在一起。一条 `answered anyway` 记录最值得打开：它的 returned_docs 指出是哪个文档诱惑模型编造了答案——多条记录指向同一文档时，矛头直指语料里那个擦边陷阱。

循环不做任何集合校验——那在运行前已完成，循环只负责测量。它还记录多文档题走得多近：spans_required 是答案依赖几个文档，spans_found 是到了几个，evidence_found 只在两者相等时为真。spans_found 把「走到一半」和「颗粒无收」区分开——两者需要不同的修法：一半通常是排序或 token 预算问题，零通常意味着查询压根没匹配上第二个文档。两个检索结果都保留，因为只看一个没法读：doc_found 为真而 evidence_found 为假，说明对的文档回来了、装答案的 chunk 没回来——这是切块问题；两者都假，是排序问题。返回的文档 id 也进记录：检索全灭时，它们说明回来的是什么——同一个错误文档跨多条记录反复出现，就指到了病因。

### 记分卡给出什么

每次运行一个结果文件，每题一行，配置钉在顶部。不记录配置的运行与任何东西不可比。记分卡就是这些行数出来的：上面没有任何东西是另外测的，所以任何数字都能打开还原成问题。

```text
示例数值，非实测运行
corpus sha256:9f2c1e... (412 documents)
golden set v1 (100 questions: 80 answerable, 20 unanswerable)
embedding <model name>@<revision>
chunking 400 tokens, no overlap
retrieval exact cosine, top 5, no filter
generation <exact model id, never an alias>, prompt sha256:4ab1d0...

answerable   correct 52   incorrect 18   abstained 10
unanswerable refused 14   answered anyway 6
document retrieved   68 of 80 answerable
evidence retrieved   61 of 80 answerable (every span)
partial evidence      5 of 80 answerable (some spans, not all)
closed book           7 of 80 answerable correct with no retrieval
tokens in median      about 2,300
```

- **三个答案数分开站着。**一个准确率数字会藏起 10 道弃答的可答题和 6 道抢答的不可答题——它们需要相反的修法。
- **检索行是是非题，不是排名。**68 份文档到了、61 份带着答案句——7 道题拿到了正确的文章和错误的部位。
- **partial 行是多文档题走到一半的**：5 道题只拿到两份里的一份，计为 miss，修法与颗粒无收不同。
- **closed-book 行是同一批问题关掉检索再跑一遍**（每个黄金集版本跑一次）。7 道题靠模型记忆答对，量的是记忆不是管线——跑完就把它们从集合里去掉。
- **token 与延迟只记录不计分。**后面放宽上下文的改动需要这笔交易的代价侧。

然后两次运行逐行比，永远不按总数比：

```text
示例数值，非实测运行
                            baseline   chunk size 256
answerable correct          52         55
answerable incorrect        18         16
answerable abstained        10          9
unanswerable refused        14         12
unanswerable answered        6          8
document retrieved   68 of 80     69 of 80
evidence retrieved   61 of 80     66 of 80
partial evidence      5 of 80      2 of 80

answerable, per 6 wrong to right
question 3 right to wrong
```

flips 来自把两个结果文件按 item_id 连接、比较 outcome——这次连接是每题一行存在的唯一理由，也是每行都带 id 的原因。可答 correct 动了 3，实际有 9 道可答题动了、其中 3 道坏了——这是总数永远显示不出来的那行。两行检索说明改动干了什么：文档检索几乎没动，说明正确的文章本来就在到；更小的 chunk 把答案句放进了一段与问题匹配的段落里。不可答行反向移动：2 道拒答的现在被抢答了，因为更小的 chunk 往模型面前塞了更多擦边内容。改动仍然值得要——**但要带着这笔代价一起要**。

先什么都不改把基线跑两遍，数 flips。温度 0 也不确定性：批处理和硬件会在运行间挪动算术。**一次改动翻动的问题数，若少于一次不改动重跑的翻动数，它什么也没证明。**

## 拼起来

第一版小到几天能建、能手读：

- **语料与管线**：一份冻结的文章与手册清单（记录哈希）、400-token chunk 与精确余弦检索、5 段带标注材料、一条允许「我找不到」的 prompt。
- **黄金集**：50 到 100 条手写条目，evidence 列出答案依赖的每个文档与其中 span，附 tags；约五分之一不可答但贴题，每条缺席都对着冻结清单核实过。
- **记分卡**：correct / incorrect / abstained 分立、不可答子集、每个必需 span 是否到齐、一次 closed-book 运行、token 与延迟入日志。
- **运行**：评分循环只送问题；每次运行一个结果文件钉住配置；两次不改动运行找噪声底；flips 双向报告。

**基线只在它不动的时候有用。对着它量的一切，才是动的。**

Happy Learning.
<!-- REWRITE_END -->

<!-- SPROUT_START -->
# 《A Baseline RAG and a Golden Set Before Any Optimisation》的发芽报告

## 材料核心

RAG 优化之前必须先建参照点，文章把它拆成冻结在同一个版本下的三件套：一条五阶段朴素管线（400 token 切块、精确余弦检索、允许拒答的 prompt），一个 50-100 条手写的黄金集（每条记录问题、答案、可答性、证据 span 与标签，五分之一不可答但贴题），一张逐题打分、分开统计正确/错误/弃答的记分卡。核心主张：总数会说谎，只有逐题对比的 flips 能暴露「修 6 坏 3」这类改动。

## 发芽 01：总数会说谎，flips 不会

### 种子

任何一次改动都同时作用于全部问题——修好六个、弄坏三个，在总数上显示为「+3」。

### 故事

文章的双运行对比示例里，correct 从 52 到 55 只动了 3，但按 item_id 连接两个结果文件后发现实际有 9 道题翻了向、其中 3 道是从对翻错；同一组数字还显示不可答题的拒答从 14 降到 12、抢答从 6 升到 8——更小的 chunk 让模型面前多了更多擦边内容。

### Aha 瞬间

「平均变好」和「净变好」是两回事：不连结果文件逐题看，你永远不知道一次改进是用什么换来的。改动仍然值得要，但要带着代价一起要——能写出「+5 correct / +2 answered anyway」这样的句子，才算真的读懂了一次优化。

## 发芽 02：证据记措辞不记地址

### 种子

黄金条目的 evidence 用逐字抄写的 span 定位答案，而不是文档 id 或 chunk id——前者太松、后者太脆。

### 故事

文章逐层论证：doc_id 太松（退货政策还有别的内容，检索回来别处也算命中）；chunk id 太脆（400 token 改 256，句子换 chunk 拿新 id，而 chunk 大小恰恰是黄金集要度量的改动——集合会整批作废）。span 是文本本身，重切不坏；而且 span 要比答案长，否则「10 working days」会在配送文章里也命中，把碰巧对的答案记成检索成功。

### Aha 瞬间

给易变系统写测试锚点时的通用原则：**锚定内容，不要锚定内容的地址**。凡是有 re-index、re-chunk、re-组织这类操作的系统（搜索、知识库、代码库），断言都该指向不变的事实本身，而不是随时会换名字的容器。

## 发芽 03：不可答问题才是集合的试金石

### 种子

黄金集里约五分之一该是语料答不了的问题——且必须贴题、附近躺着一个类型正确的貌似错误答案。

### 故事

文章用 q038 与 q041 做对照：问「设备怎么配对」（语料毫不沾边），系统拒答零成本，什么也测不出；问「退回的配件隔离多久」（政策只写设备，「10 working days」就在一个名词之外），拒答才算顶住了诱惑。q041 刻意挨着可答的 q017——同语料、同形状、只差一个名词，对两题都答 10 天的系统一题对一题错，只有这对组合能把它照出来。

### Aha 瞬间

缺失内容和正常运转在指标上长得一模一样，除非你专门为「诱惑」设计考题。评估集的价值不在覆盖了多少能答对的场景，而在埋了多少答错也显得合理的陷阱——对评估 RAG 如此，对评估任何生成式系统都如此。
<!-- SPROUT_END -->
