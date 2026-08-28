// Customer detail data may contain identity and contact information. Keep it
// in the current process only so radar -> detail feels instant without
// writing sensitive data to wx storage.
const cachePolicy = require("../utils/cache-policy");

const CACHE_TTL_MS = cachePolicy.customerDetailTtlMs;
const MAX_CACHE_ENTRIES = cachePolicy.customerDetailMaxEntries;

const state = {
  entries: {}
};

function isExpiredAccessSnapshot(response) {
  const data = response && response.data;
  const membership = data && data.membership;
  if (!data || data.paymentRequired !== true || !membership) return false;
  const expiresAt = Date.parse(String(membership.expiresAt || ""));
  return Number.isFinite(expiresAt) && expiresAt <= Date.now();
}

function environmentScope() {
  try {
    const app = getApp();
    const globalData = (app && app.globalData) || {};
    return [globalData.environmentName, globalData.apiBaseUrl, globalData.apiRoutePrefix].join("|");
  } catch (error) {
    return "default";
  }
}

function cacheKey(ownerUserId, mode = "", customerId = "", leadId = "") {
  return [
    environmentScope(),
    ownerUserId || "",
    mode || "",
    customerId || "",
    leadId || ""
  ].join(":");
}

function peek(ownerUserId, mode = "", customerId = "", leadId = "") {
  const key = cacheKey(ownerUserId, mode, customerId, leadId);
  const entry = state.entries[key];
  if (!entry || Date.now() - entry.savedAt >= CACHE_TTL_MS || isExpiredAccessSnapshot(entry.response)) {
    if (entry) delete state.entries[key];
    return null;
  }
  return entry.response;
}

function remember(ownerUserId, mode = "", customerId = "", leadId = "", response) {
  if (!response || !response.data || response.data.locked !== false) return response;
  const savedAt = Date.now();
  state.entries[cacheKey(ownerUserId, mode, customerId, leadId)] = { savedAt, response };
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

function clear(ownerUserId, mode = "") {
  const prefix = `${environmentScope()}:${ownerUserId || ""}:${mode || ""}:`;
  Object.keys(state.entries).forEach((key) => {
    if (key.indexOf(prefix) === 0) delete state.entries[key];
  });
}

function clearAll() {
  state.entries = {};
}

module.exports = {
  peek,
  remember,
  clear,
  clearAll
};
