const app = getApp();

function buildApiUrl(url = "") {
  const baseUrl = (app.globalData && app.globalData.apiBaseUrl) || "";
  const routePrefix = (app.globalData && app.globalData.apiRoutePrefix) || "";
  const path = String(url || "");
  const routedPath = routePrefix && path.startsWith("/api")
    ? `${routePrefix}${path.slice(4) || ""}`
    : path;
  return `${baseUrl}${routedPath}`;
}

function request({ url, method = "GET", data = null }) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: buildApiUrl(url),
      method,
      data,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        reject(res.data);
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

module.exports = {
  buildApiUrl,
  request
};
