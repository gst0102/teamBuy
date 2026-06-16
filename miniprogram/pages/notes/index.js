const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    user: null,
    keyword: "",
    notes: [],
    loading: false
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    this.loadNotes();
  },
  handleKeywordChange(event) {
    this.setData({ keyword: event.detail.value });
  },
  async loadNotes() {
    const { user, keyword } = this.data;
    if (!user) return;
    this.setData({ loading: true });
    try {
      const res = await api.fetchNotes({ ownerUserId: user.id, keyword: keyword.trim() });
      this.setData({ notes: res.data || [] });
    } catch (error) {
      wx.showToast({ title: error.detail || "笔记加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleSearch() {
    this.loadNotes();
  },
  handleOpen(event) {
    wx.navigateTo({ url: `/pages/note-edit/index?id=${event.currentTarget.dataset.id}` });
  },
  handleDelete(event) {
    const noteId = event.currentTarget.dataset.id;
    const { user } = this.data;
    if (!noteId || !user) return;
    wx.showModal({
      title: "删除笔记",
      content: "删除后不会删除企业微信原始消息，可在后续归档中追溯。确认删除吗？",
      confirmColor: "#e5484d",
      success: async ({ confirm }) => {
        if (!confirm) return;
        try {
          await api.deleteNote(noteId, user.id);
          wx.showToast({ title: "已删除", icon: "success" });
          this.loadNotes();
        } catch (error) {
          wx.showToast({ title: error.detail || "删除失败", icon: "none" });
        }
      }
    });
  }
});
