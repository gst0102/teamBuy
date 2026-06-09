const api = require("../../services/api");
const resourceStore = require("../../stores/resource-store");

function resolveRelayStatus(relay) {
  if (!relay) {
    return {
      submitted: false,
      followed: false,
      label: "登录后提交",
      title: "",
      text: "",
      icon: "✓"
    };
  }
  const followed = relay.followUpStatus === "followed";
  return {
    submitted: true,
    followed,
    label: followed ? "已跟进" : "已提交",
    title: followed ? "发布者已跟进" : "已提交接龙",
    text: followed ? "发布者已处理这条接龙，如需沟通可直接联系。" : "已提交，发布者会尽快联系你",
    icon: "✓"
  };
}

Page({
  data: {
    cardId: "",
    card: null,
    stats: null,
    phone: "",
    address: "",
    detailMedia: [],
    isOwner: false,
    relaySubmitted: false,
    relayFollowed: false,
    relaySubmitting: false,
    relayStatusLabel: "登录后提交",
    relaySubmittedTitle: "",
    relaySubmittedText: "",
    relaySubmittedIcon: "✓"
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
    const card = await resourceStore.getCard(this.data.cardId, { force: true });
    const detailMedia = (card.media || []).filter((item) => item.url !== card.coverUrl);
    const currentUser = getApp().globalData.currentUser || wx.getStorageSync("currentUser");
    this.setData({
      card,
      detailMedia,
      isOwner: !!(currentUser && card.ownerUserId === currentUser.id)
    });
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
    const currentRelay =
      res.data.currentUserRelay ||
      ((res.data.relayEntries || []).find((item) => currentUser && item.userId === currentUser.id) || null);
    const relayStatus = resolveRelayStatus(currentRelay);
    this.setData({
      stats: res.data,
      relaySubmitted: relayStatus.submitted,
      relayFollowed: relayStatus.followed,
      relayStatusLabel: relayStatus.label,
      relaySubmittedTitle: relayStatus.title,
      relaySubmittedText: relayStatus.text,
      relaySubmittedIcon: relayStatus.icon
    });
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
    if (this.data.relaySubmitted || this.data.relaySubmitting) {
      wx.showToast({ title: "你已经提交过接龙", icon: "none" });
      return;
    }
    this.setData({ relaySubmitting: true });
    try {
      await api.createRelay(this.data.cardId, {
        userId: currentUser.id,
        nickname: currentUser.nickname,
        avatarUrl: currentUser.avatarUrl,
        phone: this.data.phone,
        address: this.data.address
      });
      const relayStatus = resolveRelayStatus({ followUpStatus: "pending" });
      this.setData({
        relaySubmitted: relayStatus.submitted,
        relayFollowed: relayStatus.followed,
        relayStatusLabel: relayStatus.label,
        relaySubmittedTitle: relayStatus.title,
        relaySubmittedText: relayStatus.text,
        relaySubmittedIcon: relayStatus.icon
      });
      wx.showToast({ title: "提交成功", icon: "success" });
      await this.loadStats();
    } catch (error) {
      wx.showToast({ title: error.detail || "接龙失败", icon: "none" });
      if (error && error.detail === "你已经提交过接龙") {
        const relayStatus = resolveRelayStatus({ followUpStatus: "pending" });
        this.setData({
          relaySubmitted: relayStatus.submitted,
          relayFollowed: relayStatus.followed,
          relayStatusLabel: relayStatus.label,
          relaySubmittedTitle: relayStatus.title,
          relaySubmittedText: relayStatus.text,
          relaySubmittedIcon: relayStatus.icon
        });
        this.loadStats();
      }
    } finally {
      this.setData({ relaySubmitting: false });
    }
  },
  async handleDeleteRelay(event) {
    const currentUser = getApp().globalData.currentUser;
    if (!currentUser) {
      wx.showToast({ title: "请先登录", icon: "none" });
      return;
    }
    await api.deleteRelay(event.detail.id, currentUser.id);
    wx.showToast({ title: "已删除", icon: "success" });
    await this.loadStats();
  },
  async handleFollowRelay(event) {
    const currentUser = getApp().globalData.currentUser;
    if (!currentUser) {
      wx.showToast({ title: "请先登录", icon: "none" });
      return;
    }
    await api.followRelay(event.detail.id, currentUser.id);
    wx.showToast({ title: "已跟进", icon: "success" });
    await this.loadStats();
  },
  handleGoManager() {
    if (!this.data.isOwner) {
      wx.showToast({ title: "仅发布者可查看访问详情", icon: "none" });
      return;
    }
    wx.navigateTo({ url: `/pages/manager/index?id=${this.data.cardId}` });
  },
  handlePreviewImage(event) {
    const current = event.currentTarget.dataset.url;
    const urls = this.data.detailMedia.filter((item) => item.type === "image").map((item) => item.url);
    if (!current || !urls.length) return;
    wx.previewImage({ current, urls });
  },
  onShareAppMessage() {
    const shareData = {
      title: this.data.card ? this.data.card.title : "悦享互动宝资源",
      path: `/pages/card-view/index?id=${this.data.cardId}`
    };
    if (this.data.card && this.data.card.coverUrl) {
      shareData.imageUrl = this.data.card.coverUrl;
    }
    return shareData;
  }
});
