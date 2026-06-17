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
    sourceType: config.sourceType || "note",
    systemCategory: config.systemCategory || config.category || "待整理",
    bookmarkCategory: config.systemCategory || config.category || "文章收藏",
    bookmarkTags: tags,
    topicNames: Array.isArray(config.topics) ? config.topics.map((topic) => topic.name).filter(Boolean) : [],
    collectedAtText: formatDateTime(note.createdAt)
  };
}

const SOURCE_FILTERS = [
  { label: "全部", value: "" },
  { label: "笔记", value: "note" },
  { label: "链接", value: "link" },
  { label: "图片与视频", value: "media" },
  { label: "语音", value: "voice" },
  { label: "位置", value: "location" },
  { label: "聊天记录", value: "chat" },
  { label: "文件", value: "file" },
  { label: "小程序", value: "miniapp" }
];

Page({
  data: {
    user: null,
    keyword: "",
    notes: [],
    sourceFilters: SOURCE_FILTERS,
    activeSourceType: "",
    activeTag: "",
    activeTopicId: "",
    sort: "collected",
    tagFilters: [],
    topics: [],
    loading: false
  },
  onLoad(options) {
    this.setData({ activeTopicId: options.topicId || "" });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    this.loadTopics();
    this.loadNotes();
  },
  handleKeywordChange(event) {
    this.setData({ keyword: event.detail.value });
  },
  async loadNotes() {
    const { user, keyword, activeSourceType, activeTag, activeTopicId, sort } = this.data;
    if (!user) return;
    this.setData({ loading: true });
    try {
      const res = await api.fetchNotes({
        ownerUserId: user.id,
        keyword: keyword.trim(),
        sourceType: activeSourceType,
        tag: activeTag,
        topicId: activeTopicId,
        sort
      });
      const notes = (res.data || []).map(decorateNote);
      this.setData({ notes, tagFilters: this.buildTagFilters(notes) });
    } catch (error) {
      wx.showToast({ title: error.detail || "笔记加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleSearch() {
    this.loadNotes();
  },
  async loadTopics() {
    const { user } = this.data;
    if (!user) return;
    try {
      const res = await api.fetchTopics(user.id);
      this.setData({ topics: res.data || [] });
    } catch (error) {
      this.setData({ topics: [] });
    }
  },
  buildTagFilters(notes) {
    const counts = {};
    notes.forEach((note) => {
      (note.bookmarkTags || []).forEach((tag) => {
        counts[tag] = (counts[tag] || 0) + 1;
      });
    });
    return Object.keys(counts).sort().map((name) => ({ name, count: counts[name] }));
  },
  handleSourceFilter(event) {
    this.setData({ activeSourceType: event.currentTarget.dataset.value || "", activeTag: "" });
    this.loadNotes();
  },
  handleTagFilter(event) {
    const tag = event.currentTarget.dataset.tag || "";
    this.setData({ activeTag: this.data.activeTag === tag ? "" : tag });
    this.loadNotes();
  },
  handleTopicFilter(event) {
    const topicId = event.currentTarget.dataset.id || "";
    this.setData({ activeTopicId: this.data.activeTopicId === topicId ? "" : topicId });
    this.loadNotes();
  },
  handleSortToggle() {
    this.setData({ sort: this.data.sort === "collected" ? "updated" : "collected" });
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
