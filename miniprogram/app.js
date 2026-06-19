const { cacheButtonPosition } = require("./utils/nav");

App({
  globalData: {
    apiBaseUrl: "https://teambuy.lifelove.top",
    currentUser: null,
    buttonPosition: null
  },
  onLaunch() {
    this.globalData.buttonPosition = cacheButtonPosition();
    const user = wx.getStorageSync("currentUser");
    const isProductionApi = /^https:\/\//i.test(this.globalData.apiBaseUrl || "");
    const isMockUser = user && (user.openid === "openid_本地测试用户" || /^mock_/.test(user.openid || ""));
    if (user && ((isProductionApi && isMockUser) || user.apiBaseUrl !== this.globalData.apiBaseUrl)) {
      wx.removeStorageSync("currentUser");
      return;
    }
    if (user) {
      this.globalData.currentUser = user;
    }
  }
});
