const resourceStore = require("../../stores/resource-store");
const api = require("../../services/api");
const { buildDashboard, getCurrentUser } = require("../../utils/dashboard");
const { navigateToResourceView } = require("../../utils/resource-navigation");
const { PROPERTY_GROWTH_MODE_ENABLED, buildModeOptions, getModeConfig, readWorkspaceMode, saveWorkspaceMode } = require("../../utils/workspace-mode");

const LIBRARY_ENTRY_FILTER_KEY = "teambuy:libraryEntryFilter";
const RADAR_ENTRY_TAB_KEY = "teambuy:radarEntryTab";

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

function isDailyCard(card = {}) {
  return !isPropertyCard(card) && !isGroupbuyCard(card) && !isServiceCard(card);
}

function cardsForMode(cards = [], mode = "notes") {
  if (mode === "property") return cards.filter((card) => isPropertyCard(card));
  if (mode === "groupbuy") return cards.filter((card) => isGroupbuyCard(card));
  if (mode === "service") return cards.filter((card) => isServiceCard(card));
  return cards.filter((card) => isDailyCard(card));
}

function cardTypeOf(card = {}) {
  const config = card.visibilityConfig || {};
  return card.cardType || config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note");
}

function noteConfigOf(card = {}) {
  return card.visibilityConfig || {};
}

function hasTypeSuggestion(card = {}) {
  const config = noteConfigOf(card);
  return Array.isArray(config.typeSuggestions) && config.typeSuggestions.length > 0;
}

function isImageOcrTask(card = {}) {
  const config = noteConfigOf(card);
  const data = config.structuredData || {};
  const sourceType = config.sourceType || card.sourceType || "";
  const ocrStatus = data.ocr && data.ocr.status;
  const isImage = cardTypeOf(card) === "image_ocr" || ["ocr", "image_ocr", "image_capture"].includes(sourceType);
  if (!isImage) return false;
  return !["recognized", "success"].includes(ocrStatus);
}

function isPendingNoteTask(card = {}) {
  const config = noteConfigOf(card);
  if (isImageOcrTask(card) || hasTypeSuggestion(card)) return true;
  return config.systemCategory === "待整理" || config.cardState === "draft";
}

function isNotesShowcase(showcase = {}) {
  const display = showcase.displayConfig || {};
  const category = display.activeCategory || "";
  return !["房源", "房产", "团购", "商品", "电商", "好物", "服务"].includes(category);
}

function draftShowcaseCount(showcases = []) {
  return showcases.filter((item) => isNotesShowcase(item) && !["published", "archived", "deleted"].includes(item.status || "draft")).length;
}

function buildNotesTaskCards({ cards = [], imports = [], showcases = [] } = {}) {
  const imagePendingCount = cards.filter(isImageOcrTask).length;
  const pendingNoteCount = cards.filter(isPendingNoteTask).length;
  return [
    { key: "imports", icon: "导", label: "待认领", value: imports.length, desc: "企业微信导入待确认", tone: "blue", action: "imports" },
    { key: "pendingNotes", icon: "理", label: "待整理", value: pendingNoteCount, desc: "类型待确认或草稿资料", tone: "green", action: "notesPending" },
    { key: "images", icon: "图", label: "待识别图片", value: imagePendingCount, desc: "图片保存后按需识别", tone: "orange", action: "notesImagePending" },
    { key: "showcases", icon: "合", label: "未完成日常合集", value: draftShowcaseCount(showcases), desc: "草稿或未发布合集", tone: "purple", action: "showcases" }
  ];
}

function feedbackPanelCopy(modeConfig = {}) {
  if (modeConfig.key === "notes") {
    return { title: "分享反馈", linkText: "看反馈" };
  }
  if (modeConfig.key === "groupbuy") {
    return { title: "买家动态", linkText: "去接龙看板" };
  }
  if (modeConfig.key === "service") {
    return { title: "咨询动态", linkText: "去咨询看板" };
  }
  return { title: "客户动态", linkText: "去客户看板" };
}

const HOME_UI_BY_MODE = {
  property: {
    kicker: "房源成交助手",
    title: "今日成交机会",
    subtitleLines: ["先看今日机会、关注原因，", "再准备合适开场。"],
    assistantTitle: "把房源发给助手",
    assistantSub: "群里房源都能收。",
    primaryAction: {
      label: "添加房源助手",
      desc: "加企业微信后置顶转发",
      iconImage: "/static/icons/wechat.svg",
      action: "openAssistant",
      contact: true
    },
    secondaryAction: {
      label: "整理房源合集",
      desc: "把多套房源一起发",
      icon: "合",
      action: "showcases"
    },
    emptyOpportunity: "先发一份资料。",
    emptyAction: "先发一份资料",
    hotLabel: "最热房源",
    recentEmpty: "还没有最近资料，可以先把一条房源发给助手。"
  },
  service: {
    kicker: "服务成交助手",
    title: "今日咨询机会",
    subtitleLines: ["先看谁在认真了解服务或合作，", "再准备合适开场。"],
    assistantTitle: "制作服务/商机页",
    assistantSub: "名片、方案、商机都能收。",
    wecomTitle: "加企业微信助手",
    wecomSub: "服务文案、合作需求和图片都能转发进来",
    primaryAction: {
      label: "做服务/商机页",
      desc: "方案、合作、清关、招募",
      icon: "商",
      action: "serviceOpportunity"
    },
    secondaryAction: {
      label: "我的名片",
      desc: "查看或完善名片",
      icon: "名",
      action: "businessCardLibrary"
    },
    emptyOpportunity: "先发一份资料。",
    emptyAction: "先发一份资料",
    hotLabel: "最热商机",
    recentEmpty: "还没有最近资料，可以先做一张名片、服务方案或商机合作页。"
  },
  groupbuy: {
    kicker: "团购成交助手",
    title: "今日成单机会",
    subtitleLines: ["先看谁在看商品和接龙，", "再准备合适提醒。"],
    assistantTitle: "把商品发到群里",
    assistantSub: "商品、图片、接龙都能收。",
    wecomTitle: "加企业微信助手",
    wecomSub: "把群里商品、接龙和图片转发进来",
    primaryAction: {
      label: "新建商品",
      desc: "粘贴团购文案整理",
      icon: "品",
      action: "captureGroupbuy"
    },
    secondaryAction: {
      label: "商品合集",
      desc: "多个商品一起发",
      icon: "合",
      action: "showcases"
    },
    emptyOpportunity: "先发一份资料。",
    emptyAction: "先发一份资料",
    hotLabel: "最热商品",
    recentEmpty: "还没有商品资料，可以先新建一个商品。"
  },
  notes: {
    kicker: "资料分享助手",
    title: "今日分享反馈",
    subtitleLines: ["先看哪些资料被打开，", "再决定是否继续跟进。"],
    assistantTitle: "整理日常资料",
    assistantSub: "笔记、图片、链接都能收。",
    wecomTitle: "加企业微信助手",
    wecomSub: "微信里的图片、链接和文案都能转发进来",
    primaryAction: {
      label: "写笔记",
      desc: "随手记录一条资料",
      icon: "记",
      action: "capture"
    },
    secondaryAction: {
      label: "日常合集",
      desc: "打包资料分享",
      icon: "合",
      action: "showcases"
    },
    emptyOpportunity: "先发一份资料。",
    emptyAction: "先发一份资料",
    hotLabel: "最热资料",
    recentEmpty: "还没有最近资料，可以先保存一条笔记。"
  }
};

function homeUiForMode(modeConfig = {}) {
  return HOME_UI_BY_MODE[modeConfig.key] || HOME_UI_BY_MODE.property;
}

function dateKey(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function summarizeGroupbuyOrders(payload = {}) {
  const summary = (payload && payload.summary) || {};
  const orders = (payload && payload.orders) || [];
  const today = dateKey(new Date());
  return {
    total: Number(summary.total || orders.length || 0),
    pending: Number(summary.pending || 0),
    relay: Number(summary.relay || 0),
    order: Number(summary.order || 0),
    todayRelay: orders.filter((item) => item.actionKey === "relay-intent" && dateKey(item.createdAt) === today).length,
    todayOrder: orders.filter((item) => item.actionKey === "order-intent" && dateKey(item.createdAt) === today).length
  };
}

function statCardsForMode(modeConfig, dashboard, range = "today") {
  const isProperty = modeConfig.key === "property";
  const isGroupbuy = modeConfig.key === "groupbuy";
  const isService = modeConfig.key === "service";
  const labels = isProperty && range === "today" ? ["新房源", "打开", "访客", "待跟进"] : (modeConfig.stats || []);
  const cards = modeConfig.key === "property"
    ? (dashboard.cards || []).filter(isPropertyCard)
    : modeConfig.key === "groupbuy"
      ? (dashboard.cards || []).filter(isGroupbuyCard)
      : modeConfig.key === "service"
        ? (dashboard.cards || []).filter(isServiceCard)
      : (dashboard.cards || []);
  const businessSummary = range === "today" ? (dashboard.todayBusinessSummary || {}) : (dashboard.businessSummary || {});
  const opportunitySummary = dashboard.opportunitySummary || {};
  if (isProperty && Object.keys(opportunitySummary).length) {
    return [
      { key: "highIntent", icon: "热", label: "高意向", value: opportunitySummary.todayHighIntentCount || opportunitySummary.highIntentCount || 0, tone: "orange" },
      { key: "customer", icon: "跟", label: "待跟进", value: opportunitySummary.pendingFollowupCount || 0, tone: "purple" },
      { key: "uv", icon: "客", label: "今日访客", value: opportunitySummary.todayVisitorCount || 0, tone: "green" },
      { key: "pv", icon: "资", label: "最热资料", value: opportunitySummary.topContentTitle ? 1 : 0, tone: "blue" }
    ];
  }
  const hasBusinessSummary = modeConfig.key === "property" && Object.keys(businessSummary).length > 0;
  const propertyStats = {
    totalResources: hasBusinessSummary ? (businessSummary.propertyCount || 0) : cards.length,
    totalPv: hasBusinessSummary
      ? ((businessSummary.showcaseOpenCount || 0) + (businessSummary.noteClickCount || 0))
      : cards.reduce((sum, card) => sum + ((card.stats && card.stats.pv) || 0), 0),
    totalUv: hasBusinessSummary
      ? (businessSummary.visitorCount || 0)
      : cards.reduce((sum, card) => sum + ((card.stats && card.stats.uv) || 0), 0),
    totalFollowup: hasBusinessSummary
      ? (businessSummary.pendingLeadCount || 0)
      : cards.reduce((sum, card) => sum + ((card.customerSummary && card.customerSummary.pending) || card.customerActivity || 0), 0)
  };
  if (isGroupbuy) {
    const orderSummary = dashboard.groupbuyOrderSummary || {};
    const totalOrders = orderSummary.total || ((orderSummary.relay || 0) + (orderSummary.order || 0));
    return [
      { key: "resources", icon: labels[0] || "商品", label: labels[0] || "商品", value: cards.length, tone: "blue" },
      { key: "pending", icon: labels[1] || "待处理", label: labels[1] || "待处理", value: orderSummary.pending || 0, tone: "green" },
      { key: "todayRelay", icon: labels[2] || "今日接龙", label: labels[2] || "今日接龙", value: orderSummary.todayRelay || 0, tone: "orange" },
      { key: "orders", icon: labels[3] || "订单", label: labels[3] || "订单", value: totalOrders, tone: "purple" }
    ];
  }
  if (isService) {
    const businessCards = cards.filter((card) => {
      const config = card.visibilityConfig || {};
      return (card.cardType || config.cardType || "") === "business_card";
    }).length;
    const serviceOffers = cards.filter((card) => {
      const config = card.visibilityConfig || {};
      return (card.cardType || config.cardType || "") === "service_offer";
    }).length;
    return [
      { key: "resources", icon: labels[0] || "名片", label: labels[0] || "名片", value: businessCards + serviceOffers, tone: "blue" },
      { key: "pv", icon: labels[1] || "打开", label: labels[1] || "打开", value: cards.reduce((sum, card) => sum + ((card.stats && card.stats.pv) || 0), 0), tone: "green" },
      { key: "uv", icon: labels[2] || "访客", label: labels[2] || "访客", value: cards.reduce((sum, card) => sum + ((card.stats && card.stats.uv) || 0), 0), tone: "orange" },
      { key: "customer", icon: labels[3] || "咨询", label: labels[3] || "咨询", value: cards.reduce((sum, card) => sum + (card.customerActivity || ((card.customerSummary || {}).consult || 0)), 0), tone: "purple" }
    ];
  }
  const values = modeConfig.key === "property" ? propertyStats : dashboard;
  return [
    { key: "resources", icon: labels[0] || "资料", label: labels[0] || "资料", value: values.totalResources || 0, tone: "blue" },
    { key: "pv", icon: labels[1] || "打开", label: labels[1] || "打开", value: values.totalPv || 0, tone: "green" },
    { key: "uv", icon: labels[2] || "访客", label: labels[2] || "访客", value: values.totalUv || 0, tone: "orange" },
    { key: "customer", icon: labels[3] || "动态", label: labels[3] || "动态", value: values.totalFollowup || values.totalCustomerActivity || values.totalRelay || 0, tone: "purple" }
  ];
}

function buildHomeOpportunity(dashboard = {}, homeUi = HOME_UI_BY_MODE.property) {
  const alert = ((dashboard.opportunityAlerts || [])[0]) || null;
  if (alert) {
    return {
      hasAlert: true,
      intentLabel: alert.intentLabel || "高意向",
      title: alert.message || "有客户正在看资料",
      desc: alert.reason || alert.suggestedAction || "建议及时跟进。",
      action: alert.suggestedAction || "建议 30 分钟内跟进",
      script: alert.followupScript || "",
      timeText: alert.timeText || "刚刚",
      statusClass: "active"
    };
  }
  return {
    hasAlert: false,
    intentLabel: "待发现",
    title: "还没有新的客户机会",
    desc: homeUi.emptyOpportunity,
    action: homeUi.emptyAction,
    script: "",
    timeText: "",
    statusClass: "empty"
  };
}

function buildHomeRadarEntry(dashboard = {}) {
  const summary = dashboard.opportunitySummary || {};
  const alerts = dashboard.opportunityAlerts || [];
  const profiles = dashboard.radarProfiles || [];
  const revivalAlerts = dashboard.revivalAlerts || [];
  return {
    alertCount: alerts.length,
    highIntentCount: summary.todayHighIntentCount || summary.highIntentCount || profiles.filter((item) => item.intentLevel === "高").length || 0,
    pendingFollowupCount: summary.pendingFollowupCount || alerts.length || 0,
    revivalCount: summary.revivalCount || revivalAlerts.length || 0,
    desc: alerts.length ? `${alerts.length} 条新提醒，优先看高意向和沉默复活客户。` : "客户、访客、跟进建议和资料优化都在这里。",
    actionText: alerts.length ? `${alerts.length} 条新提醒` : "进入"
  };
}

function buildHomeStats(dashboard = {}, homeUi = HOME_UI_BY_MODE.property) {
  const summary = dashboard.opportunitySummary || {};
  const businessSummary = dashboard.todayBusinessSummary || dashboard.businessSummary || {};
  const totalPv = businessSummary.showcaseOpenCount || businessSummary.noteClickCount || dashboard.totalPv || 0;
  const pendingCount = summary.pendingActionCount || summary.pendingFollowupCount || businessSummary.pendingLeadCount || (dashboard.opportunityAlerts || []).length || 0;
  return [
    { key: "highIntent", label: "高意向", value: summary.todayHighIntentCount || summary.highIntentCount || 0, valueClass: "" },
    { key: "pv", label: "新打开", value: summary.todayOpenCount || totalPv || 0, valueClass: "" },
    { key: "customer", label: "待跟进", value: summary.pendingFollowupCount || businessSummary.pendingLeadCount || 0, valueClass: "" },
    { key: "pending", label: "待处理", value: pendingCount, valueClass: "" }
  ];
}

function captureUrl(workspaceMode, scene) {
  const params = [
    ["workspaceMode", workspaceMode || "notes"],
    ["scene", scene || "quick_note"],
    ["entry", "home_quick_action"]
  ]
    .filter((item) => item[1])
    .map((item) => `${item[0]}=${encodeURIComponent(item[1])}`)
    .join("&");
  return `/pages/resource-create/index?${params}`;
}

Page({
  data: {
    loading: false,
    modeChooserVisible: false,
    workspaceMode: "",
    modeConfig: getModeConfig("notes"),
    homeUi: homeUiForMode(getModeConfig("property")),
    modeSwitchLabel: getModeConfig("property").shortName,
    modeOptions: buildModeOptions(""),
    propertyContactPluginId: "3bf7435f594f0d6ca83a9a185ea201e5",
    overviewRange: "today",
    overviewRangeOptions: [
      { key: "today", label: "今日" },
      { key: "total", label: "累计" }
    ],
    homeDashboard: null,
    statCards: [],
    taskCards: [],
    pendingItems: [],
    quickActions: [],
    feedbackPanelTitle: "分享反馈",
    feedbackPanelLinkText: "看反馈",
    totalResources: 0,
    totalPv: 0,
    totalUv: 0,
    totalRelay: 0,
    totalCustomerActivity: 0,
    customerAlerts: [],
    opportunityAlerts: [],
    opportunitySummary: {},
    homeOpportunity: buildHomeOpportunity({}, HOME_UI_BY_MODE.property),
    homeRadarEntry: buildHomeRadarEntry(),
    homeStats: buildHomeStats({}, HOME_UI_BY_MODE.property),
    assistantBindModalVisible: false,
    assistantBindMessage: "",
    assistantBindCopied: false,
    assistantBindQrImage: "/static/wecom/assistant-qrcode.png",
    viewers: [],
    hotResources: []
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: `/pages/login/index?returnUrl=${encodeURIComponent("/pages/home/index")}` });
      return;
    }
    this.refreshMode(currentUser);
    this.loadDashboard();
  },
  refreshMode(currentUser) {
    const workspaceMode = readWorkspaceMode(currentUser && currentUser.id);
    const modeConfig = getModeConfig(workspaceMode || "notes");
    const homeUi = homeUiForMode(modeConfig);
    const feedbackCopy = feedbackPanelCopy(modeConfig);
    this.setData({
      workspaceMode,
      modeConfig,
      homeUi,
      modeSwitchLabel: modeConfig.shortName || "切换",
      modeOptions: buildModeOptions(workspaceMode),
      modeChooserVisible: PROPERTY_GROWTH_MODE_ENABLED ? false : !workspaceMode,
      pendingItems: modeConfig.pending || [],
      quickActions: modeConfig.quickActions || [],
      feedbackPanelTitle: feedbackCopy.title,
      feedbackPanelLinkText: feedbackCopy.linkText
    });
  },
  async loadDashboard() {
    const currentUser = getCurrentUser();
    const modeConfig = this.data.modeConfig || getModeConfig("notes");
    const homeUi = homeUiForMode(modeConfig);
    this.setData({ loading: true });
    try {
      const [cards, businessDashboard, groupbuyOrders, pendingImports, showcases] = await Promise.all([
        resourceStore.listCards({ ownerUserId: currentUser.id }, { force: true }),
        modeConfig.key !== "notes"
          ? api.fetchBusinessDashboard(currentUser.id, currentUser.id, modeConfig.key).catch(() => null)
          : Promise.resolve(null),
        modeConfig.key === "groupbuy"
          ? api.fetchOrders({ userId: currentUser.id, role: "seller" }).catch(() => null)
          : Promise.resolve(null),
        modeConfig.key === "notes" ? api.fetchPendingImports().catch(() => ({ data: [] })) : Promise.resolve({ data: [] }),
        modeConfig.key === "notes" ? api.fetchShowcases(currentUser.id).catch(() => ({ data: [] })) : Promise.resolve({ data: [] })
      ]);
      const scopedCards = cardsForMode(cards || [], modeConfig.key);
      const dashboard = buildDashboard(scopedCards);
      if (businessDashboard && businessDashboard.data && businessDashboard.data.summary) {
        dashboard.businessSummary = businessDashboard.data.summary;
        dashboard.todayBusinessSummary = businessDashboard.data.todaySummary || {};
        dashboard.opportunitySummary = businessDashboard.data.opportunitySummary || {};
        dashboard.opportunityAlerts = businessDashboard.data.opportunityAlerts || [];
        dashboard.radarProfiles = businessDashboard.data.radarProfiles || [];
        dashboard.contentInsights = businessDashboard.data.contentInsights || [];
        dashboard.revivalAlerts = businessDashboard.data.revivalAlerts || [];
      }
      if (groupbuyOrders && groupbuyOrders.data) {
        dashboard.groupbuyOrderSummary = summarizeGroupbuyOrders(groupbuyOrders.data);
      }
      this.setData({
        ...dashboard,
        homeDashboard: dashboard,
        statCards: statCardsForMode(modeConfig, dashboard, this.data.overviewRange),
        taskCards: modeConfig.key === "notes"
          ? buildNotesTaskCards({
              cards: scopedCards,
              imports: (pendingImports && pendingImports.data) || [],
              showcases: (showcases && showcases.data) || []
            })
          : [],
        opportunitySummary: dashboard.opportunitySummary || {},
        opportunityAlerts: (dashboard.opportunityAlerts || []).slice(0, 3),
        homeOpportunity: buildHomeOpportunity(dashboard, homeUi),
        homeRadarEntry: buildHomeRadarEntry(dashboard),
        homeStats: buildHomeStats(dashboard, homeUi)
      });
    } catch (error) {
      wx.showToast({ title: "首页数据加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleOverviewRangeChange(event) {
    const range = event.currentTarget.dataset.range || "today";
    const dashboard = this.data.homeDashboard;
    this.setData({
      overviewRange: range,
      statCards: dashboard ? statCardsForMode(this.data.modeConfig, dashboard, range) : this.data.statCards
    });
  },
  handleChooseMode(event) {
    const mode = event.currentTarget.dataset.mode || "notes";
    const currentUser = getCurrentUser();
    const modeConfig = saveWorkspaceMode(mode, currentUser && currentUser.id);
    const homeUi = homeUiForMode(modeConfig);
    const feedbackCopy = feedbackPanelCopy(modeConfig);
    this.setData({
      workspaceMode: modeConfig.key,
      modeConfig,
      homeUi,
      modeSwitchLabel: modeConfig.shortName || "切换",
      modeOptions: buildModeOptions(modeConfig.key),
      modeChooserVisible: false,
      pendingItems: modeConfig.pending || [],
      quickActions: modeConfig.quickActions || [],
      feedbackPanelTitle: feedbackCopy.title,
      feedbackPanelLinkText: feedbackCopy.linkText
    });
    this.loadDashboard();
  },
  handleOpenModeChooser() {
    if (PROPERTY_GROWTH_MODE_ENABLED) {
      wx.showToast({ title: "当前为房源中介版", icon: "none" });
      return;
    }
    this.setData({
      modeChooserVisible: true,
      modeOptions: buildModeOptions(this.data.workspaceMode || "notes")
    });
  },
  handleUseDailyMode() {
    this.handleChooseMode({ currentTarget: { dataset: { mode: "notes" } } });
  },
  handleQuickAction(event) {
    const action = event.currentTarget.dataset.action;
    this.openAction(action);
  },
  handleCopyHomeScript() {
    const script = (this.data.homeOpportunity && this.data.homeOpportunity.script) || "";
    if (!script) {
      this.openDashboardForMode("followup");
      return;
    }
    wx.setClipboardData({ data: script });
  },
  handleOpenTaskCard(event) {
    const action = event.currentTarget.dataset.action;
    const routes = {
      imports: () => wx.navigateTo({ url: "/pages/imports/index" }),
      notesPending: () => wx.navigateTo({ url: "/pages/notes/index?migrationPending=1" }),
      notesImagePending: () => wx.navigateTo({ url: "/pages/notes/index?sourceType=ocr&migrationPending=1" }),
      showcases: () => wx.switchTab({ url: "/pages/showcases/index" })
    };
    const run = routes[action] || routes.notesPending;
    run();
  },
  openAction(action) {
    const routes = {
      capture: () => wx.navigateTo({ url: captureUrl("notes", "quick_note") }),
      captureImage: () => wx.navigateTo({ url: captureUrl("notes", "image_note") }),
      captureLink: () => wx.navigateTo({ url: captureUrl("notes", "link_note") }),
      captureProperty: () => wx.navigateTo({ url: captureUrl("property", "property_listing") }),
      capturePropertyNeed: () => wx.navigateTo({ url: captureUrl("property", "customer_need_note") }),
      openAssistant: () => this.openPropertyAssistant(),
      generateSame: () => wx.navigateTo({ url: "/pages/property-same/index?sourceType=guide" }),
      captureGroupbuy: () => wx.navigateTo({ url: captureUrl("groupbuy", "groupbuy_product") }),
      captureGroupbuyMaterial: () => wx.navigateTo({ url: captureUrl("groupbuy", "groupbuy_material_note") }),
      captureServiceNote: () => wx.navigateTo({ url: captureUrl("service", "service_material_note") }),
      imports: () => wx.navigateTo({ url: "/pages/imports/index" }),
      library: () => wx.switchTab({ url: "/pages/library/index" }),
      showcases: () => this.openShowcasesForMode(),
      dashboard: () => this.openDashboardForMode(),
      leads: () => wx.navigateTo({ url: "/pages/leads/index" }),
      orders: () => wx.navigateTo({ url: "/pages/orders/index?role=seller" }),
      businessCard: () => wx.navigateTo({ url: "/pages/business-card-studio/index" }),
      businessCardLibrary: () => this.openBusinessCardLibrary(),
      serviceOffer: () => wx.navigateTo({ url: "/pages/service-offer-studio/index" }),
      serviceOpportunity: () => wx.navigateTo({ url: "/pages/service-offer-studio/index?template=service_business_opportunity" })
    };
    const run = routes[action] || routes.capture;
    run();
  },
  focusPropertyAssistant() {
    wx.pageScrollTo({ scrollTop: 0, duration: 260 });
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
          content: "你已经绑定过企业微信资料助手。现在可以直接把房源、资料、图片转发给它，系统会自动进入你的资料库。",
          confirmText: "知道了",
          showCancel: false
        });
        return;
      }
      const bindMessage = data.bindMessage;
      if (bindMessage) {
        this.copyWecomBindMessage(bindMessage);
        return;
      }
      wx.showToast({ title: "绑定码生成失败", icon: "none" });
    }).catch((error) => {
      console.warn("wecom assistant bind intent failed", error);
      wx.showToast({ title: "登录状态异常，请稍后再试", icon: "none" });
    });
  },
  copyWecomBindMessage(bindMessage) {
    if (!bindMessage) return;
    wx.setClipboardData({
      data: bindMessage,
      success: () => {
        this.setData({
          assistantBindModalVisible: true,
          assistantBindMessage: bindMessage,
          assistantBindCopied: true
        });
      }
    });
  },
  handleCopyAssistantBindMessage() {
    const bindMessage = this.data.assistantBindMessage;
    if (!bindMessage) return;
    wx.setClipboardData({
      data: bindMessage,
      success: () => {
        this.setData({ assistantBindCopied: true });
        wx.showToast({ title: "已复制", icon: "success" });
      }
    });
  },
  handleCloseAssistantBindModal() {
    this.setData({ assistantBindModalVisible: false });
  },
  noop() {},
  openPropertyAssistant() {
    this.focusPropertyAssistant();
    this.handleAssistantBindTap();
  },
  openShowcasesForMode() {
    wx.switchTab({ url: "/pages/showcases/index" });
  },
  openDashboardForMode(tab) {
    const mode = this.data.workspaceMode || "notes";
    const rangeParam = this.data.overviewRange === "today" ? "&range=today" : "";
    if (mode === "property") {
      wx.navigateTo({ url: `/pages/business-dashboard/index?mode=property&tab=${tab || "followup"}${rangeParam}` });
      return;
    }
    wx.navigateTo({ url: `/pages/business-dashboard/index?mode=${encodeURIComponent(mode)}&tab=${tab || "showcasePackage"}` });
  },
  openPropertyLibrary() {
    wx.setStorageSync(LIBRARY_ENTRY_FILTER_KEY, {
      mode: "property",
      cardType: "property_listing",
      label: "房源资料",
      ts: Date.now()
    });
    wx.switchTab({ url: "/pages/library/index" });
  },
  openGroupbuyLibrary() {
    wx.setStorageSync(LIBRARY_ENTRY_FILTER_KEY, {
      mode: "groupbuy",
      cardType: "groupbuy_product",
      label: "商品资料",
      ts: Date.now()
    });
    wx.switchTab({ url: "/pages/library/index" });
  },
  openServiceLibrary() {
    wx.setStorageSync(LIBRARY_ENTRY_FILTER_KEY, {
      mode: "service",
      cardType: "service_workspace",
      label: "名片/服务方案",
      ts: Date.now()
    });
    wx.switchTab({ url: "/pages/library/index" });
  },
  openBusinessCardLibrary() {
    wx.setStorageSync(LIBRARY_ENTRY_FILTER_KEY, {
      mode: "service",
      cardType: "business_card",
      label: "我的名片",
      ts: Date.now()
    });
    wx.switchTab({ url: "/pages/library/index" });
  },
  handleOpenStatCard(event) {
    const key = event.currentTarget.dataset.key;
    if (this.data.modeConfig && this.data.modeConfig.key === "property") {
      if (key === "resources") {
        this.openPropertyLibrary();
        return;
      }
      if (key === "highIntent") {
        this.openDashboardForMode("followup");
        return;
      }
      if (key === "pv") {
        this.openDashboardForMode("propertyEffect");
        return;
      }
      if (key === "uv") {
        this.openDashboardForMode("visitors");
        return;
      }
      if (key === "customer") {
        this.openDashboardForMode("followup");
        return;
      }
      if (key === "pending") {
        this.openDashboardForMode("followup");
        return;
      }
    }
    if (this.data.modeConfig && this.data.modeConfig.key === "groupbuy") {
      if (key === "resources") {
        this.openGroupbuyLibrary();
        return;
      }
      if (key === "pending") {
        wx.navigateTo({ url: "/pages/orders/index?role=seller&status=submitted" });
        return;
      }
      if (key === "todayRelay") {
        wx.navigateTo({ url: "/pages/orders/index?role=seller&date=today" });
        return;
      }
      if (key === "orders") {
        wx.navigateTo({ url: "/pages/orders/index?role=seller" });
        return;
      }
    }
    if (this.data.modeConfig && this.data.modeConfig.key === "service") {
      if (key === "resources") {
        this.openServiceLibrary();
        return;
      }
      if (key === "pending") {
        this.openDashboardForMode("followup");
        return;
      }
      this.openDashboardForMode(key === "customer" ? "followup" : key === "uv" ? "visitors" : "showcasePackage");
      return;
    }
    if (key === "resources") {
      this.handleGoLibrary();
      return;
    }
    if (key === "pv" || key === "uv") {
      this.openRadarTab(key === "uv" ? "visitors" : "insights");
      return;
    }
    if (key === "customer" || key === "pending" || key === "highIntent") {
      this.openRadarTab("followup");
      return;
    }
    this.handleGoRadar();
  },
  handleQuickAdd() {
    wx.navigateTo({ url: "/pages/resource-create/index" });
  },
  handleGoImports() {
    wx.navigateTo({ url: "/pages/imports/index" });
  },
  handleGoLibrary() {
    if (this.data.modeConfig && this.data.modeConfig.key === "service") {
      this.openServiceLibrary();
      return;
    }
    wx.switchTab({ url: "/pages/library/index" });
  },
  handleGoWorkbench() {
    if (this.data.modeConfig && this.data.modeConfig.key === "property") {
      this.openDashboardForMode("followup");
      return;
    }
    if (this.data.modeConfig && this.data.modeConfig.key === "groupbuy") {
      wx.navigateTo({ url: "/pages/orders/index?role=seller&status=submitted" });
      return;
    }
    wx.switchTab({ url: "/pages/visits/index" });
  },
  handleGoRadar() {
    this.openRadarTab("followup");
  },
  openRadarTab(tab = "followup") {
    wx.setStorageSync(RADAR_ENTRY_TAB_KEY, tab);
    wx.switchTab({ url: "/pages/visits/index" });
  },
  handleGoCollections() {
    wx.switchTab({ url: "/pages/showcases/index" });
  },
  handleOpenResource(event) {
    const id = event.currentTarget.dataset.id;
    const card = this.data.hotResources.find((item) => item.id === id) || id;
    navigateToResourceView(card);
  },
  handleInvitePlaceholder() {
    wx.showToast({ title: "邀请权益正在准备中", icon: "none" });
  }
});
