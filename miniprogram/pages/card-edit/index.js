const api = require("../../services/api");

Page({
  data: {
    cardId: "",
    card: null
  },
  onLoad(query) {
    this.setData({ cardId: query.id });
  },
  onShow() {
    this.loadCard();
  },
  async loadCard() {
    try {
      const res = await api.fetchCard(this.data.cardId);
      this.setData({ card: res.data });
    } catch (error) {
      wx.showToast({ title: "加载卡片失败", icon: "none" });
    }
  },
  handleFieldChange(event) {
    const field = event.currentTarget.dataset.field;
    this.setData({
      [`card.${field}`]: event.detail.value
    });
  },
  handleToggleRelayPhone(event) {
    this.setData({
      "card.relayConfig.requirePhone": event.detail.value
    });
  },
  async handleSave() {
    const currentUser = getApp().globalData.currentUser;
    try {
      await api.updateCard(this.data.cardId, {
        ownerUserId: currentUser.id,
        title: this.data.card.title,
        coverUrl: this.data.card.coverUrl,
        detailText: this.data.card.detailText,
        projectName: this.data.card.projectName,
        locationText: this.data.card.locationText,
        phone: this.data.card.phone,
        relayNotice: this.data.card.relayNotice,
        sourceUrl: this.data.card.sourceUrl,
        enabledFields: this.data.card.enabledFields || [],
        categoryIds: this.data.card.categoryIds || [],
        relayConfig: this.data.card.relayConfig
      });
      wx.showToast({ title: "已保存", icon: "success" });
    } catch (error) {
      wx.showToast({ title: "保存失败", icon: "none" });
    }
  },
  async handlePublish() {
    const currentUser = getApp().globalData.currentUser;
    try {
      await api.publishCard(this.data.cardId, currentUser.id);
      wx.navigateTo({ url: `/pages/card-view/index?id=${this.data.cardId}` });
    } catch (error) {
      wx.showToast({ title: "发布失败", icon: "none" });
    }
  }
});

