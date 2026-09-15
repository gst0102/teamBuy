const { fetchOpportunityLeads, fetchSupplyDemandCards, saveOpportunityLead } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildShareCardMessage, prepareShareCardImage } = require("../../plugins/share-snapshot/index");

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
    stats: buildStats([]),
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
    cards: [],
    loading: false,
    loadError: false,
    hasMore: false,
    leadCursor: "",
    supplyCursor: "",
    loadingMore: false,
    shareCardImage: ""
  },
  onLoad() {
    this.loadMarket();
  },
  prepareShareImage() {
    const first = (this.data.cards || [])[0];
    if (!first) return Promise.resolve(null);
    return prepareShareCardImage(this, {
      title: "供需广场",
      summary: first.summary || "查看可合作的需求和供给资源。",
      badge: "供需",
      path: "/pages/opportunity-market/index",
      shareTargetLabel: "供需"
    });
  },
  async loadMarket(reset = true) {
    if (!reset && (this.data.loading || this.data.loadingMore || !this.data.hasMore)) return;
    const requestSeq = (this._marketRequestSeq || 0) + 1;
    this._marketRequestSeq = requestSeq;
    const leadCursor = reset ? "" : (this.data.leadCursor || "");
    const supplyCursor = reset ? "" : (this.data.supplyCursor || "");
    this.setData(reset
      ? { loading: true, loadingMore: false, loadError: false, hasMore: false, leadCursor: "", supplyCursor: "" }
      : { loadingMore: true, loadError: false });
    try {
      const params = this.buildFilterParams();
      const shouldFetchLeads = this.data.activeFilters.cardType !== "供给";
      const [leadRes, supplyRes] = await Promise.all([
        shouldFetchLeads
          ? fetchOpportunityLeads({ ...params.lead, cursor: leadCursor, limit: 20 })
          : Promise.resolve({ data: { items: [], hasMore: false, nextCursor: "" } }),
        fetchSupplyDemandCards({ ...params.supply, cursor: supplyCursor, limit: 20 })
      ]);
      if (requestSeq !== this._marketRequestSeq) return;
      const leadPayload = leadRes.data || {};
      const supplyPayload = supplyRes.data || {};
      const leadItems = Array.isArray(leadPayload) ? leadPayload : (leadPayload.items || []);
      const supplyItems = Array.isArray(supplyPayload) ? supplyPayload : (supplyPayload.items || []);
      const leadCards = leadItems.map(mapCard);
      const supplyCards = supplyItems.map((item) => ({
        ...item,
        sourceType: "supply_demand",
        type: item.cardType || "supply",
        badge: item.badge || (item.cardType === "demand" ? "我在找" : "我能提供"),
        contactStatus: item.contactRequirement || "申请联系",
        trustStatus: item.status === "published" ? "已审核" : "待审核",
        timeText: formatTime(item.publishedAt || item.updatedAt || item.createdAt)
      }));
      const incoming = [...leadCards, ...supplyCards];
      const cards = reset
        ? incoming
        : [...(this.data.cards || []), ...incoming.filter((item) => !(this.data.cards || []).some((old) => old.id === item.id))];
      const nextLeadCursor = Array.isArray(leadPayload) ? "" : (leadPayload.nextCursor || "");
      const nextSupplyCursor = Array.isArray(supplyPayload) ? "" : (supplyPayload.nextCursor || "");
      const hasMore = Boolean(!Array.isArray(leadPayload) && leadPayload.hasMore) || Boolean(!Array.isArray(supplyPayload) && supplyPayload.hasMore);
      this.setData({
        cards,
        stats: buildStats(cards),
        loading: false,
        loadingMore: false,
        loadError: false,
        hasMore,
        leadCursor: nextLeadCursor,
        supplyCursor: nextSupplyCursor
      });
      if (reset && cards.length) this.prepareShareImage();
    } catch (error) {
      if (requestSeq !== this._marketRequestSeq) return;
      this.setData(reset
        ? { loading: false, loadingMore: false, hasMore: false, loadError: true }
        : { loadingMore: false, loadError: true });
    } finally {
      if (requestSeq === this._marketRequestSeq && reset) this.setData({ loading: false });
    }
  },
  onReachBottom() {
    this.loadMarket(false);
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
    this.loadMarket(true);
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
    this.loadMarket(true);
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
    if (!String(id).startsWith("opp_")) {
      wx.showToast({ title: "请打开详情申请合作", icon: "none" });
      return;
    }
    try {
      await saveOpportunityLead(id, { userId: user.id, status: "saved", note: "从供需广场保存" });
      wx.showToast({ title: "已保存", icon: "success" });
    } catch (error) {
      wx.showToast({ title: "保存失败，稍后再试", icon: "none" });
    }
  },
  onShareAppMessage() {
    return buildShareCardMessage(this, {
      title: "供需广场",
      summary: "查看可合作的需求和供给资源。",
      badge: "供需",
      path: "/pages/opportunity-market/index",
      shareTargetLabel: "供需"
    });
  }
});
