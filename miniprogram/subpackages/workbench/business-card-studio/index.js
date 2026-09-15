const api = require("../../../services/api");
const resourceStore = require("../../../stores/resource-store");
const { getCurrentUser } = require("../../../utils/dashboard");
const {
  BUSINESS_INDUSTRY_OPTIONS,
  getBusinessSubIndustryOptions
} = require("../../../utils/business-industry");
const {
  buildBusinessCardShareSource,
  buildBusinessCardShareTitle
} = require("../../../utils/business-card-share");
const {
  buildShareMessage,
  getNoteShareSnapshotState,
  getShareImageUrlFromState,
  prepareNoteShareSnapshot,
  setShareMenuEnabled
} = require("../../../plugins/share-snapshot/index");
const subscription = require("../../../services/subscription");

const CARD_STYLES = [
  { id: "business_blue", label: "标准专业", desc: "突出身份与联系方式", tone: "blue" }
];
const INDUSTRY_OPTIONS = ["请选择行业", ...BUSINESS_INDUSTRY_OPTIONS];

const INTENT_DIRECTION_OPTIONS = ["我近期可以合作", "我正在找合作"];
const INTENT_VALIDITY_OPTIONS = ["长期有效", "7天内有效", "30天内有效"];

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

function keywordList(value, maxCount = 6) {
  return Array.from(new Set(String(value || "").split(/[，,、\n]/).map(clean).filter(Boolean))).slice(0, maxCount);
}

function industryChildren(industry) {
  return getBusinessSubIndustryOptions(industry);
}

function selectedIndex(options, value) {
  const index = options.indexOf(value);
  return index >= 0 ? index : 0;
}

function normalizeIntent(value = {}) {
  const source = value && typeof value === "object" ? value : {};
  return {
    direction: INTENT_DIRECTION_OPTIONS.includes(source.direction) ? source.direction : INTENT_DIRECTION_OPTIONS[0],
    text: clean(source.text || source.summary),
    validity: INTENT_VALIDITY_OPTIONS.includes(source.validity) ? source.validity : INTENT_VALIDITY_OPTIONS[0]
  };
}

function hasOwn(value, key) {
  return Boolean(value && Object.prototype.hasOwnProperty.call(value, key));
}

function normalizeOpportunityVisibility(opportunity = {}) {
  const hasScopedFlags = [
    "resourceEnabled",
    "resourceDiscoverable",
    "intentEnabled",
    "intentDiscoverable"
  ].some((key) => hasOwn(opportunity, key));
  const hasLegacyFlags = hasOwn(opportunity, "enabled") || hasOwn(opportunity, "discoverable");
  const legacyPublic = hasLegacyFlags && opportunity.enabled !== false && opportunity.discoverable !== false;
  const scopedPublic = (enabledKey, discoverableKey) => {
    if (hasOwn(opportunity, enabledKey) || hasOwn(opportunity, discoverableKey)) {
      return opportunity[enabledKey] !== false && opportunity[discoverableKey] !== false;
    }
    return hasScopedFlags ? false : legacyPublic;
  };
  return {
    resourceEnabled: scopedPublic("resourceEnabled", "resourceDiscoverable"),
    intentEnabled: scopedPublic("intentEnabled", "intentDiscoverable"),
    // Legacy shared flags were already an explicit choice. New scoped flags
    // become a remembered choice only after the completion prompt or a direct
    // toggle is saved with visibilityChoiceVersion.
    visibilityChoiceMade: Boolean(opportunity.visibilityChoiceVersion)
      || (!hasScopedFlags && hasLegacyFlags)
  };
}

function buildIntentExpiry(validity) {
  if (validity === "长期有效") return "";
  const date = new Date();
  date.setDate(date.getDate() + (validity === "7天内有效" ? 7 : 30));
  return date.toISOString();
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

function noteShareState(note = {}) {
  const config = note.visibilityConfig || {};
  return String(note.shareState || config.shareState || (note.sharePublished ? "published" : "private"));
}

function createShareId(noteId) {
  return `share_note_${noteId || "note"}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
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
    shareImageReady: false,
    shareImagePreparing: false,
    shareImageState: "missing",
    shareImageUrl: "",
    shareStatusText: "发布并准备分享",
    shareDirty: false,
    uploadingField: "",
    profile: normalizeProfile(),
    profileInitial: "名",
    structuredData: { headline: "", serviceKeywordsText: "", bio: "", featuredNoteIds: [] },
    businessOpportunity: {
      resourceEnabled: false,
      intentEnabled: false,
      visibilityChoiceMade: false,
      industry: "",
      subIndustry: "",
      industryTagsText: "",
      cooperationIntent: normalizeIntent()
    },
    industryOptions: INDUSTRY_OPTIONS,
    subIndustryOptions: ["请选择细分行业"],
    industryIndex: 0,
    subIndustryIndex: 0,
    intentDirectionOptions: INTENT_DIRECTION_OPTIONS,
    intentValidityOptions: INTENT_VALIDITY_OPTIONS,
    media: [],
    styleId: "business_blue",
    styleLabel: "标准专业",
    styles: CARD_STYLES,
    contactLine: "",
    keywordChips: [],
    featuredResources: [],
    resourceOptions: [],
    resourcePickerVisible: false,
    moreContactOpen: false,
    completionPromptVisible: false
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
    const alreadyLoaded = Boolean(this.hasLoadedOnce && this.data.noteId);
    this.setData({
      user,
      profile,
      profileInitial: String(profile.displayName || "名").slice(0, 1),
      loading: false,
      ...(alreadyLoaded ? {} : { draftReady: false })
    });
    if (alreadyLoaded) return;
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
    const opportunity = config.businessOpportunity || {};
    const industry = clean(opportunity.industry || source.industry);
    const subIndustry = clean(opportunity.subIndustry || source.subIndustry);
    const industryTags = opportunity.industryTags || source.industryTags || [];
    const cooperationIntent = normalizeIntent(opportunity.cooperationIntent || source.cooperationIntent);
    const visibility = normalizeOpportunityVisibility(opportunity);
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
      businessOpportunity: {
        ...visibility,
        industry,
        subIndustry,
        industryTagsText: keywordText(industryTags),
        cooperationIntent
      },
      subIndustryOptions: industryChildren(industry),
      industryIndex: selectedIndex(INDUSTRY_OPTIONS, industry),
      subIndustryIndex: selectedIndex(industryChildren(industry), subIndustry),
      media: note.media || [],
      styleId: "business_blue",
      styleLabel: "标准专业",
      keywordChips: keywordList(structuredData.serviceKeywordsText),
      moreContactOpen: Boolean(this.data.profile.email || this.data.profile.website),
      loading: false,
      draftReady: true
    });
    this.hasLoadedOnce = true;
    this._shareNote = note;
    this.syncShareState(note);
    this.loadResourceOptions();
  },

  markShareDirty() {
    if (!this.data.draftReady) return;
    this.setData({
      shareDirty: true,
      shareImageReady: false,
      shareImageState: "stale",
      shareImageUrl: "",
      shareStatusText: "发布并准备分享"
    });
    setShareMenuEnabled(false);
  },

  syncShareState(note = {}) {
    const user = this.data.user || getCurrentUser() || {};
    const published = noteShareState(note) === "published";
    const current = published ? getNoteShareSnapshotState(note, user.id, user) : { status: "unavailable" };
    const imageUrl = published ? getShareImageUrlFromState(current) : "";
    const ready = Boolean(published && imageUrl);
    const statusText = ready
      ? "发客户"
      : published
        ? (current.status === "failed" ? "重试准备" : "准备分享")
        : "发布并准备分享";
    this.setData({
      shareImageReady: ready,
      shareImagePreparing: false,
      shareImageState: ready ? "ready" : current.status,
      shareImageUrl: imageUrl,
      shareStatusText: statusText,
      shareDirty: false
    });
    setShareMenuEnabled(ready);
    return { ...current, snapshotUrl: imageUrl };
  },

  async prepareDirectShare(note = this._shareNote || {}) {
    const user = this.data.user || getCurrentUser() || {};
    if (!note.id || noteShareState(note) !== "published") return false;
    const current = getNoteShareSnapshotState(note, user.id, user);
    const existingUrl = getShareImageUrlFromState(current);
    if (existingUrl) {
      this._shareNote = note;
      this.setData({
        shareImageReady: true,
        shareImagePreparing: false,
        shareImageState: "ready",
        shareImageUrl: existingUrl,
        shareStatusText: "发客户",
        shareDirty: false
      });
      setShareMenuEnabled(true);
      return true;
    }
    if (this.data.shareImagePreparing) return false;
    this.setData({
      shareImageReady: false,
      shareImagePreparing: true,
      shareImageState: "preparing",
      shareImageUrl: "",
      shareStatusText: "准备中",
      shareDirty: false
    });
    setShareMenuEnabled(false);
    try {
      const result = await prepareNoteShareSnapshot({
        note,
        ownerUserId: user.id,
        user
      });
      const savedNote = result.entity || note;
      const state = getNoteShareSnapshotState(savedNote, user.id, user);
      const imageUrl = getShareImageUrlFromState(state) || String((result.snapshot || {}).url || "").trim();
      if (!imageUrl) throw new Error("分享图地址为空");
      this._shareNote = savedNote;
      this.setData({
        shareImageReady: true,
        shareImagePreparing: false,
        shareImageState: "ready",
        shareImageUrl: imageUrl,
        shareStatusText: "发客户",
        shareDirty: false
      });
      setShareMenuEnabled(true);
      return true;
    } catch (error) {
      this.setData({
        shareImageReady: false,
        shareImagePreparing: false,
        shareImageState: "failed",
        shareImageUrl: "",
        shareStatusText: "重试准备",
        shareDirty: false
      });
      setShareMenuEnabled(false);
      return false;
    }
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
    this.markShareDirty();
    this.setData(update);
  },

  handleStructuredInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.detail.value || "";
    const update = { [`structuredData.${key}`]: value };
    if (key === "serviceKeywordsText") update.keywordChips = keywordList(value);
    this.markShareDirty();
    this.setData(update);
  },

  handleOpportunityInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.detail.value || "";
    this.markShareDirty();
    this.setData({ [`businessOpportunity.${key}`]: value });
  },

  handleIntentInput(event) {
    const value = event.detail.value || "";
    this.markShareDirty();
    this.setData({ "businessOpportunity.cooperationIntent.text": value });
  },

  handleIndustryChange(event) {
    const index = Number(event.detail.value || 0);
    const industry = INDUSTRY_OPTIONS[index] === "请选择行业" ? "" : INDUSTRY_OPTIONS[index];
    const options = industryChildren(industry);
    this.markShareDirty();
    this.setData({
      "businessOpportunity.industry": industry,
      "businessOpportunity.subIndustry": "",
      subIndustryOptions: options,
      industryIndex: index,
      subIndustryIndex: 0
    });
  },

  handleSubIndustryChange(event) {
    const index = Number(event.detail.value || 0);
    const subIndustry = this.data.subIndustryOptions[index] === "请选择细分行业" ? "" : this.data.subIndustryOptions[index];
    this.markShareDirty();
    this.setData({ "businessOpportunity.subIndustry": subIndustry, subIndustryIndex: index });
  },

  handleIntentDirectionChange(event) {
    const index = Number(event.detail.value || 0);
    this.markShareDirty();
    this.setData({ "businessOpportunity.cooperationIntent.direction": INTENT_DIRECTION_OPTIONS[index] || INTENT_DIRECTION_OPTIONS[0] });
  },

  handleIntentValidityChange(event) {
    const index = Number(event.detail.value || 0);
    this.markShareDirty();
    this.setData({ "businessOpportunity.cooperationIntent.validity": INTENT_VALIDITY_OPTIONS[index] || INTENT_VALIDITY_OPTIONS[0] });
  },

  handleToggleBusinessOpportunity(event) {
    const key = event && event.currentTarget && event.currentTarget.dataset && event.currentTarget.dataset.key;
    if (!["resourceEnabled", "intentEnabled"].includes(key)) return;
    this.opportunityChoiceTouched = true;
    this.markShareDirty();
    this.setData({ [`businessOpportunity.${key}`]: !this.data.businessOpportunity[key] });
  },

  handleSelectStyle(event) {
    const styleId = event.currentTarget.dataset.id || "business_blue";
    const styleLabel = event.currentTarget.dataset.label || (CARD_STYLES.find((item) => item.id === styleId) || {}).label || "标准专业";
    this.markShareDirty();
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
    this.markShareDirty();
    this.setData({ "structuredData.featuredNoteIds": selectedIds }, () => this.refreshFeaturedResources());
  },

  handleRemoveResource(event) {
    const id = event.currentTarget.dataset.id;
    const selectedIds = (this.data.structuredData.featuredNoteIds || []).filter((item) => item !== id);
    this.markShareDirty();
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
      this.markShareDirty();
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
    const rawKeywords = keywordList(this.data.structuredData.serviceKeywordsText, 100);
    if (!rawKeywords.length) return "请至少填写1项“我能提供”内容";
    if (rawKeywords.length > 6) return "服务关键词最多6个";
    const resourceEnabled = this.data.businessOpportunity.resourceEnabled === true;
    const intentEnabled = this.data.businessOpportunity.intentEnabled === true;
    if ((resourceEnabled || intentEnabled) && !clean(this.data.businessOpportunity.industry)) return "请选择所属行业";
    if (intentEnabled && !clean(this.data.businessOpportunity.cooperationIntent.text)) return "请填写当前合作需求";
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
      const industryTags = keywordList(this.data.businessOpportunity.industryTagsText, 8);
      const intent = normalizeIntent(this.data.businessOpportunity.cooperationIntent);
      const resourceEnabled = this.data.businessOpportunity.resourceEnabled === true;
      const intentEnabled = this.data.businessOpportunity.intentEnabled === true;
      const visibilityChoiceMade = Boolean(
        options.markVisibilityChoice
        || this.data.businessOpportunity.visibilityChoiceMade
        || this.opportunityChoiceTouched
      );
      const structuredData = {
        headline: clean(this.data.structuredData.headline),
        serviceKeywords: keywords,
        bio: clean(this.data.structuredData.bio),
        featuredNoteIds: (this.data.structuredData.featuredNoteIds || []).slice(0, 3),
        industry: clean(this.data.businessOpportunity.industry),
        subIndustry: clean(this.data.businessOpportunity.subIndustry),
        industryTags,
        cooperationIntent: {
          direction: intent.direction,
          text: intent.text,
          validity: intent.validity,
          expiresAt: buildIntentExpiry(intent.validity)
        }
      };
      const title = `${clean(this.data.profile.displayName)}的电子名片`;
      const visibilityConfig = {
        schemaVersion: 2,
        cardType: "business_card",
        cardState: "ready",
        structuredData,
        businessOpportunity: {
          enabled: resourceEnabled || intentEnabled,
          discoverable: resourceEnabled || intentEnabled,
          resourceEnabled,
          resourceDiscoverable: resourceEnabled,
          intentEnabled,
          intentDiscoverable: intentEnabled,
          ...(visibilityChoiceMade ? { visibilityChoiceVersion: 1 } : {}),
          industry: structuredData.industry,
          subIndustry: structuredData.subIndustry,
          industryTags,
          cooperationIntent: structuredData.cooperationIntent
        },
        displayConfig: { styleId: this.data.styleId },
        conversionConfig: {
          showContactPhone: Boolean(clean(this.data.profile.phone)),
          enablePrivateConsultation: Boolean(clean(this.data.profile.wechat) || clean(this.data.profile.wechatQrUrl)),
          collectLeads: true,
          enableAppointment: false,
          enableLightScrm: true
        }
      };
      const updateRes = await api.updateNote(this.data.noteId, {
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
      this._lastSavedRevision = updateRes && updateRes.data && Number.isFinite(Number(updateRes.data.revision))
        ? Number(updateRes.data.revision)
        : undefined;
      this._shareNote = (updateRes && updateRes.data) || {
        ...(this._shareNote || {}),
        id: this.data.noteId,
        title,
        summary: structuredData.headline,
        body: structuredData.bio || structuredData.headline,
        coverUrl: this.data.profile.avatarUrl,
        visibilityConfig,
        shareState: "private"
      };
      // The library may have painted a cached card while this editor was
      // open.  A saved card revision must invalidate that metadata snapshot
      // before the user returns to the share flow.
      resourceStore.invalidateOwner(this.data.user.id);
      wx.setStorageSync(businessCardStorageKey(this.data.user.id), this.data.noteId);
      this.setData({
        user,
        keywordChips: keywords,
        "businessOpportunity.enabled": resourceEnabled || intentEnabled,
        "businessOpportunity.visibilityChoiceMade": visibilityChoiceMade
      });
      if (visibilityChoiceMade) this.opportunityChoiceTouched = false;
      this.syncShareState(this._shareNote);
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

  async publishAndPrepareShare() {
    const expectedRevision = Number.isFinite(Number(this._lastSavedRevision))
      ? Number(this._lastSavedRevision)
      : this._shareNote && Number.isFinite(Number(this._shareNote.revision))
        ? Number(this._shareNote.revision)
      : undefined;
    const publishRes = await api.publishNote(this.data.noteId, this.data.user.id, expectedRevision);
    const publishedNote = (publishRes && publishRes.data) || {
      ...(this._shareNote || {}),
      id: this.data.noteId,
      shareState: "published"
    };
    this._shareNote = publishedNote;
    if (!this.data.businessOpportunity.visibilityChoiceMade) {
      this.setData({ completionPromptVisible: true });
      return false;
    }
    return this.prepareDirectShare(publishedNote);
  },

  async handlePublish() {
    if (!this.data.shareDirty && this._shareNote && noteShareState(this._shareNote) === "published") {
      this.setData({ saving: true });
      try {
        const ready = await this.prepareDirectShare(this._shareNote);
        wx.showToast({
          title: ready ? "已准备好，点击发客户" : "分享图准备失败，请重试",
          icon: ready ? "success" : "none"
        });
      } finally {
        this.setData({ saving: false });
      }
      return;
    }
    const saved = await this.handleSave({ silent: true });
    if (!saved) return;
    this.setData({ saving: true });
    try {
      const ready = await this.publishAndPrepareShare();
      if (this.data.completionPromptVisible) return;
      wx.showToast({
        title: ready ? "已准备好，点击发客户" : "分享图准备失败，请重试",
        icon: ready ? "success" : "none"
      });
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "发客户失败，请先完善名片", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },

  async saveCompletionChoice(update, successTitle) {
    if (this.data.saving) return;
    this.setData({ ...update, completionPromptVisible: false }, async () => {
      const saved = await this.handleSave({ silent: true, markVisibilityChoice: true });
      if (!saved) {
        this.setData({ completionPromptVisible: true });
        return;
      }
      this.setData({ saving: true });
      try {
        const ready = await this.publishAndPrepareShare();
        if (this.data.completionPromptVisible) return;
        wx.showToast({
          title: ready ? "已准备好，点击发客户" : `${successTitle}，分享图准备失败，请重试`,
          icon: ready ? "success" : "none"
        });
      } catch (error) {
        wx.showToast({ title: error.detail || error.message || "更新公开状态失败", icon: "none" });
        this.setData({ completionPromptVisible: true });
      } finally {
        this.setData({ saving: false });
      }
    });
  },

  handleChooseCompletionOption(event) {
    const key = event && event.currentTarget && event.currentTarget.dataset && event.currentTarget.dataset.key;
    const labels = {
      resourceEnabled: "已展示合作资源",
      intentEnabled: "已发布合作需求"
    };
    if (!labels[key]) return;
    if (!clean(this.data.businessOpportunity.industry)) {
      wx.showToast({ title: "请先选择所属行业", icon: "none" });
      this.setData({ completionPromptVisible: false });
      return;
    }
    if (key === "intentEnabled" && !clean(this.data.businessOpportunity.cooperationIntent.text)) {
      wx.showToast({ title: "请先填写当前合作需求", icon: "none" });
      this.setData({ completionPromptVisible: false });
      return;
    }
    this.saveCompletionChoice({ [`businessOpportunity.${key}`]: true }, labels[key]);
  },

  handleSkipCompletionChoice() {
    this.saveCompletionChoice({}, "名片已完成");
  },

  handleShareTap() {
    subscription.requestViewNotificationSubscription("business_card_editor_share");
  },

  onShareAppMessage() {
    const note = this._shareNote || {};
    const user = this.data.user || getCurrentUser() || {};
    const state = getNoteShareSnapshotState(note, user.id, user);
    const shareId = createShareId(this.data.noteId);
    const path = `/pages/note-preview/index?id=${encodeURIComponent(this.data.noteId)}&sid=${encodeURIComponent(shareId)}&from=${encodeURIComponent(user.id || "")}&src=business_card_editor_share`;
    const shareMessage = buildShareMessage({
      title: buildBusinessCardShareTitle(buildBusinessCardShareSource(note, user)),
      path,
      snapshot: state.snapshot,
      sourceRevision: state.sourceRevision,
      fingerprint: state.fingerprint,
      styleId: state.styleId,
      imageUrl: this.data.shareImageUrl || getShareImageUrlFromState(state)
    });
    if (!shareMessage) {
      this.setData({
        shareImageReady: false,
        shareImageState: "stale",
        shareImageUrl: "",
        shareStatusText: "重试准备"
      });
      setShareMenuEnabled(false);
      wx.showToast({ title: "资料分享图正在准备，请稍后再发", icon: "none" });
      return null;
    }
    if (this.data.noteId && user.id) {
      api.recordNoteView(this.data.noteId, {
        eventType: "share",
        viewerUserId: user.id,
        shareId,
        shareFromUserId: user.id,
        scene: "business_card_editor_share",
        referrer: "business_card_editor"
      }).catch(() => {});
    }
    return shareMessage;
  }
});
