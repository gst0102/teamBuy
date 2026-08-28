const api = require("../../services/api");
const subscription = require("../../services/subscription");

const LOCAL_TEST_NICKNAME = "测试用户";

function getAppInstance() {
  try {
    return typeof getApp === "function" ? getApp() || null : null;
  } catch (error) {
    return null;
  }
}

function getGlobalData() {
  const app = getAppInstance();
  return (app && app.globalData) || {};
}

function decodeReturnUrl(value) {
  try {
    return decodeURIComponent(value || "");
  } catch (error) {
    return "";
  }
}

function isLocalAvatarPath(value) {
  const text = String(value || "").trim();
  return /^(wxfile|file):/i.test(text) || /^\/tmp\//i.test(text) || /^http:\/\/tmp\//i.test(text);
}

Page({
  data: {
    allowMockLogin: false,
    returnUrl: "",
    loggingIn: false,
    loginCoverFailed: false,
    legalAgreed: false,
    loginProfileDraft: {
      nickname: "",
      avatarUrl: ""
    }
  },
  onLoad(options = {}) {
    const app = getAppInstance();
    const globalData = getGlobalData();
    if (app && app.globalData) app.globalData.authRecoveryInFlight = false;
    const returnUrl = decodeReturnUrl(options.returnUrl);
    if (globalData.currentUser) {
      this.redirectAfterLogin(returnUrl);
      return;
    }
    const baseUrl = globalData.apiBaseUrl || "";
    this.setData({
      allowMockLogin: !/^https:\/\//i.test(baseUrl),
      returnUrl
    });
  },
  handleLoginCoverError() {
    this.setData({ loginCoverFailed: true });
  },
  handleChooseAvatarFromAlbum() {
    const handleSuccess = (result = {}) => {
      const firstFile = Array.isArray(result.tempFiles) ? result.tempFiles[0] : null;
      const avatarUrl = String((firstFile && firstFile.tempFilePath) || (result.tempFilePaths || [])[0] || "").trim();
      if (!avatarUrl) {
        wx.showToast({ title: "未选择头像", icon: "none" });
        return;
      }
      this.setData({ "loginProfileDraft.avatarUrl": avatarUrl });
    };
    const handleFail = (error = {}) => {
      if (/cancel/i.test(String(error.errMsg || ""))) return;
      wx.showToast({ title: "选择头像失败，请重试", icon: "none" });
    };
    if (typeof wx.chooseMedia === "function") {
      wx.chooseMedia({ count: 1, mediaType: ["image"], sourceType: ["album"], success: handleSuccess, fail: handleFail });
      return;
    }
    if (typeof wx.chooseImage !== "function") {
      wx.showToast({ title: "当前版本暂不支持选择头像", icon: "none" });
      return;
    }
    wx.chooseImage({ count: 1, sourceType: ["album"], success: handleSuccess, fail: handleFail });
  },
  handleLoginNicknameInput(event) {
    this.setData({ "loginProfileDraft.nickname": event.detail.value });
  },
  handleToggleLegalAgree() {
    this.setData({ legalAgreed: !this.data.legalAgreed });
  },
  handleOpenTerms() {
    wx.navigateTo({ url: "/pages/legal/terms/index" });
  },
  handleOpenPrivacy() {
    wx.navigateTo({ url: "/pages/legal/privacy/index" });
  },
  ensureLegalAgreed() {
    if (this.data.legalAgreed) return true;
    wx.showToast({ title: "请先阅读并同意协议", icon: "none" });
    return false;
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
  persistLoginUser(user) {
    const app = getAppInstance();
    if (!app || !app.globalData) {
      throw { detail: "小程序正在启动，请稍后重试" };
    }
    const userWithBase = {
      ...user,
      apiBaseUrl: app.globalData.apiBaseUrl,
      apiRoutePrefix: app.globalData.apiRoutePrefix || "",
      environmentName: app.globalData.environmentName || ""
    };
    app.globalData.currentUser = userWithBase;
    wx.setStorageSync("currentUser", userWithBase);
    subscription.preloadViewNotificationSubscriptionConfig(userWithBase.id);
    return userWithBase;
  },
  async saveLogin(user) {
    const app = getAppInstance();
    if (app && app.globalData) app.globalData.authRecoveryInFlight = false;
    let finalUser = this.persistLoginUser(user);
    const draft = this.data.loginProfileDraft || {};
    const nickname = String(draft.nickname || "").trim();
    let avatarUrl = String(draft.avatarUrl || "").trim();
    if (nickname || isLocalAvatarPath(avatarUrl)) {
      try {
        if (isLocalAvatarPath(avatarUrl)) {
          const uploaded = await api.uploadAsset({
            filePath: avatarUrl,
            mediaType: "image",
            ownerUserId: finalUser.id
          });
          avatarUrl = uploaded.url || "";
        }
        const updated = await api.updateUserProfile(finalUser.id, {
          nickname: nickname || finalUser.nickname,
          avatarUrl: avatarUrl || finalUser.avatarUrl || ""
        });
        finalUser = this.persistLoginUser(updated.data || finalUser);
      } catch (error) {
        wx.showToast({ title: "已登录，头像或昵称稍后可在个人资料补充", icon: "none", duration: 2200 });
      }
    }
    this.setData({ "loginProfileDraft.avatarUrl": "" });
    this.redirectAfterLogin(this.data.returnUrl);
  },
  redirectAfterLogin(returnUrl = "") {
    const target = String(returnUrl || "").trim();
    const isMiniProgramPath = target.startsWith("/pages/") || target.startsWith("/subpackages/");
    if (target && isMiniProgramPath && !target.startsWith("/pages/home/")) {
      wx.redirectTo({ url: target });
      return;
    }
    wx.switchTab({ url: "/pages/home/index" });
  },
  handleSkipLogin() {
    // 登录是受保护业务动作的门槛，拒绝授权后只回到公开首页，不能再次回到原门槛页面。
    wx.switchTab({
      url: "/pages/home/index",
      fail: () => wx.reLaunch({ url: "/pages/home/index" })
    });
  },
  async loginWithLocalIdentity() {
    const res = await api.mockLogin({
      nickname: LOCAL_TEST_NICKNAME,
      openid: this.ensureMockOpenid()
    });
    await this.saveLogin(res.data);
  },
  async handleWechatLogin() {
    if (this.data.loggingIn) return;
    if (!this.ensureLegalAgreed()) return;
    const app = getAppInstance();
    const globalData = getGlobalData();
    const baseUrl = globalData.apiBaseUrl || "";
    if (!app || !app.globalData) {
      wx.showToast({ title: "小程序正在启动，请稍后重试", icon: "none" });
      return;
    }
    if (!/^https:\/\//i.test(baseUrl)) {
      wx.showModal({
        title: "当前是本地环境",
        content: "微信登录需要连接线上服务。本地调试请使用本地登录。",
        showCancel: false
      });
      return;
    }
    this.setData({ loggingIn: true });
    wx.showLoading({ title: "登录中" });
    try {
      const code = await this.requestWxCode();
      const res = await api.wechatLogin({ code });
      await this.saveLogin(res.data);
    } catch (error) {
      wx.hideLoading();
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
      wx.hideLoading();
      this.setData({ loggingIn: false });
    }
  },
  async handleMockLogin() {
    if (this.data.loggingIn) return;
    if (!this.ensureLegalAgreed()) return;
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
