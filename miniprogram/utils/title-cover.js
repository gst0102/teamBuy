function normalizeTitle(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .replace(/[【】\[\]（）()]/g, " ")
    .trim();
}

function splitTitleSegments(title) {
  return normalizeTitle(title)
    .split(/[|｜/、·，,。；;：:\-]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function compactFocusText(title, maxChars = 8) {
  const segments = splitTitleSegments(title);
  const raw = segments.find((item) => item.replace(/\s+/g, "").length >= 2) || normalizeTitle(title) || "";
  const compact = raw.replace(/\s+/g, "").replace(/[^\u4e00-\u9fa5A-Za-z0-9]/g, "");
  const text = compact || raw.replace(/\s+/g, "");
  if (!text) return "资料";
  return text.slice(0, maxChars);
}

function toneIndex(seed = "") {
  const text = String(seed || "");
  let total = 0;
  for (let index = 0; index < text.length; index += 1) {
    total += text.charCodeAt(index);
  }
  return total % 4;
}

function buildTitleCoverData(title, badge = "资料") {
  const focusText = compactFocusText(title, 8);
  return {
    badge: String(badge || "资料").slice(0, 4),
    focusText,
    line1: focusText.slice(0, 4),
    line2: focusText.slice(4, 8),
    tone: toneIndex(`${badge}-${title}`),
    summary: normalizeTitle(title).slice(0, 18)
  };
}

module.exports = {
  buildTitleCoverData,
  compactFocusText,
  normalizeTitle
};
