---
title: 'LLM Streaming in Production: 6 Ways Server-Sent Events Break After the Demo'
slug: 2026-11-11-llm-streaming-sse-production-failures
author: 'Pranav Kumar'
date: '2026-11-11T09:00:00+08:00'
source_url: 'https://medium.com/@k.pranav_22/llm-streaming-in-production-6-ways-server-sent-events-break-after-the-demo-4664f4cc700c'
status: processed
image: covers/2026-11-11-llm-streaming-sse-production-failures.svg
excerpt: >-
  localhost 上流式永远正常——上真实负载均衡才见六种故障：缓冲、空闲超时、孤儿生成、200 之后的错误、半截输出入库、重连重启生成；心跳头+终止事件+job-bound 架构的完整处方。
---

<!-- REWRITE_START -->

# 生产环境的 LLM 流式输出：Demo 之后，SSE 会以这六种方式坏掉

> 原文：[LLM Streaming in Production: 6 Ways Server-Sent Events Break After the Demo](https://medium.com/@k.pranav_22/llm-streaming-in-production-6-ways-server-sent-events-break-after-the-demo-4664f4cc700c) — Pranav Kumar

---

在 localhost 上，LLM 流式输出永远正常。token 在模型产出的瞬间出现，demo 活灵活现，所有人都同意这个功能做完了。然后它被放到真实的负载均衡器后面——答案在十一秒的沉默后整块出现，或者说到一半没有任何报错地停下，而没人在自己的笔记本上能复现它。

我已经不再把流式输出当作 UX 的点缀。**一条流式响应是一条长连 HTTP 连接**：它穿过你拥有的每一层代理、占着一个付费的上游生成、并且已经发出了自己的状态码。这三个事实各自产生一类故障。以下是一个流式端点上线前我会检查的六种。

## 故障 1 与 2：你与用户之间的网络

**故障 1 是缓冲（buffering）。**路径上的某样东西在转发之前先把响应攒起来。Nginx 默认缓冲代理响应；压缩中间件要攒够字节才压缩；某些 CDN 与企业代理同样如此。症状一旦你找它就一目了然：**首 token 时间 = 总响应时间。**

修法很便宜：发 `X-Accel-Buffering: no` 与 `Cache-Control: no-cache` 头、把 `text/event-stream` 从 gzip 排除，然后**通过真实的 ingress 测试，而不是端口转发**。如果你只在 localhost 上测过流式，你就没有测过流式。

**故障 2 是空闲超时（idle timeout）。**Nginx 的 `proxy_read_timeout` 默认 60 秒，AWS 应用负载均衡器的空闲超时也是。静默超过这个长度的流会被切断。这曾经很少见；现在不是了：**推理模型在输出任何东西之前要先思考，agent 会在响应中途跑工具调用——一分钟的无声间隙现在是正常行为。**

修法是心跳。SSE 内建了一个：任何以冒号开头的行是客户端会忽略的注释。**每 15 秒发一条，路径上的每个空闲计时器都被重置。**作为红利，心跳给你的 UI 一个诚实的东西可以显示：仍在工作。

## 故障 3 与 4：连接和生成是两回事

**故障 3 是孤儿生成（orphaned generation）。**用户关掉标签页、导航离开、或按了停止。除非你的服务器注意到并取消上游请求，**模型会继续生成到它的 token 上限——你在为没人会读的输出付费。**在一个答案很长、用户没耐心的聊天产品里，这是账单上一条真实的行项。

测试只要两分钟：开一条流、杀掉客户端、看上游请求有没有结束。这里还有一个陷阱：**多数 provider 在最后一个 chunk 里报告 token 用量**——被中止的流永远报告不了它。如果你按请求计费或做预算，就自己数转发的 token。

**故障 4 是 200 之后的错误。**状态码随第一个字节发出去了。如果 provider 在第 400 个 token 失败——限流、过载、内容过滤、或你自己的 deadline——你无法回头再返回一个 500。连接直接关闭，而天真的客户端把半个答案当作完成来渲染。

修法在协议层而不是基础设施。**每条流以一个显式的终止事件结束**——`done` 或 `error`——客户端把「没有终止事件就结束」的流视为失败。你的仪表盘需要同样的想法：基于状态码的错误率对中途失败是盲的——**把「没有终止事件就结束的流」作为独立指标追踪。**

以下是我能接受的最小 FastAPI handler，覆盖了头、心跳、断连取消与两种终止事件：

```python
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

@app.post("/chat/stream")
async def chat_stream(body: ChatIn, request: Request):
    async def events():
        stream = await llm.chat.completions.create(**body.params, stream=True)
        nxt = asyncio.ensure_future(anext(stream, None))
        try:
            while not await request.is_disconnected():
                done, _ = await asyncio.wait({nxt}, timeout=15)
                if not done:
                    yield ": ping\n\n"  # SSE 注释：重置代理空闲计时器
                    continue
                chunk = nxt.result()  # 重新抛出上游错误
                if chunk is None:  # 上游干净地结束
                    yield "event: done\ndata: {}\n\n"
                    return
                if chunk.choices and chunk.choices[0].delta.content:
                    yield f"data: {json.dumps(chunk.choices[0].delta.content)}\n\n"
                nxt = asyncio.ensure_future(anext(stream, None))
        except Exception:
            yield "event: error\ndata: {}\n\n"  # 带内：200 已经发出
        finally:
            nxt.cancel()
            await stream.close()  # 结束上游请求与计费
    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)
```

权衡：它保持简单，是因为 HTTP 连接仍然拥有生成。**这恰恰是下一个要崩的点。**

## 故障 5 与 6：你存了什么、你重放什么

**故障 5 是部分输出被当作完整。**文字一旦上屏就倾向于被持久化：进对话历史、进文档、进下游任务。如果流被切断——被故障 4 或撞上输出 token 上限——你就把半个答案存成了一条 assistant 回合，而下一次模型调用会建立在它上面。结构化输出更糟，因为半个 JSON 对象根本无法解析。

我的规则：**每条流式消息以 streaming / complete / truncated / failed 四种状态之一持久化。结构化输出只在终止事件时解析。在标记任何东西为 complete 之前检查 finish reason。**一条带可见「继续」按钮的截断回答是功能；一条被静默存储的截断回答是几周后你才会发现的数据质量 bug。

同样的推理适用于安全检查。你无法撤回一个已经发出的 token。如果你要校验或审核输出，要么逐句扣留文本、检查后再放行，要么在协议里内建一个「撤回并替换」事件。**两者选一个，有意地选。**

**故障 6 是重连重启生成。**移动网络会断。如果客户端重试请求，天真的服务器会开始一次全新的生成。用户看着一个不同的答案从头开始，你付两倍的钱，任何带副作用的工具调用会跑两次。浏览器的 EventSource 会自动重连——**所以这可以在你团队里没有任何人写重试代码的情况下发生。**

没有哪个 header 能修这一个。修法是架构性的：**别再让 HTTP 连接拥有生成。**

## 连接绑定 vs 任务绑定流式：我会怎么选

**连接绑定（connection-bound）**就是上面的 handler：请求调用模型、转发 chunk。一个进程、零额外基础设施，随连接而死。

**任务绑定（job-bound）**把它拆成两半。请求创建一个「生成任务」；一个 worker——Celery 任务或后台 asyncio 任务——调用模型，把每个 chunk 追加到以生成 ID 为键的 Redis Stream；HTTP handler 变成一个从指定 offset 开始 tail 该流的读取器。重连的客户端发送它最后看到的事件 ID、从那里恢复；第二个标签页或设备可以附着到同一个生成上。

它有成本：每个 chunk 多一跳、要管理的 Redis 内存（每条流设 TTL）、更多需要监控的活动部件。取消的语义也变了：断开连接不再停止工作，停止按钮必须变成一次显式的 cancel 调用。**对十分钟的 agent 运行这正是你要的；对聊天你必须记得单独去建它。**

我的经验法则：**短答案、无副作用的可以留在连接绑定。任何带工具调用、带副作用、跑分钟级、或有移动客户端的，应该任务绑定。**多数团队从前者起步，在第一个 agent 功能上线之后立刻发现需要后者。

## 本周就能做的流式测试清单

1. 让一条流穿过生产 ingress，对比首 token 时间与 localhost。
2. 让一条流静默 90 秒，确认它存活。
3. 中途杀掉客户端，确认上游请求被取消、其成本被记录。
4. 在 50 个 token 之后注入一个上游错误，确认 UI 显示失败而不是一个完成的答案。
5. 强制 token 上限截断，确认存储的消息被标记为 truncated。
6. 在手机上中途断网，确认没有第二次生成启动。
7. 加四个指标：首 token 时间、无终止事件结束的流、中止率、断连之后生成的 token 数。

以上每一项都可以用一个「会睡眠、会报错、会按命令截断」的假上游自动化。**构建那个假上游，是你能在这个功能上花掉的最好的一个下午——因为这六种故障，没有一种会出现在 happy-path 的 demo 里。**

（你的团队最先撞上的是六种里的哪一种？是在测试里发现的，还是在用户的截图里？）

<!-- REWRITE_END -->

<!-- SPROUT_START -->

# 《LLM Streaming in Production》的发芽报告

## 材料核心

「localhost 上流式永远正常」是幻觉的起点：一条流式响应是长连 HTTP 连接，穿过每层代理、占用付费上游生成、且状态码已发——三个事实各生一类故障，合计六种：①缓冲（Nginx 默认攒包，症状是首 token 时间=总时长；修：X-Accel-Buffering/Cache-Control 头+排除 gzip+真实 ingress 测试）②空闲超时（60s 默认 vs 推理模型与 agent 的长静默；修：15 秒 SSE 冒号心跳）③孤儿生成（客户端走了模型还在生成付费；注意 provider 只在最后 chunk 报 token 用量）④200 之后的错误（无法回头改状态码；修：显式终止事件 done/error+「无终止事件结束」作为独立指标）⑤半截输出入库（四种状态持久化、终止事件才解析结构化输出、安全检查逐句扣留或内建撤回）⑥重连重启生成（EventSource 自动重连即触发；修：job-bound 架构——生成与连接解耦，Redis Stream+Last-Event-ID 恢复）。经验法则：短答案无副作用可连接绑定；带工具/副作用/分钟级/移动客户端必须任务绑定。

## 发芽 01：「200 已发出」——流式的错误处理为什么在协议层不在基础设施层

### 种子

传统 HTTP 里错误以状态码表达；流式响应的第一个字节就把 200 发出去了——provider 在第 400 个 token 限流时，你无法回头返回 500。连接只是关闭，天真的客户端把半截答案当完成渲染。

### 故事

推论分三层：协议层要内建终止事件（done/error 二值），客户端把「无终止事件结束」视为失败；指标层要把「无终止事件结束的流」作为独立于状态码错误率的度量——**基于状态码的错误率对流式故障是结构性失明**；存储层要区分四种状态（streaming/complete/truncated/failed），因为半截 JSON 连解析都过不了、半截答案却会被下一次调用当作上下文。

### Aha 瞬间

**当响应变成「有生命的连接」，错误处理的全部机制必须从 HTTP 层迁移到应用协议层——状态码在第一个字节之后就成了历史文物。**「无终止事件结束的流」这个指标，是流式系统世界里 5xx 的等价物。

## 发芽 02：三个所有权的错觉——连接不拥有生成、上游不知道你走了、最后一包才报账

### 种子

故障 3/4/6 共享同一个根源错觉：以为「HTTP 连接 = 生成过程的生命周期」。实际上用户可以随时走（孤儿生成）、provider 可以中途死（200 后错误）、网络可以随时断（重连重启）。

### 故事

孤儿生成的经济账刺眼：用户按停止，模型继续生成到 token 上限——为没人读的输出付费；而 provider 只在最后 chunk 报用量，中止的流连「花了多少」都不报——要按请求计费就得自己数转发的 token。修法分两档：连接绑定的就地取消（`request.is_disconnected` + `stream.close`），或干脆改 job-bound——生成任务与连接解耦，Redis Stream 存 chunk、Last-Event-ID 支持断点恢复、第二个设备可附同一生成，停止按钮变成显式 cancel 调用。

### Aha 瞬间

**「谁拥有生成」是流式架构的第一设计决策——连接拥有它，你就继承了连接的一切脆弱性；任务拥有它，你就要自己补上取消语义。**判断标准四条：工具调用、副作用、分钟级时长、移动客户端——命中任何一条就该 job-bound。

## 发芽 03：会睡眠、会报错、会截断的假上游——一个下午的 fault-injection 基建

### 种子

七条测试清单（真实 ingress 对比 TTFT、90 秒静默存活、杀客户端确认取消、注入 50-token 后错误、强制截断、手机断网、四个指标）每一项都能自动化——前提是有一个「按命令睡眠、报错、截断」的假上游。

### 故事

为什么值得：六种故障没有一种出现在 happy-path demo 里——它们全部只在「真实 ingress+真实负载+真实网络」的组合下显形。fake upstream 相当于把生产环境的恶意条件装进一个可编程的测试夹具，让每个故障都有确定的复现脚本与预期行为（阻塞、升级、恢复）。这与本站 11-09 译文（绿测试套件要亲手弄红）是同一哲学的流式版：**守卫没见过触发就是猜测，测试没见过失败就是装饰。**

### Aha 瞬间

**为故障建可编程的假上游，是把「生产事故」提前编译成「测试用例」——这项基建的下午，是流式功能全生命周期里回报率最高的一个下午。**清单化的七条验证+四个指标，则把「这次没坏」从祈祷变成了可回归的断言。

<!-- SPROUT_END -->
