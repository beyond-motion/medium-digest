#!/usr/bin/env python3
"""build.py — 把 articles.json 渲染成静态站 docs/（GitHub Pages 源目录，零依赖）

文章页排版对齐 every.to 订阅站：单页双 H1——上半部分完整改写式翻译（保留原文
小标题结构），下半部分《原题》发芽报告（材料核心 + 发芽 01/02/03，种子/故事/Aha）。
"""
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "docs"

CSS = """body{font-family:-apple-system,'PingFang SC','Noto Sans SC',sans-serif;max-width:760px;margin:0 auto;padding:28px 16px;color:#1a1a1a;line-height:1.85;background:#fafaf8}
a{color:#0f6b5c}header{border-bottom:2px solid #0f6b5c;padding-bottom:12px;margin-bottom:24px}
header h1{margin:0 0 6px;font-size:1.45em}.desc{color:#555;font-size:.92em}
.card{background:#fff;border:1px solid #e5e2da;border-radius:10px;padding:18px 20px;margin:14px 0}
.card h2{margin:0 0 6px;font-size:1.12em}.meta{color:#777;font-size:.85em;margin-bottom:8px}
.badge{font-size:.78em;color:#0f6b5c;background:#e8f2f0;border-radius:6px;padding:2px 10px;margin-right:6px}
article{background:#fff;border:1px solid #e5e2da;border-radius:10px;padding:30px 34px;margin:16px 0}
article h1{font-size:1.3em;margin:.4em 0}article h2{font-size:1.15em;margin:1.4em 0 .5em;color:#0f4c42}
article h3{font-size:1.02em;margin:1.1em 0 .4em;color:#555}
.en-title{color:#888;font-size:1.05em !important;font-weight:600}
.sprout{background:#f7fbf6;border-color:#cfe3d5}
.sprout h1{color:#0f6b5c}
ul{padding-left:1.3em}li{margin:.45em 0}p{margin:.7em 0}
.srcbox{background:#f0ede6;border-radius:8px;padding:12px 16px;margin-top:22px;font-size:.9em}
.back{font-size:.9em}footer{color:#999;font-size:.8em;margin-top:36px;text-align:center}
.disclaimer{color:#a06a00;font-size:.82em}"""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def md2html(md: str) -> str:
    """极简 markdown：##/### 标题、- 列表、**加粗**、`代码`、段落。"""
    out, in_list = [], False
    for raw in md.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(line.strip()))
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        if line.startswith("### "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h3>{text[4:]}</h3>")
        elif line.startswith("## "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h2>{text[3:]}</h2>")
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{text[2:]}</li>")
        else:
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<p>{text}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def article_page(a: dict) -> str:
    src = (f'<div class="srcbox">原文：<a href="{esc(a["source_url"])}" rel="nofollow noopener" '
           f'target="_blank">{esc(a["en_title"])}</a><br>作者：{esc(a["author"])} · 发表于 Medium · '
           f'{esc(a["topic"])}<br><span class="disclaimer">本页为改写式中文翻译与 AI 发芽笔记，非官方译文；'
           f'内容版权归原作者所有，请通过原文链接阅读完整原文。</span></div>')
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(a['zh_title'])} · Medium 编辑精选</title><style>{CSS}</style></head><body>
<p class="back"><a href="./index.html">← 返回目录</a></p>
<article>
<h1 class="en-title">{esc(a['en_title'])}</h1>
<h1>{esc(a['zh_title'])}</h1>
{md2html(a['rewrite_md'])}
{src}
</article>
<article class="sprout">
<h1>《{esc(a['en_title'])}》的发芽报告</h1>
{md2html(a['sprout_md'])}
</article>
<footer>Medium 编辑精选 · 中文翻译与发芽</footer></body></html>"""


def main() -> None:
    data = json.loads((ROOT / "articles.json").read_text())
    site, articles = data["site"], sorted(data["articles"], key=lambda a: a["date"], reverse=True)
    (DIST / "articles").mkdir(parents=True, exist_ok=True)
    cards = []
    for a in articles:
        (DIST / "articles" / f"{a['id']}.html").write_text(article_page(a))
        first_p = next((ln.strip() for ln in a["rewrite_md"].split("\n") if len(ln.strip()) > 60 and not ln.startswith("#")), "")
        cards.append(
            f'<div class="card"><h2><a href="./articles/{a["id"]}.html">{esc(a["zh_title"])}</a></h2>'
            f'<div class="meta">{esc(a["date"])} · {esc(a["topic"])} · 原文：{esc(a["author"])}'
            f'<span class="badge">改写翻译</span><span class="badge">发芽笔记</span></div>'
            f'<p>{esc(first_p[:130])}…</p></div>'
        )
    (DIST / "index.html").write_text(f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(site['title'])}</title><style>{CSS}</style></head><body>
<header><h1>{esc(site['title'])}</h1><div class="desc">{esc(site['description'])}</div></header>
{"".join(cards)}
<footer>本站为个人学习用途；所有文章版权归原作者与原发布平台所有，请通过原文链接阅读完整内容。</footer>
</body></html>""")
    (DIST / "articles.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"构建完成：docs/ （index + {len(articles)} 篇文章页，每页含改写翻译与发芽报告）")


if __name__ == "__main__":
    main()
