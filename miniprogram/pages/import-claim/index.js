const api = require("../../services/api");

Page({
  data: {
    token: "",
    claiming: false,
    showRetry: false,
    statusTitle: "正在接收房源助手结果",
    statusDesc: "会自动保存到你的账号，之后发给助手的房源也会归到这里。"
  },
  onLoad(options = {}) {
    const token = decodeURIComponent(options.token || "");
    this.setData({ token });
    this.claimWithCurrentUser(token);
  },
  onShow() {
    if (this.data.token && !this.data.claiming) {
      this.claimWithCurrentUser(this.data.token);
    }
  },
  ensureLogin(token) {
    const currentUser = getApp().globalData.currentUser;
    if (currentUser && currentUser.id) return currentUser;
    const returnUrl = encodeURIComponent(`/pages/import-claim/index?token=${encodeURIComponent(token)}`);
    wx.redirectTo({ url: `/pages/login/index?returnUrl=${returnUrl}` });
    return null;
  },
  async claimWithCurrentUser(token) {
    if (!token) {
      this.setData({
        showRetry: false,
        statusTitle: "链接无效",
        statusDesc: "请从房源助手发回的小程序链接重新打开。"
      });
      return;
    }
    const currentUser = this.ensureLogin(token);
    if (!currentUser) return;
    if (this.data.claiming) return;
    this.setData({
      claiming: true,
      showRetry: false,
      statusTitle: "正在接收房源助手结果",
      statusDesc: "马上保存到你的账号。"
    });
    try {
      const res = await api.claimImportByToken(token, currentUser.id);
      const noteId = res.data && res.data.note && res.data.note.id;
      const cardId = res.data && res.data.card && res.data.card.id;
      wx.showToast({ title: "已保存到账号", icon: "success" });
      setTimeout(() => {
        if (noteId) {
          wx.redirectTo({ url: `/pages/note-edit/index?id=${noteId}` });
          return;
        }
        if (cardId) {
          wx.redirectTo({ url: `/pages/card-edit/index?id=${cardId}` });
          return;
        }
        wx.switchTab({ url: "/pages/library/index" });
      }, 500);
    } catch (error) {
      this.setData({
        showRetry: true,
        statusTitle: "接收失败",
        statusDesc: error.detail || error.message || "链接可能已过期，请让房源助手重新发送。"
      });
    } finally {
      this.setData({ claiming: false });
    }
  },
  handleRetry() {
    this.claimWithCurrentUser(this.data.token);
  }
});
