---
title: 'Crediting Crypto Deposits Exactly Once: Lessons from a Go Wallet Service'
slug: 2026-11-26-crypto-deposits-exactly-once
author: 'Erkin Duran'
date: '2026-11-26T09:00:00+08:00'
source_url: 'https://medium.com/@erkinduran/crediting-crypto-deposits-exactly-once-lessons-from-a-go-wallet-service-18fb17f819d5'
status: processed
image: covers/2026-11-26-crypto-deposits-exactly-once.svg
excerpt: >-
  2018 年一个人写加密交易所的入账哲学：通知不是「一次」机制（节点 walletnotify 会重发、重启会重放、HTTP 超时会重试——每条通知都变成余额更新，充 1 BTC 的用户看到 2 BTC，那不是 bug 报告是提现申请）；解法是让数据库在写钱的同一个事务里拒绝第二次入账（txid 唯一约束+ON CONFLICT DO NOTHING+重复返回 nil 而非报错）；今天的五条改法：键要 chain+txid+vout（一笔交易可付多个地址）、ETH 别漏内部调用与日志、确认数按链按金额、监听器与账本之间加队列（RabbitMQ 至少一次→约束变成可以安全迟 ack 的理由）、对账任务无论如何都要有。
---

<!-- REWRITE_START -->

# 把加密货币入账做到恰好一次：一个 Go 钱包服务的教训

> 原文：[Crediting Crypto Deposits Exactly Once: Lessons from a Go Wallet Service](https://medium.com/@erkinduran/crediting-crypto-deposits-exactly-once-lessons-from-a-go-wallet-service-18fb17f819d5) — Erkin Duran

---

*四种币、一条数据库约束，以及今天的我会如何不同处理的那些边界情况。*

2018 年，我独自写了第一版加密交易所：订单流、撮合、余额账本、充提、前端。让我夜里睡不着的那部分不是撮合，是一个简单得多的问题：**当客户把币打到充值地址，你怎么确保他的余额恰好加一次？**

## 架构

我们支持四种币：Bitcoin、Litecoin、Ethereum 和 Ripple（XRP）。BTC/LTC/ETH 每个客户有自己的充值地址，平台始终知道哪个地址属于谁；XRP 不同——共享一个充值地址，靠付款上的 destination tag 区分客户。

主应用是 PHP/Laravel，但入账不放在那里。我把它们拆成小的 Go 服务（按链族一个），理由有三：**长驻监听**——与区块链节点通信意味着整天保持连接、随时响应事件，这是 Go 进程的天赋、PHP 请求周期的别扭活；**隔离**——一个卡死或事件洪泛的节点应该拖慢入账，而不是拖慢订单簿；**钱的代码爆炸半径小**——改动余额的那部分代码小到可以一口气读完。

当时系统里没有消息中间件：Go 服务把入账直接写进数据库，再通过 HTTP 调主应用。这个约束塑造了下面的一切——**没有队列吸收重试，数据库就必须是那个说「不，这件事你已经做过」的东西。**

## 入账怎么到达

节点告诉我们地址上发生了什么：BTC/LTC 各自有全节点跑在我们服务器上，凡触及钱包地址的交易都会通知，Go 服务接住并记录；ETH 监听节点的新交易流逐笔检查，收款方是我们的充值地址就是我们的；XRP 则是打到共享地址的付款通知，destination tag 指明该给哪个客户入账。一笔确认就够入账。

## 重复问题

通知根本不是「一次」机制。同一笔交易会到你手上不止一次：节点自己会重发——Bitcoin Core 的 `-walletnotify` 在「钱包交易变化」时触发，同一个 txid 通常出现两次（首次出现一次、被挖出一次）；你的服务重启后会重放最近的事件以免漏单；对主应用的 HTTP 调用超时了，但活其实干完了，你重试。

**如果每条通知都变成一次余额更新，充 1 BTC 的客户会看到 2 BTC。在交易所里这不是 bug 报告——是提现申请。**

## 修法：让数据库拒绝第二次入账

我用交易 id（txid）做去重键，上面加唯一约束。入账是一个数据库事务：①插入入账行；②若撞唯一约束，停——这笔已经入过账；③否则写一条账本分录、更新余额；④提交。

因为检查与入账发生在同一个数据库事务里，两条通知竞争不可能双赢——第二条撞约束、什么都不做。Go 代码如下（这是重新简化的示例，非原始代码，已经用上后文更强的键）：

```go
type Deposit struct {
    Chain       string  // "btc", "ltc", "eth", "xrp"
    TxID        string
    OutputIndex int     // BTC/LTC 的 vout；ETH 的 log/call 序号；XRP 恒 0
    UserID      int64
    Amount      string  // 十进制字符串，绝不用 float
}

func CreditDeposit(ctx context.Context, db *sql.DB, d Deposit) error {
    tx, err := db.BeginTx(ctx, nil)
    if err != nil { return err }
    defer tx.Rollback()

    res, err := tx.ExecContext(ctx, `
        INSERT INTO deposits (chain, txid, output_index, user_id, amount)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (chain, txid, output_index) DO NOTHING`,
        d.Chain, d.TxID, d.OutputIndex, d.UserID, d.Amount)
    if err != nil { return err }

    n, err := res.RowsAffected()
    if err != nil { return err }
    if n == 0 { return nil // 已入账，安全忽略
    }

    if _, err := tx.ExecContext(ctx, `
        INSERT INTO ledger_entries (user_id, asset, amount, reason, ref)
        VALUES ($1, $2, $3, 'deposit', $4)`,
        d.UserID, d.Chain, d.Amount, d.TxID); err != nil { return err }

    if _, err := tx.ExecContext(ctx, `
        UPDATE balances SET available = available + $1
        WHERE user_id = $2 AND asset = $3`,
        d.Amount, d.UserID, d.Chain); err != nil { return err }

    return tx.Commit()
}
```

两个细节比看起来重要：**对重复返回 `nil`**——重复不是错误；如果你返回错误，调用方就会重试，等于给一件永远不会成功的事装上重试循环。**金额用十进制字符串**——satoshi、litoshi、wei、drops 都经不起 `float64` 一个来回；要么按最小单位存整数，要么在数据库里存十进制。

## 今天的我会怎么改

txid 约束对我们当时见到的情形够用了。带着更多经验回头看，这些边界我会补上：

**一笔交易可以付你的多个地址。**BTC/LTC 的单笔交易有多个输出——如果另一家交易所批量提现，一个 txid 可能付给你们两个客户。只按 txid 做唯一键会入第一笔、**悄悄丢掉第二笔**。键应该是 chain + txid + output index（vout）。

**Ethereum 不只有普通转账。**扫「收款方是我地址」的交易只抓得到简单 ETH 转账；会漏掉从智能合约发出的 ETH（内部调用）和代币转账——它们以事件日志形式出现，而不是交易的收款方。要支持的话，键的 index 部分来自 call 或 log 位置。

**确认数应该按链、按金额定。**BTC 的一笔确认仍可能被链重组撤销；XRP 相反，账本一验证即最终。今天我会按链设阈值、大额充值提高阈值，并把入账先存成「已见」再变「已入账」，让客户先看到钱在路上。

**在监听器与账本之间加队列。**今天我不会再用 HTTP 调主应用。Go 监听器向 RabbitMQ 发布「已见到充值」消息，消费者负责入账——持久化消息+手动 ack 意味着崩溃或主应用变慢不再丢事件：消息等着被重投。代价是 RabbitMQ 是**至少一次**投递，重投是常态不是例外；**唯一约束不会因此消失，它反而成为消费者可以安全迟 ack 的理由。**

**对账任务无论如何都要有。**队列让丢事件变得不太可能，不是不可能。一个周期任务对比「节点见到的充值」与「账本入账的充值」，抓住幸福路径漏掉的一切。

## 教训

**恰好一次的投递，网络给不了你、节点给不了你、HTTP 也给不了你。你能得到的是恰好一次的效果**：接受同一事件会到达很多次，让数据库在写钱的同一个事务里拒绝第二次入账。为这个「拒绝」选对键，是整件事的大部分工作——而在区块链上，最显然的那个键 txid，恰恰不够。

<!-- REWRITE_END -->

<!-- SPROUT_START -->

# 《Crediting Crypto Deposits Exactly Once》的发芽报告

## 材料核心

Erkin Duran（6 min）2018 年独自开发加密交易所的入账架构复盘：四币种（BTC/LTC/ETH 独立地址+XRP 共享地址靠 destination tag）；入账拆成 Go 服务三理由（长驻监听/隔离节点故障/钱的代码爆炸半径小）；无消息中间件→数据库必须亲自说「不」。重复三源：walletnotify 语义性重发（出现+挖出各一次）、重启重放、HTTP 超时重试——「充 1 BTC 看到 2 BTC 不是 bug 报告是提现申请」。修法：txid 唯一约束+单事务（插行→撞约束即停→写账本→更余额→提交）+ON CONFLICT DO NOTHING；两细节：重复返回 nil（返回错误=给永不成功的事装重试循环）、金额十进制字符串（float64 会毁 satoshi/wei）。今日五改：键 chain+txid+vout（批量提现单 txid 多地址会静默丢第二笔）、ETH 内部调用与代币日志不在「收款方」扫描里、确认数按链按金额+先「已见」后「已入账」、RabbitMQ 至少一次投递→唯一约束成为安全迟 ack 的理由、对账任务对比「节点所见 vs 账本所记」。教训：恰好一次的投递得不到，恰好一次的效果做得出。

## 发芽 01：「恰好一次的投递」不存在，「恰好一次的效果」是设计出来的

### 种子

「恰好一次的投递，网络给不了你、节点给不了你、HTTP 也给不了你。你能得到的是恰好一次的效果：接受同一事件会到达很多次，让数据库在写钱的同一个事务里拒绝第二次入账。」

### 故事

这是分布式系统最著名的「不可能三角」在钱上的落地：投递层（网络/节点/队列）无论怎么设计都只能给出「至少一次」或「至多一次」，恰好一次投递在理论上就不存在。工程上的出路是把语义上移——不追求「事件只来一次」，而追求「事件的效果只生效一次」，把去重的责任放进唯一有原子的地方：数据库事务。这个转译的精妙在于它把「不可靠的投递」重新定义为「正常情况」：重复通知不再是异常，而是系统的稳态输入。文中的 RabbitMQ 段落把这个思想推到极致：引入至少一次的队列之后，唯一约束不仅没被淘汰，反而升级为「消费者可以安全迟 ack 的理由」——去重机制从防错的补丁变成了新架构的承重墙。

### Aha 瞬间

**分布式系统的成熟不是消灭重复，而是把「重复是常态」写进架构前提——恰好一次不是投递属性而是状态机属性；钱的正确性住在数据库的拒绝里，不住在网络的可靠里。**

## 发芽 02：「最显然的键恰恰不够」——去重键是业务语义的浓缩

### 种子

「为这个『拒绝』选对键，是整件事的大部分工作——而在区块链上，最显然的那个键 txid，恰恰不够。」一笔批量提现交易可以付给你们两个客户，按 txid 去重会入第一笔、静默丢掉第二笔。

### 故事

去重键看起来是实现细节，实际是对「什么算同一次事件」的业务定义。txid 键在「一交易=一事件」的世界观下成立，而区块链的 UTXO 模型里一笔交易天然多输出——键选错不会报错，会**静默丢钱**（第二笔输出被 DO NOTHING 吞掉），这是比重复入账更隐蔽的故障：入账错误会被人发现，丢钱没人会发现。同类的语义盲区还有 ETH 的内部调用与代币日志（不在「收款方」字段里）。教训可以推广：**任何去重/幂等键都必须通过「事件的最小不可分单位是什么」这一问来验证，而不是拿系统最显眼的标识符顺手充当——最显眼的标识符往往是聚合层级，不是事件层级。**

### Aha 瞬间

**幂等键的正确粒度=事件的最小不可分单位，而不是系统的显眼标识——txid 是交易的身份证，不是入账事件的身份证；选错层级的键不报错，它静默地丢钱。**

## 发芽 03：从「数据库说 no」到「队列+约束+对账」——三层防线的职责分工

### 种子

2018：没有中间件，数据库必须亲自说「不」。今天：RabbitMQ 在监听器与账本之间（持久化+手动 ack，崩溃不再丢事件），但「唯一约束不会消失，它成为消费者可以安全迟 ack 的理由」；外加周期对账任务对比「节点所见 vs 账本所记」。

### 故事

作者的架构演进轨迹呈现一个清晰的分层纪律：队列管「不丢」（持久化+重投），约束管「不重」（同一事务里的拒绝），对账管「兜底」（幸福路径之外的对差审计）。三层各自不可替代：队列给不了恰好一次（至少一次投递），约束防不了「节点根本没通知」的丢失，对账防不了即时错误但能发现一切已发生的偏差。值得注意的是演进的方向不是「用队列取代约束」，而是「加一层、旧层换职责」——与 11-20 Plaid 译文的迟融合哲学同源：新组件进入时不替换旧机制，而是改变旧机制存在的理由。

### Aha 瞬间

**钱的正确性是三层防线的乘积：队列解决「不丢」、唯一约束解决「不重」、对账解决「万一」——任何一层被寄予另一层的期望，都会以静默的资金错误收场。**

<!-- SPROUT_END -->
