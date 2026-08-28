const api = require("../../../services/api");
const { getCurrentUser } = require("../../../utils/dashboard");
const { editorPathForCardType } = require("../../../utils/resource-navigation");

const FULFILLMENT_OPTIONS = [
  { key: "shipping", label: "快递" },
  { key: "local_delivery", label: "同城配送" },
  { key: "store_pickup", label: "到店自提" },
  { key: "community_pickup", label: "小区自提" },
  { key: "offline_contact", label: "线下联系" }
];

const PRIVATE_FIELDS = [
  { key: "supplier", label: "供应商", placeholder: "供应商名称" },
  { key: "supplierContact", label: "供应商联系方式", placeholder: "电话或微信" },
  { key: "costNote", label: "进货成本", placeholder: "仅自己可见" },
  { key: "profitNote", label: "利润备注", placeholder: "仅自己可见" },
  { key: "internalInventory", label: "内部库存", placeholder: "仅自己可见" },
  { key: "purchaseUrl", label: "采购链接", placeholder: "https://" },
  { key: "privateRemark", label: "内部备注", placeholder: "采购、对账等内部信息", multiline: true }
];

function text(value) {
  return String(value == null ? "" : value).trim();
}

const PRODUCT_PLACEHOLDER_VALUES = new Set([
  "未命名商品",
  "默认规格",
  "商品说明",
  "商品说明待补",
  "商品卖点待补",
  "补充商品信息后即可发给客户",
  "手动创建，可继续补充内容。"
]);

function contentValue(value) {
  const normalized = text(value);
  return PRODUCT_PLACEHOLDER_VALUES.has(normalized) ? "" : normalized;
}

function imageItems(media = []) {
  return media.filter((item) => item && item.type === "image");
}

function otherItems(media = []) {
  return media.filter((item) => item && item.type !== "image");
}

function splitHighlights(value) {
  return text(value).split(/[，,、\n]/).map((item) => item.trim()).filter(Boolean).slice(0, 5);
}

function yuanToFen(value) {
  const normalized = text(value).replace(/[￥¥元]/g, "");
  if (!normalized || !/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  return Math.round(Number(normalized) * 100);
}

function fenToYuan(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "";
  return (amount / 100).toFixed(2).replace(/\.00$/, "").replace(/(\.\d)0$/, "$1");
}

function makeVariant(index = 0) {
  return { id: `variant_${Date.now()}_${index}`, name: "", priceInput: "", priceFen: null, stockStatus: "available", sortOrder: index };
}

function normalizeVariants(data = {}) {
  if (Array.isArray(data.variants) && data.variants.length) {
    return data.variants.map((item, index) => ({
      id: item.id || `variant_${index}`,
      name: contentValue(item.name),
      priceFen: Number.isFinite(Number(item.priceFen)) ? Number(item.priceFen) : null,
      priceInput: fenToYuan(item.priceFen),
      stockStatus: item.stockStatus === "sold_out" ? "sold_out" : "available",
      sortOrder: index
    }));
  }
  const legacySkus = (((data || {}).skuConfig || {}).skus || []);
  if (legacySkus.length) {
    return legacySkus.map((item, index) => ({
      id: item.id || item.key || `variant_${index}`,
      name: contentValue(item.name),
      priceFen: yuanToFen(item.price),
      priceInput: text(item.price).replace(/[￥¥元]/g, ""),
      stockStatus: item.soldOut ? "sold_out" : "available",
      sortOrder: index
    }));
  }
  const variant = makeVariant();
  variant.name = contentValue(data.spec);
  variant.priceInput = text(data.price).replace(/[￥¥元]/g, "");
  variant.priceFen = yuanToFen(variant.priceInput);
  return [variant];
}

function normalizeFulfillment(data = {}) {
  const source = data.fulfillment || {};
  let methods = Array.isArray(source.methods) ? source.methods.filter(Boolean) : [];
  if (!methods.length && (data.pickupMethod || data.pickupLocation)) {
    methods = /配送|快递/.test(text(data.pickupMethod)) ? ["shipping"] : ["community_pickup"];
  }
  return {
    methods,
    shippingFeeNote: text(source.shippingFeeNote),
    deliveryArea: text(source.deliveryArea),
    deliveryFeeNote: text(source.deliveryFeeNote),
    availableTime: text(source.availableTime),
    pickupLocation: {
      name: text((source.pickupLocation || {}).name || data.pickupLocation),
      address: text((source.pickupLocation || {}).address),
      latitude: (source.pickupLocation || {}).latitude == null ? null : Number(source.pickupLocation.latitude),
      longitude: (source.pickupLocation || {}).longitude == null ? null : Number(source.pickupLocation.longitude)
    }
  };
}

function normalizePrivateData(source = {}) {
  return {
    ...source,
    costNote: source.costNote || source.cost || "",
    internalInventory: source.internalInventory || source.inventory || ""
  };
}

Page({
  data: {
    noteId: "", user: null, loading: true, saving: false, uploading: false, saveStatus: "",
    form: { title: "", summary: "", body: "", coverUrl: "", media: [], categoryIds: [], visibilityConfig: {} },
    structuredData: {}, privateData: {}, salesMode: "inquiry", variants: [makeVariant()],
    fulfillment: normalizeFulfillment(), relayConfig: {}, imageMedia: [], supplementalMedia: [],
    highlightsText: "", highlights: [], remarkCount: 0, previewTitle: "填写商品名称",
    previewPrice: "填写售价", previewHeadline: "填写一句话卖点", previewMode: "商品",
    fulfillmentOptions: FULFILLMENT_OPTIONS, privateFields: PRIVATE_FIELDS,
    openSection: "", linkDraft: { title: "", url: "" }, showLinkForm: false
  },

  onLoad(options = {}) { this.setData({ noteId: options.id || "" }); },
  onShow() {
    const user = getCurrentUser();
    if (!user) { wx.reLaunch({ url: "/pages/login/index" }); return; }
    this.setData({ user });
    if (this.data.noteId) this.loadNote(); else this.createDraft();
  },

  async createDraft() {
    if (this.creatingDraft) return;
    this.creatingDraft = true;
    try {
      const res = await api.createManualNoteDraft({ ownerUserId: this.data.user.id, cardType: "groupbuy_product", inputMode: "blank", rawText: "", title: "" });
      this.setData({ noteId: res.data.id });
      this.applyNote(res.data || {});
    } catch (error) { wx.showToast({ title: error.detail || "创建失败", icon: "none" }); }
    finally { this.creatingDraft = false; }
  },

  async loadNote() {
    try {
      const res = await api.fetchNote(this.data.noteId, this.data.user.id);
      const note = res.data || {};
      const incomingType = ((note.visibilityConfig || {}).cardType || "text_note");
      if (incomingType !== "groupbuy_product") {
        wx.redirectTo({ url: editorPathForCardType(incomingType, this.data.noteId) });
        return;
      }
      this.applyNote(note);
    } catch (error) { wx.showToast({ title: error.detail || "加载失败", icon: "none" }); }
  },

  applyNote(note) {
    const config = note.visibilityConfig || {};
    const data = { ...(config.structuredData || {}) };
    data.productName = contentValue(data.productName);
    data.headline = contentValue(data.headline);
    data.remark = contentValue(data.remark);
    const hasLegacyProductContent = Boolean(
      data.deadline || data.stockNote || text(data.rawText) ||
      (text(data.productName) && text(data.productName) !== "未命名商品")
    );
    const legacyRelayEnabled = Boolean(((config.conversionConfig || {}).enableGroupRelay) && hasLegacyProductContent);
    const form = {
      ...this.data.form,
      ...note,
      title: contentValue(note.title),
      summary: contentValue(note.summary),
      body: contentValue(note.body),
      media: note.media || [],
      visibilityConfig: config
    };
    const highlights = Array.isArray(data.highlights) ? data.highlights : splitHighlights(data.highlights);
    this.setData({
      form,
      structuredData: data,
      privateData: normalizePrivateData(config.privateData || {}),
      salesMode: data.salesMode === "relay" || (!data.salesMode && legacyRelayEnabled) ? "relay" : "inquiry",
      variants: normalizeVariants(data),
      fulfillment: normalizeFulfillment(data),
      relayConfig: { ...(data.relayConfig || {}), deadlineAt: (data.relayConfig || {}).deadlineAt || data.deadline || "" },
      highlightsText: highlights.join("，"),
      saveStatus: "已保存",
      loading: false
    }, () => this.refreshView());
  },

  refreshView() {
    const images = imageItems(this.data.form.media);
    const availablePrices = this.data.variants
      .filter((item) => item.stockStatus !== "sold_out" && yuanToFen(item.priceInput) != null)
      .map((item) => yuanToFen(item.priceInput));
    const minFen = availablePrices.length ? Math.min(...availablePrices) : null;
    this.setData({
      imageMedia: images,
      supplementalMedia: otherItems(this.data.form.media),
      highlights: splitHighlights(this.data.highlightsText),
      remarkCount: text(this.data.structuredData.remark).length,
      previewTitle: contentValue(this.data.structuredData.productName) || contentValue(this.data.form.title) || "填写商品名称",
      previewHeadline: contentValue(this.data.structuredData.headline) || "填写一句话卖点",
      previewPrice: minFen == null ? "填写售价" : `¥${fenToYuan(minFen)}${availablePrices.length > 1 ? " 起" : ""}`,
      previewMode: this.data.salesMode === "relay" ? "团购接龙" : "商品",
      fulfillmentOptions: FULFILLMENT_OPTIONS.map((item) => ({ ...item, active: this.data.fulfillment.methods.includes(item.key) })),
      showShipping: this.data.fulfillment.methods.includes("shipping"),
      showDelivery: this.data.fulfillment.methods.includes("local_delivery"),
      showPickup: this.data.fulfillment.methods.includes("store_pickup") || this.data.fulfillment.methods.includes("community_pickup")
    });
  },

  markDirty() { if (this.data.saveStatus !== "未保存") this.setData({ saveStatus: "未保存" }); },
  handleStructuredInput(event) {
    this.setData({ [`structuredData.${event.currentTarget.dataset.key}`]: event.detail.value }, () => { this.markDirty(); this.refreshView(); });
  },
  handleHighlightsInput(event) {
    this.setData({ highlightsText: event.detail.value }, () => { this.markDirty(); this.refreshView(); });
  },
  handlePrivateInput(event) { this.setData({ [`privateData.${event.currentTarget.dataset.key}`]: event.detail.value }, () => this.markDirty()); },
  handleRelayInput(event) { this.setData({ [`relayConfig.${event.currentTarget.dataset.key}`]: event.detail.value }, () => this.markDirty()); },
  handleFulfillmentInput(event) { this.setData({ [`fulfillment.${event.currentTarget.dataset.key}`]: event.detail.value }, () => this.markDirty()); },
  handleToggleSection(event) {
    const section = event.currentTarget.dataset.section;
    this.setData({ openSection: this.data.openSection === section ? "" : section });
  },
  handleModeChange() {
    wx.showActionSheet({ itemList: ["商品", "团购接龙"], success: ({ tapIndex }) => {
      const salesMode = tapIndex === 1 ? "relay" : "inquiry";
      if (salesMode === this.data.salesMode) return;
      this.setData({ salesMode }, () => { this.markDirty(); this.refreshView(); });
    } });
  },
  handleVariantInput(event) {
    const index = Number(event.currentTarget.dataset.index);
    const key = event.currentTarget.dataset.key;
    this.setData({ [`variants[${index}].${key}`]: event.detail.value }, () => { this.markDirty(); this.refreshView(); });
  },
  handleVariantStock(event) {
    const index = Number(event.currentTarget.dataset.index);
    const status = this.data.variants[index].stockStatus === "sold_out" ? "available" : "sold_out";
    this.setData({ [`variants[${index}].stockStatus`]: status }, () => { this.markDirty(); this.refreshView(); });
  },
  handleAddVariant() {
    if (this.data.variants.length >= 12) { wx.showToast({ title: "最多添加 12 个简单规格", icon: "none" }); return; }
    this.setData({ variants: [...this.data.variants, makeVariant(this.data.variants.length)] }, () => { this.markDirty(); this.refreshView(); });
  },
  handleRemoveVariant(event) {
    const index = Number(event.currentTarget.dataset.index);
    if (this.data.variants.length === 1) { wx.showToast({ title: "至少保留一个价格", icon: "none" }); return; }
    this.setData({ variants: this.data.variants.filter((_, itemIndex) => itemIndex !== index) }, () => { this.markDirty(); this.refreshView(); });
  },
  handleToggleFulfillment(event) {
    const key = event.currentTarget.dataset.key;
    const methods = this.data.fulfillment.methods.includes(key)
      ? this.data.fulfillment.methods.filter((item) => item !== key)
      : [...this.data.fulfillment.methods, key];
    this.setData({ "fulfillment.methods": methods }, () => { this.markDirty(); this.refreshView(); });
  },
  choosePickupLocation() {
    wx.chooseLocation({ success: (result) => {
      this.setData({ "fulfillment.pickupLocation": { name: result.name || "自提点", address: result.address || "", latitude: result.latitude, longitude: result.longitude } }, () => this.markDirty());
    }, fail: (error) => {
      if (/cancel/i.test(String(error.errMsg || ""))) return;
      wx.showToast({ title: "选点失败，请检查定位权限", icon: "none" });
    } });
  },

  chooseImages() {
    const count = Math.min(9 - this.data.imageMedia.length, 9);
    if (count <= 0) { wx.showToast({ title: "最多添加 9 张商品图片", icon: "none" }); return; }
    const success = ({ tempFiles = [] }) => this.uploadImages(tempFiles.map((item) => item.tempFilePath || item.path).filter(Boolean));
    if (typeof wx.chooseImage === "function") { wx.chooseImage({ count, sourceType: ["album", "camera"], success }); return; }
    wx.chooseMedia({ count, mediaType: ["image"], sourceType: ["album", "camera"], success });
  },
  async uploadImages(paths) {
    if (!paths.length || this.data.uploading) return;
    this.setData({ uploading: true });
    try {
      const uploaded = await Promise.all(paths.map((filePath) => api.uploadAsset({ filePath, mediaType: "image", ownerUserId: this.data.user.id })));
      const additions = uploaded.map((item, index) => ({ ...item, id: item.id || `image_${Date.now()}_${index}`, type: "image" }));
      const media = [...this.data.imageMedia, ...additions, ...this.data.supplementalMedia].map((item, index) => ({ ...item, sortOrder: index }));
      this.setData({ "form.media": media, "form.coverUrl": (media[0] || {}).url || "" }, () => { this.markDirty(); this.refreshView(); });
    } catch (error) { wx.showToast({ title: error.detail || "图片上传失败", icon: "none" }); }
    finally { this.setData({ uploading: false }); }
  },
  handlePreviewImage(event) {
    const index = Number(event.currentTarget.dataset.index || 0);
    const urls = this.data.imageMedia.map((item) => item.displayUrl || item.url).filter(Boolean);
    if (urls.length) wx.previewImage({ current: urls[index] || urls[0], urls });
  },
  handleSetCover(event) {
    const index = Number(event.currentTarget.dataset.index || 0);
    if (index <= 0) { wx.showToast({ title: "当前已是封面", icon: "none" }); return; }
    const images = [...this.data.imageMedia];
    const [selected] = images.splice(index, 1); images.unshift(selected);
    const media = [...images, ...this.data.supplementalMedia].map((item, itemIndex) => ({ ...item, sortOrder: itemIndex }));
    this.setData({ "form.media": media, "form.coverUrl": selected.url || "" }, () => { this.markDirty(); this.refreshView(); });
  },
  handleRemoveImage(event) {
    const index = Number(event.currentTarget.dataset.index);
    const images = this.data.imageMedia.filter((_, itemIndex) => itemIndex !== index);
    const media = [...images, ...this.data.supplementalMedia].map((item, itemIndex) => ({ ...item, sortOrder: itemIndex }));
    this.setData({ "form.media": media, "form.coverUrl": (images[0] || {}).url || "" }, () => { this.markDirty(); this.refreshView(); });
  },
  handleChooseSupplement() {
    wx.showActionSheet({ itemList: ["添加 PDF", "添加外部链接"], success: ({ tapIndex }) => {
      if (tapIndex === 0) this.choosePdf(); else this.setData({ showLinkForm: true });
    } });
  },
  choosePdf() {
    const count = Math.min(5 - this.data.supplementalMedia.filter((item) => item.type === "pdf").length, 12 - this.data.form.media.length);
    if (count <= 0) { wx.showToast({ title: "PDF 或附件数量已达上限", icon: "none" }); return; }
    wx.chooseMessageFile({ count, type: "file", extension: ["pdf"], success: async ({ tempFiles = [] }) => {
      try {
        this.setData({ uploading: true });
        const uploaded = await Promise.all(tempFiles.map((item) => api.uploadAsset({ filePath: item.path, mediaType: "pdf", ownerUserId: this.data.user.id })));
        const additions = uploaded.map((item, index) => ({ ...item, id: item.id || `pdf_${Date.now()}_${index}`, type: "pdf" }));
        const media = [...this.data.imageMedia, ...this.data.supplementalMedia, ...additions].map((item, index) => ({ ...item, sortOrder: index }));
        this.setData({ "form.media": media }, () => { this.markDirty(); this.refreshView(); });
      } catch (error) { wx.showToast({ title: error.detail || "PDF 上传失败", icon: "none" }); }
      finally { this.setData({ uploading: false }); }
    } });
  },
  handleLinkInput(event) { this.setData({ [`linkDraft.${event.currentTarget.dataset.key}`]: event.detail.value }); },
  addLink() {
    const url = text(this.data.linkDraft.url);
    if (!/^https:\/\//i.test(url)) { wx.showToast({ title: "链接必须以 https:// 开头", icon: "none" }); return; }
    if (this.data.form.media.length >= 12 || this.data.supplementalMedia.filter((item) => item.type === "link").length >= 5) { wx.showToast({ title: "链接或附件数量已达上限", icon: "none" }); return; }
    const link = { id: `link_${Date.now()}`, type: "link", title: text(this.data.linkDraft.title) || url, url, status: "ready" };
    const media = [...this.data.imageMedia, ...this.data.supplementalMedia, link].map((item, index) => ({ ...item, sortOrder: index }));
    this.setData({ "form.media": media, linkDraft: { title: "", url: "" }, showLinkForm: false }, () => { this.markDirty(); this.refreshView(); });
  },
  handleRemoveSupplement(event) {
    const index = Number(event.currentTarget.dataset.index);
    const rest = this.data.supplementalMedia.filter((_, itemIndex) => itemIndex !== index);
    const media = [...this.data.imageMedia, ...rest].map((item, itemIndex) => ({ ...item, sortOrder: itemIndex }));
    this.setData({ "form.media": media }, () => { this.markDirty(); this.refreshView(); });
  },

  async handleSave(showToast = true) {
    if (this.data.saving) return false;
    const productName = text(this.data.structuredData.productName);
    if (!productName) { wx.showToast({ title: "请填写商品名称", icon: "none" }); return false; }
    const variants = this.data.variants.map((item, index) => ({ ...item, name: contentValue(item.name), priceFen: yuanToFen(item.priceInput), sortOrder: index }));
    if (variants.some((item) => item.priceFen == null)) { wx.showToast({ title: "请填写正确的规格价格", icon: "none" }); return false; }
    const purchaseUrl = text(this.data.privateData.purchaseUrl);
    if (purchaseUrl && !/^https:\/\//i.test(purchaseUrl)) { wx.showToast({ title: "采购链接必须以 https:// 开头", icon: "none" }); return false; }
    this.setData({ saving: true });
    try {
      const highlights = splitHighlights(this.data.highlightsText);
      const structuredData = {
        ...this.data.structuredData,
        salesMode: this.data.salesMode,
        productName,
        highlights,
        variants: variants.map(({ priceInput, ...item }) => item),
        fulfillment: this.data.fulfillment,
        relayConfig: this.data.salesMode === "relay" ? {
          ...this.data.relayConfig,
          deadlineAt: text(this.data.relayConfig.deadlineAt) || null,
          limitPerPerson: text(this.data.relayConfig.limitPerPerson) ? Number(this.data.relayConfig.limitPerPerson) : null
        } : {}
      };
      ["price", "spec", "skuConfig", "pickupMethod", "pickupLocation", "deadline", "stockNote"].forEach((key) => delete structuredData[key]);
      const config = {
        ...(this.data.form.visibilityConfig || {}), schemaVersion: 2, cardType: "groupbuy_product", cardState: "editing",
        structuredData, privateData: { ...this.data.privateData, purchaseUrl },
        conversionConfig: {
          ...(((this.data.form.visibilityConfig || {}).conversionConfig) || {}),
          showContactPhone: true,
          enableLightScrm: true,
          collectLeads: true,
          enablePrivateConsultation: true,
          enableGroupRelay: this.data.salesMode === "relay"
        }
      };
      const firstImage = this.data.imageMedia[0];
      const availableVariants = variants.filter((item) => item.stockStatus !== "sold_out");
      const summaryCandidates = availableVariants.length ? availableVariants : variants;
      const summaryPrice = `¥${fenToYuan(Math.min(...summaryCandidates.map((item) => item.priceFen)))}${variants.length > 1 ? " 起" : ""}`;
      await api.updateNote(this.data.noteId, {
        ownerUserId: this.data.user.id, title: productName,
        summary: [summaryPrice, text(structuredData.headline)].filter(Boolean).join(" · "),
        body: text(structuredData.remark) || highlights.join("、") || productName,
        coverUrl: (firstImage && firstImage.url) || null, media: this.data.form.media,
        categoryIds: this.data.form.categoryIds || [], phone: null, locationText: null, visibilityConfig: config
      });
      this.setData({ saveStatus: "已保存", variants });
      if (showToast) wx.showToast({ title: "已保存", icon: "success" });
      return true;
    } catch (error) { wx.showToast({ title: error.detail || error.message || "保存失败", icon: "none" }); return false; }
    finally { this.setData({ saving: false }); }
  },
  async handlePreview() { const saved = await this.handleSave(false); if (saved) wx.navigateTo({ url: `/pages/note-preview/index?id=${this.data.noteId}&preview=1` }); },
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
    } finally { this.setData({ saving: false }); }
  },
  handleDelete() {
    wx.showModal({ title: "删除商品", content: "删除后无法恢复，确定继续吗？", confirmText: "删除", confirmColor: "#d9485f", success: async ({ confirm }) => {
      if (!confirm) return;
      try { await api.deleteNote(this.data.noteId, this.data.user.id); wx.showToast({ title: "已删除", icon: "success" }); setTimeout(() => wx.navigateBack(), 400); }
      catch (error) { wx.showToast({ title: error.detail || "删除失败", icon: "none" }); }
    } });
  }
});
