const { cacheButtonPosition } = require("./utils/nav");

App({
  globalData: {
    apiBaseUrl: "http://127.0.0.1:8000",
    currentUser: null,
    buttonPosition: null
  },
  onLaunch() {
    this.globalData.buttonPosition = cacheButtonPosition();
    const user = wx.getStorageSync("currentUser");
    if (user) {
      this.globalData.currentUser = user;
    }
  }
});
