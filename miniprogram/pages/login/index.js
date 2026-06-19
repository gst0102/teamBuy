const api = require("../../services/api");

Page({
  data: {
    nickname: "微信用户",
    avatarUrl: "https://example.com/avatar-local.png",
    allowMockLogin: false
  },
  onLoad() {
    const app = getApp();
    if (app.globalData.currentUser) {
      wx.switchTab({ url: "/pages/home/index" });
      return;
    }
    const baseUrl = (app.globalData && app.globalData.apiBaseUrl) || "";
    this.setData({ allowMockLogin: !/^https:\/\//i.test(baseUrl) });
  },
  handleNicknameChange(event) {
    this.setData({ nickname: event.detail.value });
  },
  requestWxCode() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: (res) => {
          if (res.code) resolve(res.code);
          else reject(new Error("缺少微信登录 code"));
        },
        fail: reject
      });
    });
  },
  ensureMockOpenid() {
    const key = "localMockOpenid";
    let openid = wx.getStorageSync(key);
    if (!openid) {
      openid = `mock_${Date.now()}_${Math.random().toString(16).slice(2)}`;
      wx.setStorageSync(key, openid);
    }
    return openid;
  },
  saveLogin(user) {
    const app = getApp();
    const userWithBase = {
      ...user,
      apiBaseUrl: app.globalData.apiBaseUrl
    };
    app.globalData.currentUser = userWithBase;
    wx.setStorageSync("currentUser", userWithBase);
    wx.switchTab({ url: "/pages/home/index" });
  },
  async loginWithLocalIdentity() {
    const res = await api.mockLogin({
      nickname: this.data.nickname || "微信用户",
      avatarUrl: this.data.avatarUrl,
      openid: this.ensureMockOpenid()
    });
    this.saveLogin(res.data);
  },
  async handleWechatLogin() {
    const app = getApp();
    const baseUrl = (app.globalData && app.globalData.apiBaseUrl) || "";
    if (!/^https:\/\//i.test(baseUrl)) {
      wx.showModal({
        title: "当前是本地后端",
        content: "微信登录需要连接线上 HTTPS 后端并配置 AppSecret。本地测试请点“本地 mock 登录”。",
        showCancel: false
      });
      return;
    }
    try {
      const code = await this.requestWxCode();
      const res = await api.wechatLogin({
        code,
        nickname: this.data.nickname || "微信用户",
        avatarUrl: this.data.avatarUrl
      });
      this.saveLogin(res.data);
    } catch (error) {
      if ((error.detail || "").includes("微信登录未配置")) {
        wx.showModal({
          title: "微信登录未配置",
          content: "线上后端缺少小程序 AppID/AppSecret，不能使用测试身份代替。请先配置后再登录。",
          showCancel: false
        });
        return;
      }
      wx.showModal({
        title: "登录未完成",
        content: error.detail || error.message || "微信登录失败，请确认后端已配置小程序 AppSecret。",
        showCancel: false
      });
    }
  },
  async handleMockLogin() {
    if (!this.data.allowMockLogin) {
      wx.showModal({
        title: "仅限本地测试",
        content: "当前连接的是线上后端，不能使用本地 mock 身份。",
        showCancel: false
      });
      return;
    }
    try {
      await this.loginWithLocalIdentity();
    } catch (error) {
      const message = error.detail || error.errMsg || "请确认手机和电脑在同一 Wi-Fi，且本地后端已启动";
      wx.showModal({
        title: "登录失败",
        content: message,
        showCancel: false
      });
    }
  }
});
