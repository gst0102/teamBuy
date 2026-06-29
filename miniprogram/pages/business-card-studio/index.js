const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { getSalesPageTemplates, getSalesPageTemplate, templateToneClass } = require("../../utils/sales-page-templates");
const { buildBusinessCardShareTitle, generateBusinessCardShareImage } = require("../../utils/business-card-share");

const BUSINESS_CARD_STUDIO_SHARE_CANVAS_ID = "businessCardStudioShareCanvas";

const STEPS = [
  { key: "style", label: "选风格" },
  { key: "form", label: "填资料" },
  { key: "confirm", label: "确认效果" }
];

function defaultForm(user) {
  return {
    avatarUrl: user && user.avatarUrl || "",
    name: user && user.nickname || "",
    title: "专业顾问",
    company: "",
    phone: user && user.phone || "",
    wechat: "",
    email: "",
    website: "",
    city: "",
    address: "",
    headline: "用专业经验帮你少走弯路",
    serviceScope: "咨询服务 / 客户顾问 / 长期跟进",
    bio: "我会根据你的具体需求，提供清晰建议、及时沟通和持续跟进。",
    qrCodeUrl: "",
    images: []
  };
}

function splitScope(value) {
  const list = String(value || "")
    .split(/[\n,，、/|]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  return (list.length ? list : ["咨询服务", "客户顾问", "长期跟进"]).slice(0, 4);
}

function buildTemplates() {
  return getSalesPageTemplates("business_card").map((template) => ({
    ...template,
    toneClass: templateToneClass(template),
    preview: {
      ...(template.preview || {}),
      initial: String((template.preview && template.preview.title) || template.name || "名").slice(0, 1),
      avatarClass: (template.preview && template.preview.avatarClass) || "avatar-male avatar-suit-blue",
      avatarUrl: (template.preview && template.preview.avatarUrl) || ""
    }
  }));
}

function buildPreview(form, template) {
  const scopeTags = splitScope(form.serviceScope);
  const phone = String(form.phone || "").trim();
  const wechat = String(form.wechat || "").trim();
  const email = String(form.email || "").trim();
  const contactActions = [
    phone ? { key: "phone", icon: "电", label: "电话", value: phone } : null,
    wechat ? { key: "wechat", icon: "微", label: "微信", value: wechat } : null,
    email ? { key: "email", icon: "邮", label: "邮箱", value: email } : null,
    { key: "lead", icon: "留", label: "留言", value: "" }
  ].filter(Boolean);
  const name = form.name || "你的姓名";
  return {
    templateId: template.id,
    templateName: template.name,
    toneClass: templateToneClass(template),
    name,
    role: form.title || "个人顾问",
    company: form.company || "公司 / 门店",
    headline: form.headline || template.summary || "",
    avatarUrl: form.avatarUrl,
    initial: String(name || "名").slice(0, 1),
    contactLine: [phone, wechat, email].filter(Boolean).join(" · ") || "电话 / 微信 / 邮箱",
    serviceScope: form.serviceScope || "",
    scopeTags,
    intro: form.bio || "",
    phone,
    wechat,
    email,
    website: form.website || "",
    city: form.city || "",
    address: form.address || "",
    qrCodeUrl: form.qrCodeUrl || "",
    contactActions,
    actionCount: contactActions.length
  };
}

function buildPublishChecks(form) {
  const hasContact = Boolean(String(form.phone || form.wechat || form.email || "").trim());
  const hasIdentity = Boolean(String(form.name || "").trim() && String(form.title || "").trim());
  return [
    { key: "identity", status: hasIdentity ? "done" : "warn", label: "姓名和身份", desc: hasIdentity ? "客户能知道你是谁" : "建议补全姓名和职位/身份" },
    { key: "contact", status: hasContact ? "done" : "warn", label: "联系入口", desc: hasContact ? "电话、微信或邮箱已填写" : "至少填写电话、微信或邮箱" },
    { key: "intro", status: String(form.bio || form.headline || "").trim() ? "done" : "warn", label: "个人介绍", desc: "让客户知道你能提供什么帮助" },
    { key: "visual", status: (form.avatarUrl || form.qrCodeUrl) ? "done" : "todo", label: "头像/二维码", desc: (form.avatarUrl || form.qrCodeUrl) ? "客户页更像正式名片" : "可选，但建议发客户前补一张" }
  ];
}

function shouldUseTemplateDefault(currentValue, starterValue, previousValue) {
  const current = String(currentValue || "").trim();
  if (!current) return true;
  if (current === String(starterValue || "").trim()) return true;
  return Boolean(previousValue) && current === String(previousValue || "").trim();
}

function hydrateTemplateDefaults(form, template, previousTemplate) {
  const defaults = (template && template.defaults) || {};
  const previousDefaults = (previousTemplate && previousTemplate.defaults) || {};
  const starter = DEFAULT_BUSINESS_FORM || defaultForm(null);
  const next = { ...form };
  ["title", "company", "serviceScope", "headline", "bio", "city"].forEach((key) => {
    if (shouldUseTemplateDefault(next[key], starter[key], previousDefaults[key]) && defaults[key]) {
      next[key] = defaults[key];
    }
  });
  return {
    ...next,
    title: next.title || defaults.title || "",
    company: next.company || defaults.company || "",
    serviceScope: next.serviceScope || defaults.serviceScope || "",
    headline: next.headline || defaults.headline || "",
    bio: next.bio || defaults.bio || "",
    city: next.city || defaults.city || ""
  };
}

function forceTemplateDefaults(form, template) {
  const defaults = (template && template.defaults) || {};
  return {
    ...form,
    title: defaults.title || form.title,
    company: defaults.company || form.company,
    serviceScope: defaults.serviceScope || form.serviceScope,
    headline: defaults.headline || form.headline,
    bio: defaults.bio || form.bio,
    city: defaults.city || form.city
  };
}

function buildFormFromNote(note, user) {
  const config = (note && note.visibilityConfig) || {};
  const data = config.structuredData || {};
  const base = defaultForm(user);
  return {
    ...base,
    avatarUrl: data.avatarUrl || note.coverUrl || base.avatarUrl,
    name: data.name || note.title || base.name,
    title: data.title || base.title,
    company: data.company || base.company,
    phone: data.phone || note.phone || base.phone,
    wechat: data.wechat || data.contactWechat || base.wechat,
    email: data.email || data.mail || base.email,
    website: data.website || data.companyWebsite || data.websiteUrl || base.website,
    city: data.city || note.locationText || base.city,
    address: data.address || base.address,
    headline: data.headline || note.summary || base.headline,
    serviceScope: data.serviceScope || base.serviceScope,
    bio: data.bio || note.body || base.bio,
    qrCodeUrl: data.qrCodeUrl || data.qrcodeUrl || data.qrUrl || data.wechatQrCodeUrl || base.qrCodeUrl,
    images: Array.from(new Set([...(data.images || []), ...(note.media || []).map((item) => item && item.url)].filter(Boolean)))
  };
}

const DEFAULT_BUSINESS_FORM = defaultForm(null);
const INLINE_EDIT_FIELDS = {
  name: { label: "姓名", placeholder: "填写你的姓名或昵称" },
  title: { label: "身份/职位", placeholder: "例如：专业顾问" },
  company: { label: "公司/门店", placeholder: "选填" },
  headline: { label: "一句话介绍", placeholder: "客户一眼知道你能提供什么帮助" },
  bio: { label: "服务介绍", multiline: true, placeholder: "介绍你的服务、优势和适合客户" },
  serviceScope: { label: "服务范围", multiline: true, placeholder: "可用顿号、逗号或换行分隔" },
  phone: { label: "电话", placeholder: "填写客户可联系的电话" },
  wechat: { label: "微信", placeholder: "填写微信号" },
  email: { label: "邮箱", placeholder: "选填" },
  website: { label: "网址", placeholder: "选填，例如：https://example.com" }
};

Page({
  data: {
    user: null,
    steps: STEPS,
    activeStep: "style",
    templates: [],
    templateViewMode: "list",
    selectedTemplateId: "consultant_classic",
    selectedTemplate: null,
    form: DEFAULT_BUSINESS_FORM,
    preview: null,
    previewMode: "card",
    existingVisibilityConfig: null,
    existingNoteTitle: "",
    existingNoteSummary: "",
    loadedNoteId: "",
    hasUnsavedChanges: false,
    shareImage: "",
    saving: false,
    uploadingField: "",
    savedNoteId: "",
    inlineEditor: {
      open: false,
      key: "",
      label: "",
      value: "",
      multiline: false,
      placeholder: ""
    },
    publishChecks: buildPublishChecks(DEFAULT_BUSINESS_FORM)
  },
  onLoad(options = {}) {
    const noteId = options.id || options.noteId || "";
    if (noteId) {
      this.setData({
        savedNoteId: noteId,
        activeStep: "confirm"
      });
    }
    this.pendingNoteId = noteId;
  },
  async onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const templates = buildTemplates();
    if (this.pendingNoteId && this.data.loadedNoteId !== this.pendingNoteId) {
      await this.loadExistingNote(this.pendingNoteId, user, templates);
      return;
    }
    const selectedTemplate = getSalesPageTemplate(this.data.selectedTemplateId) || templates[0];
    const form = this.data.user ? this.data.form : hydrateTemplateDefaults(defaultForm(user), selectedTemplate);
    this.setData({
      user,
      templates,
      selectedTemplate,
      form,
      preview: buildPreview(form, selectedTemplate),
      publishChecks: buildPublishChecks(form),
      hasUnsavedChanges: false
    }, () => this.updateShareMenu());
  },
  async loadExistingNote(noteId, user, templates) {
    wx.showLoading({ title: "读取名片" });
    try {
      const res = await api.fetchNote(noteId, user.id);
      const note = res.data || {};
      const config = note.visibilityConfig || {};
      const template = getSalesPageTemplate(config.displayTemplate || this.data.selectedTemplateId);
      const form = buildFormFromNote(note, user);
      this.setData({
        user,
        templates,
        savedNoteId: noteId,
        loadedNoteId: noteId,
        existingVisibilityConfig: config,
        existingNoteTitle: note.title || form.name || "电子名片",
        existingNoteSummary: note.summary || form.headline || "",
        selectedTemplateId: template.id,
        selectedTemplate: template,
        form,
        preview: buildPreview(form, template),
        publishChecks: buildPublishChecks(form),
        activeStep: "confirm",
        hasUnsavedChanges: false
      }, () => this.updateShareMenu());
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "读取名片失败", icon: "none" });
    } finally {
      wx.hideLoading();
    }
  },
  setStep(step) {
    this.setData({ activeStep: step });
  },
  handleStepTap(event) {
    const step = event.currentTarget.dataset.step;
    if (step) this.setStep(step);
  },
  noop() {},
  async handleSelectTemplate(event) {
    const id = event.currentTarget.dataset.id;
    const template = getSalesPageTemplate(id);
    if (!template) return;
    let form = hydrateTemplateDefaults(this.data.form, template, this.data.selectedTemplate);
    if (this.data.hasUnsavedChanges && this.data.selectedTemplateId !== id) {
      const mode = await new Promise((resolve) => {
        wx.showActionSheet({
          itemList: ["保留我的内容", "套用模板文案"],
          success: (res) => resolve(res.tapIndex === 1 ? "template" : "keep"),
          fail: () => resolve("keep")
        });
      });
      if (mode === "template") {
        form = forceTemplateDefaults(this.data.form, template);
      }
    }
    this.setData({
      selectedTemplateId: id,
      selectedTemplate: template,
      form,
      preview: buildPreview(form, template),
      publishChecks: buildPublishChecks(form),
      hasUnsavedChanges: true
    }, () => this.updateShareMenu());
  },
  handleTemplateViewMode(event) {
    const mode = event.currentTarget.dataset.mode;
    if (["list", "grid"].includes(mode)) {
      this.setData({ templateViewMode: mode });
    }
  },
  handlePreviewMode(event) {
    const mode = event.currentTarget.dataset.mode;
    if (["card", "detail"].includes(mode)) {
      this.setData({ previewMode: mode });
    }
  },
  handleInput(event) {
    const key = event.currentTarget.dataset.key;
    if (!key) return;
    const form = { ...this.data.form, [key]: event.detail.value };
    this.setData({
      form,
      preview: buildPreview(form, this.data.selectedTemplate),
      publishChecks: buildPublishChecks(form),
      hasUnsavedChanges: true
    }, () => this.updateShareMenu());
  },
  handleOpenInlineEditor(event) {
    const key = event.currentTarget.dataset.key;
    const config = INLINE_EDIT_FIELDS[key];
    if (!key || !config) return;
    this.setData({
      inlineEditor: {
        open: true,
        key,
        label: config.label,
        value: this.data.form[key] || "",
        multiline: Boolean(config.multiline),
        placeholder: config.placeholder || ""
      }
    });
  },
  handleInlineEditorInput(event) {
    this.setData({
      inlineEditor: {
        ...this.data.inlineEditor,
        value: event.detail.value
      }
    });
  },
  handleCloseInlineEditor() {
    this.setData({
      inlineEditor: {
        open: false,
        key: "",
        label: "",
        value: "",
        multiline: false,
        placeholder: ""
      }
    });
  },
  handleSaveInlineEditor() {
    const editor = this.data.inlineEditor || {};
    if (!editor.key) return;
    const form = {
      ...this.data.form,
      [editor.key]: editor.value
    };
    this.setData({
      form,
      preview: buildPreview(form, this.data.selectedTemplate),
      publishChecks: buildPublishChecks(form),
      hasUnsavedChanges: true,
      inlineEditor: {
        open: false,
        key: "",
        label: "",
        value: "",
        multiline: false,
        placeholder: ""
      }
    }, () => this.updateShareMenu());
  },
  handleNext() {
    if (this.data.activeStep === "style") {
      this.setStep("form");
      return;
    }
    if (this.data.activeStep === "form") {
      this.setStep("confirm");
    }
  },
  handleBackStep() {
    if (this.data.activeStep === "confirm") {
      this.setStep("form");
      return;
    }
    if (this.data.activeStep === "form") {
      this.setStep("style");
      return;
    }
    wx.navigateBack();
  },
  chooseImage(event) {
    const field = event.currentTarget.dataset.field;
    if (!["avatarUrl", "qrCodeUrl"].includes(field) || this.data.uploadingField) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      success: ({ tempFiles = [] }) => {
        const file = tempFiles[0];
        if (file && file.tempFilePath) this.uploadImage(field, file.tempFilePath);
      }
    });
  },
  handleChooseAvatar() {
    this.chooseImage({ currentTarget: { dataset: { field: "avatarUrl" } } });
  },
  handleChooseQrCode() {
    this.chooseImage({ currentTarget: { dataset: { field: "qrCodeUrl" } } });
  },
  async uploadImage(field, filePath) {
    const user = this.data.user;
    if (!user) return;
    this.setData({ uploadingField: field });
    try {
      const uploaded = await api.uploadAsset({
        filePath,
        mediaType: "image",
        ownerUserId: user.id
      });
      const url = uploaded.url || uploaded.displayUrl || "";
      if (!url) {
        wx.showToast({ title: "图片上传失败", icon: "none" });
        return;
      }
      const images = Array.from(new Set([...(this.data.form.images || []), url]));
      const form = {
        ...this.data.form,
        [field]: url,
        images
      };
      this.setData({
        form,
        preview: buildPreview(form, this.data.selectedTemplate),
        publishChecks: buildPublishChecks(form),
        hasUnsavedChanges: true
      }, () => this.updateShareMenu());
      wx.showToast({ title: field === "avatarUrl" ? "头像已上传" : "二维码已上传", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "上传失败", icon: "none" });
    } finally {
      this.setData({ uploadingField: "" });
    }
  },
  validateForm() {
    const form = this.data.form;
    if (!String(form.name || "").trim()) return "请填写姓名";
    if (!String(form.title || "").trim()) return "请填写职位/身份";
    if (!String(form.phone || form.wechat || form.email || "").trim()) return "电话、微信、邮箱至少填写一个";
    return "";
  },
  buildNotePayload() {
    const form = this.data.form;
    const template = this.data.selectedTemplate;
    const currentConfig = this.data.existingVisibilityConfig || {};
    const currentConversion = currentConfig.conversionConfig || {};
    const structuredData = {
      name: form.name,
      title: form.title,
      company: form.company,
      phone: form.phone,
      wechat: form.wechat,
      email: form.email,
      website: form.website,
      city: form.city,
      address: form.address,
      headline: form.headline,
      serviceScope: form.serviceScope,
      bio: form.bio,
      avatarUrl: form.avatarUrl,
      qrCodeUrl: form.qrCodeUrl,
      images: Array.from(new Set([form.avatarUrl, form.qrCodeUrl, ...(form.images || [])].filter(Boolean))),
      rawText: form.bio
    };
    return {
      title: form.name || template.title || "电子名片",
      summary: form.headline || template.summary || "",
      body: form.bio || form.headline || "电子名片",
      coverUrl: form.avatarUrl || form.qrCodeUrl || "",
      media: structuredData.images.map((url, index) => ({ type: "image", url, displayUrl: url, sortOrder: index + 1 })),
      categoryIds: [],
      phone: form.phone || "",
      locationText: form.city || form.address || "",
      visibilityConfig: {
        ...currentConfig,
        cardType: "business_card",
        cardState: "generated",
        sourceType: "business_card_studio",
        systemCategory: "名片",
        displayTemplate: template.id,
        displayTemplateName: template.name,
        displayTemplateScene: template.scene,
        displayTemplateTone: template.tone,
        tags: ["名片", "顾问"],
        structuredData,
        conversionConfig: {
          ...currentConversion,
          showContactPhone: Boolean(form.phone),
          enableLightScrm: true,
          collectLeads: true,
          enableAppointment: false,
          enablePrivateConsultation: Boolean(form.wechat),
          enableSharePoster: true,
          enableGroupRelay: false,
          enablePaymentPlaceholder: false
        }
      }
    };
  },
  async saveCard(openPreview = false) {
    const error = this.validateForm();
    if (error) {
      wx.showToast({ title: error, icon: "none" });
      this.setStep("form");
      return;
    }
    const user = this.data.user;
    if (!user || this.data.saving) return;
    this.setData({ saving: true });
    wx.showLoading({ title: "保存中" });
    try {
      let noteId = this.data.savedNoteId;
      if (!noteId) {
        const created = await api.createManualNoteDraft({
          ownerUserId: user.id,
          cardType: "business_card",
          inputMode: "blank",
          rawText: "",
          title: this.data.form.name || "电子名片"
        });
        noteId = created.data && created.data.id;
      }
      const payload = this.buildNotePayload();
      const updated = await api.updateNote(noteId, {
        ownerUserId: user.id,
        ...payload
      });
      const finalId = (updated.data && updated.data.id) || noteId;
      this.setData({
        savedNoteId: finalId,
        loadedNoteId: finalId,
        existingVisibilityConfig: payload.visibilityConfig,
        existingNoteTitle: payload.title,
        existingNoteSummary: payload.summary,
        hasUnsavedChanges: false
      }, () => this.updateShareMenu());
      wx.hideLoading();
      wx.showToast({ title: "名片已保存", icon: "success" });
      if (openPreview) {
        setTimeout(() => wx.navigateTo({ url: `/pages/note-preview/index?id=${finalId}` }), 350);
      }
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: err.detail || err.message || "保存失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  handleSave() {
    this.saveCard(false);
  },
  handleSavePreview() {
    this.saveCard(true);
  },
  updateShareMenu() {
    const ready = Boolean(this.data.savedNoteId && !this.data.hasUnsavedChanges);
    const fn = ready ? wx.showShareMenu : wx.hideShareMenu;
    if (typeof fn === "function") {
      fn({ menus: ["shareAppMessage", "shareTimeline"] });
    }
    if (ready) {
      this.ensureShareImage();
    } else {
      this.setData({ shareImage: "" });
    }
  },
  async ensureShareImage() {
    if (this.data.shareImage || !this.data.preview) return this.data.shareImage || "";
    try {
      const imagePath = await generateBusinessCardShareImage(this, BUSINESS_CARD_STUDIO_SHARE_CANVAS_ID, this.data.preview);
      if (imagePath) {
        this.setData({ shareImage: imagePath });
        return imagePath;
      }
    } catch (error) {}
    return "";
  },
  handleOpenSavedPreview() {
    if (!this.data.savedNoteId) {
      this.handleSavePreview();
      return;
    }
    wx.navigateTo({ url: `/pages/note-preview/index?id=${this.data.savedNoteId}` });
  },
  onShareAppMessage() {
    const id = this.data.savedNoteId;
    const preview = this.data.preview || {};
    return {
      title: buildBusinessCardShareTitle(preview),
      path: id ? `/pages/note-preview/index?id=${id}` : "/pages/business-card-studio/index",
      imageUrl: this.data.shareImage || ""
    };
  }
});
