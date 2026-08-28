const api = require("./api");

const inFlightByUser = {};
const configInFlightByUser = {};
const SUBSCRIPTION_PENDING_PREFIX = "teambuy:subscription-pending:v1";
const SUBSCRIPTION_REJECT_COOLDOWN_MS = 24 * 60 * 60 * 1000;

function currentUser() {
  const app = getApp();
  return (app && app.globalData && app.globalData.currentUser) || wx.getStorageSync("currentUser") || null;
}

function storageScope() {
  const app = getApp();
  const data = (app && app.globalData) || {};
  return `${data.environmentName || ""}|${data.apiBaseUrl || ""}|${data.apiRoutePrefix || ""}`;
}

function pendingKey(userId, templateId) {
  return `${SUBSCRIPTION_PENDING_PREFIX}:${storageScope()}:${userId}:${templateId}`;
}

function readPending(userId, templateId) {
  try {
    const value = wx.getStorageSync(pendingKey(userId, templateId));
    return value && value.requestId && value.status ? value : null;
  } catch (error) {
    return null;
  }
}

function writePending(userId, templateId, value) {
  try {
    wx.setStorageSync(pendingKey(userId, templateId), {
      requestId: value.requestId,
      status: value.status,
      source: value.source || "share",
      savedAt: Date.now()
    });
  } catch (error) {
    // The backend remains idempotent; local persistence is only a retry hint.
  }
}

function clearPending(userId, templateId) {
  try {
    wx.removeStorageSync(pendingKey(userId, templateId));
  } catch (error) {
    // Ignore storage failures; a later request will use the same in-memory path.
  }
}

function rejectionKey(userId, templateId) {
  return `${pendingKey(userId, templateId)}:rejected`;
}

function recentlyRejected(userId, templateId) {
  try {
    const timestamp = Number(wx.getStorageSync(rejectionKey(userId, templateId)) || 0);
    return timestamp > 0 && Date.now() - timestamp < SUBSCRIPTION_REJECT_COOLDOWN_MS;
  } catch (error) {
    return false;
  }
}

function rememberRejection(userId, templateId) {
  try {
    wx.setStorageSync(rejectionKey(userId, templateId), Date.now());
  } catch (error) {
    // Reject cooldown is best effort and contains no customer data.
  }
}

function isAcceptedStatus(status) {
  return status === "accept" || status === "acceptWithAudio";
}

async function recordPendingAuthorization(user, templateId, pending) {
  try {
    const response = await api.recordNotificationSubscription({
      userId: user.id,
      templateId,
      status: pending.status,
      source: pending.source || "share",
      requestId: pending.requestId
    });
    clearPending(user.id, templateId);
    if (!isAcceptedStatus(pending.status)) rememberRejection(user.id, templateId);
    const data = (response && response.data) || {};
    return {
      ok: true,
      accepted: Boolean(data.accepted) || isAcceptedStatus(pending.status),
      status: pending.status,
      duplicate: Boolean(data.duplicate)
    };
  } catch (error) {
    writePending(user.id, templateId, pending);
    return { ok: false, accepted: false, status: pending.status, reason: "record_failed" };
  }
}

function preloadViewNotificationSubscriptionConfig(userId) {
  if (!userId) return Promise.resolve(null);
  const app = getApp();
  const user = currentUser();
  if (!user || user.id !== userId) return Promise.resolve(null);
  if (configInFlightByUser[userId]) return configInFlightByUser[userId];
  const promise = api.fetchNotificationConfig(userId).then((response) => {
    const data = (response && response.data) || {};
    if (app && app.globalData) app.globalData.subscribeTemplateId = data.enabled ? String(data.templateId || "") : "";
    return data;
  }).catch((error) => {
    console.warn("[subscription] preload config failed", error);
    return null;
  }).finally(() => {
    delete configInFlightByUser[userId];
  });
  configInFlightByUser[userId] = promise;
  return promise;
}

function requestViewNotificationSubscription(source = "share") {
  const user = currentUser();
  if (!user || !user.id || typeof wx.requestSubscribeMessage !== "function") {
    return Promise.resolve({ accepted: false, reason: "not_available" });
  }
  if (inFlightByUser[user.id]) return inFlightByUser[user.id];
  const promise = (async () => {
    // The send action must wait for the server-side feature/template config;
    // preload is intentionally not a prerequisite for tapping "send".
    const config = await preloadViewNotificationSubscriptionConfig(user.id);
    const templateId = String(config && config.enabled ? config.templateId || "" : "").trim();
    if (!templateId) return { accepted: false, reason: "not_available" };

    const pending = readPending(user.id, templateId);
    if (pending) {
      const recorded = await recordPendingAuthorization(user, templateId, pending);
      if (recorded.ok) return recorded;
      return { ...recorded, status: pending.status };
    }
    if (recentlyRejected(user.id, templateId)) {
      return { accepted: false, reason: "recently_rejected" };
    }

    const requestId = `sub_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    return new Promise((resolve) => {
      wx.requestSubscribeMessage({
        tmplIds: [templateId],
        success(result = {}) {
          const status = result[templateId] || "reject";
          const pendingAuthorization = { requestId, status, source };
          recordPendingAuthorization(user, templateId, pendingAuthorization).then((recorded) => {
            resolve(recorded.ok ? recorded : { ...recorded, status });
          });
        },
        fail(error) {
          console.warn("[subscription] request failed", error);
          resolve({ accepted: false, reason: "request_failed" });
        }
      });
    });
  })().finally(() => {
    delete inFlightByUser[user.id];
  });
  inFlightByUser[user.id] = promise;
  return promise;
}

module.exports = {
  requestViewNotificationSubscription,
  preloadViewNotificationSubscriptionConfig
};
