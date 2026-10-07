---
title: 'Implementing a Lock-Free SPSC Queue in C++'
slug: 2026-10-07-lock-free-spsc-queue-in-c
author: Shah Rahman
date: '2026-10-07T09:00:00+08:00'
source_url: 'https://medium.com/@samiur1998/implementing-a-lock-free-spsc-queue-in-c-b41a5d0a0a2d'
status: processed
image: covers/2026-10-07-lock-free-spsc-queue-in-c.svg
excerpt: >-
  从 Leslie Lamport 1979 年的证明出发，用 C++ atomics 手写无锁单生产者单消费者队列的完整教程：环形缓冲 + 双游标的单线程骨架，relaxed/acquire/release 三种内存序各司其职，最后加上缓存游标与缓存行对齐两刀优化——每个成员独占一条 cache line，消除 false sharing。
---

<!-- REWRITE_START -->
# 用 C++ 实现无锁 SPSC 队列

> 原文：[Implementing a Lock-Free SPSC Queue in C++](https://medium.com/@samiur1998/implementing-a-lock-free-spsc-queue-in-c-b41a5d0a0a2d)

---

> 「构建高吞吐系统的秘诀，不是把事情并行化，而是让单个线程畅通无阻地奔跑。」——Martin Thompson

## 引子

上世纪九十年代末到两千年代初，CPU 厂商撞上了频率墙——主频停滞在 3–4 GHz 附近。高性能计算圈子因此转向多核架构。最初人们使用操作系统层的原语：锁、信号量、互斥体。但这些原语很快就跟不上高频场景——代价来自上下文切换（context switch）和缓存行弹跳（cache line bouncing）。

1979 年，Leslie Lamport 证明了一件事：**如果恰好只有一个线程写、恰好只有一个线程读，你根本不需要互斥。**单生产者单消费者（SPSC）队列由此诞生。今天它被普遍视为无锁数据结构的「圣杯」——在现代 CPU 架构上达到线程间通信吞吐的理论极限。

它的用武之地都是性能攸关的领域：高频交易（HFT）、音频处理与数字信号处理（DSP）、游戏引擎与渲染管线、高吞吐媒体流与视频编码。

本教程讲如何在 C++ 里高效实现这个数据结构。

## 实现

### 单线程版

单线程版本非常直白：

* 一个数组充当环形缓冲/队列
* 数组大小取 2 的幂，让递增可以用位运算高效完成
* Push 游标与 Pop 游标分别追踪队列的头与尾
* 保留一个空槽，用于标记队列已满

```cpp
#pragma once
#include <cstddef>

template <typename T, std::size_t capacity>
class SPSCQueue {
  std::size_t push_cursor = 0;
  std::size_t pop_cursor = 0;
  T buf[capacity];

 public:
  SPSCQueue() = default;
  ~SPSCQueue() = default;

  const bool enqueue(T& addVal) {
    std::size_t increment_one = (push_cursor + 1) & (capacity - 1); // 下一个槽
    if (increment_one == pop_cursor) return false;  // 队列满，返回 false
    buf[push_cursor] = addVal;                      // 放入值
    push_cursor = increment_one;                    // 推进 push 游标
    return true;
  }

  const bool dequeue(T& removeVal) {
    if (pop_cursor == push_cursor) return false;    // 队列空，返回 false
    removeVal = buf[pop_cursor];                    // 取出元素
    pop_cursor = (pop_cursor + 1) & (capacity - 1); // 推进 pop 游标
    return true;
  }
};
```

### 多线程版

多线程版本复杂一些。这份数据结构现在有两个线程：生产者与消费者（SPSC 之名由此而来）。生产者向缓冲入队，消费者从缓冲出队，两者都要读写 push 与 pop 游标——数据竞争不可避免。

要高效地消除竞争，可以用 C++ 的 atomics。需要做的事：

* Push 游标与 Pop 游标改为原子值
* 入队（enqueue）中：push_cursor 用 `std::memory_order_relaxed` 读取，pop_cursor 用 `std::memory_order_acquire` 读取，push_cursor 用 `std::memory_order_release` 写入
* 出队（dequeue）中：对称地，pop_cursor relaxed 读、push_cursor acquire 读、pop_cursor release 写

```cpp
#pragma once
#include <cstddef>
#include <atomic>

template <typename T, std::size_t capacity>
class SPSCQueue {
  std::atomic<std::size_t> push_cursor{0};
  std::atomic<std::size_t> pop_cursor{0};
  T buf[capacity];

 public:
  SPSCQueue() = default;
  ~SPSCQueue() = default;

  const bool enqueue(T& addVal) {
    std::size_t push_cursor_val = push_cursor.load(std::memory_order_relaxed);
    std::size_t increment_one = (push_cursor_val + 1) & (capacity - 1);
    std::size_t pop_cursor_val = pop_cursor.load(std::memory_order_acquire);
    if (increment_one == pop_cursor_val) return false;   // 队列满
    buf[push_cursor_val] = addVal;
    push_cursor.store(increment_one, std::memory_order_release);
    return true;
  }

  const bool dequeue(T& removeVal) {
    std::size_t pop_cursor_val = pop_cursor.load(std::memory_order_relaxed);
    std::size_t push_cursor_val = push_cursor.load(std::memory_order_acquire);
    if (pop_cursor_val == push_cursor_val) return false; // 队列空
    removeVal = buf[pop_cursor_val];
    pop_cursor.store((pop_cursor_val + 1) & (capacity - 1), std::memory_order_release);
    return true;
  }
};
```

用到的原子操作，简释如下：

* **Relaxed 载入**：快。用来读取当前线程自己的进度。
* **Acquire 载入**：用来读取另一个线程的游标。它强制当前线程「追上」对方线程已发生的全部内存变更。
* **Release 存储**：用来更新当前线程的游标。它强制本地对缓冲的全部读写先完成，然后才让另一个线程知道「有变化了」。

## 优化

到这里，SPSC 队列在功能上已经完整。但还有两处微妙的改动，能大幅提升性能：

**缓存 Push 与 Pop 游标**：大幅减少冗余的载入操作。

**对成员变量做填充与对齐**：给每个成员变量独占一条缓存行，消除伪共享（false sharing）。

```cpp
#pragma once
#include <cstddef>
#include <atomic>
#include <new>

template <typename T, std::size_t capacity>
class SPSCQueue {
  alignas(std::hardware_destructive_interference_size) std::atomic<std::size_t> push_cursor{0};
  alignas(std::hardware_destructive_interference_size) std::size_t cached_push_cursor{0};
  alignas(std::hardware_destructive_interference_size) std::atomic<std::size_t> pop_cursor{0};
  alignas(std::hardware_destructive_interference_size) std::size_t cached_pop_cursor{0};
  T buf[capacity];

 public:
  SPSCQueue() = default;
  ~SPSCQueue() = default;

  const bool enqueue(T& addVal) {
    std::size_t push_cursor_val = push_cursor.load(std::memory_order_relaxed);
    std::size_t increment_one = (push_cursor_val + 1) & (capacity - 1);
    if (increment_one == cached_pop_cursor) {              // 先查缓存值
      cached_pop_cursor = pop_cursor.load(std::memory_order_acquire);
      if (increment_one == cached_pop_cursor) return false; // 队列真的满了
    }
    buf[push_cursor_val] = addVal;
    push_cursor.store(increment_one, std::memory_order_release);
    return true;
  }

  const bool dequeue(T& removeVal) {
    std::size_t pop_cursor_val = pop_cursor.load(std::memory_order_relaxed);
    if (pop_cursor_val == cached_push_cursor) {            // 先查缓存值
      cached_push_cursor = push_cursor.load(std::memory_order_acquire);
      if (pop_cursor_val == cached_push_cursor) return false; // 队列真的空了
    }
    removeVal = buf[pop_cursor_val];
    pop_cursor.store((pop_cursor_val + 1) & (capacity - 1), std::memory_order_release);
    return true;
  }
};
```

缓存游标的逻辑：入队时先看本地缓存的 pop_cursor 判断「是否可能满」；只有缓存值显示可能满时，才去做昂贵的 acquire 载入、向对方游标确认。绝大多数时候，一次原子载入都不需要。

## 结语

希望这篇文章对你有信息量和用处。想深入研究 SPSC 队列，我强烈推荐 Charles Frasch 的演讲。

干杯 🥂
<!-- REWRITE_END -->

<!-- SPROUT_START -->
# 《Implementing a Lock-Free SPSC Queue in C++》的发芽报告

## 材料核心

这篇材料是一份从理论源头到生产级优化的完整无锁队列教程。理论起点是 Leslie Lamport 1979 年的证明：恰好一写一读时无需互斥——单生产者单消费者（SPSC）队列由此成为无锁数据结构的「圣杯」，在线程间通信吞吐上达到现代 CPU 的理论极限。实现分三步递进：单线程骨架（2 的幂容量的环形缓冲、双游标、留一空槽标记队满）；多线程改造（C++ atomics 三种内存序各司其职——relaxed 读自己的进度、acquire 读对方的游标并强制追上对方的内存变更、release 写自己的游标并强制本地读写先落地）；最后两刀优化——缓存对方游标让绝大多数判断不触发昂贵的跨核载入，以及按缓存行对齐消除伪共享。材料的历史线索同样清晰：频率墙逼出多核，OS 锁原语的上下文切换与缓存行弹跳逼出无锁设计。

## 发芽 01：约束越精确，成本越归零

### 种子

材料的理论根基是一条正面陈述的约束：Lamport 证明的不是「锁可以被优化」，而是「在恰好一写一读这个精确约束下，互斥是多余的」。SPSC 队列的全部性能魔法，都来自这个约束的严格性。

### 故事

对比链条清晰：通用原语（锁、信号量）为任意线程组合付出上下文切换与缓存行弹跳的代价；SPSC 把线程组合收紧到「一写一读」这一个特例，互斥的成本整体消失——它不是更快的锁，是让锁这个问题不再存在。

### Aha 瞬间

性能工程的第一杠杆不是优化手段，而是把问题的约束说精确——「任意情况下的正确」和「恰好一种情况下的正确」之间，隔着一个数量级的实现成本。

## 发芽 02：三种内存序，是三种「我知道谁动了内存」的承诺

### 种子

材料对 relaxed/acquire/release 的分工解释可以提炼成一句话：relaxed 用来读自己的进度（不需要知道别人），acquire 用来读别人的游标（强制追上对方已发生的全部内存变更），release 用来写自己的游标（强制自己的读写先落地再通知对方）。

### 故事

这套分工精确地对齐了两个线程的物理现实：自己游标的读永远不用同步（只有自己在写它），对方游标的读必须全屏障（否则可能读到脏缓冲），自己游标的写必须最后落地（否则对方可能看到游标前进而缓冲还是旧的）。

### Aha 瞬间

内存序不是玄学咒语，是对「谁在什么时候需要看见谁的写入」这个问题的逐条回答——把同步的最小必要范围精确到每一次读写，正是无锁编程的全部纪律。

## 发芽 03：最后一刀优化的本质，是把「询问对方」推迟到确有必要

### 种子

缓存游标优化的逻辑极简：先看本地缓存的对方游标，只有缓存值显示「可能满/可能空」时才去做昂贵的 acquire 载入确认——绝大多数入队出队操作，一次跨核同步都不发生。

### 故事

配合按 `hardware_destructive_interference_size` 对齐（每个游标与缓存游标各占一条缓存行），消除伪共享——否则两个线程各自写自己的变量，也会因为共享缓存行而互相拖累。优化前后代码几乎相同，性能差距却来自这两处「看不见的结构」。

### Aha 瞬间

高并发的终极优化不是让同步更快，而是让大多数同步根本不必发生——缓存一份「大概率没变」的答案，只在它可能失效时才去询问真相。
<!-- SPROUT_END -->
