const STORAGE_KEY = "teambuy:anonymousVisitorId:v2";

function scopedStorageKey() {
  try {
    const app = getApp();
    const globalData = (app && app.globalData) || {};
    const scope = [globalData.environmentName || "default", globalData.apiBaseUrl || ""]
      .join("|")
      .replace(/[^a-zA-Z0-9_.:-]/g, "_");
    return `${STORAGE_KEY}:${scope}`;
  } catch (error) {
    return `${STORAGE_KEY}:default`;
  }
}

function createAnonymousVisitorId() {
  return `visitor_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function getAnonymousVisitorId() {
  const key = scopedStorageKey();
  try {
    const stored = wx.getStorageSync(key);
    if (stored) return stored;
    const migrated = wx.getStorageSync("notePreviewAnonymousId") || wx.getStorageSync("showcaseAnonymousId");
    const next = migrated || createAnonymousVisitorId();
    wx.setStorageSync(key, next);
    return next;
  } catch (error) {
    return createAnonymousVisitorId();
  }
}

module.exports = { getAnonymousVisitorId };
