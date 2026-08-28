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
    wx.request({
      url: requestUrl,
      method,
      data,
      header,
      timeout: REQUEST_TIMEOUT_MS,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        const payload = res.data && typeof res.data === "object"
          ? { ...res.data, statusCode: res.statusCode }
          : { detail: `请求失败（${res.statusCode}）`, statusCode: res.statusCode };
        if (res.statusCode === 401) {
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
        } else if (res.statusCode >= 500) {
          payload.errorType = "server";
          payload.detail = payload.message || payload.detail || "服务暂时异常，请稍后重试";
        } else if (res.statusCode === 403) {
          payload.errorType = "forbidden";
          payload.detail = payload.message || payload.detail || "当前账号没有权限执行此操作";
        }
        reject(payload);
      },
      fail(err) {
        const rawMessage = String((err && err.errMsg) || "");
        reject({
          ...(err && typeof err === "object" ? err : {}),
          errorType: "network",
          retryable: true,
          detail: /timeout|timed out/i.test(rawMessage)
            ? "网络请求超时，请重试"
            : "网络连接失败，请检查网络后重试"
        });
      }
    });
  });
}

module.exports = {
  buildApiUrl,
  request
};
