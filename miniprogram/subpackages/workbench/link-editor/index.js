const api = require("../../../services/api");
const { getCurrentUser } = require("../../../utils/dashboard");
const { editorPathForCardType } = require("../../../utils/resource-navigation");

function text(value) {
  return String(value == null ? "" : value).trim();
}

function hostFromUrl(url) {
  return text(url).replace(/^https:\/\//i, "").split("/")[0] || "网页链接";
}

Page({
  data: {
    user: null,
    noteId: "",
    loading: true,
    saving: false,
    uploading: false,
    saveStatus: "",
    form: {
      title: "",
      summary: "",
      body: "",
      coverUrl: "",
      media: [],
      categoryIds: [],
      visibilityConfig: {}
    },
    sourceUrl: "",
    sourceName: "",
    sourceLabel: "网页链接",
    recommendation: "",
    description: "",
    recommendationCount: 0,
    descriptionCount: 0
  },

  onLoad(options = {}) {
    const user = getCurrentUser();
    const noteId = options.id || "";
    if (!user || !noteId) {
      wx.showToast({ title: "链接资料不存在", icon: "none" });
      setTimeout(() => wx.navigateBack(), 500);
      return;
    }
    this.setData({ user, noteId });
    this.loadNote();
  },

  async loadNote() {
    try {
      const res = await api.fetchNote(this.data.noteId, this.data.user.id);
      const note = res.data || {};
      const config = note.visibilityConfig || {};
      const cardType = config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note");
      if (!['link', 'article'].includes(cardType)) {
        wx.redirectTo({ url: editorPathForCardType(cardType, note.id) });
        return;
      }
      if (cardType === "link") {
        wx.redirectTo({ url: `/subpackages/workbench/link-confirm/index?id=${note.id}` });
        return;
      }
      const structured = config.structuredData || {};
      const sourceUrl = config.sourceUrl || structured.url || "";
      const description = text(structured.contentDescription || structured.description || note.summary);
      const recommendation = text(structured.salesRecommendation || structured.recommendation || "");
      this.setData({
        form: { ...this.data.form, ...note, media: note.media || [], visibilityConfig: config },
        sourceUrl,
        sourceName: config.sourceName || hostFromUrl(sourceUrl),
        sourceLabel: config.sourceLabel || "网页链接",
        description,
        recommendation,
        descriptionCount: description.length,
        recommendationCount: recommendation.length,
        saveStatus: "已保存"
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "链接资料加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  markDirty() {
    if (this.data.saveStatus !== "未保存") this.setData({ saveStatus: "未保存" });
  },

  handleInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.detail.value;
    const patch = { [key]: value };
    if (key === "recommendation") patch.recommendationCount = value.length;
    if (key === "description") patch.descriptionCount = value.length;
    this.setData(patch, () => this.markDirty());
  },

  handleTitleInput(event) {
    this.setData({ "form.title": event.detail.value }, () => this.markDirty());
  },

  handleOpenSource() {
    const url = this.data.sourceUrl;
    if (!url) return;
    if (/mp\.weixin\.qq\.com/i.test(url) && typeof wx.openOfficialAccountArticle === "function") {
      wx.openOfficialAccountArticle({ url, fail: () => this.copySourceUrl() });
      return;
    }
    this.copySourceUrl();
  },

  copySourceUrl() {
    wx.setClipboardData({ data: this.data.sourceUrl, success: () => wx.showToast({ title: "原文链接已复制", icon: "success" }) });
  },

  chooseCover() {
    const success = async ({ tempFiles = [] }) => {
      const filePath = ((tempFiles[0] || {}).tempFilePath || (tempFiles[0] || {}).path || "");
      if (!filePath) return;
      this.setData({ uploading: true });
      try {
        const uploaded = await api.uploadAsset({ filePath, mediaType: "image", ownerUserId: this.data.user.id });
        this.setData({ "form.coverUrl": uploaded.url || "" }, () => this.markDirty());
      } catch (error) {
        wx.showToast({ title: error.detail || "封面上传失败", icon: "none" });
      } finally {
        this.setData({ uploading: false });
      }
    };
    if (typeof wx.chooseImage === "function") {
      wx.chooseImage({ count: 1, sourceType: ["album", "camera"], success });
      return;
    }
    wx.chooseMedia({ count: 1, mediaType: ["image"], sourceType: ["album", "camera"], success });
  },

  async handleSave(showToast = true) {
    if (this.data.saving) return false;
    const title = text(this.data.form.title);
    const sourceUrl = text(this.data.sourceUrl);
    if (!title) {
      wx.showToast({ title: "请填写文章标题", icon: "none" });
      return false;
    }
    if (!/^https:\/\//i.test(sourceUrl)) {
      wx.showToast({ title: "原文链接必须以 https:// 开头", icon: "none" });
      return false;
    }
    this.setData({ saving: true });
    try {
      const oldConfig = this.data.form.visibilityConfig || {};
      const structuredData = {
        ...(oldConfig.structuredData || {}),
        url: sourceUrl,
        contentDescription: text(this.data.description),
        salesRecommendation: text(this.data.recommendation)
      };
      const visibilityConfig = {
        ...oldConfig,
        cardType: "article",
        contentMode: "deep_note",
        cardState: "organized",
        sourceUrl,
        sourceName: text(this.data.sourceName) || hostFromUrl(sourceUrl),
        sourceLabel: this.data.sourceLabel || "网页链接",
        structuredData
      };
      await api.updateNote(this.data.noteId, {
        ownerUserId: this.data.user.id,
        title,
        summary: text(this.data.description),
        body: text(this.data.recommendation) || text(this.data.description) || title,
        coverUrl: this.data.form.coverUrl || null,
        media: this.data.form.media || [],
        categoryIds: this.data.form.categoryIds || [],
        phone: null,
        locationText: null,
        visibilityConfig
      });
      this.setData({ saveStatus: "已保存" });
      if (showToast) wx.showToast({ title: "已保存", icon: "success" });
      return true;
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "保存失败", icon: "none" });
      return false;
    } finally {
      this.setData({ saving: false });
    }
  },

  async handlePreview() {
    const saved = await this.handleSave(false);
    if (saved) wx.navigateTo({ url: `/pages/note-preview/index?id=${this.data.noteId}&preview=1` });
  },

  async handlePublish() {
    const saved = await this.handleSave(false);
    if (!saved) return;
    this.setData({ saving: true });
    try {
      await api.publishNote(this.data.noteId, this.data.user.id);
      this.setData({ saveStatus: "可发客户" });
      wx.showToast({ title: "已准备好，可从资料卡发客户", icon: "success" });
      setTimeout(() => wx.switchTab({ url: "/pages/library/index" }), 450);
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "发客户失败，请先完善资料", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },

  handleDelete() {
    wx.showModal({
      title: "删除链接资料",
      content: "删除后无法恢复，确定继续吗？",
      confirmText: "删除",
      confirmColor: "#d9485f",
      success: async ({ confirm }) => {
        if (!confirm) return;
        try {
          await api.deleteNote(this.data.noteId, this.data.user.id);
          wx.showToast({ title: "已删除", icon: "success" });
          setTimeout(() => wx.navigateBack(), 400);
        } catch (error) {
          wx.showToast({ title: error.detail || "删除失败", icon: "none" });
        }
      }
    });
  }
});
