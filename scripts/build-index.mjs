import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import matter from "gray-matter";
import { configureFetchProxy } from "./configure-fetch-proxy.mjs";

configureFetchProxy();

const root = process.cwd();
const articlesDir = path.join(root, "content", "articles");
const dataDir = path.join(root, "data");
const outputPath = path.join(dataDir, "articles.json");
const publicDir = path.join(root, "public");
const coversDir = path.join(publicDir, "covers");
const articleImagesDir = path.join(publicDir, "article-images");
const KNOWN_IMAGE_EXTS = [".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg"];
const WEBP_QUALITY = "82";

function normalizeDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? String(value) : date.toISOString();
}

function extFromContentType(contentType = "") {
  if (contentType.includes("image/png")) return ".png";
  if (contentType.includes("image/webp")) return ".webp";
  if (contentType.includes("image/jpeg")) return ".jpg";
  if (contentType.includes("image/jpg")) return ".jpg";
  if (contentType.includes("image/gif")) return ".gif";
  return ".jpg";
}

function extFromUrl(url) {
  try {
    const pathname = new URL(url).pathname;
    const ext = path.extname(pathname);
    return ext && ext.length <= 5 ? ext : "";
  } catch {
    return "";
  }
}

async function findExistingAsset(dir, stem) {
  for (const ext of KNOWN_IMAGE_EXTS) {
    const fileName = `${stem}${ext}`;
    try {
      await fs.access(path.join(dir, fileName));
      return fileName;
    } catch {}
  }
  return "";
}

async function cleanupSiblingVariants(dir, stem, keepFile) {
  const keepName = path.basename(keepFile);
  for (const ext of KNOWN_IMAGE_EXTS) {
    const fileName = `${stem}${ext}`;
    if (fileName === keepName) continue;
    try {
      await fs.unlink(path.join(dir, fileName));
    } catch {}
  }
}

async function fetchWithRetry(url, attempts = 3) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        headers: {
          "user-agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36",
        },
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response;
    } catch (error) {
      lastError = error;
      if (attempt < attempts - 1) {
        await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
      }
    }
  }
  throw lastError;
}

function buildDownloadCandidates(imageUrl) {
  const candidates = [imageUrl];
  try {
    const parsed = new URL(imageUrl);
    if (parsed.hostname === "d24ovhgu8s7341.cloudfront.net") {
      candidates.push(`https://wsrv.nl/?url=${parsed.host}${parsed.pathname}`);
    }
  } catch {}
  return [...new Set(candidates)];
}

function curlDownload(url) {
  return spawnSync(
    "curl",
    [
      "-fsSL",
      "--retry",
      "3",
      "--retry-delay",
      "1",
      "--max-time",
      "30",
      url,
    ],
    { encoding: null, maxBuffer: 64 * 1024 * 1024 }
  );
}

function runBinary(command, args) {
  return spawnSync(command, args, {
    encoding: null,
    stdio: "ignore",
    maxBuffer: 64 * 1024 * 1024,
  });
}

async function optimizeRasterImage({ inputFile, stem, resizeMax = 0 }) {
  const sourceExt = path.extname(inputFile).toLowerCase();
  const isConvertible = [".png", ".jpg", ".jpeg"].includes(sourceExt);

  if (resizeMax > 0 && sourceExt !== ".svg" && sourceExt !== ".gif") {
    const resize = runBinary("sips", ["-Z", String(resizeMax), inputFile, "--out", inputFile]);
    if (resize.error && resize.error.code !== "ENOENT") {
      console.warn(`Could not resize image ${path.basename(inputFile)}: ${resize.error.message}`);
    }
  }

  if (!isConvertible) {
    return path.basename(inputFile);
  }

  const webpFile = path.join(path.dirname(inputFile), `${stem}.webp`);
  const webp = runBinary("cwebp", ["-quiet", "-q", WEBP_QUALITY, inputFile, "-o", webpFile]);
  if (webp.status === 0) {
    try {
      const [left, right] = await Promise.all([fs.stat(inputFile), fs.stat(webpFile)]);
      if (right.size <= left.size) {
        await fs.unlink(inputFile).catch(() => {});
        return path.basename(webpFile);
      }
      await fs.unlink(webpFile).catch(() => {});
      return path.basename(inputFile);
    } catch {
      return path.basename(webpFile);
    }
  }

  return path.basename(inputFile);
}

async function downloadImage(imageUrl) {
  let lastError;

  try {
    const response = await fetchWithRetry(imageUrl);
    return {
      buffer: Buffer.from(await response.arrayBuffer()),
      contentType: response.headers.get("content-type") || "",
      finalUrl: response.url || imageUrl,
    };
  } catch (error) {
    lastError = error;
  }

  for (const candidate of buildDownloadCandidates(imageUrl)) {
    const result = curlDownload(candidate);
    if (result.status === 0 && result.stdout?.length) {
      return {
        buffer: result.stdout,
        contentType: "",
        finalUrl: candidate,
      };
    }
    lastError = result.error || new Error(result.stderr?.toString("utf8") || `curl exited with ${result.status}`);
  }

  throw lastError;
}

async function cacheRemoteImage({ dir, publicPrefix, stem, imageUrl, resizeMax = 0 }) {
  if (!imageUrl) return "";
  if (!/^https?:\/\//.test(imageUrl)) {
    if (!imageUrl.startsWith("/")) return imageUrl;
    const localPath = path.join(publicDir, imageUrl.replace(/^\//, ""));
    try {
      const optimizedLocal = await optimizeRasterImage({ inputFile: localPath, stem, resizeMax });
      await cleanupSiblingVariants(dir, stem, optimizedLocal);
      return `${publicPrefix}/${optimizedLocal}`;
    } catch {
      return imageUrl;
    }
  }

  try {
    await fs.mkdir(dir, { recursive: true });
    const existing = await findExistingAsset(dir, stem);
    if (existing) {
      const optimizedExisting = await optimizeRasterImage({
        inputFile: path.join(dir, existing),
        stem,
        resizeMax,
      });
      await cleanupSiblingVariants(dir, stem, optimizedExisting);
      return `${publicPrefix}/${optimizedExisting}`;
    }
    const downloaded = await downloadImage(imageUrl);
    const ext =
      extFromUrl(downloaded.finalUrl) ||
      extFromUrl(imageUrl) ||
      extFromContentType(downloaded.contentType);
    const fileName = `${stem}${ext}`;
    const outputFile = path.join(dir, fileName);
    await fs.writeFile(outputFile, downloaded.buffer);
    const optimizedFile = await optimizeRasterImage({ inputFile: outputFile, stem, resizeMax });
    await cleanupSiblingVariants(dir, stem, optimizedFile);
    return `${publicPrefix}/${optimizedFile}`;
  } catch {
    return imageUrl;
  }
}

async function localizeArticleAssets(filePath, slug, parsed) {
  const updatedData = { ...parsed.data };
  let updatedContent = parsed.content;
  let changed = false;

  const coverCandidates = [updatedData.image, ...(updatedData.images || []).map((image) => image.url)];
  let localizedCover = "";
  for (const candidate of coverCandidates) {
    if (!candidate) continue;
    localizedCover = await cacheRemoteImage({
      dir: coversDir,
      publicPrefix: "/covers",
      stem: slug,
      imageUrl: candidate,
      resizeMax: 360,
    });
    if (localizedCover && !/^https?:\/\//.test(localizedCover)) break;
  }
  if (localizedCover && updatedData.image !== localizedCover) {
    updatedData.image = localizedCover;
    changed = true;
  }
  if (typeof updatedData.image === "string" && /^https?:\/\//.test(updatedData.image)) {
    updatedData.image = "";
    changed = true;
  }

  if (Array.isArray(updatedData.images) && updatedData.images.length > 0) {
    const localizedImages = [];
    for (let index = 0; index < updatedData.images.length; index += 1) {
      const image = updatedData.images[index];
      const localUrl = await cacheRemoteImage({
        dir: path.join(articleImagesDir, slug),
        publicPrefix: `/article-images/${slug}`,
        stem: String(index + 1).padStart(2, "0"),
        imageUrl: image.url,
        resizeMax: 1600,
      });
      localizedImages.push({ ...image, url: localUrl });
      if (localUrl !== image.url) {
        updatedContent = updatedContent.split(image.url).join(localUrl);
        changed = true;
      }
    }
    updatedData.images = localizedImages;
  }

  if (changed) {
    await fs.writeFile(filePath, matter.stringify(updatedContent, updatedData));
  }

  return {
    data: updatedData,
    content: updatedContent,
  };
}

async function readArticles() {
  let entries = [];
  try {
    entries = await fs.readdir(articlesDir, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }

  const articles = [];
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
    const filePath = path.join(articlesDir, entry.name);
    const raw = await fs.readFile(filePath, "utf8");
    const parsed = matter(raw);
    const slug = parsed.data.slug || entry.name.replace(/\.md$/, "");
    const localized = await localizeArticleAssets(filePath, slug, parsed);
    const cardImage = localized.data.image && !/^https?:\/\//.test(localized.data.image) ? localized.data.image : "";
    articles.push({
      slug,
      title: localized.data.title || slug,
      author: localized.data.author || "Every",
      date: normalizeDate(localized.data.date),
      sourceUrl: localized.data.source_url || localized.data.sourceUrl || "",
      status: localized.data.status || "processed",
      excerpt: localized.data.excerpt || "",
      image: localized.data.image && !/^https?:\/\//.test(localized.data.image) ? localized.data.image : "",
      cardImage,
      hash: localized.data.hash || "",
      file: `content/articles/${entry.name}`,
    });
  }

  return articles.sort((a, b) => {
    const left = a.date ? new Date(a.date).valueOf() : 0;
    const right = b.date ? new Date(b.date).valueOf() : 0;
    return right - left || a.title.localeCompare(b.title);
  });
}

await fs.mkdir(dataDir, { recursive: true });
const articles = await readArticles();
await fs.writeFile(outputPath, `${JSON.stringify(articles, null, 2)}\n`);
console.log(`Indexed ${articles.length} article(s) into ${path.relative(root, outputPath)}`);
