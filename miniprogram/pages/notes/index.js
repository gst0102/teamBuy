const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (num) => `${num}`.padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function decorateNote(note) {
  const config = note.visibilityConfig || {};
  const tags = Array.isArray(config.tags) ? config.tags : [];
  return {
    ...note,
    isBookmark: config.contentMode === "bookmark",
    sourceUrl: config.sourceUrl || "",
    sourceName: config.sourceName || "链接来源",
    sourceLabel: config.sourceLabel || "网页链接",
    bookmarkCategory: config.category || "文章收藏",
    bookmarkTags: tags,
    collectedAtText: formatDateTime(note.createdAt)
  };
}

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
      this.setData({ notes: (res.data || []).map(decorateNote) });
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
    const { id, bookmark, url, title } = event.currentTarget.dataset;
    if (bookmark && url) {
      this.openSourceUrl(url, title);
      return;
    }
    wx.navigateTo({ url: `/pages/note-edit/index?id=${id}` });
  },
  handleEdit(event) {
    wx.navigateTo({ url: `/pages/note-edit/index?id=${event.currentTarget.dataset.id}` });
  },
  openSourceUrl(url, title = "原文链接") {
    if (!url) return;
    if (/mp\.weixin\.qq\.com/i.test(url) && typeof wx.openOfficialAccountArticle === "function") {
      wx.openOfficialAccountArticle({
        url,
        fail: () => this.copySourceUrl(url, title)
      });
      return;
    }
    this.copySourceUrl(url, title);
  },
  copySourceUrl(url, title) {
    wx.setClipboardData({
      data: url,
      success: () => {
        wx.showToast({ title: "链接已复制", icon: "success" });
      },
      fail: () => {
        wx.showToast({ title: `${title}打开失败`, icon: "none" });
      }
    });
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
