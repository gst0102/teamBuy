const { request } = require("../utils/request");

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
  });
}

function claimImport(importId, userId) {
  return request({
    url: `/api/imports/${importId}/claim`,
    method: "POST",
    data: { userId }
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
  });
}

function fetchCard(cardId) {
  return request({
    url: `/api/cards/${cardId}`
  });
}

function updateCard(cardId, payload) {
  return request({
    url: `/api/cards/${cardId}`,
    method: "PUT",
    data: payload
  });
}

function publishCard(cardId, userId) {
  return request({
    url: `/api/cards/${cardId}/publish`,
    method: "POST",
    data: { userId }
  });
}

function duplicateCard(cardId, userId) {
  return request({
    url: `/api/cards/${cardId}/duplicate`,
    method: "POST",
    data: { userId }
  });
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

module.exports = {
  mockLogin,
  fetchPendingImports,
  claimImport,
  fetchCards,
  fetchCard,
  updateCard,
  publishCard,
  duplicateCard,
  recordView,
  fetchStats,
  createRelay,
  fetchRelays,
  deleteRelay,
  followRelay,
  triggerMockImport,
  fetchImportNotifications
};
