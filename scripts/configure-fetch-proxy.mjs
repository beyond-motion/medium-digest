import { EnvHttpProxyAgent, ProxyAgent, Socks5ProxyAgent, setGlobalDispatcher } from "undici";

function normalizeProxyUrl(value) {
  const proxy = String(value || "").trim();
  if (!proxy) return "";
  return proxy;
}

function selectProxyUrl() {
  return (
    normalizeProxyUrl(process.env.HTTPS_PROXY) ||
    normalizeProxyUrl(process.env.https_proxy) ||
    normalizeProxyUrl(process.env.ALL_PROXY) ||
    normalizeProxyUrl(process.env.all_proxy) ||
    normalizeProxyUrl(process.env.HTTP_PROXY) ||
    normalizeProxyUrl(process.env.http_proxy)
  );
}

export function configureFetchProxy() {
  const proxyUrl = selectProxyUrl();
  if (!proxyUrl) return null;

  const lower = proxyUrl.toLowerCase();
  const dispatcher =
    lower.startsWith("socks5://") || lower.startsWith("socks5h://")
      ? new Socks5ProxyAgent(proxyUrl)
      : lower.startsWith("http://") || lower.startsWith("https://")
        ? new ProxyAgent(proxyUrl)
        : new EnvHttpProxyAgent();

  setGlobalDispatcher(dispatcher);
  return proxyUrl;
}
