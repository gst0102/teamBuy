const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { getCurrentUser } = require("../../utils/dashboard");

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (num) => `${num}`.padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function scrmReadKey(userId, noteId) {
  return `note_scrm_read_${userId || "guest"}_${noteId || ""}`;
}

function hasUnreadCustomerAction(summary, userId, noteId) {
  if (!summary || !summary.latestActionAt) return false;
  const latest = new Date(summary.latestActionAt).getTime();
  const readAt = Number(wx.getStorageSync(scrmReadKey(userId, noteId)) || 0);
  return latest > readAt;
}

const NOISY_LABELS = new Set(["未整理", "待整理", "待跟进", "已整理", "房源候选", "团购候选"]);

function isUsefulLabel(label) {
  const value = String(label || "").trim();
  return Boolean(value && !NOISY_LABELS.has(value) && value.length <= 8);
}

function decorateNote(note) {
  const config = note.visibilityConfig || {};
  const tags = Array.isArray(config.tags) ? config.tags.filter(isUsefulLabel) : [];
  const suggestions = Array.isArray(config.typeSuggestions) ? config.typeSuggestions : [];
  const cardType = config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note");
  const structuredData = config.structuredData || {};
  return {
    ...note,
    cardType,
    structuredData,
    isBookmark: cardType === "link" && config.contentMode === "bookmark",
    isProperty: cardType === "property_listing",
    isGroupbuy: cardType === "groupbuy_product",
    sourceUrl: config.sourceUrl || "",
    sourceName: config.sourceName || "链接来源",
    sourceLabel: config.sourceLabel || "网页链接",
    sourceType: config.sourceType || "note",
    systemCategory: config.systemCategory || config.category || "待整理",
    bookmarkCategory: config.systemCategory || config.category || "文章收藏",
    bookmarkTags: tags,
    topicNames: Array.isArray(config.topics) ? config.topics.map((topic) => topic.name).filter(isUsefulLabel) : [],
    primaryValue: buildPrimaryValue(cardType, structuredData, note),
    secondaryValue: buildSecondaryValue(cardType, structuredData, note),
    cardBadge: buildCardBadge(cardType, config),
    propertyStatus: buildPropertyStatus(structuredData.propertyStatus),
    cardAction: buildCardAction(cardType),
    suggestionText: buildSuggestionText(suggestions),
    collectedAtText: formatDateTime(note.createdAt),
    uploadDateText: formatDate(note.createdAt),
    scrmSummary: null,
    scrmHasUnread: false
  };
}

function buildPropertyStatus(value) {
  if (value === "rented") return { text: "已租", className: "rented" };
  if (value === "paused") return { text: "暂停推广", className: "paused" };
  return { text: "推广中", className: "active" };
}

function buildPrimaryValue(cardType, data, note) {
  if (cardType === "property_listing") {
    return [data.price, data.layout].filter(Boolean).join(" · ") || note.summary || "房源信息";
  }
  if (cardType === "groupbuy_product") {
    return [data.price, data.spec].filter(Boolean).join(" · ") || note.summary || "团购商品";
  }
  if (data.miniapp) {
    return [data.miniapp.displayName || data.miniapp.description, data.miniapp.houseCode ? `房源编码 ${data.miniapp.houseCode}` : ""].filter(Boolean).join(" · ") || note.summary || "";
  }
  return note.summary || note.body || "";
}

function buildSecondaryValue(cardType, data, note) {
  if (cardType === "property_listing") {
    return [data.businessArea, data.address, data.utilities].filter(Boolean).join(" · ") || data.remark || "";
  }
  if (cardType === "groupbuy_product") {
    return [data.pickupMethod, data.pickupLocation, data.deadline].filter(Boolean).join(" · ") || data.remark || "";
  }
  if (data.miniapp) {
    return data.miniapp.title || note.body || "";
  }
  return note.body || "";
}

function buildCardBadge(cardType, config) {
  if (config.sourceType === "miniapp") return "小程序";
  const labels = {
    property_listing: "房源",
    groupbuy_product: "团购",
    image_ocr: "图片",
    article: "文章",
    link: "链接",
    text_note: "笔记"
  };
  return labels[cardType] || "资料";
}

function buildSuggestionText(suggestions) {
  const labels = {
    property_listing: "房源",
    groupbuy_product: "团购"
  };
  const names = suggestions.map((item) => labels[item.cardType]).filter(Boolean);
  if (!names.length) return "";
  return `可能是：${names.join(" / ")}`;
}

function buildCardAction(cardType) {
  if (cardType === "property_listing") return "转发给好友";
  if (cardType === "groupbuy_product") return "转发给好友";
  return "整理 / 编辑";
}

const SOURCE_FILTERS = [
  { label: "全部", value: "" },
  { label: "笔记", value: "note" },
  { label: "链接", value: "link" },
  { label: "图片资料", value: "ocr" },
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
    activeSystemCategory: "",
    sort: "collected",
    showAllCategories: false,
    showAllTags: false,
    categoryQuickFilters: [
      { label: "最近使用", value: "" },
      { label: "笔记", value: "note" }
    ],
    tagQuickFilters: [
      { name: "最近使用", value: "" },
      { name: "房产", value: "房产" },
      { name: "户外", value: "户外" },
      { name: "团购", value: "团购" }
    ],
    tagFilters: [],
    topics: [],
    loading: false,
    ocrUploading: false
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
    const { user, keyword, activeSourceType, activeTag, activeTopicId, activeSystemCategory, sort } = this.data;
    if (!user) return;
    this.setData({ loading: true });
    try {
      const res = await api.fetchNotes({
        ownerUserId: user.id,
        keyword: keyword.trim(),
        sourceType: activeSourceType,
        systemCategory: activeSystemCategory,
        tag: activeTag,
        topicId: activeTopicId,
        sort
      });
      const notes = (res.data || []).map(decorateNote);
      this.setData({ notes, tagFilters: this.buildTagFilters(notes) });
      this.loadScrmSummaries(notes);
    } catch (error) {
      wx.showToast({ title: error.detail || "笔记加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleSearch() {
    this.loadNotes();
  },
  handleOcrUpload() {
    const { user, ocrUploading } = this.data;
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if (ocrUploading) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      success: ({ tempFiles = [] }) => {
        const file = tempFiles[0];
        if (!file || !file.tempFilePath) return;
        this.uploadImageNote(file.tempFilePath);
      }
    });
  },
  async uploadImageNote(filePath) {
    const { user } = this.data;
    if (!user || !filePath) return;
    this.setData({ ocrUploading: true });
    wx.showLoading({ title: "保存中" });
    try {
      const result = await api.uploadImageNote({ filePath, ownerUserId: user.id });
      wx.hideLoading();
      const note = result.note || {};
      wx.showToast({ title: "图片已保存", icon: "success" });
      if (note.id) {
        wx.navigateTo({ url: `/pages/note-edit/index?id=${note.id}` });
      } else {
        this.loadNotes();
      }
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || error.errMsg || "识别失败", icon: "none" });
    } finally {
      this.setData({ ocrUploading: false });
    }
  },
  toggleCategories() {
    this.setData({ showAllCategories: !this.data.showAllCategories });
  },
  toggleTags() {
    this.setData({ showAllTags: !this.data.showAllTags });
  },
  async loadTopics() {
    const { user } = this.data;
    if (!user) return;
    try {
      const res = await api.fetchTopics(user.id);
      const topics = (res.data || []).filter((topic) => isUsefulLabel(topic.name));
      this.setData({ topics });
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
  handleAddCategory() {
    wx.showModal({
      title: "添加分类",
      content: "自定义分类会在下一步接入；当前可先在编辑页修改系统弱分类。",
      showCancel: false
    });
  },
  handleTagFilter(event) {
    const tag = event.currentTarget.dataset.tag || event.currentTarget.dataset.value || "";
    this.setData({ activeTag: this.data.activeTag === tag ? "" : tag });
    this.loadNotes();
  },
  handleAddTag() {
    wx.showModal({
      title: "添加标签",
      content: "打开某条笔记后，可在标签与专题里新增标签。",
      showCancel: false
    });
  },
  handleTopicFilter(event) {
    const topicId = event.currentTarget.dataset.id || "";
    this.setData({ activeTopicId: this.data.activeTopicId === topicId ? "" : topicId });
    this.loadNotes();
  },
  handleUnorganizedFilter() {
    const active = this.data.activeSystemCategory === "待整理" ? "" : "待整理";
    this.setData({ activeSystemCategory: active });
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
  async loadScrmSummaries(notes) {
    const { user } = this.data;
    if (!user) return;
    const candidates = (notes || []).filter((item) => item.isProperty || item.isGroupbuy);
    if (!candidates.length) return;
    const summaries = await Promise.all(candidates.map(async (note) => {
      try {
        const res = await api.fetchNoteCustomerActions(note.id, user.id);
        const summary = (res.data && res.data.summary) || {};
        return {
          id: note.id,
          summary,
          hasUnread: hasUnreadCustomerAction(summary, user.id, note.id),
          label: note.isGroupbuy
            ? summary.orderIntent ? `下单 ${summary.orderIntent}` : "下单名单"
            : summary.pending ? `待跟进 ${summary.pending}` : summary.leads ? `客户 ${summary.leads}` : "客户信息"
        };
      } catch (error) {
        return { id: note.id, summary: null, hasUnread: false };
      }
    }));
    const summaryMap = summaries.reduce((map, item) => {
      map[item.id] = item;
      return map;
    }, {});
    this.setData({
      notes: this.data.notes.map((note) => {
        const scrm = summaryMap[note.id];
        return scrm ? { ...note, scrmSummary: scrm.summary, scrmHasUnread: scrm.hasUnread, scrmLabel: scrm.label } : note;
      })
    });
  },
  handleOpenScrm(event) {
    const noteId = event.currentTarget.dataset.id;
    const { user } = this.data;
    if (!noteId) return;
    wx.setStorageSync(scrmReadKey(user && user.id, noteId), Date.now());
    this.setData({
      notes: this.data.notes.map((note) => note.id === noteId ? { ...note, scrmHasUnread: false } : note)
    });
    wx.navigateTo({ url: `/pages/note-actions/index?id=${noteId}` });
  },
  handleOpenMessages() {
    messagePlugin.openMessageCenter();
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
  },
  onShareAppMessage(event) {
    const noteId = event && event.target && event.target.dataset && event.target.dataset.id;
    const note = (this.data.notes || []).find((item) => item.id === noteId) || {};
    return {
      title: note.structuredData && (note.structuredData.community || note.structuredData.productName) || note.title || "资料详情",
      path: `/pages/note-preview/index?id=${noteId || ""}`,
      imageUrl: note.coverUrl || ""
    };
  }
});
