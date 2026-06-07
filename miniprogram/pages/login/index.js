const api = require("../../services/api");

Page({
  data: {
    nickname: "本地测试用户",
    avatarUrl: "https://example.com/avatar-local.png"
  },
  onLoad() {
    const app = getApp();
    if (app.globalData.currentUser) {
      wx.redirectTo({ url: "/pages/library/index" });
    }
  },
  handleNicknameChange(event) {
    this.setData({ nickname: event.detail.value });
  },
  async handleMockLogin() {
    try {
      const res = await api.mockLogin({
        nickname: this.data.nickname,
        avatarUrl: this.data.avatarUrl
      });
      const app = getApp();
      app.globalData.currentUser = res.data;
      wx.setStorageSync("currentUser", res.data);
      wx.navigateTo({ url: "/pages/imports/index" });
    } catch (error) {
      wx.showToast({ title: "登录失败", icon: "none" });
    }
  }
});
