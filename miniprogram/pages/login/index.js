const api = require("../../services/api");
const { getRandomDefaultNickname } = require("../../utils/dashboard");

const initialNickname = getRandomDefaultNickname();

Page({
  data: {
    nickname: initialNickname,
    avatarUrl: "",
    allowMockLogin: false,
    returnUrl: "",
    loggingIn: false
  },
  onLoad(options = {}) {
    const app = getApp();
    const returnUrl = decodeURIComponent(options.returnUrl || "");
    if (app.globalData.currentUser) {
      this.redirectAfterLogin(returnUrl);
      return;
    }
    const baseUrl = (app.globalData && app.globalData.apiBaseUrl) || "";
    this.setData({
      allowMockLogin: !/^https:\/\//i.test(baseUrl),
      returnUrl
    });
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
      apiBaseUrl: app.globalData.apiBaseUrl,
      apiRoutePrefix: app.globalData.apiRoutePrefix || "",
      environmentName: app.globalData.environmentName || ""
    };
    app.globalData.currentUser = userWithBase;
    wx.setStorageSync("currentUser", userWithBase);
    this.redirectAfterLogin(this.data.returnUrl);
  },
  redirectAfterLogin(returnUrl = "") {
    const target = String(returnUrl || "").trim();
    if (target && target.startsWith("/pages/") && !target.startsWith("/pages/home/")) {
      wx.redirectTo({ url: target });
      return;
    }
    wx.switchTab({ url: "/pages/home/index" });
  },
  async loginWithLocalIdentity() {
    const res = await api.mockLogin({
      nickname: this.data.nickname || getRandomDefaultNickname(),
      avatarUrl: this.data.avatarUrl,
      openid: this.ensureMockOpenid()
    });
    this.saveLogin(res.data);
  },
  async handleWechatLogin() {
    if (this.data.loggingIn) return;
    const app = getApp();
    const baseUrl = (app.globalData && app.globalData.apiBaseUrl) || "";
    if (!/^https:\/\//i.test(baseUrl)) {
      wx.showModal({
        title: "当前是本地环境",
        content: "微信登录需要连接线上服务。本地调试请使用本地登录。",
        showCancel: false
      });
      return;
    }
    this.setData({ loggingIn: true });
    try {
      const code = await this.requestWxCode();
      const res = await api.wechatLogin({
        code,
        nickname: this.data.nickname || getRandomDefaultNickname(),
        avatarUrl: this.data.avatarUrl
      });
      this.saveLogin(res.data);
    } catch (error) {
      if ((error.detail || "").includes("微信登录未配置")) {
        wx.showModal({
          title: "登录服务暂不可用",
          content: "微信登录服务正在配置中，请稍后再试。",
          showCancel: false
        });
        return;
      }
      wx.showModal({
        title: "登录未完成",
        content: error.detail || error.message || "微信登录失败，请稍后再试。",
        showCancel: false
      });
    } finally {
      this.setData({ loggingIn: false });
    }
  },
  async handleMockLogin() {
    if (this.data.loggingIn) return;
    if (!this.data.allowMockLogin) {
      wx.showModal({
        title: "当前不可用",
        content: "当前环境不能使用便捷登录，请使用微信登录。",
        showCancel: false
      });
      return;
    }
    this.setData({ loggingIn: true });
    try {
      await this.loginWithLocalIdentity();
    } catch (error) {
      const message = error.detail || error.errMsg || "登录失败，请稍后再试";
      wx.showModal({
        title: "登录失败",
        content: message,
        showCancel: false
      });
    } finally {
      this.setData({ loggingIn: false });
    }
  }
});
