const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

const VALIDITY_OPTIONS = ["7天", "30天", "长期有效"];

function clean(value) {
  return String(value == null ? "" : value).trim();
}

function profileOf(user = {}) {
  const profile = user.salesProfile && typeof user.salesProfile === "object" ? user.salesProfile : {};
  return {
    phone: clean(profile.phone || user.phone),
    wechat: clean(profile.wechat || user.wechat),
    city: clean(profile.city)
  };
}

function contactLine(profile = {}) {
  return [
    profile.phone ? `电话 ${profile.phone}` : "",
    profile.wechat && profile.wechat !== profile.phone ? `微信 ${profile.wechat}` : ""
  ].filter(Boolean).join(" · ");
}

function expiryFor(value) {
  if (value === "长期有效") return "";
  const date = new Date();
  date.setDate(date.getDate() + (value === "7天" ? 7 : 30));
  return date.toISOString();
}

function validityIndexForExpiry(value) {
  if (!value) return 2;
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return 1;
  return timestamp - Date.now() <= 10 * 86400000 ? 0 : 1;
}

Page({
  data: {
    user: null,
    cardId: "",
    editing: false,
    loading: true,
    saving: false,
    businessCardReady: false,
    businessCardContactLine: "",
    form: {
      cardType: "supply",
      title: "",
      summary: "",
      contactSource: "manual",
      contactType: "phone",
      contactValue: "",
      expiresAt: ""
    },
    validityOptions: VALIDITY_OPTIONS,
    validityIndex: 1
  },

  onLoad(options = {}) {
    this.cardId = options.id || "";
    this.setData({ cardId: this.cardId, editing: Boolean(this.cardId) });
  },

  onShow() {
    const user = getCurrentUser();
    if (!user || !user.id) {
      wx.navigateTo({ url: `/pages/login/index?returnUrl=${encodeURIComponent("/pages/business-opportunity/index?publish=opportunity")}` });
      return;
    }
    if (this.hasLoadedOnce) return;
    this.setData({ user, loading: true });
    this.initialize(user);
  },

  async initialize(user) {
    const profile = profileOf(user);
    let businessCardReady = false;
    try {
      const summaryResult = await api.fetchBusinessCardSummary(user.id);
      const businessCard = summaryResult.data && summaryResult.data.businessCard;
      businessCardReady = Boolean(businessCard && (profile.phone || profile.wechat));
    } catch (error) {
      businessCardReady = false;
    }
    this.setData({
      businessCardReady,
      businessCardContactLine: contactLine(profile),
      "form.contactSource": businessCardReady ? "business_card" : "manual",
      "form.contactValue": businessCardReady ? "" : (profile.phone || profile.wechat || ""),
      "form.contactType": profile.phone ? "phone" : "wechat"
    });
    if (this.cardId) await this.loadCard(user);
    this.hasLoadedOnce = true;
    this.setData({ loading: false });
  },

  async loadCard(user) {
    try {
      const result = await api.fetchSupplyDemandCard(this.cardId, user.id);
      const card = result.data || {};
      if (!card.isMine) {
        wx.showToast({ title: "无权编辑该合作机会", icon: "none" });
        return;
      }
      const contacts = Array.isArray(card.contacts) ? card.contacts : [];
      const manualContact = contacts.find((item) => item.contactType === "phone" || item.contactType === "wechat");
      const source = card.contactSource === "business_card" && this.data.businessCardReady ? "business_card" : "manual";
      const contactType = manualContact && manualContact.contactType || "phone";
      this.setData({
        form: {
          cardType: card.cardType === "demand" ? "demand" : "supply",
          title: card.title || "",
          summary: card.summary || "",
          contactSource: source,
          contactType,
          contactValue: source === "manual" && manualContact ? manualContact.contactValue || "" : "",
          expiresAt: card.expiresAt || expiryFor("30天")
        },
        validityIndex: validityIndexForExpiry(card.expiresAt)
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "读取合作机会失败", icon: "none" });
    }
  },

  handleDirectionTap(event) {
    const value = event.currentTarget.dataset.value;
    if (value === "supply" || value === "demand") this.setData({ "form.cardType": value });
  },

  handleInput(event) {
    const key = event.currentTarget.dataset.key;
    if (!key) return;
    this.setData({ [`form.${key}`]: event.detail.value || "" });
  },

  handleContactSource(event) {
    const source = event.currentTarget.dataset.value;
    if (source === "business_card" && !this.data.businessCardReady) {
      wx.showToast({ title: "名片还没有电话或微信", icon: "none" });
      return;
    }
    this.setData({ "form.contactSource": source });
  },

  handleContactType(event) {
    const value = event.currentTarget.dataset.value;
    if (value === "phone" || value === "wechat") this.setData({ "form.contactType": value });
  },

  handleValidityChange(event) {
    const index = Number(event.detail.value || 0);
    const value = VALIDITY_OPTIONS[index] || VALIDITY_OPTIONS[1];
    this.setData({ validityIndex: index, "form.expiresAt": expiryFor(value) });
  },

  validate() {
    const form = this.data.form || {};
    if (!clean(form.title)) return "请填写标题";
    if (!clean(form.summary)) return "请填写具体说明";
    if (form.contactSource === "business_card" && !this.data.businessCardReady) return "名片暂无可用联系方式";
    if (form.contactSource === "manual") {
      const value = clean(form.contactValue);
      if (!value) return "请填写手机号或微信号";
      if (form.contactType === "phone" && !/(?:^|\D)1[3-9]\d{9}(?:$|\D)/.test(value)) return "手机号格式不正确";
    }
    return "";
  },

  buildPayload() {
    const form = this.data.form || {};
    const profile = profileOf(this.data.user || {});
    const validity = this.data.validityOptions[this.data.validityIndex] || "30天";
    const contactSource = form.contactSource === "business_card" ? "business_card" : "manual";
    const contactType = contactSource === "manual" ? form.contactType : null;
    const contactValue = contactSource === "manual" ? clean(form.contactValue) : "";
    return {
      userId: this.data.user.id,
      id: this.data.cardId || null,
      cardType: form.cardType === "demand" ? "demand" : "supply",
      title: clean(form.title),
      summary: clean(form.summary),
      city: profile.city || null,
      industry: null,
      demandType: "合作",
      contactRequirement: contactSource === "business_card" ? "名片联系方式" : (contactType === "phone" ? "电话" : "微信"),
      contactSource,
      contactType,
      contactValue,
      expiresAt: form.expiresAt || expiryFor(validity),
      tags: [],
      status: "pending_review"
    };
  },

  async handlePublish() {
    if (this.data.saving) return;
    const validationError = this.validate();
    if (validationError) {
      wx.showToast({ title: validationError, icon: "none" });
      return;
    }
    this.setData({ saving: true });
    try {
      const saved = await api.saveSupplyDemandCard(this.buildPayload());
      const card = saved.data || {};
      if (!card.id) throw new Error("发布保存失败");
      await api.submitSupplyDemandCard(card.id, this.data.user.id);
      wx.showToast({ title: "已提交审核", icon: "success" });
      setTimeout(() => {
        if (getCurrentPages().length > 1) wx.navigateBack({ delta: 1 });
        else wx.reLaunch({ url: "/pages/business-opportunity/index" });
      }, 500);
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "提交失败，请稍后重试", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },

  handleCancel() {
    if (getCurrentPages().length > 1) wx.navigateBack({ delta: 1 });
    else wx.reLaunch({ url: "/pages/business-opportunity/index" });
  }
});
