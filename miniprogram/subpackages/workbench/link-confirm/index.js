const api = require("../../../services/api");
const { getCurrentUser } = require("../../../utils/dashboard");
const { navigateToNoteEditor } = require("../../../utils/resource-navigation");

const TYPE_LABELS = {
  property_listing: "房源资料",
  groupbuy_product: "商品 / 团购",
  service_offer: "服务 / 合作",
  business_card: "电子名片",
  link: "文章链接",
  article: "阅读资料",
  image_ocr: "图片资料",
  mixed_content: "图文资料",
  pdf_document: "PDF 资料",
  text_note: "普通资料"
};

const CONFIRM_PAGE_CARD_TYPES = new Set(Object.keys(TYPE_LABELS));

function hostFromUrl(url) {
  return String(url || "").replace(/^https:\/\//i, "").split("/")[0] || "网页链接";
}

function applyNote(page, note) {
  const config = note.visibilityConfig || {};
  const structured = config.structuredData || {};
  const media = Array.isArray(note.media) ? note.media : [];
  const cardType = config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note");
  const imageCount = media.filter((item) => item.type === "image").length;
  const pdfCount = media.filter((item) => item.type === "pdf").length;
  const linkCount = media.filter((item) => item.type === "link").length;
  const bodyText = String(note.body || "").trim();
  const isBlankImageDraft = imageCount && (!bodyText || bodyText === "手动创建，可继续补充内容。" || note.title === "图片资料");
  const materialType = cardType === "text_note" && imageCount
    ? (isBlankImageDraft ? "image_ocr" : "mixed_content")
    : cardType === "text_note" && pdfCount
      ? "pdf_document"
      : cardType;
  const unsupportedType = !CONFIRM_PAGE_CARD_TYPES.has(materialType);
  const sourceUrl = config.sourceUrl || structured.url || "";
  const isLink = materialType === "link";
  const parsed = isLink ? structured.parseStatus === "meta_done" : true;
  const typeLabel = TYPE_LABELS[materialType] || "待适配资料";
  const extracted = [];
  if (imageCount) extracted.push(`图片 ${imageCount} 张`);
  if (pdfCount) extracted.push(`PDF ${pdfCount} 份`);
  if (linkCount) extracted.push(`链接 ${linkCount} 条`);
  if (!extracted.length && note.body) extracted.push(`文字 ${String(note.body).length} 字`);
  page.setData({
    note,
    cardType: materialType,
    typeLabel,
    isLink,
    unsupportedType,
    primaryActionText: unsupportedType ? "当前版本暂不支持编辑" : "生成资料",
    title: note.title || structured.title || hostFromUrl(sourceUrl),
    summary: ["手动创建的普通笔记", "手动创建，可继续补充内容。"].includes(note.summary)
      ? (isBlankImageDraft ? `已添加 ${imageCount} 张图片，生成后可继续补充说明。` : "已接收内容，可继续确认和完善。")
      : note.summary || structured.description || "暂未读取到网页摘要，可继续生成资料后补充。",
    coverUrl: note.coverUrl || structured.coverUrl || "",
    sourceUrl,
    sourceName: config.sourceName || hostFromUrl(sourceUrl),
    sourceLabel: config.sourceLabel || (isLink ? "网页链接" : "手动添加"),
    parsed,
    parseText: isLink
      ? (parsed ? "已读取网页标题、摘要和封面" : "网页限制读取，链接已安全保留")
      : "已识别资料类型和当前内容，可进入对应编辑器继续完善",
    tags: Array.isArray(config.tags) ? config.tags.filter((item) => item && item !== "待整理") : [],
    extracted,
    imageCount,
    pdfCount,
    linkCount
  });
}

Page({
  data: {
    user: null,
    noteId: "",
    note: null,
    loading: true,
    saving: false,
    title: "",
    summary: "",
    coverUrl: "",
    sourceUrl: "",
    sourceName: "",
    sourceLabel: "网页链接",
    typeLabel: "资料",
    cardType: "text_note",
    isLink: false,
    unsupportedType: false,
    primaryActionText: "生成资料",
    parsed: false,
    parseText: "",
    tags: [],
    extracted: []
  },
  onLoad(options) {
    const user = getCurrentUser();
    const noteId = options.id || "";
    if (!user || !noteId) {
      wx.showToast({ title: "资料不存在", icon: "none" });
      setTimeout(() => wx.navigateBack(), 500);
      return;
    }
    this.setData({ user, noteId });
    this.loadNote();
  },
  async loadNote() {
    try {
      const res = await api.fetchNote(this.data.noteId, this.data.user.id);
      applyNote(this, res.data || {});
    } catch (error) {
      wx.showToast({ title: error.detail || "资料加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleOpenSource() {
    const url = this.data.sourceUrl;
    if (!url) return;
    if (/mp\.weixin\.qq\.com/i.test(url) && typeof wx.openOfficialAccountArticle === "function") {
      wx.openOfficialAccountArticle({ url, fail: () => this.copyUrl() });
      return;
    }
    this.copyUrl();
  },
  copyUrl() {
    wx.setClipboardData({ data: this.data.sourceUrl, success: () => wx.showToast({ title: "链接已复制", icon: "success" }) });
  },
  handleSaveOriginal() {
    wx.showToast({ title: "原链接已保存", icon: "success" });
    setTimeout(() => wx.switchTab({ url: "/pages/library/index" }), 400);
  },
  async handleGenerate() {
    if (this.data.saving) return;
    if (this.data.unsupportedType) {
      wx.showToast({ title: "资料已保留，请更新版本后再编辑", icon: "none" });
      return;
    }
    this.setData({ saving: true });
    try {
      if (this.data.isLink) {
        const res = await api.organizeNote(this.data.noteId, this.data.user.id);
        const note = res.data || {};
        wx.redirectTo({ url: `/subpackages/workbench/link-editor/index?id=${note.id || this.data.noteId}` });
        return;
      }
      navigateToNoteEditor(this.data.note);
    } catch (error) {
      wx.showToast({ title: error.detail || "生成失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  }
});
