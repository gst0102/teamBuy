// Customer intelligence is shared between the radar page and customer detail.
// Keep this cache in memory only: it speeds up a drill-down without persisting
// sensitive identity/contact data in local storage.
const cachePolicy = require("../utils/cache-policy");
const CACHE_TTL_MS = cachePolicy.customerIntelligenceTtlMs;
const MAX_CACHE_ENTRIES = cachePolicy.customerIntelligenceMaxEntries;

const state = {
  entries: {},
  inFlight: {},
  pendingMutations: {},
  generation: 0
};

function environmentScope() {
  try {
    const app = getApp();
    const globalData = (app && app.globalData) || {};
    return [globalData.environmentName, globalData.apiBaseUrl, globalData.apiRoutePrefix].join("|");
  } catch (error) {
    return "default";
  }
}

function cacheKey(ownerUserId, mode = "") {
  return `${environmentScope()}:${ownerUserId || ""}:${mode || ""}`;
}

function isExpiredAccessSnapshot(response) {
  const data = response && response.data;
  const membership = data && data.membership;
  if (!data || data.locked !== false || data.paymentRequired !== true || !membership) return false;
  const expiresAt = Date.parse(String(membership.expiresAt || ""));
  return Number.isFinite(expiresAt) && expiresAt <= Date.now();
}

function peek(ownerUserId, mode = "") {
  const key = cacheKey(ownerUserId, mode);
  const entry = state.entries[key];
  if (!entry || Date.now() - entry.savedAt >= CACHE_TTL_MS || isExpiredAccessSnapshot(entry.response)) {
    if (entry) delete state.entries[key];
    return null;
  }
  return entry.response;
}

function remember(ownerUserId, mode = "", response) {
  if (!response || !response.data) return response;
  const savedAt = Date.now();
  state.entries[cacheKey(ownerUserId, mode)] = {
    savedAt,
    response
  };
  const expiredBefore = savedAt - CACHE_TTL_MS;
  Object.keys(state.entries).forEach((key) => {
    if (state.entries[key].savedAt < expiredBefore) delete state.entries[key];
  });
  const keys = Object.keys(state.entries);
  if (keys.length > MAX_CACHE_ENTRIES) {
    keys
      .sort((left, right) => state.entries[left].savedAt - state.entries[right].savedAt)
      .slice(0, keys.length - MAX_CACHE_ENTRIES)
      .forEach((key) => delete state.entries[key]);
  }
  return response;
}

function getOrFetch(ownerUserId, mode = "", fetcher, options = {}) {
  const key = cacheKey(ownerUserId, mode);
  const requestGeneration = state.generation;
  if (!options.force) {
    const cached = peek(ownerUserId, mode);
    if (cached) return Promise.resolve(cached);
  }
  if (state.inFlight[key]) return state.inFlight[key];
  let request;
  request = Promise.resolve()
    .then(fetcher)
    .then((response) => (requestGeneration === state.generation
      ? remember(ownerUserId, mode, response)
      : response))
    .finally(() => {
      // A forced refresh can replace this promise after clear(). Never let an
      // older request delete the newer in-flight entry and create a race.
      if (state.inFlight[key] === request) delete state.inFlight[key];
    });
  state.inFlight[key] = request;
  return request;
}

function getOrFetchForAccessMode(ownerUserId, mode = "", paymentRequired = true, fetcher, options = {}) {
  const cached = options.force ? null : peek(ownerUserId, mode);
  const cachedPaymentRequired = cached && cached.data
    ? cached.data.paymentRequired !== false
    : null;
  if (cached && cachedPaymentRequired !== Boolean(paymentRequired)) {
    clear(ownerUserId, mode);
  }
  return getOrFetch(ownerUserId, mode, fetcher, options);
}

function clear(ownerUserId, mode = "") {
  // Prevent a response that was started under an older access decision from
  // repopulating the cache after membership or feature state changes.
  state.generation += 1;
  const key = cacheKey(ownerUserId, mode);
  delete state.entries[key];
  delete state.inFlight[key];
}

function clearAll() {
  state.generation += 1;
  state.entries = {};
  state.inFlight = {};
  state.pendingMutations = {};
}

function queueRadarMutation(ownerUserId, mode = "", mutation = {}) {
  const key = cacheKey(ownerUserId, mode);
  const list = state.pendingMutations[key] || [];
  const targetKey = String(
    mutation.leadId
      || mutation.visitorIdentityId
      || mutation.viewerUserId
      || mutation.anonymousId
      || mutation.customerId
      || ""
  ).trim();
  const nextMutation = {
    action: String(mutation.action || "").trim(),
    status: String(mutation.status || "").trim(),
    customerId: String(mutation.customerId || "").trim(),
    visitorIdentityId: String(mutation.visitorIdentityId || "").trim(),
    viewerUserId: String(mutation.viewerUserId || "").trim(),
    anonymousId: String(mutation.anonymousId || "").trim(),
    leadId: String(mutation.leadId || "").trim(),
    leadVersion: mutation.leadVersion === null || mutation.leadVersion === undefined
      ? null
      : Number(mutation.leadVersion),
    nextFollowUpAt: mutation.nextFollowUpAt === null || mutation.nextFollowUpAt === undefined
      ? ""
      : String(mutation.nextFollowUpAt || "").trim(),
    sourceTab: String(mutation.sourceTab || "").trim()
  };
  if (!nextMutation.action || !targetKey) return;
  const withoutSameTarget = list.filter((item) => {
    const itemKey = String(
      item.leadId
        || item.visitorIdentityId
        || item.viewerUserId
        || item.anonymousId
        || item.customerId
        || ""
    ).trim();
    return itemKey !== targetKey;
  });
  state.pendingMutations[key] = [...withoutSameTarget, nextMutation].slice(-20);
}

function drainRadarMutations(ownerUserId, mode = "") {
  const key = cacheKey(ownerUserId, mode);
  const mutations = state.pendingMutations[key] || [];
  delete state.pendingMutations[key];
  return mutations;
}

module.exports = {
  peek,
  remember,
  getOrFetch,
  getOrFetchForAccessMode,
  queueRadarMutation,
  drainRadarMutations,
  clear,
  clearAll
};
