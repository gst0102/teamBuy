const GENERAL_EDITOR_CARD_TYPES = new Set([
  "text_note",
  "image_ocr",
  "mixed_content",
  "pdf_document"
]);

const EDITOR_PATHS = {
  link: "/subpackages/workbench/link-confirm/index",
  article: "/subpackages/workbench/link-editor/index",
  property_listing: "/subpackages/workbench/property-editor/index",
  groupbuy_product: "/subpackages/workbench/product-editor/index",
  service_offer: "/subpackages/workbench/service-offer-studio/index",
  business_card: "/subpackages/workbench/business-card-studio/index"
};

function getCardId(cardOrId) {
  if (!cardOrId) return "";
  return typeof cardOrId === "string" ? cardOrId : cardOrId.id;
}

function editorPathForCardType(cardType, noteId = "", query = {}) {
  const normalizedType = String(cardType || "text_note");
  const path = EDITOR_PATHS[normalizedType]
    || (GENERAL_EDITOR_CARD_TYPES.has(normalizedType) ? "/subpackages/workbench/note-edit/index" : "/subpackages/workbench/link-confirm/index");
  const params = [];
  if (noteId) params.push(`id=${encodeURIComponent(noteId)}`);
  Object.keys(query || {}).forEach((key) => {
    const value = query[key];
    if (value !== undefined && value !== null && value !== "") {
      params.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
    }
  });
  return `${path}${params.length ? `?${params.join("&")}` : ""}`;
}

function cardTypeFromNote(note = {}) {
  const config = note.visibilityConfig || {};
  return config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note");
}

function navigateToNoteEditor(noteOrId, query = {}) {
  if (typeof noteOrId === "object" && noteOrId) {
    return wx.navigateTo({ url: editorPathForCardType(cardTypeFromNote(noteOrId), noteOrId.id, query) });
  }
  const noteId = String(noteOrId || "");
  if (!noteId) return Promise.resolve();
  const user = require("./dashboard").getCurrentUser();
  const api = require("../services/api");
  if (!user) return wx.navigateTo({ url: "/pages/login/index" });
  wx.showLoading({ title: "打开中" });
  return api.fetchNote(noteId, user.id)
    .then((res) => wx.navigateTo({ url: editorPathForCardType(cardTypeFromNote(res.data || {}), noteId, query) }))
    .catch(() => wx.navigateTo({ url: editorPathForCardType("text_note", noteId, query) }))
    .finally(() => wx.hideLoading());
}

async function resolveCard(cardOrId) {
  if (cardOrId && typeof cardOrId === "object" && cardOrId.sourceNoteId) {
    return cardOrId;
  }
  const cardId = getCardId(cardOrId);
  if (!cardId) return null;
  const api = require("../services/api");
  const res = await api.fetchCard(cardId);
  return res.data || null;
}

async function navigateToResource(cardOrId, fallback = "view", query = {}) {
  const cardId = getCardId(cardOrId);
  if (!cardId) return;
  wx.showLoading({ title: "打开中" });
  try {
    const card = await resolveCard(cardOrId);
    if (card && card.sourceNoteId) {
      const config = card.visibilityConfig || {};
      const cardType = card.cardType || config.cardType || "";
      if (fallback === "view") {
        wx.navigateTo({ url: `/pages/note-preview/index?id=${card.sourceNoteId}` });
        return;
      }
      wx.navigateTo({ url: editorPathForCardType(cardType, card.sourceNoteId, query) });
      return;
    }
    if (fallback === "view") {
      // Historical Card IDs are resolved by the public-note API. The legacy
      // detail route is gone, so every view must use the customer page.
      wx.navigateTo({ url: `/pages/note-preview/index?id=${encodeURIComponent(cardId)}` });
      return;
    }
    wx.navigateTo({ url: `/subpackages/workbench/card-edit/index?id=${encodeURIComponent(cardId)}` });
  } catch (error) {
    wx.showToast({ title: "打开失败", icon: "none" });
  } finally {
    wx.hideLoading();
  }
}

function navigateToResourceEdit(cardOrId, query = {}) {
  return navigateToResource(cardOrId, "edit", query);
}

function navigateToResourceView(cardOrId) {
  return navigateToResource(cardOrId, "view");
}

// Radar and customer-detail projections expose the canonical note ID, not a
// legacy Card ID.  Opening that ID directly avoids an unnecessary /api/cards
// lookup and, more importantly, prevents note IDs from being sent to the card
// resolver where they are reported as an unreadable resource.
function navigateToNoteView(noteId, query = {}) {
  const id = String(noteId || "").trim();
  if (!id) return Promise.resolve();
  const params = [`id=${encodeURIComponent(id)}`];
  Object.keys(query || {}).forEach((key) => {
    const value = query[key];
    if (value !== undefined && value !== null && value !== "") {
      params.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
    }
  });
  return wx.navigateTo({ url: `/pages/note-preview/index?${params.join("&")}` });
}

module.exports = {
  EDITOR_PATHS,
  GENERAL_EDITOR_CARD_TYPES,
  cardTypeFromNote,
  editorPathForCardType,
  navigateToNoteEditor,
  navigateToNoteView,
  navigateToResourceEdit,
  navigateToResourceView
};
