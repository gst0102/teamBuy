const DEFAULT_PAGE_SHARE_IMAGE = "/static/workspace/workspace-notes.webp";

function buildPageShareMessage({ title, path, imageUrl = DEFAULT_PAGE_SHARE_IMAGE } = {}) {
  const targetPath = String(path || "/pages/home/index").trim();
  const message = {
    title: String(title || "资料整理助手").trim().slice(0, 32) || "资料整理助手",
    path: targetPath.startsWith("/") ? targetPath : `/${targetPath}`
  };
  const cover = String(imageUrl || "").trim();
  if (cover) message.imageUrl = cover;
  return message;
}

module.exports = {
  DEFAULT_PAGE_SHARE_IMAGE,
  buildPageShareMessage
};
