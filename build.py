#!/usr/bin/env python3
"""build.py — 把 articles.json 渲染成静态站 dist/（零依赖，stdlib only）"""
import html
import json
import pathlib
import urllib.parse

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "dist"

CSS = """body{font-family:-apple-system,'PingFang SC','Noto Sans SC',sans-serif;max-width:720px;margin:0 auto;padding:24px 16px;color:#1a1a1a;line-height:1.75;background:#fafaf8}
a{color:#0f6b5c}header{border-bottom:2px solid #0f6b5c;padding-bottom:12px;margin-bottom:24px}
header h1{margin:0 0 6px;font-size:1.5em}.desc{color:#555;font-size:.92em}
.card{background:#fff;border:1px solid #e5e2da;border-radius:10px;padding:18px 20px;margin:14px 0}
.card h2{margin:0 0 4px;font-size:1.15em}.meta{color:#777;font-size:.85em;margin-bottom:8px}
.zh-note{font-size:.8em;color:#a06a00;background:#fff7e6;border-radius:6px;padding:4px 10px;display:inline-block;margin-bottom:8px}
ul{padding-left:1.2em}li{margin:.5em 0}.who{color:#555;font-style:italic}
.srcbox{background:#f0ede6;border-radius:8px;padding:10px 14px;margin-top:16px;font-size:.9em}
article{background:#fff;border:1px solid #e5e2da;border-radius:10px;padding:26px 30px}
.back{font-size:.9em}footer{color:#999;font-size:.8em;margin-top:36px;text-align:center}"""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def article_page(a: dict, site: dict) -> str:
    slug = a["id"]
    lis = "".join(f"<li>{esc(p)}</li>" for p in a["points"])
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(a['zh_title'])} · Medium 编辑精选导读</title><style>{CSS}</style></head><body>
<p class="back"><a href="./index.html">← 返回目录</a></p>
<article>
<h1>{esc(a['zh_title'])}</h1>
<div class="meta">{esc(a['date'])} · {esc(a['topic'])}</div>
<span class="zh-note">中文导读（要点提炼），非原文翻译</span>
<ul>{lis}</ul>
<p class="who">适合读者：{esc(a['who'])}</p>
<div class="srcbox">原文：<a href="{esc(a['source_url'])}" rel="nofollow noopener" target="_blank">{esc(a['source_title'])}</a><br>
作者：{esc(a['author'])} · 发表于 Medium。本页为中文导读与要点提炼，版权归原作者所有。</div>
</article>
<footer>Medium 编辑精选 · 中文导读站</footer></body></html>"""


def main() -> None:
    data = json.loads((ROOT / "articles.json").read_text())
    site, articles = data["site"], sorted(data["articles"], key=lambda a: a["date"], reverse=True)
    (DIST / "articles").mkdir(parents=True, exist_ok=True)
    cards = []
    for a in articles:
        p = DIST / "articles" / f"{a['id']}.html"
        p.write_text(article_page(a, site))
        cards.append(
            f'<div class="card"><h2><a href="./articles/{a["id"]}.html">{esc(a["zh_title"])}</a></h2>'
            f'<div class="meta">{esc(a["date"])} · {esc(a["topic"])} · 原文：{esc(a["author"])}</div>'
            f'<div class="zh-note">导读</div><p>{esc(a["points"][0][:120])}…</p></div>'
        )
    (DIST / "index.html").write_text(f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(site['title'])}</title><style>{CSS}</style></head><body>
<header><h1>{esc(site['title'])}</h1><div class="desc">{esc(site['description'])}</div></header>
{"".join(cards)}
<footer>本站为个人学习用途的中文导读聚合，非原文翻译；所有文章版权归原作者与 Medium 所有，请通过原文链接阅读完整内容。</footer>
</body></html>""")
    (DIST / "articles.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    n = len(articles)
    print(f"构建完成：dist/ （index + {n} 篇文章页）")


if __name__ == "__main__":
    main()
