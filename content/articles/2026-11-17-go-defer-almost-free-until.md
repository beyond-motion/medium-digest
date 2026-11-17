---
title: 'Go''s defer Is Almost Free — Until You Do This'
slug: 2026-11-17-go-defer-almost-free-until
author: 'Vitaly Sem'
date: '2026-11-17T09:00:00+08:00'
source_url: 'https://medium.com/@virtualik/gos-defers-almost-free-until-you-do-this-a5d58cce7773'
status: processed
image: covers/2026-11-17-go-defer-almost-free-until.svg
excerpt: >-
  同一个 defer 语句可以有完全不同的运行时成本：编译器三种实现（open-coded/栈分配/堆分配）的判定条件——每函数最多 8 个 open-coded 位、returns×defers≤15 启发式、循环内 defer 强制堆分配且禁用全函数 open-coded；一个 innocuous 循环如何变成 too many open files 的生产事故，以及 -d=defer 诊断旗标。
---

<!-- REWRITE_START -->

# Go 的 defer 几乎免费——直到你这么干

> 原文：[Go's defer Is Almost Free — Until You Do This](https://medium.com/@virtualik/gos-defers-almost-free-until-you-do-this-a5d58cce7773) — Vitaly Sem

---

Go 开发者爱 defer，理由充分：它让资源管理可预测、把清理逻辑留在初始化旁边、消灭了整整一类被忘记的 Close() 与 Unlock()。

看这个熟悉的模式：

```go
func loadConfig(path string) error {
    file, err := os.Open(path)
    if err != nil {
        return err
    }
    defer file.Close()

    // Read and validate configuration.
    return nil
}
```

干净。可读。地道的 Go。

但有件事会让很多开发者意外：**两条看起来一模一样的 defer 语句，运行时成本可以完全不同。**一个几乎零额外开销；一个需要运行时簿记；第三个甚至涉及堆上分配的记录。差别往往只在于你把 defer 放在了哪里。

## 「defer 很贵」的迷思

多年来，性能向的 Go 开发者都被警告别在热路径用 defer。这个建议并非全无道理：早期实现为 deferred 调用维护运行时记录，比直接函数调用多了活。

但 Go 编译器已经进化了很远。**Go 1.13 降低了多数 deferred 调用的成本；Go 1.14 引入的优化让常见 defer 模式的性能几乎贴近普通函数调用**——1.14 的 release notes 明确写了多数 deferred 调用开销近乎零。

注意关键词：**多数**。编译器并不用同一种方式实现每一条 defer。现代 Go 有三种主要机制：

- **Open-coded defer**：清理逻辑被直接生成进函数的执行路径。
- **栈分配 defer**：运行时记录创建在函数的栈帧里。
- **堆分配 defer**：运行时记录走堆后备存储。

理解差异不只对性能调优有用，对设计更安全的资源生命周期也有用。

## 1. Open-Coded Defer：编译器干重活

想象这个函数：

```go
func handleRequest() {
    defer releaseResources()

    processRequest()
}
```

第一眼看，defer 像是运行时操作：你以为 Go 创建一个清理对象、注册到某处、函数退出时处理。但当**编译器能预先确定 deferred 操作**时，它可以直接生成清理指令。概念上，这个函数变成了：

```go
func handleRequest() {
    processRequest()
    releaseResources()
}
```

（这只是概念变换——真实实现必须保住 panic 时的清理、deferred 调用的求值规则等语言保证。）但核心优化成立：**正常返回路径不需要注册和执行单独的运行时 defer 记录。**这就是 open-coded defer。

多个 return 语句怎么办？编译器用一个小小的**激活位掩码**追踪哪些 deferred 操作已被激活：每执行一条 defer 置位对应 bit；函数退出时，生成的代码检查相关 bit、按**逆注册序**（Go 保证的 LIFO）调用对应函数。优化改变的是实现，不是语言语义。

## 2. 编译器有极限

Open-coded 高效，但不是无条件的。对当前的 Go 编译器实现，两个重要限制：

- **每个函数最多 8 个 open-coded defer 位**——单字节激活掩码，8 bit 即 8 个可能的 deferred 操作。
- **return 语句数 × defer 语句数 ≤ 15** 的启发式。超过阈值，编译器会改用别的实现，而不是在众多返回路径上展开清理逻辑。

（这些是编译器实现细节，不是 Go 语言保证；限制可以在当前编译器源码里看到。）

具体化一下：

```go
func evaluate(code int) int {
    defer release()
    defer release()
    defer release()
    defer release()

    switch code {
    case 1: return 1
    case 2: return 2
    case 3: return 3
    case 4: return 4
    default: return 0
    }
}
```

四条 defer、五条 return：**4 × 5 = 20，超了。**编译器放弃 open-coded，改建栈分配的 defer 记录。这让函数灾难性地慢吗？完全没有。但它说明了一件重要的事：**看起来几乎相同的源码，可以产生不同的编译器行为**——而在极热的函数里，这些差异可测。

## 3. 栈分配 Defer：中间地带

Open-coded 不适用时，Go 仍能避开堆。如果编译器知道每条 defer 语句在一次函数调用里至多执行一次，它可以在栈帧里预留簿记空间——运行时参与注册与执行，但记录本身不需要普通堆分配（内部走 runtime.deferprocStack 这类路径）。栈存储比堆便宜得多，也避免了为本可局部管理的记录引入堆分配。**不如 open-coded 轻，但依然高效。**

更有意思的问题是：当编译器无法确定会注册多少条 deferred 调用时会发生什么。那才是与生产系统真正相关的地方。

## 4. 危险模式：循环里的 defer

```go
func processFiles(paths []string) error {
    for _, path := range paths {
        file, err := os.Open(path)
        if err != nil {
            return err
        }

        defer file.Close()

        if _, err := io.Copy(io.Discard, file); err != nil {
            return err
        }
    }

    return nil
}
```

看起来完全合理：每个文件打开、处理、安排关闭。**但有个严重问题：文件不在每轮迭代结束时关闭，而在 processFiles 返回时才关。**如果这个函数处理 10,000 个文件，它可能同时保持几千个文件描述符打开——取决于操作系统与进程限制，应用最终会死于：

```
too many open files
```

**这已经是正确性问题了。**还有编译器层面的后果：循环改变了 defer 的分配方式——每次迭代执行另一条 defer 语句，编译器无法预知它会执行多少次（可能十个文件、一千万个文件、动态接收的任务流）。每次执行都必须注册一条保持挂起直到外层函数返回的 deferred 调用。**固定大小的栈帧槽无法表示无界数量的同时挂起的 deferred 操作——编译器因此对这种模式使用堆分配的 defer 记录。**运行时有池化机制，所以不一定每次迭代都是一次全新的操作系统级分配，但这条路径的簿记比 open-coded 多。更重要的：**deferred 操作累积到函数退出为止——你同时在为运行时管理和被不必要拉长的资源生命周期付费。**

### 正确做法：把清理挪进更小的函数

不是放弃 defer，而是改变它的作用域：

```go
func processFile(path string) error {
    file, err := os.Open(path)
    if err != nil {
        return fmt.Errorf("open %s: %w", path, err)
    }
    defer file.Close()

    if _, err := io.Copy(io.Discard, file); err != nil {
        return fmt.Errorf("read %s: %w", path, err)
    }

    return nil
}

func processFiles(paths []string) error {
    for _, path := range paths {
        if err := processFile(path); err != nil {
            return err
        }
    }

    return nil
}
```

现在生命周期不同了：每轮迭代调 processFile——开一个文件、处理、返回前关闭。defer 不再在自己函数的循环里，编译器在正常优化条件下可以用 open-coded。**三件事一次拿到：每个文件及时关闭；编译器用更便宜的 defer 实现；资源所有权清晰得多。**而且没有牺牲地道 Go。

（小说明：读文件的例子不传播 close 错误；对 writer——Close() 可能报缓冲写失败——你要显式处理那个错误。）

## 5. 一个循环能连坐同函数的其他 defer

更不明显的例子：

```go
func executeBatch(count int) {
    defer releaseBatchLock()

    for i := 0; i < count; i++ {
        defer recordCompletion()
    }
}
```

第一个 defer 在循环外。你可能指望它被 open-coded 优化。**不幸的是，不会：只要函数里存在一条循环内的 defer 语句，整个函数的 open-coded defer 处理就被禁用了。**编译器仍能对单个语句做不同的分配决策——本例里 releaseBatchLock() 退到栈分配记录，recordCompletion() 因为在循环内用堆分配记录。**一条放错位置的 defer 可以改变同一函数里其他 defer 的实现策略。**这是保持职责小、资源生命周期清晰定义的又一个理由。

## 6. 怎么看编译器到底生成了什么

别猜，问编译器。Go 有个诊断旗标可以检视 defer 的实现决策：

```go
package deferlab

//go:noinline
func release() {}

func optional(enabled bool) {
    if enabled {
        defer release()
    }
}

func backlog(n int) {
    defer release()

    for i := 0; i < n; i++ {
        defer release()
    }
}
```

编译：

```
go build -gcflags='-d=defer' ./...
```

你会看到诊断输出：`open-coded defer`、`stack-allocated defer`、`heap-allocated defer`，带文件位置。对本例的预期分类：optional → open-coded（编译器知道条件 defer 至多执行一次）；backlog 的第一个 defer → 栈分配（至多执行一次，但循环让整个函数用不了 open-coded）；backlog 循环内的 defer → 堆分配（单次调用内可能执行任意次）。

这是检视陌生代码性能特征的有用技巧——不用先写一套基准。它也解释了为什么两个看起来相似的实现行为不同。注意结果绑定于编译器版本与构建旗标，诊断输出不是语言级兼容性保证。

## 7. Goroutine、递归、闭包呢？

开发者有时以为高级控制流会自动把 deferred 调用逼上堆。**幸好不是。**

- **递归**：`traverse(depth)` 递归深度未知，但每次调用有自己的帧、每帧执行一次 defer——编译器不需要为整条递归链分配一个巨大的 defer 结构。正常条件下够格 open-coded。
- **Goroutine**：`go func(){ defer markWorkerStopped(); ... }()` 里 deferred 操作属于 goroutine 的函数——在那个函数退出时执行，而不是 launchWorker 返回时。goroutine 可能活得比创建者久，这一点不会自动把它的 defer 记录逼上堆。
- **闭包**：捕获局部变量的闭包不必然意味着堆分配的 defer 记录——编译器常能推理闭包的生命周期并把相关状态留在本地。但闭包分配与逃逸分析是 defer 记录分配之外的另一件事：闭包仍可能因别的原因让值逃逸。（顺带：这个闭包观察到的是更新后的 value=100，因为它捕获的是变量本身，不是初始值参数。）

**重点：递归、goroutine、闭包本身不是 defer 的昂贵部分。要紧的是编译器能否表示这些 deferred 操作及其生命周期。**

## 8. 能量出差别吗？

能，但基准要小心。「一个 open-coded defer 对十个堆分配 defer」的对比没什么意义——你同时在测实现策略和不同的工作量。更好的做法是**对比完成同一清理工作的两种编排**：

```go
func deferredInsideLoop(n int) {
    for i := 0; i < n; i++ {
        defer cleanup()
    }
}

//go:noinline
func runIteration() {
    defer cleanup()
}

func cleanupPerIteration(n int) {
    for i := 0; i < n; i++ {
        runIteration()
    }
}
```

（配 BenchmarkDeferredInsideLoop 与 BenchmarkCleanupPerIteration，`go test -run='^$' -bench=. -benchmem`。）两次基准每次调用都注册 100 条清理，但执行时机不同：一个在一个函数调用里累积，另一个每轮在独立函数调用里完成。这对观察「累积的运行时 defer 记录 vs 每轮函数调用」的权衡有用。它不是对 defer 开销的完美隔离测量（第二版多了函数调用），也没展示持有真实资源（文件、数据库连接）的全部影响。另一个注意：**运行时池化意味着堆分配的 defer 记录未必在 -benchmem 里表现为每次 defer 一次新分配——看完整结果，别只看 allocs/op。**并且别指望一个基准结果横跨所有架构、编译器版本与负载。真实应用请把微基准与 profiling、代表性流量下的测量结合起来。

## 9. 该在性能关键代码里停用 defer 吗？

**不该。那会是错误的结论。**现代 Go 编译器对普通 deferred 调用的优化非常好。把每条 defer 换成显式清理只会让代码更难维护，换不来可测的性能提升。`mu.Lock(); defer mu.Unlock()` 在正常退出与 panic 下都直白安全；想象手动在每个 return 前放 `mu.Unlock()`——你引入了额外的维护工作和新犯错机会。对多数后端服务，数据库查询、网络操作、JSON 序列化、磁盘 I/O 的成本碾压一条典型 open-coded defer 的开销。**把可读的清理逻辑优化掉，不该是你的第一性能策略。**

该做的是：在 defer 清晰表达资源生命周期时用它；让生命周期尽可能短；循环里反复获取资源时，引入函数边界让每个资源及时释放；当性能担忧是真实的，先检视编译器生成了什么，再做聪明的重写。

## 结语

defer 有趣的地方在于：**它的简单底下藏着一层意外精致的编译器优化。**同一个关键字可以按外围函数的结构翻译成不同的机制。常见情形下，Go 产出高效的 open-coded 清理；结构超出编译器的确定性时，它退向栈或堆。理解这三种机制，你就同时理解了 defer 的成本模型和资源的生命周期设计——两者本来就是一件事的两面。

<!-- REWRITE_END -->

<!-- SPROUT_START -->

# 《Go's defer Is Almost Free — Until You Do This》的发芽报告

## 材料核心

defer 的成本不是关键字属性而是函数结构属性。历史：早期实现维护运行时记录确实贵 → Go 1.13 改进、1.14 open-coded 优化让「多数」deferred 调用近乎零开销（关键词多数）。三种机制：①open-coded——编译器把清理直接展开进执行路径+单字节激活位掩码追踪已激活项+退出按逆序（LIFO）检查位；②栈分配（runtime.deferprocStack）——语句至多执行一次时在栈帧预留；③堆分配——次数不可预知时。两个编译器限制：每函数 ≤8 个 open-coded 位（单字节掩码）、returns×defers≤15 启发式（4×5=20 超限示例）。危险模式：循环内 defer——正确性问题（文件累积到函数返回，万文件→too many open files）+编译器后果（次数不可知→堆记录）；修法是抽小函数 processFile 让 defer 作用域=资源生命周期。连坐规则：一条循环内 defer 禁用整个函数的 open-coded（外层 defer 退栈分配）。诊断：go build -gcflags='-d=defer' 直接输出分类。反直觉三条：递归（每帧一次，够格 open-coded）/goroutine（defer 属其函数）/闭包（捕获不必然堆）都不自动昂贵。基准方法：同清理不同编排对比、-benchmem 因池化失真、跨版本不可泛化。结论：不要停用 defer——显式清理的维护成本>defer 开销，DB/网络/JSON/磁盘成本碾压之。

## 发芽 01：「几乎免费」的条件式——同一个关键字的三种命运

### 种子

「两条看起来一模一样的 defer 语句，运行时成本可以完全不同」——差别只在编译器能否预先确定 deferred 操作：能则展开进执行路径（零运行时记录），不能则退栈、再退堆。

### 故事

这打破了对语言特性的「 uniform 成本」直觉：defer 的开销不是 defer 的属性，是「defer 与其所在函数结构的关系」的属性。三个判定条件各有工程含义：至多执行一次（开放编码的前提）、8 位掩码上限（一次函数里的 defer 种类数）、returns×defers≤15（展开清理代码的体积预算）。三者全部是编译器的实现细节而非语言保证——Go 团队用「多数」这个词精确划定了承诺边界。这也解释了为什么性能直觉会过期：1.13 之前的警告基于旧实现，1.14 之后同一行代码的成本结构已经换了。

### Aha 瞬间

**语言特性的真实成本曲线是「特性 × 用法形态」的函数而不是特性本身的常数——「defer 几乎免费」的完整表述是「defer 在编译器可确定其执行次数时几乎免费」；读 release notes 时，「most」这个词比结论本身更重要。**

## 发芽 02：作用域即生命周期——一个函数抽壳修好一类生产事故

### 种子

循环内 defer 的双重代价：正确性上文件关闭被推迟到函数返回（万文件并发打开→too many open files），编译器上次数不可知强制堆分配。修法只是抽一个小函数 processFile，让 defer 的作用域等于资源的生命周期。

### 故事

这个修复的深刻处在于它一行没改 defer 的用法——改的是 defer 所在的函数边界。「资源应该在最后一次使用后立即释放」这条语义需求，被翻译成了「defer 应该住在与其生命周期等长的函数里」这条结构需求。编译器层面的收益（堆退回 open-coded）只是副产品，真正的收益是故障域的收缩：原来 10,000 个文件的关闭失败互相耦合在同一个函数帧里，现在每个文件有独立的帧、独立的 defer、独立的错误传播路径。连坐规则（一条循环 defer 禁用全函数 open-coded）则是这条原则的反面警告：函数内的 defer 们共享一个实现策略预算，放错一个位置全体降级。

### Aha 瞬间

**「把资源生命周期与函数作用域对齐」是比「记得写 defer」高一个层级的资源管理纪律——defer 解决的是「忘写清理」，函数边界解决的是「清理何时发生」；循环体获取的资源就该住在循环体的函数里，这不是代码风格，是容量事故的预防针。**

## 发芽 03：诊断旗标优先于基准——「问编译器而不是猜」

### 种子

「与其猜你的代码怎么行为，问编译器」：`go build -gcflags='-d=defer' ./...` 直接输出每条 defer 的实现分类（open-coded/stack/heap）与文件位置——不用先写一套基准。

### 故事

这是测量顺序的方法论：defer 的成本差异只有在其实现形态确定后才有意义，而实现形态是编译器的私有决策——直接读它的判定输出，跳过整个「写基准→看数字→反推实现」的间接循环。作者的基准节同样自觉：对比「同一清理的两种编排」而非「不同实现的裸开销」（后者混入了工作量差异）、提醒池化让 -benchmem 失真、警告结果绑定编译器版本。三层工具链排好了优先级：诊断旗标（定性分类）→微基准（定量对比同一工作的两种编排）→代表性流量下的 profiling（真实世界校准）。

### Aha 瞬间

**性能问题排查的正确顺序是「先问编译器/运行时的分类输出，再做基准」——编译器对「你的代码被翻译成了什么」握有一手信息，基准数字只是它的下游投影；跳过一手信息直接量投影，是用更贵的方法得到更模糊的答案。**

<!-- SPROUT_END -->
