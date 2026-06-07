const api = require("../../services/api");

Page({
  data: {
    keyword: "",
    cards: []
  },
  onShow() {
    this.loadCards();
  },
  handleKeywordChange(event) {
    this.setData({ keyword: event.detail.value });
  },
  async loadCards() {
    const currentUser = getApp().globalData.currentUser;
    try {
      const res = await api.fetchCards({
        ownerUserId: currentUser ? currentUser.id : "",
        keyword: this.data.keyword
      });
      this.setData({ cards: res.data || [] });
    } catch (error) {
      wx.showToast({ title: "加载素材失败", icon: "none" });
    }
  },
  handleSearch() {
    this.loadCards();
  },
  handleOpen(event) {
    const id = event.detail.id;
    wx.navigateTo({ url: `/pages/card-edit/index?id=${id}` });
  },
  handleManage(event) {
    const id = event.detail.id;
    wx.navigateTo({ url: `/pages/manager/index?id=${id}` });
  }
});

