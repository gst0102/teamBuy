const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

const TEMPLATE_META = {
  general: {
    label: "通用资料",
    fields: ["标题", "摘要", "正文"]
  },
  realtor: {
    label: "中介信息",
    fields: ["电话", "位置", "预算/价格", "客户需求"]
  },
  groupbuy: {
    label: "团购信息",
    fields: ["价格", "截止时间", "取货方式", "联系方式"]
  }
};

Page({
  data: {
    user: null,
    noteId: "",
    template: TEMPLATE_META.general,
    form: {
      title: "",
      summary: "",
      body: "",
      coverUrl: "",
      phone: "",
      locationText: "",
      categoryIds: [],
      media: [],
      visibilityConfig: {}
    },
    isBookmark: false,
    saving: false
  },
  onLoad(options) {
    this.setData({
      noteId: options.id || "",
      template: TEMPLATE_META[options.template] || TEMPLATE_META.general
    });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    this.loadNote();
  },
  async loadNote() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    try {
      const res = await api.fetchNote(noteId, user.id);
      const note = res.data || {};
      this.setData({
        form: {
          title: note.title || "",
          summary: note.summary || "",
          body: note.body || "",
          coverUrl: note.coverUrl || "",
          phone: note.phone || "",
          locationText: note.locationText || "",
          categoryIds: note.categoryIds || [],
          media: note.media || [],
          visibilityConfig: note.visibilityConfig || {}
        },
        isBookmark: (note.visibilityConfig || {}).contentMode === "bookmark"
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "笔记加载失败", icon: "none" });
    }
  },
  handleInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`form.${key}`]: event.detail.value });
  },
  async handleSave() {
    const { user, noteId, form } = this.data;
    if (!form.title.trim()) {
      wx.showToast({ title: "标题不能为空", icon: "none" });
      return;
    }
    this.setData({ saving: true });
    try {
      await api.updateNote(noteId, {
        ownerUserId: user.id,
        ...form,
        title: form.title.trim(),
        body: form.body.trim() || form.title.trim()
      });
      wx.showToast({ title: "已保存", icon: "success" });
      setTimeout(() => wx.navigateBack(), 350);
    } catch (error) {
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  async handleOrganize() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    this.setData({ saving: true });
    try {
      const res = await api.organizeNote(noteId, user.id);
      const note = res.data || {};
      this.setData({
        form: {
          title: note.title || "",
          summary: note.summary || "",
          body: note.body || "",
          coverUrl: note.coverUrl || "",
          phone: note.phone || "",
          locationText: note.locationText || "",
          categoryIds: note.categoryIds || [],
          media: note.media || [],
          visibilityConfig: note.visibilityConfig || {}
        },
        isBookmark: false
      });
      wx.showToast({ title: "已整理", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "整理失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  handleDelete() {
    const { user, noteId } = this.data;
    wx.showModal({
      title: "删除笔记",
      content: "删除笔记不会删除原始归档消息，确认删除吗？",
      confirmColor: "#e5484d",
      success: async ({ confirm }) => {
        if (!confirm) return;
        try {
          await api.deleteNote(noteId, user.id);
          wx.showToast({ title: "已删除", icon: "success" });
          setTimeout(() => wx.navigateBack(), 350);
        } catch (error) {
          wx.showToast({ title: error.detail || "删除失败", icon: "none" });
        }
      }
    });
  }
});
