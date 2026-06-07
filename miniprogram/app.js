App({
  globalData: {
    apiBaseUrl: "http://127.0.0.1:8000",
    currentUser: null
  },
  onLaunch() {
    const user = wx.getStorageSync("currentUser");
    if (user) {
      this.globalData.currentUser = user;
    }
  }
});

