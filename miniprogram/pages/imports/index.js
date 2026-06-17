const api = require("../../services/api");

const TEMPLATE_OPTIONS = [
  {
    id: "general",
    label: "通用",
    hint: "只保留标题和内容，适合普通资料。",
    fields: ["标题", "内容"]
  },
  {
    id: "realtor",
    label: "中介",
    hint: "适合房源、客户需求、带看记录。",
    fields: ["标题", "内容", "电话", "位置", "预算/价格"]
  },
  {
    id: "groupbuy",
    label: "团购",
    hint: "适合商品、价格、截单、取货说明。",
    fields: ["标题", "内容", "价格", "截止时间", "取货方式"]
  }
];

function normalizeImport(item, selectedTemplate = "general") {
  const note = item.generatedNote || {};
  const body = note.body || note.summary || item.titleCandidate || "";
  return {
    ...item,
    selectedTemplate,
    template: TEMPLATE_OPTIONS.find((option) => option.id === selectedTemplate) || TEMPLATE_OPTIONS[0],
    displayTitle: note.title || item.titleCandidate || "未命名资料",
    displayBody: body,
    displayMeta: note.locationText || note.phone || item.sourceType || "企业微信导入"
  };
}

Page({
  data: {
    imports: [],
    notifications: [],
    loading: false,
    templates: TEMPLATE_OPTIONS
  },
  onShow() {
    this.loadImports();
  },
  async loadImports() {
    this.setData({ loading: true });
    try {
      const res = await api.fetchPendingImports();
      const noticeRes = await api.fetchImportNotifications();
      this.setData({
        imports: (res.data || []).map((item) => normalizeImport(item)),
        notifications: noticeRes.data || []
      });
    } catch (error) {
      wx.showToast({ title: "加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  async handleClaim(event) {
    const currentUser = getApp().globalData.currentUser;
    try {
      const importId = event.currentTarget.dataset.id;
      const res = await api.claimImport(importId, currentUser.id);
      const selected = this.data.imports.find((item) => item.id === importId);
      const template = selected ? selected.selectedTemplate : "general";
      const noteId = res.data.note && res.data.note.id;
      if (noteId) {
        wx.navigateTo({ url: `/pages/note-edit/index?id=${noteId}&template=${template}` });
        return;
      }
      wx.navigateTo({ url: `/pages/card-edit/index?id=${res.data.card.id}` });
    } catch (error) {
      wx.showToast({ title: "认领失败", icon: "none" });
    }
  },
  handleSelectTemplate(event) {
    const importId = event.currentTarget.dataset.id;
    const template = event.currentTarget.dataset.template;
    this.setData({
      imports: this.data.imports.map((item) => (
        item.id === importId ? normalizeImport(item, template) : item
      ))
    });
  },
  handleOpenLibrary() {
    wx.switchTab({ url: "/pages/library/index" });
  },
  handleOpenVisits() {
    wx.switchTab({ url: "/pages/visits/index" });
  }
});
