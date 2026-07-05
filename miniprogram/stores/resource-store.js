const api = require("../services/api");

const state = {
  cardsByOwner: {},
  categoriesByOwner: {},
  cardsById: {}
};

function ownerKey(ownerUserId) {
  return ownerUserId || "all";
}

function storageKey(type, ownerUserId) {
  return `resourceStore_${type}_${ownerKey(ownerUserId)}`;
}

function setCards(ownerUserId, cards = []) {
  const key = ownerKey(ownerUserId);
  state.cardsByOwner[key] = cards;
  cards.forEach((card) => {
    if (card && card.id) state.cardsById[card.id] = card;
  });
  wx.setStorageSync(storageKey("cards", ownerUserId), cards);
  return cards;
}

function setCategories(ownerUserId, categories = []) {
  const key = ownerKey(ownerUserId);
  state.categoriesByOwner[key] = categories;
  wx.setStorageSync(storageKey("categories", ownerUserId), categories);
  return categories;
}

async function listCards(params = {}, options = {}) {
  const key = ownerKey(params.ownerUserId);
  if (!options.force && state.cardsByOwner[key]) {
    return state.cardsByOwner[key];
  }
  if (!options.force) {
    const cached = wx.getStorageSync(storageKey("cards", params.ownerUserId));
    if (Array.isArray(cached) && cached.length) {
      return setCards(params.ownerUserId, cached);
    }
  }
  const res = await api.fetchCards(params);
  return setCards(params.ownerUserId, res.data || []);
}

async function listCategories(ownerUserId, options = {}) {
  const key = ownerKey(ownerUserId);
  if (!options.force && state.categoriesByOwner[key]) {
    return state.categoriesByOwner[key];
  }
  if (!options.force) {
    const cached = wx.getStorageSync(storageKey("categories", ownerUserId));
    if (Array.isArray(cached) && cached.length) {
      return setCategories(ownerUserId, cached);
    }
  }
  const res = await api.fetchCategories(ownerUserId);
  return setCategories(ownerUserId, res.data || []);
}

async function getCard(cardId, options = {}) {
  if (!options.force && state.cardsById[cardId]) {
    return state.cardsById[cardId];
  }
  const res = await api.fetchCard(cardId);
  if (res.data && res.data.id) {
    state.cardsById[res.data.id] = res.data;
  }
  return res.data;
}

function upsertCard(card) {
  if (!card || !card.id) return card;
  state.cardsById[card.id] = card;
  Object.keys(state.cardsByOwner).forEach((key) => {
    const cards = state.cardsByOwner[key] || [];
    if (cards.some((item) => item.id === card.id)) {
      state.cardsByOwner[key] = cards.map((item) => (item.id === card.id ? card : item));
      wx.setStorageSync(storageKey("cards", key), state.cardsByOwner[key]);
    }
  });
  return card;
}

function invalidateOwner(ownerUserId) {
  const key = ownerKey(ownerUserId);
  delete state.cardsByOwner[key];
  delete state.categoriesByOwner[key];
  wx.removeStorageSync(storageKey("cards", ownerUserId));
  wx.removeStorageSync(storageKey("categories", ownerUserId));
}

module.exports = {
  listCards,
  listCategories,
  getCard,
  upsertCard,
  invalidateOwner
};
