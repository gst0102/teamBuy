const api = require("../services/api");

function getCardId(cardOrId) {
  if (!cardOrId) return "";
  return typeof cardOrId === "string" ? cardOrId : cardOrId.id;
}

async function resolveCard(cardOrId) {
  if (cardOrId && typeof cardOrId === "object" && cardOrId.sourceNoteId) {
    return cardOrId;
  }
  const cardId = getCardId(cardOrId);
  if (!cardId) return null;
  const res = await api.fetchCard(cardId);
  return res.data || null;
}

async function navigateToResource(cardOrId, fallback = "view") {
  const cardId = getCardId(cardOrId);
  if (!cardId) return;
  wx.showLoading({ title: "打开中" });
  try {
    const card = await resolveCard(cardOrId);
    if (card && card.sourceNoteId) {
      wx.navigateTo({ url: `/pages/note-edit/index?id=${card.sourceNoteId}` });
      return;
    }
    wx.navigateTo({ url: `/pages/card-${fallback}/index?id=${cardId}` });
  } catch (error) {
    wx.showToast({ title: "打开失败", icon: "none" });
  } finally {
    wx.hideLoading();
  }
}

function navigateToResourceEdit(cardOrId) {
  return navigateToResource(cardOrId, "edit");
}

function navigateToResourceView(cardOrId) {
  return navigateToResource(cardOrId, "view");
}

module.exports = {
  navigateToResourceEdit,
  navigateToResourceView
};
