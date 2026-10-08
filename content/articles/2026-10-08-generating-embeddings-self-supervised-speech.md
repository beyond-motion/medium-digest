---
title: 'Generating embeddings from a self-supervised speech model'
slug: 2026-10-08-generating-embeddings-self-supervised-speech
author: Noah Macey (UC Berkeley D-Lab)
date: '2026-10-08T09:00:00+08:00'
source_url: 'https://medium.com/@dlab-berkeley/generating-embeddings-from-a-self-supervised-speech-model-025b6c93f77d'
status: processed
image: covers/2026-10-08-generating-embeddings-self-supervised-speech.svg
excerpt: >-
  UC Berkeley D-Lab 的完整教程：用 Hugging Face transformers 加载预训练 WavLM，把 audioMNIST 的 500 条录音变成 768 维语音嵌入，statpooling 压成 1536 维定长向量后 PCA 降维——数字 0/3/4 的聚类因共享「r」音互相粘连，而同样的流程在传统 MFCC 特征上聚类涣散，自监督语音模型的价值一目了然。
---

<!-- REWRITE_START -->
# 用自监督语音模型生成语音嵌入：从 WavLM 到 PCA 的完整实操

> 原文：[Generating embeddings from a self-supervised speech model](https://medium.com/@dlab-berkeley/generating-embeddings-from-a-self-supervised-speech-model-025b6c93f77d)
> 作者：Noah Macey（UC Berkeley D-Lab）· 2026-10-07 · 16 min read
> 改写式翻译，保留原文结构与全部数据；署名与原文链接如上。

---

## 自监督语音模型：会「听」的 LLM 亲戚

自监督语音模型（S3M）和大语言模型（LLM）一样，是在语言数据上训练的深度学习模型；区别在于 LLM 建模文本，S3M 建模语音——HuBERT、WavLM 这类现代模型可以用数万小时的录音训练。训练的产物是一个把语音波形转成**语音嵌入**的算法：相比原始声波，嵌入易于处理，已经在语音识别、音频分类、语言学研究中大量落地。

本教程面向有一些编程经验、但没有深厚 PyTorch/transformers 背景的读者，完整走一遍「加载预训练模型 → 生成嵌入 → 可视化 → 与传统方法对比」的流程。

先补一个最小概念集。嵌入在机器学习里无处不在：词嵌入驱动 LLM，还有图像嵌入、蛋白质嵌入等等。它们的共同思想是把对象表示成向量，使**向量之间的关系对应对象之间的关系**——本质上是「很有信息量的数字列表」。我们的语音嵌入对应音频片段，且受上下文影响（这种机制叫注意力，正是它引爆了近年的深度学习浪潮）。以 WavLM 为例，它为每 20 毫秒语音生成一个 768 维嵌入。

数学家喜欢把向量理解为空间中的点，「嵌入」这个名字本身就来自这个隐喻：模型把音频「嵌入」到某个空间里。作者第一次被语音嵌入击中，是因为 2024 年的一篇语言学论文：研究者录下不同母语的说话人，把录音转成嵌入，然后用「空间路径」提问——结果母语者的嵌入在声学空间里紧紧贴着一条路径走，而二语者的路径摇摇晃晃，彼此偏离也更远。不用再问「波形怎么了」，直接问「点怎么了」。

工程上，语音嵌入几乎总是别的算法的原料：比如做语音转文字，你可以把录音先过一遍 WavLM，把嵌入喂给转写算法。

## 环境准备

教程配套文件在作者的 GitHub 仓库。环境管理推荐 uv（装好后在仓库目录跑 `uv sync`，再 `uv run jupyter notebook`）；用 Anaconda 的读者可以直接用仓库里的 requirements.txt。

先加载库：

```python
import pandas as pd
import numpy as np
from pathlib import Path
import urllib.request, zipfile
import phonlab as pb        # 音频加载与重采样
import librosa              # MFCC 对比用
import fileorganize         # 目录转 DataFrame
from tqdm.auto import tqdm
from transformers import AutoFeatureExtractor, AutoModel
import torch
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
```

有 GPU 就用 GPU，没有就回退 CPU：

```python
device = torch.device(torch.accelerator.current_accelerator()
                      if torch.accelerator.is_available() else "cpu")
print(f"Using device: {device}")   # cpu / cuda(PC) / mps(Mac)
```

## 数据集：audioMNIST

MNIST 手写数字分类是机器学习的经典入门题，本教程致敬传统，改用 **audioMNIST**：60 位说话人对数字 0–9 的数千条录音。文件名格式为 `[数字]_[说话人]_[第几遍].wav`——`8_33_7.wav` 就是 33 号说话人第七遍说「eight」。下载脚本带缓存检查，已下载则跳过，最后把数据目录存为常量 `DATA_DIR`。

用 `fileorganize.dir_to_df()` 把目录转成 DataFrame，正则抽出数字、说话人、遍数三个标签，再随机抽 500 条录音以加快后续计算。

## 单文件建模：先跑通一条录音

取 DataFrame 第一行的文件，用 Hugging Face 的 transformers 加载 **WavLM base**（用了近千小时音频训练的基础版；更大的版本更耗算力，没必要）：

```python
MODEL = "microsoft/wavlm-base"
feature_extractor = AutoFeatureExtractor.from_pretrained(MODEL)
model = AutoModel.from_pretrained(MODEL).to(device).eval()
```

第一行声明模型；`AutoFeatureExtractor` 加载的预处理器负责把原始音频整形成模型要求的规格；`AutoModel` 加载训练好的参数并搬到设备上；因为我们只做推理不训练，加 `.eval()`。（遇到「未设置 HF_TOKEN」的警告可以忽略——WavLM 是公开模型。）

WavLM 要求输入采样率为 16000 Hz。UC Berkeley 的 phonlab 包一条命令完成「加载 + 重采样」：

```python
target_sr = 16000
fpath = DATA_DIR / relpath / fname
audio_array, sampling_rate = pb.loadsig(fpath, fs=target_sr)
```

`audio_array.shape` 是一维 NumPy 数组——那就是我们的声波。生成嵌入只需四行：

```python
inputs = feature_extractor(audio_array, sampling_rate=sampling_rate, return_tensors="pt")
inputs = {k: v.to(device) for k, v in inputs.items()}
with torch.inference_mode():
    outputs = model(**inputs, output_hidden_states=True)
```

为什么 `output_hidden_states=True`？Transformer 由多层堆叠，每一层都产出中间结果（隐藏状态）。语音模型里这些中间层非常有用：研究者通常在每个层上都训练一次任务，选表现最好的那层——浅层可能更适合说话人识别，深层更适合语音转文字。本次可视化只用最后一层。

查看输出：`outputs.hidden_states` 是 13 组嵌入（第 1 层的输入 + 后续 12 层的输出）。最后一层的形状是 `[1, 36, 768]`，从后往前读：768 是每个嵌入的维度；36 是嵌入个数（随音频时长变化）；第 1 维是批大小（批量送音频时才有意义，且音频长度相近时效果最好）。

## 批量处理：整个数据集的嵌入

把单文件流程封装成函数，加一个 `layer_idx` 参数指定取哪一层；返回值里 `.squeeze(0)` 去掉单一的第 0 维，`.cpu()` 搬回主存，`.numpy()` 转成 NumPy 数组：

```python
def extract_features(audio_array, audio_sr, layer_idx):
    inputs = feature_extractor(audio_array, sampling_rate=audio_sr, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.inference_mode():
        outputs = model(**inputs, output_hidden_states=True)
    layer_features = outputs.hidden_states[layer_idx]
    return layer_features.squeeze(0).cpu().numpy()
```

循环 500 个文件（`layer_idx=-1` 取最后一层），把波形、采样率、嵌入一并收集进 DataFrame：

```python
embedding_df = []
for idx, relpath, fname, digit, speaker, token in tqdm(dir_df.itertuples(), total=len(dir_df)):
    audio_array, sampling_rate = pb.loadsig(DATA_DIR / relpath / fname, fs=16000)
    embedding_df.append({
        "audio_arr": audio_array,
        "sampling_rate": sampling_rate,
        "embedding": extract_features(audio_array, sampling_rate, -1),
    })
df = pd.concat([dir_df, pd.DataFrame(embedding_df)], axis="columns")
```

## 可视化：statpooling + PCA

可视化有两个难题：一条录音对应多个向量，用哪个？768 维怎么画进两三维？

第一个问题的答案是 **statpooling**，三步把变长向量序列压成定长：以 30 个 768 维嵌入为例——第一步取逐分量的**均值**，得一个 768 维向量；第二步取逐分量的**标准差**，再得一个 768 维向量；第三步把两者**拼接**成 2×768=1536 维的单一向量。副产品是所有录音都变成同样大小：

```python
def statpool(x: np.ndarray) -> np.ndarray:
    assert x.ndim == 2
    means = x.mean(axis=0)
    sds = x.std(axis=0) + 1e-5
    return np.concatenate([means, sds])
df['statpool'] = df['embedding'].map(statpool)
```

第二个问题交给**主成分分析（PCA）**——线性代数里的经典降维术，目标是在尽量保住向量间关系的前提下压缩维度：

```python
df[["x_coord", "y_coord", "z_coord"]] = PCA(n_components=3).fit_transform(np.stack(df['statpool']))
```

前两个主成分的散点图上，**十个数字的聚类清晰可见**——同一数字的嵌入确实彼此相似。更妙的是聚类之间的距离有含义：0、3、4 三个簇互相粘连，而它们恰好是仅有的三个带「r」音的数字。不做更多分析不能断言这就是原因，但这正是自监督语音模型自己能找到的那种语言学特征。

## 与 MFCC 对比

把音频变成向量的另一条老路是 **MFCC**（梅尔频率倒谱系数），同样用于说话人识别等任务。它和语音嵌入有两点根本不同：结果向量**不含上下文信息**，且算法**完全不需要训练**。这两点都是巨大优势——MFCC 计算更便宜、可解释性更强。

用 librosa 算 MFCC（20 个分量，短窗口参数 n_fft=400、hop_length=160），statpool 后先标准化再走同样的 PCA 流程：

```python
mfccs_statpooled = []
for idx, audio_arr, sampling_rate in df[['audio_arr', 'sampling_rate']].itertuples():
    mfccs = librosa.feature.mfcc(y=audio_arr, sr=sampling_rate,
                                 n_mfcc=20, n_fft=400, hop_length=160).T
    mfccs_statpooled.append(statpool(mfccs))
mfcc_features = StandardScaler().fit_transform(np.stack(mfccs_statpooled))
mfcc_coords = PCA(n_components=3).fit_transform(mfcc_features)
```

散点图上数字的边界**模糊得多**。但作者特意提醒：别让这两张图骗你认为 MFCC 不行——对某些研究问题或工程场景，MFCC 反而是更好的选择，加更多处理也能改善它的表现。对比的意义在于：嵌入流程**几乎不费力气**就把数字分开了，而 MFCC 要达到同样效果需要更多调整。

## 注意事项与结语

训练 S3M 很复杂，但**用**它们生成嵌入很简单。教程可以随意改造：换成 HuBERT 等其他模型，或用自己的音频替换 audioMNIST。一个特别值得做的练习是把不同层的输出分别画出来，看哪层效果最好。

作者给出三个自己踩过的坑：其一，模型的关键规格（层数、适合的音频时长）常常埋在 Hugging Face 模型页或训练论文里，值得花时间找，而且经常别人已经整理过；其二，模型对较短音频表现更好，长句处理明显更慢；其三，各语言在这些模型的训练数据里覆盖极不均衡——用在非英语语音前，先确认该语言在不在训练集里，多语言模型可选 mHuBERT-147 之类。

想深入模型训练原理，建议从深度学习基础入手（3Blue1Brown 是极好的资源，Jurafsky & Martin 的教材有很好的章节），再转向语音模型专述和「模型到底学到了什么」的研究。

（文末附 transformers、WavLM、HuBERT、audioMNIST、phonlab、uv 等完整参考文献，见原文。）
<!-- REWRITE_END -->

<!-- SPROUT_START -->
# 《Generating embeddings from a self-supervised speech model》的发芽报告

## 材料核心

这是一篇「把大模型当原料用」的完整教程：不训练任何东西，只把预训练 WavLM 当成一个「波形→向量」的转换器，把 500 条数字录音变成 768 维嵌入，再用 statpooling（均值+标准差拼接成 1536 维）和 PCA 两级压缩画进二维散点图——十个数字自动聚类，且 0/3/4 三个带「r」音的数字互相粘连；同样的流程跑在无训练、无上下文的传统 MFCC 特征上，聚类涣散。自监督表示的价值，一张图说清。

## 发芽 01：换表示，比换问题便宜

### 种子

2024 年那篇语言学论文不问「波形怎么了」，而问「点在空间里怎么走」：母语者的嵌入贴着一条路径，二语者摇摇晃晃。

### 故事

原始声波是高维、嘈杂、难以直接推理的对象；嵌入把它们换成「空间中的点」，于是「口音差异」这种模糊的语言学问题，变成了「路径偏离程度」这种可以算距离的几何问题。教程里 PCA 聚类同样是这个思路的续篇——数字分类不需要设计声学特征，只需要在正确的表示空间里「看一眼」。

### Aha 瞬间

很多看似需要新算法的问题，其实只需要一次表示的转换。嵌入的本质是「把领域知识预付进向量里」：模型训练时吃掉的数万小时语音，变成了下游任务里免费的先验。

## 发芽 02：statpooling 是「变长到定长」的通用压型术

### 种子

一条录音产生几十个向量、每条录音长度还不同——statpooling 用逐分量均值、逐分量标准差、拼接三步，把任意长度的序列压成同一个 1536 维向量。

### 故事

均值保住「典型状态」，标准差保住「变化幅度」，拼接意味着「既描述它是什么样，也描述它怎么动」。这个套路完全不限音频：任何「一个对象对应一串向量」的场景——一段代码的逐行嵌入、一次会话的逐轮嵌入、一支股票的逐日向量——都可以用同一把刀切成定长指纹，然后进 PCA、进聚类、进任何下游模型。

### Aha 瞬间

工程上「每条数据维度不一致」是个烦人的门槛，而 statpooling 用两个统计量就把它抹平了，代价几乎为零。变量长序列的定长压缩，不一定需要注意力池化或训练一个小网络——先试试均值和标准差。

## 发芽 03：无监督长出来的音位学，与「必须带基线」的方法论

### 种子

散点图上 0、3、4 三个簇粘连，而它们是仅有的带「r」音的数字；对照组 MFCC 的聚类却涣散得多。

### 故事

没人告诉模型「r 是卷舌音」，模型在海量自监督预训练里自己把声学相似性编码进了表示空间——聚类形状就是它「学到的音位学」。而作者同样郑重地提醒：别因此给 MFCC 判死刑，它更便宜、更可解释，某些场景下更好。教程的力量恰恰在于这个对照组设计：同一份数据、同一套 statpool+PCA 流程，唯一变量是表示方法，结论因此干净。

### Aha 瞬间

自监督模型的可怕之处是它会在没人要求的地方长出结构（连音位都分好了）；而评估它的正确姿势不是「看它好不好」，而是「换掉它，其余全不变」——单变量对照实验，在机器学习教程里和在中学生物课里一样是金标准。
<!-- SPROUT_END -->
