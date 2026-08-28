const api = require("../services/api");
const { getCurrentUser } = require("./dashboard");

const CARD_STYLES = [
  { id: "business_blue", label: "商务蓝", tone: "blue" },
  { id: "business_dark", label: "深色质感", tone: "dark" },
  { id: "business_warm", label: "暖色亲和", tone: "warm" },
  { id: "business_fresh", label: "清新自然", tone: "fresh" }
];

const EDITORS = {
  property_listing: {
    title: "房源编辑器", kicker: "客户先看关键条件，再决定是否咨询",
    fields: [
      ["community", "小区 / 标题", "例如：城市之光 1 栋 1210"], ["layout", "户型", "例如：一室一厅"],
      ["price", "租金", "例如：1600 元/月"], ["area", "面积", "例如：38㎡"], ["highlights", "房源亮点", "采光、交通、装修、配套等", true]
    ],
    advancedFields: [["floor", "楼层 / 电梯", "例如：电梯高层"], ["utilities", "水电物业", "例如：民水民电"], ["paymentMethod", "押付方式", "例如：押一付一"], ["moveInTime", "入住时间", "例如：随时入住"], ["businessArea", "公开区域", "商圈或大致区域"], ["address", "公开位置", "客户可见的位置描述"]],
    privateFields: [["upstreamContact", "上游联系人", "只自己可见"], ["upstreamPhone", "上游电话", "只自己可见"], ["commission", "佣金 / 成本", "只自己可见"], ["lockNote", "门锁与带看备注", "只自己可见", true]],
    accent: "property"
  },
  groupbuy_product: {
    title: "商品编辑器", kicker: "先讲清商品价值，再承接下单意向",
    fields: [
      ["productName", "商品标题", "例如：丹东草莓 3 斤装"], ["price", "售价", "例如：59.9"], ["spec", "规格", "例如：3斤 / 盒"], ["highlights", "商品卖点", "产地、口感、保障等", true]
    ],
    advancedFields: [["stockNote", "库存说明", "例如：限量 100 份"], ["pickupMethod", "配送 / 自提", "例如：小区自提"], ["pickupLocation", "取货地点", "可选"], ["deadline", "截止时间", "例如：周五 22:00"]],
    privateFields: [["supplier", "供应商", "只自己可见"], ["cost", "成本", "只自己可见"], ["inventory", "内部库存", "只自己可见"]],
    accent: "product"
  },
  service_offer: {
    title: "商机 / 服务编辑器", kicker: "轻量说明价值、范围与合作方式",
    fields: [
      ["serviceName", "服务标题", "例如：品牌官网定制开发"], ["serviceSummary", "一句话说明", "让客户快速理解价值"], ["serviceContent", "服务内容", "包含什么、解决什么问题", true]
    ],
    advancedFields: [["serviceScope", "服务范围", "适用行业、城市或客户类型", true], ["cooperationTerms", "合作条件", "周期、起步价、合作要求", true], ["serviceProcess", "服务流程", "咨询 - 方案 - 执行 - 复盘", true]],
    privateFields: [["internalCost", "内部成本", "只自己可见"], ["supplier", "合作供应商", "只自己可见"]],
    accent: "service"
  },
  business_card: {
    title: "电子名片编辑器", kicker: "身份来自个人销售资料，名片只保存表达与样式",
    profileFields: [
      ["displayName", "姓名", "例如：王小满"], ["jobTitle", "职位 / 身份", "例如：置业顾问"], ["company", "公司 / 门店", "例如：某某门店"],
      ["city", "城市", "例如：长沙"], ["phone", "电话", "可选"], ["wechat", "微信", "可选"], ["email", "邮箱", "可选"], ["website", "网站", "可选，需 HTTPS"]
    ],
    fields: [["headline", "一句话主张", "例如：专注帮你快速找到合适房源"], ["serviceKeywordsText", "服务关键词", "用逗号分隔"], ["bio", "个人介绍", "擅长领域、经验与服务方式", true]],
    advancedFields: [],
    privateFields: [], accent: "business"
  }
};

function normalizeFields(rows = []) {
  return rows.map(([key, label, placeholder, multiline]) => ({ key, label, placeholder, multiline: Boolean(multiline) }));
}

function hasValue(value) {
  return String(value == null ? "" : value).trim().length > 0;
}

function countFilled(fields, values) {
  return fields.filter((field) => hasValue((values || {})[field.key])).length;
}

function attachmentCount(media, type) {
  return (media || []).filter((item) => item.type === type).length;
}

function buildEditorPreview(cardType, structuredData = {}, form = {}) {
  let title = form.title || "未命名资料";
  let subtitle = "";
  let body = "";
  if (cardType === "property_listing") {
    title = structuredData.community || form.title || "未命名房源";
    subtitle = [structuredData.price, structuredData.layout, structuredData.area].filter(hasValue).join(" · ");
    body = structuredData.highlights || "";
  } else if (cardType === "groupbuy_product") {
    title = structuredData.productName || form.title || "未命名商品";
    subtitle = [structuredData.price, structuredData.spec, structuredData.pickupMethod].filter(hasValue).join(" · ");
    body = structuredData.highlights || "";
  } else if (cardType === "service_offer") {
    title = structuredData.serviceName || form.title || "未命名服务";
    subtitle = structuredData.serviceSummary || "";
    body = structuredData.serviceContent || "";
  }
  if (subtitle === title) subtitle = "";
  if (body === title || body === subtitle) body = "";
  return { title, subtitle, body };
}

function createEditorPage(cardType) {
  const meta = EDITORS[cardType];
  return {
    data: {
      cardType, navTitle: meta.title, kicker: meta.kicker, accent: meta.accent,
      noteId: "", user: null, loading: true, saving: false, uploading: false,
      form: { title: "", summary: "", body: "", coverUrl: "", media: [], categoryIds: [], phone: "", locationText: "", visibilityConfig: {} },
      structuredData: {}, privateData: {}, profile: {}, fields: normalizeFields(meta.fields), advancedFields: normalizeFields(meta.advancedFields), privateFields: normalizeFields(meta.privateFields), profileFields: normalizeFields(meta.profileFields),
      preview: buildEditorPreview(cardType), advancedFilledCount: 0, privateFilledCount: 0, showAdvancedFields: false, showPrivateFields: false, showSupplement: false, attachmentsOpen: false,
      styles: CARD_STYLES, styleId: "business_blue", linkDraft: { title: "", url: "" }, isBusinessCard: cardType === "business_card", hasPrivateFields: Boolean(meta.privateFields.length)
    },
    onLoad(options = {}) { this.setData({ noteId: options.id || "" }); },
    onShow() {
      const user = getCurrentUser();
      if (!user) { wx.reLaunch({ url: "/pages/login/index" }); return; }
      this.setData({ user });
      if (this.data.noteId) this.loadNote();
      else this.createDraft();
    },
    async createDraft() {
      if (this.creatingDraft) return;
      this.creatingDraft = true;
      try {
        const res = await api.createManualNoteDraft({ ownerUserId: this.data.user.id, cardType, inputMode: "blank", rawText: "", title: "" });
        this.setData({ noteId: res.data.id });
        this.applyNote(res.data);
      } catch (error) { wx.showToast({ title: error.detail || "创建失败", icon: "none" }); }
      finally { this.creatingDraft = false; }
    },
    async loadNote() {
      try {
        const res = await api.fetchNote(this.data.noteId, this.data.user.id);
        const incomingType = (((res.data || {}).visibilityConfig || {}).cardType || "text_note");
        if (incomingType !== cardType) {
          const { editorPathForCardType } = require("./resource-navigation");
          wx.redirectTo({ url: editorPathForCardType(incomingType, this.data.noteId) });
          return;
        }
        this.applyNote(res.data || {});
      } catch (error) { wx.showToast({ title: error.detail || "加载失败", icon: "none" }); }
    },
    applyNote(note) {
      const config = note.visibilityConfig || {};
      const structuredData = { ...(config.structuredData || {}) };
      if (Array.isArray(structuredData.serviceKeywords) && !structuredData.serviceKeywordsText) structuredData.serviceKeywordsText = structuredData.serviceKeywords.join("，");
      const profile = { ...((this.data.user && this.data.user.salesProfile) || {}), displayName: (((this.data.user || {}).salesProfile || {}).displayName || (this.data.user || {}).nickname || ""), avatarUrl: (((this.data.user || {}).salesProfile || {}).avatarUrl || (this.data.user || {}).avatarUrl || ""), phone: (((this.data.user || {}).salesProfile || {}).phone || (this.data.user || {}).phone || ""), wechat: (((this.data.user || {}).salesProfile || {}).wechat || (this.data.user || {}).wechat || "") };
      const form = { ...this.data.form, ...note, media: note.media || [], visibilityConfig: config };
      const privateData = { ...(config.privateData || {}) };
      const advancedFilledCount = countFilled(this.data.advancedFields, structuredData);
      const privateFilledCount = countFilled(this.data.privateFields, privateData);
      this.setData({ form, structuredData, privateData, profile, profileInitial: String(profile.displayName || "名").slice(0, 1), styleId: ((config.displayConfig || {}).styleId || "business_blue"), preview: buildEditorPreview(cardType, structuredData, form), advancedFilledCount, privateFilledCount, showAdvancedFields: advancedFilledCount > 0, showPrivateFields: privateFilledCount > 0, showSupplement: hasValue(form.body), attachmentsOpen: form.media.length > 0, loading: false });
    },
    refreshEditorState() {
      this.setData({ preview: buildEditorPreview(cardType, this.data.structuredData, this.data.form), advancedFilledCount: countFilled(this.data.advancedFields, this.data.structuredData), privateFilledCount: countFilled(this.data.privateFields, this.data.privateData) });
    },
    handleBaseInput(event) { this.setData({ [`form.${event.currentTarget.dataset.key}`]: event.detail.value }, () => this.refreshEditorState()); },
    handleStructuredInput(event) { this.setData({ [`structuredData.${event.currentTarget.dataset.key}`]: event.detail.value }, () => this.refreshEditorState()); },
    handlePrivateInput(event) { this.setData({ [`privateData.${event.currentTarget.dataset.key}`]: event.detail.value }, () => this.refreshEditorState()); },
    handleToggleAdvancedFields() { this.setData({ showAdvancedFields: !this.data.showAdvancedFields }); },
    handleTogglePrivateFields() { this.setData({ showPrivateFields: !this.data.showPrivateFields }); },
    handleToggleAttachments() { this.setData({ attachmentsOpen: !this.data.attachmentsOpen }); },
    handleShowSupplement() { this.setData({ showSupplement: true }); },
    handleProfileInput(event) { this.setData({ [`profile.${event.currentTarget.dataset.key}`]: event.detail.value }); },
    handleLinkInput(event) { this.setData({ [`linkDraft.${event.currentTarget.dataset.key}`]: event.detail.value }); },
    handleSelectStyle(event) { this.setData({ styleId: event.currentTarget.dataset.id }); },
    handleChooseAttachment() {
      this.setData({ attachmentsOpen: true });
      wx.showActionSheet({ itemList: ["添加图片", "添加 PDF", "添加外部链接"], success: ({ tapIndex }) => { if (tapIndex === 0) this.chooseImages(); if (tapIndex === 1) this.choosePdf(); if (tapIndex === 2) this.setData({ showLinkForm: true }); } });
    },
    chooseImages() {
      const media = this.data.form.media || [];
      const count = Math.min(9 - attachmentCount(media, "image"), 12 - media.length);
      if (count <= 0) { wx.showToast({ title: "图片或附件数量已达上限", icon: "none" }); return; }
      const success = ({ tempFiles = [] }) => this.uploadFiles(tempFiles.map((item) => item.tempFilePath || item.path).filter(Boolean), "image");
      if (typeof wx.chooseImage === "function") {
        wx.chooseImage({ count, sourceType: ["album", "camera"], success });
        return;
      }
      wx.chooseMedia({ count, mediaType: ["image"], sourceType: ["album", "camera"], success });
    },
    choosePdf() {
      const media = this.data.form.media || [];
      const count = Math.min(5 - attachmentCount(media, "pdf"), 12 - media.length);
      if (count <= 0) { wx.showToast({ title: "PDF或附件数量已达上限", icon: "none" }); return; }
      wx.chooseMessageFile({ count, type: "file", extension: ["pdf"], success: ({ tempFiles = [] }) => this.uploadFiles(tempFiles.map((item) => item.path).filter(Boolean), "pdf") });
    },
    async uploadFiles(paths, type) {
      if (!paths.length || this.data.uploading) return;
      this.setData({ uploading: true });
      try {
        const uploaded = await Promise.all(paths.map((filePath) => api.uploadAsset({ filePath, mediaType: type, ownerUserId: this.data.user.id })));
        const base = this.data.form.media.length;
        const media = [...this.data.form.media, ...uploaded.map((item, index) => ({ ...item, id: item.id || `local_${Date.now()}_${index}`, type: item.type || item.mediaType || type, sortOrder: base + index }))];
        this.setData({ "form.media": media, "form.coverUrl": this.data.form.coverUrl || ((media.find((item) => item.type === "image") || {}).url || "") });
      } catch (error) { wx.showToast({ title: error.detail || "上传失败", icon: "none" }); }
      finally { this.setData({ uploading: false }); }
    },
    addLink() {
      const title = String(this.data.linkDraft.title || "").trim();
      const url = String(this.data.linkDraft.url || "").trim();
      if (!/^https:\/\//i.test(url)) { wx.showToast({ title: "链接必须以 https:// 开头", icon: "none" }); return; }
      if (attachmentCount(this.data.form.media, "link") >= 5 || this.data.form.media.length >= 12) { wx.showToast({ title: "链接或附件数量已达上限", icon: "none" }); return; }
      if (this.data.form.media.some((item) => item.type === "link" && item.url === url)) { wx.showToast({ title: "这个链接已经添加", icon: "none" }); return; }
      const media = [...this.data.form.media, { id: `link_${Date.now()}`, type: "link", title: title || url, url, sortOrder: this.data.form.media.length, source: "manual", status: "ready" }];
      this.setData({ "form.media": media, linkDraft: { title: "", url: "" }, showLinkForm: false });
    },
    removeAttachment(event) { const index = Number(event.currentTarget.dataset.index); this.setData({ "form.media": this.data.form.media.filter((_, itemIndex) => itemIndex !== index).map((item, itemIndex) => ({ ...item, sortOrder: itemIndex })) }); },
    previewAttachment(event) { const item = this.data.form.media[Number(event.currentTarget.dataset.index)]; if (!item) return; if (item.type === "image") { wx.previewImage({ current: item.url, urls: this.data.form.media.filter((row) => row.type === "image").map((row) => row.url) }); return; } if (item.type === "link") { wx.setClipboardData({ data: item.url, success: () => wx.showToast({ title: "链接已复制", icon: "success" }) }); return; } wx.downloadFile({ url: item.url, success: ({ tempFilePath }) => wx.openDocument({ filePath: tempFilePath, fileType: "pdf", showMenu: true }), fail: () => wx.showToast({ title: "PDF 打开失败", icon: "none" }) }); },
    async handleSave() {
      if (this.data.saving) return;
      this.setData({ saving: true });
      try {
        const structuredData = { ...this.data.structuredData };
        if (cardType === "business_card") { structuredData.serviceKeywords = String(structuredData.serviceKeywordsText || "").split(/[，,]/).map((item) => item.trim()).filter(Boolean); delete structuredData.serviceKeywordsText; }
        const config = { ...(this.data.form.visibilityConfig || {}), schemaVersion: 2, cardType, cardState: "editing", structuredData, privateData: this.data.privateData, displayConfig: { ...((this.data.form.visibilityConfig || {}).displayConfig || {}), styleId: this.data.styleId }, conversionConfig: { ...((this.data.form.visibilityConfig || {}).conversionConfig || {}), enableLightScrm: true } };
        let title = this.data.form.title;
        if (cardType === "property_listing") title = structuredData.community || title;
        if (cardType === "groupbuy_product") title = structuredData.productName || title;
        if (cardType === "service_offer") title = structuredData.serviceName || title;
        if (cardType === "business_card") title = `${this.data.profile.displayName || this.data.user.nickname}的电子名片`;
        if (!String(title || "").trim()) throw new Error("请填写标题");
        if (cardType === "business_card") {
          const profileRes = await api.updateUserProfile(this.data.user.id, this.data.profile);
          const user = profileRes.data || { ...this.data.user, salesProfile: this.data.profile };
          getApp().globalData.currentUser = user; wx.setStorageSync("currentUser", user); this.setData({ user });
        }
        await api.updateNote(this.data.noteId, { ownerUserId: this.data.user.id, title: String(title).trim(), summary: this.data.form.summary || structuredData.serviceSummary || "", body: this.data.form.body || structuredData.highlights || structuredData.serviceContent || String(title).trim(), coverUrl: this.data.form.coverUrl || null, media: this.data.form.media, categoryIds: this.data.form.categoryIds || [], phone: null, locationText: this.data.form.locationText || null, visibilityConfig: config });
        wx.showToast({ title: "已保存", icon: "success" });
        return true;
      } catch (error) { wx.showToast({ title: error.detail || error.message || "保存失败", icon: "none" }); return false; }
      finally { this.setData({ saving: false }); }
    },
    async handlePreview() { const saved = await this.handleSave(); if (saved) wx.navigateTo({ url: `/pages/note-preview/index?id=${this.data.noteId}&preview=1` }); }
  };
}

module.exports = { createEditorPage };
