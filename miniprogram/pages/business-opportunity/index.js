const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const {
  BUSINESS_INDUSTRY_GROUPS: INDUSTRY_GROUPS
} = require("../../utils/business-industry");

function formatTime(value) {
  if (!value) return "刚刚更新";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚更新";
  const diff = Date.now() - date.getTime();
  if (diff < 3600000) return `${Math.max(1, Math.floor(diff / 60000))}分钟前更新`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前更新`;
  return `${date.getMonth() + 1}月${date.getDate()}日更新`;
}

function unique(values) {
  return Array.from(new Set((values || []).map((item) => String(item || "").trim()).filter(Boolean)));
}

function mapCard(item = {}) {
  const intent = item.cooperationIntent || {};
  return {
    ...item,
    title: item.displayName || "合作伙伴",
    roleLine: [item.jobTitle, item.company].filter(Boolean).join(" · ") || "独立合作伙伴",
    locationLine: [item.city, item.subIndustry || item.industry].filter(Boolean).join(" · ") || "线上合作",
    industryLabel: item.subIndustry || item.industry || "综合服务",
    tags: unique([...(item.keywords || []), ...(item.industryTags || [])]).slice(0, 5),
    intentLabel: intent.directionText || "当前可合作",
    intentText: intent.text || "欢迎基于服务能力进一步沟通合作。",
    timeText: formatTime(item.updatedAt),
    avatarInitial: item.avatarInitial || String(item.displayName || "合").slice(0, 1),
    contactLabel: item.hasContact ? "联系方式可解锁" : "站内沟通",
    contactWarning: item.contactWarning || "",
    sourceLabel: item.sourceLabel || "合作名片"
  };
}

function mapSupplyDemandCard(item = {}) {
  const isDemand = item.cardType === "demand";
  return mapCard({
    ...item,
    sourceType: "supply_demand",
    sourceLabel: item.sourceLabel || "用户发布",
    displayName: item.title || "合作机会",
    jobTitle: item.ownerNickname ? `发布者：${item.ownerNickname}` : "用户发布",
    company: "合作机会",
    city: item.city || "线上合作",
    industry: item.industry || "",
    subIndustry: "",
    industryTags: [],
    keywords: item.tags || [],
    headline: item.summary || "",
    cooperationIntent: {
      directionText: isDemand ? "我正在找合作" : "我能提供",
      text: item.summary || "",
      active: true
    }
  });
}

function buildIndustryFilters(active) {
  return [{ label: "全部", active: !active }, ...INDUSTRY_GROUPS.map((item) => ({
    label: item.label,
    active: item.label === active
  }))];
}

function buildSubIndustryOptions(industry) {
  const group = INDUSTRY_GROUPS.find((item) => item.label === industry);
  return group ? [{ label: "全部细分", active: true }, ...group.children.map((label) => ({ label, active: false }))] : [];
}

Page({
  data: {
    user: null,
    activeTab: "capability",
    tabs: [
      { key: "intent", label: "合作需求", note: "正在寻找" },
      { key: "capability", label: "合作资源", note: "我能提供" },
      { key: "mine", label: "我的名片", note: "管理" }
    ],
    keyword: "",
    activeIndustry: "",
    activeSubIndustry: "",
    industryFilters: buildIndustryFilters(""),
    subIndustryOptions: [],
    cards: [],
    loading: false,
    loadingMore: false,
    hasMore: false,
    listError: false,
    opportunityError: false,
    walletBalance: null,
    viewCostPoints: 1,
    myCard: null,
    myCardLoading: false,
    myCardChecked: false,
    myCardError: false,
    publishSheetVisible: false
  },

  onLoad(options = {}) {
    const activeTab = ["intent", "capability", "mine"].includes(options.tab) ? options.tab : "capability";
    this.setData({ activeTab, publishSheetVisible: options.publish === "1" || options.publish === "opportunity" });
  },

  onShow() {
    const user = getCurrentUser();
    this.setData({ user, myCardChecked: false });
    this.loadMyCard();
    if (!this.hasLoadedOnce && this.data.activeTab !== "mine") {
      this.hasLoadedOnce = true;
      this.loadCards(true);
    }
    if (user && user.id) this.loadWallet(user.id);
  },

  onReachBottom() {
    if (this.data.activeTab !== "mine") this.loadCards(false);
  },

  async loadWallet(userId) {
    try {
      const result = await api.fetchResourceWallet(userId);
      if ((getCurrentUser() || {}).id !== userId) return;
      this.setData({ walletBalance: Number((result.data && result.data.wallet && result.data.wallet.balance) || 0) });
    } catch (error) {
      this.setData({ walletBalance: null });
    }
  },

  async loadCards(reset) {
    if (!reset && (this.data.loading || this.data.loadingMore)) return;
    if (!reset && !this.data.hasMore) return;
    const requestSeq = (this._cardRequestSeq || 0) + 1;
    this._cardRequestSeq = requestSeq;
    const cursor = reset ? "" : (this.data.nextCursor || "");
    const opportunityCursor = reset ? "" : (this.data.opportunityCursor || "");
    this.setData(reset
      ? { loading: true, loadingMore: false, listError: false, opportunityError: false, hasMore: false, nextCursor: "", opportunityCursor: "" }
      : { loadingMore: true });
    try {
      const opportunityType = this.data.activeTab === "intent" ? "demand" : "supply";
      const businessRequest = reset || cursor
        ? api.fetchBusinessOpportunityCards({
            mode: this.data.activeTab,
            keyword: this.data.keyword,
            industry: this.data.activeIndustry,
            subIndustry: this.data.activeSubIndustry,
            cursor,
            limit: 10,
            viewerUserId: this.data.user && this.data.user.id
          })
        : Promise.resolve({ data: { items: [], hasMore: false, nextCursor: "" } });
      const opportunityRequest = reset || opportunityCursor
        ? api.fetchSupplyDemandCards({
            keyword: this.data.keyword,
            industry: this.data.activeIndustry,
            cardType: opportunityType,
            cursor: opportunityCursor,
            limit: 10
          })
        : Promise.resolve({ data: { items: [], hasMore: false, nextCursor: "" } });
      // The business-card catalogue is the primary surface. User-published
      // supply/demand cards are an optional supplement and must not make the
      // whole page fail when their auth/network path is unavailable.
      const businessResultPromise = businessRequest
        .then((response) => ({ response, error: null }))
        .catch((error) => ({ response: null, error }));
      const opportunityResultPromise = opportunityRequest
        .then((response) => ({ response, error: null }))
        .catch((error) => ({ response: null, error }));
      const result = await businessResultPromise;
      if (requestSeq !== this._cardRequestSeq) return;
      const payload = result.response && result.response.data || {};
      const incoming = Array.isArray(payload.items) ? payload.items.map(mapCard) : [];
      const cards = reset ? incoming : [...this.data.cards, ...incoming.filter((item) => !this.data.cards.some((old) => old.id === item.id))];
      this.setData({
        cards,
        nextCursor: payload.nextCursor || "",
        hasMore: Boolean(payload.hasMore),
        viewCostPoints: Number(payload.viewCostPoints || 1),
        loading: false,
        loadingMore: false,
        listError: Boolean(result.error)
      });

      // Merge the optional stream only after the primary catalogue is
      // visible. A slow or failed supplement can no longer keep the page in
      // its initial loading state.
      const opportunityResult = await opportunityResultPromise;
      if (requestSeq !== this._cardRequestSeq) return;
      const opportunityPayload = opportunityResult.response && opportunityResult.response.data || {};
      const opportunityItems = Array.isArray(opportunityPayload.items)
        ? opportunityPayload.items
          .filter((item) => !this.data.user || item.ownerUserId !== this.data.user.id)
          .map(mapSupplyDemandCard)
        : [];
      const currentCards = this.data.cards || [];
      const mergedCards = [...currentCards, ...opportunityItems.filter((item) => !currentCards.some((old) => old.id === item.id))];
      this.setData({
        cards: mergedCards,
        opportunityCursor: opportunityPayload.nextCursor || "",
        hasMore: Boolean(this.data.hasMore) || Boolean(opportunityPayload.hasMore),
        opportunityError: Boolean(opportunityResult.error)
      });
    } catch (error) {
      if (requestSeq !== this._cardRequestSeq) return;
      this.setData(reset
        ? { loading: false, loadingMore: false, hasMore: false, listError: true, opportunityError: false }
        : { loadingMore: false });
    }
  },

  handleTabTap(event) {
    const key = event.currentTarget.dataset.key;
    if (!key || key === this.data.activeTab) return;
    this.setData({ activeTab: key }, () => {
      if (key !== "mine") this.loadCards(true);
    });
    if (key === "mine") {
      this.loadMyCard();
    }
  },

  handleSearchInput(event) {
    this.setData({ keyword: event.detail.value || "" });
    clearTimeout(this._searchTimer);
    this._searchTimer = setTimeout(() => this.loadCards(true), 360);
  },

  handleSearchConfirm() {
    clearTimeout(this._searchTimer);
    this.loadCards(true);
  },

  handleIndustryTap(event) {
    const value = event.currentTarget.dataset.value || "";
    const activeIndustry = value === "全部" ? "" : value;
    this.setData({
      activeIndustry,
      activeSubIndustry: "",
      industryFilters: buildIndustryFilters(activeIndustry),
      subIndustryOptions: buildSubIndustryOptions(activeIndustry)
    }, () => this.loadCards(true));
  },

  handleSubIndustryTap(event) {
    const value = event.currentTarget.dataset.value || "";
    const activeSubIndustry = value === "全部细分" ? "" : value;
    this.setData({
      activeSubIndustry,
      subIndustryOptions: this.data.subIndustryOptions.map((item) => ({ ...item, active: item.label === value || (value === "全部细分" && item.label === "全部细分") }))
    }, () => this.loadCards(true));
  },

  handleOpenCard(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    if (event.currentTarget.dataset.source === "supply_demand") {
      wx.navigateTo({ url: `/pages/supply-demand-detail/index?id=${encodeURIComponent(id)}` });
      return;
    }
    wx.navigateTo({ url: `/pages/business-opportunity-detail/index?id=${encodeURIComponent(id)}` });
  },

  noop() {},

  handleOpenPublishSheet() {
    const user = getCurrentUser();
    if (!user || !user.id) {
      wx.navigateTo({ url: `/pages/login/index?returnUrl=${encodeURIComponent("/pages/business-opportunity/index?publish=1")}` });
      return;
    }
    this.setData({ publishSheetVisible: true });
  },

  handleClosePublishSheet() {
    this.setData({ publishSheetVisible: false });
  },

  handleChoosePublish(event) {
    const type = event.currentTarget.dataset.type;
    this.setData({ publishSheetVisible: false });
    if (type === "card") {
      this.handleOpenEditor();
      return;
    }
    if (type === "opportunity") {
      wx.navigateTo({ url: "/pages/business-opportunity-publish/index" });
    }
  },

  handleOpenEditor() {
    const user = getCurrentUser();
    if (!user || !user.id) {
      wx.navigateTo({ url: `/pages/login/index?returnUrl=${encodeURIComponent("/pages/business-opportunity/index?tab=mine")}` });
      return;
    }
    const id = this.data.myCard && this.data.myCard.id;
    wx.navigateTo({ url: id ? `/subpackages/workbench/business-card-studio/index?id=${encodeURIComponent(id)}` : "/subpackages/workbench/business-card-studio/index" });
  },

  handleEmptyAction() {
    if (this.data.myCard) {
      this.handleOpenPublishSheet();
      return;
    }
    this.handleOpenEditor();
  },

  handlePreviewMyCard() {
    const id = this.data.myCard && this.data.myCard.id;
    if (id) wx.navigateTo({ url: `/pages/note-preview/index?id=${encodeURIComponent(id)}&preview=1` });
  },

  async loadMyCard() {
    const user = getCurrentUser();
    if (!user || !user.id) {
      this.setData({ myCard: null, myCardLoading: false, myCardChecked: true });
      return;
    }
    this.setData({ myCardLoading: true, myCardError: false });
    try {
      const result = await api.fetchBusinessCardSummary(user.id);
      if ((getCurrentUser() || {}).id !== user.id) return;
      const summary = result.data || {};
      const card = summary.businessCard;
      if (!card) {
        this.setData({ myCard: null, myCardLoading: false, myCardChecked: true });
        return;
      }
      const config = card.visibilityConfig || {};
      const data = config.structuredData || {};
      const opportunity = config.businessOpportunity || {};
      this.setData({
        myCard: mapCard({
          ...card,
          id: card.sourceNoteId || card.id,
          displayName: data.name || (this.data.user && this.data.user.nickname),
          avatarUrl: data.avatarUrl || (this.data.user && this.data.user.avatarUrl),
          jobTitle: data.title || "",
          company: data.company || "",
          city: data.city || "",
          industry: opportunity.industry || data.industry || "",
          subIndustry: opportunity.subIndustry || data.subIndustry || "",
          industryTags: opportunity.industryTags || data.industryTags || [],
          keywords: data.serviceKeywords || [],
          headline: data.headline || "",
          cooperationIntent: opportunity.cooperationIntent || data.cooperationIntent || {}
        }),
        myCardLoading: false,
        myCardChecked: true
      });
    } catch (error) {
      this.setData({ myCardLoading: false, myCardChecked: true, myCardError: true });
    }
  }
});
