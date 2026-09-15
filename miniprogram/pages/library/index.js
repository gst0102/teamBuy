const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const resourceStore = require("../../stores/resource-store");
const { enrichCard, formatTime, getCurrentUser } = require("../../utils/dashboard");
const { navigateToNoteEditor, navigateToResourceEdit, navigateToResourceView } = require("../../utils/resource-navigation");
const { buildNoteShareTitle, getNoteShareSnapshotState, getShareImageUrlFromState, getShareSourceRevision, isShareImageUrl, prepareNoteShareSnapshot, setShareMenuEnabled, NOTE_SHARE_CARD_STYLE_VERSION } = require("../../plugins/share-snapshot/index");
const subscription = require("../../services/subscription");

const LIBRARY_ENTRY_FILTER_KEY = "teambuy:libraryEntryFilter";
const LIBRARY_PAGE_SIZE = 10;
const SYSTEM_PLACEHOLDER_TEXTS = new Set([
  "未命名笔记",
  "未命名资料",
  "未命名房源",
  "未命名商品",
  "未命名服务方案",
  "手动创建的普通笔记",
  "手动创建，可继续补充内容。",
  "手动创建，可继续补充内容"
]);

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
  { key: "draft", label: "未发送" },
  { key: "sent", label: "已发送" },
  { key: "opened", label: "已打开" },
  { key: "feedback", label: "有反馈" }
];
const LIBRARY_TYPE_FILTERS = [
  { key: "all", label: "全部" },
  { key: "property", label: "房源" },
  { key: "groupbuy", label: "商品" },
  { key: "service", label: "服务方案" },
  { key: "business_card", label: "电子名片" },
  { key: "link", label: "链接" },
  { key: "daily", label: "普通资料" }
];

function openResourceOperations(resourceId, noteId, title) {
  if (!resourceId && !noteId) return;
  const params = [];
  if (resourceId) params.push(`resourceId=${encodeURIComponent(resourceId)}`);
  if (noteId) params.push(`noteId=${encodeURIComponent(noteId)}`);
  if (title) params.push(`title=${encodeURIComponent(title)}`);
  wx.navigateTo({ url: `/subpackages/workbench/resource-analytics/index?${params.join("&")}` });
}

function createNoteShareId(noteId) {
  return `share_note_${noteId || "note"}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function getPreparedLibraryShareImage(card = {}, shareImages = {}) {
  const prepared = card && card.id ? shareImages[card.id] : null;
  const user = getCurrentUser() || {};
  const currentState = getNoteShareSnapshotState(card, user.id, user);
  const noteId = String(card.sourceNoteId || card.id || "");
  const sourceRevision = String(currentState.sourceRevision || getShareSourceRevision("note", card) || "");
  const styleId = String(currentState.styleId || NOTE_SHARE_CARD_STYLE_VERSION);
  const fingerprint = String(currentState.fingerprint || "");
  if (
    prepared
    && isShareImageUrl(prepared.url)
    && (!prepared.noteId || String(prepared.noteId) === noteId)
    && String(prepared.sourceRevision || "") === sourceRevision
    && String(prepared.styleId || "") === styleId
    && (!fingerprint || String(prepared.fingerprint || "") === fingerprint)
  ) {
    return String(prepared.url).trim();
  }
  return getShareImageUrlFromState(currentState);
}

// The list endpoint historically returned the share state in different
// places.  Keep one authoritative resolver so cached/legacy rows cannot make
// the action button and the more-menu disagree about the same card.
function getCardShareState(card = {}) {
  const config = card.visibilityConfig || {};
  return card.shareState
    || card.sourceNoteShareState
    || config.shareState
    || (card.sharePublished ? "published" : "private");
}

function isCardContentReady(card = {}) {
  const meaningful = (value) => {
    const clean = String(value || "").trim();
    return clean && !SYSTEM_PLACEHOLDER_TEXTS.has(clean) ? clean : "";
  };
  const title = meaningful(card.title);
  const detail = meaningful(card.detailText || card.summary || card.body);
  const cover = String(card.coverUrl || card.coverDisplayUrl || "").trim();
  return Boolean(card.sourceNoteId)
    && Boolean(title)
    && Boolean(cover || detail);
}

function getCardActionState(card = {}) {
  const shareState = getCardShareState(card);
  const isRevoked = shareState === "revoked";
  const canShare = Boolean(card.sourceNoteId) && shareState === "published";
  const canPublish = !isRevoked && !canShare && isCardContentReady(card);
  return { shareState, isRevoked, canShare, canPublish };
}

function isContactReviewError(error) {
  const detail = error && (error.detail || error.message || error.data && error.data.detail);
  return /未确认的手机号|手机号.*先处理/.test(String(detail || ""));
}

function openContactReview(card) {
  if (!card || !card.sourceNoteId) return;
  wx.showModal({
    title: "先处理联系方式",
    content: "正文里发现了手机号。请先确认哪些号码可以公开，或移出正文后再发给客户。",
    confirmText: "去处理",
    success: ({ confirm }) => {
      if (confirm) navigateToResourceEdit(card, { review: "contacts" });
    }
  });
}

function buildCustomerShareTitle(title) {
  const cleanTitle = String(title || "这份资料").replace(/\s+/g, " ").trim();
  return `${cleanTitle}｜点开查看完整资料`;
}

function buildLibraryShareTitle(card = {}, fallback = "资料详情") {
  return buildNoteShareTitle(card, getCurrentUser() || {}) || card.title || fallback;
}

function buildLibraryMeta(card = {}) {
  const stats = card.stats || {};
  const updatedAt = card.updatedAt || card.createdAt || "";
  const latestShareAt = stats.latestShareAt || "";
  const updatedTime = Date.parse(updatedAt || 0);
  const sharedTime = Date.parse(latestShareAt || 0);
  const latestAction = Number.isFinite(sharedTime) && sharedTime > updatedTime
    ? `最近发送 ${formatTime(latestShareAt)}`
    : `最近编辑 ${formatTime(updatedAt)}`;
  const shareCount = Number(stats.shareCount || 0);
  const pv = Number(stats.pv || 0);
  return `${latestAction} · 发送 ${shareCount} 次 · 打开 ${pv}`;
}

function parseActivityTimestamp(value) {
  const parsed = typeof value === "number" ? value : Date.parse(String(value || ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function getLibraryActivityTimestamp(card = {}) {
  const stats = card.stats || {};
  return Math.max(
    parseActivityTimestamp(stats.latestShareAt),
    parseActivityTimestamp(card.updatedAt),
    parseActivityTimestamp(card.createdAt)
  );
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
  const labels = [categoryName, ...(card.tagNames || [])].join(" ");
  return cardType === "business_card" || cardType === "service_offer" || /名片|服务|顾问|方案/.test(labels);
}

function isBusinessCardResource(card = {}) {
  const config = card.visibilityConfig || {};
  const cardType = card.cardType || config.cardType || "";
  const categoryName = card.categoryName || "";
  const labels = [categoryName, ...(card.tagNames || [])].join(" ");
  return cardType === "business_card" || /名片|顾问/.test(labels);
}

function isServiceOfferResource(card = {}) {
  const config = card.visibilityConfig || {};
  const cardType = card.cardType || config.cardType || "";
  const categoryName = card.categoryName || "";
  const labels = [categoryName, ...(card.tagNames || [])].join(" ");
  return cardType === "service_offer" || /服务|方案/.test(labels);
}

function isLinkCard(card = {}) {
  const config = card.visibilityConfig || {};
  const cardType = card.cardType || config.cardType || "";
  return cardType === "link" || cardType === "article" || config.contentMode === "bookmark" || config.sourceType === "link";
}

function isOpportunityResource(card = {}) {
  const config = card.visibilityConfig || {};
  const structuredData = config.structuredData || {};
  const text = [
    card.title,
    card.projectName,
    card.detailText,
    card.summary,
    card.body,
    card.categoryName,
    structuredData.serviceName,
    structuredData.headline,
    structuredData.targetAudience,
    structuredData.serviceContent,
    config.displayTemplate,
    config.displayTemplateName,
    ...(card.tagNames || [])
  ].filter(Boolean).join(" ");
  return isServiceOfferResource(card) && /商机|合作|招商|代理|推广|渠道|供给|需求|外贸|独立站|落地页|官网|服务商/.test(text);
}

function isDailyCard(card = {}) {
  return !isPropertyCard(card) && !isGroupbuyCard(card) && !isServiceCard(card) && !isLinkCard(card);
}

function decorateLibraryCard(card = {}) {
  const stats = card.stats || {};
  const categoryName = card.categoryName || "";
  const businessCard = isBusinessCardResource(card);
  const typeLabel = isPropertyCard(card)
    ? "房源"
    : isGroupbuyCard(card)
      ? "商品"
      : isOpportunityResource(card)
        ? "商机"
        : businessCard
          ? "电子名片"
        : isLinkCard(card)
          ? "链接"
        : isServiceCard(card)
          ? "服务"
          : categoryName || "资料";
  const highlightTags = isPropertyCard(card)
    ? (card.propertyHighlightChips || [])
    : isGroupbuyCard(card)
      ? (card.productHighlightChips || [])
      : (card.tagNames || []);
  const libraryTags = Array.from(new Set([typeLabel, ...highlightTags].filter(Boolean))).slice(0, 3);
  const currentUser = getCurrentUser() || {};
  const salesProfile = currentUser.salesProfile || {};
  const structuredData = ((card.visibilityConfig || {}).structuredData) || {};
  return {
    ...card,
    isServiceResource: isServiceCard(card),
    isBusinessCardResource: isBusinessCardResource(card),
    isServiceOfferResource: isServiceOfferResource(card),
    libraryTags,
    libraryTone: isPropertyCard(card) ? "blue" : isGroupbuyCard(card) ? "orange" : isServiceCard(card) ? "purple" : "green",
    libraryMeta: buildLibraryMeta(card),
    title: businessCard ? (salesProfile.displayName || currentUser.nickname || card.title) : card.title,
    coverUrl: businessCard ? (salesProfile.avatarUrl || currentUser.avatarUrl || card.coverUrl) : card.coverUrl,
    coverDisplayUrl: businessCard ? (salesProfile.avatarUrl || currentUser.avatarUrl || card.coverDisplayUrl || card.coverUrl) : card.coverDisplayUrl,
    businessCardRole: businessCard ? salesProfile.jobTitle || "" : "",
    businessCardCompany: businessCard ? salesProfile.company || "" : "",
    businessCardHeadline: businessCard ? structuredData.headline || "" : ""
  };
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
  const structuredData = ((card.visibilityConfig || {}).structuredData) || {};
  if (["sale", "sell", "出售"].includes(structuredData.listingMode || structuredData.dealType)) return 0;
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

Page({
  data: {
    keyword: "",
    activeCategory: "全部",
    activeTag: "全部",
    activeTopicId: "",
    activeTopicName: "",
    categoryFilters: [],
    tagFilters: [],
    visibleTagFilters: [],
    tagKeyword: "",
    showAllTags: false,
    topicFilters: [],
    cards: [],
    pendingShare: null,
    shareImages: {},
    categories: [],
    displayCards: [],
    filteredCards: [],
    visibleCardCount: LIBRARY_PAGE_SIZE,
    hasMoreCards: false,
    serverHasMoreCards: false,
    loadingMoreCards: false,
    libraryLoading: true,
    libraryLoadError: false,
    hasAnyCards: false,
    collectionCount: 0,
    filterPanelVisible: false,
    assistantBindModalVisible: false,
    assistantBindMessage: "",
    assistantBindCopied: false,
    assistantContactPlugid: "df29f3fd3ddc95bfec70e60cef93730c",
    assistantBindQrImage: "/static/wecom/assistant-qrcode.png",
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
    activeDeliveryFilter: "all",
    libraryTypeFilters: LIBRARY_TYPE_FILTERS,
    filterSummaryText: "全部资料 · 0份",
    activeLibraryType: "all"
    ,salesFilters: [
      { key: "recent", label: "最近" },
      { key: "frequent", label: "常发" },
      { key: "feedback", label: "高反馈" },
      { key: "incomplete", label: "待完善" }
    ],
    activeSalesFilter: "recent"
  },
  onLoad(options = {}) {
    if (options.mode || options.cardType) {
      this.applyEntryFilter(readEntryFilter(options));
    }
  },
  onShow() {
    setShareMenuEnabled(false);
    const requestSeq = (this._libraryRequestSeq || 0) + 1;
    this._libraryRequestSeq = requestSeq;
    const currentUser = getCurrentUser();
    if (!currentUser) {
      // The library tab is safe to open anonymously.  It is a personal
      // workspace, so do not query with an empty owner (which could fall back
      // to a broad server list); show the empty state and require login only
      // when the user starts a protected action.
      this.setData({
        cards: [],
        categories: [],
        displayCards: [],
        filteredCards: [],
        categoryFilters: [],
        tagFilters: [],
        visibleTagFilters: [],
        topicFilters: [],
        libraryLoading: false,
        libraryLoadError: false,
        hasAnyCards: false,
        collectionCount: 0,
        hasPropertyCards: false,
        hasGroupbuyCards: false,
        stats: { total: 0, pv: 0, tags: 0, visitors: 0, customerActivity: 0 },
        pendingShare: null,
        shareImages: {},
        loadingMoreCards: false,
        serverHasMoreCards: false,
        assistantBindModalVisible: false,
        assistantBindMessage: "",
        assistantBindCopied: false,
        toolsOpen: false,
        entryFilter: null,
        entryFilterText: "",
        activeCategory: "全部",
        activeTag: "全部",
        activeTopicId: "",
        activeTopicName: "",
        activeLibraryType: "all",
        activeDeliveryFilter: "all",
        activeSalesFilter: "recent"
      });
      return;
    }
    subscription.preloadViewNotificationSubscriptionConfig(currentUser.id);
    const entryFilter = readEntryFilter();
    if (entryFilter && entryFilter.salesFilter === "sent") {
      this.setData({ activeSalesFilter: "recent", activeDeliveryFilter: "sent" });
    } else if (entryFilter) {
      this.applyEntryFilter(entryFilter);
    }
    // WeChat archive imports are written by a separate worker process.  The
    // library still paints its user-scoped snapshot immediately; refreshCards
    // revalidates it in the background when the 60-second metadata TTL has
    // expired, so a page return never waits for the archive worker or media.
    this.loadCards({ backgroundRefresh: true, requestSeq });
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
      activeLibraryType: isProperty ? "property" : isGroupbuy ? "groupbuy" : isService ? "service" : isBusinessCard ? "service" : isServiceOffer ? "service" : isNotes ? "daily" : "all",
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
  renderCardSnapshot(cardsData = [], categories = [], topics = [], showcaseCount = 0, ownerUserId = "", persist = true) {
    const categoriesById = (categories || []).reduce((result, item) => {
      result[item.id] = item.name;
      return result;
    }, {});
    const cards = (cardsData || []).map((card) => decorateLibraryCard(enrichCard(card, categoriesById)));
    if (persist) resourceStore.rememberCards(ownerUserId, cardsData || []);
    const scopedCards = this.scopeCardsByEntryFilter(cards);
    const categoryFilters = this.buildCountFilters(cards, (card) => card.categoryName);
    const tagItems = cards.flatMap((card) => (card.tagNames || []).map((tag) => ({ tag })));
    const tagFilters = this.buildCountFilters(tagItems, (item) => item.tag);
    const topicFilters = this.buildTopicFilters(cards, topics || []);
    const libraryTypeFilters = this.buildLibraryTypeFilters(scopedCards);
    const deliveryFilters = this.buildDeliveryFilters(scopedCards);
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
      visibleTagFilters: this.getVisibleTagFilters(tagFilters),
      libraryTypeFilters,
      deliveryFilters,
      topicFilters,
      stats,
      libraryLoading: false,
      libraryLoadError: false,
      hasAnyCards: cards.length > 0,
      collectionCount: Number(showcaseCount || 0),
      hasPropertyCards: cards.some((card) => isPropertyCard(card)),
      hasGroupbuyCards: cards.some((card) => isGroupbuyCard(card)),
      serverHasMoreCards: cardsData.length === LIBRARY_PAGE_SIZE
    }, () => {
      this.applyFilter();
      // A card may only enter the WeChat share flow after its static snapshot
      // has been uploaded and saved. Prepare the first page in the background
      // so normal browsing is not blocked, while the button remains gated.
      const shareCandidates = cards
        .filter((card) => getCardActionState(card).canShare)
        .slice(0, LIBRARY_PAGE_SIZE);
      if (shareCandidates.length) this.prepareLibraryShareImages(shareCandidates);
    });
    return { cards, categoriesById };
  },
  async loadCards(options = {}) {
    const currentUser = getCurrentUser();
    const ownerUserId = currentUser ? currentUser.id : "";
    const requestSeq = options.requestSeq || this._libraryRequestSeq || 0;
    const isCurrentRequest = () => requestSeq === this._libraryRequestSeq
      && (getCurrentUser() || {}).id === ownerUserId;
    if (!ownerUserId || !isCurrentRequest()) return;
    const cachedCards = resourceStore.peekCards(ownerUserId);
    const hasCachedCards = resourceStore.hasCardsCache(ownerUserId);
    const forceRefresh = options.forceRefresh === true;
    this.setData({ libraryLoading: !hasCachedCards, libraryLoadError: false });
    if (hasCachedCards) {
      this.renderCardSnapshot(
        cachedCards,
        resourceStore.peekCategories(ownerUserId),
        api.getCachedTopics(ownerUserId),
        api.getCachedShowcases(ownerUserId).length,
        ownerUserId,
        false
      );
    }
    try {
      const cardsPromise = hasCachedCards && !forceRefresh
        ? Promise.resolve(cachedCards)
        : resourceStore.listCardPage({ ownerUserId, limit: LIBRARY_PAGE_SIZE, offset: 0 });
      const categoriesPromise = resourceStore.listCategories(ownerUserId);
      const topicsPromise = api.fetchTopics(ownerUserId).catch(() => ({ data: [] }));
      const showcasesPromise = api.fetchShowcases(ownerUserId).catch(() => ({ data: [] }));
      const firstCards = await cardsPromise;
      if (!isCurrentRequest()) return;
      // Card metadata is the useful part of the library first paint. Do not
      // hold it behind categories, topics, or showcase statistics on a cold
      // tab entry; those requests continue in parallel and fill the filters.
      if (!hasCachedCards || forceRefresh) {
        this.renderCardSnapshot(
          firstCards || [],
          resourceStore.peekCategories(ownerUserId),
          api.getCachedTopics(ownerUserId),
          api.getCachedShowcases(ownerUserId).length,
          ownerUserId,
          false
        );
      }
      const [cardsData, categories, topicsRes, showcasesRes] = await Promise.all([
        cardsPromise,
        categoriesPromise,
        topicsPromise,
        showcasesPromise
      ]);
      if (!isCurrentRequest()) return;
      const snapshot = this.renderCardSnapshot(
        cardsData || [],
        categories,
        topicsRes.data || [],
        Array.isArray(showcasesRes.data) ? showcasesRes.data.length : 0,
        ownerUserId,
        !hasCachedCards || forceRefresh
      );
      if (hasCachedCards && !forceRefresh && options.backgroundRefresh !== false) {
        resourceStore.refreshCards({ ownerUserId, limit: LIBRARY_PAGE_SIZE, offset: 0 }).then((freshCards) => {
          if (!Array.isArray(freshCards)) return;
          if (!isCurrentRequest()) return;
          const fresh = freshCards.map((card) => decorateLibraryCard(enrichCard(card, snapshot.categoriesById)));
          const existingTail = (this.data.cards || []).slice(LIBRARY_PAGE_SIZE);
          const freshIds = new Set(fresh.map((card) => card.id));
          const merged = [...fresh, ...existingTail.filter((card) => !freshIds.has(card.id))];
          resourceStore.rememberCards(ownerUserId, merged);
          this.setData({ cards: merged, hasAnyCards: merged.length > 0, serverHasMoreCards: fresh.length === LIBRARY_PAGE_SIZE }, () => {
            this.refreshFilterCounts(merged);
            this.applyFilter(false);
          });
        }).catch(() => {});
      }
    } catch (error) {
      if (!isCurrentRequest()) return;
      this.setData({ libraryLoading: false, libraryLoadError: true });
      wx.showToast({ title: error.detail || "加载资源失败", icon: "none" });
    }
  },
  handleRetryLibrary() {
    this.loadCards();
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
  buildLibraryTypeFilters(cards = []) {
    return LIBRARY_TYPE_FILTERS.map((filter) => {
      let count = cards.length;
      if (filter.key !== "all") count = cards.filter((card) => this.matchLibraryTypeFor(card, filter.key)).length;
      return { ...filter, count };
    });
  },
  buildDeliveryFilters(cards = []) {
    return DELIVERY_FILTERS.map((filter) => ({
      ...filter,
      count: filter.key === "all" ? cards.length : cards.filter((card) => this.matchDeliveryFilterFor(card, filter.key)).length
    }));
  },
  refreshFilterCounts(cards = this.data.cards || []) {
    const scopedCards = this.scopeCardsByEntryFilter(cards);
    const tagItems = cards.flatMap((card) => (card.tagNames || []).map((tag) => ({ tag })));
    const tagFilters = this.buildCountFilters(tagItems, (item) => item.tag);
    this.setData({
      libraryTypeFilters: this.buildLibraryTypeFilters(scopedCards),
      deliveryFilters: this.buildDeliveryFilters(scopedCards),
      tagFilters,
      visibleTagFilters: this.getVisibleTagFilters(tagFilters)
    });
  },
  matchLibraryTypeFor(card = {}, type = "all") {
    if (type === "all") return true;
    if (type === "property") return isPropertyCard(card);
    if (type === "groupbuy") return isGroupbuyCard(card);
    if (type === "service") return isServiceCard(card) && !isBusinessCardResource(card);
    if (type === "business_card") return isBusinessCardResource(card);
    if (type === "link") return isLinkCard(card);
    if (type === "daily") return isDailyCard(card);
    return true;
  },
  matchDeliveryFilterFor(card = {}, filter = "all") {
    if (filter === "all") return true;
    const statusText = (card.deliveryStatus && card.deliveryStatus.text) || "";
    const stats = card.stats || {};
    if (filter === "draft") return !stats.shareCount && !stats.pv && !stats.uv && !/已发送|已打开/.test(statusText);
    if (filter === "sent") return Boolean(stats.shareCount);
    if (filter === "opened") return Boolean(stats.pv || stats.uv);
    if (filter === "feedback") return Boolean(card.customerActivity || card.hasCustomerSignal || (card.customerSummary && Object.values(card.customerSummary).some((value) => Boolean(value))));
    return true;
  },
  getFilterSummaryText(count = 0) {
    const type = (this.data.libraryTypeFilters || []).find((item) => item.key === this.data.activeLibraryType);
    const delivery = (this.data.deliveryFilters || []).find((item) => item.key === this.data.activeDeliveryFilter);
    const labels = [];
    if (type && type.key !== "all") labels.push(type.label);
    if (delivery && delivery.key !== "all") labels.push(delivery.label);
    return `${labels.length ? labels.join(" · ") : "全部资料"} · ${count}份`;
  },
  getVisibleTagFilters(filters = []) {
    const keyword = String(this.data.tagKeyword || "").trim().toLowerCase();
    const matched = filters.filter((item) => !keyword || String(item.name || "").toLowerCase().includes(keyword));
    if (this.data.showAllTags || keyword) return matched;
    const selected = matched.filter((item) => item.name === this.data.activeTag);
    return Array.from(new Map([...selected, ...matched.filter((item) => item.name !== "全部").slice(0, 8)].map((item) => [item.name, item])).values());
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
  applyFilter(resetVisible = true) {
    const keyword = this.data.keyword.trim().toLowerCase();
    const hasActivePropertyFilters = this.hasActivePropertyFilters();
    const hasActiveGroupbuyFilters = this.hasActiveGroupbuyFilters();
    const isPropertyMode =
      (this.data.entryFilter && this.data.entryFilter.cardType === "property_listing") ||
      this.data.activeLibraryType === "property" ||
      this.data.activeCategory === "房源" ||
      this.data.activeCategory === "房产" ||
      hasActivePropertyFilters;
    const isGroupbuyMode =
      (this.data.entryFilter && this.data.entryFilter.cardType === "groupbuy_product") ||
      this.data.activeLibraryType === "groupbuy" ||
      this.data.activeCategory === "商品" ||
      this.data.activeCategory === "团购" ||
      hasActiveGroupbuyFilters;
    const shareImages = this.data.shareImages || {};
    const filteredCards = this.data.cards.filter((card) => {
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
      const matchType = this.matchLibraryType(card);
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
      const matchSales = this.matchSalesFilter(card);
      return matchCategory && matchType && matchTag && matchTopic && matchKeyword && matchPropertyFilters && matchGroupbuyFilters && matchDelivery && matchSales;
    }).sort((a, b) => {
      if (this.data.activeSalesFilter === "recent") {
        const recentDiff = getLibraryActivityTimestamp(b) - getLibraryActivityTimestamp(a);
        if (Number.isFinite(recentDiff) && recentDiff) return recentDiff;
      }
      const hotDiff = Number(b.hasHotCustomerSignal) - Number(a.hasHotCustomerSignal);
      if (hotDiff) return hotDiff;
      const signalDiff = Number(b.hasCustomerSignal) - Number(a.hasCustomerSignal);
      if (signalDiff) return signalDiff;
      const activityDiff = (b.customerActivity || 0) - (a.customerActivity || 0);
      if (activityDiff) return activityDiff;
      return (b.stats.pv || 0) - (a.stats.pv || 0);
    }).map((card) => {
      const shareImage = getPreparedLibraryShareImage(card, shareImages);
      const { shareState, isRevoked, canShare, canPublish } = getCardActionState(card);
      return {
        ...card,
        shareState,
        canShare,
        canPublish,
        shareImageReady: Boolean(shareImage),
        shareImagePreparing: false,
        shareDisabled: !canShare || isRevoked,
      shareStatusText: isRevoked ? "已停止分享" : canShare ? "发客户" : canPublish ? "发客户" : "完善"
      };
    });
    const visibleCardCount = resetVisible ? LIBRARY_PAGE_SIZE : Math.max(this.data.visibleCardCount || LIBRARY_PAGE_SIZE, LIBRARY_PAGE_SIZE);
    const displayCards = filteredCards.slice(0, visibleCardCount);
    this.setData({ filteredCards, displayCards, visibleCardCount, filterSummaryText: this.getFilterSummaryText(filteredCards.length), hasMoreCards: displayCards.length < filteredCards.length || this.data.serverHasMoreCards, showPropertyFilters: isPropertyMode, showGroupbuyFilters: isGroupbuyMode });
  },
  async onReachBottom() {
    if (!this.data.hasMoreCards || this.data.loadingMoreCards) return;
    const visibleCardCount = (this.data.visibleCardCount || LIBRARY_PAGE_SIZE) + LIBRARY_PAGE_SIZE;
    if (visibleCardCount > (this.data.filteredCards || []).length && this.data.serverHasMoreCards) {
      const currentUser = getCurrentUser();
      const requestSeq = this._libraryRequestSeq || 0;
      const requestOwnerUserId = currentUser ? currentUser.id : "";
      this.setData({ loadingMoreCards: true });
      try {
        const next = await resourceStore.listCardPage({ ownerUserId: currentUser ? currentUser.id : "", limit: LIBRARY_PAGE_SIZE, offset: (this.data.cards || []).length });
        if (requestSeq !== this._libraryRequestSeq || (getCurrentUser() || {}).id !== requestOwnerUserId) return;
        const categoriesById = (this.data.categories || []).reduce((result, item) => { result[item.id] = item.name; return result; }, {});
        const existingIds = new Set((this.data.cards || []).map((card) => card.id));
        const decorated = next.filter((card) => !existingIds.has(card.id)).map((card) => decorateLibraryCard(enrichCard(card, categoriesById)));
        const mergedCards = [...(this.data.cards || []), ...decorated];
        resourceStore.rememberCards(currentUser ? currentUser.id : "", mergedCards);
        this.setData({ cards: mergedCards, serverHasMoreCards: next.length === LIBRARY_PAGE_SIZE, visibleCardCount, loadingMoreCards: false }, () => {
          this.refreshFilterCounts(mergedCards);
          this.applyFilter(false);
        });
        return;
      } catch (error) {
        this.setData({ loadingMoreCards: false });
        wx.showToast({ title: "加载更多失败，请重试", icon: "none" });
        return;
      }
    }
    const displayCards = (this.data.filteredCards || []).slice(0, visibleCardCount);
    this.setData({ visibleCardCount, displayCards, hasMoreCards: displayCards.length < (this.data.filteredCards || []).length || this.data.serverHasMoreCards });
  },
  matchLibraryType(card = {}) {
    const type = this.data.activeLibraryType || "all";
    return this.matchLibraryTypeFor(card, type);
  },
  matchSalesFilter(card = {}) {
    const filter = this.data.activeSalesFilter || "recent";
    const stats = card.stats || {};
    const config = card.visibilityConfig || {};
    if (filter === "recent") return true;
    if (filter === "frequent") return Number(stats.shareCount || 0) >= 2;
    if (filter === "feedback") return Boolean(card.hasHotCustomerSignal || card.hasCustomerSignal || Number(card.customerActivity || 0) > 0 || Number(stats.pv || 0) >= 3);
    if (filter === "incomplete") return !card.sourceNoteId || config.cardState === "draft" || !String(card.title || "").trim() || (!card.coverUrl && !card.detailText);
    return true;
  },
  handleSalesFilter(event) {
    this.setData({ activeSalesFilter: event.currentTarget.dataset.key || "recent" }, () => this.applyFilter());
  },
  matchDeliveryFilter(card = {}) {
    return this.matchDeliveryFilterFor(card, this.data.activeDeliveryFilter || "all");
  },
  handleDeliveryFilter(event) {
    this.setData({ activeDeliveryFilter: event.currentTarget.dataset.key || "all" }, () => this.applyFilter());
  },
  handleTagKeywordChange(event) {
    this.setData({ tagKeyword: event.detail.value || "" }, () => this.refreshVisibleTagFilters());
  },
  handleShowAllTags() {
    this.setData({ showAllTags: !this.data.showAllTags }, () => this.refreshVisibleTagFilters());
  },
  refreshVisibleTagFilters() {
    this.setData({ visibleTagFilters: this.getVisibleTagFilters(this.data.tagFilters || []) });
  },
  handleLibraryTypeFilter(event) {
    const type = event.currentTarget.dataset.key || "all";
    this.setData({
      activeLibraryType: type,
      entryFilter: null,
      entryFilterText: "",
      activeCategory: "全部",
      activeTag: "全部",
      tagKeyword: "",
      showAllTags: false,
      activeTopicId: "",
      activeTopicName: ""
    }, () => {
      this.refreshVisibleTagFilters();
      this.applyFilter();
    });
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
      activeTopicName: "",
      activeLibraryType: "all"
    });
    this.loadCards();
  },
  handleSearch() {
    this.applyFilter();
  },
  handleToggleFilterPanel() {
    this.setData({ filterPanelVisible: !this.data.filterPanelVisible });
  },
  handleCloseFilterPanel() {
    this.setData({ filterPanelVisible: false });
  },
  handleResetLibraryFilters() {
    this.setData({
      keyword: "",
      activeCategory: "全部",
      activeTag: "全部",
      activeTopicId: "",
      activeTopicName: "",
      activeLibraryType: "all",
      activeDeliveryFilter: "all",
      activeSalesFilter: "recent",
      tagKeyword: "",
      showAllTags: false,
      entryFilter: null,
      entryFilterText: "",
      propertyPricePreset: "all",
      propertyPriceMin: "",
      propertyPriceMax: "",
      propertyLayoutFilter: "不限",
      propertyMetroFilter: "不限",
      propertyElevatorFilter: "不限",
      propertyAreaFilter: "不限",
      propertyPaymentFilter: "不限",
      propertyMoveInFilter: "不限",
      propertyStatusFilter: "不限",
      groupbuyPricePreset: "all",
      groupbuyPriceMin: "",
      groupbuyPriceMax: "",
      groupbuyPickupFilter: "不限",
      groupbuyDeadlineFilter: "不限",
      groupbuyStatusFilter: "不限"
    }, () => {
      this.refreshVisibleTagFilters();
      this.applyFilter();
    });
  },
  handleFilter(event) {
    this.setData({ activeCategory: event.currentTarget.dataset.filter });
    this.applyFilter();
  },
  handleTagFilter(event) {
    this.setData({ activeTag: event.currentTarget.dataset.tag }, () => {
      this.refreshVisibleTagFilters();
      this.applyFilter();
    });
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
      url: `/subpackages/workbench/showcase-edit/index?mode=notes&topicId=${encodeURIComponent(topicId)}&topicName=${encodeURIComponent(this.data.activeTopicName || "专题")}`
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
    }, () => {
      this.applyFilter();
      const businessCards = cards
        .filter((card) => isBusinessCardResource(card) && getCardActionState(card).canShare)
        .sort((a, b) => getLibraryActivityTimestamp(b) - getLibraryActivityTimestamp(a))
        .slice(0, 1);
      if (businessCards.length) this.prepareLibraryShareImages(businessCards);
    });
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
    wx.navigateTo({ url: "/subpackages/workbench/showcase-edit/index?mode=property&method=condition" });
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
    wx.navigateTo({ url: "/subpackages/workbench/showcase-edit/index?mode=groupbuy&method=condition" });
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
    openResourceOperations(id, card.sourceNoteId || "", card.title);
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
    const canManageShare = Boolean(card.sourceNoteId);
    const { shareState } = getCardActionState(card);
    const actionItems = [
      isGroupbuy ? "编辑商品" : isProperty ? "编辑房源" : isService ? "编辑资料" : "编辑资料",
      "加入合集",
      ...(isGroupbuy || isService ? [isGroupbuy ? "复用成新商品" : "复用成新资料"] : []),
      "复制文案",
      ...(canManageShare && shareState === "published" ? ["停止分享"] : []),
      ...(canManageShare && shareState === "revoked" ? ["重新发布"] : []),
      "资料运营",
      "删除资料"
    ];
    // 微信操作菜单最多承载 6 项；资料运营是资料卡的统一运营入口，超出时移除
    // 低频的复制文案，避免菜单整体弹出失败。
    if (actionItems.length > 6) {
      const copyIndex = actionItems.indexOf("复制文案");
      if (copyIndex >= 0) actionItems.splice(copyIndex, 1);
    }
    wx.showActionSheet({
      itemList: actionItems,
      success: (res) => {
        const index = res.tapIndex;
        const payload = { currentTarget: { dataset: { id } }, detail: { id } };
        const action = actionItems[index];
        if (action === "编辑商品" || action === "编辑房源" || action === "编辑资料") this.handleOpen(payload);
        if (action === "加入合集") this.handleAddToCollection(payload);
        if (action === "复用成新商品") this.handleDuplicateProduct(payload);
        if (action === "复用成新资料") this.handleDuplicateServiceResource(payload);
        if (action === "复制文案") this.handleCopySummary(payload);
        if (action === "停止分享") this.handleRevokeShare(payload);
        if (action === "重新发布") this.handleRepublish(payload);
        if (action === "资料运营") openResourceOperations(id, card.sourceNoteId, card.title);
        if (action === "删除资料") this.handleDelete(payload);
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
      navigateToNoteEditor(note);
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
      navigateToNoteEditor(note);
    } catch (error) {
      wx.showToast({ title: error.detail || "复用失败", icon: "none" });
    }
  },
  handleOpenPendingImports() {
    wx.navigateTo({ url: "/pages/imports/index" });
  },
  handleAssistantBindTap() {
    const currentUser = getCurrentUser();
    if (!currentUser || !currentUser.id) {
      wx.navigateTo({ url: "/pages/login/index" });
      return;
    }
    api.createWecomBindIntent(currentUser.id).then((response) => {
      const data = (response && response.data) || {};
      if (data.bound || data.status === "bound") {
        wx.showModal({
          title: "资料助手已绑定",
          content: "你已经绑定过企业微信资料助手，可以直接把资料、图片和链接转发给它。",
          confirmText: "知道了",
          showCancel: false
        });
        return;
      }
      this.setData({
        assistantBindModalVisible: true,
        assistantBindMessage: data.bindMessage || "",
        assistantBindCopied: false
      });
    }).catch((error) => {
      console.warn("wecom assistant bind intent failed", error);
      const statusCode = Number(error && error.statusCode);
      const title = statusCode === 401
        ? "登录已失效，请重新登录"
        : statusCode === 404
          ? "资料助手服务正在更新，请稍后重试"
          : "资料助手暂时不可用，请稍后重试";
      wx.showToast({ title, icon: "none" });
    });
  },
  copyAssistantBindMessage(bindMessage) {
    wx.setClipboardData({
      data: bindMessage,
      success: () => this.setData({
        assistantBindModalVisible: true,
        assistantBindMessage: bindMessage,
        assistantBindCopied: true
      })
    });
  },
  handleCopyAssistantBindMessage() {
    if (!this.data.assistantBindMessage) return;
    wx.setClipboardData({
      data: this.data.assistantBindMessage,
      success: () => wx.showToast({ title: "已复制", icon: "success" })
    });
  },
  handleAssistantContactStart() {
    this.setData({ assistantContactStarted: true });
  },
  handleAssistantContactComplete(event = {}) {
    const detail = event.detail || event || {};
    if (Number(detail.errcode) === 0) {
      wx.showToast({ title: "已添加，请复制绑定消息发送", icon: "none", duration: 2200 });
      return;
    }
    wx.showToast({ title: "添加资料助手未完成", icon: "none" });
  },
  handleCloseAssistantBindModal() {
    this.setData({ assistantBindModalVisible: false });
  },
  noop() {},
  handleOpenNotes() {
    wx.navigateTo({ url: "/pages/notes/index" });
  },
  handleOpenTopics() {
    wx.navigateTo({ url: "/pages/topics/index" });
  },
  handleManualAdd() {
    const entryFilter = this.data.entryFilter || {};
    const type = this.data.activeLibraryType || "";
    if (entryFilter.cardType === "business_card") {
      wx.navigateTo({ url: "/subpackages/workbench/business-card-studio/index" });
      return;
    }
    if (entryFilter.cardType === "service_offer") {
      wx.navigateTo({ url: "/subpackages/workbench/service-offer-studio/index" });
      return;
    }
    if (entryFilter.cardType === "groupbuy_product" || type === "groupbuy") {
      wx.navigateTo({ url: "/subpackages/workbench/resource-create/index?workspaceMode=groupbuy&scene=groupbuy_product" });
      return;
    }
    if (entryFilter.cardType === "property_listing" || type === "property") {
      wx.navigateTo({ url: "/subpackages/workbench/resource-create/index?workspaceMode=property&scene=property_listing" });
      return;
    }
    if (entryFilter.cardType === "service_workspace" || type === "service" || type === "opportunity") {
      wx.navigateTo({ url: "/subpackages/workbench/service-offer-studio/index" });
      return;
    }
    wx.navigateTo({ url: "/subpackages/workbench/resource-create/index?workspaceMode=notes&scene=quick_note" });
  },
  handleToggleTools() {
    this.setData({ toolsOpen: !this.data.toolsOpen });
  },
  handleOpenCollections() {
    wx.navigateTo({ url: "/pages/showcases/index" });
  },
  handleAddToCollection(event) {
    const id = event && (event.currentTarget.dataset.id || event.detail.id);
    const card = this.data.cards.find((item) => item.id === id);
    if (!card || !card.sourceNoteId) {
      wx.showToast({ title: "这份资料还不能加入合集", icon: "none" });
      return;
    }
    const scene = isPropertyCard(card) ? "property" : isGroupbuyCard(card) ? "groupbuy" : isServiceCard(card) ? "service" : "notes";
    wx.navigateTo({ url: `/pages/showcases/index?select=1&noteId=${encodeURIComponent(card.sourceNoteId)}&scene=${scene}` });
  },
  async handleRevokeShare(event) {
    const id = event && (event.currentTarget.dataset.id || event.detail.id);
    const card = this.data.cards.find((item) => item.id === id);
    const user = getCurrentUser();
    if (!card || !card.sourceNoteId || !user) return;
    const confirmed = await new Promise((resolve) => wx.showModal({ title: "停止分享", content: "停止后客户将无法继续打开这份资料，之后仍可重新发布。", confirmColor: "#e5484d", success: (res) => resolve(Boolean(res.confirm)), fail: () => resolve(false) }));
    if (!confirmed) return;
    try {
      await api.revokeNote(card.sourceNoteId, user.id);
      wx.showToast({ title: "已停止分享", icon: "success" });
      await this.loadCards({ forceRefresh: true, backgroundRefresh: false });
    } catch (error) {
      wx.showToast({ title: error.detail || "停止分享失败", icon: "none" });
    }
  },
  async handleRepublish(event) {
    const id = event && (event.currentTarget.dataset.id || event.detail.id);
    const card = this.data.cards.find((item) => item.id === id);
    const user = getCurrentUser();
    if (!card || !card.sourceNoteId || !user) return;
    try {
      await api.publishNote(card.sourceNoteId, user.id, card.revision);
      wx.showToast({ title: "已重新发布", icon: "success" });
      await this.loadCards({ forceRefresh: true, backgroundRefresh: false });
    } catch (error) {
      if (isContactReviewError(error)) {
        openContactReview(card);
        return;
      }
      wx.showToast({ title: error.detail || "重新发布失败", icon: "none" });
    }
  },
  async handlePublish(event) {
    const id = event && (event.currentTarget.dataset.id || event.detail.id);
    const card = this.data.cards.find((item) => item.id === id);
    const user = getCurrentUser();
    const { canPublish } = getCardActionState(card || {});
    if (!card || !card.sourceNoteId || !user || !canPublish) return;
    try {
      await api.publishNote(card.sourceNoteId, user.id, card.revision);
      wx.showToast({ title: "已准备好，点发客户即可发送", icon: "success" });
      await this.loadCards({ forceRefresh: true, backgroundRefresh: false });
    } catch (error) {
      if (isContactReviewError(error)) {
        openContactReview(card);
        return;
      }
      wx.showToast({ title: error.detail || "发客户失败，请先完善资料", icon: "none" });
    }
  },
  handleOpenBusinessCardStudio() {
    wx.navigateTo({ url: "/subpackages/workbench/business-card-studio/index" });
  },
  handleOpenServiceOfferStudio() {
    wx.navigateTo({ url: "/subpackages/workbench/service-offer-studio/index" });
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
        libraryMeta: buildLibraryMeta({ ...card, stats }),
        deliveryStatus: {
          text: "已发出，等待打开",
          tone: "sent",
          hint: "客户打开后会进入雷达"
        }
      };
    };
    const cards = (this.data.cards || []).map(updateCard);
    const displayCards = (this.data.displayCards || []).map(updateCard);
    const updatedCard = cards.find((card) => card && card.id === cardId);
    if (updatedCard) resourceStore.upsertCard(updatedCard);
    this.setData({ cards, displayCards }, () => this.applyFilter(false));
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
  async prepareLibraryShareImages(cards = []) {
    const pending = (cards || []).filter((card) => {
      if (!card || !card.id || !card.sourceNoteId) return false;
      if (!getCardActionState(card).canShare) return false;
      return true;
    });
    if (!pending.length) return;
    if (!this.libraryShareGenerating) this.libraryShareGenerating = {};
    for (const card of pending) {
      if (this.libraryShareGenerating[card.id]) continue;
      const generationOwnerUserId = (getCurrentUser() || {}).id || "";
      const generationRequestSeq = this._libraryRequestSeq || 0;
      if (!generationOwnerUserId) continue;
      const isCurrentGeneration = () => Boolean(
        generationOwnerUserId
          && (getCurrentUser() || {}).id === generationOwnerUserId
          && (this._libraryRequestSeq || 0) === generationRequestSeq
      );
      this.libraryShareGenerating[card.id] = true;
      const markPreparing = (item) => {
        if (!item || item.id !== card.id) return item;
        return {
          ...item,
          shareImagePreparing: true,
          // Do not leave an old ready flag on the native-share button while
          // the latest owner revision is being validated. Otherwise the
          // user can tap through during the validation window and send a
          // link for a revision that has already become private.
          shareImageReady: false,
          shareImageState: "preparing",
          shareStatusText: "分享图生成中"
        };
      };
      this.setData({
        cards: (this.data.cards || []).map(markPreparing),
        displayCards: (this.data.displayCards || []).map(markPreparing)
      });
      try {
        if (!isCurrentGeneration()) throw new Error("share generation is stale");
        let sourceCard = card;
        let sourceNoteId = card.sourceNoteId;
        let sourceRevision = card.revision;
        let config = card.visibilityConfig || {};
        // The library is intentionally allowed to paint a cached metadata
        // snapshot first, but a share snapshot must never be generated from
        // that stale revision. Re-read every source note before building the
        // share plan so property fields, product prices and media all use the
        // same revision as the plugin's fingerprint.
        {
          const latest = await api.fetchNote(card.sourceNoteId, generationOwnerUserId, { force: true });
          const latestNote = latest && latest.data;
          if (!latestNote || !latestNote.id) throw new Error("无法读取资料最新版本");
          sourceCard = {
            ...card,
            ...latestNote,
            id: card.id,
            sourceNoteId: card.sourceNoteId,
            businessCardPreview: card.businessCardPreview || latestNote.businessCardPreview,
            ownerProfile: card.ownerProfile || latestNote.ownerProfile,
            // The owner endpoint is the authority for the current publication
            // boundary. Never let a cached library row fill a missing state
            // back in as "published" after the note was edited.
            shareState: latestNote.shareState || ((latestNote.visibilityConfig || {}).shareState) || "private",
            visibilityConfig: latestNote.visibilityConfig || {}
          };
          sourceNoteId = card.sourceNoteId;
          sourceRevision = latestNote.revision;
          config = latestNote.visibilityConfig || config;
        }
        if (!isCurrentGeneration()) throw new Error("share generation is stale");
        const latestAction = getCardActionState(sourceCard);
        if (!latestAction.canShare) {
          const markUnavailable = (item) => {
            if (!item || item.id !== card.id) return item;
            return {
              ...item,
              visibilityConfig: config,
              revision: sourceRevision || item.revision,
              shareState: latestAction.shareState,
              sourceNoteShareState: latestAction.shareState,
              canShare: false,
              canPublish: latestAction.canPublish,
              shareImageReady: false,
              shareImageState: "stale",
              shareImagePreparing: false,
              shareDisabled: true,
              shareStatusText: latestAction.isRevoked ? "已停止分享" : latestAction.canPublish ? "发客户" : "完善"
            };
          };
          const shareImages = { ...(this.data.shareImages || {}) };
          delete shareImages[card.id];
          this.setData({
            shareImages,
            cards: (this.data.cards || []).map(markUnavailable),
            displayCards: (this.data.displayCards || []).map(markUnavailable)
          });
          continue;
        }
        const noteEntity = {
          ...sourceCard,
          id: sourceNoteId,
          sourceNoteId,
          revision: sourceRevision,
          shareState: latestAction.shareState,
          visibilityConfig: config
        };
        const result = await prepareNoteShareSnapshot({
          note: noteEntity,
          ownerUserId: generationOwnerUserId,
          user: getCurrentUser() || {}
        });
        if (!isCurrentGeneration()) throw new Error("share generation is stale");
        const imagePath = result.snapshot && result.snapshot.url;
        const shareReady = Boolean(imagePath);
        const savedConfig = result.entity && result.entity.visibilityConfig;
        if (shareReady) {
          const shareImages = imagePath ? {
            ...(this.data.shareImages || {}),
            [card.id]: {
              url: imagePath,
              noteId: sourceNoteId,
              sourceRevision: result.sourceRevision,
              fingerprint: result.fingerprint,
              styleId: result.styleId || NOTE_SHARE_CARD_STYLE_VERSION
            }
          } : (this.data.shareImages || {});
          const markReady = (item) => {
            if (!item || item.id !== card.id) return item;
            const { shareState, isRevoked, canShare, canPublish } = latestAction;
            return {
              ...item,
              visibilityConfig: savedConfig || item.visibilityConfig,
              revision: sourceRevision || item.revision,
              shareState,
              canShare,
              canPublish,
              shareImageReady: shareReady,
              shareImageState: "ready",
              shareImagePreparing: false,
              shareDisabled: !canShare || isRevoked,
              shareStatusText: isRevoked ? "已停止分享" : canShare ? "发客户" : canPublish ? "发客户" : "完善"
            };
          };
          this.setData({
            shareImages,
            cards: (this.data.cards || []).map(markReady),
            displayCards: (this.data.displayCards || []).map(markReady)
          });
        }
      } catch (error) {
        const markFailed = (item) => {
          if (!item || item.id !== card.id) return item;
          const { shareState, isRevoked, canShare, canPublish } = getCardActionState(item);
          return {
            ...item,
            shareState,
            canShare,
            canPublish,
            shareImageReady: false,
            shareImageState: "failed",
            shareImagePreparing: false,
            shareDisabled: !canShare || isRevoked,
            shareStatusText: isRevoked ? "已停止分享" : canShare ? "重试分享图" : canPublish ? "发客户" : "完善"
          };
        };
        this.setData({
          cards: (this.data.cards || []).map(markFailed),
          displayCards: (this.data.displayCards || []).map(markFailed)
        });
      } finally {
        this.libraryShareGenerating[card.id] = false;
      }
    }
  },
  async prepareShare(event) {
    const dataset = (event && event.currentTarget && event.currentTarget.dataset) || {};
    const cardId = dataset.id || "";
    const card = (this.data.cards || []).find((item) => item.id === cardId) || {};
    const { canShare } = getCardActionState(card);
    if (!card.sourceNoteId || !canShare) {
      wx.showToast({ title: "资料状态已变化，请刷新后再发客户", icon: "none" });
      return;
    }
    if (this.libraryShareGenerating && this.libraryShareGenerating[cardId]) {
      wx.showToast({ title: "资料分享图正在准备", icon: "none" });
      return;
    }
    const persistedState = getNoteShareSnapshotState(card, (getCurrentUser() || {}).id, getCurrentUser() || {});
    const persistedImage = persistedState.status === "ready" && persistedState.snapshot ? persistedState.snapshot.url : "";
    const generatedImageUrl = getPreparedLibraryShareImage(card, this.data.shareImages || {}) || persistedImage;
    const imageUrl = generatedImageUrl;
    const pendingShare = {
      id: cardId,
      // The card list is the source of truth. Never trust a stale dataset
      // noteId to build a public path for a different card.
      noteId: card.sourceNoteId,
      title: buildLibraryShareTitle(card, dataset.title || card.title),
      imageUrl,
      sourceRevision: getShareSourceRevision("note", card)
    };
    this.setData({ pendingShare });
    if (!generatedImageUrl && pendingShare.noteId) {
      wx.showToast({ title: "正在准备分享图，完成后再点击发客户", icon: "none" });
      this.prepareLibraryShareImages([card]);
      return;
    }
    if (generatedImageUrl) {
      const shareImages = {
        ...(this.data.shareImages || {}),
        [card.id]: {
          url: generatedImageUrl,
          noteId: card.sourceNoteId,
          sourceRevision: getShareSourceRevision("note", card),
          fingerprint: persistedState.fingerprint || "",
          styleId: persistedState.styleId || NOTE_SHARE_CARD_STYLE_VERSION
        }
      };
      const markReady = (item) => item && item.id === card.id
        ? { ...item, shareImageReady: true, shareImageState: "ready", shareImagePreparing: false, shareStatusText: "发客户" }
        : item;
      this.setData({
        shareImages,
        cards: (this.data.cards || []).map(markReady),
        displayCards: (this.data.displayCards || []).map(markReady)
      });
    }
    subscription.requestViewNotificationSubscription("library_share");
  },
  onShareAppMessage(options) {
    const dataset = options && options.target && options.target.dataset ? options.target.dataset : {};
    const cardId = dataset.id || "";
    const card = this.data.cards.find((item) => item.id === cardId) || {};
    const pendingCandidate = this.data.pendingShare || {};
    // A fast second tap can arrive before the previous setData callback. Never
    // reuse another card's generated snapshot for the current note.
    const pendingShare = !cardId || !pendingCandidate.id || pendingCandidate.id === cardId ? pendingCandidate : {};
    const { canShare } = getCardActionState(card);
    const cardNoteId = card.sourceNoteId || "";
    const requestedNoteId = dataset.noteId || pendingShare.noteId || "";
    const noteId = cardNoteId;
    const title = buildLibraryShareTitle(card, dataset.title || pendingShare.title || card.title);
    const persistedState = getNoteShareSnapshotState(card, (getCurrentUser() || {}).id, getCurrentUser() || {});
    const imageUrl = getPreparedLibraryShareImage(card, this.data.shareImages || {})
      || getShareImageUrlFromState(persistedState);
    const user = getCurrentUser();
    if (!cardId || !cardNoteId || !canShare || (requestedNoteId && requestedNoteId !== cardNoteId)) {
      wx.showToast({ title: "资料状态已变化，请刷新后再发客户", icon: "none" });
      setShareMenuEnabled(false);
      return null;
    }
    if (!imageUrl) {
      this.prepareLibraryShareImages([card]);
      wx.showToast({ title: "资料分享图正在准备，请稍后再发", icon: "none" });
      setShareMenuEnabled(false);
      return null;
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
