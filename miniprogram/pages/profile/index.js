const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { buildDashboard, getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    user: null,
    totalResources: 0,
    totalPv: 0,
    totalRelay: 0,
    messageUnread: 0
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user: currentUser });
    this.loadProfileStats();
  },
  async loadProfileStats() {
    const currentUser = getCurrentUser();
    try {
      const res = await api.fetchCards({ ownerUserId: currentUser.id });
      const dashboard = buildDashboard(res.data || []);
      this.setData({
        totalResources: dashboard.totalResources,
        totalPv: dashboard.totalPv,
        totalRelay: dashboard.totalRelay
      });
      const messageUnread = await messagePlugin.fetchUnreadTotal(currentUser.id);
      this.setData({ messageUnread });
    } catch (error) {
      wx.showToast({ title: "我的数据加载失败", icon: "none" });
    }
  },
  handleGoLibrary() {
    wx.switchTab({ url: "/pages/library/index" });
  },
  handleGoVisits() {
    wx.switchTab({ url: "/pages/visits/index" });
  },
  handleGoLeads() {
    wx.navigateTo({ url: "/pages/leads/index" });
  },
  handleGoCustomers() {
    wx.navigateTo({ url: "/pages/customers/index" });
  },
  handleGoBuyerOrders() {
    wx.navigateTo({ url: "/pages/orders/index?role=buyer" });
  },
  handleGoSellerOrders() {
    wx.navigateTo({ url: "/pages/orders/index?role=seller" });
  },
  handleGoMessages() {
    messagePlugin.openMessageCenter();
  },
  async handleCreateDemoData() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    try {
      wx.showLoading({ title: "生成中" });
      const res = await api.createDemoData(currentUser.id);
      wx.hideLoading();
      wx.showModal({
        title: "测试数据已生成",
        content: `已生成 ${(res.data.notes || []).length} 条资料、${res.data.leadsCreated || 0} 条线索。可以去“我的笔记”测试房源和商品接龙。`,
        showCancel: false,
        success: () => this.loadProfileStats()
      });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || "生成失败", icon: "none" });
    }
  },
  handleGoNotes() {
    wx.navigateTo({ url: "/pages/notes/index" });
  },
  handleGoTopics() {
    wx.navigateTo({ url: "/pages/topics/index" });
  },
  handleGoShowcases() {
    wx.navigateTo({ url: "/pages/showcases/index" });
  },
  handleMemberPlaceholder() {
    wx.showToast({ title: "会员权益将在 v0.2 开放", icon: "none" });
  },
  handleSettingsPlaceholder() {
    wx.showToast({ title: "设置中心后续开放", icon: "none" });
  },
  handleLogout() {
    wx.removeStorageSync("currentUser");
    getApp().globalData.currentUser = null;
    wx.reLaunch({ url: "/pages/login/index" });
  }
});
