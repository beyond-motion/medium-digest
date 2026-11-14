---
title: 'Cisco CodeGuard: Security Rules for AI Coding Agents'
slug: 2026-11-14-cisco-codeguard-security-rules
author: 'Abhishek Kanwar'
date: '2026-11-14T09:00:00+08:00'
source_url: 'https://medium.com/@abhics.blr/cisco-codeguard-security-rules-for-ai-coding-agents-dc284bcc4660'
status: processed
image: covers/2026-11-14-cisco-codeguard-security-rules.svg
excerpt: >-
  Cisco 开源、已捐 CoSAI（Google/Anthropic/OpenAI/NVIDIA/Microsoft 维护）的 CodeGuard：23 条 markdown 安全规则写一次、翻译器分发到 Cursor/Copilot/Claude Code/Codex，在规划/生成/审查三个时点进入 agent 上下文——扫描器告诉你第 3 行有问题，规则告诉 agent 正确的模式是什么。
---

<!-- REWRITE_START -->

# Cisco CodeGuard：给 AI 编码智能体的安全规则

> 原文：[Cisco CodeGuard: Security Rules for AI Coding Agents](https://medium.com/@abhics.blr/cisco-codeguard-security-rules-for-ai-coding-agents-dc284bcc4660) — Abhishek Kanwar

---

CodeGuard 是一套免费开源的安全规则，直接放进你的项目里。你的 AI 编码 agent 在计划、编写和审查代码时都会读到它们——**于是安全的模式成为它伸手够到的第一个模式**。

AI 编码 agent 以极快的速度写大量代码，并且反复犯同样的安全错误。Cisco 列出的常见项：不安全的默认值、缺失的输入校验、硬编码的密钥、过时的密码学、寿命终结的依赖。扫描器可以在事后抓到其中一些，但那时代码已经写完，得有人回头返工。

Project CodeGuard 走的是另一条路：**在 agent 动手之前把规则告诉它。**Cisco 于 2025 年 10 月 16 日将其开源，并于 2026 年 2 月 9 日捐赠给 Coalition for Secure AI（CoSAI）。CoSAI 现在负责维护，Google、Anthropic、OpenAI、NVIDIA 和 Microsoft 都是预期贡献的成员。

**它不是扫描器，也不是模型。**它是一个纯 markdown 规则库，外加把这些规则交付给你所用编码 agent 的工具链。本文讲这些规则做什么、它们如何帮 agent 发现并正确修复问题、以及如何在几分钟内装好。

## CodeGuard 给你什么

项目有三部分。

**规则。**23 条核心规则，markdown 编写，基于 OWASP、CWE 等既有指引。另有一组可选的 OWASP 系规则供更深入的审查。

**翻译器。**规则只写一次，然后被转换成每种 agent 期待的格式：Cursor 和 Windsurf 的规则文件、GitHub Copilot 的指令文件、Codex 等工具的 skills，以及 Claude Code 的插件。

**验证器。**在规则与 skills 发布前检查其格式良好的工具链。

规则覆盖八个领域。规则有两种加载方式：**always-on 规则**作用于所有文件、充当轻量基线；**scoped 规则**只在 agent 触碰匹配的语言或文件类型时加载——所以一条 Python 规则不会在 agent 编辑 Dockerfile 时占用它的上下文空间。

## 它如何帮 agent 发现问题并正确修复

没有指引的 agent 会写出它在训练数据里见得最多的模式——而那个模式经常是不安全的那个。CodeGuard 在 agent 工作的三个时点把规则送进上下文：

- **写之前：规划。**规则塑造设计。当 agent 计划一个登录功能时，它已经知道密码需要慢哈希、密钥属于环境变量——于是计划里就包含了这些。
- **写的时候：生成。**agent 一边写代码一边应用安全模式，绕开不安全的写法。**大多数问题在这一步被预防。**
- **写完之后：审查。**agent 用同一套规则检查代码，指名错在哪，并给出修正版本。几个语言包为此附带一个专职的审查 agent（codeguard-reviewer）。

**第三个时点是修复质量的关键。**扫描器告诉你第 3 行有问题；规则告诉 agent 正确的模式是什么——于是它做出正确的修改，而不只是把警告消音。

期望的差异大致如下（示意）。让 agent 存一个用户密码，没有规则时你可能得到：

```python
import hashlib

def store_password(user, password):
    user.password_hash = hashlib.md5(password.encode()).hexdigest()
```

加载了 CodeGuard，agent 被导向专用的密码哈希：

```python
from argon2 import PasswordHasher

ph = PasswordHasher()

def store_password(user, password):
    user.password_hash = ph.hash(password)
```

对第一个版本跑审查器，它应该标出 MD5 不适合用于密码，并改写成第二个。同样的道理适用于字符串拼接出来的 SQL（改写为参数化查询）和贴进源码的 API key（移到环境变量或密钥管理器）。

因为规则是仓库里的纯 markdown，你的团队可以阅读它们、评审对它们的改动、并添加自己的规则。仓库里还有一个 MCP server，供想把一套中央规则服务到每个开发者 agent 的团队使用。

## 怎么获取

一切都在 CoSAI 仓库的 releases 页。每个工具有自己的 zip，codeguard-all.zip 包含全部格式。

**Claude Code**：在 Claude Code 里跑三条命令：

```
/plugin marketplace add cosai-oasis/project-codeguard
/plugin install codeguard-security@project-codeguard
/reload-plugins
```

**其他工具**：下载你工具的 zip，解压，把一个文件夹拷进项目根目录，重启工具。比如 Cursor：

```
unzip codeguard-cursor.zip
cp -r .cursor/ /path/to/your/project/
```

这些文件夹以点开头，默认隐藏——macOS 上在 Finder 按 Cmd+Shift+. 显示。把文件夹提交进仓库，团队里每个人就拿到了同一套规则。

**验证它生效**：开一个新文件，向 agent 要一点安全敏感的东西：「创建一个哈希密码的函数」「写连接数据库的代码」「生成一个带认证的 API 端点」。你应该看到密码用 bcrypt 或 Argon2、数据库用参数化查询、端点有真实的认证与授权检查。如果没有，重启工具并确认文件夹在项目根目录。

每种工具的完整说明、以及从源码构建规则，见 getting started 指南。

## 它不会做的事

- **它不保证安全的代码。**Cisco 自己直说：规则把 agent 导向更安全的模式，但没有任何单一输出被保证安全。agent 仍可能忽略或误用一条规则。
- **它不替代你的扫描器。**项目自己的 FAQ 建议在既有安全扫描器旁边一起跑 CodeGuard。扫描器分析整个代码库，覆盖更广的问题面。
- **它不替代审查。**同行评审与常规安全工程实践仍然适用。CodeGuard 是防御的一层，不是全部。
- **只有 agent 真的加载了它才有效。**放错位置的文件夹什么也不做。装完后跑那三个测试 prompt。

## 为什么这件事重要

**预防比清理便宜。**agent 写代码之前读到的一条规则，每行成本为零；扫描报告里的一个发现，烧掉某人一下午。

**它与你已经在用的 agent 兼容。**规则与模型无关。你写一次或采纳一次，翻译器搞定 Cursor、Copilot、Claude Code 和其余工具。

**它现在是一个共享标准。**在 CoSAI 之下，规则集由跨行业的维护者在公开环境下维护，任何人都可以提议一条规则。

如果你的团队让 AI agent 写代码，给那个 agent一本安全规则手册，大概是目前能买到的最便宜的改进。几分钟，一个文件夹。

<!-- REWRITE_END -->

<!-- SPROUT_START -->

# 《Cisco CodeGuard: Security Rules for AI Coding Agents》的发芽报告

## 材料核心

CodeGuard（Cisco 2025-10-16 开源、2026-02-09 捐给 CoSAI——Google/Anthropic/OpenAI/NVIDIA/Microsoft 维护）是给 AI 编码 agent 的纯 markdown 安全规则库：23 条核心规则基于 OWASP/CWE，写一次经翻译器分发为 Cursor/Windsurf 规则文件、Copilot 指令文件、Codex skills、Claude Code 插件；另有验证器与中央 MCP server。加载分 always-on（全文件轻量基线）与 scoped（按语言加载，Python 规则不占编辑 Dockerfile 时的上下文）。在三个时点进入 agent 工作：规划（设计即含安全：慢哈希、密钥进环境变量）、生成（边写边用安全模式——预防大头）、审查（codeguard-reviewer 对照规则指名问题并给正确版本——比扫描器强在「告诉你正确模式」而非「告诉你第 3 行有问题」，规则让 agent 做正确的修改而不只是消音警告）。示例：MD5 密码哈希→Argon2；拼接 SQL→参数化；硬编码 key→环境变量。明确不做：不保证安全、不替代扫描器（FAQ 建议并行）、不替代 review、agent 不加载就无效（三测试 prompt 验证）。

## 发芽 01：规则库 vs 扫描器——「指名正确模式」与「指名错误行号」的差距

### 种子

扫描器告诉你第 3 行有问题；规则告诉 agent 正确的模式是什么——于是它做出正确的修改，而不只是把警告消音。

### 故事

这个差距在修复质量上具体化：MD5 存密码的例子，扫描器的输出是「MD5 不安全」的告警，开发者需要自己知道替代品（Argon2/bcrypt）及其迁移路径；而装了规则的 agent 在生成时就直奔 PasswordHasher，审查时又能引用规则说「为什么改、改成什么」。两段机制对应安全工作的两个成本中心——生成时防错（零边际成本）与事后返工（某人的一下午）。CodeGuard 的三时点设计（规划/生成/审查）把最大权重放在生成，正是这个成本结构的反映。

### Aha 瞬间

**给 agent 的安全左移不是「更早地扫描」而是「把正确模式预载进上下文」——扫描器是检测器，规则是先验；检测器回答「哪里坏了」，先验回答「一开始就该长什么样」，两者的成本差一个数量级。**

## 发芽 02：scoped 加载——规则库的上下文经济学

### 种子

always-on 规则做轻量基线，scoped 规则只在 agent 触碰匹配语言时加载——Python 规则不在 agent 编辑 Dockerfile 时占上下文。

### 故事

这个设计与本站 10-17 译文（context engineering 四招里的 reduce）是同一问题在安全领域的实例：上下文是稀缺资源，23 条全量常驻会稀释注意力，也会把 token 预算花在与当前任务无关的规则上。CodeGuard 的解法是把规则集当成「按需加载的模块」——与代码里的 lazy import 同构。这也解释了为什么规则用 markdown 而不是微调模型：规则可评审、可版本化、可按项目增删，模型的「安全倾向」却无法被团队本地编辑。

### Aha 瞬间

**给 agent 的规则集需要自己的一套「包管理」：基线常驻+按域懒加载+翻译器适配各 agent 的格式——安全规则正在变成一种新的依赖类型，npm 装的是代码的库，项目根目录那个点开头文件夹装的是行为的库。**

## 发芽 03：捐赠给 CoSAI——安全规则从公司实践到行业标准的路径

### 种子

Cisco 2025 年 10 月开源，2026 年 2 月捐给 CoSAI，Google、Anthropic、OpenAI、NVIDIA、Microsoft 成为预期贡献者——任何人都可以提议一条规则。

### 故事

这条路径与历史上安全标准的形成方式一致：单公司实践（Cisco 内部的 agent 安全规则）→ 开源工具 → 中立基金会托管（CoSAI）→ 行业共同维护。选择 markdown 规则而非专有格式是关键一步：规则透明可审（团队可以读、可以 diff、可以加自己的），翻译器层吸收各工具的格式差异——标准的本体是那 23 条规则，而不是任何一个 agent 的接入方式。对使用者的含义：采纳它的风险极低（一个文件夹），迁移成本为零（规则与模型无关），改进是行业分摊的（提议一条规则的门槛是提 PR）。

### Aha 瞬间

**当「如何安全地让 AI 写代码」成为全行业问题，答案的载体不会是某家模型的某个版本，而是一份模型无关、可版本化、行业共护的 markdown——行为规范正在像代码依赖一样被集中维护、按版本分发。**

<!-- SPROUT_END -->
