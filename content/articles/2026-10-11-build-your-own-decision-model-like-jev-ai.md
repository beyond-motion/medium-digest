---
title: 'Build Your Own Decision Model like Jev AI'
slug: 2026-10-11-build-your-own-decision-model-like-jev-ai
author: Mehul Gupta
date: '2026-10-11T09:00:00+08:00'
source_url: 'https://medium.com/data-science-in-your-pocket/build-your-own-decision-model-like-jev-ai-3126b1e0e1b1'
status: processed
image: covers/2026-10-11-build-your-own-decision-model-like-jev-ai.svg
excerpt: >-
  别让 LLM 写段落，让它做选择：把 Qwen3-1.7B 的输出限制在 A-E 五个 token 上，对这五个 logit 做 softmax 直接得到答案概率分布——「天空什么颜色」一题 B 选项 99.88%；CommonsenseQA 留出集上 59.38% 准确率、微调后 62.41%。但最大的坑是 98.55% 的自信只换来 70.09% 的正确率，用温度缩放（T=3.7973）校准后才对齐。附完整代码与 Build Your Own Jev 仓库。
---

<!-- REWRITE_START -->
# 亲手打造你自己的「Jev AI」式决策模型

> 原文：[Build Your Own Decision Model like Jev AI](https://medium.com/data-science-in-your-pocket/build-your-own-decision-model-like-jev-ai-3126b1e0e1b1)
> 作者：Mehul Gupta
> 改写式翻译，保留原文结构与全部数据；署名与原文链接如上。

---

「天空是什么颜色？」——普通语言模型会生成一段像模像样的回答：「天空在白天通常呈现蓝色，因为大气分子对阳光的散射……」这答案没毛病。但假如你在构建分类系统、答题应用，或者一个必须从固定列表里选一个动作的智能体，你要的不是一段话，而是一个**决定**。

你可以让模型返回 JSON：`{"answer": "B", "confidence": 0.95}`。结构化输出能约束格式合法，但模型仍然是在逐 token 生成——**能生成合法 JSON，不代表它的 confidence 有意义。**

对于只有五个候选答案的任务，有个更简单的做法：把模型的输出限制在这五个选项里，直接比较它们的概率。

## 决策模型的原理

同一个问题，给出五个选项：A: Red / B: Blue / C: Green / D: Grey / E: Pink。

传统语言模型在 prompt 之后可以生成无数种 token——可能以答案开头、以解释开头、甚至格式错乱。决策模型不同：我们把可能的输出**限制为代表 A、B、C、D、E 的那几个 token**。

模型本来就会为下一个 token 算出分数（logits）。我们只保留允许选项对应的分数，用 softmax 转成概率。结果可能长这样：

- A: 5.6% Red
- B: 83.3% Blue
- C: 5.6% Green
- D: 3.3% Grey
- E: 2.2% Pink

模型选 B，因为它在允许选项里概率最高。

注意一个重要细节：**限制输出并没有让模型变聪明——我们只是改变了使用它的方式。** 我们不再请它生成完整回答，而是用它的 next-token 分布来做决策。这还能减少解码步数：如果答案能用一个 token 表示，处理完 prompt 之后可能只需一次生成步。（prompt 仍需处理，实际延迟取决于模型、硬件与实现。）

## 用 Qwen3 亲手造一个

实验用 Hugging Face 上的 **Qwen/Qwen3-1.7B**——一个相对小巧的模型。五个选项，让模型预测哪个正确。先装库：`pip install torch transformers`。

核心脚本（保留原文完整逻辑）：

```python
import argparse, json, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "Qwen/Qwen3-1.7B"
options = ["A", "B", "C", "D", "E"]

parser = argparse.ArgumentParser()
parser.add_argument("--input", default="question.json")
args = parser.parse_args()

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name, torch_dtype="auto", device_map="auto")

# 拿到允许答案的 token ID
option_token_ids = [
    tokenizer.encode(option, add_special_tokens=False)[0]
    for option in options
]

def format_prompt(item):
    prompt = item["question"] + "\n"
    for option in options:
        prompt += f"{option}. {item[option]}\n"
    prompt += "Answer:"
    messages = [{"role": "user", "content": prompt}]
    return tokenizer.apply_chat_template(
        messages, tokenize=False,
        add_generation_prompt=True, enable_thinking=False)

item = json.load(open(args.input))
model_inputs = tokenizer(format_prompt(item), return_tensors="pt").to(model.device)

with torch.no_grad():
    logits = model(**model_inputs).logits[0, -1]   # 最后一个位置的 logits

option_logits = logits[option_token_ids].float()   # 只留允许选项的分数
probs = torch.softmax(option_logits, dim=-1)       # softmax 成概率
prediction = options[probs.argmax().item()]        # 取最可能的答案

print(f"Prediction: {prediction}")
for option, prob in zip(options, probs.tolist()):
    print(f"{option}: {prob:.4f} {item[option]}")
```

这里有三件事在发生：其一，加载模型、对问题做 token 化，模型处理 prompt 并产出下一 token 的 logits（原始分数，表示模型对各候选 token 的倾向）；其二，只抽出五个答案选项对应的 logits，其余词表全部忽略；其三，对这五个分数做 softmax，得到加和为 100% 的选项概率分布。

一个值得检查的实现细节是**分词**：代码假设每个答案标签恰好映射到预期的单个 token ID。生产应用里要验证这个假设，确保答案 token 无歧义。

## 跑个简单例子

`question.json`：

```json
{
  "question": "What color is the sky?",
  "A": "Red", "B": "Blue", "C": "Green",
  "D": "Purple", "E": "I don't know"
}
```

运行 `python decision_model.py --input question.json`，示例输出：

```
Prediction: B
A: 0.0000 Red
B: 0.9988 Blue
C: 0.0000 Green
D: 0.0000 Purple
E: 0.0012 I don't know
```

模型选 B（Blue）。具体概率会随模型版本、分词器、prompt 模板和推理设置而变。例子简单，但同一模式可用于情感分类、客户请求路由、文档归类、或在预定义动作里做选择——**核心要求是输出空间必须明确定义。**

## 小决策模型准头如何？

简单问题只能验证代码能跑，不能说明模型在更难的问题上表现如何。作者在 CommonsenseQA（常识推理多选题数据集）的随机留出样本上评测。**Qwen3-1.7B 未经微调**的结果：

- 准确率：725 / 1221 = **59.38%**
- Macro F1：**0.5844**（对每个答案类别分别算 F1 再取平均，各类等权）

对一个特定评测上的小模型来说，59% 上下是合理的起点——它不代表模型能解任意推理题，结果也依赖数据集样本与评测设置。

## 微调之后呢？

下一步在数据集上微调模型，结果提升：

- 准确率：762 / 1221 = **62.41%**
- Macro F1：**0.6234**

准确率提升约三个百分点。结论直白：**把模型限制在固定选项上让决策过程更直接，但不能替代训练**——微调仍能改善模型理解任务、区分选项的能力。可靠评测必须在训练或模型选择未用过的数据上进行。

## 最大的坑：置信度不是准确率

到这里我们拿到了预测和概率分布。把最高概率当成「模型对自己正确的信心」很有诱惑力——有趣的部分来了。

考虑这个问题：「你最可能在哪里找到 bat？」选项：A: Cave / B: Baseball game / C: Attic / D: Zoo / E: Sporting goods store。模型给出：

```
Prediction: A
A: 0.9978 Cave
B: 0.0004 Baseball game
C: 0.0017 Attic
D: 0.0000 Zoo
E: 0.0001 Sporting goods store
```

几乎 100% 压在 Cave 上。但这个问题有歧义：bat 可以是动物也可以是球棒；就算是动物，洞穴也不是唯一去处。**模型强烈偏向一个答案，不等于它有 99.78% 的概率正确。** 凡是用模型概率做决策的场合，这个区别都至关重要——模型可以整体表现不错，同时对单个答案过度自信。

## 校准是什么

校准关心的是**预测置信度与实际准确率之间的关系**。想象模型做了 100 次预测、每次置信度都是 80%：若模型校准良好，长期看这 100 次里应有约 80 次正确。不是每组 100 次都恰好 80 次，而是预测概率在大量预测上应与实际结果基本吻合。

实验把预测按置信度分桶，比较每桶的平均置信度与实际准确率。校准前：

| 置信区间 | 数量 | 平均置信度 | 实际准确率 |
|---|---|---|---|
| 30-40% | 26 | 37.61% | 26.92% |
| 40-50% | 41 | 45.38% | 26.83% |
| 50-60% | 70 | 54.90% | 32.86% |
| 60-70% | 74 | 64.76% | 36.49% |
| 70-80% | 77 | 74.95% | 42.86% |
| 80-90% | 121 | 85.55% | 47.11% |
| 90-100% | 809 | **98.55%** | **70.09%** |

看最后一组：平均置信度 98.55%，实际准确率只有 70.09%——差距巨大。模型经常对自己的预测比实际表现自信得多。**这就是为什么原始 next-token 概率不应被自动当成可信的置信分。**

## 用温度缩放校准概率

一种改进办法是**温度缩放（temperature scaling）**：在转成概率之前修改 logits，用温度参数 T。T > 1 时分布变平——首选答案仍可能最高，但它与其他选项的差距变小。例如原始分布 A: 2.1% / B: 94.3% / C: 1.7% / D: 1.0% / E: 0.8%，施加 T=2.2 后可能变成 A: 11.2% / **B: 63.2%** / C: 10.3% / D: 8.2% / E: 7.1%。模型仍然选 B，但不再把它当成近乎必然。

温度缩放**不改善模型的推理、不改变选项排序**，它只改变概率分布，让置信分更好地反映实际正确率。

## 找到合适的温度

温度参数应在**单独的验证集**上调，用合适的校准指标找到让预测置信度贴近实际准确率的值。本实验拟合出的温度约为 **T = 3.7973**。校准后各置信桶：

| 置信区间 | 数量 | 平均置信度 | 实际准确率 |
|---|---|---|---|
| 20-30% | 82 | 27.12% | 23.17% |
| 30-40% | 217 | 35.07% | 39.17% |
| 40-50% | 199 | 44.72% | 51.26% |
| 50-60% | 166 | 54.75% | 54.82% |
| 60-70% | 139 | 65.62% | 58.27% |
| 70-80% | 140 | 74.92% | 77.14% |
| 80-90% | 169 | 85.07% | 79.88% |
| 90-100% | 109 | 93.33% | 95.41% |

校准后的概率与实际准确率明显贴近。仍有波动——这正常：校准估计依赖评测数据的量与代表性，预测数少的桶噪声大。一个重要细节：**温度要在验证集上拟合，不能在最终测试集上拟合**，否则报告出来的校准性能会过于乐观。

## 什么时候该用决策模型

当应用有一组**已知的可能输出**时，决策模型特别有用：客服系统在计费/技术支持/账户访问等预定义类别里挑；文档系统给来件分类；AI 智能体从固定动作集里选一个工具。这些场景下，决策模型直接给出答案加一个选项上的概率分布，还省去生成再解析长回答的开销。

但它有局限：模型只能在你给的选项里选——如果正确答案不在其中，它仍可能挑一个「看起来最接近」的，除非显式支持弃权（比如加一个「I don't know」选项）。而且 **0.95 的分数不自动等于 95% 的正确概率**。高风险应用要在有代表性的数据上评测、衡量不同错误的代价、并决定系统何时应当拒判。

## 自己动手

玩这个想法不需要巨型模型——Qwen3-1.7B 足以演示全部要点。从一个小型多选数据集开始，测准确率、看概率分布，再试微调和校准。完整实现（含数据集构建、评测、微调、校准脚本）在作者的 **Build Your Own Jev** GitHub 仓库。作者也想看更大模型上的表现：更大的模型可能提升准确率，但它的概率仍然需要被评估，而不是被假设可靠。

更大的图景是：**我们并不总需要 LLM 生成文本。有时我们只需要它做一个选择，并给出一个可以被评估、而不是被盲信的概率分布。**
<!-- REWRITE_END -->

<!-- SPROUT_START -->
# 《Build Your Own Decision Model like Jev AI》的发芽报告

## 材料核心

这篇教程把 LLM 从「文本生成器」翻转成「决策器」：不让模型写段落或生成 JSON，而是把输出空间收窄到 A-E 五个答案 token，直接对这五个 logit 做 softmax，一步拿到带概率分布的答案。Qwen3-1.7B 在 CommonsenseQA 留出集上 59.38%、微调后 62.41%；但置信度与准确率严重脱节（98.55% 自信只对应 70.09% 正确），用温度缩放（T=3.7973，在验证集上拟合）校准后才对齐（93.33% ↔ 95.41%）。全文代码、基准与校准表俱全，配套 Build Your Own Jev 仓库。

## 发芽 01：限制输出不是让模型变聪明，是换了用它的问题

### 种子

同一个模型，让它写「天空为什么是蓝的」得到一段散文；把输出锁死在 A-E 五个 token 上，得到「B: 99.88%」。

### 故事

文章反复强调：决策模型没有赋予模型任何新能力——模型原本就在为每个可能的 token 算分数，我们只是决定「只看这五个分数」。生成式用法里，模型的分布被采样过程展开成文本；决策用法里，我们直接在分布层面取答案。副作用是解码步数从「一段话」缩到「一个 token」。

### Aha 瞬间

同一个模型可以是完全不同的产品，取决于你向它要「叙述」还是要「分布」。很多「LLM 不适合做 X」的判断，其实只是「生成式接口不适合做 X」——换一个接口层，问题可能就消失了。

## 发芽 02：流利度是自信的假面

### 种子

bat 一题，模型以 99.78% 的概率选 Cave；90-100% 置信桶里平均自信 98.55%、实际正确率 70.09%。

### 故事

模型对歧义问题（bat 是动物还是球棒？）毫无犹豫，把压倒性的概率给了某个理解。校准表揭示了系统性模式：越自信的桶，虚高的幅度越大。这不是小模型的毛病——它说明 next-token 概率度量的是「这个答案在训练分布里多常见」，而不是「它正确的概率」。

### Aha 瞬间

不要把模型「说话的笃定程度」当成「正确的证据」——这条对 next-token 概率成立，对任何生成式输出的语气同样成立。凡是要用分数做决策的场合，先画一张分桶校准表，看看自信和正确到底差多远。

## 发芽 03：温度缩放不改答案，只改诚实度

### 种子

T=2.2 把 94.3% 的「近乎必然」压成 63.2% 的「比较可能」——排序不变，选的还是 B；拟合出的 T=3.7973 让 90-100% 桶变成 93.33% ↔ 95.41% 的对齐。

### 故事

校准与微调是两个正交的操作：微调改变模型「选哪个」（59.38% → 62.41%），温度缩放只改变「它对这个选择有多确定」的标度。而且这个标度必须在与测试隔离的验证集上拟合——在测试集上调温度，等于偷看答案后再宣布自己诚实。

### Aha 瞬间

一个系统的「输出内容」和「输出内容的置信度」可以分开修理。先问清楚要修的是哪一个：答错的问题靠训练，答得太满的问题靠校准——用校准的手段去修准确率，或用训练的手段去修置信度，都是用错了工具。
<!-- SPROUT_END -->
