const api = require("../../services/api");

Page({
  data: {
    cardId: "",
    card: null,
    stats: null,
    phone: "",
    address: "",
    detailMedia: []
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
    const card = res.data;
    const detailMedia = (card.media || []).filter((item) => item.url !== card.coverUrl);
    this.setData({ card, detailMedia });
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
  handleCopyInfo() {
    const card = this.data.card;
    wx.setClipboardData({
      data: [
        card.title,
        card.projectName,
        card.locationText,
        card.phone ? `电话：${card.phone}` : "",
        card.sourceUrl ? `链接：${card.sourceUrl}` : ""
      ].filter(Boolean).join("\n")
    });
  },
  handleCopySource() {
    if (!this.data.card.sourceUrl) {
      wx.showToast({ title: "暂无来源链接", icon: "none" });
      return;
    }
    wx.setClipboardData({ data: this.data.card.sourceUrl });
  },
  handleSharePlaceholder() {
    wx.showToast({ title: "可通过小程序右上角分享", icon: "none" });
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
  },
  handleGoManager() {
    wx.navigateTo({ url: `/pages/manager/index?id=${this.data.cardId}` });
  },
  handlePreviewImage(event) {
    const current = event.currentTarget.dataset.url;
    const urls = this.data.detailMedia.filter((item) => item.type === "image").map((item) => item.url);
    if (!current || !urls.length) return;
    wx.previewImage({ current, urls });
  },
  onShareAppMessage() {
    return {
      title: this.data.card ? this.data.card.title : "悦享互动宝资源",
      path: `/pages/card-view/index?id=${this.data.cardId}`
    };
  }
});
