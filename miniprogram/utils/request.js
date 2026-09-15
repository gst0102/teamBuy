function getAppInstance() {
  try {
    return typeof getApp === "function" ? getApp() || null : null;
  } catch (error) {
    return null;
  }
}

function getGlobalData() {
  const app = getAppInstance();
  return (app && app.globalData) || {};
}

function buildApiUrl(url = "") {
  const globalData = getGlobalData();
  const baseUrl = globalData.apiBaseUrl || "";
  const routePrefix = globalData.apiRoutePrefix || "";
  const path = String(url || "");
  const routedPath = routePrefix && path.startsWith("/api")
    ? `${routePrefix}${path.slice(4) || ""}`
    : path;
  return `${baseUrl}${routedPath}`;
}

const REQUEST_TIMEOUT_MS = 15000;

function formatApiErrorDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (typeof item === "string") return item;
      if (!item || typeof item !== "object") return String(item || "");
      const location = Array.isArray(item.loc)
        ? item.loc.filter((part) => part !== undefined && part !== null && part !== "").join(".")
        : "";
      const message = String(item.msg || item.message || item.detail || "").trim();
      if (location && message) return `${location}: ${message}`;
      return message || JSON.stringify(item);
    }).filter(Boolean).join("；");
  }
  if (detail && typeof detail === "object") {
    return String(detail.message || detail.msg || detail.detail || JSON.stringify(detail));
  }
  return detail === undefined || detail === null ? "" : String(detail);
}

function request({ url, method = "GET", data = null }) {
  return new Promise((resolve, reject) => {
    const app = getAppInstance();
    const globalData = (app && app.globalData) || {};
    const user = globalData.currentUser || wx.getStorageSync("currentUser") || {};
    const authToken = String(user.authToken || "").trim();
    const clientBuildVersion = String(globalData.clientBuildVersion || "").trim();
    const header = {
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...(clientBuildVersion ? { "X-TeamBuy-Client-Build": clientBuildVersion } : {})
    };
    const requestUrl = buildApiUrl(url);
    if (!requestUrl || (!globalData.apiBaseUrl && !/^https?:\/\//i.test(requestUrl))) {
      reject({
        errorType: "app_init",
        retryable: true,
        detail: "小程序正在启动，请稍后重试"
      });
      return;
    }
    let settled = false;
    const resolveResponse = (res) => {
      if (settled) return;
      settled = true;
      if (res && res.statusCode >= 200 && res.statusCode < 300) {
        resolve(res.data);
        return;
      }
      const payload = res && res.data && typeof res.data === "object"
        ? { ...res.data, statusCode: res.statusCode }
        : { detail: `请求失败（${res && res.statusCode ? res.statusCode : "无状态码"}）`, statusCode: res && res.statusCode };
      const normalizedDetail = formatApiErrorDetail(payload.detail || payload.message);
      if (normalizedDetail) payload.detail = normalizedDetail;
      if (res && res.statusCode === 401) {
        if (app && typeof app.clearExpiredSession === "function") {
          app.clearExpiredSession({ redirect: Boolean(authToken) });
        }
        if (authToken) {
          payload.authExpired = true;
          payload.detail = "登录已失效，请重新登录";
          payload.errorType = "auth";
        } else {
          payload.authExpired = false;
          payload.errorType = "auth_required";
          payload.detail = "该操作需要登录";
        }
      } else if (res && res.statusCode >= 500) {
        payload.errorType = "server";
        payload.detail = payload.message || payload.detail || "服务暂时异常，请稍后重试";
      } else if (res && res.statusCode === 403) {
        payload.errorType = "forbidden";
        payload.detail = payload.message || payload.detail || "当前账号没有权限执行此操作";
      }
      reject(payload);
    };
    const rejectRequest = (err) => {
      if (settled) return;
      settled = true;
      const rawMessage = String((err && err.errMsg) || "");
      reject({
        ...(err && typeof err === "object" ? err : {}),
        errorType: "network",
        retryable: true,
        detail: /timeout|timed out/i.test(rawMessage)
          ? "网络请求超时，请重试"
          : "网络连接失败，请检查网络后重试"
      });
    };
    wx.request({
      url: requestUrl,
      method,
      data,
      header,
      timeout: REQUEST_TIMEOUT_MS,
      success: resolveResponse,
      fail: rejectRequest,
      // Some OpenHarmony WeChat builds have returned from the native request
      // layer through `complete` without invoking `success`. If a complete
      // callback carries an HTTP response, treat it exactly like success.
      complete(res) {
        if (settled) return;
        if (res && typeof res.statusCode === "number") resolveResponse(res);
        else rejectRequest(res || { errMsg: "request completed without a response" });
      }
    });
  });
}

module.exports = {
  buildApiUrl,
  formatApiErrorDetail,
  request
};
