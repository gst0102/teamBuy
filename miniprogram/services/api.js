const { buildApiUrl, request } = require("../utils/request");
const { withCachedMedia, withCachedCards } = require("../utils/media-cache");
const cachePolicy = require("../utils/cache-policy");

const NOTE_CACHE_PREFIX = "teambuy:notes-cache";
const SHOWCASE_CACHE_PREFIX = "teambuy:showcases-cache:v1";
const TOPIC_CACHE_PREFIX = "teambuy:topics-cache:v1";
const listCacheMemory = {
  showcases: {},
  topics: {}
};
const listCacheInFlight = {
  showcases: {},
  topics: {}
};
const noteCacheMemory = {};
const LIST_CACHE_MEMORY_MAX_ENTRIES = 16;
let listCacheGeneration = 0;
const noteListInFlight = {};
let noteListGeneration = 0;
const membershipCache = {};
const membershipInFlight = {};
let membershipCacheGeneration = 0;
const customerIntelligenceSummaryCache = {};
const customerIntelligenceSummaryInFlight = {};
let customerIntelligenceSummaryCacheGeneration = 0;
const notificationConfigCache = {};
const notificationConfigInFlight = {};
let notificationConfigCacheGeneration = 0;

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
  const structuredData = ((card.visibilityConfig || {}).structuredData) || {};
  const normalizedMedia = Array.isArray(card.media)
    ? card.media.map((item) => ({
        ...item,
        url: toAbsoluteUrl(item.url)
      }))
    : card.media;
  const firstImage = Array.isArray(normalizedMedia)
    ? normalizedMedia.find((item) => item && item.type === "image" && item.url)
    : null;
  const structuredCoverUrl = toAbsoluteUrl(structuredData.coverUrl);
  return {
    ...card,
    coverUrl: structuredCoverUrl || toAbsoluteUrl(card.coverUrl) || (firstImage && firstImage.url) || "",
    media: normalizedMedia
  };
}

function normalizeNotePayload(note) {
  if (!note || typeof note !== "object") return note;
  const visibilityConfig = note.visibilityConfig && typeof note.visibilityConfig === "object"
    ? { ...note.visibilityConfig }
    : note.visibilityConfig;
  if (visibilityConfig && visibilityConfig.shareSnapshot) {
    visibilityConfig.shareSnapshot = {
      ...visibilityConfig.shareSnapshot,
      url: toAbsoluteUrl(visibilityConfig.shareSnapshot.url)
    };
  }
  if (visibilityConfig && Array.isArray(visibilityConfig.shareSnapshotHistory)) {
    visibilityConfig.shareSnapshotHistory = visibilityConfig.shareSnapshotHistory.map((item) => ({
      ...item,
      url: toAbsoluteUrl(item && item.url)
    }));
  }
  return {
    ...note,
    visibilityConfig,
    coverUrl: toAbsoluteUrl(note.coverUrl),
    contentBlocks: Array.isArray(note.contentBlocks)
      ? note.contentBlocks.map((item) => ({
          ...item,
          url: toAbsoluteUrl(item && item.url),
          coverUrl: toAbsoluteUrl(item && item.coverUrl)
        }))
      : note.contentBlocks,
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

function authHeader() {
  const app = getApp();
  const user = (app && app.globalData && app.globalData.currentUser) || wx.getStorageSync("currentUser") || {};
  const authToken = String(user.authToken || "").trim();
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

function cacheScope() {
  const app = getApp();
  const data = (app && app.globalData) || {};
  return [data.environmentName || "", data.apiBaseUrl || "", data.apiRoutePrefix || ""].join("|");
}

function noteListCacheKey(params = {}) {
  const normalized = {
    ownerUserId: params.ownerUserId || "",
    keyword: params.keyword || "",
    categoryId: params.categoryId || "",
    sourceType: params.sourceType || "",
    systemCategory: params.systemCategory || "",
    tag: params.tag || "",
    topicId: params.topicId || "",
    sort: params.sort || "",
    includeDeleted: Boolean(params.includeDeleted)
  };
  return `${NOTE_CACHE_PREFIX}:list:${cacheScope()}:${JSON.stringify(normalized)}`;
}

function noteItemCacheKey(ownerUserId, noteId) {
  return `${NOTE_CACHE_PREFIX}:item:${cacheScope()}:${ownerUserId || ""}:${noteId || ""}`;
}

function readCache(key, options = {}) {
  const memory = noteCacheMemory[key];
  const ttl = options.allowStale ? cachePolicy.noteListStaleTtlMs : cachePolicy.noteListTtlMs;
  if (memory) {
    if (memory.savedAt && Date.now() - Number(memory.savedAt) <= ttl) return memory.data || null;
    delete noteCacheMemory[key];
    return null;
  }
  try {
    const item = wx.getStorageSync(key);
    if (!item || !item.savedAt) return null;
    if (Date.now() - Number(item.savedAt || 0) > ttl) return null;
    noteCacheMemory[key] = item;
    return item.data || null;
  } catch (error) {
    return null;
  }
}

function writeCache(key, data) {
  const value = { savedAt: Date.now(), data };
  noteCacheMemory[key] = value;
  try {
    if (typeof wx.setStorage === "function") wx.setStorage({ key, data: value });
    else wx.setStorageSync(key, value);
  } catch (error) {
    // Cache is a speed hint; network data remains the source of truth.
  }
}

function listCacheKey(prefix, ownerUserId) {
  return `${prefix}:${cacheScope()}:${ownerUserId || ""}`;
}

function readListCache(kind, prefix, ownerUserId) {
  const ttl = kind === "topics" ? cachePolicy.topicTtlMs : cachePolicy.showcaseListTtlMs;
  const key = listCacheKey(prefix, ownerUserId);
  const memory = listCacheMemory[kind][key];
  if (memory && Date.now() - Number(memory.savedAt || 0) <= ttl) {
    return memory.data;
  }
  try {
    const stored = wx.getStorageSync(key);
    if (stored && stored.savedAt && Date.now() - Number(stored.savedAt) <= ttl) {
      listCacheMemory[kind][key] = stored;
      return stored.data;
    }
  } catch (error) {}
  return null;
}

function writeListCache(kind, prefix, ownerUserId, data) {
  const key = listCacheKey(prefix, ownerUserId);
  const value = { savedAt: Date.now(), data: Array.isArray(data) ? data : [] };
  listCacheMemory[kind][key] = value;
  const keys = Object.keys(listCacheMemory[kind]);
  if (keys.length > LIST_CACHE_MEMORY_MAX_ENTRIES) {
    keys.sort((left, right) => Number(listCacheMemory[kind][left].savedAt || 0) - Number(listCacheMemory[kind][right].savedAt || 0));
    keys.slice(0, keys.length - LIST_CACHE_MEMORY_MAX_ENTRIES).forEach((oldKey) => delete listCacheMemory[kind][oldKey]);
  }
  try {
    if (typeof wx.setStorage === "function") wx.setStorage({ key, data: value });
    else wx.setStorageSync(key, value);
  } catch (error) {}
  return value.data;
}

function removeListCache(kind, prefix, ownerUserId) {
  const key = listCacheKey(prefix, ownerUserId);
  delete listCacheMemory[kind][key];
  try {
    if (typeof wx.removeStorage === "function") wx.removeStorage({ key });
    else wx.removeStorageSync(key);
  } catch (error) {}
}

function clearUserScopedCaches() {
  listCacheGeneration += 1;
  noteListGeneration += 1;
  membershipCacheGeneration += 1;
  customerIntelligenceSummaryCacheGeneration += 1;
  notificationConfigCacheGeneration += 1;
  Object.keys(listCacheMemory).forEach((kind) => { listCacheMemory[kind] = {}; });
  Object.keys(noteCacheMemory).forEach((key) => { delete noteCacheMemory[key]; });
  Object.keys(listCacheInFlight).forEach((kind) => { listCacheInFlight[kind] = {}; });
  Object.keys(noteListInFlight).forEach((key) => { delete noteListInFlight[key]; });
  Object.keys(membershipCache).forEach((key) => { delete membershipCache[key]; });
  Object.keys(membershipInFlight).forEach((key) => { delete membershipInFlight[key]; });
  Object.keys(customerIntelligenceSummaryCache).forEach((key) => { delete customerIntelligenceSummaryCache[key]; });
  Object.keys(customerIntelligenceSummaryInFlight).forEach((key) => { delete customerIntelligenceSummaryInFlight[key]; });
  Object.keys(notificationConfigCache).forEach((key) => { delete notificationConfigCache[key]; });
  Object.keys(notificationConfigInFlight).forEach((key) => { delete notificationConfigInFlight[key]; });
  try {
    const info = wx.getStorageInfoSync();
    const prefixes = [NOTE_CACHE_PREFIX, SHOWCASE_CACHE_PREFIX, TOPIC_CACHE_PREFIX];
    (info.keys || [])
      .filter((key) => prefixes.some((prefix) => key.startsWith(prefix)))
      .forEach((key) => {
        if (typeof wx.removeStorage === "function") wx.removeStorage({ key });
        else wx.removeStorageSync(key);
      });
  } catch (error) {}
}

function getCachedList(kind, prefix, ownerUserId) {
  const cached = readListCache(kind, prefix, ownerUserId);
  return Array.isArray(cached) ? cached : [];
}

function writeNoteItemCache(note) {
  if (!note || !note.id) return;
  writeCache(noteItemCacheKey(note.ownerUserId, note.id), note);
}

function invalidateNoteListCaches(ownerUserId) {
  noteListGeneration += 1;
  Object.keys(noteCacheMemory).forEach((key) => { delete noteCacheMemory[key]; });
  const ownerText = `"ownerUserId":"${ownerUserId || ""}`;
  Object.keys(noteListInFlight).forEach((key) => {
    if (!ownerUserId || key.includes(ownerText)) delete noteListInFlight[key];
  });
  try {
    const info = wx.getStorageInfoSync();
    const storageOwnerText = `"ownerUserId":"${ownerUserId || ""}"`;
    (info.keys || []).forEach((key) => {
      if (key.startsWith(`${NOTE_CACHE_PREFIX}:list:`) && (!ownerUserId || key.includes(storageOwnerText))) {
        if (typeof wx.removeStorage === "function") wx.removeStorage({ key });
        else wx.removeStorageSync(key);
      }
    });
  } catch (error) {
    // Cache invalidation is best effort.
  }
}

// The resource library has a separate metadata cache from the note list
// cache. Require it lazily so the store's dependency on this API module does
// not create an initialization cycle.
function invalidateResourceStoreCards(ownerUserId) {
  if (!ownerUserId) return;
  try {
    const resourceStore = require("../stores/resource-store");
    if (resourceStore && typeof resourceStore.invalidateCards === "function") {
      resourceStore.invalidateCards(ownerUserId);
    }
  } catch (error) {
    // The API remains the source of truth if the optional cache cannot be
    // invalidated.
  }
}

function getCachedNotes(params = {}, options = {}) {
  return readCache(noteListCacheKey(params), options) || [];
}

function hasCachedNotes(params = {}, options = {}) {
  const cached = readCache(noteListCacheKey(params), options);
  return Array.isArray(cached);
}

function getCachedNote(noteId, ownerUserId) {
  return readCache(noteItemCacheKey(ownerUserId, noteId));
}

function normalizeShowcasePayload(showcase) {
  if (!showcase || typeof showcase !== "object") return showcase;
  return {
    ...showcase,
    bannerUrl: toAbsoluteUrl(showcase.bannerUrl),
    shareSnapshot: showcase.shareSnapshot
      ? { ...showcase.shareSnapshot, url: toAbsoluteUrl(showcase.shareSnapshot.url) }
      : showcase.shareSnapshot,
    shareSnapshotHistory: Array.isArray(showcase.shareSnapshotHistory)
      ? showcase.shareSnapshotHistory.map((item) => ({ ...item, url: toAbsoluteUrl(item && item.url) }))
      : showcase.shareSnapshotHistory,
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

function getWecomBindStatus(userId) {
  return request({
    url: `/api/auth/wecom-bind-status?userId=${encodeURIComponent(userId || "")}`
  });
}

function bindWecomCard(token, userId) {
  return request({
    url: "/api/auth/wecom-bind-card",
    method: "POST",
    data: { token, userId }
  });
}

function createH5Ticket(payload) {
  return request({
    url: "/api/auth/h5-ticket",
    method: "POST",
    data: payload
  });
}

function fetchNotes(params = {}, options = {}) {
  const key = noteListCacheKey(params);
  const cached = !options.force ? readCache(key) : null;
  if (Array.isArray(cached)) return Promise.resolve({ data: cached, cached: true });
  if (!options.force && noteListInFlight[key]) return noteListInFlight[key];
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
  const generation = noteListGeneration;
  const promise = request({
    url: `/api/notes${suffix}`
  }).then(async (res) => {
    const data = Array.isArray(res.data)
      ? options.metadataOnly
        ? res.data.map(normalizeNotePayload)
        : await Promise.all(res.data.map(normalizeAndCacheNote))
      : res.data;
    if (Array.isArray(data)) {
      if (generation === noteListGeneration) writeCache(key, data);
      // A metadata list must not overwrite the detail cache with a partial
      // payload. Full note detail is cached only after a full fetch.
      if (!options.metadataOnly) data.forEach(writeNoteItemCache);
    }
    return { ...res, data };
  }).finally(() => {
    if (noteListInFlight[key] === promise) delete noteListInFlight[key];
  });
  noteListInFlight[key] = promise;
  return promise;
}

function fetchBusinessCardSummary(ownerUserId) {
  return request({
    url: `/api/notes/business-card-summary?ownerUserId=${encodeURIComponent(ownerUserId || "")}`
  });
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
  })).then((res) => {
    writeNoteItemCache(res.data);
    invalidateNoteListCaches(payload.ownerUserId);
    invalidateResourceStoreCards(payload.ownerUserId);
    return res;
  });
}

function createQuickNoteCapture(payload) {
  return request({
    url: "/api/notes/quick-capture",
    method: "POST",
    data: payload
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  })).then((res) => {
    writeNoteItemCache(res.data);
    invalidateNoteListCaches(payload.ownerUserId);
    invalidateResourceStoreCards(payload.ownerUserId);
    return res;
  });
}

function createLinkNoteCapture(payload) {
  return request({
    url: "/api/notes/link-capture",
    method: "POST",
    data: payload
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  })).then((res) => {
    writeNoteItemCache(res.data);
    invalidateNoteListCaches(payload.ownerUserId);
    invalidateResourceStoreCards(payload.ownerUserId);
    return res;
  });
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
  })).then((res) => {
    invalidateNoteListCaches(payload.ownerUserId);
    invalidateShowcasesCache(payload.ownerUserId);
    invalidateResourceStoreCards(payload.ownerUserId);
    return res;
  });
}

function getCachedTopics(ownerUserId) {
  return getCachedList("topics", TOPIC_CACHE_PREFIX, ownerUserId);
}

function fetchTopics(ownerUserId, options = {}) {
  const cached = !options.force ? readListCache("topics", TOPIC_CACHE_PREFIX, ownerUserId) : null;
  if (Array.isArray(cached)) return Promise.resolve({ data: cached, cached: true });
  const key = listCacheKey(TOPIC_CACHE_PREFIX, ownerUserId);
  if (!options.force && listCacheInFlight.topics[key]) return listCacheInFlight.topics[key];
  const generation = listCacheGeneration;
  const promise = request({ url: `/api/notes/topics?ownerUserId=${ownerUserId}` })
    .then((res) => ({
      ...res,
      data: generation === listCacheGeneration
        ? writeListCache("topics", TOPIC_CACHE_PREFIX, ownerUserId, res.data)
        : res.data
    }))
    .finally(() => {
      if (listCacheInFlight.topics[key] === promise) delete listCacheInFlight.topics[key];
    });
  listCacheInFlight.topics[key] = promise;
  return promise;
}

function invalidateTopicsCache(ownerUserId) {
  removeListCache("topics", TOPIC_CACHE_PREFIX, ownerUserId);
}

function createDemoData(ownerUserId) {
  return request({
    url: `/api/notes/demo-data?ownerUserId=${ownerUserId}`,
    method: "POST"
  }).then((res) => {
    invalidateNoteListCaches(ownerUserId);
    invalidateShowcasesCache(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return res;
  });
}

function cleanupDemoData(ownerUserId) {
  return request({
    url: `/api/notes/demo-data/cleanup?ownerUserId=${ownerUserId}`,
    method: "POST"
  }).then((res) => {
    invalidateNoteListCaches(ownerUserId);
    invalidateShowcasesCache(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return res;
  });
}

function createTopic(payload) {
  return request({
    url: "/api/notes/topics",
    method: "POST",
    data: payload
  }).then((res) => {
    invalidateTopicsCache(payload.ownerUserId);
    return res;
  });
}

function deleteTopic(topicId, ownerUserId) {
  return request({
    url: `/api/notes/topics/${topicId}?ownerUserId=${ownerUserId}`,
    method: "DELETE"
  }).then((res) => {
    invalidateTopicsCache(ownerUserId);
    return res;
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
  })).then((res) => {
    invalidateNoteListCaches(ownerUserId);
    invalidateTopicsCache(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return res;
  });
}

function removeNoteFromTopic(noteId, topicId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}/topics/${topicId}?ownerUserId=${ownerUserId}`,
    method: "DELETE"
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  })).then((res) => {
    invalidateNoteListCaches(ownerUserId);
    invalidateTopicsCache(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return res;
  });
}

function fetchNote(noteId, ownerUserId, options = {}) {
  const cached = !options.force && getCachedNote(noteId, ownerUserId);
  if (cached) return Promise.resolve({ data: cached, cached: true });
  return request({
    url: `/api/notes/${noteId}?ownerUserId=${ownerUserId}`
  }).then(async (res) => {
    const data = await normalizeAndCacheNote(res.data);
    writeNoteItemCache(data);
    return { ...res, data };
  });
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
  }).then(async (res) => {
    const data = await normalizeAndCacheNote(res.data);
    writeNoteItemCache(data);
    invalidateNoteListCaches(payload.ownerUserId);
    invalidateShowcasesCache(payload.ownerUserId);
    invalidateResourceStoreCards(payload.ownerUserId);
    return { ...res, data };
  });
}

function saveNoteShareSnapshot(noteId, payload) {
  return request({
    url: `/api/notes/${noteId}/share-snapshot`,
    method: "PATCH",
    data: payload
  }).then(async (res) => {
    const data = await normalizeAndCacheNote(res.data);
    writeNoteItemCache(data);
    invalidateNoteListCaches(payload.ownerUserId);
    invalidateResourceStoreCards(payload.ownerUserId);
    return { ...res, data };
  });
}

function publishNote(noteId, ownerUserId, expectedRevision) {
  return request({
    url: `/api/notes/${noteId}/publish`,
    method: "POST",
    data: { ownerUserId, expectedRevision }
  }).then(async (res) => {
    const data = await normalizeAndCacheNote(res.data);
    writeNoteItemCache(data);
    invalidateNoteListCaches(ownerUserId);
    invalidateShowcasesCache(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return { ...res, data };
  });
}

function revokeNote(noteId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}/revoke`,
    method: "POST",
    data: { ownerUserId }
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  })).then((res) => {
    invalidateNoteListCaches(ownerUserId);
    invalidateShowcasesCache(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return res;
  });
}

function duplicateNote(noteId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}/duplicate`,
    method: "POST",
    data: { ownerUserId }
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  })).then((res) => {
    writeNoteItemCache(res.data);
    invalidateNoteListCaches(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return res;
  });
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
  }).then((res) => {
    invalidateNoteListCaches(payload.ownerUserId);
    invalidateShowcasesCache(payload.ownerUserId);
    invalidateResourceStoreCards(payload.ownerUserId);
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
  })).then((res) => {
    writeNoteItemCache(res.data);
    invalidateNoteListCaches(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return res;
  });
}

function generateNote(noteId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}/generate?ownerUserId=${ownerUserId}`,
    method: "POST"
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheNote(res.data)
  })).then((res) => {
    writeNoteItemCache(res.data);
    invalidateNoteListCaches(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return res;
  });
}

function confirmNoteType(noteId, payload) {
  return request({
    url: `/api/notes/${noteId}/confirm-type`,
    method: "POST",
    data: payload
  }).then(async (res) => {
    const data = await normalizeAndCacheNote(res.data);
    writeNoteItemCache(data);
    invalidateNoteListCaches(payload.ownerUserId);
    invalidateResourceStoreCards(payload.ownerUserId);
    return { ...res, data };
  });
}

function deleteNote(noteId, ownerUserId) {
  return request({
    url: `/api/notes/${noteId}?ownerUserId=${ownerUserId}`,
    method: "DELETE"
  }).then((res) => {
    invalidateNoteListCaches(ownerUserId);
    invalidateShowcasesCache(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return res;
  });
}

function fetchCards(params = {}, options = {}) {
  const query = [];
  if (params.ownerUserId) query.push(`ownerUserId=${params.ownerUserId}`);
  if (params.keyword) query.push(`keyword=${encodeURIComponent(params.keyword)}`);
  if (params.categoryId) query.push(`categoryId=${params.categoryId}`);
  if (Number.isFinite(Number(params.limit))) query.push(`limit=${Math.max(1, Number(params.limit))}`);
  if (Number.isFinite(Number(params.offset)) && Number(params.offset) > 0) query.push(`offset=${Number(params.offset)}`);
  const suffix = query.length ? `?${query.join("&")}` : "";
  return request({
    url: `/api/cards${suffix}`
  }).then(async (res) => ({
    ...res,
    data: Array.isArray(res.data)
      ? options.metadataOnly
        ? res.data.map(normalizeCardPayload)
        : await normalizeAndCacheCards(res.data)
      : res.data
  }));
}

function fetchCardsMetadata(params = {}) {
  return fetchCards(params, { metadataOnly: true });
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
  })).then((res) => {
    invalidateResourceStoreCards(payload.ownerUserId);
    return res;
  });
}

function uploadAsset({ filePath, mediaType = "image", ownerUserId = "" }) {
  const app = getApp();
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: buildApiUrl("/api/uploads/asset"),
      filePath,
      name: "file",
      header: authHeader(),
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
          const asset = data && data.data;
          if (!asset || !asset.url) {
            reject({ detail: (data && (data.message || data.detail)) || "上传成功但未返回文件地址" });
            return;
          }
          resolve({
            ...asset,
            url: toAbsoluteUrl(asset.url),
            displayUrl: toAbsoluteUrl(asset.url)
          });
          return;
        }
        reject({ ...data, detail: data.detail || data.message || `上传失败（${res.statusCode || "无状态码"}）` });
      },
      fail(err) {
        reject({ ...err, detail: "头像或图片上传失败，请检查网络后重试" });
      }
    });
  });
}

function uploadShareSnapshot({ filePath, ownerUserId = "" }) {
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: buildApiUrl("/api/uploads/share-snapshot"),
      filePath,
      name: "file",
      header: authHeader(),
      formData: { ownerUserId },
      success(res) {
        let data = {};
        try {
          data = JSON.parse(res.data);
        } catch (error) {
          reject({ detail: "分享图上传返回解析失败" });
          return;
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          const asset = data && data.data;
          if (!asset || !asset.url) {
            reject({ detail: (data && (data.message || data.detail)) || "分享图上传成功但未返回地址" });
            return;
          }
          resolve({
            ...asset,
            url: toAbsoluteUrl(asset.url),
            displayUrl: toAbsoluteUrl(asset.url)
          });
          return;
        }
        reject({ ...data, detail: data.detail || data.message || `分享图上传失败（${res.statusCode || "无状态码"}）` });
      },
      fail(err) {
        reject({ ...err, detail: "分享图上传失败，请检查网络后重试" });
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
      header: authHeader(),
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
          invalidateNoteListCaches(ownerUserId);
          invalidateResourceStoreCards(ownerUserId);
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
  })).then((res) => {
    invalidateNoteListCaches(ownerUserId);
    invalidateResourceStoreCards(ownerUserId);
    return res;
  });
}

function getCachedShowcases(ownerUserId) {
  return getCachedList("showcases", SHOWCASE_CACHE_PREFIX, ownerUserId).map(normalizeShowcasePayload);
}

function fetchShowcases(ownerUserId, options = {}) {
  const cached = !options.force ? readListCache("showcases", SHOWCASE_CACHE_PREFIX, ownerUserId) : null;
  if (Array.isArray(cached)) return Promise.resolve({ data: cached.map(normalizeShowcasePayload), cached: true });
  const key = listCacheKey(SHOWCASE_CACHE_PREFIX, ownerUserId);
  if (!options.force && listCacheInFlight.showcases[key]) return listCacheInFlight.showcases[key];
  const generation = listCacheGeneration;
  const promise = request({
    url: `/api/showcases?ownerUserId=${encodeURIComponent(ownerUserId)}`
  }).then((res) => {
    const data = Array.isArray(res.data) ? res.data.map(normalizeShowcasePayload) : [];
    return {
      ...res,
      data: generation === listCacheGeneration
        ? writeListCache("showcases", SHOWCASE_CACHE_PREFIX, ownerUserId, data)
        : data
    };
  }).finally(() => {
    if (listCacheInFlight.showcases[key] === promise) delete listCacheInFlight.showcases[key];
  });
  listCacheInFlight.showcases[key] = promise;
  return promise;
}

function invalidateShowcasesCache(ownerUserId) {
  removeListCache("showcases", SHOWCASE_CACHE_PREFIX, ownerUserId);
}

function createShowcase(payload) {
  return request({
    url: "/api/showcases",
    method: "POST",
    data: payload
  }).then((res) => ({
    ...res,
    data: normalizeShowcasePayload(res.data)
  })).then((res) => {
    invalidateShowcasesCache(payload.ownerUserId);
    return res;
  });
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
  })).then((res) => {
    invalidateShowcasesCache(payload.ownerUserId);
    return res;
  });
}

function saveShowcaseShareSnapshot(showcaseId, payload) {
  return request({
    url: `/api/showcases/${showcaseId}/share-snapshot`,
    method: "PATCH",
    data: payload
  }).then((res) => ({
    ...res,
    data: normalizeShowcasePayload(res.data)
  })).then((res) => {
    invalidateShowcasesCache(payload.ownerUserId);
    return res;
  });
}

function publishShowcase(showcaseId, ownerUserId) {
  return request({
    url: `/api/showcases/${showcaseId}/publish`,
    method: "POST",
    data: { ownerUserId }
  }).then((res) => ({
    ...res,
    data: normalizeShowcasePayload(res.data)
  })).then((res) => {
    invalidateShowcasesCache(ownerUserId);
    return res;
  });
}

function archiveShowcase(showcaseId, ownerUserId) {
  return request({
    url: `/api/showcases/${showcaseId}/archive`,
    method: "POST",
    data: { ownerUserId }
  }).then((res) => ({
    ...res,
    data: normalizeShowcasePayload(res.data)
  })).then((res) => {
    invalidateShowcasesCache(ownerUserId);
    return res;
  });
}

function deleteShowcase(showcaseId, ownerUserId) {
  return request({
    url: `/api/showcases/${showcaseId}/delete`,
    method: "POST",
    data: { ownerUserId }
  }).then((res) => {
    invalidateShowcasesCache(ownerUserId);
    return res;
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

function fetchCustomerIntelligence(ownerUserId, requesterUserId = ownerUserId, mode = "", options = {}) {
  const query = [
    `ownerUserId=${encodeURIComponent(ownerUserId)}`,
    `requesterUserId=${encodeURIComponent(requesterUserId)}`
  ];
  if (mode) query.push(`mode=${encodeURIComponent(mode)}`);
  if (options && options.force) query.push("refresh=1");
  return request({ url: `/api/scrm/customer-intelligence?${query.join("&")}` });
}

function fetchCustomerIntelligenceSummary(ownerUserId, requesterUserId = ownerUserId, mode = "", options = {}) {
  const query = [
    `ownerUserId=${encodeURIComponent(ownerUserId)}`,
    `requesterUserId=${encodeURIComponent(requesterUserId)}`
  ];
  if (mode) query.push(`mode=${encodeURIComponent(mode)}`);
  if (options && options.force) query.push("refresh=1");
  const key = customerIntelligenceSummaryCacheKey(ownerUserId, requesterUserId, mode);
  const cached = customerIntelligenceSummaryCache[key];
  if (!options.force && cached && Date.now() - cached.savedAt <= cachePolicy.customerIntelligenceTtlMs) {
    return Promise.resolve({ ...cached.response, cached: true });
  }
  if (customerIntelligenceSummaryInFlight[key]) return customerIntelligenceSummaryInFlight[key];
  const generation = customerIntelligenceSummaryCacheGeneration;
  const promise = request({ url: `/api/scrm/customer-intelligence/summary?${query.join("&")}` })
    .then((response) => {
      if (generation === customerIntelligenceSummaryCacheGeneration) {
        customerIntelligenceSummaryCache[key] = { savedAt: Date.now(), response };
      }
      return response;
    })
    .finally(() => {
      if (customerIntelligenceSummaryInFlight[key] === promise) delete customerIntelligenceSummaryInFlight[key];
    });
  customerIntelligenceSummaryInFlight[key] = promise;
  return promise;
}

function customerIntelligenceSummaryCacheKey(ownerUserId, requesterUserId, mode) {
  return `${cacheScope()}:${ownerUserId || ""}:${requesterUserId || ""}:${mode || ""}`;
}

function clearCustomerIntelligenceSummaryCache(ownerUserId) {
  customerIntelligenceSummaryCacheGeneration += 1;
  const prefix = `${cacheScope()}:${ownerUserId || ""}:`;
  Object.keys(customerIntelligenceSummaryCache).forEach((key) => {
    if (key.startsWith(prefix)) delete customerIntelligenceSummaryCache[key];
  });
  Object.keys(customerIntelligenceSummaryInFlight).forEach((key) => {
    if (key.startsWith(prefix)) delete customerIntelligenceSummaryInFlight[key];
  });
}

function fetchCustomerDetail(ownerUserId, requesterUserId, customerId, mode = "", leadId = "") {
  const query = [
    `ownerUserId=${encodeURIComponent(ownerUserId || "")}`,
    `requesterUserId=${encodeURIComponent(requesterUserId || ownerUserId || "")}`
  ];
  if (mode) query.push(`mode=${encodeURIComponent(mode)}`);
  if (leadId) {
    // leadId is the canonical identity after a follow-up record exists.
    // Never let a legacy customer alias compete with it at the API boundary.
    query.push(`leadId=${encodeURIComponent(leadId)}`);
  } else {
    query.push(`customerId=${encodeURIComponent(customerId || "")}`);
  }
  return request({ url: `/api/scrm/customer-detail?${query.join("&")}` });
}

function actOnCustomerFollowup(payload = {}) {
  const normalizedPayload = payload.leadId
    ? { ...payload, customerId: "" }
    : payload;
  return request({
    url: "/api/scrm/customer-followups/action",
    method: "POST",
    data: normalizedPayload
  });
}

function membershipCacheKey(userId) {
  return `${cacheScope()}:${userId || ""}`;
}

function clearMembershipCache(userId) {
  membershipCacheGeneration += 1;
  const key = membershipCacheKey(userId);
  delete membershipCache[key];
  delete membershipInFlight[key];
  clearCustomerIntelligenceSummaryCache(userId);
  clearNotificationConfigCache(userId);
}

function fetchMembership(userId, options = {}) {
  const key = membershipCacheKey(userId);
  const cached = membershipCache[key];
  if (!options.force && cached && Date.now() - cached.savedAt <= cachePolicy.membershipTtlMs) {
    return Promise.resolve({ ...cached.response, cached: true });
  }
  if (membershipInFlight[key]) return membershipInFlight[key];
  const generation = membershipCacheGeneration;
  const promise = request({ url: `/api/scrm/membership?userId=${encodeURIComponent(userId)}` })
    .then((response) => {
      if (generation === membershipCacheGeneration) membershipCache[key] = { savedAt: Date.now(), response };
      return response;
    })
    .finally(() => {
      if (membershipInFlight[key] === promise) delete membershipInFlight[key];
    });
  membershipInFlight[key] = promise;
  return promise;
}

function notificationConfigCacheKey(userId) {
  return `${cacheScope()}:${userId || ""}`;
}

function clearNotificationConfigCache(userId) {
  notificationConfigCacheGeneration += 1;
  const key = notificationConfigCacheKey(userId);
  delete notificationConfigCache[key];
  delete notificationConfigInFlight[key];
}

function fetchNotificationConfig(userId, options = {}) {
  const key = notificationConfigCacheKey(userId);
  const cached = notificationConfigCache[key];
  if (!options.force && cached && Date.now() - cached.savedAt <= cachePolicy.notificationConfigTtlMs) {
    return Promise.resolve({ ...cached.response, cached: true });
  }
  if (notificationConfigInFlight[key]) return notificationConfigInFlight[key];
  const generation = notificationConfigCacheGeneration;
  const promise = request({ url: `/api/scrm/notification-config?userId=${encodeURIComponent(userId)}` })
    .then((response) => {
      if (generation === notificationConfigCacheGeneration) {
        notificationConfigCache[key] = { savedAt: Date.now(), response };
      }
      return response;
    })
    .finally(() => {
      if (notificationConfigInFlight[key] === promise) delete notificationConfigInFlight[key];
    });
  notificationConfigInFlight[key] = promise;
  return promise;
}

function recordNotificationSubscription(payload) {
  return request({
    url: "/api/scrm/notification-subscriptions",
    method: "POST",
    data: payload
  });
}

function updateNotificationPreferences(payload) {
  return request({
    url: "/api/scrm/notification-preferences",
    method: "PUT",
    data: payload
  }).then((response) => {
    clearNotificationConfigCache(payload.userId);
    return response;
  });
}

function createMembershipOrder(userId) {
  return request({ url: "/api/scrm/membership/orders", method: "POST", data: { userId } });
}

function createMembershipPayment(orderId, userId) {
  return request({
    url: `/api/scrm/membership/orders/${orderId}/pay`,
    method: "POST",
    data: { userId }
  });
}

function confirmTestMembershipOrder(orderId, transactionId) {
  return request({
    url: `/api/scrm/membership/orders/${orderId}/test-confirm`,
    method: "POST",
    data: { transactionId }
  });
}

function fetchReferralCenter(userId) {
  return request({ url: `/api/scrm/referrals?userId=${encodeURIComponent(userId)}` });
}

function bindReferral(inviteeUserId, inviteCode) {
  return request({ url: "/api/scrm/referrals/bind", method: "POST", data: { inviteeUserId, inviteCode } });
}

function bindReferralFromShare(inviteeUserId, inviterUserId, source = "share_link") {
  return request({
    url: "/api/scrm/referrals/share-bind",
    method: "POST",
    data: { inviteeUserId, inviterUserId, source }
  });
}

function createReferralWithdrawal(userId, amountFen) {
  return request({ url: "/api/scrm/referrals/withdrawals", method: "POST", data: { userId, amountFen } });
}

function generateSameStyle(payload) {
  return request({ url: "/api/scrm/same-style/generate", method: "POST", data: payload }).then((res) => {
    invalidateNoteListCaches(payload && payload.ownerUserId);
    invalidateShowcasesCache(payload && payload.ownerUserId);
    return res;
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
  })).then((res) => {
    invalidateResourceStoreCards(payload.ownerUserId);
    return res;
  });
}

function deleteCard(cardId, ownerUserId) {
  return request({
    url: `/api/cards/${cardId}?ownerUserId=${ownerUserId}`,
    method: "DELETE"
  }).then((res) => {
    invalidateResourceStoreCards(ownerUserId);
    return res;
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
  })).then((res) => {
    invalidateResourceStoreCards(userId);
    return res;
  });
}

function duplicateCard(cardId, userId) {
  return request({
    url: `/api/cards/${cardId}/duplicate`,
    method: "POST",
    data: { userId }
  }).then(async (res) => ({
    ...res,
    data: await normalizeAndCacheCard(res.data)
  })).then((res) => {
    invalidateResourceStoreCards(userId);
    return res;
  });
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

function fetchViewHistory(userId, limit = 30) {
  return request({
    url: `/api/view-history?userId=${encodeURIComponent(userId || "")}&limit=${Math.min(Math.max(Number(limit) || 30, 1), 50)}`
  });
}

function recordNoteInteraction(noteId, payload) {
  return request({
    url: `/api/notes/${noteId}/events`,
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

function fetchOpportunityLeads(params = {}) {
  const query = [];
  ["keyword", "userId", "city", "industry", "demandType", "contactStatus"].forEach((key) => {
    if (params[key]) query.push(`${key}=${encodeURIComponent(params[key])}`);
  });
  const suffix = query.length ? `?${query.join("&")}` : "";
  return request({ url: `/api/opportunity-leads${suffix}` });
}

function fetchOpportunityLead(leadId) {
  return request({ url: `/api/opportunity-leads/${leadId}` });
}

function fetchSavedOpportunityLeads(userId, params = {}) {
  const query = [`userId=${encodeURIComponent(userId)}`];
  ["status", "keyword", "packageStatus"].forEach((key) => {
    if (params[key]) query.push(`${key}=${encodeURIComponent(params[key])}`);
  });
  return request({ url: `/api/opportunity-leads/saved?${query.join("&")}` });
}

function saveOpportunityLead(leadId, payload) {
  return request({
    url: `/api/opportunity-leads/${leadId}/save`,
    method: "POST",
    data: payload
  });
}

function addOpportunityFollowup(leadId, payload) {
  return request({
    url: `/api/opportunity-leads/${leadId}/followups`,
    method: "POST",
    data: payload
  });
}

function unlockOpportunityContact(leadId, payload) {
  return request({
    url: `/api/opportunity-leads/${leadId}/unlock-contact`,
    method: "POST",
    data: payload
  });
}

function previewResponsePackage(leadId, payload) {
  return request({
    url: `/api/opportunity-leads/${leadId}/response-packages/preview`,
    method: "POST",
    data: payload
  });
}

function createResponsePackage(leadId, payload) {
  return request({
    url: `/api/opportunity-leads/${leadId}/response-packages`,
    method: "POST",
    data: payload
  });
}

function fetchResponsePackage(packageId, ownerUserId) {
  return request({
    url: `/api/response-packages/${packageId}?ownerUserId=${encodeURIComponent(ownerUserId)}`
  });
}

function recordResponsePackageEvent(packageId, payload) {
  return request({
    url: `/api/response-packages/${packageId}/events`,
    method: "POST",
    data: payload
  });
}

function fetchResponsePackageRadar(packageId, ownerUserId) {
  return request({
    url: `/api/response-packages/${packageId}/radar?ownerUserId=${encodeURIComponent(ownerUserId)}`
  });
}

function fetchOpportunitySubscriptions(userId) {
  return request({ url: `/api/opportunity-subscriptions/me?userId=${encodeURIComponent(userId)}` });
}

function saveOpportunitySubscription(payload) {
  return request({
    url: "/api/opportunity-subscriptions",
    method: "POST",
    data: payload
  });
}

function fetchSupplyDemandCards(params = {}) {
  const query = [];
  ["keyword", "city", "industry", "demandType", "cardType", "contactStatus"].forEach((key) => {
    if (params[key]) query.push(`${key}=${encodeURIComponent(params[key])}`);
  });
  return request({ url: `/api/supply-demand/cards${query.length ? `?${query.join("&")}` : ""}` });
}

function fetchMySupplyDemandCards(userId) {
  return request({ url: `/api/supply-demand/cards/me?userId=${encodeURIComponent(userId)}` });
}

function fetchSupplyDemandCard(cardId, userId) {
  const query = userId ? `?userId=${encodeURIComponent(userId)}` : "";
  return request({ url: `/api/supply-demand/cards/${cardId}${query}` });
}

function saveSupplyDemandCard(payload) {
  return request({
    url: "/api/supply-demand/cards",
    method: "POST",
    data: payload
  });
}

function updateSupplyDemandCard(cardId, payload) {
  return request({
    url: `/api/supply-demand/cards/${cardId}`,
    method: "PUT",
    data: payload
  });
}

function submitSupplyDemandCard(cardId, userId) {
  return request({
    url: `/api/supply-demand/cards/${cardId}/submit`,
    method: "POST",
    data: { userId }
  });
}

function applySupplyDemandCard(cardId, payload) {
  return request({
    url: `/api/supply-demand/cards/${cardId}/applications`,
    method: "POST",
    data: payload
  });
}

function fetchSupplyDemandApplications(userId, role = "owner") {
  return request({
    url: `/api/supply-demand/cards/applications?userId=${encodeURIComponent(userId)}&role=${encodeURIComponent(role)}`
  });
}

function reviewSupplyDemandApplication(applicationId, payload) {
  return request({
    url: `/api/supply-demand/cards/applications/${applicationId}/review`,
    method: "POST",
    data: payload
  });
}

function fetchOpportunityPushDigests(userId) {
  return request({ url: `/api/opportunity-push-digests?userId=${encodeURIComponent(userId)}` });
}

function generateOpportunityPushDigest(userId) {
  return request({
    url: "/api/opportunity-push-digests/generate",
    method: "POST",
    data: { userId }
  });
}

function markOpportunityPushDigestRead(digestId, userId) {
  return request({
    url: `/api/opportunity-push-digests/${digestId}/read`,
    method: "POST",
    data: { userId }
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
  getWecomBindStatus,
  bindWecomCard,
  createH5Ticket,
  fetchNotes,
  fetchBusinessCardSummary,
  getCachedNotes,
  hasCachedNotes,
  clearUserScopedCaches,
  clearMembershipCache,
  clearCustomerIntelligenceSummaryCache,
  fetchTagSuggestions,
  createManualNoteDraft,
  createQuickNoteCapture,
  createLinkNoteCapture,
  parsePropertyBatch,
  createPropertyBatch,
  getCachedTopics,
  fetchTopics,
  createDemoData,
  cleanupDemoData,
  createTopic,
  deleteTopic,
  addNoteToTopic,
  removeNoteFromTopic,
  fetchNote,
  getCachedNote,
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
  saveNoteShareSnapshot,
  publishNote,
  revokeNote,
  duplicateNote,
  clonePropertySame,
  organizeNote,
  generateNote,
  confirmNoteType,
  deleteNote,
  fetchCards,
  fetchCardsMetadata,
  fetchCard,
  fetchCategories,
  createCategory,
  deleteCategory,
  createCard,
  uploadAsset,
  uploadShareSnapshot,
  uploadImageNote,
  recognizeNoteImage,
  getCachedShowcases,
  fetchShowcases,
  createShowcase,
  fetchShowcase,
  updateShowcase,
  saveShowcaseShareSnapshot,
  publishShowcase,
  archiveShowcase,
  deleteShowcase,
  recordShowcaseEvent,
  fetchShowcaseAnalytics,
  fetchPublicShowcase,
  fetchBusinessDashboard,
  fetchCustomerIntelligence,
  fetchCustomerIntelligenceSummary,
  fetchCustomerDetail,
  actOnCustomerFollowup,
  fetchMembership,
  fetchNotificationConfig,
  recordNotificationSubscription,
  updateNotificationPreferences,
  createMembershipOrder,
  createMembershipPayment,
  confirmTestMembershipOrder,
  fetchReferralCenter,
  bindReferral,
  bindReferralFromShare,
  createReferralWithdrawal,
  generateSameStyle,
  updateCard,
  deleteCard,
  publishCard,
  duplicateCard,
  recordView,
  recordNoteView,
  fetchViewHistory,
  recordNoteInteraction,
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
  deleteLeadReminder,
  fetchOpportunityLeads,
  fetchOpportunityLead,
  fetchSavedOpportunityLeads,
  saveOpportunityLead,
  addOpportunityFollowup,
  unlockOpportunityContact,
  previewResponsePackage,
  createResponsePackage,
  fetchResponsePackage,
  recordResponsePackageEvent,
  fetchResponsePackageRadar,
  fetchOpportunitySubscriptions,
  saveOpportunitySubscription,
  fetchSupplyDemandCards,
  fetchMySupplyDemandCards,
  fetchSupplyDemandCard,
  saveSupplyDemandCard,
  updateSupplyDemandCard,
  submitSupplyDemandCard,
  applySupplyDemandCard,
  fetchSupplyDemandApplications,
  reviewSupplyDemandApplication,
  fetchOpportunityPushDigests,
  generateOpportunityPushDigest,
  markOpportunityPushDigestRead
};
