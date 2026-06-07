const api = require("../../services/api");

Page({
  data: {
    cardId: "",
    card: null,
    stats: null,
    phone: "",
    address: ""
  },
  onLoad(query) {
    this.setData({ cardId: query.id });
  },
  async onShow() {
    await this.loadCard();
    await this.recordView();
    await this.loadStats();
  },
  async loadCard() {
    const res = await api.fetchCard(this.data.cardId);
    this.setData({ card: res.data });
  },
  async recordView() {
    const currentUser = getApp().globalData.currentUser;
    await api.recordView(this.data.cardId, currentUser ? {
      viewerUserId: currentUser.id,
      nickname: currentUser.nickname,
      avatarUrl: currentUser.avatarUrl
    } : {
      anonymousId: `anon_${Date.now()}`
    });
  },
  async loadStats() {
    const currentUser = getApp().globalData.currentUser;
    const res = await api.fetchStats(this.data.cardId, currentUser ? currentUser.id : "");
    this.setData({ stats: res.data });
  },
  handleCall() {
    if (!this.data.card.phone) {
      return;
    }
    wx.makePhoneCall({
      phoneNumber: this.data.card.phone
    });
  },
  handlePhoneChange(event) {
    this.setData({ phone: event.detail.value });
  },
  handleAddressChange(event) {
    this.setData({ address: event.detail.value });
  },
  async handleRelaySubmit() {
    const currentUser = getApp().globalData.currentUser;
    if (!currentUser) {
      wx.showToast({ title: "请先登录后接龙", icon: "none" });
      return;
    }
    try {
      await api.createRelay(this.data.cardId, {
        userId: currentUser.id,
        nickname: currentUser.nickname,
        avatarUrl: currentUser.avatarUrl,
        phone: this.data.phone,
        address: this.data.address
      });
      wx.showToast({ title: "接龙成功", icon: "success" });
      this.loadStats();
    } catch (error) {
      wx.showToast({ title: error.detail || "接龙失败", icon: "none" });
    }
  }
});

