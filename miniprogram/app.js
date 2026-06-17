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
    if (user) {
      this.globalData.currentUser = user;
    }
  }
});
