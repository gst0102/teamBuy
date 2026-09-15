const resourceStore = require("../../stores/resource-store");
const api = require("../../services/api");
const customerIntelligenceStore = require("../../stores/customer-intelligence-store");
const { buildDashboard, getCurrentUser } = require("../../utils/dashboard");
const { navigateToResourceView } = require("../../utils/resource-navigation");
const { getModeConfig } = require("../../utils/workspace-mode");
const { buildPageShareMessage } = require("../../utils/page-share");

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

const UNIFIED_HOME_UI = {
  emptyOpportunity: "先添加或分享一份资料，系统会把反馈集中到这里。",
  emptyAction: "添加资料"
};

const HOME_QUICK_TOOLS = [
  { key: "assistant", label: "添加资料助手", desc: "微信内容转发进资料库", icon: "微", iconImage: "/static/icons/wechat.svg", action: "openAssistant", contact: true, chip: "推荐" },
  { key: "property", label: "房源", desc: "新建房源或看房源筛选", icon: "房", action: "propertyLibrary" },
  { key: "opportunity", label: "商机", desc: "服务合作、代理、推广", icon: "商", action: "serviceOpportunity" },
  { key: "service", label: "服务", desc: "名片和服务方案", icon: "服", action: "serviceLibrary" },
  { key: "groupbuy", label: "商品", desc: "团购商品和接龙", icon: "品", action: "groupbuyLibrary" },
  { key: "showcases", label: "合集", desc: "把多条资料打包发", icon: "合", action: "showcases" }
];

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
    todayRelay: Number(summary.todayRelay || orders.filter((item) => item.actionKey === "relay-intent" && dateKey(item.createdAt) === today).length),
    todayOrder: Number(summary.todayOrder || orders.filter((item) => item.actionKey === "order-intent" && dateKey(item.createdAt) === today).length)
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
  const todaySummary = dashboard.todayBusinessSummary || {};
  return {
    alertCount: alerts.length,
    todayShareCount: Number(todaySummary.shareCount || 0),
    todayOpenCount: Number(todaySummary.visitorCount || 0),
    todayFollowupCount: Number(todaySummary.pendingLeadCount || 0),
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

function getSalesRangeSummary(intelligence = {}, dashboard = {}, range = "total") {
  const rangeSummaries = dashboard.rangeSummaries || {};
  if (rangeSummaries[range]) return rangeSummaries[range];
  if (range === "today") return dashboard.todayBusinessSummary || {};
  return dashboard.businessSummary || intelligence.summary || {};
}

function getFeedbackRangeTitle(range = "total") {
  if (range === "today") return "今日数据";
  if (range === "last7") return "近7日数据";
  return "累计数据";
}

function buildSalesHomeState(cards = [], intelligence = {}, dashboard = {}, range = "total") {
  const summary = intelligence.summary || {};
  const alerts = dashboard.opportunityAlerts || [];
  const rangeSummary = getSalesRangeSummary(intelligence, dashboard, range);
  const hasRangeSummary = Boolean(rangeSummary && Object.prototype.hasOwnProperty.call(rangeSummary, "shareCount"));
  const pendingCount = hasRangeSummary ? Number(rangeSummary.pendingLeadCount || 0) : Number(summary.pendingLeadCount || 0);
  const visitorCount = hasRangeSummary ? Number(rangeSummary.visitorCount || 0) : Number(summary.visitorCount || dashboard.totalUv || 0);
  const repeatCount = Number(summary.repeatVisitorCount || 0);
  const interactionCount = hasRangeSummary
    ? Number(rangeSummary.consultCount || rangeSummary.todayActionCount || 0)
    : Number(summary.newInteractionCount || dashboard.totalCustomerActivity || 0);
  const signalCount = visitorCount + interactionCount;
  const sentCount = hasRangeSummary ? Number(rangeSummary.shareCount || 0) : Math.max(
    cards.filter((card) => Number(((card.stats || {}).shareCount) || 0) > 0 || Number(((card.stats || {}).pv) || 0) > 0).length,
    Number(summary.feedbackResourceCount || 0)
  );
  const incompleteCount = cards.filter((card) => card.salesCheck && card.salesCheck.tone === "warn").length;
  const firstAlert = alerts[0] || null;

  if (!cards.length) {
    return {
      key: "empty",
      eyebrow: "从第一份资料开始",
      title: "先做一份能发给客户的资料",
      desc: "粘贴文案、图片或链接，整理好后直接分享到客户。",
      action: "添加第一份资料",
      actionKey: "add",
      step: 0,
      sentCount,
      visitorCount,
      repeatCount,
      interactionCount,
      signalCount,
      pendingCount,
      incompleteCount
    };
  }
  if (pendingCount > 0 || firstAlert) {
    const locked = intelligence.locked === true;
    return {
      key: "followup",
      eyebrow: `当前有 ${pendingCount || 1} 条值得处理`,
      title: firstAlert ? (firstAlert.message || "有客户正在认真看资料") : "先处理最值得联系的客户",
      desc: firstAlert ? (firstAlert.reason || firstAlert.suggestedAction || "查看客户关注点，再决定怎么联系。") : "查看客户最近看了什么，以及下一步建议。",
      action: locked ? "解锁并跟进" : "查看并跟进",
      actionKey: locked ? "membership" : "radar",
      step: 3,
      sentCount,
      visitorCount,
      repeatCount,
      interactionCount,
      signalCount,
      pendingCount,
      incompleteCount
    };
  }
  if (signalCount > 0) {
    const locked = intelligence.locked === true;
    return {
      key: "signal",
      eyebrow: "客户反馈已回来",
      title: repeatCount ? `有 ${repeatCount} 位访客重复查看` : `已有 ${visitorCount || interactionCount} 条客户反馈`,
      desc: locked ? "反馈已安全记录，开通后可查看身份、联系方式和完整轨迹。" : "查看他们关注的资料和完整访问轨迹。",
      action: locked ? "解锁客户信息链" : "查看客户反馈",
      actionKey: locked ? "membership" : "radar",
      step: 2,
      sentCount,
      visitorCount,
      repeatCount,
      interactionCount,
      signalCount,
      pendingCount,
      incompleteCount
    };
  }
  if (sentCount > 0) {
    return {
      key: "waiting",
      eyebrow: `${sentCount} 份资料已经发出`,
      title: "等客户打开，反馈会回到这里",
      desc: "你也可以继续发一份更匹配客户需求的资料。",
      action: "再选一份发客户",
      actionKey: "library",
      step: 1,
      sentCount,
      visitorCount,
      repeatCount,
      interactionCount,
      signalCount,
      pendingCount,
      incompleteCount
    };
  }
  return {
    key: "ready",
    eyebrow: `已有 ${cards.length} 份资料可用`,
    title: incompleteCount === cards.length ? "先完善一份，再发给客户" : "选一份资料，发给今天要跟的客户",
    desc: incompleteCount ? `其中 ${incompleteCount} 份还可补强，完善标题、图片或联系方式后更容易获得回复。` : "客户打开后，访客和动作会自动回到首页。",
    action: incompleteCount === cards.length ? "去完善资料" : "选择资料发客户",
    actionKey: "library",
    step: 0,
    sentCount,
    visitorCount,
    repeatCount,
    interactionCount,
    signalCount,
    pendingCount,
    incompleteCount
  };
}

function buildFeedbackSummary(intelligence = {}, dashboard = {}, range = "total", cards = []) {
  const rangeSummary = getSalesRangeSummary(intelligence, dashboard, range);
  const hasRangeSummary = Boolean(rangeSummary && Object.prototype.hasOwnProperty.call(rangeSummary, "shareCount"));
  return {
    sentCount: hasRangeSummary
      ? Number(rangeSummary.shareCount || 0)
      : Math.max(
        cards.filter((card) => Number(((card.stats || {}).shareCount) || 0) > 0 || Number(((card.stats || {}).pv) || 0) > 0).length,
        Number((intelligence.summary || {}).feedbackResourceCount || 0)
      ),
    visitorCount: hasRangeSummary
      ? Number(rangeSummary.visitorCount || 0)
      : Number((intelligence.summary || {}).visitorCount || dashboard.totalUv || 0),
    pendingCount: hasRangeSummary
      ? Number(rangeSummary.pendingLeadCount || 0)
      : Number((intelligence.summary || {}).pendingLeadCount || 0),
  };
}

function buildPriorityCustomer(intelligence = {}, dashboard = {}) {
  const locked = intelligence.locked === true;
  const alert = (dashboard.opportunityAlerts || [])[0] || null;
  const preview = (intelligence.signalPreview || [])[0] || null;
  if (!alert && !preview) return { visible: false };
  if (locked) {
    return {
      visible: true,
      locked: true,
      eyebrow: "最高优先级客户",
      name: (preview && preview.identityLabel) || "一位客户",
      avatarText: "?",
      signal: (preview && preview.signal) || "正在查看你的资料",
      source: preview && preview.noteCount ? `查看了 ${preview.noteCount} 份资料` : "客户身份和来源资料已安全记录",
      suggestion: "解锁后查看身份、联系方式、完整轨迹和跟进建议。",
      primaryAction: "解锁身份与轨迹"
    };
  }
  const name = alert.nickname || alert.customerName || alert.name || "一位客户";
  const source = alert.noteTitle || ((alert.noteTitles || [])[0]) || alert.sourceTitle || "客户资料";
  return {
    visible: true,
    locked: false,
    eyebrow: "最高优先级客户",
    name,
    avatarText: String(name).slice(0, 1),
    signal: alert.message || alert.reason || "有新的客户行为值得关注",
    source: `最近查看：${source}`,
    suggestion: alert.suggestedAction || alert.reason || "查看完整轨迹，再决定怎么联系。",
    primaryAction: "立即跟进"
  };
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
  return `/subpackages/workbench/resource-create/index?${params}`;
}

function openProtectedPage(url) {
  const currentUser = getCurrentUser();
  if (currentUser && currentUser.id) {
    wx.navigateTo({ url });
    return;
  }
  wx.navigateTo({
    url: `/pages/login/index?returnUrl=${encodeURIComponent(url)}`
  });
}

function anonymousHomeState() {
  return {
    loading: false,
    homeDashboard: null,
    cards: [],
    businessSummary: {},
    todayBusinessSummary: {},
    radarProfiles: [],
    contentInsights: [],
    revivalAlerts: [],
    groupbuyOrderSummary: {},
    statCards: [],
    taskCards: [],
    pendingItems: [],
    totalResources: 0,
    totalPv: 0,
    totalUv: 0,
    totalRelay: 0,
    totalCustomerActivity: 0,
    customerAlerts: [],
    opportunityAlerts: [],
    opportunitySummary: {},
    homeOpportunity: buildHomeOpportunity({}, UNIFIED_HOME_UI),
    homeRadarEntry: buildHomeRadarEntry(),
    feedbackRangeReady: false,
    feedbackRangeTitle: "累计数据",
    feedbackSummary: buildFeedbackSummary({}, {}, "total"),
    homeStats: buildHomeStats({}, UNIFIED_HOME_UI),
    viewers: [],
    hotResources: [],
    intelligenceLocked: true,
    signalPreview: [],
    salesHomeState: buildSalesHomeState([], {}, {}),
    priorityCustomer: { visible: false },
    recentResources: [],
    assistantBindModalVisible: false,
    assistantBindMessage: "",
    assistantBindCopied: false
  };
}

Page({
  data: {
    loading: false,
    modeChooserVisible: false,
    workspaceMode: "",
    modeConfig: getModeConfig("notes"),
    homeUi: UNIFIED_HOME_UI,
    modeSwitchLabel: "",
    modeOptions: [],
    homeQuickTools: HOME_QUICK_TOOLS,
    propertyContactPluginId: "3bf7435f594f0d6ca83a9a185ea201e5",
    overviewRange: "total",
    overviewRangeOptions: [
      { key: "today", label: "今日" },
      { key: "last7", label: "近7日" },
      { key: "total", label: "累计" }
    ],
    homeDashboard: null,
    feedbackRangeReady: false,
    feedbackRangeTitle: "累计数据",
    feedbackSummary: buildFeedbackSummary({}, {}, "total"),
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
    homeOpportunity: buildHomeOpportunity({}, UNIFIED_HOME_UI),
    homeRadarEntry: buildHomeRadarEntry(),
    homeStats: buildHomeStats({}, UNIFIED_HOME_UI),
    assistantBindModalVisible: false,
    assistantBindMessage: "",
    assistantBindCopied: false,
    assistantContactPlugid: "df29f3fd3ddc95bfec70e60cef93730c",
    assistantBindQrImage: "/static/wecom/assistant-qrcode.png",
    viewers: [],
    hotResources: [],
    intelligenceLocked: true,
    signalPreview: [],
    salesHomeState: buildSalesHomeState([], {}, {}, "total"),
    priorityCustomer: { visible: false },
    recentResources: []
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      this.dashboardUserId = "";
      this.refreshMode(null);
      this.setData(anonymousHomeState());
      return;
    }
    this.dashboardUserId = currentUser.id;
    this.refreshMode(currentUser);
    this.loadDashboard();
  },
  onShareAppMessage() {
    return buildPageShareMessage({
      title: "资料整理助手｜把资料整理成能成交的内容",
      path: "/pages/home/index"
    });
  },
  refreshMode(currentUser) {
    const modeConfig = getModeConfig("notes");
    const feedbackCopy = feedbackPanelCopy(modeConfig);
    this.setData({
      workspaceMode: "notes",
      modeConfig,
      homeUi: UNIFIED_HOME_UI,
      modeSwitchLabel: "",
      modeOptions: [],
      modeChooserVisible: false,
      pendingItems: [],
      quickActions: HOME_QUICK_TOOLS,
      feedbackPanelTitle: feedbackCopy.title,
      feedbackPanelLinkText: feedbackCopy.linkText
    });
  },
  async loadDashboard() {
    const currentUser = getCurrentUser();
    const requestUserId = currentUser && currentUser.id;
    if (!requestUserId) return;
    const modeConfig = this.data.modeConfig || getModeConfig("notes");
    const homeUi = UNIFIED_HOME_UI;
    const cachedCards = resourceStore.peekCards(requestUserId);
    if (resourceStore.hasCardsCache(requestUserId)) {
      // The home tab must have a useful first paint even when membership,
      // customer intelligence, orders, or archive status are still loading.
      // This snapshot is scoped to the current user and contains no anonymous
      // or cross-user radar payload.
      const cachedDashboard = buildDashboard(cachedCards || []);
      this.setData({
        ...cachedDashboard,
        homeDashboard: cachedDashboard,
        statCards: statCardsForMode(modeConfig, cachedDashboard, this.data.overviewRange),
        feedbackRangeReady: Boolean(cachedDashboard.rangeSummaries && cachedDashboard.rangeSummaries.today && cachedDashboard.rangeSummaries.last7 && cachedDashboard.rangeSummaries.total),
        feedbackRangeTitle: getFeedbackRangeTitle(this.data.overviewRange),
        feedbackSummary: buildFeedbackSummary({}, cachedDashboard, this.data.overviewRange, cachedDashboard.cards || []),
        recentResources: (cachedDashboard.hotResources || []).slice(0, 3),
        loading: false
      });
    }
    // Never keep the previous user's radar numbers visible while the current
    // user's customer intelligence request is in flight.
    this.setData({
      loading: true,
      homeRadarEntry: buildHomeRadarEntry(),
      feedbackRangeReady: false,
      feedbackRangeTitle: "累计数据",
      feedbackSummary: buildFeedbackSummary({}, {}, "total")
    });
    try {
      const cardsPromise = resourceStore.listCards({ ownerUserId: currentUser.id, allowStale: true }).then((rows) => {
        // Revalidate metadata without making the first paint wait for the
        // archive worker or the customer dashboard.
        resourceStore.refreshCards({ ownerUserId: currentUser.id }).catch(() => {});
        return rows;
      });
      cardsPromise.then((cards) => {
        if (this.dashboardUserId !== requestUserId || (getCurrentUser() || {}).id !== requestUserId) return;
        const cardDashboard = buildDashboard(cards || []);
        this.setData({
          ...cardDashboard,
          homeDashboard: cardDashboard,
          statCards: statCardsForMode(modeConfig, cardDashboard, this.data.overviewRange),
          feedbackRangeReady: false,
          feedbackRangeTitle: getFeedbackRangeTitle(this.data.overviewRange),
          feedbackSummary: buildFeedbackSummary({}, cardDashboard, this.data.overviewRange, cardDashboard.cards || []),
          homeOpportunity: buildHomeOpportunity(cardDashboard, homeUi),
          homeRadarEntry: buildHomeRadarEntry(cardDashboard),
          homeStats: buildHomeStats(cardDashboard, homeUi),
          salesHomeState: buildSalesHomeState(cardDashboard.cards || [], {}, cardDashboard, this.data.overviewRange),
          recentResources: (cardDashboard.hotResources || []).slice(0, 3),
          loading: false
        });
      }).catch(() => {});
      const [cards, businessDashboard, groupbuyOrders, pendingImports, showcases] = await Promise.all([
        cardsPromise,
        api.fetchMembership(currentUser.id).then((membershipRes) => {
          const membership = (membershipRes && membershipRes.data) || {};
          if (membership.featureEnabled === false) {
            return { data: { featureEnabled: false, locked: true, summary: {}, signalPreview: [] } };
          }
          return customerIntelligenceStore.getOrFetchForAccessMode(
            currentUser.id,
            "property",
            membership.paymentRequired !== false,
            () => api.fetchCustomerIntelligence(currentUser.id, currentUser.id, "property")
          );
        }).catch(() => null),
        api.fetchOrders({ userId: currentUser.id, role: "seller", summaryOnly: true }).catch(() => null),
        // Import reminders only need metadata on the home tab.  Media is
        // loaded when the user opens the import workflow, not during home
        // refresh.
        api.fetchPendingImports({ metadataOnly: true }).catch(() => ({ data: [] })),
        api.fetchShowcases(currentUser.id).catch(() => ({ data: [] }))
      ]);
      if (this.dashboardUserId !== requestUserId || (getCurrentUser() || {}).id !== requestUserId) return;
      const scopedCards = cards || [];
      const dashboard = buildDashboard(scopedCards);
      const intelligence = (businessDashboard && businessDashboard.data) || {};
      const unlockedDashboard = intelligence.dashboard || {};
      if (unlockedDashboard.summary) {
        dashboard.businessSummary = unlockedDashboard.summary || dashboard.businessSummary || intelligence.rangeSummaries && intelligence.rangeSummaries.total || {};
        dashboard.todayBusinessSummary = unlockedDashboard.todaySummary || intelligence.rangeSummaries && intelligence.rangeSummaries.today || {};
        dashboard.rangeSummaries = unlockedDashboard.rangeSummaries || intelligence.rangeSummaries || {};
        dashboard.opportunitySummary = unlockedDashboard.opportunitySummary || {};
        dashboard.opportunityAlerts = unlockedDashboard.opportunityAlerts || [];
        dashboard.radarProfiles = unlockedDashboard.radarProfiles || [];
        dashboard.contentInsights = unlockedDashboard.contentInsights || [];
        dashboard.revivalAlerts = unlockedDashboard.revivalAlerts || [];
      }
      dashboard.rangeSummaries = dashboard.rangeSummaries || intelligence.rangeSummaries || {};
      dashboard.businessSummary = dashboard.businessSummary || dashboard.rangeSummaries.total || {};
      dashboard.todayBusinessSummary = dashboard.todayBusinessSummary || dashboard.rangeSummaries.today || {};
      if (groupbuyOrders && groupbuyOrders.data) {
        dashboard.groupbuyOrderSummary = summarizeGroupbuyOrders(groupbuyOrders.data);
      }
      this.setData({
        ...dashboard,
        homeDashboard: dashboard,
        feedbackRangeReady: Boolean(dashboard.rangeSummaries && dashboard.rangeSummaries.today && dashboard.rangeSummaries.last7 && dashboard.rangeSummaries.total),
        feedbackRangeTitle: getFeedbackRangeTitle(this.data.overviewRange),
        feedbackSummary: buildFeedbackSummary(intelligence, dashboard, this.data.overviewRange, dashboard.cards || []),
        statCards: statCardsForMode(modeConfig, dashboard, this.data.overviewRange),
        taskCards: buildNotesTaskCards({
          cards: scopedCards,
          imports: (pendingImports && pendingImports.data) || [],
          showcases: (showcases && showcases.data) || []
        }),
        opportunitySummary: dashboard.opportunitySummary || {},
        opportunityAlerts: (dashboard.opportunityAlerts || []).slice(0, 3),
        homeOpportunity: buildHomeOpportunity(dashboard, homeUi),
        homeRadarEntry: buildHomeRadarEntry(dashboard),
        homeStats: intelligence.locked ? [
          { key: "visitor", label: "访客", value: Number((intelligence.summary || {}).visitorCount || 0), valueClass: "" },
          { key: "repeat", label: "复访", value: Number((intelligence.summary || {}).repeatVisitorCount || 0), valueClass: "" },
          { key: "interaction", label: "新动作", value: Number((intelligence.summary || {}).newInteractionCount || 0), valueClass: "" },
          { key: "feedback", label: "有反馈资料", value: Number((intelligence.summary || {}).feedbackResourceCount || 0), valueClass: "" }
        ] : buildHomeStats(dashboard, homeUi),
        intelligenceLocked: Boolean(businessDashboard && intelligence.locked === true),
        signalPreview: intelligence.signalPreview || [],
        salesHomeState: buildSalesHomeState(dashboard.cards || [], intelligence, dashboard, this.data.overviewRange),
        priorityCustomer: buildPriorityCustomer(intelligence, dashboard),
        recentResources: (dashboard.hotResources || []).slice(0, 3)
      });
    } catch (error) {
      if (this.dashboardUserId !== requestUserId || (getCurrentUser() || {}).id !== requestUserId) return;
      if (error && error.authExpired) return;
      this.setData({
        feedbackRangeReady: false,
        feedbackRangeTitle: "累计数据",
        feedbackSummary: buildFeedbackSummary({}, {}, "total")
      });
      wx.showToast({ title: error && error.detail ? error.detail : "首页数据加载失败", icon: "none" });
    } finally {
      if (this.dashboardUserId === requestUserId) this.setData({ loading: false });
    }
  },
  handleOverviewRangeChange(event) {
    const range = event.currentTarget.dataset.range || "today";
    const dashboard = this.data.homeDashboard;
    this.setData({
      overviewRange: range,
      feedbackRangeTitle: getFeedbackRangeTitle(range),
      statCards: dashboard ? statCardsForMode(this.data.modeConfig, dashboard, range) : this.data.statCards,
      feedbackSummary: dashboard
        ? buildFeedbackSummary(this.data.intelligence || {}, dashboard, range, dashboard.cards || [])
        : this.data.feedbackSummary
    });
  },
  handleChooseMode(event) {
    this.setData({ modeChooserVisible: false });
  },
  handleOpenModeChooser() {
    wx.showToast({ title: "资料库已统一入口", icon: "none" });
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
      showcases: () => wx.navigateTo({ url: "/pages/showcases/index" })
    };
    const run = routes[action] || routes.notesPending;
    run();
  },
  openAction(action) {
    const routes = {
      capture: () => openProtectedPage(captureUrl("notes", "quick_note")),
      captureImage: () => openProtectedPage(captureUrl("notes", "image_note")),
      captureLink: () => openProtectedPage(captureUrl("notes", "link_note")),
      captureProperty: () => openProtectedPage(captureUrl("property", "property_listing")),
      capturePropertyNeed: () => openProtectedPage(captureUrl("property", "customer_need_note")),
      openAssistant: () => this.openPropertyAssistant(),
      generateSame: () => openProtectedPage("/subpackages/workbench/property-same/index?sourceType=guide"),
      captureGroupbuy: () => openProtectedPage(captureUrl("groupbuy", "groupbuy_product")),
      captureGroupbuyMaterial: () => openProtectedPage(captureUrl("groupbuy", "groupbuy_material_note")),
      captureServiceNote: () => openProtectedPage(captureUrl("service", "service_material_note")),
      imports: () => wx.navigateTo({ url: "/pages/imports/index" }),
      library: () => wx.switchTab({ url: "/pages/library/index" }),
      propertyLibrary: () => this.openPropertyLibrary(),
      groupbuyLibrary: () => this.openGroupbuyLibrary(),
      serviceLibrary: () => this.openServiceLibrary(),
      showcases: () => this.openShowcasesForMode(),
      dashboard: () => this.openDashboardForMode(),
      leads: () => wx.navigateTo({ url: "/pages/leads/index" }),
      orders: () => wx.navigateTo({ url: "/pages/orders/index?role=seller" }),
      businessCard: () => openProtectedPage("/subpackages/workbench/business-card-studio/index"),
      businessCardLibrary: () => this.openBusinessCardLibrary(),
      serviceOffer: () => openProtectedPage("/subpackages/workbench/service-offer-studio/index"),
      serviceOpportunity: () => openProtectedPage("/subpackages/workbench/service-offer-studio/index?template=service_business_opportunity")
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
      wx.navigateTo({
        url: `/pages/login/index?returnUrl=${encodeURIComponent("/pages/home/index")}`
      });
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
  openPropertyAssistant() {
    this.focusPropertyAssistant();
    this.handleAssistantBindTap();
  },
  openShowcasesForMode() {
    wx.navigateTo({ url: "/pages/showcases/index" });
  },
  openDashboardForMode(tab) {
    const mode = this.data.workspaceMode || "notes";
    const rangeParam = this.data.overviewRange === "today" ? "&range=today" : "";
    if (mode === "property") {
      wx.navigateTo({ url: `/subpackages/workbench/business-dashboard/index?mode=property&tab=${tab || "followup"}${rangeParam}` });
      return;
    }
    wx.navigateTo({ url: `/subpackages/workbench/business-dashboard/index?mode=${encodeURIComponent(mode)}&tab=${tab || "showcasePackage"}` });
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
      this.openRadarTab("visitors");
      return;
    }
    if (key === "customer" || key === "pending" || key === "highIntent") {
      this.openRadarTab("followup");
      return;
    }
    this.handleGoRadar();
  },
  handleQuickAdd() {
    openProtectedPage("/subpackages/workbench/resource-create/index");
  },
  handlePrimaryAction() {
    const action = (this.data.salesHomeState || {}).actionKey;
    if (action === "radar") return this.handleGoRadar();
    if (action === "membership") return this.handleOpenMembership();
    if (action === "library") return this.handleGoLibrary();
    return this.handleQuickAdd();
  },
  handleFeedbackStage(event) {
    const stage = event.currentTarget.dataset.stage;
    if (stage === "sent") {
      wx.setStorageSync(LIBRARY_ENTRY_FILTER_KEY, { salesFilter: "sent", label: "已发客户", ts: Date.now() });
      return this.handleGoLibrary();
    }
    this.openRadarTab(stage === "opened" ? "visitors" : "followup");
  },
  handlePriorityPrimary() {
    if (this.data.priorityCustomer && this.data.priorityCustomer.locked) return this.handleOpenMembership();
    this.openRadarTab("followup");
  },
  handlePriorityTrack() {
    this.openRadarTab("visitors");
  },
  handleGoImports() {
    wx.navigateTo({ url: "/pages/imports/index" });
  },
  handleGoLibrary() {
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
  handleOpenMembership() {
    wx.navigateTo({ url: "/pages/membership/index" });
  },
  openRadarTab(tab = "followup") {
    wx.setStorageSync(RADAR_ENTRY_TAB_KEY, tab);
    wx.switchTab({ url: "/pages/visits/index" });
  },
  handleGoCollections() {
    wx.navigateTo({ url: "/pages/showcases/index" });
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
