const api = require("../../services/api");

function getCurrentUser() {
  const app = getApp();
  return (app.globalData && app.globalData.currentUser) || wx.getStorageSync("currentUser") || null;
}

Page({
  data: {
    token: "",
    status: "loading",
    title: "正在确认绑定",
    message: "请稍候"
  },

  onLoad(options = {}) {
    const token = String(options.token || "").trim();
    this.setData({ token });
    if (!token) {
      this.setData({ status: "failed", title: "绑定链接无效", message: "请从资料助手发来的最新卡片进入。" });
      return;
    }
    const user = getCurrentUser();
    if (!user || !user.id) {
      wx.redirectTo({
        url: `/pages/login/index?returnUrl=${encodeURIComponent(`/pages/wecom-bind/index?token=${encodeURIComponent(token)}`)}`
      });
      return;
    }
    this.bindCard(user);
  },

  bindCard(user) {
    if (this.data.status === "binding") return;
    this.setData({ status: "binding", title: "正在确认绑定", message: "正在把企业微信和当前小程序账号关联起来。" });
    api.bindWecomCard(this.data.token, user.id).then((response) => {
      const data = (response && response.data) || {};
      if (data.status === "bound" || data.status === "already_bound") {
        this.setData({ status: "success", title: "绑定成功", message: "以后把资料发给企业微信资料助手，就会自动进入你的资料库。" });
        return;
      }
      throw new Error("绑定状态异常");
    }).catch((error) => {
      const statusCode = Number(error && error.statusCode);
      const message = statusCode === 409
        ? "这张卡片已经绑定了其他小程序账号。"
        : statusCode === 410
          ? "这张绑定卡片已失效，请重新添加资料助手。"
          : (error && (error.detail || error.message)) || "绑定失败，请稍后从最新卡片重试。";
      this.setData({ status: "failed", title: "绑定未完成", message });
    });
  },

  handleBackHome() {
    wx.switchTab({ url: "/pages/home/index" });
  },

  handleRetry() {
    const user = getCurrentUser();
    if (user && user.id) this.bindCard(user);
  }
});
