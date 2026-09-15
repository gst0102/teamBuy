const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    noteId: "",
    user: null,
    card: null,
    loading: true,
    error: false,
    unlocking: false,
    reportingContact: false
  },

  onLoad(options = {}) {
    this.setData({ noteId: options.id || "" });
  },

  onShow() {
    this.setData({ user: getCurrentUser() });
    this.loadDetail();
  },

  async loadDetail() {
    if (!this.data.noteId) {
      this.setData({ loading: false, error: true });
      return;
    }
    const requestSeq = (this._requestSeq || 0) + 1;
    this._requestSeq = requestSeq;
    this.setData({ loading: true, error: false });
    try {
      const user = getCurrentUser();
      const result = await api.fetchBusinessOpportunityCard(this.data.noteId, user && user.id);
      if (requestSeq !== this._requestSeq) return;
      this.setData({ card: result.data || null, loading: false });
    } catch (error) {
      if (requestSeq !== this._requestSeq) return;
      this.setData({ loading: false, error: true });
    }
  },

  handleUnlock() {
    const user = getCurrentUser();
    if (!user || !user.id) {
      wx.navigateTo({ url: `/pages/login/index?returnUrl=${encodeURIComponent(`/pages/business-opportunity-detail/index?id=${this.data.noteId}`)}` });
      return;
    }
    if (this.data.unlocking || !this.data.card || !this.data.card.contactLocked) return;
    wx.showModal({
      title: "查看完整联系方式",
      content: `将消耗 ${this.data.card.viewCostPoints || 1} 个基础积分，24小时内再次查看不重复扣分。`,
      confirmText: "确认查看",
      cancelText: "暂不查看",
      success: async (result) => {
        if (!result.confirm) return;
        this.setData({ unlocking: true });
        try {
          const response = await api.unlockBusinessOpportunityCard(this.data.noteId, user.id);
          const payload = response.data || {};
          this.setData({ card: payload.card || this.data.card, unlocking: false });
          wx.showToast({ title: payload.duplicate ? "联系方式已恢复" : "已解锁联系方式", icon: "success" });
        } catch (error) {
          this.setData({ unlocking: false });
          wx.showToast({ title: error.detail || error.message || "积分不足，暂时无法查看", icon: "none" });
        }
      }
    });
  },

  handleCopyContact(event) {
    const index = Number(event.currentTarget.dataset.index);
    const contact = (this.data.card && this.data.card.contacts || [])[index];
    if (!contact || !contact.contactValue || contact.contactType === "wechatQr") return;
    wx.setClipboardData({ data: contact.contactValue, success: () => wx.showToast({ title: `${contact.label}已复制`, icon: "success" }) });
  },

  handleCall(event) {
    const index = Number(event.currentTarget.dataset.index);
    const contact = (this.data.card && this.data.card.contacts || [])[index];
    const phone = String(contact && contact.contactValue || "").replace(/[^\d+]/g, "");
    if (!phone) return;
    wx.makePhoneCall({ phoneNumber: phone });
  },

  handlePreviewQr(event) {
    const index = Number(event.currentTarget.dataset.index);
    const contact = (this.data.card && this.data.card.contacts || [])[index];
    if (contact && contact.contactValue) wx.previewImage({ current: contact.contactValue, urls: [contact.contactValue] });
  },

  handleReportContactInvalid() {
    const user = getCurrentUser();
    const card = this.data.card;
    if (!user || !user.id) {
      wx.navigateTo({ url: `/pages/login/index?returnUrl=${encodeURIComponent(`/pages/business-opportunity-detail/index?id=${this.data.noteId}`)}` });
      return;
    }
    if (!card || card.isMine || card.contactLocked || !card.contacts || !card.contacts.length || this.data.reportingContact) return;
    wx.showModal({
      title: "举报联系方式",
      content: "如果电话或微信已失效，可以提交“联系方式失效”反馈，帮助其他人避坑。",
      confirmText: "确认举报",
      cancelText: "暂不举报",
      success: async (result) => {
        if (!result.confirm) return;
        this.setData({ reportingContact: true });
        try {
          const response = await api.reportBusinessOpportunityContactInvalid(this.data.noteId, user.id, "联系方式失效");
          const payload = response.data || {};
          this.setData({
            card: payload.card || {
              ...card,
              contactWarning: payload.contactWarning || card.contactWarning,
              contactInvalidReportCount: payload.contactInvalidReportCount || card.contactInvalidReportCount
            },
            reportingContact: false
          });
          wx.showToast({ title: payload.duplicate ? "你已反馈过" : "感谢反馈", icon: "success" });
        } catch (error) {
          this.setData({ reportingContact: false });
          wx.showToast({ title: error.detail || error.message || "提交失败，请稍后重试", icon: "none" });
        }
      }
    });
  },

  handleOpenFeatured(event) {
    const id = event.currentTarget.dataset.id;
    if (id) wx.navigateTo({ url: `/pages/note-preview/index?id=${encodeURIComponent(id)}` });
  },

  handleEdit() {
    const id = this.data.card && this.data.card.noteId;
    if (id) wx.navigateTo({ url: `/subpackages/workbench/business-card-studio/index?id=${encodeURIComponent(id)}` });
  }
});
