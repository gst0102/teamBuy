const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const resourceStore = require("../../stores/resource-store");
const { generateTitleShareImage } = require("../../utils/business-card-share");
const { enrichCard, getCurrentUser } = require("../../utils/dashboard");
const { navigateToResourceEdit, navigateToResourceView } = require("../../utils/resource-navigation");
const { readWorkspaceMode } = require("../../utils/workspace-mode");

const LIBRARY_ENTRY_FILTER_KEY = "teambuy:libraryEntryFilter";
const RADAR_ENTRY_TAB_KEY = "teambuy:radarEntryTab";
const RADAR_SOURCE_FILTER_KEY = "teambuy:radarSourceFilter";
const LIBRARY_SHARE_CANVAS_ID = "libraryShareCanvas";

const PROPERTY_PRICE_PRESETS = [
  { key: "all", label: "不限", min: "", max: "" },
  { key: "under1300", label: "1300以下", min: "", max: "1300" },
  { key: "1300to1800", label: "1300-1800", min: "1300", max: "1800" },
  { key: "1800to2500", label: "1800-2500", min: "1800", max: "2500" },
  { key: "above2500", label: "2500以上", min: "2500", max: "" }
];

const PROPERTY_LAYOUT_FILTERS = ["不限", "一房", "两房", "三房", "公寓"];
const PROPERTY_METRO_FILTERS = ["不限", "地铁", "近地铁"];
const PROPERTY_ELEVATOR_FILTERS = ["不限", "电梯", "楼梯"];
const PROPERTY_AREA_FILTERS = ["不限", "30㎡内", "30-50㎡", "50㎡以上"];
const PROPERTY_PAYMENT_FILTERS = ["不限", "押一付一", "押一付三"];
const PROPERTY_MOVE_IN_FILTERS = ["不限", "随时入住", "本周可住"];
const PROPERTY_STATUS_FILTERS = ["不限", "可租", "已租", "待确认"];
const GROUPBUY_PRICE_PRESETS = [
  { key: "all", label: "不限", min: "", max: "" },
  { key: "under30", label: "30以下", min: "", max: "30" },
  { key: "30to80", label: "30-80", min: "30", max: "80" },
  { key: "80to150", label: "80-150", min: "80", max: "150" },
  { key: "above150", label: "150以上", min: "150", max: "" }
];
const GROUPBUY_PICKUP_FILTERS = ["不限", "自提", "配送", "快递"];
const GROUPBUY_DEADLINE_FILTERS = ["不限", "今日截止", "本周截止"];
const GROUPBUY_STATUS_FILTERS = ["不限", "有订单", "有接龙", "待补价格", "待补取货"];
const SHOWCASE_CONDITION_FILTER_KEY = "teambuy:showcaseConditionFilter";
const DELIVERY_FILTERS = [
  { key: "all", label: "全部" },
  { key: "draft", label: "待整理" },
  { key: "sent", label: "已发客户" },
  { key: "feedback", label: "有反馈" }
];

function createNoteShareId(noteId) {
  return `share_note_${noteId || "note"}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function buildCustomerShareTitle(title) {
  const cleanTitle = String(title || "这份资料").replace(/\s+/g, " ").trim();
  return `${cleanTitle}｜点开查看完整资料`;
}

function isPropertyCard(card = {}) {
  const config = card.visibilityConfig || {};
  const cardType = card.cardType || config.cardType || "";
  const categoryName = card.categoryName || "";
  const text = `${card.title || ""} ${card.projectName || ""} ${card.detailText || ""}`;
  return cardType === "property_listing" || categoryName === "房源" || /房源|小区|户型|看房|租房|买房/.test(text);
}

function isGroupbuyCard(card = {}) {
  const config = card.visibilityConfig || {};
  const cardType = card.cardType || config.cardType || "";
  const categoryName = card.categoryName || "";
  const text = `${card.title || ""} ${card.projectName || ""} ${card.detailText || ""} ${card.summary || ""}`;
  return cardType === "groupbuy_product" || categoryName === "团购" || /团购|接龙|商品|下单|买家|库存/.test(text);
}

function isServiceCard(card = {}) {
  const config = card.visibilityConfig || {};
  const cardType = card.cardType || config.cardType || "";
  const categoryName = card.categoryName || "";
  return cardType === "business_card" || cardType === "service_offer" || categoryName === "名片" || categoryName === "服务";
}

function isBusinessCardResource(card = {}) {
  const config = card.visibilityConfig || {};
  const cardType = card.cardType || config.cardType || "";
  const categoryName = card.categoryName || "";
  return cardType === "business_card" || categoryName === "名片";
}

function isServiceOfferResource(card = {}) {
  const config = card.visibilityConfig || {};
  const cardType = card.cardType || config.cardType || "";
  const categoryName = card.categoryName || "";
  return cardType === "service_offer" || categoryName === "服务";
}

function isDailyCard(card = {}) {
  return !isPropertyCard(card) && !isGroupbuyCard(card) && !isServiceCard(card);
}

function propertyText(card = {}) {
  const structuredData = ((card.visibilityConfig || {}).structuredData) || {};
  return [
    card.title,
    card.projectName,
    card.detailText,
    card.summary,
    card.body,
    card.propertyInfoLine,
    structuredData.price,
    structuredData.layout,
    structuredData.area,
    structuredData.floor,
    structuredData.paymentMethod,
    structuredData.moveInTime,
    structuredData.utilities,
    structuredData.address,
    structuredData.businessArea,
    ...(card.propertyHighlightChips || []),
    ...(card.tagNames || [])
  ].filter(Boolean).join(" ");
}

function propertyRent(card = {}) {
  const text = propertyText(card);
  const labeled = text.match(/租金\s*([0-9]{3,6})/);
  if (labeled) return Number(labeled[1]);
  const unit = text.match(/(^|[^0-9A-Za-z-])([1-9]\d{2,5})\s*(?:元|块|\/月|每月|月租|月)($|[^0-9A-Za-z-])/);
  if (unit) return Number(unit[2]);
  return 0;
}

function propertyArea(card = {}) {
  const text = propertyText(card);
  const matched = text.match(/([1-9]\d{1,2})\s*(?:㎡|平|平方)/);
  return matched ? Number(matched[1]) : 0;
}

function groupbuyText(card = {}) {
  const structuredData = ((card.visibilityConfig || {}).structuredData) || {};
  return [
    card.title,
    card.projectName,
    card.detailText,
    card.summary,
    card.body,
    card.productInfoLine,
    structuredData.productName,
    structuredData.price,
    structuredData.spec,
    structuredData.pickupMethod,
    structuredData.pickupLocation,
    structuredData.deadline,
    structuredData.remark,
    ...(card.productHighlightChips || []),
    ...(card.tagNames || [])
  ].filter(Boolean).join(" ");
}

function groupbuyPrice(card = {}) {
  const structuredData = ((card.visibilityConfig || {}).structuredData) || {};
  const skuConfig = structuredData.skuConfig || {};
  const skuPrices = (skuConfig.skus || [])
    .map((sku) => Number(String(sku.price || "").replace(/[^\d.]/g, "")))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (skuPrices.length) return Math.min(...skuPrices);
  const direct = Number(String(structuredData.price || "").replace(/[^\d.]/g, ""));
  if (Number.isFinite(direct) && direct > 0) return direct;
  const text = groupbuyText(card);
  const labeled = text.match(/(?:¥|￥|价格|团购价|售价|单价)[：:\s]*([1-9]\d{0,4}(?:\.\d{1,2})?)/);
  if (labeled) return Number(labeled[1]);
  const unit = text.match(/([1-9]\d{0,4}(?:\.\d{1,2})?)\s*(?:元|块)(?:\/(?:份|斤|个|盒|件|箱))?/);
  return unit ? Number(unit[1]) : 0;
}

function matchesKeywordFromList(text, keywords = []) {
  return keywords.some((keyword) => text.includes(keyword));
}

function readEntryFilter(options = {}) {
  if (options.mode || options.cardType) {
    const isProperty = options.cardType === "property_listing" || options.mode === "property";
    const isGroupbuy = options.cardType === "groupbuy_product" || options.mode === "groupbuy";
    const isService = options.cardType === "service_workspace" || options.mode === "service";
    const isBusinessCard = options.cardType === "business_card" || options.mode === "business_card";
    const isServiceOffer = options.cardType === "service_offer" || options.mode === "service_offer";
    const isNotes = options.cardType === "notes_workspace" || options.mode === "notes";
    return {
      mode: options.mode || "",
      cardType: options.cardType || "",
      label: isProperty ? "房源资料" : isGroupbuy ? "商品资料" : isBusinessCard ? "我的名片" : isServiceOffer ? "服务方案" : isService ? "名片/服务方案" : isNotes ? "日常资料" : ""
    };
  }
  try {
    const value = wx.getStorageSync(LIBRARY_ENTRY_FILTER_KEY);
    wx.removeStorageSync(LIBRARY_ENTRY_FILTER_KEY);
    if (!value || Date.now() - Number(value.ts || 0) > 120000) return null;
    return value;
  } catch (error) {
    return null;
  }
}

function entryFilterFromWorkspace(userId) {
  const mode = readWorkspaceMode(userId);
  if (mode === "property") {
    return {
      mode: "property",
      cardType: "property_listing",
      label: "房源资料"
    };
  }
  if (mode === "groupbuy") {
    return {
      mode: "groupbuy",
      cardType: "groupbuy_product",
      label: "商品资料"
    };
  }
  if (mode === "service") {
    return {
      mode: "service",
      cardType: "service_workspace",
      label: "名片/服务方案"
    };
  }
  return {
    mode: "notes",
    cardType: "notes_workspace",
    label: "日常资料"
  };
}

Page({
  data: {
    keyword: "",
    activeCategory: "全部",
    activeTag: "全部",
    activeTopicId: "",
    activeTopicName: "",
    categoryFilters: [],
    tagFilters: [],
    topicFilters: [],
    cards: [],
    pendingShare: null,
    categories: [],
    displayCards: [],
    toolsOpen: false,
    viewMode: "list",
    entryFilter: null,
    entryFilterText: "",
    hasPropertyCards: false,
    showPropertyFilters: false,
    hasGroupbuyCards: false,
    showGroupbuyFilters: false,
    groupbuyFiltersOpen: true,
    groupbuyPricePresets: GROUPBUY_PRICE_PRESETS,
    groupbuyPricePreset: "all",
    groupbuyPriceMin: "",
    groupbuyPriceMax: "",
    groupbuyPickupFilters: GROUPBUY_PICKUP_FILTERS,
    groupbuyPickupFilter: "不限",
    groupbuyDeadlineFilters: GROUPBUY_DEADLINE_FILTERS,
    groupbuyDeadlineFilter: "不限",
    groupbuyStatusFilters: GROUPBUY_STATUS_FILTERS,
    groupbuyStatusFilter: "不限",
    propertyFiltersOpen: false,
    propertyPricePresets: PROPERTY_PRICE_PRESETS,
    propertyPricePreset: "all",
    propertyPriceMin: "",
    propertyPriceMax: "",
    propertyLayoutFilters: PROPERTY_LAYOUT_FILTERS,
    propertyLayoutFilter: "不限",
    propertyMetroFilters: PROPERTY_METRO_FILTERS,
    propertyMetroFilter: "不限",
    propertyElevatorFilters: PROPERTY_ELEVATOR_FILTERS,
    propertyElevatorFilter: "不限",
    propertyAreaFilters: PROPERTY_AREA_FILTERS,
    propertyAreaFilter: "不限",
    propertyPaymentFilters: PROPERTY_PAYMENT_FILTERS,
    propertyPaymentFilter: "不限",
    propertyMoveInFilters: PROPERTY_MOVE_IN_FILTERS,
    propertyMoveInFilter: "不限",
    propertyStatusFilters: PROPERTY_STATUS_FILTERS,
    propertyStatusFilter: "不限",
    stats: {
      total: 0,
      pv: 0,
      tags: 0,
      visitors: 0,
      customerActivity: 0
    },
    deliveryFilters: DELIVERY_FILTERS,
    activeDeliveryFilter: "all"
  },
  onLoad(options = {}) {
    this.applyEntryFilter(readEntryFilter(options));
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const entryFilter = readEntryFilter() || entryFilterFromWorkspace(currentUser.id);
    if (entryFilter) this.applyEntryFilter(entryFilter);
    this.loadCards();
  },
  applyEntryFilter(entryFilter) {
    if (!entryFilter) return;
    const isProperty = entryFilter.mode === "property" || entryFilter.cardType === "property_listing";
    const isGroupbuy = entryFilter.mode === "groupbuy" || entryFilter.cardType === "groupbuy_product";
    const isService = entryFilter.mode === "service" || entryFilter.cardType === "service_workspace";
    const isBusinessCard = entryFilter.mode === "business_card" || entryFilter.cardType === "business_card";
    const isServiceOffer = entryFilter.mode === "service_offer" || entryFilter.cardType === "service_offer";
    const isNotes = entryFilter.mode === "notes" || entryFilter.cardType === "notes_workspace";
    this.setData({
      entryFilter: isProperty
        ? { mode: "property", cardType: "property_listing" }
        : isGroupbuy
          ? { mode: "groupbuy", cardType: "groupbuy_product" }
          : isBusinessCard
            ? { mode: "service", cardType: "business_card" }
            : isServiceOffer
              ? { mode: "service", cardType: "service_offer" }
          : isService
            ? { mode: "service", cardType: "service_workspace" }
            : isNotes
              ? { mode: "notes", cardType: "notes_workspace" }
          : entryFilter,
      entryFilterText: isProperty ? "当前只看房源资料" : isGroupbuy ? "当前只看商品资料" : isBusinessCard ? "当前只看我的名片" : isServiceOffer ? "当前只看服务方案" : isService ? "当前只看名片/服务方案" : isNotes ? "当前只看日常资料" : (entryFilter.label || "当前筛选资料"),
      activeCategory: "全部",
      activeTag: "全部",
      activeTopicId: "",
      activeTopicName: "",
      viewMode: "list",
      propertyFiltersOpen: false,
      groupbuyFiltersOpen: true
    });
  },
  handleKeywordChange(event) {
    this.setData({ keyword: event.detail.value });
  },
  async loadCards() {
    const currentUser = getCurrentUser();
    try {
      const [cardsData, categories, topicsRes] = await Promise.all([
        resourceStore.listCards({ ownerUserId: currentUser ? currentUser.id : "" }, { force: true }),
        resourceStore.listCategories(currentUser ? currentUser.id : "", { force: true }),
        api.fetchTopics(currentUser ? currentUser.id : "").catch(() => ({ data: [] }))
      ]);
      const categoriesById = categories.reduce((result, item) => {
        result[item.id] = item.name;
        return result;
      }, {});
      const cards = (cardsData || []).map((card) => enrichCard(card, categoriesById));
      const scopedCards = this.scopeCardsByEntryFilter(cards);
      const categoryFilters = this.buildCountFilters(scopedCards, (card) => card.categoryName);
      const tagItems = scopedCards.flatMap((card) => (card.tagNames || []).map((tag) => ({ tag })));
      const tagFilters = this.buildCountFilters(tagItems, (item) => item.tag);
      const topicFilters = this.buildTopicFilters(scopedCards, topicsRes.data || []);
      const stats = {
        total: scopedCards.length,
        pv: scopedCards.reduce((sum, card) => sum + card.stats.pv, 0),
        tags: new Set(tagItems.map((item) => item.tag)).size,
        visitors: scopedCards.reduce((sum, card) => sum + card.stats.uv, 0),
        customerActivity: scopedCards.reduce((sum, card) => sum + (card.customerActivity || 0), 0)
      };
      this.setData({
        cards,
        categories,
        categoryFilters,
        tagFilters,
        topicFilters,
        stats,
        hasPropertyCards: cards.some((card) => isPropertyCard(card)),
        hasGroupbuyCards: cards.some((card) => isGroupbuyCard(card))
      });
      this.applyFilter();
    } catch (error) {
      wx.showToast({ title: error.detail || "加载资源失败", icon: "none" });
    }
  },
  scopeCardsByEntryFilter(cards) {
    const entryFilter = this.data.entryFilter || {};
    if (entryFilter.cardType === "property_listing") {
      return (cards || []).filter((card) => isPropertyCard(card));
    }
    if (entryFilter.cardType === "groupbuy_product") {
      return (cards || []).filter((card) => isGroupbuyCard(card));
    }
    if (entryFilter.cardType === "service_workspace") {
      return (cards || []).filter((card) => isServiceCard(card));
    }
    if (entryFilter.cardType === "business_card") {
      return (cards || []).filter((card) => isBusinessCardResource(card));
    }
    if (entryFilter.cardType === "service_offer") {
      return (cards || []).filter((card) => isServiceOfferResource(card));
    }
    if (entryFilter.cardType === "notes_workspace") {
      return (cards || []).filter((card) => isDailyCard(card));
    }
    return cards || [];
  },
  buildCountFilters(items, resolveName) {
    const counts = items.reduce((result, item) => {
      const name = resolveName(item);
      if (!name) return result;
      result[name] = (result[name] || 0) + 1;
      return result;
    }, {});
    return [
      { name: "全部", count: items.length },
      ...Object.keys(counts)
        .sort()
        .map((name) => ({ name, count: counts[name] }))
    ];
  },
  buildTopicFilters(cards = [], topics = []) {
    const topicMap = {};
    (topics || []).forEach((topic) => {
      if (topic && topic.id) {
        topicMap[topic.id] = { id: topic.id, name: topic.name || "未命名专题", count: 0 };
      }
    });
    (cards || []).forEach((card) => {
      const config = card.visibilityConfig || {};
      const cardTopics = Array.isArray(config.topics) ? config.topics : [];
      const topicIds = Array.isArray(config.topicIds) ? config.topicIds : [];
      cardTopics.forEach((topic) => {
        if (!topic || !topic.id) return;
        if (!topicMap[topic.id]) topicMap[topic.id] = { id: topic.id, name: topic.name || "未命名专题", count: 0 };
        topicMap[topic.id].count += 1;
      });
      topicIds.forEach((topicId) => {
        if (!topicId || cardTopics.some((topic) => topic && topic.id === topicId)) return;
        if (!topicMap[topicId]) topicMap[topicId] = { id: topicId, name: "未命名专题", count: 0 };
        topicMap[topicId].count += 1;
      });
    });
    const rows = Object.values(topicMap)
      .filter((topic) => topic.count > 0)
      .sort((a, b) => b.count - a.count || String(a.name).localeCompare(String(b.name), "zh-Hans-CN"));
    return [{ id: "", name: "全部", count: cards.length }, ...rows];
  },
  applyFilter() {
    const keyword = this.data.keyword.trim().toLowerCase();
    const hasActivePropertyFilters = this.hasActivePropertyFilters();
    const hasActiveGroupbuyFilters = this.hasActiveGroupbuyFilters();
    const isPropertyMode =
      (this.data.entryFilter && this.data.entryFilter.cardType === "property_listing") ||
      this.data.activeCategory === "房源" ||
      this.data.activeCategory === "房产" ||
      hasActivePropertyFilters;
    const isGroupbuyMode =
      (this.data.entryFilter && this.data.entryFilter.cardType === "groupbuy_product") ||
      this.data.activeCategory === "商品" ||
      this.data.activeCategory === "团购" ||
      hasActiveGroupbuyFilters;
    const displayCards = this.data.cards.filter((card) => {
      if (this.data.entryFilter && this.data.entryFilter.cardType === "property_listing" && !isPropertyCard(card)) {
        return false;
      }
      if (this.data.entryFilter && this.data.entryFilter.cardType === "groupbuy_product" && !isGroupbuyCard(card)) {
        return false;
      }
      if (this.data.entryFilter && this.data.entryFilter.cardType === "service_workspace" && !isServiceCard(card)) {
        return false;
      }
      if (this.data.entryFilter && this.data.entryFilter.cardType === "business_card" && !isBusinessCardResource(card)) {
        return false;
      }
      if (this.data.entryFilter && this.data.entryFilter.cardType === "service_offer" && !isServiceOfferResource(card)) {
        return false;
      }
      if (this.data.entryFilter && this.data.entryFilter.cardType === "notes_workspace" && !isDailyCard(card)) {
        return false;
      }
      const matchCategory = this.data.activeCategory === "全部" || card.categoryName === this.data.activeCategory;
      const matchTag = this.data.activeTag === "全部" || (card.tagNames || []).includes(this.data.activeTag);
      const config = card.visibilityConfig || {};
      const topicIds = Array.isArray(config.topicIds) ? config.topicIds : [];
      const cardTopics = Array.isArray(config.topics) ? config.topics : [];
      const matchTopic = !this.data.activeTopicId || topicIds.includes(this.data.activeTopicId) || cardTopics.some((topic) => topic && topic.id === this.data.activeTopicId);
      const matchPropertyFilters = !isPropertyMode || this.matchPropertyFilters(card);
      const matchGroupbuyFilters = !isGroupbuyMode || this.matchGroupbuyFilters(card);
      const haystack = [
        card.title,
        card.projectName,
        card.detailText,
        card.sourceUrl,
        card.categoryName,
        ...(card.tagNames || []),
        ...cardTopics.map((topic) => topic && topic.name).filter(Boolean)
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const matchKeyword = !keyword || haystack.includes(keyword);
      const matchDelivery = this.matchDeliveryFilter(card);
      return matchCategory && matchTag && matchTopic && matchKeyword && matchPropertyFilters && matchGroupbuyFilters && matchDelivery;
    }).sort((a, b) => {
      const hotDiff = Number(b.hasHotCustomerSignal) - Number(a.hasHotCustomerSignal);
      if (hotDiff) return hotDiff;
      const signalDiff = Number(b.hasCustomerSignal) - Number(a.hasCustomerSignal);
      if (signalDiff) return signalDiff;
      const activityDiff = (b.customerActivity || 0) - (a.customerActivity || 0);
      if (activityDiff) return activityDiff;
      return (b.stats.pv || 0) - (a.stats.pv || 0);
    });
    this.setData({ displayCards, showPropertyFilters: isPropertyMode, showGroupbuyFilters: isGroupbuyMode });
  },
  matchDeliveryFilter(card = {}) {
    const filter = this.data.activeDeliveryFilter || "all";
    if (filter === "all") return true;
    const statusText = (card.deliveryStatus && card.deliveryStatus.text) || "";
    if (filter === "draft") return /待发送|等待客户打开/.test(statusText) && !(card.stats && (card.stats.pv || card.stats.uv || card.stats.shareCount));
    if (filter === "sent") return !!((card.stats && card.stats.shareCount) || !/待发送|等待客户打开/.test(statusText) || (card.stats && (card.stats.pv || card.stats.uv)));
    if (filter === "feedback") return !!(card.customerActivity || card.hasCustomerSignal || (card.customerSummary && (card.customerSummary.pending || card.customerSummary.consult || card.customerSummary.leadContact || card.customerSummary.appointment || card.customerSummary.orderIntent || card.customerSummary.relayIntent)));
    return true;
  },
  handleDeliveryFilter(event) {
    this.setData({ activeDeliveryFilter: event.currentTarget.dataset.key || "all" }, () => this.applyFilter());
  },
  hasActivePropertyFilters() {
    return Boolean(
      this.data.propertyPriceMin ||
      this.data.propertyPriceMax ||
      this.data.propertyLayoutFilter !== "不限" ||
      this.data.propertyMetroFilter !== "不限" ||
      this.data.propertyElevatorFilter !== "不限" ||
      this.data.propertyAreaFilter !== "不限" ||
      this.data.propertyPaymentFilter !== "不限" ||
      this.data.propertyMoveInFilter !== "不限" ||
      this.data.propertyStatusFilter !== "不限"
    );
  },
  hasActiveGroupbuyFilters() {
    return Boolean(
      this.data.groupbuyPriceMin ||
      this.data.groupbuyPriceMax ||
      this.data.groupbuyPickupFilter !== "不限" ||
      this.data.groupbuyDeadlineFilter !== "不限" ||
      this.data.groupbuyStatusFilter !== "不限"
    );
  },
  handleClearEntryFilter() {
    this.setData({
      entryFilter: null,
      entryFilterText: "",
      activeCategory: "全部",
      activeTag: "全部",
      activeTopicId: "",
      activeTopicName: ""
    });
    this.loadCards();
  },
  handleSearch() {
    this.applyFilter();
  },
  handleFilter(event) {
    this.setData({ activeCategory: event.currentTarget.dataset.filter });
    this.applyFilter();
  },
  handleTagFilter(event) {
    this.setData({ activeTag: event.currentTarget.dataset.tag });
    this.applyFilter();
  },
  handleTopicFilter(event) {
    const topicId = event.currentTarget.dataset.id || "";
    const topic = (this.data.topicFilters || []).find((item) => item.id === topicId);
    this.setData({
      activeTopicId: topicId,
      activeTopicName: topic && topicId ? topic.name : ""
    });
    this.applyFilter();
  },
  handleCreateShowcaseFromTopic() {
    const topicId = this.data.activeTopicId;
    if (!topicId) return;
    wx.navigateTo({
      url: `/pages/showcase-edit/index?mode=notes&topicId=${encodeURIComponent(topicId)}&topicName=${encodeURIComponent(this.data.activeTopicName || "专题")}`
    });
  },
  matchPropertyFilters(card) {
    if (!isPropertyCard(card)) return false;
    const text = propertyText(card);
    const rent = propertyRent(card);
    const area = propertyArea(card);
    const min = Number(this.data.propertyPriceMin || 0);
    const max = Number(this.data.propertyPriceMax || 0);
    if (min && (!rent || rent < min)) return false;
    if (max && (!rent || rent > max)) return false;
    if (this.data.propertyLayoutFilter !== "不限") {
      const layoutMap = {
        一房: ["一房", "一室", "公寓一房"],
        两房: ["两房", "两室", "二房", "二室"],
        三房: ["三房", "三室"],
        公寓: ["公寓"]
      };
      if (!matchesKeywordFromList(text, layoutMap[this.data.propertyLayoutFilter] || [this.data.propertyLayoutFilter])) return false;
    }
    if (this.data.propertyMetroFilter !== "不限") {
      const keywords = this.data.propertyMetroFilter === "近地铁" ? ["近地铁", "地铁口", "地铁站", "步行"] : ["地铁", "地铁口", "地铁站"];
      if (!matchesKeywordFromList(text, keywords)) return false;
    }
    if (this.data.propertyElevatorFilter !== "不限" && !text.includes(this.data.propertyElevatorFilter)) return false;
    if (this.data.propertyAreaFilter !== "不限") {
      if (!area) return false;
      if (this.data.propertyAreaFilter === "30㎡内" && area > 30) return false;
      if (this.data.propertyAreaFilter === "30-50㎡" && (area < 30 || area > 50)) return false;
      if (this.data.propertyAreaFilter === "50㎡以上" && area < 50) return false;
    }
    if (this.data.propertyPaymentFilter !== "不限" && !text.includes(this.data.propertyPaymentFilter)) return false;
    if (this.data.propertyMoveInFilter !== "不限") {
      const moveMap = {
        随时入住: ["随时入住", "拎包入住", "空置"],
        本周可住: ["本周可住", "本周入住"]
      };
      if (!matchesKeywordFromList(text, moveMap[this.data.propertyMoveInFilter] || [this.data.propertyMoveInFilter])) return false;
    }
    if (this.data.propertyStatusFilter !== "不限") {
      const statusMap = {
        可租: ["可租", "在租", "可看", "空置"],
        已租: ["已租", "已出租"],
        待确认: ["待确认", "待核实", "待补"]
      };
      if (!matchesKeywordFromList(text, statusMap[this.data.propertyStatusFilter] || [this.data.propertyStatusFilter])) return false;
    }
    return true;
  },
  matchGroupbuyFilters(card) {
    if (!isGroupbuyCard(card)) return false;
    const text = groupbuyText(card);
    const price = groupbuyPrice(card);
    const min = Number(this.data.groupbuyPriceMin || 0);
    const max = Number(this.data.groupbuyPriceMax || 0);
    if (min && (!price || price < min)) return false;
    if (max && (!price || price > max)) return false;
    if (this.data.groupbuyPickupFilter !== "不限" && !text.includes(this.data.groupbuyPickupFilter)) return false;
    if (this.data.groupbuyDeadlineFilter !== "不限") {
      if (this.data.groupbuyDeadlineFilter === "今日截止" && !matchesKeywordFromList(text, ["今日截止", "今天截止", "今晚截止", "当天截止"])) return false;
      if (this.data.groupbuyDeadlineFilter === "本周截止" && !matchesKeywordFromList(text, ["本周截止", "周末截止", "这周截止", "截止"])) return false;
    }
    if (this.data.groupbuyStatusFilter !== "不限") {
      const summary = card.customerSummary || {};
      if (this.data.groupbuyStatusFilter === "有订单" && !(summary.orderIntent || summary.relayIntent || card.customerActivity)) return false;
      if (this.data.groupbuyStatusFilter === "有接龙" && !(summary.relayIntent || ((card.stats || {}).relayCount))) return false;
      if (this.data.groupbuyStatusFilter === "待补价格" && groupbuyPrice(card)) return false;
      if (this.data.groupbuyStatusFilter === "待补取货" && matchesKeywordFromList(text, ["自提", "配送", "快递", "取货"])) return false;
    }
    return true;
  },
  handleTogglePropertyFilters() {
    this.setData({ propertyFiltersOpen: !this.data.propertyFiltersOpen });
  },
  handleToggleGroupbuyFilters() {
    this.setData({ groupbuyFiltersOpen: !this.data.groupbuyFiltersOpen });
  },
  handlePropertyPricePreset(event) {
    const key = event.currentTarget.dataset.key || "all";
    const preset = PROPERTY_PRICE_PRESETS.find((item) => item.key === key) || PROPERTY_PRICE_PRESETS[0];
    this.setData({
      propertyPricePreset: preset.key,
      propertyPriceMin: preset.min,
      propertyPriceMax: preset.max
    }, () => this.applyFilter());
  },
  handlePropertyPriceInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = String(event.detail.value || "").replace(/[^\d]/g, "");
    this.setData({
      [key]: value,
      propertyPricePreset: "custom"
    }, () => this.applyFilter());
  },
  handlePropertyQuickFilter(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.currentTarget.dataset.value || "不限";
    this.setData({ [key]: value }, () => this.applyFilter());
  },
  handleResetPropertyFilters() {
    this.setData({
      propertyPricePreset: "all",
      propertyPriceMin: "",
      propertyPriceMax: "",
      propertyLayoutFilter: "不限",
      propertyMetroFilter: "不限",
      propertyElevatorFilter: "不限",
      propertyAreaFilter: "不限",
      propertyPaymentFilter: "不限",
      propertyMoveInFilter: "不限",
      propertyStatusFilter: "不限"
    }, () => this.applyFilter());
  },
  handleGroupbuyPricePreset(event) {
    const key = event.currentTarget.dataset.key || "all";
    const preset = GROUPBUY_PRICE_PRESETS.find((item) => item.key === key) || GROUPBUY_PRICE_PRESETS[0];
    this.setData({
      groupbuyPricePreset: preset.key,
      groupbuyPriceMin: preset.min,
      groupbuyPriceMax: preset.max
    }, () => this.applyFilter());
  },
  handleGroupbuyPriceInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = String(event.detail.value || "").replace(/[^\d.]/g, "");
    this.setData({
      [key]: value,
      groupbuyPricePreset: "custom"
    }, () => this.applyFilter());
  },
  handleGroupbuyQuickFilter(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.currentTarget.dataset.value || "不限";
    this.setData({ [key]: value }, () => this.applyFilter());
  },
  handleResetGroupbuyFilters() {
    this.setData({
      groupbuyPricePreset: "all",
      groupbuyPriceMin: "",
      groupbuyPriceMax: "",
      groupbuyPickupFilter: "不限",
      groupbuyDeadlineFilter: "不限",
      groupbuyStatusFilter: "不限"
    }, () => this.applyFilter());
  },
  handleCreateShowcaseFromCurrentFilter() {
    try {
      wx.setStorageSync(SHOWCASE_CONDITION_FILTER_KEY, {
        ts: Date.now(),
        priceMin: this.data.propertyPriceMin,
        priceMax: this.data.propertyPriceMax,
        layout: this.data.propertyLayoutFilter,
        metro: this.data.propertyMetroFilter,
        elevator: this.data.propertyElevatorFilter,
        area: this.data.propertyAreaFilter,
        payment: this.data.propertyPaymentFilter,
        moveIn: this.data.propertyMoveInFilter,
        status: this.data.propertyStatusFilter
      });
    } catch (error) {}
    wx.navigateTo({ url: "/pages/showcase-edit/index?mode=property&method=condition" });
  },
  handleCreateGroupbuyShowcaseFromCurrentFilter() {
    try {
      wx.setStorageSync(SHOWCASE_CONDITION_FILTER_KEY, {
        ts: Date.now(),
        mode: "groupbuy",
        priceMin: this.data.groupbuyPriceMin,
        priceMax: this.data.groupbuyPriceMax,
        pickup: this.data.groupbuyPickupFilter,
        deadline: this.data.groupbuyDeadlineFilter
      });
    } catch (error) {}
    wx.navigateTo({ url: "/pages/showcase-edit/index?mode=groupbuy&method=condition" });
  },
  handleViewModeChange(event) {
    this.setData({ viewMode: event.currentTarget.dataset.mode || "list" });
  },
  handleOpen(event) {
    const id = event.currentTarget.dataset.id || event.detail.id;
    const card = this.data.cards.find((item) => item.id === id) || id;
    navigateToResourceEdit(card);
  },
  handleManage(event) {
    const id = event.currentTarget.dataset.id || event.detail.id;
    const card = this.data.cards.find((item) => item.id === id) || {};
    const noteId = card.sourceNoteId || "";
    if (noteId && isGroupbuyCard(card)) {
      wx.navigateTo({ url: `/pages/orders/index?role=seller&noteId=${encodeURIComponent(noteId)}` });
      return;
    }
    const summary = card.customerSummary || {};
    const hasNoteCustomerData = noteId && (
      card.customerActivity ||
      summary.total ||
      summary.pending ||
      summary.leads ||
      summary.leadContact ||
      summary.appointment ||
      summary.consult
    );
    if (hasNoteCustomerData) {
      try {
        wx.setStorageSync(RADAR_ENTRY_TAB_KEY, "followup");
        wx.setStorageSync(RADAR_SOURCE_FILTER_KEY, {
          ts: Date.now(),
          noteId,
          resourceId: id,
          title: card.title || "这条资料"
        });
      } catch (error) {}
      wx.switchTab({ url: "/pages/visits/index" });
      return;
    }
    wx.navigateTo({ url: `/pages/manager/index?id=${id}` });
  },
  handleOpenMessages() {
    messagePlugin.openMessageCenter();
  },
  handleView(event) {
    const id = event.currentTarget.dataset.id;
    const card = this.data.cards.find((item) => item.id === id) || id;
    navigateToResourceView(card);
  },
  handleMoreCardActions(event) {
    const id = event.currentTarget.dataset.id;
    const card = this.data.cards.find((item) => item.id === id);
    if (!card) return;
    const isGroupbuy = isGroupbuyCard(card);
    const isService = isServiceCard(card);
    const isProperty = isPropertyCard(card);
    const actionItems = isGroupbuy
      ? ["编辑商品", "加入合集", "复用成新商品", "复制文案", "删除资料"]
      : isService
        ? ["编辑资料", "加入案例合集", "复用成新资料", "复制文案", "删除资料"]
        : isProperty
          ? ["编辑房源", "加入合集", "复制文案", "删除资料"]
          : ["编辑资料", "加入合集", "复制文案", "删除资料"];
    wx.showActionSheet({
      itemList: actionItems,
      success: (res) => {
        const index = res.tapIndex;
        const payload = { currentTarget: { dataset: { id } }, detail: { id } };
        if (index === 0) this.handleOpen(payload);
        if (index === 1) this.handleAddToCollection(payload);
        if (isGroupbuy && index === 2) this.handleDuplicateProduct(payload);
        if (isService && index === 2) this.handleDuplicateServiceResource(payload);
        if (index === (isGroupbuy || isService ? 3 : 2)) this.handleCopySummary(payload);
        if (index === (isGroupbuy || isService ? 4 : 3)) this.handleDelete(payload);
      }
    });
  },
  async handleDuplicateProduct(event) {
    const id = event.currentTarget.dataset.id || event.detail.id;
    const card = this.data.cards.find((item) => item.id === id) || {};
    const noteId = card.sourceNoteId || "";
    const currentUser = getCurrentUser();
    if (!noteId || !currentUser) {
      wx.showToast({ title: "当前商品暂不能复用", icon: "none" });
      return;
    }
    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: "复用成新商品",
        content: "会复制商品文案、图片、规格和取货设置，不复制旧接龙、订单、访客和统计。复制后请重新检查价格、取货和截止时间。",
        confirmText: "复用",
        cancelText: "取消",
        success: (res) => resolve(Boolean(res.confirm)),
        fail: () => resolve(false)
      });
    });
    if (!confirmed) return;
    try {
      const res = await api.duplicateNote(noteId, currentUser.id);
      const note = res.data || {};
      wx.showToast({ title: "已生成新商品", icon: "success" });
      wx.navigateTo({ url: `/pages/note-edit/index?id=${note.id}` });
    } catch (error) {
      wx.showToast({ title: error.detail || "复用失败", icon: "none" });
    }
  },
  async handleDuplicateServiceResource(event) {
    const id = event.currentTarget.dataset.id || event.detail.id;
    const card = this.data.cards.find((item) => item.id === id) || {};
    const noteId = card.sourceNoteId || "";
    const currentUser = getCurrentUser();
    if (!noteId || !currentUser) {
      wx.showToast({ title: "当前资料暂不能复用", icon: "none" });
      return;
    }
    const config = card.visibilityConfig || {};
    const cardType = card.cardType || config.cardType || "";
    const isBusinessCard = cardType === "business_card";
    const label = isBusinessCard ? "名片" : "服务方案";
    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: `复用成新${label}`,
        content: `会复制${label}内容、图片、模板和联系方式，不复制旧访客、留言、预约和统计。复制后请重新检查客户页效果。`,
        confirmText: "复用",
        cancelText: "取消",
        success: (res) => resolve(Boolean(res.confirm)),
        fail: () => resolve(false)
      });
    });
    if (!confirmed) return;
    try {
      const res = await api.duplicateNote(noteId, currentUser.id);
      const note = res.data || {};
      wx.showToast({ title: `已生成新${label}`, icon: "success" });
      wx.navigateTo({ url: isBusinessCard ? `/pages/business-card-studio/index?id=${note.id}` : `/pages/service-offer-studio/index?id=${note.id}` });
    } catch (error) {
      wx.showToast({ title: error.detail || "复用失败", icon: "none" });
    }
  },
  handleOpenPendingImports() {
    wx.navigateTo({ url: "/pages/imports/index" });
  },
  handleOpenNotes() {
    wx.navigateTo({ url: "/pages/notes/index" });
  },
  handleOpenTopics() {
    wx.navigateTo({ url: "/pages/topics/index" });
  },
  handleManualAdd() {
    const currentUser = getCurrentUser();
    const entryFilter = this.data.entryFilter || {};
    const mode = entryFilter.mode || readWorkspaceMode(currentUser && currentUser.id) || "";
    if (entryFilter.cardType === "business_card") {
      wx.navigateTo({ url: "/pages/business-card-studio/index" });
      return;
    }
    if (entryFilter.cardType === "service_offer") {
      wx.navigateTo({ url: "/pages/service-offer-studio/index" });
      return;
    }
    if (mode === "groupbuy") {
      wx.navigateTo({ url: "/pages/resource-create/index?workspaceMode=groupbuy&scene=groupbuy_product" });
      return;
    }
    if (mode === "property") {
      wx.navigateTo({ url: "/pages/resource-create/index?workspaceMode=property&scene=property_listing" });
      return;
    }
    if (mode === "service") {
      wx.navigateTo({ url: "/pages/service-offer-studio/index" });
      return;
    }
    wx.navigateTo({ url: "/pages/resource-create/index?workspaceMode=notes&scene=quick_note" });
  },
  handleToggleTools() {
    this.setData({ toolsOpen: !this.data.toolsOpen });
  },
  handleAddToCollection(event) {
    const id = event && (event.currentTarget.dataset.id || event.detail.id);
    const card = this.data.cards.find((item) => item.id === id);
    if (card && isGroupbuyCard(card)) {
      wx.navigateTo({ url: "/pages/showcase-edit/index?mode=groupbuy" });
      return;
    }
    if (card && isServiceCard(card)) {
      wx.navigateTo({ url: "/pages/showcase-edit/index?mode=service" });
      return;
    }
    if (card && card.sourceNoteId) {
      wx.navigateTo({ url: `/pages/showcase-edit/index?mode=notes&noteId=${encodeURIComponent(card.sourceNoteId)}` });
      return;
    }
    wx.switchTab({ url: "/pages/showcases/index" });
  },
  handleOpenBusinessCardStudio() {
    wx.navigateTo({ url: "/pages/business-card-studio/index" });
  },
  handleOpenServiceOfferStudio() {
    wx.navigateTo({ url: "/pages/service-offer-studio/index" });
  },
  handleTagPlaceholder() {
    wx.navigateTo({ url: "/pages/tag-manage/index" });
  },
  handleCopySummary(event) {
    const card = this.data.cards.find((item) => item.id === event.currentTarget.dataset.id);
    if (!card) return;
    wx.setClipboardData({
      data: `${card.title}\n${card.detailText || ""}\n${card.sourceUrl || ""}`.trim()
    });
  },
  markCardShared(cardId) {
    if (!cardId) return;
    const updateCard = (card) => {
      if (!card || card.id !== cardId) return card;
      const stats = {
        ...(card.stats || {}),
        shareCount: Number(((card.stats || {}).shareCount) || 0) + 1,
        latestShareAt: new Date().toISOString()
      };
      return {
        ...card,
        stats,
        deliveryStatus: {
          text: "已发出，等待打开",
          tone: "sent",
          hint: "客户打开后会进入雷达"
        }
      };
    };
    this.setData({
      cards: (this.data.cards || []).map(updateCard),
      displayCards: (this.data.displayCards || []).map(updateCard)
    });
  },
  handleDelete(event) {
    const cardId = event.currentTarget.dataset.id;
    const currentUser = getCurrentUser();
    if (!cardId || !currentUser) return;
    const card = this.data.cards.find((item) => item.id === cardId) || {};
    const noteOnlyResource = card.sourceNoteId && String(card.id || "").indexOf("note_card_") === 0;
    wx.showModal({
      title: "删除资料",
      content: "删除后该资料和相关互动记录都会移除，确认删除吗？",
      confirmColor: "#ff5d5d",
      success: async ({ confirm }) => {
        if (!confirm) return;
        try {
          if (noteOnlyResource) {
            await api.deleteNote(card.sourceNoteId, currentUser.id);
          } else {
            await api.deleteCard(cardId, currentUser.id);
          }
          resourceStore.invalidateOwner(currentUser.id);
          wx.showToast({ title: "已删除", icon: "success" });
          this.loadCards();
        } catch (error) {
          wx.showToast({ title: error.detail || "删除失败", icon: "none" });
        }
      }
    });
  },
  async prepareShare(event) {
    const dataset = (event && event.currentTarget && event.currentTarget.dataset) || {};
    const cardId = dataset.id || "";
    const card = (this.data.cards || []).find((item) => item.id === cardId) || {};
    const cover = dataset.cover || card.coverDisplayUrl || card.coverUrl || "";
    const pendingShare = {
      id: cardId,
      noteId: dataset.noteId || card.sourceNoteId || "",
      title: dataset.title || card.title || "资料详情",
      cover,
      imageUrl: ""
    };
    this.setData({ pendingShare });
    if (!pendingShare.noteId) return;
    try {
      const imagePath = await generateTitleShareImage(this, LIBRARY_SHARE_CANVAS_ID, {
        title: pendingShare.title,
        summary: card.summary || card.subtitle || "",
        badge: card.categoryName || (card.cardType === "groupbuy_product" ? "商品" : "资料"),
        hint: "打开小程序查看完整资料",
        growthHint: "我也想做同款"
      });
      if (imagePath && this.data.pendingShare && this.data.pendingShare.id === pendingShare.id) {
        this.setData({
          pendingShare: {
            ...this.data.pendingShare,
            imageUrl: imagePath
          }
        });
      }
    } catch (error) {}
  },
  onShareAppMessage(options) {
    const dataset = options && options.target && options.target.dataset ? options.target.dataset : {};
    const cardId = dataset.id || "";
    const card = this.data.cards.find((item) => item.id === cardId) || {};
    const pendingShare = this.data.pendingShare || {};
    const noteId = dataset.noteId || pendingShare.noteId || card.sourceNoteId || "";
    const title = dataset.title || pendingShare.title || card.title || "资料详情";
    const imageUrl = pendingShare.imageUrl || "";
    const user = getCurrentUser();
    if (!noteId) {
      wx.showToast({ title: "这条资料暂不能直接发客户", icon: "none" });
      return {
        title,
        path: "/pages/library/index",
        imageUrl
      };
    }
    const shareId = createNoteShareId(noteId);
    const shareFromUserId = user ? user.id : "";
    if (shareFromUserId) {
      api.recordNoteView(noteId, {
        eventType: "share",
        viewerUserId: shareFromUserId,
        shareId,
        shareFromUserId,
        scene: "library_send_customer",
        referrer: "library"
      }).catch(() => {});
    }
    this.markCardShared(cardId);
    wx.showToast({ title: "已生成可追踪资料", icon: "none" });
    return {
      title: buildCustomerShareTitle(title),
      path: `/pages/note-preview/index?id=${encodeURIComponent(noteId)}&sid=${encodeURIComponent(shareId)}&from=${encodeURIComponent(shareFromUserId)}&src=library_send_customer`,
      imageUrl
    };
  }
});
