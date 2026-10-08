---
title: 'An Introduction to Causal ML — A Practitioner''s Approach, Part 1'
slug: 2026-10-08-introduction-to-causal-ml-part-1
author: Niranjan Rao
date: '2026-10-08T09:00:00+08:00'
source_url: 'https://medium.com/@niranjan-rao/an-introduction-to-causal-ml-a-practitioners-approach-part-1-fdd91c46ff8a'
status: processed
image: covers/2026-10-08-introduction-to-causal-ml-part-1.svg
excerpt: >-
  从「巧克力消费量与诺贝尔奖数相关」的经典陷阱出发，讲清因果机器学习要回答的是「如果我多做一小时题，成绩会涨多少」这类反事实问题：用 Uber 开源的 causalml 库在合成 RCT 数据上亲手实现 S/T/X 三种 meta-learner，再用营销四象限（尤其别惊醒「睡觉的狗」）和 Gain 曲线回答「优惠券到底该发给谁」。
---

<!-- REWRITE_START -->
# 因果机器学习入门：从业者的实战路径（一）

> 原文：[An Introduction to Causal ML — A Practitioner's Approach, Part 1](https://medium.com/@niranjan-rao/an-introduction-to-causal-ml-a-practitioners-approach-part-1-fdd91c46ff8a)
> 作者：Niranjan Rao · 2026-10-07 · 9 min read
> 改写式翻译，保留原文结构与全部数据；署名与原文链接如上。

---

## 引言：相关不等于因果，但到底差在哪

我们都背诵过「相关不等于因果」。经典例子是巧克力消费量与诺贝尔奖数量的强相关——真正的驱动者是人均 GDP 这个混杂变量，它同时推高巧克力消费和获奖数量。反过来，吸烟与肺癌的因果链则是靠大量研究、临床试验才最终钉死的。因果科学的基石，就是把虚假相关和真实因果区分开。作者推荐 Judea Pearl 的《The Book of Why》作为这个领域词汇表的入门。

再想一个更日常的例子：学习时长与考试成绩正相关，但「如果我每天多学一小时，能多考几分？」——这个简单的问题让所有相关分析哑火。睡眠与心理健康也一样：我们知道相关，却无法量化「每多睡一小时带来多少活力」。能回答这类问题的，是因果机器学习（Causal ML）：它试图隔离动作本身的效果，甚至能研究反事实——「如果当时做的是另一个动作，结果会怎样？」

作者用牙膏厂商举例：经典机器学习能回答「Given 一个顾客的全部特征，他购买新牙膏的概率是多少」，帮你买广告位精准触达；但它答不了「如果用这支牙膏刷牙，未来 5 年蛀牙减少的概率是多少」。

## 数学建模：从 do-算到 RCT

Pearl 的书里给出了用 do-算子（do-calculus）和因果图从数据中榨取因果信息的完整方法论，而 establishing causality 的「黄金标准」是随机对照试验（RCT）。本文的实操基于 Uber 开源、后捐赠给社区的 causalml 库：先用合成数据模拟一次 RCT，再用几种「meta-learner」——因为它们在底层套用的是经典 ML 模型——来估计因果效应。

## Meta-Learner 之一：S-Learner

S-Learner（Single）的做法最朴素：把处理标记 w 当作普通特征塞进模型一起训练。预测时，把同一条样本分别以 w=1 和 w=0 各预测一次，两次预测之差就是处理效应——其余特征完全相同，唯一的区别是「是否接受处理」。

用 scikit-learn + causalml 实现（合成数据 mode=1，n=2000，p=5）：

```python
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from causalml.dataset import synthetic_data
from causalml.inference.meta import BaseSLearner

y, X, treatment, tau, b, e = synthetic_data(mode=1, n=2000, p=5, sigma=1.0)
X_train, X_test, y_train, y_test, treatment_train, treatment_test = train_test_split(
    X, y, treatment, test_size=0.2, random_state=42)

X_train_with_w = np.concat((X_train, treatment_train.reshape(1600, 1)), axis=1)
model = GradientBoostingRegressor()
model.fit(X_train_with_w, y_train)

x_dim = treatment_test.shape
X_test_with_w_1 = np.concat((X_test, np.ones((x_dim[0], 1))), axis=1)
X_test_with_w_0 = np.concat((X_test, np.zeros((x_dim[0], 1))), axis=1)
te_pred = model.predict(X_test_with_w_1) - model.predict(X_test_with_w_0)

learner = BaseSLearner(learner=GradientBoostingRegressor(random_state=42))
ate_lib = learner.estimate_ate(X=X, treatment=treatment, y=y)
print(f'ATE from code: {te_pred.mean():.2}')          # 0.61
print(f'ATE from library: {ate_lib.item():.2}')       # 0.61
```

手写实现与库函数给出的平均处理效应（ATE）完全一致：0.61。

## Meta-Learner 之二：T-Learner

T-Learner 的 T 指「two」：训练两个独立模型，一个只学处理组样本，一个只学对照组样本。推断时处理效应 = 处理模型预测 − 对照模型预测。

```python
from causalml.inference.meta import BaseTLearner

treatment_model = GradientBoostingRegressor()
control_model = GradientBoostingRegressor()
treatment_model.fit(X_train[treatment_train == 1], y_train[treatment_train == 1])
control_model.fit(X_train[treatment_train == 0], y_train[treatment_train == 0])

te_pred = treatment_model.predict(X_test) - control_model.predict(X_test)
# ATE from code: 0.63 / ATE from library: 0.61
```

这次手写值 0.63 与库值 0.61 出现了微小分歧——不同的建模方式对同一个数据给出略有差异的估计，这正是后文需要模型评估方法的原因之一。

## Meta-Learner 之三：X-Learner

X-Learner 名字里的 X 来自第一阶段两个模型的「交叉」（cross over）：用对照模型去预测处理组样本、用处理模型去预测对照组样本，从而得到「补全的处理效应」（imputed effect）：

- 处理组的补全效应 d_treatment = 处理组真实 y − 对照模型对处理组 X 的预测
- 对照组的补全效应 d_control = 处理模型对对照组 X 的预测 − 对照组真实 y

然后再训练两个模型分别拟合这两个补全效应，最终预测时用倾向得分 e 加权融合：

```python
from causalml.inference.meta import BaseXRegressor

treatment_model.fit(treatment_X, treatment_y)
control_model.fit(control_X, control_y)

d_treatment = treatment_y - control_model.predict(treatment_X)
d_control = treatment_model.predict(control_X) - control_y

imputed_treatment_model = GradientBoostingRegressor(random_state=42).fit(treatment_X, d_treatment)
imputed_control_model = GradientBoostingRegressor(random_state=42).fit(control_X, d_control)

te_pred = (imputed_control_model.predict(X_test) * e_test
           + imputed_treatment_model.predict(X_test) * (1 - e_test))
# ATE from code: 0.52 / ATE from library: 0.53
```

三学习者全部跑通：S 给出 0.61、T 给出 0.63、X 给出 0.52。

## 评估 Uplift 模型：优惠券该发给谁

数字营销行业最经典的问题：「优惠券发给谁，才能让他们真的买单？」如果营销零成本，人人发券自然是最优解——但成本现实存在，答案就没那么显然了。作者指出，任何潜在受众里其实住着四种人：

- **Do Not Disturbs（睡觉的狗）**：发券反而坏事。想想 Netflix 那封「有新片上线」的邮件如何提醒了你「你已经很久没登录了」，然后你退订了会员——个性化动作对业务造成了实质伤害。这类人的 uplift 为**负**。
- **Lost Causes**：发不发券都不会买，对产品完全无感（想想给美食博主寄薯片优惠券）。uplift 为**零**。
- **Sure Things**：最优质的忠实顾客，发不发券都会买。uplift 为**零**。
- **Persuadables**：真正「可争取」的人——不发券不买，发券就会产生购买兴趣。uplift 为**正**。

好的营销活动应该只 targeting Persuadables，因为他们才代表营销投入的真实回报。这也是 uplift 模型评估之所以重要的原因。

## Gain 曲线：投放的止损点在哪

评估方法：先把受众按预测 uplift 从高到低排序，在第 k 个位置计算累计增益（处理组均值 − 对照组均值）×（两组累计人数），画出 Gain 随投放人数的曲线；归一化版本就是著名的 Qini 曲线。

```python
from causalml.metrics import get_cumlift, plot_gain

learner = BaseXRegressor(learner=GradientBoostingRegressor(random_state=42))
y, X, treatment, tau, b, e = synthetic_data(mode=1, n=2000, p=5, sigma=1.0)
cate_x = learner.fit_predict(X=X, treatment=treatment, y=y)

cate_df = pd.DataFrame({
    'cate_x': cate_x.reshape(-1), 'treatment': treatment, 'y': y, 'tau': tau,
}).sort_values(by='cate_x', ascending=False)

gain, ys_t, ys_c = [], [], []
for row in cate_df.itertuples():
    (ys_t if row.treatment == 1 else ys_c).append(row.y)
    if ys_t and ys_c:
        gain.append((np.sum(ys_t) / len(ys_t) - np.sum(ys_c) / len(ys_c))
                    * (len(ys_t) + len(ys_c)))

plt.plot(gain)
plt.plot(np.argmax(gain), gain[np.argmax(gain)], 'ro')
plt.xlabel('Population treated'); plt.ylabel('Gain')
```

曲线上的红点标记最大增益位置：越过这一点继续扩大投放，回报转负——因为剩余受众的 uplift 是零或负值。

## 结语

这篇入门覆盖了因果推断的基本原理、记号，并从零实现了三种 meta-learner 和 Gain 曲线评估。因果机器学习在数字营销和广告技术里有巨大的落地潜力。系列后续将探索更多学习方法、真实世界的细微差别、评估方法，并把这些技术用到真实开源数据集上。配套代码在作者的 GitHub 仓库（niranjanrao13/uplift-modelling-expt），参考文档为 causalml 官方文档。
<!-- REWRITE_END -->

<!-- SPROUT_START -->
# 《An Introduction to Causal ML — A Practitioner's Approach, Part 1》的发芽报告

## 材料核心

这篇文章回答的是一个被「相关不等于因果」这句口头禅掩盖了几十年的实操问题：怎样才能从观测数据里得到「如果我做 X，Y 会怎么变」的量化答案。作者以 Pearl 的 do-演算为理论底座，以 Uber 开源的 causalml 为工程抓手，在合成 RCT 数据上把三种 meta-learner（S/T/X）逐个实现并对比 ATE 估计值，最后用营销四象限和 Gain 曲线把「uplift 建模为什么值得做」讲成了一个人人能懂的发券问题。

## 发芽 01：混淆变量是「常识」最大的藏身之处

### 种子

巧克力消费量与诺贝尔奖数量强相关，人均 GDP 同时驱动两者；吸烟与肺癌的因果链则花了几十年流行病学研究才钉死。

### 故事

文章开篇把一虚一实两个例子并排放置：前者里「常识」一眼识破伪相关，后者里恰恰是常识（吸烟致癌）需要大量临床试验才能从「强相关」升级为「因果」。同一种统计工具，在两个场景里的任务完全相反——一个要拆掉虚假的因果叙事，一个要为真实的因果主张补足证据。

### Aha 瞬间

「相关不等于因果」不是一句否定句，而是一句中性的事实陈述：相关里可能藏着混杂变量，也可能藏着尚未确认的真因果。因果 ML 的价值不是「否定相关」，而是提供一套程序，把相关往两个方向各自审问到底。

## 发芽 02：S/T/X 三学习者，是同一个问题的三种实验设计

### 种子

S-Learner 把处理标记当普通特征；T-Learner 分组建两个模型；X-Learner 用交叉预测补全「假如对照组接受了处理会怎样」的反事实结果，再用倾向得分加权。

### 故事

三个学习器估计的是同一个 ATE，给出的答案却是 0.61、0.63、0.52——而且都是「正确」的。S 简单但可能让处理信号被其他特征淹没；T 干净但两组样本各自变少；X 最精巧，它借对照模型的形状去想象处理组的反事实，等于用数据自己补了一次「未发生的实验」。

### Aha 瞬间

选哪种 meta-learner 不是「哪个更准」的问题，而是「你愿意为反事实付出哪种建模假设」的问题。X-Learner 的本质是：当处理组样本稀缺时，让对照组的信息通过一个交叉模型「移民」过来——小样本场景下的杠杆。

## 发芽 03：四类人群拆掉了「发券总比不发好」的直觉

### 种子

受众分四种：睡觉的狗（uplift 为负）、无可救药（零）、必然购买（零）、可争取者（正）；Gain 曲线的红点给出投放止损位。

### 故事

Netflix 的「新片上线」邮件把沉睡用户提醒到退订——这是「睡觉的狗」最生动的注脚：对一部分人，营销动作本身就是负资产。传统响应模型会把「必然购买者」也列为营销目标（他们确实买了），但那笔优惠券是纯浪费；只有 uplift 视角能识别出「因为发了券才买」的那一小群人。

### Aha 瞬间

精准营销的终极目标函数不是「谁会买」，而是「谁的购买是发券引起的」。Gain 曲线上红点之前的人值得投，红点之后的每一分钱都在补贴零 uplift 和负 uplift 的人群——把「投放预算」变成了一个可以用曲线读出的止损问题。
<!-- SPROUT_END -->
