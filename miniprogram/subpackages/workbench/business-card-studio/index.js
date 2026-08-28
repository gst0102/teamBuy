const api = require("../../../services/api");
const resourceStore = require("../../../stores/resource-store");
const { getCurrentUser } = require("../../../utils/dashboard");

const CARD_STYLES = [
  { id: "business_blue", label: "标准专业", desc: "突出身份与联系方式", tone: "blue" }
];

const TYPE_LABELS = {
  property_listing: "房源",
  groupbuy_product: "商品",
  service_offer: "服务",
  text_note: "资料",
  image_ocr: "图片",
  pdf_document: "PDF",
  link: "链接",
  article: "文章"
};

function clean(value) {
  return String(value == null ? "" : value).trim();
}

function cardTypeOf(note = {}) {
  return ((note.visibilityConfig || {}).cardType || "text_note");
}

function normalizeProfile(user = {}) {
  const source = user.salesProfile || {};
  return {
    displayName: source.displayName || user.nickname || "",
    avatarUrl: source.avatarUrl || user.avatarUrl || "",
    jobTitle: source.jobTitle || "",
    company: source.company || "",
    city: source.city || "",
    phone: source.phone || user.phone || "",
    wechat: source.wechat || user.wechat || "",
    wechatQrUrl: source.wechatQrUrl || "",
    email: source.email || "",
    website: source.website || ""
  };
}

function keywordText(value) {
  return Array.isArray(value) ? value.join("，") : clean(value);
}

function keywordList(value) {
  return Array.from(new Set(String(value || "").split(/[，,、\n]/).map(clean).filter(Boolean))).slice(0, 6);
}

function contactLineForProfile(profile = {}) {
  const phone = clean(profile.phone);
  const wechat = clean(profile.wechat);
  const email = clean(profile.email);
  return [
    phone ? (wechat && phone === wechat ? `电话 / 微信 ${phone}` : `电话 ${phone}`) : "",
    wechat && phone !== wechat ? `微信 ${wechat}` : "",
    email ? `邮箱 ${email}` : ""
  ].filter(Boolean).join(" · ");
}

function businessCardStorageKey(ownerUserId) {
  return `businessCardNoteId:${ownerUserId || ""}`;
}

function resourceOption(note, selectedIds) {
  const type = cardTypeOf(note);
  return {
    id: note.id,
    title: note.title || "未命名资料",
    summary: note.summary || note.body || "",
    coverUrl: note.coverUrl || ((note.media || []).find((item) => item.type === "image") || {}).url || "",
    typeLabel: TYPE_LABELS[type] || "资料",
    typeInitial: String(TYPE_LABELS[type] || "资料").slice(0, 1),
    selected: selectedIds.includes(note.id)
  };
}

Page({
  data: {
    user: null,
    noteId: "",
    loading: true,
    draftReady: false,
    saving: false,
    uploadingField: "",
    profile: normalizeProfile(),
    profileInitial: "名",
    structuredData: { headline: "", serviceKeywordsText: "", bio: "", featuredNoteIds: [] },
    media: [],
    styleId: "business_blue",
    styleLabel: "标准专业",
    styles: CARD_STYLES,
    contactLine: "",
    keywordChips: [],
    featuredResources: [],
    resourceOptions: [],
    resourcePickerVisible: false,
    moreContactOpen: false
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
    const profile = normalizeProfile(user);
    this.setData({ user, profile, profileInitial: String(profile.displayName || "名").slice(0, 1), loading: false, draftReady: false });
    if (this.hasLoadedOnce && this.data.noteId) return;
    if (this.data.noteId) this.loadNote();
    else this.createDraft();
  },

  async createDraft() {
    if (this.creatingDraft) return;
    this.creatingDraft = true;
    try {
      const cachedNoteId = wx.getStorageSync(businessCardStorageKey(this.data.user.id));
      if (cachedNoteId) {
        try {
          const cachedNoteRes = await api.fetchNote(cachedNoteId, this.data.user.id);
          const cachedNote = cachedNoteRes.data || {};
          if (cardTypeOf(cachedNote) === "business_card" && cachedNote.status !== "deleted") {
            this.setData({ noteId: cachedNote.id });
            await this.applyNote(cachedNote);
            return;
          }
        } catch (error) {
          wx.removeStorageSync(businessCardStorageKey(this.data.user.id));
        }
      }
      const listParams = { ownerUserId: this.data.user.id, sort: "updated_desc" };
      const cachedNotes = api.getCachedNotes(listParams);
      const existing = (cachedNotes || []).find((note) => cardTypeOf(note) === "business_card" && note.status !== "deleted")
        || await api.fetchNotes(listParams, { metadataOnly: true }).then((res) => (res.data || []).find((note) => cardTypeOf(note) === "business_card" && note.status !== "deleted"));
      if (existing) {
        this.setData({ noteId: existing.id });
        wx.setStorageSync(businessCardStorageKey(this.data.user.id), existing.id);
        await this.applyNote(existing);
        return;
      }
      const res = await api.createManualNoteDraft({
        ownerUserId: this.data.user.id,
        cardType: "business_card",
        inputMode: "blank",
        rawText: "",
        title: ""
      });
      this.setData({ noteId: res.data.id });
      wx.setStorageSync(businessCardStorageKey(this.data.user.id), res.data.id);
      await this.applyNote(res.data || {});
    } catch (error) {
      wx.showToast({ title: error.detail || "创建名片失败", icon: "none" });
    } finally {
      this.creatingDraft = false;
    }
  },

  async loadNote() {
    try {
      const res = await api.fetchNote(this.data.noteId, this.data.user.id);
      const note = res.data || {};
      if (cardTypeOf(note) !== "business_card") {
        wx.showToast({ title: "这不是电子名片", icon: "none" });
        return;
      }
      await this.applyNote(note);
    } catch (error) {
      wx.showToast({ title: error.detail || "读取名片失败", icon: "none" });
    }
  },

  async applyNote(note) {
    const config = note.visibilityConfig || {};
    const source = config.structuredData || {};
    const structuredData = {
      headline: clean(source.headline),
      serviceKeywordsText: keywordText(source.serviceKeywords),
      bio: clean(source.bio),
      featuredNoteIds: Array.isArray(source.featuredNoteIds) ? source.featuredNoteIds.slice(0, 3) : []
    };
    const legacyProfile = {
      ...this.data.profile,
      displayName: this.data.profile.displayName || clean(source.name),
      avatarUrl: this.data.profile.avatarUrl || clean(source.avatarUrl) || note.coverUrl || "",
      jobTitle: this.data.profile.jobTitle || clean(source.title),
      company: this.data.profile.company || clean(source.company),
      city: this.data.profile.city || clean(source.city),
      phone: this.data.profile.phone || clean(source.phone) || note.phone || "",
      wechat: this.data.profile.wechat || clean(source.wechat),
      wechatQrUrl: this.data.profile.wechatQrUrl || clean(source.qrCodeUrl)
    };
    this.setData({
      profile: legacyProfile,
      profileInitial: String(legacyProfile.displayName || "名").slice(0, 1),
      contactLine: contactLineForProfile(legacyProfile),
      structuredData,
      media: note.media || [],
      styleId: "business_blue",
      styleLabel: "标准专业",
      keywordChips: keywordList(structuredData.serviceKeywordsText),
      moreContactOpen: Boolean(this.data.profile.email || this.data.profile.website),
      loading: false,
      draftReady: true
    });
    this.hasLoadedOnce = true;
    this.loadResourceOptions();
  },

  async loadResourceOptions() {
    try {
      const params = { ownerUserId: this.data.user.id, sort: "updated_desc" };
      const cached = api.getCachedNotes(params);
      const res = api.hasCachedNotes(params)
        ? { data: cached, cached: true }
        : await api.fetchNotes(params, { metadataOnly: true });
      const selectedIds = this.data.structuredData.featuredNoteIds || [];
      const options = (res.data || [])
        .filter((note) => note.id !== this.data.noteId && cardTypeOf(note) !== "business_card" && note.status !== "deleted")
        .slice(0, 40)
        .map((note) => resourceOption(note, selectedIds));
      this.setData({ resourceOptions: options }, () => this.refreshFeaturedResources());
    } catch (error) {
      this.setData({ resourceOptions: [] });
    }
  },

  refreshFeaturedResources() {
    const selectedIds = this.data.structuredData.featuredNoteIds || [];
    const byId = new Map((this.data.resourceOptions || []).map((item) => [item.id, item]));
    const featuredResources = selectedIds.map((id) => byId.get(id)).filter(Boolean);
    const resourceOptions = (this.data.resourceOptions || []).map((item) => ({ ...item, selected: selectedIds.includes(item.id) }));
    this.setData({ featuredResources, resourceOptions });
  },

  handleProfileInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.detail.value || "";
    const update = { [`profile.${key}`]: value };
    if (key === "displayName") update.profileInitial = String(value || "名").slice(0, 1);
    if (["phone", "wechat", "email"].includes(key)) {
      update.contactLine = contactLineForProfile({ ...this.data.profile, [key]: value });
    }
    this.setData(update);
  },

  handleStructuredInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.detail.value || "";
    const update = { [`structuredData.${key}`]: value };
    if (key === "serviceKeywordsText") update.keywordChips = keywordList(value);
    this.setData(update);
  },

  handleSelectStyle(event) {
    const styleId = event.currentTarget.dataset.id || "business_blue";
    const styleLabel = event.currentTarget.dataset.label || (CARD_STYLES.find((item) => item.id === styleId) || {}).label || "标准专业";
    this.setData({ styleId, styleLabel });
  },

  handleToggleMoreContact() {
    this.setData({ moreContactOpen: !this.data.moreContactOpen });
  },

  handleOpenResourcePicker() {
    this.setData({ resourcePickerVisible: true });
  },

  handleCloseResourcePicker() {
    this.setData({ resourcePickerVisible: false });
  },

  noop() {},

  handleToggleResource(event) {
    const id = event.currentTarget.dataset.id;
    const selectedIds = [...(this.data.structuredData.featuredNoteIds || [])];
    const index = selectedIds.indexOf(id);
    if (index >= 0) selectedIds.splice(index, 1);
    else if (selectedIds.length >= 3) {
      wx.showToast({ title: "精选资料最多3份", icon: "none" });
      return;
    } else selectedIds.push(id);
    this.setData({ "structuredData.featuredNoteIds": selectedIds }, () => this.refreshFeaturedResources());
  },

  handleRemoveResource(event) {
    const id = event.currentTarget.dataset.id;
    const selectedIds = (this.data.structuredData.featuredNoteIds || []).filter((item) => item !== id);
    this.setData({ "structuredData.featuredNoteIds": selectedIds }, () => this.refreshFeaturedResources());
  },

  chooseProfileImage(event) {
    const field = event.currentTarget.dataset.field;
    if (!field || this.data.uploadingField) return;
    const success = ({ tempFiles = [], tempFilePaths = [] }) => {
      const path = (tempFiles[0] && (tempFiles[0].tempFilePath || tempFiles[0].path)) || tempFilePaths[0];
      if (path) this.uploadProfileImage(path, field);
    };
    const fail = (error = {}) => {
      if (String(error.errMsg || "").includes("cancel")) return;
      wx.showToast({ title: "图片选择失败", icon: "none" });
    };
    if (typeof wx.chooseImage === "function") {
      wx.chooseImage({ count: 1, sourceType: ["album", "camera"], success, fail });
      return;
    }
    wx.chooseMedia({ count: 1, mediaType: ["image"], sourceType: ["album", "camera"], success, fail });
  },

  async uploadProfileImage(filePath, field) {
    this.setData({ uploadingField: field });
    try {
      const asset = await api.uploadAsset({ filePath, mediaType: "image", ownerUserId: this.data.user.id });
      if (!asset.url) throw new Error("上传结果无图片地址");
      this.setData({ [`profile.${field}`]: asset.url });
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "上传失败", icon: "none" });
    } finally {
      this.setData({ uploadingField: "" });
    }
  },

  validate() {
    const profile = this.data.profile;
    if (!clean(profile.avatarUrl)) return "请添加头像";
    if (!clean(profile.displayName)) return "请填写姓名";
    if (!clean(profile.jobTitle)) return "请填写职位或身份";
    if (!clean(this.data.structuredData.headline)) return "请填写一句话介绍";
    const keywords = keywordList(this.data.structuredData.serviceKeywordsText);
    if (keywords.length > 6) return "服务关键词最多6个";
    return "";
  },

  async handleSave(options = {}) {
    if (this.data.saving) return false;
    if (!this.data.noteId) {
      wx.showToast({ title: "名片正在准备，请稍候", icon: "none" });
      return false;
    }
    const errorText = this.validate();
    if (errorText) {
      wx.showToast({ title: errorText, icon: "none" });
      return false;
    }
    this.setData({ saving: true });
    try {
      const profilePayload = { ...this.data.profile, avatarUrl: this.data.profile.avatarUrl };
      const profileRes = await api.updateUserProfile(this.data.user.id, profilePayload);
      const user = profileRes.data || { ...this.data.user, salesProfile: this.data.profile };
      getApp().globalData.currentUser = user;
      wx.setStorageSync("currentUser", user);
      const keywords = keywordList(this.data.structuredData.serviceKeywordsText);
      const structuredData = {
        headline: clean(this.data.structuredData.headline),
        serviceKeywords: keywords,
        bio: clean(this.data.structuredData.bio),
        featuredNoteIds: (this.data.structuredData.featuredNoteIds || []).slice(0, 3)
      };
      const title = `${clean(this.data.profile.displayName)}的电子名片`;
      const visibilityConfig = {
        schemaVersion: 2,
        cardType: "business_card",
        cardState: "ready",
        structuredData,
        displayConfig: { styleId: this.data.styleId },
        conversionConfig: {
          showContactPhone: Boolean(clean(this.data.profile.phone)),
          enablePrivateConsultation: Boolean(clean(this.data.profile.wechat) || clean(this.data.profile.wechatQrUrl)),
          collectLeads: true,
          enableAppointment: false,
          enableLightScrm: true
        }
      };
      await api.updateNote(this.data.noteId, {
        ownerUserId: this.data.user.id,
        title,
        summary: structuredData.headline,
        body: structuredData.bio || structuredData.headline,
        coverUrl: this.data.profile.avatarUrl,
        media: this.data.media || [],
        categoryIds: [],
        phone: null,
        locationText: null,
        visibilityConfig
      });
      // The library may have painted a cached card while this editor was
      // open.  A saved card revision must invalidate that metadata snapshot
      // before the user returns to the share flow.
      resourceStore.invalidateOwner(this.data.user.id);
      wx.setStorageSync(businessCardStorageKey(this.data.user.id), this.data.noteId);
      this.setData({ user, keywordChips: keywords });
      if (!options.silent) wx.showToast({ title: "名片已保存", icon: "success" });
      return true;
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "保存失败", icon: "none" });
      return false;
    } finally {
      this.setData({ saving: false });
    }
  },

  async handlePreview() {
    const saved = await this.handleSave({ silent: true });
    if (saved) wx.navigateTo({ url: `/pages/note-preview/index?id=${this.data.noteId}&preview=1` });
  },

  async handlePublish() {
    const saved = await this.handleSave({ silent: true });
    if (!saved) return;
    this.setData({ saving: true });
    try {
      await api.publishNote(this.data.noteId, this.data.user.id);
      wx.showToast({ title: "名片已准备好，可从资料卡发客户", icon: "success" });
      setTimeout(() => wx.switchTab({ url: "/pages/library/index" }), 450);
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "发客户失败，请先完善名片", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  }
});
