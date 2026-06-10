const { request } = require("../utils/request");
const { withCachedMedia, withCachedCards } = require("../utils/media-cache");

function toAbsoluteUrl(url) {
  if (!url) return url;
  if (/^https?:\/\//i.test(url)) return url;
  const app = getApp();
  const baseUrl = (app && app.globalData && app.globalData.apiBaseUrl) || "";
  if (!baseUrl) return url;
  return `${baseUrl}${url.startsWith("/") ? "" : "/"}${url}`;
}

function normalizeCardPayload(card) {
  if (!card || typeof card !== "object") return card;
  return {
    ...card,
    coverUrl: toAbsoluteUrl(card.coverUrl),
    media: Array.isArray(card.media)
      ? card.media.map((item) => ({
          ...item,
          url: toAbsoluteUrl(item.url)
        }))
      : card.media
  };
}

function normalizeAndCacheCard(card) {
  return withCachedMedia(normalizeCardPayload(card));
}

function normalizeAndCacheCards(cards) {
  return withCachedCards((cards || []).map(normalizeCardPayload));
}

function mockLogin(payload) {
  return request({
    url: "/api/auth/mock-login",
    method: "POST",
    data: payload
  });
}

function fetchPendingImports() {
  return request({
    url: "/api/imports/pending"
  }).then(async (res) => ({
    ...res,
    data: Array.isArray(res.data)
      ? await Promise.all(res.data.map(async (item) => ({
          ...item,
          generatedCard: await normalizeAndCacheCard(item.generatedCard)
        })))
      : res.data
  }));
}

function claimImport(importId, userId) {
  return request({
    url: `/api/imports/${importId}/claim`,
    method: "POST",
    data: { userId }
  }).then(async (res) => ({
    ...res,
    data: {
      ...res.data,
      card: await normalizeAndCacheCard(res.data && res.data.card)
    }
  }));
}

function fetchCards(params = {}) {
  const query = [];
  if (params.ownerUserId) query.push(`ownerUserId=${params.ownerUserId}`);
  if (params.keyword) query.push(`keyword=${encodeURIComponent(params.keyword)}`);
  if (params.categoryId) query.push(`categoryId=${params.categoryId}`);
  const suffix = query.length ? `?${query.join("&")}` : "";
  return request({
    url: `/api/cards${suffix}`
  }).then(async (res) => ({
    ...res,
    data: Array.isArray(res.data) ? await normalizeAndCacheCards(res.data) : res.data
  }));
}

function fetchCard(cardId) {
  return request({
    url: `/api/cards/${cardId}`
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheCard(res.data)
  }));
}

function fetchCategories(ownerUserId) {
  const suffix = ownerUserId ? `?ownerUserId=${ownerUserId}` : "";
  return request({
    url: `/api/categories${suffix}`
  });
}

function createCategory(payload) {
  return request({
    url: "/api/categories",
    method: "POST",
    data: payload
  });
}

function deleteCategory(categoryId, ownerUserId) {
  return request({
    url: `/api/categories/${categoryId}?ownerUserId=${ownerUserId}`,
    method: "DELETE"
  });
}

function createCard(payload) {
  return request({
    url: "/api/cards",
    method: "POST",
    data: payload
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheCard(res.data)
  }));
}

function uploadAsset({ filePath, mediaType = "image", ownerUserId = "" }) {
  const app = getApp();
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${app.globalData.apiBaseUrl}/api/uploads/asset`,
      filePath,
      name: "file",
      formData: {
        ownerUserId,
        mediaType
      },
      success(res) {
        let data = {};
        try {
          data = JSON.parse(res.data);
        } catch (error) {
          reject({ detail: "上传返回解析失败" });
          return;
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve({
            ...data.data,
            url: toAbsoluteUrl(data.data && data.data.url),
            displayUrl: toAbsoluteUrl(data.data && data.data.url)
          });
          return;
        }
        reject(data);
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

function updateCard(cardId, payload) {
  return request({
    url: `/api/cards/${cardId}`,
    method: "PUT",
    data: payload
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheCard(res.data)
  }));
}

function deleteCard(cardId, ownerUserId) {
  return request({
    url: `/api/cards/${cardId}?ownerUserId=${ownerUserId}`,
    method: "DELETE"
  });
}

function publishCard(cardId, userId) {
  return request({
    url: `/api/cards/${cardId}/publish`,
    method: "POST",
    data: { userId }
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheCard(res.data)
  }));
}

function duplicateCard(cardId, userId) {
  return request({
    url: `/api/cards/${cardId}/duplicate`,
    method: "POST",
    data: { userId }
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheCard(res.data)
  }));
}

function recordView(cardId, payload) {
  return request({
    url: `/api/cards/${cardId}/view`,
    method: "POST",
    data: payload
  });
}

function fetchStats(cardId, requesterUserId) {
  const suffix = requesterUserId ? `?requesterUserId=${requesterUserId}` : "";
  return request({
    url: `/api/cards/${cardId}/stats${suffix}`
  });
}

function createRelay(cardId, payload) {
  return request({
    url: `/api/cards/${cardId}/relay`,
    method: "POST",
    data: payload
  });
}

function fetchRelays(cardId, requesterUserId) {
  return request({
    url: `/api/cards/${cardId}/relays?requesterUserId=${requesterUserId}`
  });
}

function deleteRelay(relayId, operatorUserId) {
  return request({
    url: `/api/relays/${relayId}?operatorUserId=${operatorUserId}`,
    method: "DELETE"
  });
}

function followRelay(relayId, operatorUserId) {
  return request({
    url: `/api/relays/${relayId}/follow-up`,
    method: "POST",
    data: { operatorUserId }
  });
}

function triggerMockImport(payload) {
  return request({
    url: "/api/wecom/mock-sync",
    method: "POST",
    data: payload
  });
}

function fetchImportNotifications() {
  return request({
    url: "/api/wecom/notifications"
  });
}

function fetchLeadReminders(ownerUserId, status = "") {
  const query = [`ownerUserId=${ownerUserId}`];
  if (status) query.push(`status=${status}`);
  return request({
    url: `/api/lead-reminders?${query.join("&")}`
  });
}

function upsertLeadReminder(payload) {
  return request({
    url: "/api/lead-reminders",
    method: "POST",
    data: payload
  });
}

function updateLeadReminder(reminderId, payload) {
  return request({
    url: `/api/lead-reminders/${reminderId}`,
    method: "PUT",
    data: payload
  });
}

function deleteLeadReminder(reminderId, ownerUserId) {
  return request({
    url: `/api/lead-reminders/${reminderId}?ownerUserId=${ownerUserId}`,
    method: "DELETE"
  });
}

module.exports = {
  mockLogin,
  fetchPendingImports,
  claimImport,
  fetchCards,
  fetchCard,
  fetchCategories,
  createCategory,
  deleteCategory,
  createCard,
  uploadAsset,
  updateCard,
  deleteCard,
  publishCard,
  duplicateCard,
  recordView,
  fetchStats,
  createRelay,
  fetchRelays,
  deleteRelay,
  followRelay,
  triggerMockImport,
  fetchImportNotifications,
  fetchLeadReminders,
  upsertLeadReminder,
  updateLeadReminder,
  deleteLeadReminder
};
