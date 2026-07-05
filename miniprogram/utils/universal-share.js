const { generateTitleShareImage } = require("./business-card-share");

const UNIVERSAL_SHARE_CANVAS_ID = "universalShareCanvas";
const DEFAULT_FALLBACK_PATH = "/pages/home/index";

function cleanText(value, fallback = "") {
  return String(value || fallback || "").replace(/\s+/g, " ").trim();
}

function buildCustomerShareTitle(title, fallback = "资料整理助手") {
  const cleanTitle = cleanText(title, fallback);
  return cleanTitle.includes("｜") ? cleanTitle : `${cleanTitle}｜点开查看完整资料`;
}

function normalizeShareSource(source = {}) {
  return {
    title: cleanText(source.title, "资料整理助手"),
    summary: cleanText(source.summary || source.subtitle, "打开小程序查看完整资料"),
    badge: cleanText(source.badge || source.categoryName, "资料"),
    coverUrl: cleanText(source.coverUrl || source.coverDisplayUrl || source.imageUrl, ""),
    path: cleanText(source.path, DEFAULT_FALLBACK_PATH),
    shareTargetLabel: cleanText(source.shareTargetLabel || source.badge, "资料")
  };
}

async function prepareUniversalShareImage(page, source = {}) {
  if (!page || !page.setData) return "";
  const share = normalizeShareSource(source);
  try {
    const imageUrl = await generateTitleShareImage(page, UNIVERSAL_SHARE_CANVAS_ID, {
      title: share.title,
      summary: share.summary,
      badge: share.badge,
      coverUrl: share.coverUrl,
      hint: share.summary,
      growthHint: "点击生成同款",
      shareTargetLabel: share.shareTargetLabel
    });
    page.setData({
      universalShareImage: imageUrl || "",
      universalShareSource: share
    });
    return imageUrl || "";
  } catch (error) {
    page.setData({
      universalShareImage: "",
      universalShareSource: share
    });
    return "";
  }
}

function buildUniversalShareMessage(page, source = {}) {
  const data = (page && page.data) || {};
  const share = normalizeShareSource({
    ...(data.universalShareSource || {}),
    ...(source || {})
  });
  const imageUrl = cleanText(source.imageUrl || data.universalShareImage, "");
  return {
    title: buildCustomerShareTitle(share.title),
    path: share.path || DEFAULT_FALLBACK_PATH,
    ...(imageUrl ? { imageUrl } : {})
  };
}

module.exports = {
  UNIVERSAL_SHARE_CANVAS_ID,
  buildCustomerShareTitle,
  buildUniversalShareMessage,
  prepareUniversalShareImage
};
