const api = require("../../services/api");

Page({
  data: {
    nickname: "微信用户",
    avatarUrl: "https://example.com/avatar-local.png"
  },
  onLoad() {
    const app = getApp();
    if (app.globalData.currentUser) {
      wx.switchTab({ url: "/pages/home/index" });
    }
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
    app.globalData.currentUser = user;
    wx.setStorageSync("currentUser", user);
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
          title: "使用测试身份",
          content: "后端还未配置小程序 AppSecret，本次先使用这台设备的测试身份，数据不会和其他手机混在一起。",
          showCancel: false,
          success: () => this.loginWithLocalIdentity()
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
    try {
      await this.loginWithLocalIdentity();
    } catch (error) {
      wx.showToast({ title: "登录失败", icon: "none" });
    }
  }
});
