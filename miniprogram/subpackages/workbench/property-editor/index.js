const api = require("../../../services/api");
const { getCurrentUser } = require("../../../utils/dashboard");
const { editorPathForCardType } = require("../../../utils/resource-navigation");

const MORE_FIELDS = [
  { key: "floor", label: "楼层 / 电梯", placeholder: "例如：电梯高层" },
  { key: "utilities", label: "水电物业", placeholder: "例如：民水民电" },
  { key: "paymentMethod", label: "押付方式", placeholder: "例如：押一付一" },
  { key: "moveInTime", label: "入住时间", placeholder: "例如：随时入住" }
];

const PRIVATE_FIELDS = [
  { key: "upstreamContact", label: "上游联系人", placeholder: "只自己可见" },
  { key: "upstreamPhone", label: "上游电话", placeholder: "只自己可见" },
  { key: "commission", label: "佣金 / 成本", placeholder: "只自己可见" },
  { key: "lockNote", label: "门锁与带看备注", placeholder: "只自己可见", multiline: true }
];

function value(value) {
  return String(value == null ? "" : value).trim();
}

function imageItems(media = []) {
  return media.filter((item) => item && item.type === "image");
}

function otherItems(media = []) {
  return media.filter((item) => item && item.type !== "image");
}

function splitHighlights(text) {
  return value(text).split(/[，,、\n]/).map((item) => item.trim()).filter(Boolean).slice(0, 8);
}

function displayPropertyPrice(price, mode) {
  const amount = value(price);
  if (!amount) return mode === "sale" ? "售价待补" : "租金待补";
  if (/元|万|\/月|每月/.test(amount)) return amount;
  return `${amount}${mode === "sale" ? "万元" : "元/月"}`;
}

function normalizePriceInput(price) {
  const amount = value(price);
  const matched = amount.match(/\d+(?:\.\d+)?/);
  return matched ? matched[0] : amount;
}

function inferListingMode(data = {}) {
  if (["sale", "sell", "出售"].includes(data.listingMode || data.dealType)) return "sale";
  if (data.salePrice && !data.rentPrice) return "sale";
  return "rent";
}

function buildMapPreview(structuredData = {}) {
  const location = structuredData.mapLocation || {};
  const latitude = Number(location.latitude);
  const longitude = Number(location.longitude);
  const address = value(location.address) || value(structuredData.address) || value(structuredData.businessArea);
  if (Number.isFinite(latitude) && Number.isFinite(longitude) && latitude !== 0 && longitude !== 0) {
    return {
      hasPoint: true,
      latitude,
      longitude,
      address,
      markers: [{
        id: 1,
        latitude,
        longitude,
        title: value(location.name) || address || "房源位置",
        callout: {
          content: "🏠 房源位置",
          color: "#172033",
          fontSize: 13,
          borderRadius: 6,
          bgColor: "#ffffff",
          padding: 8,
          display: "ALWAYS"
        }
      }]
    };
  }
  return { hasPoint: false, latitude: 0, longitude: 0, address, markers: [] };
}

function simplifyMapAddress(address) {
  return String(address || "")
    .replace(/[，,]/g, " ")
    .replace(/(?:\d+|[一二三四五六七八九十百]+)栋(?:\d+|[一二三四五六七八九十百]+)?(?:号|室)?[^\s]*/u, "")
    .replace(/(?:\d+|[一二三四五六七八九十百]+)(?:号|室)[^\s]*/u, "")
    .replace(/\s+/g, " ")
    .trim();
}

function buildMapAddressCandidates(structuredData = {}) {
  const address = value(structuredData.address);
  const community = value(structuredData.community);
  const businessArea = value(structuredData.businessArea);
  const raw = [
    address,
    [address, community].filter(Boolean).join(" "),
    [community, businessArea].filter(Boolean).join(" "),
    community,
    businessArea
  ].filter(Boolean);
  const simpleCommunity = community.replace(/\d+\s*(?:户型|房源|栋|号|室).*$/u, "").trim();
  const candidates = [...raw, ...raw.map(simplifyMapAddress), simpleCommunity]
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, index, list) => list.indexOf(item) === index);
  const city = (candidates.join(" ").match(/[^\s，,]+市/) || [""])[0];
  if (!city) return candidates;
  return [...candidates, ...candidates.map((item) => item.includes(city) ? item : `${city} ${item}`)]
    .filter((item, index, list) => list.indexOf(item) === index);
}

function inferMapRegion(structuredData = {}) {
  const text = buildMapAddressCandidates(structuredData).join(" ");
  const city = (text.match(/[^\s，,]+市/) || [""])[0];
  if (city) return city;
  if (text.includes("湖南")) return "湖南省";
  return "";
}

Page({
  data: {
    noteId: "",
    user: null,
    loading: true,
    saving: false,
    uploading: false,
    saveStatus: "",
    listingMode: "rent",
    form: {
      title: "",
      summary: "",
      body: "",
      coverUrl: "",
      media: [],
      categoryIds: [],
      locationText: "",
      visibilityConfig: {}
    },
    structuredData: {},
    privateData: {},
    imageMedia: [],
    supplementalMedia: [],
    highlights: [],
    remarkCount: 0,
    mapPreview: buildMapPreview(),
    geocodingAddress: false,
    previewTitle: "未命名房源",
    previewPrice: "租金待补",
    previewFacts: "补充户型与面积",
    previewArea: "补充公开区域",
    priceLabel: "租金",
    priceUnit: "元/月",
    moreFields: MORE_FIELDS,
    privateFields: PRIVATE_FIELDS,
    openSection: "",
    linkDraft: { title: "", url: "" },
    showLinkForm: false
  },

  onLoad(options = {}) {
    this.setData({ noteId: options.id || "" });
  },

  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    if (this.data.noteId) this.loadNote();
    else this.createDraft();
  },

  async createDraft() {
    if (this.creatingDraft) return;
    this.creatingDraft = true;
    try {
      const res = await api.createManualNoteDraft({
        ownerUserId: this.data.user.id,
        cardType: "property_listing",
        inputMode: "blank",
        rawText: "",
        title: ""
      });
      this.setData({ noteId: res.data.id });
      this.applyNote(res.data || {});
    } catch (error) {
      wx.showToast({ title: error.detail || "创建失败", icon: "none" });
    } finally {
      this.creatingDraft = false;
    }
  },

  async loadNote() {
    try {
      const res = await api.fetchNote(this.data.noteId, this.data.user.id);
      const note = res.data || {};
      const cardType = ((note.visibilityConfig || {}).cardType || "text_note");
      if (cardType !== "property_listing") {
        wx.redirectTo({ url: editorPathForCardType(cardType, this.data.noteId) });
        return;
      }
      this.applyNote(note);
    } catch (error) {
      wx.showToast({ title: error.detail || "加载失败", icon: "none" });
    }
  },

  applyNote(note) {
    const config = note.visibilityConfig || {};
    const structuredData = { ...(config.structuredData || {}) };
    const listingMode = inferListingMode(structuredData);
    if (!structuredData.price) {
      structuredData.price = listingMode === "sale" ? (structuredData.salePrice || "") : (structuredData.rentPrice || "");
    }
    structuredData.price = normalizePriceInput(structuredData.price);
    const form = { ...this.data.form, ...note, media: note.media || [], visibilityConfig: config };
    this.setData({
      form,
      structuredData,
      privateData: { ...(config.privateData || {}) },
      listingMode,
      mapPreview: buildMapPreview(structuredData),
      saveStatus: "已保存",
      loading: false
    }, () => {
      this.refreshView();
      this.resolveMapLocation({ silent: true, persist: true });
    });
  },

  refreshView() {
    const data = this.data.structuredData || {};
    const mode = this.data.listingMode;
    const images = imageItems(this.data.form.media);
    const title = value(data.community) || value(this.data.form.title) || "未命名房源";
    const price = value(data.price);
    this.setData({
      imageMedia: images,
      supplementalMedia: otherItems(this.data.form.media),
      highlights: splitHighlights(data.highlights),
      remarkCount: value(data.remark).length,
      previewTitle: title,
      previewPrice: displayPropertyPrice(price, mode),
      previewFacts: [value(data.layout), value(data.area)].filter(Boolean).join(" · ") || "补充户型与面积",
      previewArea: value(data.businessArea) || value(data.address) || "补充公开区域",
      priceLabel: mode === "sale" ? "售价" : "租金",
      priceUnit: mode === "sale" ? "万元" : "元/月",
      mapPreview: buildMapPreview(data)
    });
  },

  markDirty() {
    if (this.data.saveStatus !== "未保存") this.setData({ saveStatus: "未保存" });
  },

  handleStructuredInput(event) {
    const key = event.currentTarget.dataset.key;
    const nextStructuredData = { ...this.data.structuredData, [key]: event.detail.value };
    if (["address", "community", "businessArea"].includes(key)) {
      delete nextStructuredData.mapLocation;
    }
    this.setData({ structuredData: nextStructuredData, mapPreview: buildMapPreview(nextStructuredData) }, () => {
      this.markDirty();
      this.refreshView();
      if (key === "address" || key === "community" || key === "businessArea") this.resolveMapLocation({ silent: true, persist: false });
    });
  },

  async resolveMapLocation({ silent = false, persist = false } = {}) {
    if (this.data.geocodingAddress || this.data.mapPreview.hasPoint) return this.data.mapPreview.hasPoint;
    const structuredData = this.data.structuredData || {};
    if (!value(structuredData.address) && !value(structuredData.community)) return false;
    const requestedMapKey = ["address", "community", "businessArea"].map((key) => value(structuredData[key])).join("|");
    const candidates = buildMapAddressCandidates(structuredData);
    if (!candidates.length) return false;
    this.setData({ geocodingAddress: true });
    try {
      const region = inferMapRegion(structuredData);
      const regions = region ? [region, ""] : [""];
      let location = null;
      for (const regionItem of regions) {
        for (const candidate of candidates) {
          const response = await api.geocodeAddress({ address: candidate, region: regionItem });
          const data = (response && response.data) || {};
          if (data.found && Number.isFinite(Number(data.latitude)) && Number.isFinite(Number(data.longitude))) {
            location = data;
            break;
          }
        }
        if (location) break;
      }
      if (!location) {
        if (!silent) wx.showToast({ title: "暂未匹配到地图位置", icon: "none" });
        return false;
      }
      const currentMapKey = ["address", "community", "businessArea"].map((key) => value(this.data.structuredData[key])).join("|");
      if (currentMapKey !== requestedMapKey) return false;
      const nextStructuredData = {
        ...structuredData,
        mapLocation: {
          name: value(location.name) || value(structuredData.community) || "房源位置",
          address: value(location.address) || candidates[0],
          latitude: Number(location.latitude),
          longitude: Number(location.longitude)
        }
      };
      this.setData({ structuredData: nextStructuredData, mapPreview: buildMapPreview(nextStructuredData) }, async () => {
        this.markDirty();
        if (persist && this.data.noteId && value(nextStructuredData.community)) await this.handleSave(false);
      });
      return true;
    } catch (error) {
      if (!silent) wx.showToast({ title: error.detail || "地图定位失败", icon: "none" });
      return false;
    } finally {
      this.setData({ geocodingAddress: false });
    }
  },

  handleResolveMap() {
    this.resolveMapLocation({ silent: false, persist: true });
  },

  openWechatLocation(location) {
    wx.openLocation({
      latitude: Number(location.latitude),
      longitude: Number(location.longitude),
      name: value(location.name) || value(this.data.structuredData.community) || "房源位置",
      address: value(location.address) || value(this.data.structuredData.address)
    });
  },

  openNavigationApp(location) {
    if (!wx.createMapContext) {
      this.openWechatLocation(location);
      return;
    }
    const mapContext = wx.createMapContext("propertyEditorMap", this);
    if (!mapContext || typeof mapContext.openMapApp !== "function") {
      this.openWechatLocation(location);
      return;
    }
    mapContext.openMapApp({
      latitude: Number(location.latitude),
      longitude: Number(location.longitude),
      destination: value(location.name) || value(this.data.structuredData.community) || "房源位置",
      fail: () => this.openWechatLocation(location)
    });
  },

  handleOpenMap() {
    const location = this.data.structuredData.mapLocation || {};
    if (!Number(location.latitude) || !Number(location.longitude)) {
      this.handleResolveMap();
      return;
    }
    wx.showActionSheet({
      itemList: ["选择导航App", "微信内置地图", "复制地址"],
      success: ({ tapIndex }) => {
        if (tapIndex === 0) this.openNavigationApp(location);
        if (tapIndex === 1) this.openWechatLocation(location);
        if (tapIndex === 2) {
          const address = value(location.address) || value(this.data.structuredData.address);
          if (address) wx.setClipboardData({ data: address, success: () => wx.showToast({ title: "地址已复制", icon: "success" }) });
        }
      }
    });
  },

  handlePrivateInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`privateData.${key}`]: event.detail.value }, () => this.markDirty());
  },

  handleModeChange(event) {
    wx.showActionSheet({
      itemList: ["出租", "出售"],
      success: ({ tapIndex }) => {
        const listingMode = tapIndex === 1 ? "sale" : "rent";
        if (listingMode === this.data.listingMode) return;
        this.setData({ listingMode }, () => {
          this.markDirty();
          this.refreshView();
        });
      }
    });
  },

  handleToggleSection(event) {
    const section = event.currentTarget.dataset.section;
    this.setData({ openSection: this.data.openSection === section ? "" : section });
  },

  chooseImages() {
    const count = Math.min(9 - this.data.imageMedia.length, 9);
    if (count <= 0) {
      wx.showToast({ title: "最多添加 9 张房源图片", icon: "none" });
      return;
    }
    const success = ({ tempFiles = [] }) => this.uploadImages(tempFiles.map((item) => item.tempFilePath || item.path).filter(Boolean));
    if (typeof wx.chooseImage === "function") {
      wx.chooseImage({ count, sourceType: ["album", "camera"], success });
      return;
    }
    wx.chooseMedia({ count, mediaType: ["image"], sourceType: ["album", "camera"], success });
  },

  async uploadImages(paths) {
    if (!paths.length || this.data.uploading) return;
    this.setData({ uploading: true });
    try {
      const uploaded = await Promise.all(paths.map((filePath) => api.uploadAsset({ filePath, mediaType: "image", ownerUserId: this.data.user.id })));
      const imageCount = this.data.imageMedia.length;
      const additions = uploaded.map((item, index) => ({ ...item, id: item.id || `image_${Date.now()}_${index}`, type: "image", sortOrder: imageCount + index }));
      const media = [...this.data.imageMedia, ...additions, ...this.data.supplementalMedia].map((item, index) => ({ ...item, sortOrder: index }));
      this.setData({ "form.media": media, "form.coverUrl": (media[0] || {}).url || "" }, () => {
        this.markDirty();
        this.refreshView();
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "图片上传失败", icon: "none" });
    } finally {
      this.setData({ uploading: false });
    }
  },

  handlePreviewImage(event) {
    const index = Number(event.currentTarget.dataset.index || 0);
    const urls = this.data.imageMedia.map((item) => item.url).filter(Boolean);
    if (urls.length) wx.previewImage({ current: urls[index] || urls[0], urls });
  },

  handleSetCover(event) {
    const index = Number(event.currentTarget.dataset.index || 0);
    if (index <= 0) {
      wx.showToast({ title: "当前已是封面", icon: "none" });
      return;
    }
    const images = [...this.data.imageMedia];
    const [selected] = images.splice(index, 1);
    images.unshift(selected);
    const media = [...images, ...this.data.supplementalMedia].map((item, itemIndex) => ({ ...item, sortOrder: itemIndex }));
    this.setData({ "form.media": media, "form.coverUrl": selected.url || "" }, () => {
      this.markDirty();
      this.refreshView();
      wx.showToast({ title: "已设为封面", icon: "success" });
    });
  },

  handleRemoveImage(event) {
    const index = Number(event.currentTarget.dataset.index);
    const images = this.data.imageMedia.filter((_, itemIndex) => itemIndex !== index);
    const media = [...images, ...this.data.supplementalMedia].map((item, itemIndex) => ({ ...item, sortOrder: itemIndex }));
    this.setData({ "form.media": media, "form.coverUrl": (images[0] || {}).url || "" }, () => {
      this.markDirty();
      this.refreshView();
    });
  },

  handleChooseSupplement() {
    wx.showActionSheet({
      itemList: ["添加 PDF", "添加外部链接"],
      success: ({ tapIndex }) => {
        if (tapIndex === 0) this.choosePdf();
        if (tapIndex === 1) this.setData({ showLinkForm: true });
      }
    });
  },

  choosePdf() {
    const count = Math.min(5 - this.data.supplementalMedia.filter((item) => item.type === "pdf").length, 5);
    if (count <= 0) return;
    wx.chooseMessageFile({
      count,
      type: "file",
      extension: ["pdf"],
      success: async ({ tempFiles = [] }) => {
        try {
          this.setData({ uploading: true });
          const uploaded = await Promise.all(tempFiles.map((item) => api.uploadAsset({ filePath: item.path, mediaType: "pdf", ownerUserId: this.data.user.id })));
          const additions = uploaded.map((item, index) => ({ ...item, id: item.id || `pdf_${Date.now()}_${index}`, type: "pdf" }));
          const media = [...this.data.imageMedia, ...this.data.supplementalMedia, ...additions].map((item, index) => ({ ...item, sortOrder: index }));
          this.setData({ "form.media": media }, () => { this.markDirty(); this.refreshView(); });
        } catch (error) {
          wx.showToast({ title: error.detail || "PDF 上传失败", icon: "none" });
        } finally {
          this.setData({ uploading: false });
        }
      }
    });
  },

  handleLinkInput(event) {
    this.setData({ [`linkDraft.${event.currentTarget.dataset.key}`]: event.detail.value });
  },

  addLink() {
    const url = value(this.data.linkDraft.url);
    if (!/^https:\/\//i.test(url)) {
      wx.showToast({ title: "链接必须以 https:// 开头", icon: "none" });
      return;
    }
    const link = { id: `link_${Date.now()}`, type: "link", title: value(this.data.linkDraft.title) || url, url };
    const media = [...this.data.imageMedia, ...this.data.supplementalMedia, link].map((item, index) => ({ ...item, sortOrder: index }));
    this.setData({ "form.media": media, linkDraft: { title: "", url: "" }, showLinkForm: false }, () => {
      this.markDirty();
      this.refreshView();
    });
  },

  handleRemoveSupplement(event) {
    const index = Number(event.currentTarget.dataset.index);
    const rest = this.data.supplementalMedia.filter((_, itemIndex) => itemIndex !== index);
    const media = [...this.data.imageMedia, ...rest].map((item, itemIndex) => ({ ...item, sortOrder: itemIndex }));
    this.setData({ "form.media": media }, () => { this.markDirty(); this.refreshView(); });
  },

  async handleSave(showToast = true) {
    if (this.data.saving) return false;
    const community = value(this.data.structuredData.community);
    if (!community) {
      wx.showToast({ title: "请填写小区 / 楼盘", icon: "none" });
      return false;
    }
    this.setData({ saving: true });
    try {
      const structuredData = { ...this.data.structuredData, listingMode: this.data.listingMode };
      delete structuredData.rentPrice;
      delete structuredData.salePrice;
      delete structuredData.dealType;
      const firstImage = this.data.imageMedia[0];
      const config = {
        ...(this.data.form.visibilityConfig || {}),
        schemaVersion: 2,
        cardType: "property_listing",
        cardState: "editing",
        structuredData,
        privateData: this.data.privateData
      };
      await api.updateNote(this.data.noteId, {
        ownerUserId: this.data.user.id,
        title: community,
        summary: [value(structuredData.price), value(structuredData.layout), value(structuredData.area)].filter(Boolean).join(" · "),
        body: value(structuredData.highlights) || community,
        coverUrl: (firstImage && firstImage.url) || null,
        media: this.data.form.media,
        categoryIds: this.data.form.categoryIds || [],
        phone: null,
        locationText: value(structuredData.address) || null,
        visibilityConfig: config
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
      wx.showToast({ title: error.detail || error.message || "发客户失败，请先完善房源", icon: "none" });
    } finally { this.setData({ saving: false }); }
  },

  handleDelete() {
    wx.showModal({
      title: "删除房源",
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
