const api = require("../../services/api");
const { buildDashboard, getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    loading: false,
    totalResources: 0,
    totalPv: 0,
    totalUv: 0,
    totalRelay: 0,
    viewers: [],
    hotResources: []
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadDashboard();
  },
  async loadDashboard() {
    const currentUser = getCurrentUser();
    this.setData({ loading: true });
    try {
      const res = await api.fetchCards({ ownerUserId: currentUser.id });
      const dashboard = buildDashboard(res.data || []);
      this.setData(dashboard);
    } catch (error) {
      wx.showToast({ title: "首页数据加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleQuickAdd() {
    wx.switchTab({ url: "/pages/resource-create/index" });
  },
  handleGoLibrary() {
    wx.switchTab({ url: "/pages/library/index" });
  },
  handleGoVisits() {
    wx.switchTab({ url: "/pages/visits/index" });
  },
  handleOpenResource(event) {
    wx.navigateTo({ url: `/pages/card-view/index?id=${event.currentTarget.dataset.id}` });
  },
  handleManageResource(event) {
    wx.navigateTo({ url: `/pages/manager/index?id=${event.currentTarget.dataset.id}` });
  },
  handleInvitePlaceholder() {
    wx.showToast({ title: "邀请权益将在 v0.2 开放", icon: "none" });
  }
});
