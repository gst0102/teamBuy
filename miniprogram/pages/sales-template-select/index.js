const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { getSalesPageTemplates, getSalesPageTemplate, templateToneClass } = require("../../utils/sales-page-templates");

function cardTypeLabel(cardType) {
  return cardType === "business_card" ? "电子名片" : "服务方案";
}

function buildTemplateView(template) {
  const preview = template.preview || {};
  return {
    ...template,
    toneClass: templateToneClass(template),
    featureText: (template.features || []).slice(0, 4).join(" · "),
    preview: {
      ...preview,
      initial: String(preview.title || template.name || "名").slice(0, 1)
    }
  };
}

function applyTemplateToNote(note, template, user) {
  const config = note.visibilityConfig || {};
  const current = config.structuredData || {};
  const defaults = template.defaults || {};
  const cardType = template.cardType;
  const structuredData = cardType === "business_card"
    ? {
        ...current,
        ...defaults,
        name: current.name || user.nickname || note.title,
        phone: current.phone || user.phone || note.phone || "",
        avatarUrl: current.avatarUrl || user.avatarUrl || note.coverUrl || "",
        images: Array.from(new Set([...(current.images || []), user.avatarUrl || note.coverUrl || ""].filter(Boolean)))
      }
    : {
        ...current,
        ...defaults
      };
  return {
    ...note,
    title: cardType === "business_card" ? (structuredData.name || template.title) : (structuredData.serviceName || template.title),
    summary: structuredData.headline || template.summary || note.summary,
    body: cardType === "business_card" ? (structuredData.bio || note.body || template.summary) : (structuredData.serviceContent || note.body || template.summary),
    coverUrl: cardType === "business_card" ? (structuredData.avatarUrl || note.coverUrl || "") : (note.coverUrl || ""),
    phone: structuredData.phone || structuredData.contact || note.phone || "",
    locationText: structuredData.city || structuredData.serviceArea || note.locationText || "",
    visibilityConfig: {
      ...config,
      displayTemplate: template.id,
      displayTemplateName: template.name,
      displayTemplateScene: template.scene,
      displayTemplateTone: template.tone,
      structuredData,
      tags: Array.from(new Set([...(config.tags || []), ...(cardType === "business_card" ? ["名片", "顾问"] : ["服务", "销售"])]))
    }
  };
}

Page({
  data: {
    user: null,
    cardType: "business_card",
    title: "选择模板",
    tabs: [
      { label: "电子名片", value: "business_card" },
      { label: "服务方案", value: "service_offer" }
    ],
    templates: [],
    selectedTemplateId: "",
    selectedTemplate: null,
    creating: false
  },
  onLoad(options) {
    const cardType = options.type === "service_offer" ? "service_offer" : "business_card";
    this.applyCardType(cardType);
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
  },
  applyCardType(cardType) {
    const templates = getSalesPageTemplates(cardType).map(buildTemplateView);
    const selectedTemplate = templates[0] || null;
    this.setData({
      cardType,
      title: cardTypeLabel(cardType),
      templates,
      selectedTemplateId: selectedTemplate ? selectedTemplate.id : "",
      selectedTemplate
    });
  },
  handleSwitchType(event) {
    const cardType = event.currentTarget.dataset.type;
    if (!cardType || cardType === this.data.cardType) return;
    this.applyCardType(cardType);
  },
  handleSelectTemplate(event) {
    const templateId = event.currentTarget.dataset.id;
    const template = buildTemplateView(getSalesPageTemplate(templateId));
    this.setData({
      selectedTemplateId: template.id,
      selectedTemplate: template
    });
  },
  async handleCreate() {
    const { user, selectedTemplateId, creating } = this.data;
    if (!user || !selectedTemplateId || creating) return;
    const template = getSalesPageTemplate(selectedTemplateId);
    if (template && template.cardType === "service_offer") {
      wx.navigateTo({ url: `/pages/service-offer-studio/index?template=${template.id}` });
      return;
    }
    this.setData({ creating: true });
    wx.showLoading({ title: "创建中" });
    try {
      const created = await api.createManualNoteDraft({
        ownerUserId: user.id,
        cardType: template.cardType,
        inputMode: "blank",
        rawText: "",
        title: template.title
      });
      const note = created.data || {};
      const nextNote = applyTemplateToNote(note, template, user);
      const updated = await api.updateNote(note.id, {
        ownerUserId: user.id,
        title: nextNote.title,
        summary: nextNote.summary,
        body: nextNote.body,
        coverUrl: nextNote.coverUrl,
        media: nextNote.media || [],
        categoryIds: nextNote.categoryIds || [],
        phone: nextNote.phone || "",
        locationText: nextNote.locationText || "",
        visibilityConfig: nextNote.visibilityConfig
      });
      wx.hideLoading();
      const finalNote = updated.data || note;
      wx.navigateTo({ url: `/pages/note-edit/index?id=${finalNote.id}` });
    } catch (error) {
      wx.hideLoading();
      const detail = error.detail || error.errMsg || "创建失败";
      wx.showToast({
        title: detail.includes("不支持") ? "服务正在更新，请稍后再试" : detail,
        icon: "none"
      });
    } finally {
      this.setData({ creating: false });
    }
  }
});
