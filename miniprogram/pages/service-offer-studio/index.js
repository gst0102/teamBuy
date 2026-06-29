const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { getSalesPageTemplates, getSalesPageTemplate, templateToneClass } = require("../../utils/sales-page-templates");
const { buildServiceOfferShareTitle, generateServiceOfferShareImage } = require("../../utils/business-card-share");

const SERVICE_OFFER_STUDIO_SHARE_CANVAS_ID = "serviceOfferStudioShareCanvas";

const STEPS = [
  { key: "style", label: "选模板" },
  { key: "form", label: "填资料" },
  { key: "confirm", label: "确认效果" }
];

function defaultForm(user) {
  return {
    serviceName: "一对一咨询服务",
    headline: "先沟通需求，再给你清晰建议",
    targetAudience: "适合有明确问题、需要专业建议或长期陪跑的客户",
    serviceContent: "需求梳理、问题分析、方案建议、后续跟进",
    pricingNote: "按服务内容和服务周期报价",
    serviceProcess: "提交需求 - 预约沟通 - 输出建议 - 后续跟进",
    caseHighlights: "可补充过往案例、客户反馈或服务成果",
    serviceArea: "线上 / 本地均可",
    phone: (user && user.phone) || "",
    wechat: "",
    email: "",
    website: "",
    appointmentNote: "建议提前一天预约沟通时间",
    primaryAction: "电话咨询",
    secondaryAction: "微信咨询",
    coverUrl: "",
    images: []
  };
}

function splitText(value, fallback, limit = 4) {
  const list = String(value || "")
    .split(/[\n,，、/|]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  return (list.length ? list : fallback).slice(0, limit);
}

function buildTemplates() {
  return getSalesPageTemplates("service_offer").map((template) => ({
    ...template,
    toneClass: templateToneClass(template)
  }));
}

function shouldUseTemplateDefault(currentValue, starterValue, previousValue) {
  const current = String(currentValue || "").trim();
  if (!current) return true;
  if (current === String(starterValue || "").trim()) return true;
  return Boolean(previousValue) && current === String(previousValue || "").trim();
}

function hydrateTemplateDefaults(form, template, previousTemplate) {
  const defaults = (template && template.defaults) || {};
  const preview = (template && template.preview) || {};
  const previousDefaults = (previousTemplate && previousTemplate.defaults) || {};
  const starter = DEFAULT_SERVICE_FORM || defaultForm(null);
  const next = { ...form };
  [
    "serviceName",
    "headline",
    "targetAudience",
    "serviceContent",
    "pricingNote",
    "serviceProcess",
    "caseHighlights",
    "serviceArea",
    "appointmentNote",
    "primaryAction",
    "secondaryAction"
  ].forEach((key) => {
    if (shouldUseTemplateDefault(next[key], starter[key], previousDefaults[key]) && defaults[key]) {
      next[key] = defaults[key];
    }
  });
  return {
    ...next,
    serviceName: next.serviceName || defaults.serviceName || "",
    headline: next.headline || defaults.headline || "",
    targetAudience: next.targetAudience || defaults.targetAudience || "",
    serviceContent: next.serviceContent || defaults.serviceContent || "",
    pricingNote: next.pricingNote || defaults.pricingNote || "",
    serviceProcess: next.serviceProcess || defaults.serviceProcess || "",
    caseHighlights: next.caseHighlights || defaults.caseHighlights || "",
    serviceArea: next.serviceArea || defaults.serviceArea || "",
    appointmentNote: next.appointmentNote || defaults.appointmentNote || "",
    primaryAction: next.primaryAction || preview.primaryAction || "电话咨询",
    secondaryAction: next.secondaryAction || preview.secondaryAction || "微信咨询"
  };
}

function forceTemplateDefaults(form, template) {
  const defaults = (template && template.defaults) || {};
  const preview = (template && template.preview) || {};
  return {
    ...form,
    serviceName: defaults.serviceName || form.serviceName,
    headline: defaults.headline || form.headline,
    targetAudience: defaults.targetAudience || form.targetAudience,
    serviceContent: defaults.serviceContent || form.serviceContent,
    pricingNote: defaults.pricingNote || form.pricingNote,
    serviceProcess: defaults.serviceProcess || form.serviceProcess,
    caseHighlights: defaults.caseHighlights || form.caseHighlights,
    serviceArea: defaults.serviceArea || form.serviceArea,
    appointmentNote: defaults.appointmentNote || form.appointmentNote,
    primaryAction: preview.primaryAction || form.primaryAction,
    secondaryAction: preview.secondaryAction || form.secondaryAction
  };
}

function buildFormFromNote(note, user) {
  const config = (note && note.visibilityConfig) || {};
  const data = config.structuredData || {};
  const base = defaultForm(user);
  const mediaImages = Array.isArray(note.media)
    ? note.media.filter((item) => item && item.type === "image").map((item) => item.url)
    : [];
  const images = Array.from(new Set([...(data.images || []), ...mediaImages].filter(Boolean)));
  return {
    ...base,
    serviceName: data.serviceName || note.title || base.serviceName,
    headline: data.headline || note.summary || base.headline,
    targetAudience: data.targetAudience || base.targetAudience,
    serviceContent: data.serviceContent || note.body || base.serviceContent,
    pricingNote: data.pricingNote || base.pricingNote,
    serviceProcess: data.serviceProcess || base.serviceProcess,
    caseHighlights: data.caseHighlights || base.caseHighlights,
    serviceArea: data.serviceArea || note.locationText || base.serviceArea,
    phone: data.phone || data.contactPhone || note.phone || data.contact || base.phone,
    wechat: data.wechat || data.contactWechat || base.wechat,
    email: data.email || data.mail || base.email,
    website: data.website || data.companyWebsite || data.websiteUrl || base.website,
    appointmentNote: data.appointmentNote || base.appointmentNote,
    primaryAction: data.primaryAction || base.primaryAction,
    secondaryAction: data.secondaryAction || base.secondaryAction,
    coverUrl: data.coverUrl || note.coverUrl || images[0] || "",
    images
  };
}

function buildMetricCards(templateId, audienceBullets, serviceBullets, processSteps, contactCount) {
  if (templateId === "service_pricing") {
    return [
      { value: `${serviceBullets.length}项`, label: "服务范围" },
      { value: `${processSteps.length}步`, label: "交付流程" },
      { value: `${contactCount}种`, label: "联系渠道" }
    ];
  }
  if (templateId === "service_campaign") {
    return [
      { value: `${audienceBullets.length}类`, label: "适合人群" },
      { value: `${processSteps.length}步`, label: "报名流程" },
      { value: `${contactCount}种`, label: "报名方式" }
    ];
  }
  if (templateId === "service_business_opportunity") {
    return [
      { value: `${audienceBullets.length}类`, label: "适合对象" },
      { value: `${serviceBullets.length}项`, label: "合作重点" },
      { value: `${contactCount}种`, label: "咨询方式" }
    ];
  }
  if (templateId === "service_case_story") {
    return [
      { value: `${serviceBullets.length}项`, label: "服务亮点" },
      { value: `${Math.max(1, audienceBullets.length)}类`, label: "适合客户" },
      { value: `${Math.max(1, processSteps.length)}步`, label: "服务路径" }
    ];
  }
  return [
    { value: `${audienceBullets.length}类`, label: "适合人群" },
    { value: `${serviceBullets.length}项`, label: "服务内容" },
    { value: `${contactCount}种`, label: "联系渠道" }
  ];
}

function buildPreview(form, template) {
  const safeTemplate = template || getSalesPageTemplate("service_consultation") || {};
  const templatePreview = safeTemplate.preview || {};
  const safeForm = form || defaultForm(null);
  const phone = String(safeForm.phone || "").trim();
  const wechat = String(safeForm.wechat || "").trim();
  const email = String(safeForm.email || "").trim();
  const contactCount = Math.max(1, [phone, wechat, email].filter(Boolean).length);
  const templateCoverUrl = templatePreview.coverUrl || "";
  const templateCaseImageUrls = Array.isArray(templatePreview.caseImageUrls) ? templatePreview.caseImageUrls.filter(Boolean) : [];
  const uploadedImages = Array.from(new Set((safeForm.images || []).filter(Boolean)));
  const coverUrl = safeForm.coverUrl || uploadedImages[0] || templateCoverUrl || "";
  const images = Array.from(new Set([coverUrl, ...uploadedImages].filter(Boolean)));
  const caseImages = Array.from(new Set([
    ...uploadedImages.filter((item) => item !== coverUrl),
    ...templateCaseImageUrls,
    safeTemplate.id === "service_case_story" && coverUrl ? coverUrl : ""
  ].filter(Boolean))).slice(0, 3);
  const audienceBullets = splitText(
    safeForm.targetAudience,
    templatePreview.bullets || ["适合有明确问题、想获得专业建议的客户"],
    3
  );
  const serviceBullets = splitText(
    safeForm.serviceContent,
    templatePreview.serviceItems || ["需求梳理", "方案建议", "后续跟进"],
    4
  );
  const processSteps = splitText(
    safeForm.serviceProcess,
    ["提交需求", "预约沟通", "输出建议", "后续跟进"],
    4
  );
  const caseBullets = splitText(
    safeForm.caseHighlights,
    templatePreview.caseLabels || ["案例成果", "客户反馈", "服务保障"],
    3
  );
  const pricingTags = splitText(
    safeForm.pricingNote,
    templatePreview.quoteTags || ["按项目报价", "按阶段报价", "定制方案"],
    3
  );
  const supportChips = Array.from(new Set([
    ...(templatePreview.chips || []),
    safeForm.serviceArea ? safeForm.serviceArea : "",
    safeForm.appointmentNote ? safeForm.appointmentNote : ""
  ].filter(Boolean))).slice(0, 4);
  const primaryAction = safeForm.primaryAction || templatePreview.primaryAction || "电话咨询";
  const secondaryAction = safeForm.secondaryAction || templatePreview.secondaryAction || "微信咨询";
  const actionTiles = [
    phone ? { key: "phone", icon: "电话", label: primaryAction, editKey: "primaryAction" } : null,
    wechat ? { key: "wechat", icon: "微信", label: secondaryAction, editKey: "secondaryAction" } : null,
    { key: "lead", icon: "留言", label: "留下电话/微信" },
    { key: "appointment", icon: "预约", label: "预约沟通" }
  ].filter(Boolean).slice(0, 4);
  const metricCards = buildMetricCards(
    safeTemplate.id,
    audienceBullets,
    serviceBullets,
    processSteps,
    contactCount
  );

  return {
    templateId: safeTemplate.id || "service_consultation",
    templateName: safeTemplate.name || "咨询预约",
    templateScene: safeTemplate.scene || "咨询预约",
    toneClass: templateToneClass(safeTemplate),
    mockType: templatePreview.mockType || "consultation",
    serviceName: safeForm.serviceName || safeTemplate.title || "服务方案",
    headline: safeForm.headline || safeTemplate.summary || "",
    audienceBullets,
    serviceBullets,
    processSteps,
    caseBullets,
    pricingTags,
    pricingNote: safeForm.pricingNote || "按需求沟通报价",
    serviceArea: safeForm.serviceArea || "",
    appointmentNote: safeForm.appointmentNote || "",
    phone,
    wechat,
    email,
    website: safeForm.website || "",
    coverUrl,
    images,
    caseImages,
    heroAvatarUrl: templatePreview.avatarUrl || "",
    supportChips,
    sections: (templatePreview.sections || []).slice(0, 3),
    serviceItems: serviceBullets.slice(0, 4),
    metricItems: metricCards,
    countdown: (templatePreview.countdown || []).slice(0, 4),
    countdownLabels: (templatePreview.countdownLabels || []).slice(0, 4),
    primaryAction,
    secondaryAction,
    featureHighlights: (safeTemplate.features || []).slice(0, 4),
    actionTiles,
    metricCards
  };
}

function buildPublishChecks(form) {
  const hasContact = Boolean(String(form.phone || form.wechat || form.email || "").trim());
  return [
    { key: "name", status: String(form.serviceName || "").trim() ? "done" : "warn", label: "服务名称", desc: "客户能知道你提供什么服务" },
    { key: "content", status: String(form.serviceContent || "").trim() ? "done" : "warn", label: "服务内容", desc: "说明服务包含什么、怎么交付" },
    { key: "lead", status: "done", label: "留言/预约", desc: "客户页已开启留言和预约沟通" },
    { key: "contact", status: hasContact ? "done" : "todo", label: "直接联系", desc: hasContact ? "电话、微信或邮箱已填写" : "可选，建议补一个直接联系入口" },
    { key: "visual", status: form.coverUrl || (form.images || []).length ? "done" : "todo", label: "封面/案例图", desc: form.coverUrl || (form.images || []).length ? "客户页更完整" : "可选，发客户前建议补图" }
  ];
}

function safeShowLoading(title) {
  if (typeof wx !== "undefined" && typeof wx.showLoading === "function") {
    wx.showLoading({ title });
  }
}

function safeHideLoading() {
  if (typeof wx !== "undefined" && typeof wx.hideLoading === "function") {
    wx.hideLoading();
  }
}

function safeShowToast(options) {
  if (typeof wx !== "undefined" && typeof wx.showToast === "function") {
    wx.showToast(options);
  }
}

const DEFAULT_SERVICE_TEMPLATE = getSalesPageTemplate("service_consultation");
const DEFAULT_SERVICE_FORM = defaultForm(null);
const DEFAULT_SERVICE_PREVIEW = buildPreview(DEFAULT_SERVICE_FORM, DEFAULT_SERVICE_TEMPLATE);

const INLINE_EDIT_FIELDS = {
  serviceName: { label: "服务名称", placeholder: "例如：一对一咨询服务" },
  headline: { label: "一句话卖点", placeholder: "客户一眼看到你能帮他解决什么" },
  targetAudience: { label: "适合人群", multiline: true, placeholder: "可用顿号、逗号或换行分隔" },
  serviceContent: { label: "服务内容", multiline: true, placeholder: "可用顿号、逗号或换行分隔" },
  serviceProcess: { label: "服务流程", multiline: true, placeholder: "例如：提交需求 - 预约沟通 - 输出建议" },
  pricingNote: { label: "报价说明", multiline: true, placeholder: "例如：按服务范围、周期和交付内容报价" },
  caseHighlights: { label: "案例/成果", multiline: true, placeholder: "可写案例成果、客户反馈或服务保障" },
  phone: { label: "电话", placeholder: "填写客户可联系的电话" },
  wechat: { label: "微信", placeholder: "填写微信号" },
  email: { label: "邮箱", placeholder: "选填" },
  website: { label: "网址", placeholder: "选填，例如：https://example.com" },
  appointmentNote: { label: "预约说明", multiline: true, placeholder: "例如：建议提前一天预约沟通时间" },
  primaryAction: { label: "主按钮文案", placeholder: "例如：电话咨询" },
  secondaryAction: { label: "微信按钮文案", placeholder: "例如：微信咨询" }
};

Page({
  data: {
    user: null,
    steps: STEPS,
    activeStep: "style",
    templates: [],
    selectedTemplateId: "service_consultation",
    selectedTemplate: DEFAULT_SERVICE_TEMPLATE,
    form: DEFAULT_SERVICE_FORM,
    preview: DEFAULT_SERVICE_PREVIEW,
    existingVisibilityConfig: null,
    existingNoteTitle: "",
    existingNoteSummary: "",
    loadedNoteId: "",
    savedNoteId: "",
    pageError: "",
    hasUnsavedChanges: false,
    shareImage: "",
    saving: false,
    uploadingField: "",
    inlineEditor: {
      open: false,
      key: "",
      label: "",
      value: "",
      multiline: false,
      placeholder: ""
    },
    publishChecks: buildPublishChecks(DEFAULT_SERVICE_FORM)
  },

  onLoad(options = {}) {
    if (options.template) {
      this.setData({ selectedTemplateId: options.template });
    }
    const noteId = options.id || options.noteId || "";
    if (noteId) {
      this.setData({ savedNoteId: noteId, activeStep: "confirm" });
    }
    this.pendingNoteId = noteId;
  },

  async onShow() {
    try {
      const user = getCurrentUser();
      if (!user) {
        this.setData({ pageError: "请先登录后再创建服务方案" });
        return;
      }
      const templates = buildTemplates();
      if (!templates.length) {
        this.setData({ pageError: "服务方案模板加载失败" });
        return;
      }
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
        pageError: "",
        hasUnsavedChanges: false
      }, () => this.updateShareMenu());
    } catch (error) {
      this.setData({
        pageError: (error && (error.detail || error.message)) || "服务方案加载失败",
        templates: this.data.templates.length ? this.data.templates : buildTemplates(),
        selectedTemplate: this.data.selectedTemplate || DEFAULT_SERVICE_TEMPLATE,
        form: this.data.form || DEFAULT_SERVICE_FORM,
        preview: this.data.preview || DEFAULT_SERVICE_PREVIEW,
        publishChecks: buildPublishChecks(this.data.form || DEFAULT_SERVICE_FORM)
      });
    }
  },

  async loadExistingNote(noteId, user, templates) {
    safeShowLoading("读取方案");
    try {
      const res = await api.fetchNote(noteId, user.id);
      const note = res.data || {};
      const config = note.visibilityConfig || {};
      const template = getSalesPageTemplate(config.displayTemplate || this.data.selectedTemplateId) || templates[0];
      const form = buildFormFromNote(note, user);
      this.setData({
        user,
        templates,
        savedNoteId: noteId,
        loadedNoteId: noteId,
        existingVisibilityConfig: config,
        existingNoteTitle: note.title || form.serviceName || "服务方案",
        existingNoteSummary: note.summary || form.headline || "",
        selectedTemplateId: template.id,
        selectedTemplate: template,
        form,
        preview: buildPreview(form, template),
        publishChecks: buildPublishChecks(form),
        activeStep: "confirm",
        hasUnsavedChanges: false,
        pageError: ""
      }, () => this.updateShareMenu());
    } catch (error) {
      this.setData({ pageError: error.detail || error.message || "读取方案失败" });
      safeShowToast({ title: error.detail || error.message || "读取方案失败", icon: "none" });
    } finally {
      safeHideLoading();
    }
  },

  handleRetryLoad() {
    this.setData({ pageError: "" });
    this.onShow();
  },

  handleGoLogin() {
    wx.reLaunch({ url: "/pages/login/index" });
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
    if (!template || template.cardType !== "service_offer") return;
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
    if (!["coverUrl", "caseImage"].includes(field) || this.data.uploadingField) return;
    const onChoose = ({ tempFiles = [] }) => {
      const file = tempFiles[0];
      const filePath = file && (file.tempFilePath || file.path);
      if (filePath) this.uploadImage(field, filePath);
    };
    if (typeof wx.chooseMedia === "function") {
      wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sourceType: ["album", "camera"],
        success: onChoose
      });
      return;
    }
    if (typeof wx.chooseImage === "function") {
      wx.chooseImage({
        count: 1,
        sourceType: ["album", "camera"],
        success: ({ tempFilePaths = [] }) => {
          const filePath = tempFilePaths[0];
          if (filePath) this.uploadImage(field, filePath);
        }
      });
      return;
    }
    safeShowToast({ title: "当前版本不支持选择图片", icon: "none" });
  },

  handleChooseCoverImage() {
    this.chooseImage({ currentTarget: { dataset: { field: "coverUrl" } } });
  },

  handleChooseCaseImage() {
    this.chooseImage({ currentTarget: { dataset: { field: "caseImage" } } });
  },

  async uploadImage(field, filePath) {
    const user = this.data.user;
    if (!user) return;
    this.setData({ uploadingField: field });
    try {
      const uploaded = await api.uploadAsset({ filePath, mediaType: "image", ownerUserId: user.id });
      const url = uploaded.url || uploaded.displayUrl || "";
      if (!url) {
        safeShowToast({ title: "图片上传失败", icon: "none" });
        return;
      }
      const images = Array.from(new Set([...(this.data.form.images || []), url]));
      const form = {
        ...this.data.form,
        coverUrl: field === "coverUrl" ? url : (this.data.form.coverUrl || url),
        images
      };
      this.setData({
        form,
        preview: buildPreview(form, this.data.selectedTemplate),
        publishChecks: buildPublishChecks(form),
        hasUnsavedChanges: true
      }, () => this.updateShareMenu());
      safeShowToast({ title: field === "coverUrl" ? "封面已上传" : "案例图已上传", icon: "success" });
    } catch (error) {
      safeShowToast({ title: error.detail || error.errMsg || "上传失败", icon: "none" });
    } finally {
      this.setData({ uploadingField: "" });
    }
  },

  validateForm() {
    const form = this.data.form;
    if (!String(form.serviceName || "").trim()) return "请填写服务名称";
    if (!String(form.headline || "").trim()) return "请填写一句话卖点";
    if (!String(form.serviceContent || "").trim()) return "请填写服务内容";
    return "";
  },

  buildNotePayload() {
    const form = this.data.form;
    const template = this.data.selectedTemplate;
    const currentConfig = this.data.existingVisibilityConfig || {};
    const currentConversion = currentConfig.conversionConfig || {};
    const images = Array.from(new Set([form.coverUrl, ...(form.images || [])].filter(Boolean)));
    const structuredData = {
      serviceName: form.serviceName,
      headline: form.headline,
      targetAudience: form.targetAudience,
      serviceContent: form.serviceContent,
      pricingNote: form.pricingNote,
      serviceProcess: form.serviceProcess,
      caseHighlights: form.caseHighlights,
      serviceArea: form.serviceArea,
      phone: form.phone,
      contact: form.phone,
      wechat: form.wechat,
      email: form.email,
      website: form.website,
      appointmentNote: form.appointmentNote,
      primaryAction: form.primaryAction,
      secondaryAction: form.secondaryAction,
      coverUrl: form.coverUrl,
      images,
      rawText: form.serviceContent
    };
    return {
      title: form.serviceName || template.title || "服务方案",
      summary: form.headline || template.summary || "",
      body: form.serviceContent || form.headline || "服务方案",
      coverUrl: form.coverUrl || images[0] || "",
      media: images.map((url, index) => ({ type: "image", url, displayUrl: url, sortOrder: index + 1 })),
      categoryIds: [],
      phone: form.phone || "",
      locationText: form.serviceArea || "",
      visibilityConfig: {
        ...currentConfig,
        cardType: "service_offer",
        cardState: "generated",
        sourceType: "service_offer_studio",
        systemCategory: "服务",
        displayTemplate: template.id,
        displayTemplateName: template.name,
        displayTemplateScene: template.scene,
        displayTemplateTone: template.tone,
        tags: ["服务", "销售"],
        structuredData,
        conversionConfig: {
          ...currentConversion,
          showContactPhone: Boolean(form.phone),
          enableLightScrm: true,
          collectLeads: true,
          enableAppointment: true,
          enablePrivateConsultation: Boolean(form.wechat),
          enableSharePoster: true,
          enableGroupRelay: false,
          enablePaymentPlaceholder: false
        }
      }
    };
  },

  async saveOffer(openPreview = false) {
    const error = this.validateForm();
    if (error) {
      safeShowToast({ title: error, icon: "none" });
      this.setStep("form");
      return;
    }
    const user = this.data.user;
    if (!user || this.data.saving) return;
    this.setData({ saving: true });
    safeShowLoading("保存中");
    try {
      let noteId = this.data.savedNoteId;
      if (!noteId) {
        const created = await api.createManualNoteDraft({
          ownerUserId: user.id,
          cardType: "service_offer",
          inputMode: "blank",
          rawText: "",
          title: this.data.form.serviceName || "服务方案"
        });
        noteId = created.data && created.data.id;
      }
      const payload = this.buildNotePayload();
      const updated = await api.updateNote(noteId, { ownerUserId: user.id, ...payload });
      const finalId = (updated.data && updated.data.id) || noteId;
      this.setData({
        savedNoteId: finalId,
        loadedNoteId: finalId,
        existingVisibilityConfig: payload.visibilityConfig,
        existingNoteTitle: payload.title,
        existingNoteSummary: payload.summary,
        hasUnsavedChanges: false
      }, () => this.updateShareMenu());
      safeHideLoading();
      safeShowToast({ title: "方案已保存", icon: "success" });
      if (openPreview) {
        setTimeout(() => wx.navigateTo({ url: `/pages/note-preview/index?id=${finalId}` }), 350);
      }
    } catch (error) {
      safeHideLoading();
      safeShowToast({ title: error.detail || error.message || "保存失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },

  handleSave() {
    this.saveOffer(false);
  },

  handleSavePreview() {
    this.saveOffer(true);
  },

  handleOpenSavedPreview() {
    if (!this.data.savedNoteId) {
      this.saveOffer(true);
      return;
    }
    wx.navigateTo({ url: `/pages/note-preview/index?id=${this.data.savedNoteId}` });
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
      const imagePath = await generateServiceOfferShareImage(this, SERVICE_OFFER_STUDIO_SHARE_CANVAS_ID, this.data.preview);
      if (imagePath) {
        this.setData({ shareImage: imagePath });
        return imagePath;
      }
    } catch (error) {}
    return "";
  },

  onShareAppMessage() {
    const id = this.data.savedNoteId;
    const preview = this.data.preview || {};
    return {
      title: buildServiceOfferShareTitle(preview),
      path: id ? `/pages/note-preview/index?id=${id}` : "/pages/service-offer-studio/index",
      imageUrl: this.data.shareImage || preview.coverUrl || preview.heroAvatarUrl || ""
    };
  }
});
