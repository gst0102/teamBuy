const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    user: null,
    noteId: "",
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
    saving: false
  },
  onLoad(options) {
    this.setData({ noteId: options.id || "" });
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
        }
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
