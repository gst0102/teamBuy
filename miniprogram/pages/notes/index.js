const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { getCurrentUser } = require("../../utils/dashboard");
const { decorateNoteForList, isUsefulLabel } = require("../../utils/note-display");
const { buildBusinessCardShareTitle, buildServiceOfferShareTitle, generatePropertyShareImage, generateBusinessCardShareImage, generateServiceOfferShareImage, generateTitleShareImage } = require("../../utils/business-card-share");

const SALES_CARD_SHARE_CANVAS_ID = "salesCardListShareCanvas";

function scrmReadKey(userId, noteId) {
  return `note_scrm_read_${userId || "guest"}_${noteId || ""}`;
}

function hasUnreadCustomerAction(summary, userId, noteId) {
  if (!summary || !summary.latestActionAt) return false;
  const latest = new Date(summary.latestActionAt).getTime();
  const readAt = Number(wx.getStorageSync(scrmReadKey(userId, noteId)) || 0);
  return latest > readAt;
}

const SOURCE_FILTERS = [
  { label: "全部", value: "", key: "all" },
  { label: "笔记", value: "note", key: "source:note" },
  { label: "链接", value: "link", key: "source:link" },
  { label: "图片资料", value: "ocr", key: "source:ocr" },
  { label: "图片与视频", value: "media", key: "source:media" },
  { label: "语音", value: "voice", key: "source:voice" },
  { label: "位置", value: "location", key: "source:location" },
  { label: "聊天记录", value: "chat", key: "source:chat" },
  { label: "文件", value: "file", key: "source:file" },
  { label: "小程序", value: "miniapp", key: "source:miniapp" }
];

function isPlainNoteItem(note) {
  return note && note.cardType === "text_note" && !note.suggestionText && !note.migrationConfirmType;
}

function withInitialShareState(note) {
  if (!note || !note.id) return note;
  return {
    ...note,
    shareDisabled: true,
    shareImageReady: false,
    shareStatusText: "封面准备中"
  };
}

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
    activePlainNoteOnly: false,
    activeCategoryKey: "all",
    activeMigrationPending: false,
    sort: "collected",
    viewMode: "list",
    showAllCategories: false,
    showAllTags: false,
    categoryQuickFilters: [
      { label: "全部", value: "", mode: "all", key: "all" },
      { label: "普通笔记", value: "plain_note", mode: "plain", key: "plain_note" },
      { label: "房源", value: "房源", mode: "system", key: "system:房源" },
      { label: "商品团购", value: "团购", mode: "system", key: "system:团购" },
      { label: "电子名片", value: "名片", mode: "system", key: "system:名片" },
      { label: "服务方案", value: "服务", mode: "system", key: "system:服务" }
    ],
    tagQuickFilters: [
      { name: "最近使用", value: "" },
      { name: "房产", value: "房产" },
      { name: "户外", value: "户外" },
      { name: "团购", value: "团购" }
    ],
    tagFilters: [],
    topics: [],
    migrationSummary: null,
    noteShareImages: {},
    loading: false
  },
  onLoad(options) {
    const sourceType = options.sourceType || "";
    const migrationPending = options.migrationPending === "1";
    const plainOnly = options.plain === "1";
    const systemCategory = options.systemCategory || "";
    this.setData({
      activeTopicId: options.topicId || "",
      activeSourceType: sourceType,
      activeMigrationPending: migrationPending,
      activePlainNoteOnly: plainOnly,
      activeSystemCategory: systemCategory,
      activeCategoryKey: plainOnly ? "plain_note" : sourceType ? `source:${sourceType}` : systemCategory ? `system:${systemCategory}` : "all"
    });
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
    this.setData({ keyword: event.detail.value, activeMigrationPending: false });
  },
  async loadNotes() {
    const { user, keyword, activeSourceType, activeTag, activeTopicId, activeSystemCategory, activePlainNoteOnly, sort } = this.data;
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
      const allNotes = (res.data || []).map(decorateNoteForList);
      let notes = activePlainNoteOnly ? allNotes.filter(isPlainNoteItem) : allNotes;
      notes = this.data.activeMigrationPending ? notes.filter((note) => note.migrationNeedsAction) : notes;
      notes = notes.map(withInitialShareState);
      this.setData({ notes, tagFilters: this.buildTagFilters(notes), migrationSummary: this.buildMigrationSummary(allNotes) });
      this.loadScrmSummaries(notes);
      this.prepareNoteShareImages(notes);
    } catch (error) {
      wx.showToast({ title: error.detail || "笔记加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  async prepareNoteShareImages(notes) {
    const shareableNotes = (notes || []).filter((note) => note && note.id);
    if (!shareableNotes.length) {
      this.setData({ noteShareImages: {} });
      return;
    }
    const nextImages = {};
    for (const note of shareableNotes) {
      if (!note.id) continue;
      try {
        let imagePath = "";
        if (note.isServiceOffer && note.serviceOfferPreview) {
          imagePath = await generateServiceOfferShareImage(this, SALES_CARD_SHARE_CANVAS_ID, {
            ...note.serviceOfferPreview,
            structuredData: note.structuredData || {},
            title: note.title,
            summary: note.summary,
            coverUrl: note.serviceOfferPreview.coverUrl || note.coverUrl
          });
        } else if (note.isBusinessCard && note.businessCardPreview) {
          imagePath = await generateBusinessCardShareImage(this, SALES_CARD_SHARE_CANVAS_ID, {
            ...note.businessCardPreview,
            structuredData: note.structuredData || {},
            title: note.title,
            summary: note.summary,
            coverUrl: note.coverUrl
          });
        } else if (note.isProperty) {
          const data = note.structuredData || {};
          imagePath = await generatePropertyShareImage(this, SALES_CARD_SHARE_CANVAS_ID, {
            title: note.title || data.community || "房源资料",
            price: data.price || note.primaryValue || "",
            layout: data.layout || "",
            area: data.area || "",
            address: data.address || data.businessArea || note.secondaryValue || "",
            coverUrl: note.coverDisplayUrl || note.coverUrl || ""
          });
        } else {
          imagePath = await generateTitleShareImage(this, SALES_CARD_SHARE_CANVAS_ID, {
            title: note.title || "资料详情",
            summary: note.summary || note.gridSummary || note.secondaryValue || "",
            badge: note.cardBadge || note.systemCategory || (note.isGroupbuy ? "商品" : "资料"),
            hint: note.isGroupbuy ? "打开小程序查看商品详情" : "打开小程序查看完整资料",
            growthHint: "我也想做同款"
          });
        }
        if (imagePath) {
          nextImages[note.id] = imagePath;
          this.setData({ noteShareImages: { ...nextImages } });
        }
        this.updateShareState(note.id, Boolean(imagePath));
      } catch (error) {
        nextImages[note.id] = "";
        this.updateShareState(note.id, false);
      }
    }
  },
  updateShareState(noteId, ready) {
    this.setData({
      notes: (this.data.notes || []).map((note) => (
        note.id === noteId
          ? {
              ...note,
              shareImageReady: ready,
              shareDisabled: false,
              shareStatusText: note.cardAction
            }
          : note
      ))
    });
  },
  handleSearch() {
    this.loadNotes();
  },
  toggleCategories() {
    this.setData({ showAllCategories: !this.data.showAllCategories });
  },
  handleCategoryFilter(event) {
    const mode = event.currentTarget.dataset.mode || "all";
    const value = event.currentTarget.dataset.value || "";
    const key = event.currentTarget.dataset.key || "all";
    const next = {
      activeCategoryKey: key,
      activeMigrationPending: false,
      activeTag: ""
    };
    if (mode === "plain") {
      Object.assign(next, { activePlainNoteOnly: true, activeSourceType: "", activeSystemCategory: "" });
    } else if (mode === "system") {
      Object.assign(next, { activePlainNoteOnly: false, activeSourceType: "", activeSystemCategory: value });
    } else if (mode === "source") {
      Object.assign(next, { activePlainNoteOnly: false, activeSourceType: value, activeSystemCategory: "" });
    } else {
      Object.assign(next, { activePlainNoteOnly: false, activeSourceType: "", activeSystemCategory: "" });
    }
    this.setData(next);
    this.loadNotes();
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
  buildMigrationSummary(notes) {
    const items = notes || [];
    const pending = items.filter((note) => note.migrationNeedsAction);
    const imagePending = items.filter((note) => note.cardType === "image_ocr" && note.migrationNeedsAction);
    const suggested = items.filter((note) => note.suggestionText);
    const wecom = items.filter((note) => /企业微信/.test(note.migrationSourceText || ""));
    const manual = items.filter((note) => /手动|图片保存/.test(note.migrationSourceText || ""));
    return {
      total: items.length,
      pendingCount: pending.length,
      imagePendingCount: imagePending.length,
      suggestedCount: suggested.length,
      wecomCount: wecom.length,
      manualCount: manual.length,
      hasPending: pending.length > 0,
      statusText: pending.length ? `${pending.length} 条待处理` : "全部已入库",
      actionText: pending.length ? "只看待处理" : "查看全部",
      firstPendingId: pending[0] ? pending[0].id : "",
      firstPendingText: pending[0] ? (pending[0].migrationActionText || "继续整理") : ""
    };
  },
  handleSourceFilter(event) {
    const value = event.currentTarget.dataset.value || "";
    this.setData({
      activeSourceType: value,
      activeCategoryKey: value ? `source:${value}` : "all",
      activePlainNoteOnly: false,
      activeSystemCategory: "",
      activeTag: "",
      activeMigrationPending: false
    });
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
    this.setData({ activeTag: this.data.activeTag === tag ? "" : tag, activeMigrationPending: false });
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
    this.setData({ activeTopicId: this.data.activeTopicId === topicId ? "" : topicId, activeMigrationPending: false });
    this.loadNotes();
  },
  handleUnorganizedFilter() {
    const active = this.data.activeSystemCategory === "待整理" ? "" : "待整理";
    this.setData({
      activeSystemCategory: active,
      activeCategoryKey: active ? "system:待整理" : "all",
      activePlainNoteOnly: false,
      activeSourceType: "",
      activeMigrationPending: false
    });
    this.loadNotes();
  },
  handleMigrationPendingFilter() {
    if (!this.data.migrationSummary || !this.data.migrationSummary.hasPending) {
      this.setData({ activeMigrationPending: false, activeSystemCategory: "", activeSourceType: "", activePlainNoteOnly: false, activeCategoryKey: "all", activeTag: "" });
      this.loadNotes();
      return;
    }
    const active = !this.data.activeMigrationPending;
    this.setData({ activeMigrationPending: active, activeSystemCategory: "", activeSourceType: "", activePlainNoteOnly: false, activeCategoryKey: "all", activeTag: "" });
    this.loadNotes();
  },
  handleOpenFirstPending() {
    const summary = this.data.migrationSummary || {};
    if (!summary.firstPendingId) return;
    wx.navigateTo({ url: `/pages/note-edit/index?id=${summary.firstPendingId}` });
  },
  handleSortToggle() {
    this.setData({ sort: this.data.sort === "collected" ? "updated" : "collected" });
    this.loadNotes();
  },
  handleViewModeChange(event) {
    this.setData({ viewMode: event.currentTarget.dataset.mode || "list" });
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
  handleConfirmType(event) {
    const noteId = event.currentTarget.dataset.id;
    const cardType = event.currentTarget.dataset.type;
    const { user } = this.data;
    if (!noteId || !cardType || !user) return;
    const title = cardType === "property_listing" ? "整理成房源" : "整理成商品";
    wx.showModal({
      title,
      content: "确认后系统会按这个类型重新整理字段，原文和图片会保留。",
      confirmText: "确认整理",
      confirmColor: "#11924d",
      success: async ({ confirm }) => {
        if (!confirm) return;
        wx.showLoading({ title: "整理中" });
        try {
          const res = await api.confirmNoteType(noteId, {
            ownerUserId: user.id,
            cardType
          });
          wx.hideLoading();
          wx.showToast({ title: "已整理", icon: "success" });
          const note = res.data || {};
          if (note.id) {
            wx.navigateTo({ url: `/pages/note-edit/index?id=${note.id}` });
          } else {
            this.loadNotes();
          }
        } catch (error) {
          wx.hideLoading();
          wx.showToast({ title: error.detail || error.errMsg || "整理失败", icon: "none" });
        }
      }
    });
  },
  async loadScrmSummaries(notes) {
    const { user } = this.data;
    if (!user) return;
    const candidates = (notes || []).filter((item) => item.isProperty || item.isGroupbuy || item.isServiceCard);
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
      content: "删除后不会删除企业微信原始消息，可在归档中追溯。确认删除吗？",
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
    const shareImage = this.data.noteShareImages && this.data.noteShareImages[noteId];
    return {
      title: note.isBusinessCard && note.businessCardPreview
        ? buildBusinessCardShareTitle(note.businessCardPreview)
        : note.isServiceOffer && note.serviceOfferPreview
          ? buildServiceOfferShareTitle(note.serviceOfferPreview)
          : note.structuredData && (note.structuredData.community || note.structuredData.productName) || note.title || "资料详情",
      path: `/pages/note-preview/index?id=${noteId || ""}`,
      imageUrl: shareImage || ""
    };
  }
});
