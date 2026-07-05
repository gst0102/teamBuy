const { fetchNotes, fetchShowcases, fetchSupplyDemandCard, saveSupplyDemandCard, submitSupplyDemandCard } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildUniversalShareMessage, prepareUniversalShareImage } = require("../../utils/universal-share");

const cityOptions = ["长沙", "上海", "深圳", "广州", "杭州", "全国"];
const industryOptions = ["本地生活", "团购", "企业服务", "推广渠道", "房源", "供应链"];
const demandTypeOptions = ["找渠道", "找货源", "找服务商", "服务介绍页", "案例合集", "合作"];

function getApiErrorTitle(error, fallback) {
  const message = String((error && (error.detail || error.message || error.errMsg)) || "");
  if (/not found|404/i.test(message)) {
    return "测试后端未同步接口";
  }
  return message || fallback;
}

Page({
  data: {
    form: {
      cardType: "supply",
      title: "",
      summary: "",
      city: "长沙",
      industry: "",
      demandType: "",
      contactRequirement: "有电话",
      linkedNoteId: "",
      linkedResourceType: "",
      linkedResourceId: "",
      tagsText: ""
    },
    cityOptions,
    industryOptions,
    demandTypeOptions,
    resourceOptions: [],
    selectedResourceTitle: "",
    cardId: "",
    isEdit: false,
    saving: false,
    universalShareImage: ""
  },
  onLoad(options = {}) {
    this.cardId = options.id || "";
    if (this.cardId) {
      this.setData({ cardId: this.cardId, isEdit: true });
      this.loadCard();
    }
    this.loadResources();
    this.prepareShareImage();
  },
  prepareShareImage() {
    const form = this.data.form || {};
    return prepareUniversalShareImage(this, {
      title: form.title || "发布需求 / 供给",
      summary: form.summary || "提交后进入审核，审核通过会展示到供需广场。",
      badge: form.cardType === "demand" ? "需求" : "供给",
      path: this.data.cardId ? `/pages/supply-demand-publish/index?id=${encodeURIComponent(this.data.cardId)}` : "/pages/supply-demand-publish/index",
      shareTargetLabel: "供需"
    });
  },
  async loadCard() {
    const user = getCurrentUser();
    if (!user || !this.cardId) return;
    try {
      const res = await fetchSupplyDemandCard(this.cardId, user.id);
      const card = res.data || {};
      if (!card.isMine) {
        wx.showToast({ title: "无权编辑该发布", icon: "none" });
        return;
      }
      this.setData({
        form: {
          cardType: card.cardType || "supply",
          title: card.title || "",
          summary: card.summary || "",
          city: card.city || "长沙",
          industry: card.industry || "",
          demandType: card.demandType || "",
          contactRequirement: card.contactRequirement || "有电话",
          linkedNoteId: card.linkedNoteId || "",
          linkedResourceType: card.linkedResourceType || (card.linkedNoteId ? "note" : ""),
          linkedResourceId: card.linkedResourceId || card.linkedNoteId || "",
          tagsText: (card.tags || []).join(" ")
        },
        selectedResourceTitle: card.linkedResourceTitle || card.linkedNoteTitle || ""
      });
      this.prepareShareImage();
    } catch (error) {
      wx.showToast({ title: getApiErrorTitle(error, "读取发布失败"), icon: "none" });
    }
  },
  async loadResources() {
    const user = getCurrentUser();
    if (!user) return;
    try {
      const [notesRes, showcasesRes] = await Promise.all([
        fetchNotes({ ownerUserId: user.id }),
        fetchShowcases(user.id)
      ]);
      const notes = Array.isArray(notesRes.data) ? notesRes.data.slice(0, 20).map((item) => ({
        id: item.id,
        type: "note",
        label: item.title || "未命名资料",
        desc: item.summary || "资料库"
      })) : [];
      const showcases = Array.isArray(showcasesRes.data) ? showcasesRes.data.slice(0, 20).map((item) => ({
        id: item.id,
        type: "showcase",
        label: item.name || "未命名合集",
        desc: `合集 · ${item.itemCount || 0} 条资料`
      })) : [];
      this.setData({ resourceOptions: [...notes, ...showcases] });
    } catch (error) {
      this.setData({ resourceOptions: [] });
    }
  },
  setField(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`form.${key}`]: event.detail.value });
    if (key === "title" || key === "summary") this.prepareShareImage();
  },
  setChip(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.currentTarget.dataset.value;
    if (!key || !value) return;
    this.setData({ [`form.${key}`]: value });
  },
  setType(event) {
    this.setData({ "form.cardType": event.currentTarget.dataset.value });
    this.prepareShareImage();
  },
  handleChooseResource(event) {
    const id = event.currentTarget.dataset.id;
    const type = event.currentTarget.dataset.type;
    const resource = this.data.resourceOptions.find((item) => item.id === id && item.type === type);
    if (!resource) return;
    this.setData({
      "form.linkedResourceType": type,
      "form.linkedResourceId": id,
      "form.linkedNoteId": type === "note" ? id : "",
      selectedResourceTitle: resource.label
    });
  },
  handleClearResource() {
    this.setData({
      "form.linkedResourceType": "",
      "form.linkedResourceId": "",
      "form.linkedNoteId": "",
      selectedResourceTitle: ""
    });
  },
  buildPayload(status = "draft") {
    const user = getCurrentUser();
    return {
      userId: user.id,
      id: this.data.cardId || null,
      ...this.data.form,
      status,
      tags: String(this.data.form.tagsText || "").split(/[,，\s]+/).filter(Boolean)
    };
  },
  async handleSaveDraft() {
    const user = getCurrentUser();
    if (!user) return;
    this.setData({ saving: true });
    try {
      const res = await saveSupplyDemandCard(this.buildPayload("draft"));
      if (res.data && res.data.id) {
        this.setData({ cardId: res.data.id, isEdit: true });
      }
      wx.showToast({ title: "草稿已保存", icon: "success" });
    } catch (error) {
      wx.showToast({ title: getApiErrorTitle(error, "保存失败"), icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  async handleSubmit() {
    const user = getCurrentUser();
    if (!user) return;
    this.setData({ saving: true });
    try {
      const saved = await saveSupplyDemandCard(this.buildPayload("pending_review"));
      this.setData({ cardId: saved.data.id, isEdit: true });
      await submitSupplyDemandCard(saved.data.id, user.id);
      wx.showToast({ title: "已提交审核", icon: "success" });
      wx.navigateTo({ url: "/pages/supply-demand-my/index" });
    } catch (error) {
      wx.showToast({ title: getApiErrorTitle(error, "提交失败"), icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  onShareAppMessage() {
    const form = this.data.form || {};
    return buildUniversalShareMessage(this, {
      title: form.title || "发布需求 / 供给",
      summary: form.summary || "提交后进入审核，审核通过会展示到供需广场。",
      badge: form.cardType === "demand" ? "需求" : "供给",
      path: this.data.cardId ? `/pages/supply-demand-publish/index?id=${encodeURIComponent(this.data.cardId)}` : "/pages/supply-demand-publish/index",
      shareTargetLabel: "供需"
    });
  }
});
