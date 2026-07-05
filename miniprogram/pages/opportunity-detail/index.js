const { addOpportunityFollowup, fetchOpportunityLead, saveOpportunityLead, unlockOpportunityContact } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildUniversalShareMessage, prepareUniversalShareImage } = require("../../utils/universal-share");

const mockLead = {
  id: "opp_demo_1",
  title: "长沙新店找本地推广渠道",
  summary: "餐饮新店准备开业，想找能触达社区和商圈客户的合作方。",
  content: "对方希望 7 天内启动开业推广，优先找有社区群、商圈地推、达人探店资源的合作方。预算明确，希望先看案例和执行方式。",
  fields: [
    { label: "城市", value: "长沙" },
    { label: "行业", value: "本地生活" },
    { label: "需求类型", value: "找渠道" },
    { label: "联系方式", value: "有电话 · 已核验" },
    { label: "有效期", value: "2 天内优先联系" },
    { label: "可信状态", value: "可联系" }
  ],
  fits: ["本地商家", "推广渠道", "服务介绍页", "案例合集"],
  followups: [
    { status: "待联系", desc: "建议先生成回应包，再查看联系方式。" },
    { status: "提醒", desc: "今天 18:00 前处理优先级最高。" }
  ]
};

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

function isDemoLeadId(value) {
  return /^opp_demo_/.test(String(value || ""));
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
    lead: mockLead,
    loading: false,
    usingMock: true,
    universalShareImage: ""
  },
  onLoad(options = {}) {
    this.leadId = options.id || "opp_demo_1";
    this.loadLead();
  },
  async loadLead() {
    this.setData({ loading: true });
    try {
      const res = await fetchOpportunityLead(this.leadId);
      this.setData({ lead: mapLead(res.data || {}), usingMock: false });
      this.prepareShareImage();
    } catch (error) {
      this.setData({ lead: { ...mockLead, id: this.leadId || mockLead.id }, usingMock: true });
      this.prepareShareImage();
    } finally {
      this.setData({ loading: false });
    }
  },
  handleGeneratePackage() {
    wx.navigateTo({ url: `/pages/response-package/index?leadId=${this.data.lead.id}` });
  },
  prepareShareImage() {
    const lead = this.data.lead || mockLead;
    return prepareUniversalShareImage(this, {
      title: lead.title || "商机线索",
      summary: lead.summary || lead.content || "打开查看完整线索。",
      badge: "线索",
      coverUrl: lead.coverUrl || lead.coverDisplayUrl || "",
      path: `/pages/opportunity-detail/index?id=${encodeURIComponent(lead.id || this.leadId || "")}`,
      shareTargetLabel: "商机"
    });
  },
  async handleContact() {
    if (isDemoLeadId(this.data.lead.id)) {
      wx.showModal({
        title: "示例联系方式",
        content: "示例数据不展示真实电话。真实线索生成回应包后，可按规则查看联系方式。",
        showCancel: false
      });
      return;
    }
    const user = getCurrentUser();
    if (!user) return;
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
    if (!user) return;
    if (isDemoLeadId(this.data.lead.id)) {
      wx.showToast({ title: "已保存到跟进台", icon: "success" });
      return;
    }
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
    if (!user) return;
    if (isDemoLeadId(this.data.lead.id)) {
      wx.showToast({ title: label, icon: "success" });
      return;
    }
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
    const lead = this.data.lead || mockLead;
    return buildUniversalShareMessage(this, {
      title: lead.title || "商机线索",
      summary: lead.summary || "打开查看完整线索。",
      badge: "线索",
      path: `/pages/opportunity-detail/index?id=${encodeURIComponent(lead.id || this.leadId || "")}`,
      shareTargetLabel: "商机"
    });
  }
});
