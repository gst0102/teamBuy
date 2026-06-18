const resourceStore = require("../../stores/resource-store");
const { buildDashboard, getCurrentUser } = require("../../utils/dashboard");
const { navigateToResourceView } = require("../../utils/resource-navigation");

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
      const cards = await resourceStore.listCards({ ownerUserId: currentUser.id }, { force: true });
      const dashboard = buildDashboard(cards || []);
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
  handleGoImports() {
    wx.navigateTo({ url: "/pages/imports/index" });
  },
  handleGoLibrary() {
    wx.switchTab({ url: "/pages/library/index" });
  },
  handleGoVisits() {
    wx.switchTab({ url: "/pages/visits/index" });
  },
  handleOpenResource(event) {
    const id = event.currentTarget.dataset.id;
    const card = this.data.hotResources.find((item) => item.id === id) || id;
    navigateToResourceView(card);
  },
  handleManageResource(event) {
    wx.navigateTo({ url: `/pages/manager/index?id=${event.currentTarget.dataset.id}` });
  },
  handleInvitePlaceholder() {
    wx.showToast({ title: "邀请权益将在 v0.2 开放", icon: "none" });
  }
});
