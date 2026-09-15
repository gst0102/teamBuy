const WEBVIEW_BUSINESS_DOMAINS = ["teambuy.lifelove.top"];

function decodePart(value) {
  try {
    return decodeURIComponent(String(value || ""));
  } catch (error) {
    return String(value || "");
  }
}

function getMiniAppTitle(shortLink) {
  const value = String(shortLink || "").trim();
  const body = value.replace(/^#小程序:\/\//, "");
  const name = body.split("/")[0].trim();
  return decodePart(name) || "目标小程序";
}

function getWebHost(url) {
  const match = String(url || "").match(/^https:\/\/([^/?#]+)/i);
  return match ? String(match[1]).toLowerCase() : "";
}

function isOfficialAccountArticleUrl(url) {
  return getWebHost(url) === "mp.weixin.qq.com";
}

function isWebViewBusinessDomain(host) {
  const normalizedHost = String(host || "").toLowerCase().replace(/:\d+$/, "");
  return WEBVIEW_BUSINESS_DOMAINS.some((domain) => {
    const normalizedDomain = String(domain || "").toLowerCase();
    return normalizedHost === normalizedDomain || normalizedHost.endsWith(`.${normalizedDomain}`);
  });
}

function makeLinkId(type, value, index = 0) {
  const safeValue = String(value || "").replace(/[^a-z0-9]+/gi, "_").slice(0, 30);
  return `task_link_${type}_${safeValue || index}_${index}`;
}

function normalizeLink(link, index = 0) {
  if (!link || typeof link !== "object") return null;
  const raw = String(link.raw || link.shortLink || link.url || "").trim();
  const title = String(link.title || "").trim();
  const parsed = parseTaskLink(raw, title);
  if (!parsed.ok) return null;
  return {
    ...parsed.link,
    id: String(link.id || makeLinkId(parsed.link.type, raw, index)),
    opened: Boolean(link.opened)
  };
}

function parseTaskLink(rawInput, titleInput = "") {
  const raw = String(rawInput || "").trim();
  const title = String(titleInput || "").trim();
  if (!raw) return { ok: false, error: "请粘贴小程序短链接或 HTTPS 网页链接" };

  if (/^#小程序:\/\//.test(raw)) {
    const miniTitle = title || getMiniAppTitle(raw);
    return {
      ok: true,
      link: {
        type: "miniapp",
        typeLabel: "小程序",
        raw,
        shortLink: raw,
        url: "",
        title: miniTitle,
        displayTitle: miniTitle,
        description: "点击进入目标小程序",
        detailDescription: "点击进入小程序，返回后提交完成",
        actionLabel: "打开小程序",
        openMode: "miniapp",
        host: ""
      }
    };
  }

  if (/^http:\/\//i.test(raw)) {
    return { ok: false, error: "网页链接请使用 HTTPS 地址" };
  }

  if (/^https:\/\//i.test(raw)) {
    const host = getWebHost(raw);
    if (!host) return { ok: false, error: "网页链接格式不正确" };
    const officialArticle = isOfficialAccountArticleUrl(raw);
    const allowed = isWebViewBusinessDomain(host);
    const webTitle = title || host;
    return {
      ok: true,
      link: {
        type: "web",
        typeLabel: "网页",
        raw,
        shortLink: "",
        url: raw,
        title: webTitle,
        displayTitle: webTitle,
        description: officialArticle
          ? "使用微信能力打开公众号文章"
          : (allowed ? "在资料整理助手内打开网页" : "复制链接后用手机浏览器打开"),
        detailDescription: officialArticle
          ? "点击打开公众号文章，失败时可复制链接"
          : (allowed ? "网页将在小程序内打开" : "请复制链接后用手机浏览器打开"),
        actionLabel: officialArticle ? "打开公众号文章" : (allowed ? "打开网页" : "复制到浏览器"),
        openMode: officialArticle ? "official_article" : (allowed ? "webview" : "browser"),
        host
      }
    };
  }

  return { ok: false, error: "链接格式不支持，请粘贴 #小程序:// 或 HTTPS 地址" };
}

function normalizeTaskLinks(links = [], legacyShortLink = "") {
  const source = Array.isArray(links) && links.length
    ? links
    : (String(legacyShortLink || "").trim() ? [{ raw: String(legacyShortLink).trim() }] : []);
  return source.map((link, index) => normalizeLink(link, index)).filter(Boolean);
}

function summarizeTaskLinks(links = []) {
  const normalized = normalizeTaskLinks(links);
  if (!normalized.length) return "暂无任务入口";
  const miniappCount = normalized.filter((link) => link.type === "miniapp").length;
  const webCount = normalized.filter((link) => link.type === "web").length;
  const parts = [];
  if (miniappCount) parts.push(`小程序 ${miniappCount}`);
  if (webCount) parts.push(`网页 ${webCount}`);
  return `任务入口 · ${parts.join(" / ")}`;
}

module.exports = {
  WEBVIEW_BUSINESS_DOMAINS,
  getWebHost,
  isOfficialAccountArticleUrl,
  isWebViewBusinessDomain,
  normalizeTaskLinks,
  parseTaskLink,
  summarizeTaskLinks
};
