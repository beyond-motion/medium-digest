---
title: 'CDC System Design Interview: PostgreSQL, Kafka, Debezium and the Failure Nobody Tests'
slug: 2026-11-09-cdc-system-design-postgresql-kafka-debezium
author: 'Architecture Unfiltered'
date: '2026-11-09T09:00:00+08:00'
source_url: 'https://medium.com/engineering-playbook/cdc-system-design-interview-postgresql-kafka-debezium-and-the-failure-nobody-tests-852d4aed0a4a'
status: processed
image: covers/2026-11-09-cdc-system-design-postgresql-kafka-debezium.svg
excerpt: >-
  CDC 系统设计八讲：复制槽能填满你的磁盘、初始快照是一致性问题、Kafka 顺序有边界、At-Least-Once 要求幂等、CDC vs Outbox、failover 追问——「数据库 HA 与 CDC 连续性是分开的工程保证」。
---

<!-- REWRITE_START -->

# CDC 系统设计面试：PostgreSQL、Kafka、Debezium 与那个没人测的故障

> 原文：[CDC System Design Interview: PostgreSQL, Kafka, Debezium and the Failure Nobody Tests](https://medium.com/engineering-playbook/cdc-system-design-interview-postgresql-kafka-debezium-and-the-failure-nobody-tests-852d4aed0a4a) — Architecture Unfiltered

---

典型的 CDC（Change Data Capture，变更数据捕获）架构长这样：

```
APPLICATION
     |
     v
 POSTGRESQL
     |
     v
WRITE-AHEAD LOG
     |
     v
LOGICAL REPLICATION
     |
     v
  DEBEZIUM
     |
     v
 KAFKA TOPICS
     |
  +--+----------+
  |     |       |
  v     v       v
SEARCH ANALYTICS CACHE
INDEX   PIPELINE UPDATER
```

**数据库保持为真相源。下游系统维护可能暂时落后于已提交状态的派生视图。**

这个区分要紧，因为 **CDC 不会自动提供 PostgreSQL 与每个消费者之间的同步一致性。**

## 1. 估算 CDC 负载

假设一个 PostgreSQL 平台每天产生 1 亿行变更：

| 需求 | 目标 |
|---|---|
| 日行变更数 | 1 亿 |
| 平均变更速率 | ~1,157/秒 |
| 峰值变更速率 | 15,000/秒 |
| 平均事件大小 | 2 KB |
| 日原始事件量 | ~200 GB |
| 正常复制延迟 | < 5 秒 |
| 投递语义 | At Least Once |

（这是示意性的容量假设。WAL 体量、Kafka 存储与实际事件大小取决于 PostgreSQL 配置、表结构与连接器的事件表示。）

设计要同时测量吞吐与复制延迟：**一条仍在处理事件的管道，如果渐进地落后于数据库，同样可能在运营上变得危险。**

## 2. PostgreSQL 复制槽能填满你的磁盘

PostgreSQL 复制槽让消费者跟踪自己在逻辑变更流里处理到了哪里，**也影响数据库为该消费者保留 WAL 的时长。**

假设 Debezium 停止消费 6 小时，而 PostgreSQL 继续承载生产流量：

```
POSTGRESQL WRITES
     |
     v
    WAL
     |
     +----> DEBEZIUM CONSUMING
     |
     +----> REPLICATION SLOT POSITION
                  |
                  v
            WAL RETENTION
```

复制槽没有足够推进时，数据库可能保留大量 WAL。**如果保留量不加约束，磁盘使用可以一路涨到威胁主库。**

设置 `max_slot_wal_keep_size` 可以限制保留量，但超过上限可能使槽不可用、需要恢复或重新初始化——这是「保护磁盘容量」与「保留从原位置恢复的能力」之间的权衡。

监控必须包含：保留的 WAL 字节、槽 restart 位置、confirmed flush 位置、连接器健康、下游 lag。**一条 CDC 故障，绝不应该在无预警的情况下变成主库故障。**

## 3. 初始快照是一致性问题

CDC 对一个已有数据库启动时，可能需要先复制数百万条既有行，再开始消费持续的变更。

天真的做法是：先扫描表，然后开始读 WAL。**这两个操作之间的间隙会造成漏更新。**

Debezium 支持为「初始数据捕获与持续变更流的协调」设计的快照机制（具体行为取决于连接器版本与快照模式）。系统必须定义快照记录如何与后续变更交互——消费者可能先看到一个初始行镜像，之后再收到同一行的更新。

大数据集下快照吞吐同样要紧：激进的扫描会与生产查询抢 I/O 和数据库资源。Staff 级的设计应该讲清楚：快照隔离、到流式的交接、快照中途失败的恢复。

## 4. Kafka 顺序有边界

**Kafka 在分区内保持记录顺序；它不提供跨所有分区的全局顺序。**

要实体级一致性，同一实体的事件一般应使用稳定的分区键：

```
Customer 42 -> Partition 3
Customer 42 -> Partition 3
Customer 91 -> Partition 7
```

这能保住共享键事件的处理顺序——前提是生产者与分区策略维持该保证。

但顺序在下游仍可能被破坏：一个并发处理记录、乱序提交结果的消费者，会用旧状态覆盖新状态。消费者应使用合适的排序控制或**源版本检查**——比如派生库存储一个可单调比较的源位置、拒绝陈旧更新。版本方案必须反映真实的源与连接器保证，而不是假设任意 WAL 位置在 failover 之后仍全局可比。

## 5. CDC 通常是 At-Least-Once

假设 Debezium 向 Kafka 发布了一个事件，然后在源进度被持久化之前崩溃。重启后，连接器可能**再次发布同一个变更**。

消费者因此必须容忍重复事件。实用做法是「稳定的事件身份 + 幂等的数据库操作」：更新派生视图时记录最后应用的源版本，在同一个事务里拒绝更旧或重复的更新。

这对**计数器与金融聚合尤其重要**——把同一个增量应用两次，即使原始 PostgreSQL 事务只提交了一次，也会损坏派生数据。

**流平台内部的 exactly-once 保证，不会自动让对外部数据库的写入变成 exactly-once。**

## 6. CDC vs 事务性 Outbox

CDC 与事务性 outbox 解决相关但不同的问题：**CDC 捕获数据库变更；事务性 outbox 在与业务状态变更的同一个事务里记录显式的业务事件。**

| 方式 | 最适合 |
|---|---|
| 裸表 CDC | 数据复制、同步 |
| 事务性 Outbox | 业务事件发布 |
| CDC + Outbox | 可靠的事件传输 |

裸表 CDC 会把内部 schema 细节暴露给下游——一次列改名或表重构可能变成集成问题。Outbox 给应用对事件契约的控制权；Debezium 随后把 outbox 记录发布到 Kafka，应用代码无需在数据库提交后单独发一次网络请求。

当业务事件需要显式语义与可靠传输时，这个组合正合适。

## 7. Staff 工程师面试的追问

面试官引入一个 PostgreSQL failover：旧主库不可用，副本被提升，而 Debezium 仍连着原来的源。

**连接器能无丢失、无重复地恢复吗？**

答案取决于 PostgreSQL 版本、复制槽的 failover 支持、连接器配置、以及被提升服务器的 WAL 历史与原主库的关系。架构必须验证复制槽的连续性、确立一个安全的重启位置；**如果连续性无法被证明，恢复可能需要对权威数据库重新快照或对账。**

消费者在事件被重放时仍应保持正确，并且必须检测那些无法通过普通重试修复的缺口。

**最强的答案不会因为「PostgreSQL 有副本」就承诺无缝 failover。数据库高可用与 CDC 连续性，是两个分开的工程保证。**

## 高频 FAQ

- **什么是 CDC？**变更数据捕获把已提交的数据库变更传播到下游系统。基于日志的 CDC 读取数据库事务日志，支持异步复制或事件驱动集成。
- **Debezium 如何配合 PostgreSQL 与 Kafka？**Debezium 用 PostgreSQL 的逻辑解码捕获变更，经 Kafka Connect 发布结构化事件。初始快照与流式行为取决于连接器配置。
- **Debezium 会造成 PostgreSQL 磁盘问题吗？**停滞的逻辑复制槽会导致 WAL 保留增长。保留限制与监控对保护数据库容量至关重要。
- **CDC 保证 exactly-once 处理吗？**CDC 管道通常要求消费者处理重复投递。端到端正确性取决于幂等性、顺序与派生状态的事务化处理。
- **PostgreSQL failover 时 CDC 会怎样？**恢复取决于复制槽可用性、WAL 连续性与连接器能力。某些 failover 场景需要对账或重新快照。

理解 Kafka 是有用的；能讲清「一个 PostgreSQL 复制槽如何威胁生产存储」「快照如何与活写入交互」「消费者如何拒绝陈旧事件」，展示的是更深一层的工程判断。

（文末推广：作者的 Senior & Staff System Design Interview OS、Spring Boot 课程与 ProdRescue AI 评估服务。）

<!-- REWRITE_END -->

<!-- SPROUT_START -->

# 《CDC System Design Interview》的发芽报告

## 材料核心

以「Staff 系统设计面试」框架讲 CDC 管线的八个要害：架构（PostgreSQL→WAL→逻辑复制→Debezium→Kafka→派生消费，数据库是唯一真相源、CDC 不提供同步一致性）；负载估算（1 亿行/天、峰值 15000/秒、At-Least-Once）；**复制槽能填满磁盘**（消费停 6 小时→WAL 保留暴涨威胁主库，max_slot_wal_keep_size 是「保磁盘 vs 保恢复位」的权衡）；初始快照是间隙一致性问题；Kafka 只有分区内序（实体级一致性靠稳定分区键+下游源版本检查拒绝陈旧更新）；At-Least-Once 要求幂等（计数器与金融聚合最脆弱；流平台内部 exactly-once 不外溢）；CDC vs Outbox（裸表暴露 schema，outbox 给事件契约）；failover 追问的最强答案是「数据库 HA 与 CDC 连续性是分开的工程保证」。

## 发芽 01：「生产的第一公民」会被人质的身份绑架——复制槽的存储人质问题

### 种子

CDC 的设计初衷是「别丢事件」，于是复制槽让数据库为慢消费者保留 WAL——但数据库是生产系统的一等公民：保留没有上限，磁盘一路涨到威胁主库；加了上限（max_slot_wal_keep_size），超限又可能让槽不可用、需要重新初始化。

### 故事

这是一个结构性两难：保磁盘还是保恢复位置，**你必须显式选一个，不选就是两个都输**。解法是监控组合拳（保留 WAL 字节、槽 restart 位置、confirmed flush 位置、连接器健康、下游 lag）加一条运营红线：「CDC 故障绝不应在无预警的情况下变成主库故障」——下级管道的故障不应该靠上级基础设施的灾难来暴露。

### Aha 瞬间

**任何「上游为下游保留状态」的机制，都隐含一份上游资源的人质——设计时必须同时写清赎回策略（上限+对账+重置成本），否则慢消费者就会变成生产库的人质劫持者。**

## 发芽 02：At-Least-Once 的幂等账本——「流平台内部 exactly-once 不外溢」

### 种子

Debezium 发布事件后在记录进度前崩溃→重启重发。消费者必须容忍重复；对计数器与金融聚合，同一增量应用两次就能损坏派生数据——即使原始事务只提交了一次。

### 故事

实用解是「稳定事件身份 + 幂等操作」：派生库记录最后应用的源版本、在同一事务里拒绝更旧或重复的更新。顺序层面配套：分区内序+实体级稳定分区键+并发消费者的源版本检查（且版本方案必须反映真实连接器保证，别假设 WAL 位置跨 failover 可比）。一句话总结全文最重要的边界：**Kafka 事务的 exactly-once 只存在于 Kafka 内部；一出边界，正确性就是消费者的责任。**

### Aha 瞬间

**「系统边界的每一侧各持一份语义，越过边界的只有事件」——分发语义（at-least-once）在边界上衰减为「至少」，于是幂等与版本对账从最佳实践升格为正确性的构成部分。**计数器是这类脆弱性的试金石。

## 发芽 03：HA ≠ CDC 连续性——两个「保证」的独立性宣言

### 种子

面试追问：PostgreSQL failover、副本提升、Debezium 还连着旧源——连接器能无丢失无重复恢复吗？最强答案：**不承诺。数据库高可用与 CDC 连续性是分开的工程保证。**

### 故事

理由链：恢复取决于 PG 版本、槽 failover 支持、连接器配置、新主的 WAL 历史与原主的关系——任何一环断裂，恢复路径就退化为重新快照或对权威库对账。所以架构必须验证槽连续性、确立安全重启位置；消费者必须在重放时保持正确、检测普通重试修不了的缺口。「有副本」只解决数据库层的可用性，它对「变更流不丢不重」什么都没承诺。

### Aha 瞬间

**「下层高可用」不自动构成「上层连续性」——每一层都要单独证明自己的恢复语义。**凡是建立在别人 HA 之上的管道，都该回答同一个面试追问：你的上游 failover 时，你的不变量还成立吗？

<!-- SPROUT_END -->
