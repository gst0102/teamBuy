const api = require("../services/api");
const cachePolicy = require("../utils/cache-policy");

const state = {
  cardsByOwner: {},
  categoriesByOwner: {},
  cardsById: {},
  cardsSavedAtByOwner: {},
  categoriesSavedAtByOwner: {},
  cardsRefreshByOwner: {},
  cardsCacheGenerationByOwner: {}
};

// Bump when the card payload contract changes.  This prevents an older
// resource list (without sourceNoteId/shareState) from masking the current
// share actions after a mini-program update.
const CACHE_SCHEMA_VERSION = "v2";
const CARD_CACHE_TTL_MS = cachePolicy.resourceListTtlMs;
const CARD_CACHE_STALE_TTL_MS = cachePolicy.resourceListStaleTtlMs;
const CATEGORY_CACHE_TTL_MS = cachePolicy.categoryTtlMs;
const CATEGORY_CACHE_STALE_TTL_MS = cachePolicy.categoryStaleTtlMs;

function isWithinTtl(savedAt, ttlMs) {
  return Boolean(savedAt) && Date.now() - savedAt < ttlMs;
}

function environmentScope() {
  try {
    const app = getApp();
    const globalData = (app && app.globalData) || {};
    return [globalData.environmentName, globalData.apiBaseUrl, globalData.apiRoutePrefix].join("|")
      .replace(/[^a-zA-Z0-9_.:-]/g, "_");
  } catch (error) {
    return "default";
  }
}

function ownerKey(ownerUserId) {
  return ownerUserId || "all";
}

function cardCacheKey(ownerUserId, cardId) {
  return `${ownerKey(ownerUserId)}:${cardId || ""}`;
}

function currentOwnerUserId() {
  try {
    const app = getApp();
    const currentUser = (app && app.globalData && app.globalData.currentUser) || wx.getStorageSync("currentUser") || {};
    return currentUser.id || "";
  } catch (error) {
    return "";
  }
}

function storageKey(type, ownerUserId) {
  return `resourceStore_${CACHE_SCHEMA_VERSION}_${environmentScope()}_${type}_${ownerKey(ownerUserId)}`;
}

function persistStorage(key, data) {
  try {
    if (typeof wx.setStorage === "function") wx.setStorage({ key, data });
    else wx.setStorageSync(key, data);
  } catch (error) {
    // Cache is an acceleration layer; the API remains the source of truth.
  }
}

function removeStorage(key) {
  try {
    if (typeof wx.removeStorage === "function") wx.removeStorage({ key });
    else wx.removeStorageSync(key);
  } catch (error) {}
}

function setCards(ownerUserId, cards = []) {
  const key = ownerKey(ownerUserId);
  const savedAt = Date.now();
  state.cardsByOwner[key] = Array.isArray(cards) ? cards : [];
  state.cardsSavedAtByOwner[key] = savedAt;
  state.cardsByOwner[key].forEach((card) => {
    if (card && card.id) state.cardsById[cardCacheKey(card.ownerUserId || ownerUserId, card.id)] = card;
  });
  persistStorage(storageKey("cards", ownerUserId), { savedAt, cards: state.cardsByOwner[key] });
  return state.cardsByOwner[key];
}

function rememberCards(ownerUserId, cards = []) {
  return setCards(ownerUserId, cards);
}

function setCategories(ownerUserId, categories = []) {
  const key = ownerKey(ownerUserId);
  const savedAt = Date.now();
  state.categoriesByOwner[key] = Array.isArray(categories) ? categories : [];
  state.categoriesSavedAtByOwner[key] = savedAt;
  persistStorage(storageKey("categories", ownerUserId), { savedAt, categories: state.categoriesByOwner[key] });
  return state.categoriesByOwner[key];
}

async function listCards(params = {}, options = {}) {
  const key = ownerKey(params.ownerUserId);
  const savedAt = Number(state.cardsSavedAtByOwner[key] || 0);
  const isFresh = isWithinTtl(savedAt, CARD_CACHE_TTL_MS);
  const isStaleButUsable = isWithinTtl(savedAt, CARD_CACHE_STALE_TTL_MS);
  if (!options.force && state.cardsByOwner[key] && (isFresh || (options.allowStale && isStaleButUsable))) {
    return state.cardsByOwner[key];
  }
  if (!options.force) {
    const stored = wx.getStorageSync(storageKey("cards", params.ownerUserId));
    const cached = Array.isArray(stored) ? stored : stored && stored.cards;
    const savedAt = Array.isArray(stored) ? 0 : Number(stored && stored.savedAt || 0);
    if (Array.isArray(cached) && (isWithinTtl(savedAt, CARD_CACHE_TTL_MS) || (options.allowStale && isWithinTtl(savedAt, CARD_CACHE_STALE_TTL_MS)))) {
      state.cardsSavedAtByOwner[key] = savedAt;
      state.cardsByOwner[key] = cached;
      cached.forEach((card) => { if (card && card.id) state.cardsById[cardCacheKey(card.ownerUserId || params.ownerUserId, card.id)] = card; });
      return cached;
    }
  }
  const res = await api.fetchCardsMetadata(params);
  return setCards(params.ownerUserId, res.data || []);
}

function peekCards(ownerUserId) {
  const key = ownerKey(ownerUserId);
  if (isWithinTtl(Number(state.cardsSavedAtByOwner[key] || 0), CARD_CACHE_STALE_TTL_MS)) return state.cardsByOwner[key];
  try {
    const stored = wx.getStorageSync(storageKey("cards", ownerUserId));
    const cards = Array.isArray(stored) ? stored : stored && stored.cards;
    const savedAt = Array.isArray(stored) ? 0 : Number(stored && stored.savedAt || 0);
    if (!Array.isArray(cards) || !isWithinTtl(savedAt, CARD_CACHE_STALE_TTL_MS)) return [];
    state.cardsByOwner[key] = cards;
    state.cardsSavedAtByOwner[key] = savedAt;
    cards.forEach((card) => { if (card && card.id) state.cardsById[cardCacheKey(card.ownerUserId || ownerUserId, card.id)] = card; });
    return cards;
  } catch (error) {
    return [];
  }
}

function hasCardsCache(ownerUserId) {
  const key = ownerKey(ownerUserId);
  if (Object.prototype.hasOwnProperty.call(state.cardsByOwner, key)) {
    return isWithinTtl(Number(state.cardsSavedAtByOwner[key] || 0), CARD_CACHE_STALE_TTL_MS);
  }
  try {
    const stored = wx.getStorageSync(storageKey("cards", ownerUserId));
    const cards = Array.isArray(stored) ? stored : stored && stored.cards;
    const savedAt = Array.isArray(stored) ? 0 : Number(stored && stored.savedAt || 0);
    return Array.isArray(cards) && isWithinTtl(savedAt, CARD_CACHE_STALE_TTL_MS);
  } catch (error) {
    return false;
  }
}

function peekCategories(ownerUserId) {
  const key = ownerKey(ownerUserId);
  if (isWithinTtl(Number(state.categoriesSavedAtByOwner[key] || 0), CATEGORY_CACHE_STALE_TTL_MS)) {
    return state.categoriesByOwner[key];
  }
  try {
    const stored = wx.getStorageSync(storageKey("categories", ownerUserId));
    const categories = Array.isArray(stored) ? stored : stored && stored.categories;
    const savedAt = Array.isArray(stored) ? 0 : Number(stored && stored.savedAt || 0);
    if (!Array.isArray(categories) || !isWithinTtl(savedAt, CATEGORY_CACHE_STALE_TTL_MS)) return [];
    state.categoriesByOwner[key] = categories;
    state.categoriesSavedAtByOwner[key] = savedAt;
    return categories;
  } catch (error) {
    return [];
  }
}

async function listCardPage(params = {}) {
  const res = await api.fetchCardsMetadata(params);
  return Array.isArray(res.data) ? res.data : [];
}

function refreshCards(params = {}) {
  const key = ownerKey(params.ownerUserId);
  if (state.cardsRefreshByOwner[key]) return state.cardsRefreshByOwner[key];
  const isFresh = Date.now() - Number(state.cardsSavedAtByOwner[key] || 0) < CARD_CACHE_TTL_MS;
  if (state.cardsByOwner[key] && isFresh) return Promise.resolve(state.cardsByOwner[key]);
  const generation = Number(state.cardsCacheGenerationByOwner[key] || 0);
  const request = api.fetchCardsMetadata(params)
    .then((res) => {
      if (generation !== Number(state.cardsCacheGenerationByOwner[key] || 0)) return null;
      return setCards(params.ownerUserId, res.data || []);
    })
    .finally(() => {
      if (state.cardsRefreshByOwner[key] === request) delete state.cardsRefreshByOwner[key];
    });
  state.cardsRefreshByOwner[key] = request;
  return request;
}

async function listCategories(ownerUserId, options = {}) {
  const key = ownerKey(ownerUserId);
  const memorySavedAt = Number(state.categoriesSavedAtByOwner[key] || 0);
  const memoryFresh = memorySavedAt && Date.now() - memorySavedAt < CATEGORY_CACHE_TTL_MS;
  const memoryStaleButUsable = memorySavedAt && isWithinTtl(memorySavedAt, CATEGORY_CACHE_STALE_TTL_MS);
  if (!options.force && state.categoriesByOwner[key] && (memoryFresh || (options.allowStale && memoryStaleButUsable))) {
    return state.categoriesByOwner[key];
  }
  if (!options.force) {
    const cached = wx.getStorageSync(storageKey("categories", ownerUserId));
    const categories = Array.isArray(cached) ? cached : cached && cached.categories;
    const savedAt = Array.isArray(cached) ? 0 : Number(cached && cached.savedAt || 0);
    if (Array.isArray(categories) && (isWithinTtl(savedAt, CATEGORY_CACHE_TTL_MS) || (options.allowStale && isWithinTtl(savedAt, CATEGORY_CACHE_STALE_TTL_MS)))) {
      state.categoriesByOwner[key] = categories;
      state.categoriesSavedAtByOwner[key] = savedAt;
      return categories;
    }
  }
  const res = await api.fetchCategories(ownerUserId);
  return setCategories(ownerUserId, res.data || []);
}

async function getCard(cardId, options = {}) {
  const ownerUserId = options.ownerUserId || currentOwnerUserId();
  const cacheId = cardCacheKey(ownerUserId, cardId);
  const ownerSavedAt = Number(state.cardsSavedAtByOwner[ownerKey(ownerUserId)] || 0);
  if (!options.force && state.cardsById[cacheId] && (isWithinTtl(ownerSavedAt, CARD_CACHE_TTL_MS) || (options.allowStale && isWithinTtl(ownerSavedAt, CARD_CACHE_STALE_TTL_MS)))) {
    return state.cardsById[cacheId];
  }
  const res = await api.fetchCard(cardId);
  if (res.data && res.data.id) {
    state.cardsById[cardCacheKey(res.data.ownerUserId || ownerUserId, res.data.id)] = res.data;
  }
  return res.data;
}

function upsertCard(card) {
  if (!card || !card.id) return card;
  const ownerUserId = card.ownerUserId || currentOwnerUserId();
  state.cardsById[cardCacheKey(ownerUserId, card.id)] = card;
  Object.keys(state.cardsByOwner).forEach((key) => {
    const cards = state.cardsByOwner[key] || [];
    if (cards.some((item) => item.id === card.id)) {
      state.cardsByOwner[key] = cards.map((item) => (item.id === card.id ? card : item));
      state.cardsSavedAtByOwner[key] = Date.now();
      persistStorage(storageKey("cards", key), {
        savedAt: state.cardsSavedAtByOwner[key],
        cards: state.cardsByOwner[key]
      });
    }
  });
  return card;
}

function invalidateCards(ownerUserId) {
  const key = ownerKey(ownerUserId);
  state.cardsCacheGenerationByOwner[key] = Number(state.cardsCacheGenerationByOwner[key] || 0) + 1;
  delete state.cardsRefreshByOwner[key];
  delete state.cardsByOwner[key];
  delete state.cardsSavedAtByOwner[key];
  Object.keys(state.cardsById).forEach((cardId) => {
    if (cardId.startsWith(`${key}:`) || (state.cardsById[cardId] && state.cardsById[cardId].ownerUserId === ownerUserId)) {
      delete state.cardsById[cardId];
    }
  });
  removeStorage(storageKey("cards", ownerUserId));
}

function invalidateOwner(ownerUserId) {
  const key = ownerKey(ownerUserId);
  invalidateCards(ownerUserId);
  delete state.categoriesByOwner[key];
  delete state.categoriesSavedAtByOwner[key];
  removeStorage(storageKey("categories", ownerUserId));
}

function clearAll() {
  state.cardsByOwner = {};
  state.categoriesByOwner = {};
  state.cardsById = {};
  state.cardsSavedAtByOwner = {};
  state.categoriesSavedAtByOwner = {};
  state.cardsRefreshByOwner = {};
  state.cardsCacheGenerationByOwner = {};
  try {
    const info = wx.getStorageInfoSync();
    const prefix = `resourceStore_${CACHE_SCHEMA_VERSION}_`;
    (info.keys || []).filter((key) => key.startsWith(prefix)).forEach(removeStorage);
  } catch (error) {}
}

module.exports = {
  listCards,
  listCardPage,
  peekCards,
  hasCardsCache,
  peekCategories,
  rememberCards,
  refreshCards,
  listCategories,
  getCard,
  upsertCard,
  invalidateCards,
  invalidateOwner,
  clearAll
};
