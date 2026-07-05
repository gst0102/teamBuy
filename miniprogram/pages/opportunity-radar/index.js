const { fetchOpportunityLeads, fetchOpportunityPushDigests, generateOpportunityPushDigest, markOpportunityPushDigestRead, saveOpportunityLead } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildUniversalShareMessage, prepareUniversalShareImage } = require("../../utils/universal-share");

const tabs = [
  { key: "mine", label: "我的机会" },
  { key: "market", label: "供需广场" },
  { key: "saved", label: "已保存" },
  { key: "sub", label: "订阅" }
];

const mockTopOpportunity = {
  id: "opp_demo_1",
  level: "高匹配",
  score: 92,
  title: "长沙新店找本地推广渠道",
  summary: "餐饮新店准备开业，想找能触达社区和商圈客户的合作方。",
  city: "长沙",
  industry: "本地生活",
  demandType: "找渠道",
  contactStatus: "有电话 · 已核验",
  trustStatus: "可联系",
  expireText: "2 天内优先联系",
  action: "生成服务介绍页和案例合集发给对方",
  reasons: ["长沙", "本地商家", "推广渠道", "有联系方式"],
  radar: [
    { label: "城市", value: 96 },
    { label: "行业", value: 88 },
    { label: "需求", value: 94 },
    { label: "联系", value: 86 },
    { label: "时效", value: 91 }
  ]
};

const mockMoreOpportunities = [
  {
    id: "opp_demo_2",
    level: "中匹配",
    score: 78,
    title: "社区团购团长找稳定货源",
    summary: "希望找到日用品、食品类供给方，可接受样品试卖。",
    city: "长沙",
    industry: "团购",
    contactStatus: "可私信",
    action: "整理商品合集后申请联系",
    reasons: ["团购", "货源", "可联系"]
  },
  {
    id: "opp_demo_3",
    level: "中匹配",
    score: 74,
    title: "企业客户找活动执行供应商",
    summary: "下周有线下活动，需要摄影、物料和现场执行团队。",
    city: "长沙",
    industry: "企业服务",
    contactStatus: "联系方式待核验",
    action: "先保存，等核验后生成回应包",
    reasons: ["企业客户", "服务合作", "时效强"]
  }
];

function scoreLead(lead = {}, index = 0) {
  let score = 68;
  if (lead.city) score += 8;
  if (lead.industry) score += 6;
  if (lead.demandType) score += 5;
  if (lead.hasContact || ["available", "masked", "locked"].includes(lead.contactStatus)) score += 8;
  if (lead.trustStatus === "verified") score += 5;
  return Math.max(62, Math.min(96, score - index * 3));
}

function mapLead(lead = {}, index = 0) {
  const score = lead.matchScore || scoreLead(lead, index);
  const reasons = (lead.matchReasons && lead.matchReasons.length ? lead.matchReasons : [lead.city, lead.industry, lead.demandType, lead.hasContact ? "有联系方式" : ""])
    .filter(Boolean)
    .slice(0, 4);
  return {
    ...lead,
    level: score >= 86 ? "高匹配" : "中匹配",
    score,
    title: lead.title || "未命名商机",
    summary: lead.summary || "这条线索还没有摘要。",
    city: lead.city || "不限城市",
    industry: lead.industry || "综合资源",
    demandType: lead.demandType || "合作需求",
    contactStatus: lead.hasContact ? "有联系方式" : "联系方式待核验",
    trustStatus: lead.trustStatus === "verified" ? "可联系" : "待核验",
    expireText: lead.expiresAt ? "有效期内" : "持续关注",
    action: lead.hasContact ? "生成回应包后查看联系方式" : "先保存，等联系方式核验后跟进",
    reasons: reasons.length ? reasons : ["需求明确"],
    radar: [
      { label: "城市", value: lead.city ? 88 : 64 },
      { label: "行业", value: lead.industry ? 84 : 66 },
      { label: "需求", value: lead.demandType ? 90 : 70 },
      { label: "联系", value: lead.hasContact ? 86 : 58 },
      { label: "时效", value: lead.expiresAt ? 82 : 72 }
    ]
  };
}

function isDemoLeadId(value) {
  return /^opp_demo_/.test(String(value || ""));
}

Page({
  data: {
    tabs,
    activeTab: "mine",
    topOpportunity: mockTopOpportunity,
    moreOpportunities: mockMoreOpportunities,
    recommendationTitle: "今日推荐机会",
    recommendationMeta: "进入页面时按订阅条件刷新",
    pushDigests: [],
    generatingDigest: false,
    loading: false,
    usingMock: true,
    universalShareImage: ""
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadOpportunities();
    this.loadPushDigests();
    this.prepareShareImage();
  },
  prepareShareImage() {
    const lead = this.data.topOpportunity || mockTopOpportunity;
    return prepareUniversalShareImage(this, {
      title: "我的机会",
      summary: lead.summary || "系统按你的资料和订阅条件推荐可跟进机会。",
      badge: "商机",
      path: "/pages/opportunity-radar/index",
      shareTargetLabel: "商机"
    });
  },
  async loadOpportunities() {
    this.setData({ loading: true });
    try {
      const user = getCurrentUser();
      const res = await fetchOpportunityLeads({ userId: user && user.id });
      const rawList = Array.isArray(res.data) ? res.data : (res.data && res.data.items) || [];
      const list = rawList.map(mapLead);
      if (!list.length) {
        this.setData({
          topOpportunity: mockTopOpportunity,
          moreOpportunities: mockMoreOpportunities,
          usingMock: true
        });
        return;
      }
      this.setData({
        topOpportunity: list[0],
        moreOpportunities: list.slice(1),
        recommendationTitle: (res.data && res.data.recommendationTitle) || "今日推荐机会",
        recommendationMeta: (res.data && res.data.rule) || "按订阅条件生成",
        usingMock: false
      });
      this.prepareShareImage();
    } catch (error) {
      this.setData({
        topOpportunity: mockTopOpportunity,
        moreOpportunities: mockMoreOpportunities,
        usingMock: true
      });
    } finally {
      this.setData({ loading: false });
    }
  },
  async loadPushDigests() {
    const user = getCurrentUser();
    if (!user) return;
    try {
      const res = await fetchOpportunityPushDigests(user.id);
      const pushDigests = Array.isArray(res.data) ? res.data.slice(0, 3) : [];
      this.setData({ pushDigests });
    } catch (error) {
      this.setData({ pushDigests: [] });
    }
  },
  async handleGenerateDigest() {
    const user = getCurrentUser();
    if (!user) return;
    this.setData({ generatingDigest: true });
    try {
      await generateOpportunityPushDigest(user.id);
      wx.showToast({ title: "今日推荐已生成", icon: "success" });
      this.loadPushDigests();
    } catch (error) {
      wx.showToast({ title: "生成失败", icon: "none" });
    } finally {
      this.setData({ generatingDigest: false });
    }
  },
  async handleReadDigest(event) {
    const user = getCurrentUser();
    const id = event.currentTarget.dataset.id;
    if (!user || !id) return;
    try {
      await markOpportunityPushDigestRead(id, user.id);
      this.loadPushDigests();
      wx.showToast({ title: "已读", icon: "none" });
    } catch (error) {
      wx.showToast({ title: "操作失败", icon: "none" });
    }
  },
  handleTabTap(event) {
    const key = event.currentTarget.dataset.key;
    if (key === "market") {
      wx.navigateTo({ url: "/pages/opportunity-market/index" });
      return;
    }
    if (key === "saved") {
      wx.navigateTo({ url: "/pages/opportunity-saved/index" });
      return;
    }
    if (key === "sub") {
      wx.navigateTo({ url: "/pages/opportunity-subscription/index" });
    }
  },
  handleOpenDetail(event) {
    const id = event.currentTarget.dataset.id || this.data.topOpportunity.id;
    wx.navigateTo({ url: `/pages/opportunity-detail/index?id=${id}` });
  },
  handleGeneratePackage() {
    wx.navigateTo({ url: `/pages/response-package/index?leadId=${this.data.topOpportunity.id}` });
  },
  async handleSave() {
    const user = getCurrentUser();
    const lead = this.data.topOpportunity;
    if (!user || !user.id) {
      wx.showToast({ title: "请先重新登录", icon: "none" });
      return;
    }
    if (!lead || !lead.id) return;
    if (isDemoLeadId(lead.id)) {
      wx.showToast({ title: "已保存到跟进台", icon: "success" });
      return;
    }
    if (!String(lead.id).startsWith("opp_")) {
      wx.showToast({ title: "这条不是商机线索，请去供需详情申请", icon: "none" });
      return;
    }
    try {
      await saveOpportunityLead(lead.id, { userId: user.id, status: "saved", note: "从我的机会保存" });
      wx.showToast({ title: "已保存到跟进台", icon: "success" });
    } catch (error) {
      const message = (error && (error.detail || error.message)) || "保存失败，稍后再试";
      if (/用户不存在|认证|登录/.test(String(message))) {
        wx.removeStorageSync("currentUser");
        getApp().globalData.currentUser = null;
      }
      wx.showToast({ title: String(message).slice(0, 18), icon: "none" });
    }
  },
  handleContact() {
    wx.showToast({ title: "先生成回应包，再查看联系动作", icon: "none" });
  },
  onShareAppMessage() {
    return buildUniversalShareMessage(this, {
      title: "我的机会",
      summary: "系统按你的资料和订阅条件推荐可跟进机会。",
      badge: "商机",
      path: "/pages/opportunity-radar/index",
      shareTargetLabel: "商机"
    });
  }
});
