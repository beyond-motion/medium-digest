#!/usr/bin/env python3
"""gen_cover.py — 为文章生成品牌化 SVG 封面（与站点设计系统同款）

用法：python3 scripts/gen_cover.py <slug> "<中文标题>" [作者] [日期]
输出：public/covers/<slug>.svg
"""
import html
import pathlib
import sys
import textwrap

ROOT = pathlib.Path(__file__).resolve().parent.parent

W, H = 1200, 675
BG = "#f6f4ef"
SURFACE = "#fffdfa"
INK = "#20201d"
ACCENT = "#0f6b5c"
MUTED = "#8a8578"


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def wrap_zh(text: str, width: int = 15, max_lines: int = 3) -> list[str]:
    """中文按字符换行（中英混排时英文单词不拆断）。"""
    lines, current, cur_len = [], [], 0
    for word in text.replace("：", "： ").split(" "):
        seg = word
        while len(seg) + cur_len > width:
            take = max(1, width - cur_len)
            current.append(seg[:take])
            seg = seg[take:]
            lines.append("".join(current))
            current, cur_len = [], 0
        current.append(seg)
        cur_len += len(seg)
        while cur_len >= width:
            overflow = current.pop()
            lines.append("".join(current))
            current, cur_len = [overflow[:width]], len(overflow[:width])
            rest = overflow[width:]
            if rest:
                current, cur_len = [rest], len(rest)
            break
    if current:
        lines.append("".join(current))
    return lines[:max_lines]


def main() -> int:
    slug = sys.argv[1]
    title = sys.argv[2]
    author = sys.argv[3] if len(sys.argv) > 3 else ""
    date = sys.argv[4] if len(sys.argv) > 4 else ""

    lines = wrap_zh(title)
    size = 64 if max(len(l) for l in lines) <= 12 else 52
    line_h = int(size * 1.42)
    block_h = line_h * len(lines)
    y0 = (H - block_h) // 2 + int(size * 0.2)

    tspans = "\n".join(
        f'    <text x="90" y="{y0 + i * line_h}" font-size="{size}" font-weight="700" fill="{INK}">{esc(l)}</text>'
        for i, l in enumerate(lines)
    )
    meta = " · ".join(x for x in [author, date] if x)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <rect x="0" y="0" width="14" height="{H}" fill="{ACCENT}"/>
  <g font-family="-apple-system, 'PingFang SC', 'Noto Sans SC', sans-serif">
    <rect x="90" y="64" width="56" height="56" rx="12" fill="{INK}"/>
    <text x="118" y="102" font-size="30" font-weight="800" fill="{SURFACE}" text-anchor="middle">M</text>
    <text x="164" y="102" font-size="22" font-weight="600" fill="{MUTED}">Medium 编辑精选 · 中文翻译与发芽</text>
{tspans}
    <text x="90" y="{H - 72}" font-size="24" fill="{MUTED}">{esc(meta)}</text>
    <text x="90" y="{H - 36}" font-size="20" fill="{ACCENT}">改写式翻译 · 发芽笔记</text>
  </g>
</svg>
"""
    out = ROOT / "public" / "covers" / f"{slug}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)
    print(f"封面已生成：public/covers/{slug}.svg（{len(lines)} 行标题）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
