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

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (num) => `${num}`.padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function buildBookmark(note) {
  const config = note.visibilityConfig || {};
  const tags = Array.isArray(config.tags) ? config.tags : [];
  return {
    sourceUrl: config.sourceUrl || "",
    sourceName: config.sourceName || "链接来源",
    sourceLabel: config.sourceLabel || "网页链接",
    category: config.category || "文章收藏",
    tags,
    collectedAtText: formatDateTime(note.createdAt)
  };
}

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
    bookmark: {},
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
      const isBookmark = (note.visibilityConfig || {}).contentMode === "bookmark";
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
        isBookmark,
        bookmark: isBookmark ? buildBookmark(note) : {}
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
        isBookmark: false,
        bookmark: {}
      });
      wx.showToast({ title: "已整理", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "整理失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  handleOpenSource() {
    const { sourceUrl } = this.data.bookmark || {};
    if (!sourceUrl) {
      wx.showToast({ title: "没有原文链接", icon: "none" });
      return;
    }
    if (/mp\.weixin\.qq\.com/i.test(sourceUrl) && typeof wx.openOfficialAccountArticle === "function") {
      wx.openOfficialAccountArticle({
        url: sourceUrl,
        fail: () => this.copySourceUrl(sourceUrl)
      });
      return;
    }
    this.copySourceUrl(sourceUrl);
  },
  copySourceUrl(url) {
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: "链接已复制", icon: "success" }),
      fail: () => wx.showToast({ title: "复制失败", icon: "none" })
    });
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
