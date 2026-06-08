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
  async handleMockImport() {
    try {
      await api.triggerMockImport({
        externalUserId: "external_demo",
        conversationId: "conv_demo",
        fixture: "note"
      });
      wx.showToast({ title: "已生成 mock 导入", icon: "none" });
      this.loadImports();
    } catch (error) {
      wx.showToast({ title: "导入失败", icon: "none" });
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
