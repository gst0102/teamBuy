const { addOpportunityFollowup, fetchOpportunityLead, saveOpportunityLead, unlockOpportunityContact } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildShareCardMessage, prepareShareCardImage } = require("../../plugins/share-snapshot/index");

function contactText(lead = {}) {
  if (lead.hasContact) return "有联系方式";
  if (lead.contactStatus === "pending_verify") return "待核验";
  if (lead.contactStatus === "none") return "暂无";
  return lead.contactStatus || "待核验";
}

function trustText(value) {
  if (value === "verified") return "可联系";
  if (value === "risk") return "需谨慎";
  return "待核验";
}

function mapLead(lead = {}) {
  const content = lead.content || lead.summary || "这条线索还没有完整正文。";
  return {
    ...lead,
    title: lead.title || "未命名商机",
    summary: lead.summary || "这条线索还没有摘要。",
    content,
    fields: [
      { label: "城市", value: lead.city || "不限城市" },
      { label: "行业", value: lead.industry || "综合资源" },
      { label: "需求类型", value: lead.demandType || "合作需求" },
      { label: "联系方式", value: contactText(lead) },
      { label: "有效期", value: lead.expiresAt ? "有效期内" : "持续关注" },
      { label: "可信状态", value: trustText(lead.trustStatus) }
    ],
    fits: [lead.city, lead.industry, lead.demandType, ...(lead.tags || [])].filter(Boolean).slice(0, 6),
    followups: [
      { status: "待处理", desc: "建议先生成回应包，再根据联系方式状态跟进。" },
      { status: "提醒", desc: lead.hasContact ? "有联系方式，适合尽快联系。" : "联系方式核验后再联系。" }
    ]
  };
}

Page({
  data: {
    lead: {},
    loading: true,
    loadError: false,
    shareCardImage: ""
  },
  onLoad(options = {}) {
    this.leadId = options.id || "";
    this.loadLead();
  },
  async loadLead() {
    if (!this.leadId) {
      this.setData({ loading: false, loadError: true, lead: {} });
      return;
    }
    this.setData({ loading: true, loadError: false });
    try {
      const res = await fetchOpportunityLead(this.leadId);
      this.setData({ lead: mapLead(res.data || {}), loadError: false });
      this.prepareShareImage();
    } catch (error) {
      this.setData({ lead: {}, loadError: true });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleGeneratePackage() {
    if (!this.data.lead.id) return;
    wx.navigateTo({ url: `/pages/response-package/index?leadId=${this.data.lead.id}` });
  },
  prepareShareImage() {
    const lead = this.data.lead || {};
    if (!lead.id) return Promise.resolve(null);
    return prepareShareCardImage(this, {
      title: lead.title || "商机线索",
      summary: lead.summary || lead.content || "打开查看完整线索。",
      badge: "线索",
      coverUrl: lead.coverUrl || lead.coverDisplayUrl || "",
      path: `/pages/opportunity-detail/index?id=${encodeURIComponent(lead.id || this.leadId || "")}`,
      shareTargetLabel: "商机"
    });
  },
  async handleContact() {
    const user = getCurrentUser();
    if (!user || !this.data.lead.id) return;
    try {
      const res = await unlockOpportunityContact(this.data.lead.id, { userId: user.id });
      const contacts = (res.data && res.data.contacts) || [];
      const contactText = contacts.map((item) => `${item.contactType}：${item.contactValue}`).join("\n") || "暂无联系方式";
      wx.showModal({ title: "联系方式", content: contactText, showCancel: false });
    } catch (error) {
      wx.showToast({ title: (error && error.detail) || "查看失败，稍后再试", icon: "none" });
    }
  },
  async handleSave() {
    const user = getCurrentUser();
    if (!user || !this.data.lead.id) return;
    try {
      await saveOpportunityLead(this.data.lead.id, { userId: user.id, status: "saved", note: "从线索详情保存" });
      wx.showToast({ title: "已保存到跟进台", icon: "success" });
    } catch (error) {
      wx.showToast({ title: "保存失败，稍后再试", icon: "none" });
    }
  },
  async handleFollowupAction(event) {
    const user = getCurrentUser();
    const label = event.currentTarget.dataset.label || "已记录";
    if (!user || !this.data.lead.id) return;
    try {
      await addOpportunityFollowup(this.data.lead.id, {
        userId: user.id,
        actionType: label.includes("联系") ? "contacted" : "note",
        note: label
      });
      wx.showToast({ title: label, icon: "success" });
    } catch (error) {
      wx.showToast({ title: "记录失败，稍后再试", icon: "none" });
    }
  },
  onShareAppMessage() {
    const lead = this.data.lead || {};
    return buildShareCardMessage(this, {
      title: lead.title || "商机线索",
      summary: lead.summary || "打开查看完整线索。",
      badge: "线索",
      path: `/pages/opportunity-detail/index?id=${encodeURIComponent(lead.id || this.leadId || "")}`,
      shareTargetLabel: "商机"
    });
  }
});
