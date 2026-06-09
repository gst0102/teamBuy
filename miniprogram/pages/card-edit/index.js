const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    cardId: "",
    card: null,
    categories: [],
    saving: false,
    publishing: false
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
      this.setData({ card: res.data });
      this.syncCategorySelection((res.data && res.data.categoryIds) || []);
    } catch (error) {
      wx.showToast({ title: error.detail || "加载卡片失败", icon: "none" });
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
      wx.showToast({ title: error.detail || "标签加载失败", icon: "none" });
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
      await api.updateCard(this.data.cardId, {
        ownerUserId: currentUser.id,
        title: this.data.card.title.trim(),
        coverUrl: this.data.card.coverUrl || null,
        detailText: this.data.card.detailText || "",
        projectName: this.data.card.projectName,
        locationText: this.data.card.locationText,
        phone: this.data.card.phone,
        relayNotice: this.data.card.relayNotice,
        sourceUrl: this.data.card.sourceUrl,
        enabledFields: this.data.card.enabledFields || [],
        categoryIds: this.data.categories.filter((item) => item.selected).map((item) => item.id),
        relayConfig: this.data.card.relayConfig || {
          enabled: true,
          requirePhone: false,
          requireAddress: false
        }
      });
      wx.showToast({ title: "已保存", icon: "success" });
      return true;
    } catch (error) {
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
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
      wx.showToast({ title: error.detail || "发布失败", icon: "none" });
    } finally {
      this.setData({ publishing: false });
    }
  }
});
