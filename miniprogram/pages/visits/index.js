const resourceStore = require("../../stores/resource-store");
const { buildDashboard, buildVisitGroups, getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    activeRange: "today",
    ranges: [
      { key: "today", label: "今天" },
      { key: "7d", label: "近7天" },
      { key: "30d", label: "近30天" }
    ],
    summary: {
      totalUv: 0,
      totalPv: 0,
      repeatVisits: 0,
      highIntent: 0
    },
    activeVisitFilter: "all",
    visitFilters: [
      { key: "all", label: "全部记录" },
      { key: "resource", label: "按资源" },
      { key: "intent", label: "高意向" }
    ],
    allGroups: [],
    groups: []
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadVisits();
  },
  async loadVisits() {
    const currentUser = getCurrentUser();
    try {
      const cards = await resourceStore.listCards({ ownerUserId: currentUser.id }, { force: true });
      const dashboard = buildDashboard(cards);
      const groups = buildVisitGroups(cards);
      this.setData({
        allGroups: groups,
        groups: this.filterGroups(groups, this.data.activeVisitFilter),
        summary: {
          totalUv: dashboard.totalUv,
          totalPv: dashboard.totalPv,
          repeatVisits: groups.filter((item) => item.stats.pv > item.stats.uv).length,
          highIntent: groups.filter((item) => item.highIntent).length
        }
      });
    } catch (error) {
      wx.showToast({ title: "访问记录加载失败", icon: "none" });
    }
  },
  handleRangeChange(event) {
    this.setData({ activeRange: event.currentTarget.dataset.key });
    wx.showToast({ title: "当前为聚合数据展示", icon: "none" });
  },
  filterGroups(groups, filter) {
    if (filter === "intent") {
      return groups.filter((item) => item.highIntent);
    }
    return groups;
  },
  handleVisitFilterChange(event) {
    const activeVisitFilter = event.currentTarget.dataset.key;
    this.setData({
      activeVisitFilter,
      groups: this.filterGroups(this.data.allGroups, activeVisitFilter)
    });
  },
  handleOpenManager(event) {
    wx.navigateTo({ url: `/pages/manager/index?id=${event.currentTarget.dataset.id}` });
  },
  handleOpenCard(event) {
    wx.navigateTo({ url: `/pages/card-view/index?id=${event.currentTarget.dataset.id}` });
  }
});
