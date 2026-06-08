const api = require("../../services/api");
const { inferCategory, getCurrentUser, withStats } = require("../../utils/dashboard");

Page({
  data: {
    keyword: "",
    activeFilter: "全部",
    filters: ["全部", "房源", "团购", "视频", "文档"],
    cards: [],
    displayCards: [],
    stats: {
      total: 0,
      pv: 0,
      tags: 0,
      today: 0
    }
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadCards();
  },
  handleKeywordChange(event) {
    this.setData({ keyword: event.detail.value });
  },
  async loadCards() {
    const currentUser = getCurrentUser();
    try {
      const res = await api.fetchCards({
        ownerUserId: currentUser ? currentUser.id : "",
        keyword: this.data.keyword
      });
      const cards = (res.data || []).map((card) => ({
        ...withStats(card),
        categoryName: inferCategory(card)
      }));
      const stats = {
        total: cards.length,
        pv: cards.reduce((sum, card) => sum + card.stats.pv, 0),
        tags: new Set(cards.map((card) => card.categoryName)).size,
        today: cards.reduce((sum, card) => sum + card.stats.pv, 0)
      };
      this.setData({ cards, stats });
      this.applyFilter();
    } catch (error) {
      wx.showToast({ title: "加载素材失败", icon: "none" });
    }
  },
  applyFilter() {
    const displayCards = this.data.activeFilter === "全部"
      ? this.data.cards
      : this.data.cards.filter((card) => card.categoryName === this.data.activeFilter);
    this.setData({ displayCards });
  },
  handleSearch() {
    this.loadCards();
  },
  handleFilter(event) {
    this.setData({ activeFilter: event.currentTarget.dataset.filter });
    this.applyFilter();
  },
  handleOpen(event) {
    const id = event.currentTarget.dataset.id || event.detail.id;
    wx.navigateTo({ url: `/pages/card-edit/index?id=${id}` });
  },
  handleManage(event) {
    const id = event.currentTarget.dataset.id || event.detail.id;
    wx.navigateTo({ url: `/pages/manager/index?id=${id}` });
  },
  handleView(event) {
    wx.navigateTo({ url: `/pages/card-view/index?id=${event.currentTarget.dataset.id}` });
  },
  handleGoImports() {
    wx.switchTab({ url: "/pages/imports/index" });
  },
  handleManualAdd() {
    wx.showToast({ title: "请先通过客服导入后编辑", icon: "none" });
  },
  handleTagPlaceholder() {
    wx.showToast({ title: "标签管理将在后续开放", icon: "none" });
  }
});
