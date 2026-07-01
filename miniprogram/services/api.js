const { buildApiUrl, request } = require("../utils/request");
const { withCachedMedia, withCachedCards } = require("../utils/media-cache");

function toAbsoluteUrl(url) {
  if (!url) return url;
  if (/^https?:\/\//i.test(url)) return url;
  const app = getApp();
  const baseUrl = (app && app.globalData && app.globalData.apiBaseUrl) || "";
  const mediaRoutePrefix = (app && app.globalData && app.globalData.mediaRoutePrefix) || "";
  if (!baseUrl) return url;
  if (mediaRoutePrefix && url.startsWith("/media")) {
    return `${baseUrl}${mediaRoutePrefix}${url.slice("/media".length)}`;
  }
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

function normalizeNotePayload(note) {
  if (!note || typeof note !== "object") return note;
  return {
    ...note,
    coverUrl: toAbsoluteUrl(note.coverUrl),
    media: Array.isArray(note.media)
      ? note.media.map((item) => ({
          ...item,
          url: toAbsoluteUrl(item.url)
        }))
      : note.media
  };
}

function normalizeAndCacheCard(card) {
  return withCachedMedia(normalizeCardPayload(card));
}

function normalizeAndCacheNote(note) {
  return withCachedMedia(normalizeNotePayload(note));
}

function normalizeShowcasePayload(showcase) {
  if (!showcase || typeof showcase !== "object") return showcase;
  return {
    ...showcase,
    bannerUrl: toAbsoluteUrl(showcase.bannerUrl),
    items: Array.isArray(showcase.items)
      ? showcase.items.map((item) => ({
          ...item,
          coverUrl: toAbsoluteUrl(item.coverUrl)
        }))
      : showcase.items
  };
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

function wechatLogin(payload) {
  return request({
    url: "/api/auth/wechat-login",
    method: "POST",
    data: payload
  });
}

function updateUserProfile(userId, payload) {
  return request({
    url: `/api/auth/users/${userId}/profile`,
    method: "PATCH",
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
          generatedCard: await normalizeAndCacheCard(item.generatedCard),
          generatedNote: await normalizeAndCacheNote(item.generatedNote)
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
      card: await normalizeAndCacheCard(res.data && res.data.card),
      note: await normalizeAndCacheNote(res.data && res.data.note)
    }
  }));
}

function claimImportByToken(token, userId) {
  return request({
    url: "/api/imports/claim-by-token",
    method: "POST",
    data: { token, userId }
  }).then(async (res) => ({
    ...res,
    data: {
      ...res.data,
      card: await normalizeAndCacheCard(res.data && res.data.card),
      note: await normalizeAndCacheNote(res.data && res.data.note)
    }
  }));
}

function createWecomBindIntent(userId) {
  return request({
    url: "/api/auth/wecom-bind-intent",
    method: "POST",
    data: { userId }
  });
}

function fetchNotes(params = {}) {
  const query = [];
  if (params.ownerUserId) query.push(`ownerUserId=${params.ownerUserId}`);
  if (params.keyword) query.push(`keyword=${encodeURIComponent(params.keyword)}`);
  if (params.categoryId) query.push(`categoryId=${params.categoryId}`);
  if (params.sourceType) query.push(`sourceType=${encodeURIComponent(params.sourceType)}`);
  if (params.systemCategory) query.push(`systemCategory=${encodeURIComponent(params.systemCategory)}`);
  if (params.tag) query.push(`tag=${encodeURIComponent(params.tag)}`);
  if (params.topicId) query.push(`topicId=${encodeURIComponent(params.topicId)}`);
  if (params.sort) query.push(`sort=${encodeURIComponent(params.sort)}`);
  if (params.includeDeleted) query.push("includeDeleted=true");
  const suffix = query.length ? `?${query.join("&")}` : "";
  return request({
    url: `/api/notes${suffix}`
  }).then(async (res) => ({
    ...res,
    data: Array.isArray(res.data) ? await Promise.all(res.data.map(normalizeAndCacheNote)) : res.data
  }));
}

function fetchTagSuggestions(params = {}) {
  const query = [];
  if (params.ownerUserId) query.push(`ownerUserId=${params.ownerUserId}`);
  if (params.noteId) query.push(`noteId=${params.noteId}`);
  if (params.text) query.push(`text=${encodeURIComponent(params.text)}`);
  const suffix = query.length ? `?${query.join("&")}` : "";
  return request({ url: `/api/notes/tag-suggestions${suffix}` });
}

function createManualNoteDraft(payload) {
  return request({
    url: "/api/notes/manual-draft",
    method: "POST",
    data: payload
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function createQuickNoteCapture(payload) {
  return request({
    url: "/api/notes/quick-capture",
    method: "POST",
    data: payload
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function parsePropertyBatch(payload) {
  return request({
    url: "/api/notes/property-batch/parse",
    method: "POST",
    data: payload
  });
}

function createPropertyBatch(payload) {
  return request({
    url: "/api/notes/property-batch/create",
    method: "POST",
    data: payload
  }).then(async (res) => ({
    ...res,
    data: {
      ...res.data,
      notes: Array.isArray(res.data && res.data.notes)
        ? await Promise.all(res.data.notes.map(normalizeAndCacheNote))
        : []
    }
  }));
}

function fetchTopics(ownerUserId) {
  return request({ url: `/api/notes/topics?ownerUserId=${ownerUserId}` });
}

function createDemoData(ownerUserId) {
  return request({
    url: `/api/notes/demo-data?ownerUserId=${ownerUserId}`,
    method: "POST"
  });
}

function cleanupDemoData(ownerUserId) {
  return request({
    url: `/api/notes/demo-data/cleanup?ownerUserId=${ownerUserId}`,
    method: "POST"
  });
}

function createTopic(payload) {
  return request({
    url: "/api/notes/topics",
    method: "POST",
    data: payload
  });
}

function deleteTopic(topicId, ownerUserId) {
  return request({
    url: `/api/notes/topics/${topicId}?ownerUserId=${ownerUserId}`,
    method: "DELETE"
  });
}

function addNoteToTopic(noteId, topicId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}/topics/${topicId}`,
    method: "POST",
    data: { ownerUserId }
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function removeNoteFromTopic(noteId, topicId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}/topics/${topicId}?ownerUserId=${ownerUserId}`,
    method: "DELETE"
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function fetchNote(noteId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}?ownerUserId=${ownerUserId}`
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function fetchPublicNote(noteId) {
  return request({
    url: `/api/notes/public/${noteId}`
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function geocodeAddress(params = {}) {
  const query = [];
  if (params.address) query.push(`address=${encodeURIComponent(params.address)}`);
  if (params.region) query.push(`region=${encodeURIComponent(params.region)}`);
  return request({
    url: `/api/location/geocode?${query.join("&")}`
  });
}

function searchEnterpriseResources(params = {}) {
  const query = [];
  if (params.keyword) query.push(`keyword=${encodeURIComponent(params.keyword)}`);
  if (params.pageSize) query.push(`page_size=${encodeURIComponent(params.pageSize)}`);
  return request({
    url: `/api/enterprise-resources/search?${query.join("&")}`
  });
}

function fetchCustomerActionConfig(noteId, params = {}) {
  const query = [];
  if (params.viewerUserId) query.push(`viewerUserId=${encodeURIComponent(params.viewerUserId)}`);
  if (params.anonymousId) query.push(`anonymousId=${encodeURIComponent(params.anonymousId)}`);
  return request({
    url: `/api/notes/${noteId}/customer-actions/config?${query.join("&")}`
  });
}

function fetchNoteCustomerActions(noteId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}/customer-actions?ownerUserId=${ownerUserId}`
  });
}

function submitCustomerAction(noteId, actionKey, payload = {}) {
  return request({
    url: `/api/notes/${noteId}/customer-actions/${actionKey}`,
    method: "POST",
    data: payload
  });
}

function fetchOrders(params = {}) {
  const query = [];
  if (params.userId) query.push(`userId=${encodeURIComponent(params.userId)}`);
  if (params.role) query.push(`role=${encodeURIComponent(params.role)}`);
  if (params.noteId) query.push(`noteId=${encodeURIComponent(params.noteId)}`);
  return request({ url: `/api/orders?${query.join("&")}` });
}

function fetchOrder(orderId, userId) {
  return request({ url: `/api/orders/${orderId}?userId=${encodeURIComponent(userId)}` });
}

function updateOrderStatus(orderId, payload) {
  return request({
    url: `/api/orders/${orderId}/status`,
    method: "PATCH",
    data: payload
  });
}

function fetchMessageThreads(userId) {
  return request({ url: `/api/messages/threads?userId=${encodeURIComponent(userId)}` });
}

function createMessageThread(payload) {
  return request({
    url: "/api/messages/threads",
    method: "POST",
    data: payload
  });
}

function fetchThreadMessages(threadId, userId) {
  return request({ url: `/api/messages/threads/${threadId}/messages?userId=${encodeURIComponent(userId)}` });
}

function sendThreadMessage(threadId, payload) {
  return request({
    url: `/api/messages/threads/${threadId}/messages`,
    method: "POST",
    data: payload
  });
}

function markThreadRead(threadId, userId) {
  return request({
    url: `/api/messages/threads/${threadId}/read`,
    method: "POST",
    data: { userId }
  });
}

function updateNote(noteId, payload) {
  return request({
    url: `/api/notes/${noteId}`,
    method: "PUT",
    data: payload
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function duplicateNote(noteId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}/duplicate`,
    method: "POST",
    data: { ownerUserId }
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function clonePropertySame(payload) {
  return request({
    url: "/api/notes/property-same/clone",
    method: "POST",
    data: payload
  }).then(async (res) => {
    const data = res.data || {};
    if (data.type === "note" && data.note) {
      return {
        ...res,
        data: {
          ...data,
          note: await normalizeAndCacheNote(data.note)
        }
      };
    }
    if (data.type === "showcase" && data.showcase) {
      return {
        ...res,
        data: {
          ...data,
          showcase: normalizeShowcasePayload(data.showcase)
        }
      };
    }
    return res;
  });
}

function organizeNote(noteId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}/organize?ownerUserId=${ownerUserId}`,
    method: "POST"
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function generateNote(noteId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}/generate?ownerUserId=${ownerUserId}`,
    method: "POST"
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function confirmNoteType(noteId, payload) {
  return request({
    url: `/api/notes/${noteId}/confirm-type`,
    method: "POST",
    data: payload
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  }));
}

function deleteNote(noteId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}?ownerUserId=${ownerUserId}`,
    method: "DELETE"
  });
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
      url: buildApiUrl("/api/uploads/asset"),
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

function uploadImageNote({ filePath, ownerUserId = "" }) {
  const app = getApp();
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: buildApiUrl("/api/notes/image-capture"),
      filePath,
      name: "file",
      formData: {
        ownerUserId
      },
      success(res) {
        let data = {};
        try {
          data = JSON.parse(res.data);
        } catch (error) {
          reject({ detail: res.statusCode === 413 ? "图片太大，请换一张较小的图片" : `图片保存失败（${res.statusCode || "无状态码"}）` });
          return;
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve({
            ...data.data,
            note: normalizeNotePayload(data.data && data.data.note)
          });
          return;
        }
        reject(data);
      },
      fail: reject
    });
  });
}

function recognizeNoteImage(noteId, ownerUserId) {
  return request({
    url: `/api/ocr/notes/${noteId}/recognize`,
    method: "POST",
    data: { ownerUserId }
  }).then(async (res) => ({
    ...res,
    data: {
      ...res.data,
      note: await normalizeAndCacheNote(res.data && res.data.note)
    }
  }));
}

function fetchShowcases(ownerUserId) {
  return request({
    url: `/api/showcases?ownerUserId=${encodeURIComponent(ownerUserId)}`
  }).then((res) => ({
    ...res,
    data: Array.isArray(res.data) ? res.data.map(normalizeShowcasePayload) : res.data
  }));
}

function createShowcase(payload) {
  return request({
    url: "/api/showcases",
    method: "POST",
    data: payload
  }).then((res) => ({
    ...res,
    data: normalizeShowcasePayload(res.data)
  }));
}

function fetchShowcase(showcaseId, ownerUserId) {
  return request({
    url: `/api/showcases/${showcaseId}?ownerUserId=${encodeURIComponent(ownerUserId)}`
  }).then((res) => ({
    ...res,
    data: normalizeShowcasePayload(res.data)
  }));
}

function updateShowcase(showcaseId, payload) {
  return request({
    url: `/api/showcases/${showcaseId}`,
    method: "PUT",
    data: payload
  }).then((res) => ({
    ...res,
    data: normalizeShowcasePayload(res.data)
  }));
}

function publishShowcase(showcaseId, ownerUserId) {
  return request({
    url: `/api/showcases/${showcaseId}/publish`,
    method: "POST",
    data: { ownerUserId }
  }).then((res) => ({
    ...res,
    data: normalizeShowcasePayload(res.data)
  }));
}

function archiveShowcase(showcaseId, ownerUserId) {
  return request({
    url: `/api/showcases/${showcaseId}/archive`,
    method: "POST",
    data: { ownerUserId }
  }).then((res) => ({
    ...res,
    data: normalizeShowcasePayload(res.data)
  }));
}

function deleteShowcase(showcaseId, ownerUserId) {
  return request({
    url: `/api/showcases/${showcaseId}/delete`,
    method: "POST",
    data: { ownerUserId }
  });
}

function recordShowcaseEvent(showcaseId, payload = {}) {
  return request({
    url: `/api/showcases/${showcaseId}/events`,
    method: "POST",
    data: payload
  });
}

function fetchShowcaseAnalytics(showcaseId, ownerUserId) {
  return request({
    url: `/api/showcases/${showcaseId}/analytics?ownerUserId=${encodeURIComponent(ownerUserId)}`
  });
}

function fetchPublicShowcase(showcaseId) {
  return request({
    url: `/api/showcases/public/${showcaseId}`
  }).then((res) => ({
    ...res,
    data: normalizeShowcasePayload(res.data)
  }));
}

function fetchBusinessDashboard(ownerUserId, requesterUserId = ownerUserId, mode = "") {
  const query = [
    `ownerUserId=${encodeURIComponent(ownerUserId)}`,
    `requesterUserId=${encodeURIComponent(requesterUserId)}`
  ];
  if (mode) query.push(`mode=${encodeURIComponent(mode)}`);
  return request({
    url: `/api/dashboard/business?${query.join("&")}`
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

function recordNoteView(noteId, payload) {
  return request({
    url: `/api/notes/${noteId}/view`,
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

function fetchLeadReminder(reminderId, ownerUserId) {
  return request({
    url: `/api/lead-reminders/${reminderId}?ownerUserId=${ownerUserId}`
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
  wechatLogin,
  updateUserProfile,
  fetchPendingImports,
  claimImport,
  claimImportByToken,
  createWecomBindIntent,
  fetchNotes,
  fetchTagSuggestions,
  createManualNoteDraft,
  createQuickNoteCapture,
  parsePropertyBatch,
  createPropertyBatch,
  fetchTopics,
  createDemoData,
  cleanupDemoData,
  createTopic,
  deleteTopic,
  addNoteToTopic,
  removeNoteFromTopic,
  fetchNote,
  fetchPublicNote,
  geocodeAddress,
  searchEnterpriseResources,
  fetchCustomerActionConfig,
  fetchNoteCustomerActions,
  submitCustomerAction,
  fetchOrders,
  fetchOrder,
  updateOrderStatus,
  fetchMessageThreads,
  createMessageThread,
  fetchThreadMessages,
  sendThreadMessage,
  markThreadRead,
  updateNote,
  duplicateNote,
  clonePropertySame,
  organizeNote,
  generateNote,
  confirmNoteType,
  deleteNote,
  fetchCards,
  fetchCard,
  fetchCategories,
  createCategory,
  deleteCategory,
  createCard,
  uploadAsset,
  uploadImageNote,
  recognizeNoteImage,
  fetchShowcases,
  createShowcase,
  fetchShowcase,
  updateShowcase,
  publishShowcase,
  archiveShowcase,
  deleteShowcase,
  recordShowcaseEvent,
  fetchShowcaseAnalytics,
  fetchPublicShowcase,
  fetchBusinessDashboard,
  updateCard,
  deleteCard,
  publishCard,
  duplicateCard,
  recordView,
  recordNoteView,
  fetchStats,
  createRelay,
  fetchRelays,
  deleteRelay,
  followRelay,
  triggerMockImport,
  fetchImportNotifications,
  fetchLeadReminders,
  fetchLeadReminder,
  upsertLeadReminder,
  updateLeadReminder,
  deleteLeadReminder
};
