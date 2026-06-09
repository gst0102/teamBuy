const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

function statusLabel(status) {
  return status === "published" ? "已发布" : "未发布";
}

Page({
  data: {
    cardId: "",
    card: null,
    categories: [],
    saving: false,
    publishing: false,
    statusLabel: ""
  },
  onLoad(query) {
    this.setData({ cardId: query.id });
  },
  async onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    await this.loadAll();
  },
  async loadAll() {
    await Promise.all([this.loadCard(), this.loadCategories()]);
  },
  async loadCard() {
    try {
      const res = await api.fetchCard(this.data.cardId);
      const card = {
        ...res.data,
        relayConfig: {
          enabled: !(res.data && res.data.relayConfig && res.data.relayConfig.enabled === false),
          requirePhone: !!(res.data && res.data.relayConfig && res.data.relayConfig.requirePhone),
          requireAddress: !!(res.data && res.data.relayConfig && res.data.relayConfig.requireAddress)
        }
      };
      this.setData({ card, statusLabel: statusLabel(card.status) });
      this.syncCategorySelection(card.categoryIds || []);
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "卡片加载失败", icon: "none" });
    }
  },
  async loadCategories() {
    const currentUser = getCurrentUser();
    if (!currentUser) return;
    try {
      const res = await api.fetchCategories(currentUser.id);
      this.setData({ categories: res.data || [] });
      this.syncCategorySelection(this.data.card ? this.data.card.categoryIds || [] : []);
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "标签加载失败", icon: "none" });
    }
  },
  syncCategorySelection(categoryIds) {
    const selected = categoryIds || [];
    this.setData({
      categories: this.data.categories.map((item) => ({
        ...item,
        selected: selected.includes(item.id)
      }))
    });
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
  handleToggleRelayAddress(event) {
    this.setData({
      "card.relayConfig.requireAddress": event.detail.value
    });
  },
  handleCategoryToggle(event) {
    const id = event.currentTarget.dataset.id;
    const categories = this.data.categories.map((item) => ({
      ...item,
      selected: item.id === id ? !item.selected : item.selected
    }));
    this.setData({
      categories,
      "card.categoryIds": categories.filter((item) => item.selected).map((item) => item.id)
    });
  },
  handleGoTagManage() {
    wx.navigateTo({ url: "/pages/tag-manage/index" });
  },
  buildPayload(currentUser) {
    const card = this.data.card || {};
    return {
      ownerUserId: currentUser.id,
      title: (card.title || "").trim(),
      coverUrl: card.coverUrl || null,
      detailText: card.detailText || "",
      projectName: card.projectName || null,
      locationText: card.locationText || null,
      phone: card.phone || null,
      relayNotice: card.relayNotice || null,
      sourceUrl: card.sourceUrl || null,
      enabledFields: Array.isArray(card.enabledFields) ? card.enabledFields : [],
      categoryIds: this.data.categories.filter((item) => item.selected).map((item) => item.id),
      media: Array.isArray(card.media)
        ? card.media.map((item, index) => ({
            type: item.type,
            url: item.url,
            sortOrder: item.sortOrder || index + 1
          }))
        : [],
      relayConfig: {
        enabled: !(card.relayConfig && card.relayConfig.enabled === false),
        requirePhone: !!(card.relayConfig && card.relayConfig.requirePhone),
        requireAddress: !!(card.relayConfig && card.relayConfig.requireAddress)
      }
    };
  },
  async handleSave() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return false;
    }
    if (!this.data.card || !this.data.card.title || !this.data.card.title.trim()) {
      wx.showToast({ title: "标题不能为空", icon: "none" });
      return false;
    }
    this.setData({ saving: true });
    try {
      const res = await api.updateCard(this.data.cardId, this.buildPayload(currentUser));
      const updatedCard = res.data || this.data.card;
      this.setData({
        card: {
          ...this.data.card,
          ...updatedCard
        },
        statusLabel: statusLabel(updatedCard.status || this.data.card.status)
      });
      wx.showToast({ title: "已保存", icon: "success" });
      return true;
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "保存失败", icon: "none" });
      return false;
    } finally {
      this.setData({ saving: false });
    }
  },
  async handlePublish() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const saved = await this.handleSave();
    if (!saved) return;
    this.setData({ publishing: true });
    try {
      await api.publishCard(this.data.cardId, currentUser.id);
      wx.navigateTo({ url: `/pages/card-view/index?id=${this.data.cardId}` });
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "发布失败", icon: "none" });
    } finally {
      this.setData({ publishing: false });
    }
  }
});
