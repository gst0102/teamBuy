const app = getApp();

function request({ url, method = "GET", data = null }) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.apiBaseUrl}${url}`,
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
  request
};

