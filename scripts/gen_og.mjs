// 批量把 public/covers/*.svg 转成 og:image 可用的 .png（社交爬虫不认 SVG）。
// 输出统一裁成 og 黄金比例 1200x630（原 SVG 1200x675，上下各裁 22.5px，版式无伤）。
// 增量：目标 PNG 比 SVG 新则跳过。另外生成一张首页用的全站卡 og-site.png。
import fs from "node:fs";
import path from "node:path";
import { Resvg } from "@resvg/resvg-js";

const ROOT = path.resolve(process.cwd());
const COVERS = path.join(ROOT, "public", "covers");

const SITE_CARD_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
  <rect width="1200" height="675" fill="#f6f4ef"/>
  <rect x="0" y="0" width="14" height="675" fill="#0f6b5c"/>
  <text x="80" y="300" font-family="-apple-system, 'PingFang SC', 'Noto Sans SC', sans-serif" font-size="64" font-weight="700" fill="#1a1a1a">Medium 编辑精选</text>
  <text x="80" y="386" font-family="-apple-system, 'PingFang SC', 'Noto Sans SC', sans-serif" font-size="40" fill="#555555">中文翻译与发芽</text>
  <rect x="80" y="440" width="72" height="6" fill="#0f6b5c"/>
  <text x="80" y="500" font-family="-apple-system, 'PingFang SC', 'Noto Sans SC', sans-serif" font-size="26" fill="#888888">改写式翻译 · 发芽笔记 · 每日更新</text>
</svg>`;

// og:image 爬虫对非 1.91:1 比例会轻微裁切；统一裁到 630 高。
function cropToOg(svg) {
  return svg
    .replace('width="1200" height="675" viewBox="0 0 1200 675"', 'width="1200" height="630" viewBox="0 22.5 1200 630"')
    .replace('viewBox="0 0 1200 675"', 'viewBox="0 22.5 1200 630"');
}

function renderPng(svg) {
  const r = new Resvg(cropToOg(svg), {
    fitTo: { mode: "width", value: 1200 },
    font: { loadSystemFonts: true },
  });
  return r.render().asPng();
}

let converted = 0;
let skipped = 0;
const svgs = fs.readdirSync(COVERS).filter((f) => f.endsWith(".svg"));
for (const file of svgs) {
  const svgPath = path.join(COVERS, file);
  const pngPath = svgPath.replace(/\.svg$/, ".png");
  if (fs.existsSync(pngPath) && fs.statSync(pngPath).mtimeMs >= fs.statSync(svgPath).mtimeMs) {
    skipped += 1;
    continue;
  }
  const svg = fs.readFileSync(svgPath, "utf8");
  fs.writeFileSync(pngPath, renderPng(svg));
  converted += 1;
}

// 首页全站卡：无 SVG 源文件，直接渲染；内容不变但保持与其它卡同生命周期。
const sitePng = path.join(COVERS, "og-site.png");
fs.writeFileSync(sitePng, renderPng(SITE_CARD_SVG));

console.log(`[gen_og] converted=${converted} skipped=${skipped} site-card=ok`);
