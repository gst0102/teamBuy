const resourceStore = require("../../stores/resource-store");
const api = require("../../services/api");
const { buildDashboard, buildVisitGroups, getCurrentUser } = require("../../utils/dashboard");
const { navigateToResourceView } = require("../../utils/resource-navigation");
const { getModeConfig, readWorkspaceMode } = require("../../utils/workspace-mode");

const RADAR_ENTRY_TAB_KEY = "teambuy:radarEntryTab";
const RADAR_SOURCE_FILTER_KEY = "teambuy:radarSourceFilter";

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

function cardsForMode(cards = [], mode = "property") {
  if (mode === "property") return cards.filter((card) => isPropertyCard(card));
  if (mode === "groupbuy") return cards.filter((card) => isGroupbuyCard(card));
  if (mode === "service") return cards.filter((card) => isServiceCard(card));
  return cards;
}

function radarCopyForMode(mode = "property") {
  const copies = {
    property: {
      content: "房源",
      customer: "客户",
      compare: "同价位对比合集",
      emptyFollowup: "先把房源发给客户。",
      emptyVisitor: "客户打开房源后，我会自动打上价格敏感、位置优先、正在比较、沉默复活等标签。",
      emptyInsight: "先发出 3 套房源。",
      insightHelp: "我会帮你看哪套打开多、哪套咨询少，价格、联系方式和保障说明哪里该补强。",
      compareTitle: "建议生成对比合集",
      compareDesc: "当客户连续看多套相似房源时，把价格、位置和入住成本放在一页里，更容易促成回复。",
      compareButton: "生成对比合集建议"
    },
    groupbuy: {
      content: "商品",
      customer: "买家",
      compare: "商品对比合集",
      emptyFollowup: "先把商品发到群里。",
      emptyVisitor: "买家打开商品、接龙或咨询后，我会自动整理谁想买、谁在比较、谁要催单。",
      emptyInsight: "先发出 3 个商品。",
      insightHelp: "我会帮你看哪个商品打开多、接龙少，价格、规格和取货说明哪里该补强。",
      compareTitle: "建议生成商品对比",
      compareDesc: "当买家连续看多个相似商品时，把价格、规格、取货方式放在一页里，更容易促成下单。",
      compareButton: "生成商品对比建议"
    },
    service: {
      content: "服务页",
      customer: "咨询客户",
      compare: "服务方案对比",
      emptyFollowup: "先把名片或服务方案发给客户。",
      emptyVisitor: "客户打开服务页后，我会自动整理关注价格、案例、保障或预约意向。",
      emptyInsight: "先发出 3 份服务资料。",
      insightHelp: "我会帮你看哪份服务页打开多、咨询少，案例、报价和联系方式哪里该补强。",
      compareTitle: "建议生成服务方案对比",
      compareDesc: "当客户连续看多个服务方案时，把价格、服务内容、案例和预约入口放在一页里，更容易回复。",
      compareButton: "生成方案对比建议"
    },
    notes: {
      content: "资料",
      customer: "访客",
      compare: "资料合集",
      emptyFollowup: "先分享一份资料。",
      emptyVisitor: "访客打开资料后，我会自动整理复访、重点查看和分享反馈。",
      emptyInsight: "先发出 3 份资料。",
      insightHelp: "我会帮你看哪份资料打开多、互动少，标题、重点和联系方式哪里该补强。",
      compareTitle: "建议生成资料合集",
      compareDesc: "当访客连续看多份相似资料时，把重点放在一个合集里，更容易继续阅读。",
      compareButton: "生成合集建议"
    }
  };
  return copies[mode] || copies.property;
}

function displayName(item = {}) {
  return item.nickname || item.customerName || item.name || (item.anonymous ? "匿名访客" : "微信客户");
}

function firstText(values, fallback) {
  if (Array.isArray(values) && values.length) return values[0];
  return fallback;
}

function normalizeAlert(item = {}, index = 0) {
  const title = item.message || `${displayName(item)}有新的浏览动态`;
  const reason = item.reason || item.intentExplanation || "有新的浏览或咨询动作。";
  const action = item.suggestedAction || "继续观察或轻触达";
  const sourceTitle = item.noteTitle || firstText(item.noteTitles, "客户资料");
  const tags = buildAlertTags(item);
  const script = item.followupScript || scriptForTags(tags, sourceTitle);
  return {
    id: item.id || `alert-${index}`,
    name: displayName(item),
    avatarText: displayName(item).slice(0, 1),
    intentLabel: item.intentLabel || (item.intentLevel ? `${item.intentLevel}意向` : "中意向"),
    stateLabel: item.isRevival ? "沉默复活" : item.intentLevel === "高" ? "高意向" : "持续关注",
    title,
    reason,
    action,
    script,
    timeText: item.timeText || "刚刚",
    noteId: item.noteId || firstText(item.noteIds, ""),
    sourceId: item.sourceId || item.resourceId || item.showcaseId || item.noteId || firstText(item.noteIds, ""),
    noteTitle: sourceTitle,
    tags,
    isPeerLike: isPeerLike(item, tags),
    nextStep: nextStepForTags(tags, action)
  };
}

function normalizeProfile(item = {}, index = 0) {
  const name = displayName(item);
  const focusTags = buildProfileTags(item);
  const viewed = firstText(item.noteTitles, "资料");
  const reason = item.intentExplanation || item.reasonText || `看过 ${viewed}，打开 ${item.viewCount || 0} 次。`;
  const action = item.suggestedAction || (item.noteIds && item.noteIds.length > 1 ? "建议生成同价位对比合集" : "建议轻触达");
  return {
    id: item.id || `profile-${index}`,
    name,
    avatarText: name.slice(0, 1),
    intentLabel: item.intentLabel || (item.intentLevel ? `${item.intentLevel}意向` : "待判断"),
    stateLabel: item.isRevival ? "沉默复活" : (item.intentLevel === "高" ? "高意向" : "持续关注"),
    title: `${name} · ${viewed}`,
    reason,
    action,
    script: item.followupScript || scriptForTags(focusTags, viewed),
    timeText: item.timeText || "",
    noteId: firstText(item.noteIds, ""),
    sourceId: item.sourceId || item.resourceId || item.showcaseId || firstText(item.noteIds, ""),
    noteTitle: viewed,
    tags: focusTags,
    isPeerLike: isPeerLike(item, focusTags),
    nextStep: nextStepForTags(focusTags, action)
  };
}

function buildAlertTags(item = {}) {
  const tags = [];
  (item.focusSections || []).forEach((section) => {
    if (/价格|优惠/.test(section)) tags.push("价格敏感");
    if (/地址|位置/.test(section)) tags.push("位置优先");
    if (/联系方式/.test(section)) tags.push("反复看联系方式");
    if (/FAQ|保障/.test(section)) tags.push("关注保障");
    if (/案例|成果/.test(section)) tags.push("需要信任");
  });
  (item.customerTags || []).forEach((tag) => tags.push(tag));
  if (item.isRevival) tags.push("沉默复活");
  if (item.intentLevel === "高") tags.push("高意向");
  if (item.visitorIdentityType === "peer_agent") tags.push("疑似同行");
  if (item.visitorIdentityType === "upstream") tags.push("疑似上游");
  const unique = tags.filter((tag, index) => tag && tags.indexOf(tag) === index);
  return unique.length ? unique.slice(0, 5) : ["有新动作", "待判断"];
}

function buildProfileTags(item = {}) {
  const tags = [];
  const sections = item.focusSections || [];
  const noteCount = (item.noteIds || []).length || (item.noteTitles || []).length;
  sections.forEach((section) => {
    if (/价格|优惠/.test(section)) tags.push("价格敏感");
    if (/地址|位置/.test(section)) tags.push("位置优先");
    if (/联系方式/.test(section)) tags.push("联系意向");
    if (/FAQ|保障/.test(section)) tags.push("关注保障");
    if (/案例|成果/.test(section)) tags.push("需要信任");
  });
  if (item.isRevival) tags.push("沉默复活");
  if ((item.viewCount || 0) >= 3) tags.push("反复查看");
  if (noteCount >= 2) tags.push("正在比较");
  if ((item.consultCount || 0) > 0) tags.push("有咨询动作");
  if (item.visitorIdentityType === "peer_agent") tags.push("疑似同行");
  if (item.visitorIdentityType === "upstream") tags.push("疑似上游");
  if ((item.shareIds || []).length >= 2) tags.push("多次触达");
  (item.customerTags || []).forEach((tag) => tags.push(tag));
  const unique = tags.filter((tag, index) => tag && tags.indexOf(tag) === index);
  if (unique.length) return unique.slice(0, 5);
  if (item.intentLevel === "高") return ["重点客户", "建议先跟"];
  if (item.anonymous) return ["匿名访客", "待留资"];
  return ["持续关注"];
}

function isPeerLike(item = {}, tags = []) {
  return item.visitorIdentityType === "peer_agent" ||
    item.visitorIdentityType === "upstream" ||
    tags.includes("疑似同行") ||
    tags.includes("疑似上游");
}

function scriptForTags(tags = [], title = "这份资料") {
  const text = tags.join(" ");
  if (/价格|优惠|预算/.test(text)) return `您好，刚看到你比较关注《${title}》的价格，我可以再发你一份同价位对比。`;
  if (/位置|地址|地铁/.test(text)) return `您好，《${title}》的位置你可以先看下，我也可以补几条附近可选方案给你对比。`;
  if (/联系方式|联系意向/.test(text)) return `您好，刚看到你看了《${title}》的联系方式，需要的话我现在帮你确认细节。`;
  if (/案例|信任|保障|FAQ/.test(text)) return `您好，《${title}》我可以再发你几个案例和保障说明，方便你判断。`;
  if (/沉默复活/.test(text)) return `您好，看到你又打开了《${title}》，我把最新情况和可选方案发你参考一下。`;
  if (/正在比较|反复查看/.test(text)) return `您好，我看你比较关注《${title}》，我可以再发你几份相近的做对比。`;
  return `您好，刚看到你看了《${title}》，我可以把重点信息整理给你。`;
}

function nextStepForTags(tags = [], action = "") {
  const text = `${tags.join(" ")} ${action || ""}`;
  if (/价格|优惠|预算|对比/.test(text)) return { text: "发对比合集", tone: "compare", hint: "把同价位或相似资料整理给客户" };
  if (/位置|地址|地铁/.test(text)) return { text: "补附近方案", tone: "location", hint: "发位置、交通和可选方案" };
  if (/联系方式|联系意向|咨询/.test(text)) return { text: "立即轻触达", tone: "contact", hint: "先用短话术确认需求" };
  if (/案例|信任|保障|FAQ/.test(text)) return { text: "发案例保障", tone: "trust", hint: "补客户反馈、案例或保障说明" };
  if (/沉默复活/.test(text)) return { text: "发最新情况", tone: "revival", hint: "用更新信息重新打开对话" };
  if (/同行|上游/.test(text)) return { text: "先观察", tone: "muted", hint: "不进入主跟进池" };
  return { text: "详情", tone: "default", hint: "看浏览痕迹和联系方式" };
}

function normalizeInsight(item = {}, index = 0) {
  return {
    id: item.noteId || `insight-${index}`,
    noteId: item.noteId || "",
    title: item.title || "资料优化建议",
    stats: `打开 ${item.viewCount || 0} · 咨询 ${item.consultCount || 0}`,
    suggestion: item.suggestion || "建议补充价格、优惠、联系方式或保障说明。",
    action: /联系方式/.test(item.suggestion || "") ? "把联系方式提前" : "补充成交说明"
  };
}

function buildFallbackAlerts(groups = []) {
  return groups
    .filter((item) => item.highIntent || (item.viewers || []).length)
    .slice(0, 3)
    .map((item, index) => {
      const viewer = (item.viewers || [])[0] || {};
      const name = viewer.nickname || "匿名访客";
      return {
        id: `fallback-${item.id || index}`,
        name,
        avatarText: name.slice(0, 1),
        intentLabel: item.highIntent ? "高意向" : "中意向",
        stateLabel: item.highIntent ? "高意向" : "持续关注",
        title: `${name}看过《${item.title || "资料"}》`,
        reason: item.highIntent ? "出现重复打开或互动，建议优先跟进。" : "有新的浏览动态，可继续观察。",
        action: item.highIntent ? "查看浏览痕迹后及时联系" : "观察后轻触达",
        script: `您好，刚看到你看了《${item.title || "这套房源"}》，我可以把价格、位置和入住成本发你对比一下。`,
        timeText: viewer.timeText || "",
        noteId: item.id || "",
        sourceId: item.id || "",
        noteTitle: item.title || "资料",
        tags: item.highIntent ? ["重点客户"] : ["浏览客户"],
        isPeerLike: false,
        nextStep: item.highIntent
          ? { text: "立即轻触达", tone: "contact", hint: "先用短话术确认需求" }
          : { text: "继续观察", tone: "muted", hint: "有重复打开再跟进" }
      };
    });
}

function matchSourceFilter(item = {}, sourceFilter = null) {
  if (!sourceFilter || (!sourceFilter.noteId && !sourceFilter.resourceId && !sourceFilter.showcaseId)) return true;
  const sourceIds = [
    item.noteId,
    item.sourceId,
    item.resourceId,
    item.showcaseId,
    ...(item.showcaseIds || []),
    ...(item.noteIds || [])
  ].filter(Boolean).map(String);
  const targetIds = [sourceFilter.noteId, sourceFilter.resourceId, sourceFilter.showcaseId].filter(Boolean).map(String);
  return targetIds.some((id) => sourceIds.includes(id));
}

function applySourceFilter(items = [], sourceFilter = null) {
  if (!sourceFilter) return items;
  return items.filter((item) => matchSourceFilter(item, sourceFilter));
}

function buildTimeline(alerts = [], profiles = []) {
  const source = alerts.length ? alerts : profiles;
  return source.slice(0, 3).map((item, index) => ({
    id: item.id || `timeline-${index}`,
    title: index === 0 ? "打开重点资料" : index === 1 ? "查看价格/联系方式" : "进入跟进队列",
    desc: item.title || item.reason || "客户有新的浏览动作",
    timeText: item.timeText || (index === 0 ? "刚刚" : "")
  }));
}

function buildSummaryView(tab, summary = {}, radarCards = [], visitorCards = [], insights = []) {
  if (tab === "insights") {
    const priceCount = insights.filter((item) => /价格|优惠|押金|月付/.test(item.suggestion || "")).length;
    const contactCount = insights.filter((item) => /联系|电话|微信/.test(item.suggestion || "")).length;
    return {
      title: "资料优化机会",
      sub: "我会从打开、停留和咨询里找出哪份资料该提前、补充或强化。",
      badge: `${insights.length} 条建议`,
      metrics: [
        { key: "pending", value: insights.length, label: "待优化资料" },
        { key: "lowConsult", value: insights.filter((item) => /咨询少|打开多/.test(item.suggestion || "")).length, label: "打开多咨询少" },
        { key: "price", value: priceCount, label: "价格关注" },
        { key: "contact", value: contactCount, label: "联系方式关注" }
      ]
    };
  }
  if (tab === "visitors") {
    return {
      title: "访客画像",
      sub: "把身份、意向、关注点和行为证据放在一起，方便判断怎么聊。",
      badge: `${visitorCards.length} 位访客`,
      metrics: [
        { key: "high", value: visitorCards.filter((item) => /高/.test(item.intentLabel)).length, label: "高意向" },
        { key: "compare", value: visitorCards.filter((item) => (item.tags || []).includes("正在比较")).length, label: "正在比较" },
        { key: "price", value: visitorCards.filter((item) => (item.tags || []).includes("价格敏感")).length, label: "价格敏感" },
        { key: "revival", value: visitorCards.filter((item) => item.stateLabel === "沉默复活").length, label: "沉默复活" }
      ]
    };
  }
  return {
    title: "今天优先跟进",
    sub: "AI会先把最值得联系的人排在前面。",
    badge: `${summary.pending || 0} 条新提醒`,
    metrics: [
      { key: "high", value: summary.highIntent || 0, label: "高意向" },
      { key: "pending", value: summary.pending || 0, label: "待跟进" },
      { key: "revival", value: summary.revival || 0, label: "复活机会" },
      { key: "filtered", value: summary.filtered || 0, label: "同行过滤" }
    ]
  };
}

function buildAssistantBrief(tab, summary = {}, radarCards = [], visitorCards = [], insights = [], copy = radarCopyForMode()) {
  if (tab === "insights") {
    if (insights.length) {
      const first = insights[0];
      return `今天优先优化《${first.title}》，${first.suggestion || "先补充客户最关心的信息。"}`;
    }
    return `${copy.emptyInsight}我会帮你找出打开多、咨询少、被反复看的内容。`;
  }
  if (tab === "visitors") {
    if (visitorCards.length) {
      const highCount = visitorCards.filter((item) => /高/.test(item.intentLabel)).length;
      const compareCount = visitorCards.filter((item) => (item.tags || []).includes("正在比较")).length;
      if (highCount) return `今天有 ${highCount} 位${copy.customer}更值得关注，先看他们关注的${copy.content}和标签。`;
      if (compareCount) return `${compareCount} 位${copy.customer}正在比较多份${copy.content}，适合发${copy.compare}。`;
      return `已有 ${visitorCards.length} 位访客画像，先看谁反复查看、谁关注价格。`;
    }
    return copy.emptyVisitor;
  }
  if (radarCards.length) {
    const first = radarCards[0];
    return `今天先跟 ${first.name}：${first.reason || first.action || "有新的浏览动作。"}`;
  }
  if (summary.pending) return `今天有 ${summary.pending} 条新提醒，先处理高意向和沉默复活客户。`;
  return "先发资料，雷达会亮。";
}

Page({
  data: {
    loading: false,
    activeTab: "followup",
    tabs: [
      { key: "followup", label: "待跟进" },
      { key: "visitors", label: "访客" },
      { key: "insights", label: "资料优化" }
    ],
    workspaceMode: "property",
    modeConfig: getModeConfig("property"),
    radarCopy: radarCopyForMode("property"),
    summary: {
      highIntent: 0,
      pending: 0,
      revival: 0,
      filtered: 0
    },
    summaryView: buildSummaryView("followup", {
      highIntent: 0,
      pending: 0,
      revival: 0,
      filtered: 0
    }),
    assistantBrief: buildAssistantBrief("followup", {}, [], [], [], radarCopyForMode("property")),
    radarCards: [],
    visitorCards: [],
    insights: [],
    timeline: [],
    suggestedActions: [],
    sourceFilter: null
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const workspaceMode = readWorkspaceMode(currentUser.id) || "property";
    let activeTab = this.data.activeTab || "followup";
    try {
      const storedTab = wx.getStorageSync(RADAR_ENTRY_TAB_KEY);
      if (["followup", "visitors", "insights"].includes(storedTab)) {
        activeTab = storedTab;
        wx.removeStorageSync(RADAR_ENTRY_TAB_KEY);
      }
    } catch (error) {}
    let sourceFilter = null;
    try {
      const storedFilter = wx.getStorageSync(RADAR_SOURCE_FILTER_KEY);
      if (storedFilter && Date.now() - Number(storedFilter.ts || 0) < 10 * 60 * 1000) {
        sourceFilter = storedFilter;
      }
      wx.removeStorageSync(RADAR_SOURCE_FILTER_KEY);
    } catch (error) {}
    this.setData({
      workspaceMode,
      modeConfig: getModeConfig(workspaceMode),
      radarCopy: radarCopyForMode(workspaceMode),
      activeTab,
      sourceFilter
    });
    this.loadRadar();
  },
  async loadRadar() {
    const currentUser = getCurrentUser();
    const mode = this.data.workspaceMode || "property";
    const radarCopy = radarCopyForMode(mode);
    this.setData({ loading: true });
    try {
      const [cards, businessRes] = await Promise.all([
        resourceStore.listCards({ ownerUserId: currentUser.id }, { force: true }),
        api.fetchBusinessDashboard(currentUser.id, currentUser.id, mode === "property" ? "property" : mode).catch(() => null)
      ]);
      const scopedCards = cardsForMode(cards || [], mode);
      const localDashboard = buildDashboard(scopedCards);
      const groups = buildVisitGroups(scopedCards);
      const data = (businessRes && businessRes.data) || {};
      const alerts = (data.opportunityAlerts || []).map(normalizeAlert);
      const profiles = (data.radarProfiles || []).map(normalizeProfile);
      const fallbackAlerts = alerts.length ? alerts : buildFallbackAlerts(groups);
      const rawRadarCards = fallbackAlerts.length ? fallbackAlerts : profiles.slice(0, 5);
      const rawVisitorCards = profiles.length ? profiles.slice(0, 12) : buildFallbackAlerts(groups).slice(0, 12);
      const radarCards = applySourceFilter(rawRadarCards.filter((item) => !item.isPeerLike), this.data.sourceFilter);
      const visitorCards = applySourceFilter(rawVisitorCards, this.data.sourceFilter);
      const insights = applySourceFilter((data.contentInsights || []).map(normalizeInsight), this.data.sourceFilter);
      const summary = data.opportunitySummary || {};
      const suggestedActions = [
        radarCards[0] ? `查看${radarCards[0].name}的浏览痕迹和联系方式` : "",
        radarCards[0] && /对比/.test(radarCards[0].action) ? "生成同价位对比合集" : "",
        insights[0] ? `优化《${insights[0].title}》` : ""
      ].filter(Boolean);
      const scoped = Boolean(this.data.sourceFilter);
      const radarSummary = {
        highIntent: scoped ? radarCards.filter((item) => /高/.test(item.intentLabel)).length : (summary.todayHighIntentCount || summary.highIntentCount || radarCards.filter((item) => /高/.test(item.intentLabel)).length || 0),
        pending: scoped ? radarCards.length : (summary.pendingFollowupCount || radarCards.length || 0),
        revival: scoped ? radarCards.filter((item) => item.stateLabel === "沉默复活").length : (summary.revivalCount || (data.revivalAlerts || []).length || radarCards.filter((item) => item.stateLabel === "沉默复活").length || 0),
        filtered: scoped ? rawRadarCards.filter((item) => item.isPeerLike && matchSourceFilter(item, this.data.sourceFilter)).length : (summary.filteredPeerCount || 0)
      };
      this.setData({
        summary: radarSummary,
        summaryView: buildSummaryView(this.data.activeTab, radarSummary, radarCards, visitorCards, insights),
        assistantBrief: buildAssistantBrief(this.data.activeTab, radarSummary, radarCards, visitorCards, insights, radarCopy),
        radarCards,
        visitorCards,
        insights,
        timeline: buildTimeline(radarCards, profiles),
        suggestedActions,
        localDashboard
      });
    } catch (error) {
      wx.showToast({ title: "雷达加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleTabChange(event) {
    const activeTab = event.currentTarget.dataset.key || "followup";
    this.setData({
      activeTab,
      summaryView: buildSummaryView(activeTab, this.data.summary, this.data.radarCards, this.data.visitorCards, this.data.insights),
      assistantBrief: buildAssistantBrief(activeTab, this.data.summary, this.data.radarCards, this.data.visitorCards, this.data.insights, this.data.radarCopy)
    });
  },
  handleClearSourceFilter() {
    this.setData({ sourceFilter: null });
    this.loadRadar();
  },
  handleCopyScript(event) {
    const index = Number(event.currentTarget.dataset.index);
    const item = (this.data.radarCards || [])[index] || {};
    if (!item.script) {
      wx.showToast({ title: "暂无话术", icon: "none" });
      return;
    }
    wx.setClipboardData({ data: item.script });
  },
  handleNextStepAction(event) {
    const index = Number(event.currentTarget.dataset.index);
    const item = (this.data.radarCards || [])[index] || {};
    const text = `${(item.nextStep && item.nextStep.text) || ""} ${item.action || ""}`;
    if (/对比|合集/.test(text)) {
      this.handleGenerateCompare();
      return;
    }
    this.openRadarDetail();
  },
  handleOpenRadarDetail() {
    this.openRadarDetail();
  },
  openRadarDetail() {
    wx.navigateTo({ url: `/pages/business-dashboard/index?mode=${encodeURIComponent(this.data.workspaceMode || "property")}&tab=visitors` });
  },
  handleMarkContacted() {
    wx.showToast({ title: "已记录本次跟进", icon: "none" });
  },
  handleOpenRadarMore(event) {
    const index = Number(event.currentTarget.dataset.index);
    const item = (this.data.radarCards || [])[index] || {};
    const actions = [];
    if (item.noteId && item.nextStep && item.nextStep.tone === "compare") {
      actions.push("生成对比");
    }
    if (item.noteId) {
      actions.push("打开来源");
    }
    actions.push("标记已联系");
    wx.showActionSheet({
      itemList: actions,
      success: ({ tapIndex }) => {
        const action = actions[tapIndex];
        if (action === "生成对比") {
          this.handleGenerateCompare();
          return;
        }
        if (action === "打开来源" && item.noteId) {
          this.handleOpenResource({ currentTarget: { dataset: { id: item.noteId } } });
          return;
        }
        if (action === "标记已联系") {
          this.handleMarkContacted();
        }
      }
    });
  },
  handleOpenBusinessDashboard(event) {
    const tab = (event && event.currentTarget && event.currentTarget.dataset.tab) || "followup";
    wx.navigateTo({ url: `/pages/business-dashboard/index?mode=${encodeURIComponent(this.data.workspaceMode || "property")}&tab=${tab}` });
  },
  handleGenerateCompare() {
    const mode = this.data.workspaceMode || "property";
    const source = (this.data.radarCards || []).find((item) => item.noteId) || (this.data.visitorCards || []).find((item) => item.noteId) || {};
    const params = [
      `mode=${encodeURIComponent(mode)}`,
      "method=radar_compare",
      source.noteId ? `noteId=${encodeURIComponent(source.noteId)}` : ""
    ].filter(Boolean).join("&");
    wx.navigateTo({ url: `/pages/showcase-edit/index?${params}` });
  },
  handleOpenResource(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({
      url: `/pages/note-preview/index?id=${encodeURIComponent(id)}`,
      fail: () => navigateToResourceView(id)
    });
  }
});
