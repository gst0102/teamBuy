const { fetchOpportunityLeads, fetchSupplyDemandCards, saveOpportunityLead } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildUniversalShareMessage, prepareUniversalShareImage } = require("../../utils/universal-share");

const mockCards = [
  {
    id: "opp_demo_1",
    type: "demand",
    badge: "官方收录",
    title: "长沙新店找本地推广渠道",
    summary: "餐饮新店准备开业，想找能触达社区和商圈客户的合作方。",
    city: "长沙",
    industry: "本地生活",
    demandType: "找渠道",
    contactStatus: "有电话",
    trustStatus: "可联系",
    timeText: "今天 10:20"
  },
  {
    id: "supply_demo_1",
    type: "supply",
    badge: "我能提供",
    title: "长沙地推团队可接门店开业",
    summary: "可提供社区派单、商圈地推、团长对接，适合本地门店。",
    city: "长沙",
    industry: "推广渠道",
    demandType: "服务介绍页",
    contactStatus: "申请联系",
    trustStatus: "待审核",
    timeText: "昨天 18:40"
  }
];

const filterGroups = [
  { key: "city", label: "城市", options: ["全部", "长沙", "上海", "深圳", "全国"] },
  { key: "industry", label: "行业", options: ["全部", "本地生活", "团购", "企业服务", "推广渠道"] },
  { key: "cardType", label: "类型", options: ["全部", "需求", "供给"] },
  { key: "demandType", label: "需求类型", options: ["全部", "找渠道", "找货源", "找服务商", "合作"] },
  { key: "contactStatus", label: "联系", options: ["全部", "有联系方式", "待核验"] }
];

function formatTime(value) {
  if (!value) return "刚刚";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚";
  const diff = Date.now() - date.getTime();
  if (diff < 3600000) return `${Math.max(1, Math.floor(diff / 60000))}分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
  return `${date.getMonth() + 1}-${date.getDate()}`;
}

function mapCard(lead = {}) {
  return {
    ...lead,
    sourceType: "opportunity_lead",
    type: "demand",
    badge: lead.sourceLabel || "官方收录",
    title: lead.title || "未命名商机",
    summary: lead.summary || "这条线索还没有摘要。",
    city: lead.city || "不限",
    industry: lead.industry || "综合",
    demandType: lead.demandType || "合作",
    contactStatus: lead.hasContact ? "有联系方式" : "待核验",
    trustStatus: lead.trustStatus === "verified" ? "可联系" : "待审核",
    timeText: formatTime(lead.publishedAt || lead.updatedAt || lead.createdAt)
  };
}

function buildStats(cards = []) {
  const contactCount = cards.filter((item) => item.contactStatus === "有联系方式").length;
  return [
    { label: "今日新增", value: cards.length },
    { label: "可联系", value: contactCount },
    { label: "高匹配", value: Math.min(cards.length, Math.max(0, contactCount)) },
    { label: "用户发布", value: cards.filter((item) => item.sourceType === "supply_demand").length }
  ];
}

function isMockCardId(value) {
  return /^(opp_demo_|supply_demo_)/.test(String(value || ""));
}

function buildFilterGroups(activeFilters = {}) {
  return filterGroups.map((group) => ({
    ...group,
    value: activeFilters[group.key] || "全部",
    options: group.options.map((label) => ({
      label,
      active: (activeFilters[group.key] || "全部") === label
    }))
  }));
}

Page({
  data: {
    stats: buildStats(mockCards),
    activeFilters: {
      city: "全部",
      industry: "全部",
      cardType: "全部",
      demandType: "全部",
      contactStatus: "全部"
    },
    filterGroups: buildFilterGroups({
      city: "全部",
      industry: "全部",
      cardType: "全部",
      demandType: "全部",
      contactStatus: "全部"
    }),
    cards: mockCards,
    loading: false,
    usingMock: true,
    universalShareImage: ""
  },
  onLoad() {
    this.loadMarket();
    this.prepareShareImage();
  },
  prepareShareImage() {
    const first = (this.data.cards || [])[0] || mockCards[0];
    return prepareUniversalShareImage(this, {
      title: "供需广场",
      summary: first.summary || "查看可合作的需求和供给资源。",
      badge: "供需",
      path: "/pages/opportunity-market/index",
      shareTargetLabel: "供需"
    });
  },
  async loadMarket() {
    this.setData({ loading: true });
    try {
      const params = this.buildFilterParams();
      const shouldFetchLeads = this.data.activeFilters.cardType !== "供给";
      const [leadRes, supplyRes] = await Promise.all([
        shouldFetchLeads ? fetchOpportunityLeads(params.lead) : Promise.resolve({ data: [] }),
        fetchSupplyDemandCards(params.supply)
      ]);
      const leadCards = Array.isArray(leadRes.data) ? leadRes.data.map(mapCard) : [];
      const supplyCards = Array.isArray(supplyRes.data) ? supplyRes.data.map((item) => ({
        ...item,
        sourceType: "supply_demand",
        type: item.cardType || "supply",
        badge: item.badge || (item.cardType === "demand" ? "我在找" : "我能提供"),
        contactStatus: item.contactRequirement || "申请联系",
        trustStatus: item.status === "published" ? "已审核" : "待审核",
        timeText: formatTime(item.publishedAt || item.updatedAt || item.createdAt)
      })) : [];
      const cards = [...leadCards, ...supplyCards];
      if (!cards.length) {
        this.setData({ cards: mockCards, stats: buildStats(mockCards), usingMock: true });
        return;
      }
      this.setData({ cards, stats: buildStats(cards), usingMock: false });
      this.prepareShareImage();
    } catch (error) {
      this.setData({ cards: mockCards, stats: buildStats(mockCards), usingMock: true });
    } finally {
      this.setData({ loading: false });
    }
  },
  buildFilterParams() {
    const filters = this.data.activeFilters || {};
    const common = {};
    if (filters.city && filters.city !== "全部") common.city = filters.city;
    if (filters.industry && filters.industry !== "全部") common.industry = filters.industry;
    if (filters.demandType && filters.demandType !== "全部") common.demandType = filters.demandType;
    if (filters.contactStatus && filters.contactStatus !== "全部") common.contactStatus = filters.contactStatus;
    const lead = { ...common };
    const supply = { ...common };
    if (filters.cardType === "需求") {
      supply.cardType = "demand";
    } else if (filters.cardType === "供给") {
      supply.cardType = "supply";
    }
    return { lead, supply };
  },
  handleFilterTap(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.currentTarget.dataset.value;
    if (!key || !value) return;
    const activeFilters = {
      ...this.data.activeFilters,
      [key]: value
    };
    this.setData({
      activeFilters,
      filterGroups: buildFilterGroups(activeFilters)
    });
    this.loadMarket();
  },
  handleFilterInput(event) {
    const key = event.currentTarget.dataset.key;
    if (!key) return;
    const activeFilters = {
      ...this.data.activeFilters,
      [key]: event.detail.value || "全部"
    };
    this.setData({
      activeFilters,
      filterGroups: buildFilterGroups(activeFilters)
    });
  },
  handleFilterConfirm() {
    this.loadMarket();
  },
  handleOpenDetail(event) {
    const id = event.currentTarget.dataset.id;
    if (!String(id || "").startsWith("opp_")) {
      wx.navigateTo({ url: `/pages/supply-demand-detail/index?id=${id}` });
      return;
    }
    wx.navigateTo({ url: `/pages/opportunity-detail/index?id=${id}` });
  },
  async handleSave(event) {
    const user = getCurrentUser();
    const id = event.currentTarget.dataset.id;
    if (!user || !id) return;
    if (isMockCardId(id)) {
      wx.showToast({ title: "已保存", icon: "success" });
      return;
    }
    if (!String(id).startsWith("opp_")) {
      wx.showToast({ title: "已保存供需卡", icon: "success" });
      return;
    }
    try {
      await saveOpportunityLead(id, { userId: user.id, status: "saved", note: "从供需广场保存" });
      wx.showToast({ title: "已保存", icon: "success" });
    } catch (error) {
      wx.showToast({ title: "保存失败，稍后再试", icon: "none" });
    }
  },
  handlePublish() {
    wx.navigateTo({ url: "/pages/supply-demand-publish/index" });
  },
  onShareAppMessage() {
    return buildUniversalShareMessage(this, {
      title: "供需广场",
      summary: "查看可合作的需求和供给资源。",
      badge: "供需",
      path: "/pages/opportunity-market/index",
      shareTargetLabel: "供需"
    });
  }
});
