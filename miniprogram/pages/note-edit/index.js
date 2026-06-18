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

const SOURCE_TYPES = [
  { label: "笔记", value: "note" },
  { label: "链接", value: "link" },
  { label: "图片与视频", value: "media" },
  { label: "语音", value: "voice" },
  { label: "位置", value: "location" },
  { label: "聊天记录", value: "chat" },
  { label: "文件", value: "file" },
  { label: "小程序", value: "miniapp" }
];

const SYSTEM_CATEGORIES = ["文章", "图片", "链接", "文件", "生活", "工作", "待整理"];

const CARD_TYPES = {
  link: "链接卡",
  article: "阅读卡",
  text_note: "文本卡",
  property_listing: "房源字段卡",
  groupbuy_product: "团购商品卡",
  image_ocr: "图片 OCR 卡"
};

const PROPERTY_FIELDS = [
  { key: "community", label: "小区 / 标题", placeholder: "例如：碧桂园城市之光1栋1210" },
  { key: "layout", label: "户型", placeholder: "例如：公寓一房" },
  { key: "price", label: "价格 / 租金", placeholder: "例如：1600元/月" },
  { key: "utilities", label: "水电物业", placeholder: "例如：自缴" },
  { key: "businessArea", label: "商圈 / 区域", placeholder: "例如：万家丽、高桥北" },
  { key: "address", label: "地址 / 位置", placeholder: "可选" },
  { key: "serviceFee", label: "服务费", placeholder: "例如：服务费200" },
  { key: "contact", label: "联系方式", placeholder: "可选" }
];

const GROUPBUY_FIELDS = [
  { key: "productName", label: "商品名", placeholder: "例如：丹东草莓" },
  { key: "price", label: "价格", placeholder: "例如：39.9元" },
  { key: "spec", label: "规格", placeholder: "例如：3斤装" },
  { key: "deadline", label: "截止时间", placeholder: "例如：今晚22点" },
  { key: "pickupMethod", label: "自提 / 配送", placeholder: "例如：包邮到家 / 小区自提" },
  { key: "pickupLocation", label: "取货地点", placeholder: "可选" },
  { key: "stockNote", label: "库存 / 数量", placeholder: "可选" },
  { key: "contact", label: "联系方式", placeholder: "可选" }
];

const CONVERSION_OPTIONS = [
  { key: "showContactPhone", label: "展示联系电话", desc: "生成页展示电话或联系按钮", property: true, groupbuy: true },
  { key: "enableLightScrm", label: "轻 SCRM 跟进", desc: "记录浏览、收藏、咨询等转化行为", property: true, groupbuy: true },
  { key: "collectLeads", label: "收集线索", desc: "允许用户提交联系方式和备注", property: true, groupbuy: true },
  { key: "enableAppointment", label: "预约看房", desc: "房源页展示预约看房入口", property: true, groupbuy: false },
  { key: "enablePrivateConsultation", label: "私聊咨询", desc: "房源页展示私聊咨询入口", property: true, groupbuy: false },
  { key: "enableSharePoster", label: "生成海报", desc: "生成页保留分享海报入口", property: true, groupbuy: true },
  { key: "enableGroupRelay", label: "团购接龙", desc: "团购页展示接龙/报名入口", property: false, groupbuy: true },
  { key: "enablePaymentPlaceholder", label: "下单按钮预留", desc: "只展示预留入口，不接真实支付", property: false, groupbuy: true }
];

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
  const userTags = Array.isArray(config.userTags) ? config.userTags : [];
  return {
    sourceUrl: config.sourceUrl || "",
    sourceName: config.sourceName || "链接来源",
    sourceLabel: config.sourceLabel || "网页链接",
    sourceType: config.sourceType || "link",
    systemCategory: config.systemCategory || config.category || "文章",
    category: config.systemCategory || config.category || "文章",
    tags,
    userTags,
    topics: Array.isArray(config.topics) ? config.topics : [],
    cardType: config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note"),
    cardState: config.cardState || "collected",
    collectedAtText: formatDateTime(note.createdAt)
  };
}

function hydrateFields(fields, data) {
  return fields.map((field) => ({
    ...field,
    value: data && data[field.key] ? data[field.key] : ""
  }));
}

function defaultConversionConfig(cardType) {
  if (cardType === "property_listing") {
    return {
      showContactPhone: true,
      enableLightScrm: true,
      collectLeads: true,
      enableAppointment: true,
      enablePrivateConsultation: true,
      enableSharePoster: true,
      enableGroupRelay: false,
      enablePaymentPlaceholder: false
    };
  }
  if (cardType === "groupbuy_product") {
    return {
      showContactPhone: true,
      enableLightScrm: true,
      collectLeads: true,
      enableAppointment: false,
      enablePrivateConsultation: false,
      enableSharePoster: true,
      enableGroupRelay: true,
      enablePaymentPlaceholder: false
    };
  }
  return {};
}

function hydrateConversionOptions(cardType, config) {
  const merged = { ...defaultConversionConfig(cardType), ...(config || {}) };
  return CONVERSION_OPTIONS
    .filter((option) => (cardType === "property_listing" ? option.property : cardType === "groupbuy_product" ? option.groupbuy : false))
    .map((option) => ({
      ...option,
      checked: Boolean(merged[option.key])
    }));
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
    sourceTypes: SOURCE_TYPES,
    systemCategories: SYSTEM_CATEGORIES,
    cardTypeLabel: CARD_TYPES.text_note,
    isProperty: false,
    isGroupbuy: false,
    structuredData: {},
    conversionConfig: {},
    conversionOptions: [],
    propertyFields: hydrateFields(PROPERTY_FIELDS, {}),
    groupbuyFields: hydrateFields(GROUPBUY_FIELDS, {}),
    topics: [],
    tagDraft: "",
    topicDraft: "",
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
    this.loadTopics();
    this.loadNote();
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
  async loadNote() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    try {
      const res = await api.fetchNote(noteId, user.id);
      const note = res.data || {};
      this.applyLoadedNote(note);
    } catch (error) {
      wx.showToast({ title: error.detail || "笔记加载失败", icon: "none" });
    }
  },
  applyLoadedNote(note) {
    const config = note.visibilityConfig || {};
    const cardType = config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note");
    const isBookmark = cardType === "link" && config.contentMode === "bookmark";
    const structuredData = config.structuredData || {};
    const conversionConfig = { ...defaultConversionConfig(cardType), ...(config.conversionConfig || {}) };
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
        visibilityConfig: config
      },
      isBookmark,
      isProperty: cardType === "property_listing",
      isGroupbuy: cardType === "groupbuy_product",
      cardTypeLabel: CARD_TYPES[cardType] || "资料卡",
      structuredData,
      conversionConfig,
      conversionOptions: hydrateConversionOptions(cardType, conversionConfig),
      propertyFields: hydrateFields(PROPERTY_FIELDS, structuredData),
      groupbuyFields: hydrateFields(GROUPBUY_FIELDS, structuredData),
      bookmark: buildBookmark(note)
    });
  },
  handleInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`form.${key}`]: event.detail.value });
  },
  handleBookmarkField(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.currentTarget.dataset.value || event.detail.value;
    const config = { ...(this.data.form.visibilityConfig || {}), [key]: value };
    this.setData({
      "form.visibilityConfig": config,
      [`bookmark.${key}`]: value
    });
  },
  handleStructuredInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.detail.value;
    const structuredData = { ...(this.data.structuredData || {}), [key]: value };
    const config = { ...(this.data.form.visibilityConfig || {}), structuredData, cardState: "editing" };
    this.setData({
      structuredData,
      propertyFields: hydrateFields(PROPERTY_FIELDS, structuredData),
      groupbuyFields: hydrateFields(GROUPBUY_FIELDS, structuredData),
      "form.visibilityConfig": config
    });
  },
  handleConversionToggle(event) {
    const key = event.currentTarget.dataset.key;
    const conversionConfig = { ...(this.data.conversionConfig || {}), [key]: Boolean(event.detail.value) };
    const config = {
      ...(this.data.form.visibilityConfig || {}),
      conversionConfig,
      cardState: "editing"
    };
    this.setData({
      conversionConfig,
      conversionOptions: hydrateConversionOptions(config.cardType, conversionConfig),
      "form.visibilityConfig": config
    });
  },
  handleTagDraft(event) {
    this.setData({ tagDraft: event.detail.value });
  },
  handleAddTag() {
    const tag = this.data.tagDraft.trim();
    if (!tag) return;
    const config = { ...(this.data.form.visibilityConfig || {}) };
    const userTags = Array.from(new Set([...(config.userTags || []), tag]));
    const tags = Array.from(new Set([...(config.tags || []), tag]));
    config.userTags = userTags;
    config.tags = tags;
    config.tagStatus = "user_updated";
    this.setData({
      "form.visibilityConfig": config,
      "bookmark.userTags": userTags,
      "bookmark.tags": tags,
      tagDraft: ""
    });
  },
  handleRemoveTag(event) {
    const tag = event.currentTarget.dataset.tag;
    const config = { ...(this.data.form.visibilityConfig || {}) };
    config.userTags = (config.userTags || []).filter((item) => item !== tag);
    config.tags = (config.tags || []).filter((item) => item !== tag);
    config.tagStatus = "user_updated";
    this.setData({
      "form.visibilityConfig": config,
      "bookmark.userTags": config.userTags,
      "bookmark.tags": config.tags
    });
  },
  handleTopicDraft(event) {
    this.setData({ topicDraft: event.detail.value });
  },
  async handleCreateTopic() {
    const name = this.data.topicDraft.trim();
    const { user } = this.data;
    if (!name || !user) return;
    try {
      const res = await api.createTopic({ ownerUserId: user.id, name });
      this.setData({ topicDraft: "" });
      await this.loadTopics();
      await this.handleAddTopicById(res.data.id);
    } catch (error) {
      wx.showToast({ title: error.detail || "专题创建失败", icon: "none" });
    }
  },
  async handleAddTopic(event) {
    await this.handleAddTopicById(event.currentTarget.dataset.id);
  },
  async handleAddTopicById(topicId) {
    const { user, noteId } = this.data;
    if (!topicId || !user || !noteId) return;
    try {
      const res = await api.addNoteToTopic(noteId, topicId, user.id);
      this.applyLoadedNote(res.data || {});
    } catch (error) {
      wx.showToast({ title: error.detail || "加入专题失败", icon: "none" });
    }
  },
  async handleRemoveTopic(event) {
    const { user, noteId } = this.data;
    const topicId = event.currentTarget.dataset.id;
    if (!topicId || !user || !noteId) return;
    try {
      const res = await api.removeNoteFromTopic(noteId, topicId, user.id);
      this.applyLoadedNote(res.data || {});
    } catch (error) {
      wx.showToast({ title: error.detail || "移出专题失败", icon: "none" });
    }
  },
  async handleSave() {
    this.setData({ saving: true });
    try {
      await this.handleSaveOnly();
      wx.showToast({ title: "已保存", icon: "success" });
      setTimeout(() => wx.navigateBack(), 350);
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "保存失败", icon: "none" });
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
      this.applyLoadedNote(note);
      wx.showToast({ title: "已整理", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "整理失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  async handleGenerate() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    this.setData({ saving: true });
    try {
      await this.handleSaveOnly();
      const res = await api.generateNote(noteId, user.id);
      this.applyLoadedNote(res.data || {});
      wx.showToast({ title: "已生成配置", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "生成失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  async handleSaveOnly() {
    const { user, noteId, form } = this.data;
    if (!form.title.trim()) {
      throw new Error("标题不能为空");
    }
    await api.updateNote(noteId, {
      ownerUserId: user.id,
      ...form,
      title: form.title.trim(),
      body: form.body.trim() || form.title.trim()
    });
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
