const api = require("../../services/api");

Page({
  data: {
    imports: [],
    notifications: [],
    loading: false
  },
  onShow() {
    this.loadImports();
  },
  async loadImports() {
    this.setData({ loading: true });
    try {
      const res = await api.fetchPendingImports();
      const noticeRes = await api.fetchImportNotifications();
      this.setData({
        imports: res.data || [],
        notifications: noticeRes.data || []
      });
    } catch (error) {
      wx.showToast({ title: "加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  async handleClaim(event) {
    const currentUser = getApp().globalData.currentUser;
    try {
      const importId = event.currentTarget.dataset.id;
      const res = await api.claimImport(importId, currentUser.id);
      wx.navigateTo({ url: `/pages/card-edit/index?id=${res.data.card.id}` });
    } catch (error) {
      wx.showToast({ title: "认领失败", icon: "none" });
    }
  },
  handleOpenLibrary() {
    wx.switchTab({ url: "/pages/library/index" });
  },
  handleOpenVisits() {
    wx.switchTab({ url: "/pages/visits/index" });
  }
});
