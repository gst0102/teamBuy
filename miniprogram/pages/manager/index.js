const api = require("../../services/api");

Page({
  data: {
    cardId: "",
    card: null,
    stats: null
  },
  onLoad(query) {
    this.setData({ cardId: query.id });
  },
  onShow() {
    this.loadAll();
  },
  async loadAll() {
    const currentUser = getApp().globalData.currentUser;
    const [cardRes, statsRes] = await Promise.all([
      api.fetchCard(this.data.cardId),
      api.fetchStats(this.data.cardId, currentUser.id)
    ]);
    this.setData({
      card: cardRes.data,
      stats: statsRes.data
    });
  },
  async handleDelete(event) {
    const currentUser = getApp().globalData.currentUser;
    await api.deleteRelay(event.detail.id, currentUser.id);
    wx.showToast({ title: "已删除", icon: "success" });
    this.loadAll();
  },
  async handleFollow(event) {
    const currentUser = getApp().globalData.currentUser;
    await api.followRelay(event.detail.id, currentUser.id);
    wx.showToast({ title: "已跟进", icon: "success" });
    this.loadAll();
  },
  async handleDuplicate() {
    const currentUser = getApp().globalData.currentUser;
    const res = await api.duplicateCard(this.data.cardId, currentUser.id);
    wx.navigateTo({ url: `/pages/card-edit/index?id=${res.data.id}` });
  }
});

