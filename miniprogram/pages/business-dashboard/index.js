const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

const PROPERTY_TABS = [
  { key: "followup", label: "待跟进" },
  { key: "visitors", label: "最近访客" },
  { key: "propertyEffect", label: "房源效果" },
  { key: "showcasePackage", label: "推荐包效果" }
];

const GROUPBUY_TABS = [
  { key: "followup", label: "待处理" },
  { key: "visitors", label: "买家/访客" },
  { key: "propertyEffect", label: "商品效果" },
  { key: "showcasePackage", label: "发群效果" }
];

const SERVICE_TABS = [
  { key: "followup", label: "待咨询" },
  { key: "visitors", label: "访客" },
  { key: "propertyEffect", label: "方案效果" },
  { key: "showcasePackage", label: "案例合集" }
];

const GENERAL_TABS = [
  { key: "showcasePackage", label: "分享效果" },
  { key: "visitors", label: "访客详情" },
  { key: "propertyEffect", label: "资料数据" },
  { key: "followup", label: "客户资料" }
];

const TAB_ALIASES = {
  showcases: "showcasePackage",
  showcase: "showcasePackage",
  showcasePackage: "showcasePackage",
  package: "showcasePackage",
  visitors: "visitors",
  recentVisitors: "visitors",
  notes: "propertyEffect",
  propertyEffect: "propertyEffect",
  effects: "propertyEffect",
  customers: "followup",
  customer: "followup",
  followup: "followup"
};

const EMPTY_DASHBOARD = {
  summary: {
    showcaseOpenCount: 0,
    visitorCount: 0,
    loggedInVisitorCount: 0,
    anonymousVisitorCount: 0,
    noteClickCount: 0,
    consultCount: 0,
    shareCount: 0,
    shareSourceCount: 0,
    pendingLeadCount: 0,
    customerCount: 0,
    orderCount: 0,
    pendingOrderCount: 0,
    todayEventCount: 0,
    todayActionCount: 0
  },
  recentVisitors: [],
  topNotes: [],
  topShares: [],
  latestActions: [],
  followupActions: [],
  showcaseBreakdown: [],
  visitorProfiles: [],
  propertyEffectRows: []
};

function normalizeTabKey(tab, fallback = "followup") {
  const key = TAB_ALIASES[tab] || tab || fallback;
  return PROPERTY_TABS.some((item) => item.key === key) ? key : fallback;
}

function tabsForMode(mode) {
  if (mode === "groupbuy") return GROUPBUY_TABS;
  if (mode === "service") return SERVICE_TABS;
  return mode === "property" ? PROPERTY_TABS : GENERAL_TABS;
}

function titleForMode(mode) {
  if (mode === "property") return "房源客户看板";
  if (mode === "service") return "咨询看板";
  if (mode === "groupbuy") return "团购看板";
  if (mode === "notes") return "分享效果";
  return "客户看板";
}

const DEFAULT_VISITOR_FILTER = {
  type: "all",
  identityType: "customer",
  label: "客户线索",
  desc: "默认只看客户线索；同行和上游可切到对应分组。"
};

const TODAY_VISITOR_FILTER = {
  type: "all",
  range: "today",
  identityType: "customer",
  label: "今日客户",
  desc: "只看今天打开房源、查看推荐包、留言或预约的客户。"
};

const VISITOR_IDENTITY_FILTERS = [
  { key: "customer", label: "客户", desc: "租客、买家和明确咨询的人" },
  { key: "peer_agent", label: "同行", desc: "生成同款、同行传播和对盘线索" },
  { key: "upstream", label: "上游", desc: "疑似房东、二房东或供应侧关注" },
  { key: "all", label: "全部", desc: "客户、同行和上游都显示" }
];

function cleanContact(value) {
  const text = String(value || "").replace(/\s/g, "");
  return text;
}

function avatarText(name) {
  const text = String(name || "客").trim();
  return text.slice(0, 1);
}

function safeAvatarUrl(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (!/^https:\/\//i.test(text)) return "";
  if (/example\.com/i.test(text)) return "";
  if (/avatar-default/i.test(text)) return "";
  if (/^(wxfile|file|blob):/i.test(text)) return "";
  if (/^\/tmp\//i.test(text)) return "";
  return text;
}

function formatTime(value) {
  if (!value) return "刚刚";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diff = Date.now() - date.getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diff < minute) return "刚刚";
  if (diff < hour) return `${Math.max(1, Math.floor(diff / minute))}分钟前`;
  if (diff < day) return `${Math.floor(diff / hour)}小时前`;
  return `${date.getMonth() + 1}-${date.getDate()}`;
}

function formatClock(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${hour}:${minute}`;
}

function actionStatusText(item) {
  return item.orderStatusText || item.statusText || item.actionLabel || "已互动";
}

function displayVisitorName(item = {}) {
  const name = String(item.nickname || item.customerName || "").trim();
  if (!item.viewerUserId && (!name || name === "匿名客户" || name === "客户")) return "匿名访客";
  return name || "微信客户";
}

function visitorIdentityLabel(type) {
  const match = VISITOR_IDENTITY_FILTERS.find((item) => item.key === type);
  return match && match.key !== "all" ? match.label : "客户";
}

function normalizeVisitorIdentityType(type) {
  return ["customer", "peer_agent", "upstream"].includes(type) ? type : "customer";
}

function showcaseStatusText(status) {
  if (status === "published") return "已发布";
  if (status === "draft") return "草稿";
  if (status === "archived") return "已下架";
  return status || "未知";
}

function buildVisitorStats(item) {
  const parts = [];
  if (item.viewCount) parts.push(`打开 ${item.viewCount}`);
  if (item.noteClickCount) parts.push(`看资料 ${item.noteClickCount}`);
  if (item.consultCount) parts.push(`咨询 ${item.consultCount}`);
  if (item.actionCount) parts.push(`动作 ${item.actionCount}`);
  return parts.length ? parts.join(" · ") : "暂无动作";
}

function buildVisitorSource(item) {
  const source = (item.showcaseNames || [])[0] || "";
  const note = (item.noteTitles || [])[0] || "";
  if (source && note) return `${source} / ${note}`;
  return source || note || "未记录来源";
}

function contactKey(item = {}) {
  return cleanContact(item.phone || item.displayPhone) ||
    cleanContact(item.wechat || item.displayWechat) ||
    String(item.viewerUserId || item.customerName || item.nickname || item.id || "").trim();
}

function actionPriorityTags(item = {}, mode = "property") {
  const text = `${item.actionLabel || ""}${item.statusText || ""}`;
  const tags = [];
  if (/预约|看房/.test(text)) tags.push(mode === "property" ? "预约看房" : "预约沟通");
  if (item.displayPhone || /电话|留言/.test(text)) tags.push("留了电话");
  if (item.displayWechat || /微信/.test(text)) tags.push("微信可联系");
  if (/咨询|留言|私聊/.test(text)) tags.push("明确咨询");
  return tags.length ? tags.slice(0, 2) : ["待跟进"];
}

function actionReasonText(item = {}) {
  const clock = item.clockText || item.timeText || "刚刚";
  const action = item.actionLabel || item.statusText || "客户动作";
  if (item.noteTitle) return `${clock} ${action} · ${item.noteTitle}`;
  return `${clock} ${action}`;
}

function visitorIntentTags(item = {}) {
  const tags = [];
  if ((item.consultCount || 0) > 0 || item.leadReminderId) tags.push("有咨询");
  if ((item.noteClickCount || 0) >= 2 || (item.noteTitles || []).length >= 2) tags.push("看了多套");
  if ((item.viewCount || 0) >= 3) tags.push("多次查看");
  if (item.isToday) tags.push("今日新访客");
  return tags.slice(0, 2);
}

function visitorReasonText(item = {}, mode = "property") {
  const noteLabel = mode === "service" ? "看方案" : mode === "groupbuy" ? "看商品" : mode === "notes" ? "看资料" : "看房源";
  const parts = [];
  if (item.noteClickCount) parts.push(`${noteLabel} ${item.noteClickCount} 次`);
  if (item.viewCount) parts.push(`打开 ${item.viewCount} 次`);
  if ((item.noteTitles || []).length) parts.push((item.noteTitles || [])[0]);
  return parts.length ? parts.join(" · ") : item.sourceText || "有新的浏览动态";
}

function buildPriorityContacts(actions = [], visitors = [], mode = "property") {
  const usedKeys = {};
  const actionCards = actions.map((item, index) => {
    const tags = actionPriorityTags(item, mode);
    const key = contactKey(item) || `action-${item.id || index}`;
    usedKeys[key] = true;
    return {
      ...item,
      kind: "action",
      viewKey: `action-${item.id || item.leadReminderId || index}`,
      sourceIndex: index,
      priorityNo: index + 1,
      priorityTags: tags,
      reasonText: actionReasonText(item),
      sourceText: item.noteTitle || (mode === "service" ? "服务资料" : mode === "groupbuy" ? "商品资料" : mode === "notes" ? "资料" : "房源资料"),
      actionText: item.displayPhone ? "打电话" : item.displayWechat ? "复制微信" : "处理",
      secondaryText: "已联系"
    };
  });
  const visitorCards = visitors
    .map((item, index) => ({
      ...item,
      kind: "visitor",
      viewKey: `visitor-${item.id || item.viewerUserId || index}`,
      sourceIndex: index,
      priorityTags: visitorIntentTags(item),
      reasonText: visitorReasonText(item, mode),
      sourceText: item.sourceText || (mode === "service" ? "服务访问" : mode === "groupbuy" ? "商品访问" : mode === "notes" ? "资料访问" : "房源访问"),
      actionText: item.displayPhone ? "打电话" : item.displayWechat ? "复制微信" : "看轨迹",
      secondaryText: "稍后跟进",
      intentScore: (item.consultCount || 0) * 8 + (item.noteClickCount || 0) * 3 + (item.viewCount || 0) + ((item.noteTitles || []).length > 1 ? 3 : 0)
    }))
    .filter((item) => item.priorityTags.length && !usedKeys[contactKey(item)])
    .sort((a, b) => (b.intentScore || 0) - (a.intentScore || 0));
  return [...actionCards, ...visitorCards].slice(0, 3).map((item, index) => ({
    ...item,
    priorityNo: index + 1
  }));
}

function buildCustomerDynamics(actions = [], visitors = [], priorityContacts = []) {
  const priorityKeys = {};
  priorityContacts.forEach((item) => {
    const key = contactKey(item);
    if (key) priorityKeys[key] = true;
  });
  const actionItems = actions.map((item, index) => ({
    ...item,
    kind: "action",
    viewKey: `dynamic-action-${item.id || item.leadReminderId || index}`,
    sourceIndex: index,
    dynamicType: item.actionLabel || "客户动作",
    dynamicTitle: item.customerName || "微信客户",
    dynamicSub: actionReasonText(item),
    dynamicMeta: item.displayPhone || item.displayWechat ? "可联系" : "查看记录",
    isPriorityRelated: !!priorityKeys[contactKey(item)]
  }));
  const visitorItems = visitors.map((item, index) => ({
    ...item,
    kind: "visitor",
    viewKey: `dynamic-visitor-${item.id || item.viewerUserId || index}`,
    sourceIndex: index,
    dynamicType: item.isToday ? "新访客" : "访客",
    dynamicTitle: item.nickname || "微信客户",
    dynamicSub: visitorReasonText(item),
    dynamicMeta: item.statsText || "浏览动态",
    isPriorityRelated: !!priorityKeys[contactKey(item)]
  }));
  return [...actionItems, ...visitorItems]
    .sort((a, b) => Number(b.isPriorityRelated) - Number(a.isPriorityRelated))
    .slice(0, 6);
}

function normalizeDashboard(data = {}, mode = "property") {
  const recentVisitors = (data.recentVisitors || []).map((item, index) => ({
    ...item,
    avatarUrl: safeAvatarUrl(item.avatarUrl),
    nickname: displayVisitorName(item),
    avatarText: avatarText(displayVisitorName(item), item.viewerUserId ? "客" : "匿"),
    timeText: formatTime(item.lastViewedAt),
    clockText: formatClock(item.lastViewedAt),
    visitText: item.actionText || `打开了${item.showcaseName || "推荐包"}`,
    tone: index % 3
  }));
  const topNotes = (data.topNotes || []).map((item, index) => ({
    ...item,
    rankNo: index + 1,
    avatarText: avatarText(item.title),
    rankTone: index < 3 ? index + 1 : 4
  }));
  const topShares = (data.topShares || []).map((item, index) => ({
    ...item,
    rankNo: index + 1,
    rankTone: index < 3 ? index + 1 : 4,
    shortId: item.shareId ? String(item.shareId).slice(-8) : `分享${index + 1}`,
    timeText: formatTime(item.lastEventAt),
    sourceText: item.showcaseName || "推荐包",
    visitorText: (item.visitorNames || []).length ? `访客：${(item.visitorNames || []).join("、")}` : "暂无访客明细"
  }));
  const latestActions = (data.latestActions || []).map((item, index) => ({
    ...item,
    avatarUrl: safeAvatarUrl(item.avatarUrl),
    avatarText: avatarText(item.customerName),
    displayPhone: cleanContact(item.phone),
    displayWechat: cleanContact(item.wechat),
    timeText: formatTime(item.createdAt),
    clockText: formatClock(item.createdAt),
    statusText: actionStatusText(item),
    visitorIdentityType: normalizeVisitorIdentityType(item.visitorIdentityType),
    visitorIdentityLabel: item.visitorIdentityLabel || visitorIdentityLabel(item.visitorIdentityType),
    tone: index % 4
  }));
  const followupActions = latestActions.filter((item) => (
    (item.visitorIdentityType || "customer") === "customer" && (
    item.leadReminderId ||
    item.displayPhone ||
    item.displayWechat ||
    /留言|预约|咨询|电话|微信|待联系|待跟进/.test(`${item.actionLabel || ""}${item.statusText || ""}`)
    )
  ));
  const primaryCustomer = latestActions.find((item) => item.customerName && item.customerName !== "客户") || latestActions[0] || null;
  const showcaseBreakdown = (data.showcaseBreakdown || []).map((item, index) => ({
    ...item,
    rankNo: index + 1,
    rankTone: index < 3 ? index + 1 : 4,
    statusText: showcaseStatusText(item.status),
    timeText: formatTime(item.lastEventAt),
    totalText: `打开 ${item.openCount || 0} · 访客 ${item.visitorCount || 0} · 看资料 ${item.noteClickCount || 0} · 咨询 ${item.consultCount || 0}`
  }));
  const visitorProfiles = (data.visitorProfiles || []).map((item, index) => ({
    ...item,
    avatarUrl: safeAvatarUrl(item.avatarUrl),
    nickname: displayVisitorName(item),
    avatarText: avatarText(displayVisitorName(item), item.viewerUserId ? "客" : "匿"),
    displayPhone: cleanContact(item.phone),
    displayWechat: cleanContact(item.wechat),
    showcaseNames: item.showcaseNames || [],
    noteTitles: item.noteTitles || [],
    shareIds: item.shareIds || [],
    shortShareIds: (item.shareIds || []).map((shareId) => String(shareId).slice(-8)),
    sourceText: buildVisitorSource(item),
    statsText: buildVisitorStats(item),
    timeText: formatTime(item.lastActivityAt),
    contactText: cleanContact(item.phone) || cleanContact(item.wechat) || "",
    targetText: item.orderActionId ? "查看订单" : item.leadReminderId ? "处理线索" : item.noteId ? "查看动作" : "查看记录",
    visitorIdentityType: normalizeVisitorIdentityType(item.visitorIdentityType),
    visitorIdentityLabel: item.visitorIdentityLabel || visitorIdentityLabel(item.visitorIdentityType),
    tone: index % 4
  }));
  const propertyEffectRows = buildPropertyEffectRows(topNotes, latestActions, visitorProfiles, mode);
  const radarProfiles = (data.radarProfiles || []).map((item, index) => ({
    ...item,
    avatarUrl: safeAvatarUrl(item.avatarUrl),
    avatarText: avatarText(displayVisitorName(item)),
    nickname: displayVisitorName(item),
    timeText: formatTime(item.lastActivityAt),
    tone: index % 4
  }));
  const opportunityAlerts = (data.opportunityAlerts || []).map((item, index) => ({
    ...item,
    tone: index % 4,
    timeText: formatTime(item.lastActivityAt)
  }));
  return {
    ...EMPTY_DASHBOARD,
    ...data,
    summary: {
      ...EMPTY_DASHBOARD.summary,
      ...(data.summary || {})
    },
    todaySummary: {
      ...EMPTY_DASHBOARD.summary,
      ...(data.todaySummary || {})
    },
    recentVisitors,
    topNotes,
    topShares,
    latestActions,
    followupActions,
    showcaseBreakdown,
    visitorProfiles,
    propertyEffectRows,
    primaryCustomer,
    opportunitySummary: data.opportunitySummary || {},
    opportunityAlerts,
    radarProfiles,
    contentInsights: data.contentInsights || [],
    revivalAlerts: data.revivalAlerts || []
  };
}

function buildPropertyEffectRows(topNotes = [], latestActions = [], visitorProfiles = [], mode = "property") {
  const fallbackTitle = mode === "service" ? "服务方案" : mode === "groupbuy" ? "商品资料" : mode === "notes" ? "资料" : "房源资料";
  const rowsByNote = {};
  topNotes.forEach((item, index) => {
    const key = item.noteId || item.title || `note-${index}`;
    rowsByNote[key] = {
      noteId: item.noteId || "",
      title: item.title || fallbackTitle,
      openCount: Number(item.clickCount || item.openCount || 0),
      visitorCount: 0,
      followupCount: 0,
      timeText: "",
      rankNo: index + 1,
      rankTone: index < 3 ? index + 1 : 4
    };
  });
  latestActions.forEach((action) => {
    const key = action.noteId || action.noteTitle || "";
    if (!key) return;
    const row = rowsByNote[key] || {
      noteId: action.noteId || "",
      title: action.noteTitle || fallbackTitle,
      openCount: 0,
      visitorCount: 0,
      followupCount: 0,
      timeText: action.timeText || "",
      rankNo: Object.keys(rowsByNote).length + 1,
      rankTone: 4
    };
    row.followupCount += 1;
    row.timeText = row.timeText || action.timeText || "";
    rowsByNote[key] = row;
  });
  visitorProfiles.forEach((visitor) => {
    const noteIds = visitor.noteIds || [];
    const noteTitles = visitor.noteTitles || [];
    [...noteIds, ...noteTitles].forEach((key) => {
      if (!key || !rowsByNote[key]) return;
      rowsByNote[key].visitorCount += 1;
    });
  });
  return Object.keys(rowsByNote)
    .map((key, index) => ({
      ...rowsByNote[key],
      rankNo: rowsByNote[key].rankNo || index + 1
    }))
    .sort((a, b) => (b.openCount || 0) - (a.openCount || 0) || (b.followupCount || 0) - (a.followupCount || 0));
}

function visitorMatchesFilter(visitor, filter) {
  if (!filter) return true;
  if (filter.range === "today" && !visitor.isToday) return false;
  if (filter.identityType && filter.identityType !== "all" && (visitor.visitorIdentityType || "customer") !== filter.identityType) return false;
  if (filter.type === "all") return true;
  if (filter.type === "view") return (visitor.viewCount || 0) > 0;
  if (filter.type === "note_click") return (visitor.noteClickCount || 0) > 0;
  if (filter.type === "consult") return (visitor.consultCount || 0) > 0 || !!visitor.leadReminderId;
  if (filter.type === "showcase") return (visitor.showcaseNames || []).includes(filter.showcaseName);
  if (filter.type === "share") return (visitor.shareIds || []).includes(filter.shareId);
  if (filter.type === "note") {
    const noteIds = visitor.noteIds || [];
    if (filter.noteId && (noteIds.includes(filter.noteId) || visitor.noteId === filter.noteId)) return true;
    return !!filter.noteTitle && (visitor.noteTitles || []).includes(filter.noteTitle);
  }
  return true;
}

function summarizeVisitors(visitors) {
  return {
    visitorCount: visitors.length,
    customerCount: visitors.filter((item) => (item.visitorIdentityType || "customer") === "customer").length,
    peerAgentCount: visitors.filter((item) => item.visitorIdentityType === "peer_agent").length,
    upstreamCount: visitors.filter((item) => item.visitorIdentityType === "upstream").length,
    phoneCount: visitors.filter((item) => item.displayPhone).length,
    wechatCount: visitors.filter((item) => item.displayWechat).length,
    consultCount: visitors.reduce((sum, item) => sum + (item.consultCount || 0), 0),
    noteClickCount: visitors.reduce((sum, item) => sum + (item.noteClickCount || 0), 0)
  };
}

function actionMatchesVisibleVisitors(action, visitors, filter) {
  if (!filter) return true;
  if (filter.range === "today" && !action.isToday) return false;
  if (filter.identityType && filter.identityType !== "all" && (action.visitorIdentityType || "customer") !== filter.identityType) return false;
  if (filter.type === "all") return true;
  return (visitors || []).some((visitor) => {
    if (action.displayPhone && visitor.displayPhone && action.displayPhone === visitor.displayPhone) return true;
    if (action.displayWechat && visitor.displayWechat && action.displayWechat === visitor.displayWechat) return true;
    if (action.noteId && ((visitor.noteIds || []).includes(action.noteId) || (visitor.noteId && action.noteId === visitor.noteId))) return true;
    if (action.leadReminderId && visitor.leadReminderId && action.leadReminderId === visitor.leadReminderId) return true;
    if (action.orderActionId && visitor.orderActionId && action.orderActionId === visitor.orderActionId) return true;
    return false;
  });
}

Page({
  data: {
    tabs: PROPERTY_TABS,
    activeTab: "followup",
    mode: "property",
    pageTitle: "客户看板",
    loading: false,
    errorText: "",
    dashboard: EMPTY_DASHBOARD,
    activeRange: "all",
    visibleSummary: EMPTY_DASHBOARD.summary,
    activeVisitorFilter: DEFAULT_VISITOR_FILTER,
    visitorIdentityFilters: VISITOR_IDENTITY_FILTERS,
    activeVisitorIdentity: "customer",
    visibleVisitorProfiles: [],
    visibleLatestActions: [],
    visibleFollowupActions: [],
    priorityContacts: [],
    customerDynamics: [],
    visibleVisitorSummary: summarizeVisitors([]),
    identitySummary: summarizeVisitors([]),
    opportunityAlerts: [],
    radarProfiles: [],
    contentInsights: [],
    visitorDetailOpen: false,
    selectedVisitor: null
  },
  onLoad(options) {
    const mode = options.mode || "notes";
    const activeTab = normalizeTabKey(options.tab, mode === "property" ? "followup" : "showcasePackage");
    const activeRange = options.range === "today" ? "today" : "all";
    this.setData({
      mode,
      activeTab,
      activeRange,
      activeVisitorFilter: activeRange === "today" ? TODAY_VISITOR_FILTER : DEFAULT_VISITOR_FILTER,
      tabs: tabsForMode(mode),
      pageTitle: titleForMode(mode)
    });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadDashboard(user.id);
  },
  async loadDashboard(ownerUserId) {
    this.setData({ loading: true, errorText: "" });
    try {
      const res = await api.fetchBusinessDashboard(ownerUserId, ownerUserId, this.data.mode);
      this.applyDashboardView(normalizeDashboard(res.data || {}, this.data.mode), this.data.activeVisitorFilter);
    } catch (error) {
      const detail = error.detail || error.message || error.errMsg || "";
      const errorText = /not found/i.test(detail)
        ? "客户看板正在更新，先展示空看板。"
        : detail || "客户看板加载失败";
      this.applyDashboardView(normalizeDashboard({}, this.data.mode), DEFAULT_VISITOR_FILTER, { errorText });
    } finally {
      this.setData({ loading: false });
    }
  },
  applyDashboardView(dashboard, filter = DEFAULT_VISITOR_FILTER, extra = {}) {
    const activeVisitorFilter = filter || DEFAULT_VISITOR_FILTER;
    const visibleVisitorProfiles = (dashboard.visitorProfiles || []).filter((item) => visitorMatchesFilter(item, activeVisitorFilter));
    const visibleLatestActions = (dashboard.latestActions || []).filter((item) => actionMatchesVisibleVisitors(item, visibleVisitorProfiles, activeVisitorFilter));
    const visibleFollowupActions = (dashboard.followupActions || []).filter((item) => this.data.activeRange !== "today" || item.isToday);
    const visibleSummary = this.data.activeRange === "today" ? dashboard.todaySummary : dashboard.summary;
    const priorityContacts = buildPriorityContacts(visibleFollowupActions, visibleVisitorProfiles, this.data.mode);
    const customerDynamics = buildCustomerDynamics(visibleLatestActions, visibleVisitorProfiles, priorityContacts);
    this.setData({
      dashboard,
      visibleSummary,
      activeVisitorFilter,
      activeVisitorIdentity: activeVisitorFilter.identityType || "customer",
      visibleVisitorProfiles,
      visibleLatestActions,
      visibleFollowupActions,
      priorityContacts,
      customerDynamics,
      visibleVisitorSummary: summarizeVisitors(visibleVisitorProfiles),
      identitySummary: summarizeVisitors(dashboard.visitorProfiles || []),
      opportunityAlerts: dashboard.opportunityAlerts || [],
      radarProfiles: dashboard.radarProfiles || [],
      contentInsights: dashboard.contentInsights || [],
      visitorDetailOpen: false,
      selectedVisitor: null,
      ...extra
    });
  },
  handleTabChange(event) {
    const key = normalizeTabKey(event.currentTarget.dataset.key, this.data.activeTab);
    if (!key || key === this.data.activeTab) return;
    this.setData({ activeTab: key });
  },
  handleMetricDrilldown(event) {
    const type = event.currentTarget.dataset.filterType || "all";
    const filterMap = {
      view: {
        type: "view",
        range: this.data.activeRange === "today" ? "today" : "",
        identityType: this.data.activeVisitorIdentity || "customer",
        label: "打开过推荐包的访客",
        desc: "从总打开数下钻，下面只看实际打开过推荐包的人。"
      },
      all: {
        ...(this.data.activeRange === "today" ? TODAY_VISITOR_FILTER : DEFAULT_VISITOR_FILTER),
        identityType: this.data.activeVisitorIdentity || "customer",
        desc: "从总访客数下钻，下面展示所有访客和可处理客户。"
      },
      note_click: {
        type: "note_click",
        range: this.data.activeRange === "today" ? "today" : "",
        identityType: this.data.activeVisitorIdentity || "customer",
        label: "看过资料的访客",
        desc: "从看资料下钻，下面只看点进过资料的人。"
      },
      consult: {
        type: "consult",
        range: this.data.activeRange === "today" ? "today" : "",
        identityType: this.data.activeVisitorIdentity || "customer",
        label: "咨询过的客户",
        desc: "从咨询下钻，下面只看电话、微信、留言或预约相关客户。"
      }
    };
    this.applyDashboardView(this.data.dashboard, filterMap[type] || DEFAULT_VISITOR_FILTER, { activeTab: "visitors" });
  },
  handleClearVisitorFilter() {
    this.applyDashboardView(this.data.dashboard, this.data.activeRange === "today" ? TODAY_VISITOR_FILTER : DEFAULT_VISITOR_FILTER);
  },
  handleVisitorIdentityChange(event) {
    const key = event.currentTarget.dataset.key || "customer";
    const identity = VISITOR_IDENTITY_FILTERS.find((item) => item.key === key) || VISITOR_IDENTITY_FILTERS[0];
    const base = this.data.activeVisitorFilter || DEFAULT_VISITOR_FILTER;
    this.applyDashboardView(
      this.data.dashboard,
      {
        ...base,
        identityType: identity.key,
        label: identity.key === "all" ? "全部访客" : identity.label,
        desc: identity.desc
      },
      { activeTab: "visitors" }
    );
  },
  handleOpenShowcases() {
    wx.switchTab({ url: "/pages/showcases/index" });
  },
  handleFilterByShowcase(event) {
    const showcaseName = event.currentTarget.dataset.showcaseName;
    if (!showcaseName) return;
    this.applyDashboardView(
      this.data.dashboard,
      {
        type: "showcase",
        identityType: this.data.activeVisitorIdentity || "customer",
        showcaseName,
        label: showcaseName,
        desc: "从这个推荐包下钻，下面只看它带来的访客、咨询和客户动作。"
      },
      { activeTab: "visitors" }
    );
  },
  handleFilterByShare(event) {
    const shareId = event.currentTarget.dataset.shareId;
    const showcaseName = event.currentTarget.dataset.showcaseName || "这次分享";
    if (!shareId) return;
    this.applyDashboardView(
      this.data.dashboard,
      {
        type: "share",
        identityType: this.data.activeVisitorIdentity || "customer",
        shareId,
        label: showcaseName,
        desc: `从分享批次 ${String(shareId).slice(-8)} 下钻，下面只看这次分享带来的客户。`
      },
      { activeTab: "visitors" }
    );
  },
  handleOpenShowcaseAnalytics(event) {
    const showcaseId = event.currentTarget.dataset.showcaseId;
    if (!showcaseId) {
      this.handleOpenShowcases();
      return;
    }
    wx.navigateTo({ url: `/pages/showcase-analytics/index?id=${showcaseId}` });
  },
  handleOpenLeads() {
    wx.navigateTo({ url: "/pages/leads/index" });
  },
  handleOpenOrders() {
    wx.navigateTo({ url: "/pages/orders/index?role=seller" });
  },
  handleOpenCustomers() {
    wx.navigateTo({ url: "/pages/customers/index" });
  },
  handleOpenNoteData(event) {
    const noteId = event.currentTarget.dataset.noteId;
    if (!noteId) return;
    wx.navigateTo({ url: `/pages/note-actions/index?id=${noteId}` });
  },
  handleFilterByNote(event) {
    const { noteId, noteTitle } = event.currentTarget.dataset;
    if (!noteId && !noteTitle) return;
    this.applyDashboardView(this.data.dashboard, {
      type: "note",
      identityType: this.data.activeVisitorIdentity || "customer",
      noteId: noteId || "",
      noteTitle: noteTitle || "",
      label: noteTitle || "这条资料",
      desc: "从资料点击排行进入，下面只看点进过这条资料的访客和动作。"
    }, { activeTab: "visitors" });
  },
  handleOpenCustomerAction(event) {
    const sourceKey = event.currentTarget.dataset.source;
    const source = sourceKey === "visible"
      ? this.data.visibleLatestActions
      : sourceKey === "visibleFollowup"
        ? this.data.visibleFollowupActions
      : sourceKey === "followup"
        ? this.data.dashboard.followupActions
        : this.data.dashboard.latestActions;
    const action = (source || [])[Number(event.currentTarget.dataset.index)];
    if (!action) return;
    if (action.targetType === "order" && action.orderActionId) {
      wx.navigateTo({ url: `/pages/order-detail/index?id=${action.orderActionId}&role=seller` });
      return;
    }
    if (action.targetType === "lead" && action.leadReminderId) {
      wx.navigateTo({ url: `/pages/lead-detail/index?id=${action.leadReminderId}` });
      return;
    }
    if (action.noteId) {
      wx.navigateTo({ url: `/pages/note-actions/index?id=${action.noteId}` });
    }
  },
  handleOpenPriorityContact(event) {
    const item = (this.data.priorityContacts || [])[Number(event.currentTarget.dataset.index)];
    if (!item) return;
    if (item.kind === "visitor") {
      this.setData({
        selectedVisitor: item,
        visitorDetailOpen: true
      });
      return;
    }
    if (item.targetType === "order" && item.orderActionId) {
      wx.navigateTo({ url: `/pages/order-detail/index?id=${item.orderActionId}&role=seller` });
      return;
    }
    if (item.targetType === "lead" && item.leadReminderId) {
      wx.navigateTo({ url: `/pages/lead-detail/index?id=${item.leadReminderId}` });
      return;
    }
    if (item.noteId) {
      wx.navigateTo({ url: `/pages/note-actions/index?id=${item.noteId}` });
    }
  },
  handleCopyOpportunityScript(event) {
    const index = Number(event.currentTarget.dataset.index);
    const item = (this.data.opportunityAlerts || [])[index] || {};
    const script = item.followupScript || "";
    if (!script) {
      wx.showToast({ title: "暂无跟进话术", icon: "none" });
      return;
    }
    wx.setClipboardData({ data: script });
  },
  handleOpenDynamicItem(event) {
    const item = (this.data.customerDynamics || [])[Number(event.currentTarget.dataset.index)];
    if (!item) return;
    if (item.kind === "visitor") {
      this.setData({
        selectedVisitor: item,
        visitorDetailOpen: true
      });
      return;
    }
    this.handleOpenCustomerAction({
      currentTarget: {
        dataset: {
          source: "visible",
          index: item.sourceIndex
        }
      }
    });
  },
  handleOpenVisitorProfile(event) {
    const visitor = (this.data.visibleVisitorProfiles || [])[Number(event.currentTarget.dataset.index)];
    if (!visitor) return;
    this.setData({
      selectedVisitor: visitor,
      visitorDetailOpen: true
    });
  },
  handleCloseVisitorDetail() {
    this.setData({
      visitorDetailOpen: false,
      selectedVisitor: null
    });
  },
  noop() {},
  handleOpenSelectedVisitorTarget() {
    const visitor = this.data.selectedVisitor;
    if (!visitor) return;
    if (visitor.orderActionId) {
      wx.navigateTo({ url: `/pages/order-detail/index?id=${visitor.orderActionId}&role=seller` });
      return;
    }
    if (visitor.leadReminderId) {
      wx.navigateTo({ url: `/pages/lead-detail/index?id=${visitor.leadReminderId}` });
      return;
    }
    if (visitor.noteId) {
      wx.navigateTo({ url: `/pages/note-actions/index?id=${visitor.noteId}` });
      return;
    }
    wx.showToast({ title: "暂无可处理记录", icon: "none" });
  },
  handleRetry() {
    const user = getCurrentUser();
    if (!user) return;
    this.loadDashboard(user.id);
  },
  handleCallPhone(event) {
    const phone = event.currentTarget.dataset.phone;
    if (!phone) {
      wx.showToast({ title: "暂无手机号", icon: "none" });
      return;
    }
    wx.makePhoneCall({ phoneNumber: phone });
  },
  handleCopyWechat(event) {
    const wechat = event.currentTarget.dataset.wechat;
    if (!wechat) {
      wx.showToast({ title: "暂无微信号", icon: "none" });
      return;
    }
    wx.setClipboardData({ data: wechat });
  },
  getPrimaryLeadAction() {
    const actions = this.data.dashboard.latestActions || [];
    return actions.find((item) => item.leadReminderId) || null;
  },
  handleAddFollowUp() {
    const action = this.getPrimaryLeadAction();
    if (!action) {
      wx.showToast({ title: "暂无可跟进线索", icon: "none" });
      this.handleOpenLeads();
      return;
    }
    wx.showModal({
      title: "添加跟进",
      editable: true,
      placeholderText: "例如：已电话沟通，约明天继续看资料",
      confirmText: "保存",
      success: async (res) => {
        if (!res.confirm) return;
        const content = String(res.content || "").trim();
        if (!content) {
          wx.showToast({ title: "请填写跟进内容", icon: "none" });
          return;
        }
        const user = getCurrentUser();
        try {
          await api.updateLeadReminder(action.leadReminderId, {
            ownerUserId: user.id,
            logContent: content,
            status: "contacted"
          });
          wx.showToast({ title: "跟进已保存", icon: "success" });
          this.loadDashboard(user.id);
        } catch (error) {
          wx.showToast({ title: error.detail || "保存失败", icon: "none" });
        }
      }
    });
  },
  handleAddRemark() {
    const action = this.getPrimaryLeadAction();
    if (!action) {
      wx.showToast({ title: "暂无可备注线索", icon: "none" });
      this.handleOpenCustomers();
      return;
    }
    wx.showModal({
      title: "备注",
      editable: true,
      placeholderText: "记录客户偏好、预算、意向等",
      confirmText: "保存",
      success: async (res) => {
        if (!res.confirm) return;
        const content = String(res.content || "").trim();
        if (!content) {
          wx.showToast({ title: "请填写备注", icon: "none" });
          return;
        }
        const user = getCurrentUser();
        try {
          await api.updateLeadReminder(action.leadReminderId, {
            ownerUserId: user.id,
            note: content
          });
          wx.showToast({ title: "备注已保存", icon: "success" });
          this.loadDashboard(user.id);
        } catch (error) {
          wx.showToast({ title: error.detail || "保存失败", icon: "none" });
        }
      }
    });
  }
});
