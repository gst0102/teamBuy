const { getCurrentUser } = require("./dashboard");
const api = require("../services/api");

// This module lives in the main package because main-package pages cannot
// require files from a subpackage. The mutual-help subpackage re-exports the
// same helpers so every tool keeps one client-side cache shape.
const POINTS_KEY_PREFIX = "teambuy:mutual-help:demo-points:v3";
const POINTS_SEED_KEY_PREFIX = "teambuy:mutual-help:demo-points-seed:v3";
const LEGACY_POINTS_KEY_PREFIX = "teambuy:mutual-help:demo-points:v2";
const POINTS_SEED_VERSION = "shared-account-v1";
const INITIAL_POINTS = 100;
const POINT_TYPE_BASE = "base";
const POINT_TYPE_REWARD = "reward";
const POINT_TYPE_LABELS = {
  [POINT_TYPE_BASE]: "基础积分",
  [POINT_TYPE_REWARD]: "充值积分"
};

function getDefaultUserId() {
  try {
    const user = getCurrentUser();
    return String((user && (user.id || user.openid)) || "guest");
  } catch (error) {
    return "guest";
  }
}

function scopedKey(prefix, userId) {
  return `${prefix}:${userId || "guest"}`;
}

function readStorage(key, fallback) {
  try {
    const value = wx.getStorageSync(key);
    return value === undefined || value === null ? fallback : value;
  } catch (error) {
    return fallback;
  }
}

function writeStorage(key, value) {
  try {
    wx.setStorageSync(key, value);
  } catch (error) {
    // The page remains usable when local persistence is unavailable.
  }
}

function normalizePointType(pointType = POINT_TYPE_BASE) {
  return pointType === POINT_TYPE_REWARD ? POINT_TYPE_REWARD : POINT_TYPE_BASE;
}

function normalizePointBalances(value, fallbackBase = INITIAL_POINTS) {
  const source = value && typeof value === "object" ? value : {};
  const base = Number(source.base);
  const reward = Number(source.reward);
  return {
    base: Number.isFinite(base) ? Math.max(0, Math.floor(base)) : Math.max(0, fallbackBase),
    reward: Number.isFinite(reward) ? Math.max(0, Math.floor(reward)) : 0
  };
}

function getPointBalances(userId = getDefaultUserId()) {
  const pointsKey = scopedKey(POINTS_KEY_PREFIX, userId);
  const seedKey = scopedKey(POINTS_SEED_KEY_PREFIX, userId);
  if (readStorage(seedKey, "") !== POINTS_SEED_VERSION) {
    const current = readStorage(pointsKey, null);
    const legacyValue = Number(readStorage(scopedKey(LEGACY_POINTS_KEY_PREFIX, userId), INITIAL_POINTS));
    // v2 had no provenance, so its mixed balance is kept as base points. For
    // v3, do not infer provenance from the numeric balance: the reward bucket
    // may contain recharge points, and only the server ledger can safely move
    // identifiable historical platform rewards to base points.
    const migrated = current && typeof current === "object"
      ? normalizePointBalances(current, 0)
      : normalizePointBalances({ base: legacyValue, reward: 0 });
    writeStorage(pointsKey, migrated);
    writeStorage(seedKey, POINTS_SEED_VERSION);
    return { ...migrated, total: migrated.base + migrated.reward };
  }
  const balances = normalizePointBalances(readStorage(pointsKey, null));
  return { ...balances, total: balances.base + balances.reward };
}

function getPointsByType(userId = getDefaultUserId(), pointType = POINT_TYPE_BASE) {
  return getPointBalances(userId)[normalizePointType(pointType)];
}

function getPoints(userId = getDefaultUserId()) {
  return getPointBalances(userId).total;
}

function savePointBalances(balances, userId = getDefaultUserId()) {
  const normalized = normalizePointBalances(balances, 0);
  writeStorage(scopedKey(POINTS_KEY_PREFIX, userId), normalized);
  writeStorage(scopedKey(POINTS_SEED_KEY_PREFIX, userId), POINTS_SEED_VERSION);
  return { ...normalized, total: normalized.base + normalized.reward };
}

function savePoints(points, userId = getDefaultUserId(), pointType = POINT_TYPE_BASE) {
  const balances = getPointBalances(userId);
  const normalizedPointType = normalizePointType(pointType);
  balances[normalizedPointType] = Math.max(0, Math.floor(Number(points) || 0));
  return savePointBalances(balances, userId)[normalizedPointType];
}

function setTotalPoints(points, userId = getDefaultUserId()) {
  const current = getPointBalances(userId);
  const target = Math.max(0, Math.floor(Number(points) || 0));
  const delta = target - current.total;
  if (delta > 0) {
    // Platform-earned points always enter the base bucket.
    current.base += delta;
  } else if (delta < 0) {
    let remaining = Math.abs(delta);
    const fromBase = Math.min(current.base, remaining);
    current.base -= fromBase;
    remaining -= fromBase;
    current.reward = Math.max(0, current.reward - remaining);
  }
  return savePointBalances(current, userId);
}

function saveServerPointData(data = {}, userId = getDefaultUserId()) {
  const accounts = data && data.accounts && typeof data.accounts === "object" ? data.accounts : {};
  if (accounts.base || accounts.reward) {
    return savePointBalances({
      base: accounts.base && accounts.base.balance,
      reward: accounts.reward && accounts.reward.balance
    }, userId);
  }
  if (data && data.points && typeof data.points === "object") {
    return savePointBalances(data.points, userId);
  }
  // Old status responses exposed only a mixed account balance. Keeping it in
  // base avoids silently manufacturing reward/cash-like points.
  if (data && data.account && data.account.balance !== undefined) {
    return savePointBalances({ base: data.account.balance, reward: 0 }, userId);
  }
  return getPointBalances(userId);
}

async function syncServerPointData(userId = getDefaultUserId()) {
  const cleanUserId = String(userId || "").trim();
  if (!cleanUserId || cleanUserId === "guest") return getPointBalances(cleanUserId);
  const response = await api.fetchMutualHelpStatus(cleanUserId);
  return saveServerPointData(response && response.data ? response.data : {}, cleanUserId);
}

module.exports = {
  INITIAL_POINTS,
  POINT_TYPE_BASE,
  POINT_TYPE_REWARD,
  POINT_TYPE_LABELS,
  getPoints,
  getPointsByType,
  getPointBalances,
  savePointBalances,
  savePoints,
  setTotalPoints,
  saveServerPointData,
  syncServerPointData
};
