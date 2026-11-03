---
title: 'Advanced RAG: Layout Analysis for Document Ingestion'
slug: 2026-11-03-advanced-rag-layout-analysis
author: 'Okan Yenigün'
date: '2026-11-03T09:00:00+08:00'
status: processed
source_url: 'https://medium.com/python-in-plain-english/advanced-rag-layout-analysis-for-document-ingestion-5bbf8bf560de'
image: covers/2026-11-03-advanced-rag-layout-analysis.svg
excerpt: >-
  文档不只是词序列——价格属于行、图注属于图旁、同高度的两段可能在不同的栏：用 Raggae SDK 的版式分析 worker 在摄入阶段保住结构，让文本按文本读、表格按表格读、图像按图像读。
---

<!-- REWRITE_START -->

# 高级 RAG：面向文档摄入的版式分析

> 原文：[Advanced RAG: Layout Analysis for Document Ingestion](https://medium.com/python-in-plain-english/advanced-rag-layout-analysis-for-document-ingestion-5bbf8bf560de) — Okan Yenigün

---

文档不只是词的序列。**一个价格属于某一行，一个图注属于某幅图旁边，同一高度的两段话可能分属不同的栏。**

人们几乎不假思索地使用这些线索。而把整个文档压成一个字符串的管道，会在创建第一个 chunk 之前就把它们丢光。

想象你问一个 RAG 系统：「我们在运费标签上花了多少钱？」文档里有答案。但如果摄入过程把价格和品名分了家，检索到正确的页面也可能给模型送错证据。

**版式分析（layout analysis）识别文档的组成部分以及它们各自属于哪里。**在 RAG 管道里，这张地图帮助后续的读取器分别处理段落、表格和图像，然后组装有用的上下文——而不是只依赖字节碰巧被存储的顺序。

本文覆盖从定位表格与插图、建议阅读顺序到识别重复页眉的各类版式分析场景，使用 **Raggae**——一个带独立文档处理 worker 的 Python SDK：

```bash
pip install raggae
```

## 混合了双栏、表格与插图的 PDF

一份文档可能以各种排布混搭段落、表格、插图与图注：正文走双栏、一张表横跨两栏、下一页是一幅图表。把它拍平成一个字符串会同时制造多个问题：两栏互相交错、表格数值失去表头、图表彻底消失。把所有内容同时送给文本读取器和表格读取器，还可能让表格内容被重复提取。

示例 `complex-report.pdf` 是一份两页报告：第 1 页在双栏与一张宽表之间切换，第 2 页是图表、图注与后续正文。

`NativePdfLayoutAnalyzer` 检查 PDF 存储的字符、表格线与栅格图位置：把文本聚成候选块、定位带线的表格、记录图表图像的位置。

```python
from raggae.documents.layout_analysis import NativePdfLayoutAnalyzer

pdf_worker = NativePdfLayoutAnalyzer()
from collections import Counter

pdf_layout = pdf_worker.analyze("complex-report.pdf")

print(pdf_layout.outcome)
print("pages:", len(pdf_layout.surfaces))
print("regions:", dict(Counter(region.kind for region in pdf_layout.regions)))
for region in pdf_layout.regions:
    if region.kind in ("table", "image"):
        print(region.id, region.kind, region.bbox)
```

输出：

```
success
pages: 2
regions: {'text': 22, 'table': 1, 'image': 1}
page-1-r8 table (48.0, 312.0, 564.0, 420.0)
page-2-r5 image (48.0, 180.0, 564.0, 402.0)
```

这个结果给了后续读取器具体的工作位置：文本块、一个表格区、一个图片区。**表格的单元格文本被排除在普通文本区域之外**——避免同一段内容经两条路径被重复提取。

想在原始页面上查看这些区域，用 Raggae 的 `DocumentRegionRenderer`：它为每页准备一张 Pillow 图像并把返回的框画上去，本身不显示任何东西（PDF 渲染需要 `pip install 'raggae[layout-visual]'`）。Jupyter 里用 `display` 展示；其他应用可以先 `preview.save("page.png")` 再关闭。返回的框：蓝色是文本、绿色是表格、橙色是图像。每个区域保留自己的类型与位置，让对应的读取器有明确的检查点。

## 下一个区域是谁？

框告诉我们内容在哪，没告诉我们怎么穿行。这份报告还需要一条穿过双栏、宽表、下一页插图的**建议阅读顺序**。

`GeometricReadingOrderResolver` 接收已有的版式结果，寻找矩形之间的空隙，返回「先读这个区域、后读那个」的链接——**不重新读 PDF**：

```python
from raggae.documents.layout_analysis import GeometricReadingOrderResolver

resolver = GeometricReadingOrderResolver()
order = resolver.resolve_order(pdf_layout, direction="ltr")
print(order.outcome, "links:", len(order.edges))
print("unresolved:", len(order.unresolved_region_ids))
for edge in order.edges:
    if edge.before_region_id in ("page-1-r8", "page-2-r5"):
        print(edge.before_region_id, "->", edge.after_region_id, edge.basis)
```

```
success links: 23
unresolved: 0
page-1-r8 -> page-1-r9 horizontal_gap
page-2-r5 -> page-2-r6 horizontal_gap
```

比如图像 `page-2-r5` 排在旁边的文本 `page-2-r6` 之前；`horizontal_gap` 记录了这条建议的几何证据。**这是一条排序链接，不是「该文本是图像图注」的断言。**再用 `DocumentReadingOrderRenderer` 把链接画出来：箭头是前后链接，数字是页内建议顺序。图像与旁边的文本仍是独立区域，只有一条显式链接——后续组装步骤可以在排布提取内容时使用它们。

## 常见的 PDF 版式模式

- **普通段落之间的购物表**：`Shipping labels / 600 / $90` 在导语与交货说明之间的一张带线表格里。表格应保持整体、不吞并周围散文——表格读取器可以一起检查品名、数量、金额三列。
- **全宽导语下的三栏**：页面以横贯全宽的导语开头，中间三段团队更新，结尾共享的总结。**只因出现在同一高度就拼接行，会把三段更新搅在一起**——Raggae 按栏内分组而非跨页合并，导语与总结各留自己的区域。
- **旋转页**：页面以横向显示，底层 PDF 页却以纵向存储——内容位置需要跟随显示旋转。Raggae 计入旋转，返回与显示出的文本和表格对齐的框。
- **两幅插图各带图注**：两幅嵌入图表各有旁边的说明。图片要有独立位置，图像读取器才能分别处理，文本读取器处理标签。

## 地图里到底装了什么？

所有发现类 worker 返回 `LayoutAnalysisResult`：

- **surfaces**：承载内容的地方——PDF 页、幻灯片、工作表、图像帧，或连续文档体。
- **regions**：找到的碎片，各带 ID、类型与在原文件中的位置。
- **bbox**：有物理坐标时的矩形：left、top、right、bottom。PDF 矩形用「点」，从显示页左上起算；图像矩形用像素。**未渲染的 Word 文档或工作表则用结构位置——编造页坐标会产生误导。**
- **findings**：对覆盖缺失、限制或问题的说明。

地图里既没有最终段落文本，也没有提取出的图像文件。Region ID 只是标识碎片，**其编号不构成阅读顺序**。保留原始来源与地图并存，后续读取器才能解析那些位置。

## 表格里嵌图的 Word 报告

采购报告可能混搭标题、说明段落、成本表，以及一张既含嵌套表又含图片的引用表。只读文档顶层段落会漏内容；把每个单元格段落递归当正文又会导致重复。

`receiving-report.docx`：第 1 页是普通段落间的采购表；第 2 页是引用表——左边嵌套表、右边嵌入图片。Word 以真实元素存储这些，所以 `DocxLayoutAnalyzer` 不需要从像素猜角色：

```python
analyzer = DocxLayoutAnalyzer()
word_layout = analyzer.analyze("receiving-report.docx")
print(word_layout.outcome)
print(dict(Counter(region.kind for region in word_layout.regions)))
for region in word_layout.regions:
    if region.kind in ("table", "image"):
        print(region.id, region.kind, region.location.child_indexes)
```

```
success
{'heading': 2, 'text': 3, 'table': 2, 'image': 1}
body-r3 table (2,)
body-r6 table (6,)
body-r7 image (6, 2, 1, 2, 0, 0)
```

两个顶层表保持为单表区域——单元格段落与嵌套表不再被复制成独立的 body 区域；嵌入图片在第二张表内部获得精确位置。元素路径如 `(2,)` 意为「第三个 body 元素」，图像的长路径则穿过表内多层子元素。每个位置还标注内部文档部件（这里是 `word/document.xml`），另一个读取器能在同一文件里找到同一元素。

其他 Word 场景：**自定义标题样式的员工手册**——内建标题及继承样式都归为 heading，为后续 chunk 组装保留章节边界；**含图片的引用表**——表与嵌入图各保留精确位置；**重复措辞的报告**——元素路径直接定位原始段落或表格，无需按文本搜索选对实例。

## 形状不等于阅读顺序的演示文稿

一份货运简报幻灯片有标题、导语、库存表、图片、下方注释。只提取文本会丢掉图片和表格结构；而按存储的形状列表走有另一种风险——**它描述的是堆叠顺序，不一定是演讲者想要的顺序**。

`PptxLayoutAnalyzer` 同时返回源形状位置与各幻灯片上的位置：

```python
analyzer = PptxLayoutAnalyzer()
slide_layout = analyzer.analyze("shipment-briefing.pptx")
print(slide_layout.outcome)
print("slides:", len(slide_layout.surfaces))
print(dict(Counter(region.kind for region in slide_layout.regions)))
for region in slide_layout.regions:
    if region.kind in ("table", "image"):
        print(region.id, region.kind, region.bbox)
```

```
success
slides: 2
{'heading': 1, 'text': 4, 'table': 1, 'image': 1}
slide-1-s2 table (40.0, 200.0, 340.0, 340.0)
slide-1-s3 image (400.0, 200.0, 580.0, 320.0)
```

表格与图片有了各自的位置；每个区域还标识原始 slide 部件与形状路径——`(3, 1)` 意为第四个形状（一个组）内的第二个子元素。框是从幻灯片左上起量的形状矩形；阅读顺序建议与这些源位置分开保存。

其他演示场景：**分组、缩放、镜像的图表**——子元素存相对组坐标，worker 应用组变换（含嵌套组）后返回幻灯片坐标，返回叶区域而非重叠的组容器；**后创建却位于上方的文本框**——几何解析器按实际位置建议「上先于下」，而非按创建顺序；**跨多张幻灯片的简报**——每张幻灯片有自己的 surface 与形状位置。

## 有多个独立内容区的工作簿

仓库工作簿的同一张表上可能并存库存表、独立的成本块和一个合并标签。把整个 used 范围当一张表读，会把它们连同中间的空列搅在一起。

`stock-and-costs.xlsx` 的 Warehouse 表：左库存、右成本、下方合并的发货标签；第二张表有填满的网格与两个对角标签。

```python
analyzer = XlsxLayoutAnalyzer()
sheet_layout = analyzer.analyze("stock-and-costs.xlsx")
print(sheet_layout.outcome)
print(dict(Counter(region.kind for region in sheet_layout.regions)))
for region in sheet_layout.regions:
    print(region.kind, region.location.sheet_name, region.location.cell_range)
```

```
success
{'table': 1, 'unknown': 5}
table Warehouse A1:B4
unknown Warehouse A7:D7
unknown Warehouse F2:G4
unknown No declared table A1:B3
unknown No declared table F1
unknown No declared table G2
```

声明的表保留 table 角色；其他占用的区域得到 `unknown` 类型与精确范围，留给后续读取器检查。有用的正是**分离**：成本与库存分开、合并标签只出现一次、对角标签保持两个独立区域。每个位置都标注工作表名——不同表上的相同单元格地址不会混淆。

其他电子表格场景：**钉在 E6 的徽标**——图像获得含工作表、图像序号、锚点单元格的 drawing 位置；**A1 是 0、Excel 的 last cell 是 False**——稀疏示例只返回两个占区，不扫中间每个单元格，两者都算内容、纯格式单元格忽略；**含空表的工作簿**——空表保留自己的 surface，不引入空内容区域。

工作表的位置是单元格范围与绘图引用，而非页面矩形。

## 结构已经写好的网页文章

存档的网页报告可能已经用 HTML 标签区分了标题、段落、库存表和图注。**把标签全部剥掉，等于在读取器使用证据之前先扔掉证据。**

`HtmlLayoutAnalyzer` 不抓图、不执行页面，直接定位元素：

```python
analyzer = HtmlLayoutAnalyzer()
html_layout = analyzer.analyze("warehouse-report.html")
print(html_layout.outcome)
for region in html_layout.regions:
    print(region.kind, region.location.tag, region.location.child_indexes)
```

```
success
heading h1 (0, 1, 0, 0)
text p (0, 1, 0, 1)
heading h2 (0, 1, 0, 2, 0)
table table (0, 1, 0, 2, 1)
image img (0, 1, 0, 3, 0)
caption figcaption (0, 1, 0, 3, 1)
text p (0, 1, 0, 4)
```

表格连同自己的 caption 留在同一个 table 区域内；插图的 `figcaption` 独立出来，留给关系分析。元素路径从解析后的文档根起数子元素——不是屏幕坐标。后续读取器解析表格元素即可，不必重新搜索整页。

其他 HTML 场景：多级标题的文章（标题标签保留主标题与节标题之别）；含段落与图片的表格（表格作为整体区域，嵌入图像元素另保位置）；HTML 片段（可直接分析，路径仍从解析根起算）。

## 整页大图的扫描件报告

扫描 PDF 看起来可能与数字报告一模一样——但里面段落、表格、图表全是一张图里的像素。原生分析器没有存储的文本框或表格线可恢复。

OCR 能把像素变成词，但我们还需要判断哪个区域该给表格读取器、哪块是图表——**这是视觉版式问题，不只是文字识别问题。**

`scanned-report.pdf` 第 1 页是原生 PDF 内容，第 2 页把类似报告存成整页图。`VisualLayoutAnalyzer` 渲染 PDF 页或打开图像文件，把像素发送到**显式选择的本地检测服务**。可选后端有两种：Paddle 的版式检测器与 Docling 的 Heron 模型——两个上游项目都把版式检测描述为「定位并分类文档区域」，与其更完整的文档处理流水线是两回事。

```bash
pip install 'raggae[layout-visual,layout-docling]'
# 或者： pip install 'raggae[layout-visual,layout-paddle]'
```

模型权重需另外从模型仓库下载；`RAGGAE_DOCLING_MODEL_DIR` 必须指向已存在的本地 Heron 模型文件夹——构造服务不是下载步骤。文档推理在本地运行。

```python
import os
from raggae.documents.layout_analysis import (
    DoclingLayoutService, VisualLayoutAnalyzer,
)

service = DoclingLayoutService(
    model_path=Path(os.environ["RAGGAE_DOCLING_MODEL_DIR"]),
    device="cpu",
)
visual_worker = VisualLayoutAnalyzer(service=service)
scan_pdf = Path("scanned-report.pdf")
visual_layout = visual_worker.analyze(scan_pdf)
print(visual_layout.outcome)
for surface in visual_layout.surfaces:
    kinds = Counter(
        region.kind for region in visual_layout.regions
        if region.surface_id == surface.id_
    )
    print(surface.id_, dict(kinds))
```

```
success
page-1 {'table': 1, 'text': 5, 'image': 1, 'caption': 1, 'heading': 1}
page-2 {'text': 5, 'table': 1, 'image': 1, 'caption': 1, 'heading': 1}
```

现在每页都有候选的文本、表格、图片区域——即便其中一页完全没有原生文本。改用 Paddle 时，**换的是注入的服务，不是 worker 接口**：

```python
from raggae.documents.layout_analysis import PaddleLayoutService

paddle_service = PaddleLayoutService(
    model_path=Path(os.environ["RAGGAE_PADDLE_MODEL_DIR"]),
    device="cpu",
)
paddle_layout = VisualLayoutAnalyzer(service=paddle_service).analyze(scan_pdf)
```

worker 接口与结果 schema 在更换服务时保持不变——应用可以复用同一批下游读取器与渲染器，自由选择本地检测后端。

其他视觉分析场景：**以 PNG 提供的收据或报告**——同一个 worker 直接分析，不必把图包进 PDF；**多帧 TIFF 或原生/扫描混合 PDF**——帧与页逐一检查；视觉分析是原生发现的**替代**，不是每个 PDF 都必须跑的自动二过；**可复用的本地检测服务**——创建一次、传给后续调用，把模型初始化与单个文档处理分开。

## 被拼成一段破碎对话的双栏

找到每个文本块还不够。研究文章可能先走完左栏再走右栏；**只按高度排序块，会在左右栏之间来回跳跃。**几何可以帮忙：空的竖直条带暗示分栏；水平间隙可以分隔标题与正文。`GeometricReadingOrderResolver` 把这些规则应用到已有地图，返回前后建议，不重开文档。

其他排序场景：**后创建却位于下方的框**——解析器按实际位置建议「上→下」（`slide-2-s1 -> slide-2-s0`），与创建时间无关；**从右到左的栏**——`direction="rtl"` 显式选择遍历方向（这是文档的版式约定）；**文本区之间的宽表**——表在建议序列中保持单区域，单元格不与周围段落交错；**跨多页的文档**——页序链接连接有内容的 surface，让组装跨页边界延续。

## 每个 chunk 里都重复标题的手册

100 页的手册可能每页都印公司名、内部使用告示和页码。这些碎片如果持续进入提取的正文，会占用 chunk 空间、打断有用的段落。

**删除所有重复句不是安全的替代**——「Always record the shipment ID」可能是刻意在多个章节重复的重要指令。

`handbook.pdf`：两页不同的节标题、重复的手册页眉、内部使用页脚、变化的页码、两页中部相同的提醒。我们要同时区分**重复**与**位置**：

```python
from raggae.documents.layout_analysis import PdfRepeatedMarginDetector

analyzer = NativePdfLayoutAnalyzer()
handbook_pdf = Path("handbook.pdf")
handbook_layout = analyzer.analyze(handbook_pdf)
margins = PdfRepeatedMarginDetector().detect(handbook_layout, handbook_pdf)
for group in margins.groups:
    print(group.kind, group.basis, len(group.region_ids))
```

```
header repeated_text 2
footer repeated_text 2
footer page_number 2
```

这个 worker 从创建地图的同一 PDF 读取原生文本短样本，跨页比较文本与相对位置（含受支持的变化页码模式）。候选组与原内容保持独立——后续组装步骤可以把重复的「页面家具」从正文剔除、留作元数据、或显式标注。

其他场景：**变化的页码与变化的发票号**——`Page 1 of 2`/`Page 2 of 2` 成组，`Invoice 1001`/`Invoice 1002` 不成组——worker 不会为了凑匹配抹掉每个变化数字；重复的 `Release 2026` 标签仍可作为普通文本匹配；**正文内部的重复提醒**——位于中部使其不入页眉/页脚组，重复+位置共同把它与页面家具区分开；**不同页面尺寸下位置一致的页眉**——位置按各页尺寸的相对值比较，而非假定每页同尺寸。

## 需要与说明待在一起的图

图表画着四根柱子，紧下方的文字解释它们代表什么，更远处还有一段讨论别的话题的文字。把近旁的标签与图关联，能给后续内容组装有用的上下文。

`caption-report.pdf`：第 1 页图表配下方短标签，第 2 页表格配上方标签。`RuleBasedRegionRelationshipDetector` 接收已有版式结果，用邻近度（proximity）与对齐（alignment）提议 caption 链接，用结构路径或包围矩形建立 containment 链接：

```python
caption_layout = pdf_worker.analyze("caption-report.pdf")
relationship_worker = RuleBasedRegionRelationshipDetector()
links = relationship_worker.detect(caption_layout)

print(links.outcome)

for link in links.relationships:
    print(link.kind, link.source_region_id, "->", link.target_region_id, link.basis)
```

```
success
caption_candidate page-1-r5 -> page-1-r4 proximity
caption_candidate page-2-r4 -> page-2-r5 proximity
```

每个近旁的标签都与对应目标连上——不管标签在上方还是下方。结果记录 proximity 作为证据，给后续组装一个具体的图注候选。

## 把有用的部分一起跑

前文为看清职责拆开了 worker。正常摄入调用不必重复这些接线。`DocumentLayoutAnalyzer` 选择发现 worker，然后运行适用于该地图的启用分析：

```python
from raggae.documents.layout_analysis import DocumentLayoutAnalyzer

report = DocumentLayoutAnalyzer().analyze(handbook_pdf)
print(report.outcome)
print("regions:", len(report.layout.regions))
print("margin groups:", len(report.repeated_margins.groups))
```

```
success
regions: 16
margin groups: 3
```

报告把原始版式与 `reading_order`、`relationships`、`repeated_margins` 并存。这些分析**独立检查同一张地图**：检测到页眉并不会在顺序解析前悄悄移除它。默认按扩展名路由 PDF、DOCX、PPTX、XLSX、HTML；原始字节用 `source_format="pdf"` 显式选择。只要内容位置？关掉附加任务：

```python
discovery_only = DocumentLayoutAnalyzer().analyze(
    handbook_pdf,
    reading_order=False,
    relationships=False,
    repeated_margins=False,
)
```

图像配 `visual_service=service`；要用视觉发现处理扫描 PDF，直接注入 `DocumentLayoutAnalyzer(analyzer=VisualLayoutAnalyzer(service=service))`。

## 结语

版式分析保留了纯文本无法表达的信息：**表格的边界、段落在页上的位置、形状在幻灯片上的位置、图注的可能目标。**这给后续读取器更好的起点——文本按文本读、表格按表格读、图像按图像读，同时带着足够的位置信息把内容重新拼回一起。

下一阶段提取内容、利用版式链接组装、并把相关上下文带入可检索的 chunk。**先定位证据，再提取，再用语义决定它们如何归属。**当摄入没有先丢弃那些让内容可被理解的结构时，RAG 系统才有更好的机会从正确的证据出发作答。

（本文是作者的 Advanced RAG 系列 continuation；同系列另有《The Copy Before the Reader》《The Gate Before the Parser》。）

<!-- REWRITE_END -->

<!-- SPROUT_START -->

# 《Advanced RAG: Layout Analysis for Document Ingestion》的发芽报告

## 材料核心

RAG 系统答错的原因常常不在检索，而在摄入阶段已经把结构丢掉：整篇文档压成字符串时，价格与品名分家、双栏交错、表格失表头、图表消失。版式分析（layout analysis）为文档建一张「什么在哪」的地图——surfaces（页/幻灯片/工作表/帧）、regions（带 ID/类型/位置的碎片）、bbox（有物理坐标才给页坐标，结构文档给元素路径）、findings（限制说明）——让后续读取器按类型分工（文本按文本读、表格按表格读、图像按图像读）。配套四件套：几何阅读顺序（矩形间隙→前后链接，不重读文档）、重复页眉检测（重复+位置双判据，不误删正文刻意重复）、图注关系（proximity+alignment 证据）、统一入口 DocumentLayoutAnalyzer（同一地图独立分析，检测页眉不偷偷移除）。

## 发芽 01：「先丢结构再检索」是 RAG 答错题的隐形第一因

### 种子

「运费标签花了多少钱」的答案就在文档里，检索也命中了正确的页——但摄入时价格已与品名分家，模型拿到的是错误证据。失败发生在建第一个 chunk 之前。

### 故事

人类读者几乎不假思索地使用版式线索（价格属于行、图注属于图、同高度分属两栏），而「压成字符串」这一步恰恰是把人类最依赖的证据系统化丢弃。文中的修复顺序值得记住：先定位证据（版式地图）→再提取→再用语义决定归属——而不是先全文提取再指望模型自己理清。

### Aha 瞬间

**RAG 的质量上限在摄入时刻就已经确定，检索与生成只是在花这笔遗产。**「检索对了答案却错了」这类故障，第一嫌疑人是管道早先把证据的结构破坏了。

## 发芽 02：位置的语义——为什么「编造页坐标」比没有坐标更糟

### 种子

bbox 只在物理坐标存在时给出（PDF 用点、图像用像素）；未渲染的 Word 与工作表改用结构位置（元素路径、单元格范围）。原文的警告：给结构文档编造页坐标会产生误导。

### 故事

坐标不是格式细节，是「证据在什么坐标系里可复现」的承诺：PDF 的点坐标让渲染器能画框验证；Word 的 `(6,2,1,2,0,0)` 元素路径让另一个读取器在同一 `word/document.xml` 里找到同一元素；Excel 的位置带工作表名，不同表的相同地址不混淆。扫描件没有原生坐标，就诚实地说「这是像素」并交给视觉模型预测——每种文档类型用它真实拥有的定位方式，不假装统一。

### Aha 瞬间

**元数据的第一美德不是齐全，而是诚实——错误的定位信息比缺失更危险。**任何「给所有东西套同一种坐标」的便利设计，都在制造看起来可用、实则无法复现的证据引用。

## 发芽 03：重复+位置双判据——自动化清理里「证据足够」的样板

### 种子

删掉所有重复句子不是安全替代：「Always record the shipment ID」可能是刻意重复的重要指令。页眉页脚检测器同时要求「文本重复」与「位于边距带」两个证据，变化的页码（Page 1 of 2 / Page 2 of 2）按模式成组，而变化的发票号（Invoice 1001/1002）不凑数。

### 故事

候选组与原内容保持独立——检测到页眉并不会在后续分析前被悄悄移除；组装步骤自己决定剔除、留作元数据、还是显式标注。整个设计把「识别」与「处置」分成两层，处置永远留给带着完整语境的下游。

### Aha 瞬间

**自动化清理的安全边界 = 证据标准的严格度 + 决策权的分离度。**「我发现了模式」永远不等于「我授权了删除」——把判据讲清楚（重复且在边距带）、把处置权留给下游，是所有内容清洗系统该抄的作业。

<!-- SPROUT_END -->
