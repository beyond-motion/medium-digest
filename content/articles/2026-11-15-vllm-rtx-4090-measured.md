---
title: 'How to serve your own LLM on a GPU with vLLM: what we measured on a rented RTX 4090'
slug: 2026-11-15-vllm-rtx-4090-measured
author: 'Roni Das'
date: '2026-11-15T09:00:00+08:00'
source_url: 'https://medium.com/@systemdesignacademy/how-to-serve-your-own-llm-on-a-gpu-with-vllm-what-we-measured-on-a-rented-rtx-4090-0343ac020d30'
status: processed
image: covers/2026-11-15-vllm-rtx-4090-measured.svg
excerpt: >-
  租一张 RTX 4090（$0.89/时）跑 vLLM 0.33 实测全记录：安装 1 分钟、启动 2 分 50 秒（权重只占 10 秒，其余是编译+CUDA 图）、KV cache 纸上可算（0.6B 每 token 112 KiB）、64 人并发总吞吐 34 倍而每人只慢 1.9 倍（读快写慢 56 倍的连续批处理红利）、容量规划要按 cache token 数不按用户数。
---

<!-- REWRITE_START -->

# 用 vLLM 在 GPU 上自托管 LLM：我们在一张租来的 RTX 4090 上实测了什么

> 原文：[How to serve your own LLM on a GPU with vLLM: what we measured on a rented RTX 4090](https://medium.com/@systemdesignacademy/how-to-serve-your-own-llm-on-a-gpu-with-vllm-what-we-measured-on-a-rented-rtx-4090-0343ac020d30) — Roni Das

---

一个调用托管模型的团队，为每个 token 付费。迟早有人会把月度账单转发给工程师，附一个问题：**我们能不能租一张自己的 GPU 跑开源模型，按小时付费？**

在回答之前，需要几个朴素的事实：把模型服务器跑起来要多久、GPU 的显存去了哪里、团队的代码要改多少、以及一张卡能同时服务多少人。

2026 年 11 月 13 日，我们在 RunPod 租了一张 24 GB 的 NVIDIA GeForce RTX 4090——安全云 $0.89/小时（社区云 $0.34/小时，有卡空闲时）。我们装了 vLLM 0.33.0，服务了两个开源模型：Qwen3-0.6B 和 Qwen3-8B，并录制了整个过程。**本文的每个数字都来自那次录屏，或来自你可以在纸上验算的算术。**数字若来自别的工具，我会说明。

## vLLM 是什么，一段话

vLLM 是一个开源程序，在一张 GPU 上把语言模型同时服务给很多人。它成为自托管 LLM 的首选有两个原因。第一，它在同样的网址、以同样的 JSON 格式应答——比如 `/v1/chat/completions`——所以为托管模型写的代码照常工作。第二，它围绕共享 GPU 构建：它把每个对话的工作笔记保存在显存里，并把很多人的请求拼进同一批通过模型的步骤。

## 第 1 步：安装 vLLM，预期约一分钟

vLLM 很大，所以给它单独的 Python 环境。我们用了 uv（一个快速的 Python 包管理器）：

```bash
uv venv --python 3.12 ~/vllm-env
source ~/vllm-env/bin/activate
time uv pip install vllm==0.33.0
```

全新 pod 上安装耗时 **1 分 0.7 秒**，几乎全是下载：uv 日志说「Prepared 164 packages in 55.18s」。共装了 199 个库，其中包括做 GPU 算术的 PyTorch 2.14.0 和读取模型文件的 Transformers。同一 pod 上的第二次安装只要 3.9 秒——uv 缓存了所有下载。**别按 3.9 秒做计划**：新 pod 从空缓存开始。

一个让我们整整废掉一次尝试的实用警告：环境用 `du -sh` 量出来有 9.0 GB。我们的 pod 只有 60 GB 盘，还装着早前的实验——vLLM 下载模型时磁盘满了，服务器死于 **No space left on device**。开跑前先 `df -h /`，删掉旧环境和模型文件。

## 第 2 步：启动模型，等将近三分钟

启动是一条命令。这行把 vLLM 放到后台，然后计时到它的健康检查地址应答为止：

```bash
vllm serve Qwen/Qwen3-0.6B > vllm.log 2>&1 & time (until curl -sf -o /dev/null http://127.0.0.1:8000/health; do sleep 1; done)
```

**2 分 50 秒**就绪。这让人意外，因为模型文件只有 1.5 GB。日志显示了时间去向：**加载权重本身只花了 10.1 秒。**然后是 1 分 59 秒，等在 cache 那行之前——这是 vLLM 准备 GPU 的时间：文档说默认启动会编译模型并捕获 CUDA graphs（对许多小 GPU 任务的录制，可以一口气重放，为之后的每个 token 省时间）。

如果你在试参数、频繁重启，`--enforce-eager` 可以跳过编译和 CUDA 图。文档把它描述为「以稳态解码性能为代价」的最快启动。**对要跑好几天、几周的服务器，默认值是更好的交换。**

## 先把门关上

这样启动的 vLLM 监听机器上的**每一个网络地址**，而且不要密钥。我们自己的日志写着「Starting vLLM server on http://0.0.0.0:8000」——0.0.0.0 意味着所有地址。它在我们的 pod 上安全，只因 RunPod 只发布你列出的端口，而 8000 不在其中。**如果你要暴露端口，用 `--api-key` 启动**——并且知道 vLLM 安全文档自己都说不要只依赖密钥。加 `--host 127.0.0.1` 让服务器只在本机可达。**一个开放的端口，就是在你的账单上邀请别人用你的 GPU。**

## 第 3 步：读一读 24 GB 去了哪

vLLM 会打印它如何瓜分这张卡。日志里三行讲完故事：

```bash
grep -E 'Model loading took|Available KV cache memory|GPU KV cache size' vllm.log
Model loading took 1.12 GiB memory and 10.109634 seconds
Available KV cache memory: 19.43 GiB
GPU KV cache size: 181,936 tokens, Maximum concurrency for 40,960 tokens per request: 4.44x
```

权重要了 1.12 GiB：Qwen3-0.6B 约 5.96 亿个参数，16 位存储每个 2 字节。但 nvidia-smi 显示卡几乎满了。原因是一个叫 `--gpu-memory-utilization` 的设置：vLLM 0.33 里默认 0.92——**vLLM 一启动就领取卡的 23.52 GiB 可用显存中的 92%（21.64 GiB）**，从里面拿走权重和约 1.09 GiB 工作区，剩下的每一字节——19.43 GiB——全部变成 KV cache 的空间。卡的末尾 1.88 GiB 留作余量不被动用。

空着的显存服务不了任何人，所以 vLLM 启动时一次性领走，然后随对话来去分配。需要与别的程序共享这张卡，就调低 `--gpu-memory-utilization`。要在你自己的版本上核一件事：2026-11-13 读到的最新 vLLM 文档描述了 CUDA 上更新的行为——按预热后实际空闲的显存定 cache 大小，设置默认 1.0。**读你自己的启动日志，别信博客里的数字，包括这一篇。**

## KV cache，在纸上算清楚

那个 cache 是什么，为什么几乎拿走全部显存？

模型写一个 token 时，attention 这一步要回看对话里每个更早的 token。为此，每一层为每个更早的 token 保留两小列数字：一个 key（描述这个 token 是关于什么的），一个 value（承载它贡献了什么）。它们一旦算出就不再变化，所以服务器把它们存起来，不为每个新 token 重算。这个存储就是 KV cache。

每个 token 的 cache 大小可以从模型 config.json 里的四个事实推出：

```
cache per token = 2（一个 key 一个 value）x 层数 x key-value 头数 x 头维度 x 2 字节
```

对 Qwen3-0.6B：2 × 28 × 8 × 128 × 2 = **114,688 字节，每 token 112 KiB**。用 19.43 GiB 除以 112 KiB，得到日志打印的 181,936 tokens，误差在日志舍入之内。Qwen3-8B 是 36 层，每 token 147,456 字节（144 KiB）。

两个模型每层都只有 8 个 key-value 头，尽管 Qwen3-8B 有 32 个注意力头。**多个头共享一对 key-value——这叫分组查询注意力（GQA）——它让 8B 的 cache 比每头独立时小四倍。**

我们在同类卡上又跑了 16 位完整形态的 Qwen3-8B，每个对话上限 32,768 token：

```bash
vllm serve Qwen/Qwen3-8B --max-model-len 32768 > vllm.log 2>&1 &
Model loading took 15.27 GiB memory and 40.029865 seconds
Available KV cache memory: 4.56 GiB
GPU KV cache size: 33,216 tokens, Maximum concurrency for 32,768 tokens per request: 1.01x
```

权重现在吃掉了预算的大头，cache 只剩 4.56 GiB。用算术核验：33,216 tokens × 147,456 字节 ≈ 4.9 GB，对上日志里的 4.56 GiB。vLLM 以 16 token 为一块存 cache，这里是 2,076 块。一个 2,000 token 的对话要 125 块——**所以同一张卡能同时容纳 16 个这样的对话，而小模型是约 90 个**。而「maximum concurrency 1.01x」意味着满长 32,768 token 的对话一次只能容下一个。

**规划自托管 LLM 时最有用的一课：用 cache 的 token 数写容量计划，不要用用户数。**一个装得下的大模型，余量可能只够很少的人。

## 第 4 步：用 OpenAI 库调用它，只改两行

这是我们客户端的核心。与 OpenAI 官方服务的代码相比，只有 base_url 和模型名不同：

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed-for-a-local-server")
stream = client.chat.completions.create(
    model="Qwen/Qwen3-0.6B",
    messages=[{"role": "user", "content": "In three sentences, explain to a new support agent "
               "why a parcel's tracking page might not change for a day."}],
    max_tokens=200,
    temperature=0,
    stream=True,
    stream_options={"include_usage": True},
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)
```

`extra_body` 承载不在 OpenAI 参数表上的设置——这里它关掉 Qwen3 的「思考外露」，库会原样透传。这个问题是 35 token，答案 55 token。**第一个词 0.167 秒后到达，之后模型以每秒 464 token 的速度书写**——约 2.2 毫秒一个 token。token 计数来自 vLLM 自己的 usage 字段，与付费服务报账单的方式一样。这是启动后第一个请求、只跑了一次，所以等待里可能含一次性开销。

## 第 5 步：同一时刻发 64 个问题

真正的问题是一张卡能服务多少人。一个小脚本用 AsyncOpenAI 和 asyncio.gather 同时发很多问题，每个都要求恰好 200 token（vLLM 的 ignore_eos 强制写满长度，让各次可比较——这是测量用的设置，不是真实服务该用的）：

- **1 人**：0.56 秒全部返回，总吞吐 359 token/s，单人 359 token/s。
- **16 人同时**：0.71 秒全部返回，总 4,530 token/s，每人 283 token/s。
- **32 人同时**：约 0.77 秒全部返回，总 8,273 token/s，每人 259 token/s。
- **64 人同时**：1.06 秒全部返回，**总 12,087 token/s**，每人 189 token/s。

**六十四个人拿到了单人 34 倍的总书写量，而每个人只慢了 1.9 倍。**全部 12,800 个答案 token 返回的总时间，只有单个答案的约 1.9 倍。

为什么第一个脚本里单人 464 token/s、这里 359？两者计时的东西不同。第一个从首词起表、只数书写；第二个用 200 token 除以「发出问题到最后一个词」的全程——含读题与服务器往返。**都不算错。引用速度时，永远说清你说的是哪一种。**

vLLM 靠**连续批处理（continuous batching）**做到这一点：它把每个等待中的请求放进同一批通过模型的步骤，在步骤之间加入新请求、移除完成的，没人等一整组做完。它还数自己做的每件事：`/metrics` 端点（Prometheus 可读的纯文本格式）显示这几轮之后 generation_tokens_total = 22,655——单问的 55 token 加四轮 113 人的每人 200，一个 token 不差。

## 为什么共享几乎免费：读得快，写得慢

原因藏在每个请求的两段里。

**Prefill 读问题。**它的全部 token 在模型开始之前就存在，所以一遍通过权重就一起处理完。**Decode 写答案**，一次一个 token，因为每个新 token 依赖前一个——每一遍都要从显存读出全部权重，只为产出一个 token。

我们在同一张 4090 上用 llama.cpp 自带的测速工具 llama-bench 量了这个差距：小模型读 256 token 的 prompt 达 35,796 token/s，写只有 642.0 token/s——**读比写每 token 快约 56 倍**。Qwen3-8B（4.68 GiB 文件，每数字约 4.9 bit），读 12,095、写 164.0 token/s。

最后一个数字让你可以在纸上看见显存极限：**每写一个 token 要读约 4.68 GB 权重，164.0 token/s × 4.68 GB ≈ 767 GB/s。NVIDIA 给 RTX 4090 的显存速度是 1,008 GB/s。**也就是说书写时，这张卡以约 76% 的极限读自己的显存，算术单元大部分在等。批处理把闲置的算术用起来：**读一次权重，为 64 个人各产出一个 token，而不是一个。**

## 长对话变慢，也是 cache 的原因

cache 省了计算，但读它不免费：每写一个新 token，attention 除了权重还要读所有更早 token 的笔记。llama-bench 在同一张卡上：Qwen3-8B 空缓存时写 164.1 token/s，对话里已有 16,384 token 时写 114.9——那个深度下笔记有 2,304 MiB，**每个 token 要读的东西比权重本身还多一半**，实测减速与这个算术的预测相差约 6%。

## 你的第一台 vLLM 服务器的清单

1. 给机器留磁盘空间。光环境就 9.0 GB，满盘会让启动死于 No space left on device。
2. 预期约一分钟安装、几分钟首次启动。实验期用 `--enforce-eager`，长跑服务器用默认。
3. 端口 8000 保持私有，或用 `--api-key` 并放到有鉴权的东西后面。
4. 读三行启动日志：权重、可用 KV cache 显存、cache token 数。**它们才是你的容量**，不是 GPU 的大小。
5. 从 config.json 算每 token 的 cache，按 cache token 数做规划。
6. `--max-model-len` 设成用户真正需要的值，这样「maximum concurrency」这个数字才有意义。
7. 用多并发测量，并且永远说清速度是单人还是总量、计时器包含了什么。

## 接下来去哪

以上全部内容来自我正在写的课程，其中两节免费开放，带同样的终端录屏与代码（KV cache 实测一节在真实 config 文件上算这笔账并与 llama.cpp、vLLM 双向核对；prefill 与 decode 一节逐步计时两段）。如果想直接玩数字，免费的 GPU 显存计算器可以为任何模型与卡片算权重与 cache 之和。

完整课程 Hands-On Inference Engineering（System Design Academy）从这里继续：PagedAttention、调度器、量化、投机解码、SGLang、Kubernetes 上的规模化服务——每一项都在租来的 GPU 上跑过、量过。写给想自己服务模型的后端与 AI 工程团队。

（来源：我们 2026-11-13 的实测；vLLM 文档与 0.33.0 源码；NVIDIA Ada 白皮书；Hugging Face 模型卡；RunPod 定价页。）

<!-- REWRITE_END -->

<!-- SPROUT_START -->

# 《How to serve your own LLM on a GPU with vLLM》的发芽报告

## 材料核心

一次可复现的自托管 LLM 实测全记录（RunPod RTX 4090，$0.89/h，vLLM 0.33.0，Qwen3-0.6B 与 8B）。时间：安装 1 分钟（uv 199 库）、启动 2 分 50 秒——权重加载仅 10.1 秒（0.6B）/40 秒（8B 15.27 GiB），其余是编译+CUDA 图捕获（--enforce-eager 可跳但牺牲稳态）。显存：--gpu-memory-utilization 默认 0.92 一次性领走 21.64 GiB，0.6B 权重仅 1.12 GiB、KV cache 得 19.43 GiB；8B 权重 15.27 GiB、cache 仅剩 4.56 GiB。KV cache 可纸上推算：2×层数×KV 头数×头维度×2 字节（0.6B 112 KiB/token、8B 144 KiB/token；GQA 8 KV 头让 8B cache 缩 4 倍）→ 0.6B 181,936 tokens、8B 33,216 tokens（32k 满长并发 1.01x）。安全：默认 0.0.0.0 无鉴权。客户端：OpenAI 库改两行（base_url+模型名），extra_body 透传关 thinking。并发：64 人总吞吐 12,087 token/s=单人 34 倍、每人只慢 1.9 倍（continuous batching）；原理是读快写慢 56 倍（prefill 35,796 vs decode 642 token/s），8B 解码时显存读速 767 GB/s≈1008 GB/s 极限的 76%——带宽受限，batching 把闲置算力喂满。长对话：16k 上下文时笔记 2,304 MiB，写速 164→114.9（与预测差 6%）。八条 checklist。

## 发芽 01：容量规划的单位——「用户数」是错误量纲

### 种子

同样一张 24 GB 卡：0.6B 模型 19.43 GiB cache（181,936 tokens、约 90 个 2k 对话），8B 模型只剩 4.56 GiB（33,216 tokens、16 个 2k 对话、满长并发 1.01x）。「模型装得下」与「人坐得下」是两个问题。

### 故事

新手直觉把容量想成「模型大小 vs 显存大小」，但实测显示权重只是预算的一部分：模型翻 13 倍（0.6B→8B），cache 空间缩 4.3 倍，并发能力从 90 个对话掉到 16 个——而如果对话是满长 32k，并发是 1。作者给出的正确量纲是 cache token 数：先算每 token cache 字节（config.json 四个数可纸上推算），再用「平均对话长度 × 目标并发」反推需求。这也解释了为什么「maximum concurrency 1.01x」是启动日志里最该读的一行——它把抽象的 GiB 翻译成了「同时能服务几个满长对话」。

### Aha 瞬间

**GPU 容量的真实货币是 KV cache 的 token 数，不是 GiB 也不是用户数——「我们的模型能服务多少用户」这个问题，在算出每 token cache 字节并问清「多长的对话」之前，是无法回答的。**

## 发芽 02：读快写慢 56 倍——批处理红利与「带宽墙」的纸上证明

### 种子

prefill 读 256 token 达 35,796 token/s，decode 只有 642 token/s——每 token 读写差 56 倍；64 人并发总吞吐 34 倍、每人只慢 1.9 倍。

### 故事

两段结构的物理根源：prefill 的全部 token 一起过一遍权重；decode 每产出一个 token 就要读一遍全部权重（8B 每次读 4.68 GB）。纸上验证：164 token/s × 4.68 GB ≈ 767 GB/s，是 4090 显存带宽 1008 GB/s 的 76%——**decode 是带宽受限的，算术单元大部分在等数据**。批处理把这段等待变现：读一次权重同时为 64 人各产出一个 token，边际成本趋近于零。这也精确解释了为什么共享「几乎免费」而非「完全免费」：每人速度仍从 359 降到 189（1.9 倍），因为 attention 还要读不断增长的 KV cache（16k 上下文时笔记 2,304 MiB，比权重还多一半——实测减速与纸上预测差 6%）。

### Aha 瞬间

**LLM 推理 server 的经济学由一条硬件参数决定：显存带宽——decode 的每 token 成本本质是「一遍权重读取」，所以并发摊薄的是这笔读取费；「多用户摊薄单用户成本」在 LLM 服务上不是商业模式修辞，是 76% 带宽利用率下的物理事实。**

## 发芽 03：每个数字都有出处——一篇测量文的方法学

### 种子

「本文的每个数字都来自那次录屏，或来自你可以在纸上验算的算术」——安装时间精确到 0.7 秒、KV cache 推算与日志舍入对齐、长对话减速与预测差 6%、甚至 /metrics 的 22,655 token 都能逐项对账（55 + 113×200）。

### 故事

这篇文的可信任度来自三层互相咬合的证据：实测（录屏+日志 grep）、纸上算术（config.json 四参数推 cache、带宽乘法推瓶颈）、第三方交叉（llama-bench 独立计时两段、NVIDIA 白皮书给带宽上限）。连易错处都主动标记：「第一次请求含一次性开销」「两种测速口径都不算错但要说清是哪种」「最新文档行为已变，读你自己的日志别信博客包括这篇」。八条 checklist 把经验转成可执行项，其中第 7 条（测量时说清口径）本身就是方法学的一部分。

### Aha 瞬间

**让技术内容可信的不是权威而是「可验算性」——每个关键数字都附上从原始参数出发的独立推算路径，读者可以用纸+config.json 复核你的测量；这比跑十次基准取最好值的那类文章，长久有用得多。**

<!-- SPROUT_END -->
