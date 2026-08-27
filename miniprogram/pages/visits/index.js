const customerIntelligenceStore = require("../../stores/customer-intelligence-store");
const customerDetailStore = require("../../stores/customer-detail-store");
const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { navigateToNoteView } = require("../../utils/resource-navigation");
const { getModeConfig, readWorkspaceMode } = require("../../utils/workspace-mode");
const { getCustomerPaymentState } = require("../../utils/customer-access");

const RADAR_ENTRY_TAB_KEY = "teambuy:radarEntryTab";
const RADAR_SOURCE_FILTER_KEY = "teambuy:radarSourceFilter";

function createOperationId(action, target) {
  return `${action}:${target || "customer"}:${Date.now()}:${Math.random().toString(36).slice(2, 10)}`;
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

function formatActivityTime(value) {
  if (!value) return "时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "最近";
  const now = new Date();
  const pad = (number) => String(number).padStart(2, "0");
  if (date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate()) {
    return `今天 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }
  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatNextFollowUp(value) {
  const text = String(value || "").trim();
  if (!text) return "未设置下次跟进时间";
  // Date-only values are parsed as UTC by some JS runtimes. Read the date
  // portion directly so a scheduled 2026-08-28 never renders as Aug 27 in
  // China Standard Time.
  const dateOnly = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (dateOnly) return `${Number(dateOnly[2])}月${Number(dateOnly[3])}日`;
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function buildSeenContentText(item = {}, sourceTitle = "") {
  const sections = [...new Set((item.focusSections || []).filter(Boolean).map((section) => String(section).trim()))];
  if (sections.length) return `重点查看：${sections.slice(0, 3).join("、")}`;
  if (sourceTitle && sourceTitle !== "客户资料" && sourceTitle !== "资料") return `查看《${sourceTitle}》的公开内容`;
  return "查看公开内容";
}

function buildRecentActivityText(item = {}, sourceTitle = "") {
  const parts = [];
  if (sourceTitle && sourceTitle !== "客户资料" && sourceTitle !== "资料") parts.push(`《${sourceTitle}》`);
  const viewCount = Number(item.viewCount || item.openCount || 0);
  const actionCount = Number(item.actionCount || 0);
  const consultCount = Number(item.consultCount || 0);
  if (viewCount) parts.push(`打开 ${viewCount} 次`);
  if (actionCount) parts.push(`${actionCount} 次互动`);
  if (consultCount) parts.push(`${consultCount} 次咨询`);
  return `${parts.length ? parts.join(" · ") : "有新的浏览动作"} · ${formatActivityTime(item.lastActivityAt || item.abandonedAt || item.updatedAt || item.createdAt)}`;
}

function normalizeAlert(item = {}, index = 0) {
  const title = item.message || `${displayName(item)}有新的浏览动态`;
  const reason = item.reason || item.intentExplanation || "有新的浏览或咨询动作。";
  const action = item.suggestedAction || "继续观察或轻触达";
  const sourceTitle = item.noteTitle || firstText(item.noteTitles, "客户资料");
  // This link is rendered as a note preview. Do not fall back to a Card,
  // resource, or showcase ID here; those IDs belong to different routes.
  const sourceId = item.sourceNoteId || item.noteId || firstText(item.noteIds, "");
  const tags = buildAlertTags(item);
  const script = item.followupScript || scriptForTags(tags, sourceTitle);
  return {
    id: item.id || `alert-${index}`,
    customerId: item.visitorIdentityId || item.customerId || item.viewerUserId || item.anonymousId || "",
    leadReminderId: item.leadReminderId || "",
    leadVersion: item.leadVersion !== undefined ? Number(item.leadVersion) : (item.version !== undefined ? Number(item.version) : null),
    viewerUserId: item.viewerUserId || "",
    anonymousId: item.anonymousId || "",
    visitorIdentityId: item.visitorIdentityId || item.customerId || "",
    avatarUrl: item.avatarUrl || "",
    name: displayName(item),
    avatarText: displayName(item).slice(0, 1),
    intentLabel: item.intentLabel || (item.intentLevel ? `${item.intentLevel}意向` : "中意向"),
    isHighIntent: item.intentLevel === "高" || item.intentLevel === "high" || String(item.intentLabel || "").includes("高意向"),
    stateLabel: item.isRevival ? "沉默复活" : item.intentLevel === "高" ? "高意向" : "持续关注",
    title,
    reason,
    action,
    script,
    timeText: item.timeText || "刚刚",
    noteId: item.noteId || firstText(item.noteIds, ""),
    noteIds: item.noteIds || [],
    noteTitles: item.noteTitles || [],
    focusSections: item.focusSections || [],
    sourceId,
    sourceNoteId: sourceId,
    noteTitle: sourceTitle,
    tags,
    viewCount: Number(item.viewCount || item.openCount || 0),
    consultCount: Number(item.consultCount || 0),
    actionCount: Number(item.actionCount || 0),
    evidenceText: buildEvidenceText(item),
    seenContentText: item.seenContentText || buildSeenContentText(item, sourceTitle),
    recentActivityText: item.recentActivityText || buildRecentActivityText(item, sourceTitle),
    lastActivityAt: item.lastActivityAt || item.updatedAt || item.createdAt || "",
    leadStatus: item.leadStatus || "pending",
    leadStatusText: item.leadStatusText || "待跟进",
    nextFollowUpAt: item.nextFollowUpAt || "",
    nextFollowUpText: formatNextFollowUp(item.nextFollowUpAt),
    isAnonymous: Boolean(item.anonymous),
    hasLead: Boolean(item.leadReminderId),
    abandonedAt: item.abandonedAt || "",
    isPeerLike: isPeerLike(item, tags),
    nextStep: nextStepForTags(tags, action)
  };
}

function normalizeProfile(item = {}, index = 0) {
  const name = displayName(item);
  const focusTags = buildProfileTags(item);
  const viewed = firstText(item.noteTitles, "资料");
  // Customer radar projections expose note IDs for the content the customer
  // actually saw. Keep this separate from resource/showcase identifiers.
  const sourceId = item.sourceNoteId || item.noteId || firstText(item.noteIds, "");
  const reason = item.intentExplanation || item.reasonText || `看过 ${viewed}，打开 ${item.viewCount || 0} 次。`;
  const action = item.suggestedAction || (item.noteIds && item.noteIds.length > 1 ? "建议生成同价位对比合集" : "建议轻触达");
  return {
    id: item.id || `profile-${index}`,
    customerId: item.visitorIdentityId || item.customerId || item.viewerUserId || item.anonymousId || item.id || "",
    leadReminderId: item.leadReminderId || "",
    leadVersion: item.leadVersion !== undefined ? Number(item.leadVersion) : (item.version !== undefined ? Number(item.version) : null),
    viewerUserId: item.viewerUserId || "",
    anonymousId: item.anonymousId || "",
    visitorIdentityId: item.visitorIdentityId || item.customerId || item.id || "",
    avatarUrl: item.avatarUrl || "",
    name,
    avatarText: name.slice(0, 1),
    intentLabel: item.intentLabel || (item.intentLevel ? `${item.intentLevel}意向` : "待判断"),
    isHighIntent: item.intentLevel === "高" || item.intentLevel === "high" || String(item.intentLabel || "").includes("高意向"),
    stateLabel: item.isRevival ? "沉默复活" : (item.intentLevel === "高" ? "高意向" : "持续关注"),
    title: `${name} · ${viewed}`,
    reason,
    action,
    script: item.followupScript || scriptForTags(focusTags, viewed),
    timeText: item.timeText || "",
    noteId: firstText(item.noteIds, ""),
    noteIds: item.noteIds || [],
    noteTitles: item.noteTitles || [],
    focusSections: item.focusSections || [],
    phone: item.phone || item.displayPhone || "",
    wechat: item.wechat || item.displayWechat || "",
    budgetText: item.budgetText || "",
    customerTags: item.customerTags || [],
    sourceId,
    sourceNoteId: sourceId,
    noteTitle: viewed,
    tags: focusTags,
    viewCount: Number(item.viewCount || item.openCount || 0),
    consultCount: Number(item.consultCount || 0),
    actionCount: Number(item.actionCount || 0),
    evidenceText: buildEvidenceText(item),
    seenContentText: item.seenContentText || buildSeenContentText(item, viewed),
    recentActivityText: item.recentActivityText || buildRecentActivityText(item, viewed),
    lastActivityAt: item.lastActivityAt || item.updatedAt || item.createdAt || "",
    leadStatus: item.leadStatus || "pending",
    leadStatusText: item.leadStatusText || "待跟进",
    nextFollowUpAt: item.nextFollowUpAt || "",
    nextFollowUpText: formatNextFollowUp(item.nextFollowUpAt),
    isAnonymous: Boolean(item.anonymous),
    hasLead: Boolean(item.leadReminderId),
    abandonedAt: item.abandonedAt || "",
    isPeerLike: isPeerLike(item, focusTags),
    nextStep: nextStepForTags(focusTags, action)
  };
}

function buildEvidenceText(item = {}) {
  const parts = [];
  const viewCount = Number(item.viewCount || item.openCount || 0);
  const actionCount = Number(item.actionCount || 0);
  const consultCount = Number(item.consultCount || 0);
  const durationSeconds = Number(item.durationSeconds || 0);
  if (viewCount) parts.push(`打开 ${viewCount} 次`);
  if (actionCount) parts.push(`${actionCount} 次互动`);
  if (consultCount) parts.push(`${consultCount} 次咨询`);
  if (durationSeconds >= 60) parts.push(`停留 ${Math.round(durationSeconds / 60)} 分钟`);
  if (item.timeText) parts.push(item.timeText);
  return parts.slice(0, 3).join(" · ") || "最近有新的浏览动作";
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

function sameRadarCustomer(left = {}, right = {}) {
  const leftIds = [left.visitorIdentityId, left.customerId, left.viewerUserId, left.anonymousId, left.leadReminderId]
    .filter(Boolean)
    .map(String);
  const rightIds = [right.visitorIdentityId, right.customerId, right.viewerUserId, right.anonymousId, right.leadReminderId]
    .filter(Boolean)
    .map(String);
  if (!leftIds.length || !rightIds.length) return left.id && right.id && String(left.id) === String(right.id);
  return leftIds.some((id) => rightIds.includes(id));
}

function followupActionHint(item = {}) {
  return {
    visitorIdentityId: item.visitorIdentityId || item.customerId || "",
    viewerUserId: item.viewerUserId || "",
    anonymousId: item.anonymousId || "",
    sourceNoteId: item.sourceNoteId || item.sourceId || item.noteId || (item.noteIds && item.noteIds[0]) || "",
    nickname: item.name || item.nickname || "",
    avatarUrl: item.avatarUrl || "",
    viewCount: Number(item.viewCount || 0),
    lastActivityAt: item.lastActivityAt || ""
  };
}

function followupStatusText(status = "") {
  return {
    pending: "待跟进",
    following: "跟进中",
    contacted: "已联系",
    paused: "已放弃跟进"
  }[status] || "";
}

function followupMutationItem(item = {}, mutation = {}) {
  const status = mutation.status || ({
    start: "following",
    continue: "following",
    abandon: "paused",
    restore: "pending"
  }[mutation.action] || "");
  const actionText = {
    start: "已开始跟进",
    continue: "已继续跟进",
    abandon: "已放弃跟进",
    restore: "已恢复跟进"
  }[mutation.action] || "";
  return {
    ...item,
    customerId: mutation.customerId || item.customerId || "",
    visitorIdentityId: mutation.visitorIdentityId || item.visitorIdentityId || "",
    viewerUserId: mutation.viewerUserId || item.viewerUserId || "",
    anonymousId: mutation.anonymousId || item.anonymousId || "",
    leadReminderId: mutation.leadId || item.leadReminderId || "",
    leadVersion: mutation.leadVersion === null || mutation.leadVersion === undefined
      ? item.leadVersion
      : Number(mutation.leadVersion),
    leadStatus: status,
    leadStatusText: followupStatusText(status),
    nextFollowUpAt: mutation.nextFollowUpAt !== undefined ? mutation.nextFollowUpAt : (item.nextFollowUpAt || ""),
    nextFollowUpText: formatNextFollowUp(mutation.nextFollowUpAt !== undefined ? mutation.nextFollowUpAt : item.nextFollowUpAt),
    hasLead: true,
    stateLabel: status === "paused" ? "已放弃跟进" : "持续关注"
  };
}

function applyRadarMutations(collections = {}, mutations = []) {
  let next = {
    allRadarCards: [...(collections.allRadarCards || [])],
    allVisitorCards: [...(collections.allVisitorCards || [])],
    allFollowingCards: [...(collections.allFollowingCards || [])],
    allAbandonedCards: [...(collections.allAbandonedCards || [])]
  };
  let changed = false;
  (mutations || []).forEach((mutation) => {
    const target = {
      id: mutation.leadId || mutation.customerId || mutation.visitorIdentityId || mutation.viewerUserId || mutation.anonymousId,
      customerId: mutation.customerId || mutation.visitorIdentityId || "",
      visitorIdentityId: mutation.visitorIdentityId || mutation.customerId || "",
      viewerUserId: mutation.viewerUserId || "",
      anonymousId: mutation.anonymousId || "",
      leadReminderId: mutation.leadId || ""
    };
    const all = [
      ...next.allRadarCards,
      ...next.allVisitorCards,
      ...next.allFollowingCards,
      ...next.allAbandonedCards
    ];
    const existing = all.find((item) => sameRadarCustomer(item, target));
    if (!existing) return;
    const removeTarget = (items) => items.filter((item) => !sameRadarCustomer(item, target));
    next.allRadarCards = removeTarget(next.allRadarCards);
    next.allVisitorCards = removeTarget(next.allVisitorCards);
    next.allFollowingCards = removeTarget(next.allFollowingCards);
    next.allAbandonedCards = removeTarget(next.allAbandonedCards);
    const updated = followupMutationItem(existing, mutation);
    if (mutation.action === "abandon") {
      next.allAbandonedCards.unshift(updated);
    } else if (mutation.action === "restore") {
      next.allRadarCards.unshift(updated);
    } else {
      next.allFollowingCards.unshift(updated);
    }
    changed = true;
  });
  return { collections: next, changed };
}

function applyMetricFilter(items = [], metric = "") {
  if (metric === "highIntent") {
    return items.filter((item) => /高/.test(item.intentLabel || "") || (item.tags || []).includes("高意向") || (item.tags || []).includes("重点客户"));
  }
  if (metric === "interactions") {
    return items.filter((item) => Number(item.actionCount || 0) > 0 || Number(item.consultCount || 0) > 0 || (item.tags || []).includes("有咨询动作"));
  }
  return items;
}

function visibleCollections(metric, radarCards, visitorCards, insights) {
  return {
    radarCards: metric === "highIntent" ? applyMetricFilter(radarCards, metric) : radarCards,
    visitorCards: metric === "interactions" ? applyMetricFilter(visitorCards, metric) : visitorCards,
    insights
  };
}

function radarCollectionsFromDashboard(data = {}, sourceFilter = null) {
  const alerts = (data.opportunityAlerts || []).map(normalizeAlert);
  const profiles = (data.radarProfiles || []).map(normalizeProfile);
  const rawVisitorCards = profiles.filter((item) => !item.leadReminderId).slice(0, 12);
  const radarCards = applySourceFilter(alerts.filter((item) => !item.isPeerLike), sourceFilter);
  const visitorCards = applySourceFilter(rawVisitorCards, sourceFilter);
  const followingCards = applySourceFilter((data.followingProfiles || []).map(normalizeProfile), sourceFilter);
  const abandonedCards = applySourceFilter((data.abandonedProfiles || []).map(normalizeProfile), sourceFilter);
  const insights = applySourceFilter((data.contentInsights || []).map(normalizeInsight), sourceFilter);
  return {
    radarCards,
    visitorCards,
    followingCards,
    abandonedCards,
    insights,
    profiles
  };
}

function summaryFromCollections(collections = {}, fallback = {}) {
  const radarCards = collections.radarCards || [];
  const visitorCards = collections.visitorCards || [];
  const followingCards = collections.followingCards || [];
  const abandonedCards = collections.abandonedCards || [];
  return {
    ...fallback,
    pending: radarCards.length,
    visitors: visitorCards.length,
    following: followingCards.length,
    abandoned: abandonedCards.length,
    highIntent: radarCards.filter((item) => item.isHighIntent).length
  };
}

function summaryDisplayFromSummary(summary = {}) {
  const display = (value) => value === null || value === undefined || value === "" ? "—" : String(Math.max(0, Number(value) || 0));
  return {
    pending: display(summary.pending),
    visitors: display(summary.visitors),
    following: display(summary.following),
    abandoned: display(summary.abandoned)
  };
}

function applySummaryNumbers(summary = {}, fallback = {}) {
  return {
    highIntent: Number.isFinite(Number(summary.highIntent)) ? Number(summary.highIntent) : Number(fallback.highIntent || 0),
    pending: Number.isFinite(Number(summary.pending)) ? Number(summary.pending) : Number(fallback.pending || 0),
    visitors: Number.isFinite(Number(summary.visitors)) ? Number(summary.visitors) : Number(fallback.visitors || 0),
    interactions: Number.isFinite(Number(summary.interactions)) ? Number(summary.interactions) : Number(fallback.interactions || 0),
    revival: Number.isFinite(Number(summary.revival)) ? Number(summary.revival) : Number(fallback.revival || 0),
    filtered: Number.isFinite(Number(summary.filtered)) ? Number(summary.filtered) : Number(fallback.filtered || 0),
    following: Number.isFinite(Number(summary.following)) ? Number(summary.following) : Number(fallback.following || 0),
    abandoned: Number.isFinite(Number(summary.abandoned)) ? Number(summary.abandoned) : Number(fallback.abandoned || 0)
  };
}

Page({
  data: {
    loading: false,
    loadError: "",
    radarLoadedAt: 0,
    radarLoadKey: "",
    activeTab: "followup",
    tabs: [
      { key: "followup", label: "待跟进" },
      { key: "visitors", label: "访客" },
      { key: "following", label: "跟进中" },
      { key: "abandoned", label: "已放弃" }
    ],
    workspaceMode: "property",
    modeConfig: getModeConfig("property"),
    radarCopy: radarCopyForMode("property"),
    summary: {
      highIntent: 0,
      pending: 0,
      visitors: 0,
      interactions: 0,
      revival: 0,
      filtered: 0,
      following: 0,
      abandoned: 0
    },
    summaryDisplay: { pending: "—", visitors: "—", following: "—", abandoned: "—" },
    summaryReady: false,
    radarCards: [],
    visitorCards: [],
    insights: [],
    allRadarCards: [],
    allVisitorCards: [],
    followingCards: [],
    allFollowingCards: [],
    abandonedCards: [],
    allAbandonedCards: [],
    allInsights: [],
    sourceFilter: null,
    intelligenceLocked: false,
    customerInfoChainEnabled: false,
    customerInfoChainPaymentRequired: true,
    customerInfoAccessState: "disabled",
    anonymous: false,
    featureDisabled: false,
    signalPreview: [],
    hasCustomerSignals: false,
  },
  onHide() {
    // A radar read must not be allowed to paint after leaving this page for a
    // customer detail action. The returning onShow will consume the committed
    // mutation projection instead of accepting that stale response.
    this._radarRequestId = (this._radarRequestId || 0) + 1;
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      // Customer radar is an owner workspace.  Anonymous users can keep
      // browsing public pages, but must not be pushed into a login loop just
      // by touching the radar tab.
      this._radarRequestId = (this._radarRequestId || 0) + 1;
      this.setData({
        loading: false,
        loadError: "",
        anonymous: true,
        featureDisabled: true,
        customerInfoChainEnabled: false,
        customerInfoChainPaymentRequired: true,
        customerInfoAccessState: "disabled",
        intelligenceLocked: false,
        workspaceMode: "property",
        modeConfig: getModeConfig("property"),
        radarCopy: radarCopyForMode("property"),
        sourceFilter: null,
        signalPreview: [],
        hasCustomerSignals: false,
        summary: { highIntent: 0, pending: 0, visitors: 0, interactions: 0, revival: 0, filtered: 0, following: 0, abandoned: 0 },
        summaryDisplay: { pending: "0", visitors: "0", following: "0", abandoned: "0" },
        summaryReady: true,
        radarCards: [],
        visitorCards: [],
        followingCards: [],
        abandonedCards: [],
        insights: [],
        allRadarCards: [],
        allVisitorCards: [],
        allFollowingCards: [],
        allAbandonedCards: [],
        allInsights: []
      });
      return;
    }
    const workspaceMode = readWorkspaceMode(currentUser.id) || "property";
    const requestMode = workspaceMode === "property" ? "property" : workspaceMode;
    const cachedIntelligence = customerIntelligenceStore.peek(currentUser.id, requestMode);
    const hasReusableIntelligence = Boolean(cachedIntelligence);
    // A detail-page action has already been committed by the action endpoint.
    // Consume its short-lived in-memory projection and update this tab without
    // waiting for a full radar rebuild. Sensitive customer data is never put in
    // persistent storage; the next normal refresh remains authoritative.
    const pendingMutations = customerIntelligenceStore.drainRadarMutations(currentUser.id, requestMode);
    let pendingCollections = null;
    let pendingMutationApplied = false;
    if (pendingMutations.length) {
      // Invalidate any older background read before painting the committed
      // mutation, otherwise its late response could resurrect the old card.
      this._radarRequestId = (this._radarRequestId || 0) + 1;
      const mutationResult = applyRadarMutations({
        allRadarCards: this.data.allRadarCards || [],
        allVisitorCards: this.data.allVisitorCards || [],
        allFollowingCards: this.data.allFollowingCards || [],
        allAbandonedCards: this.data.allAbandonedCards || []
      }, pendingMutations);
      pendingCollections = mutationResult.collections;
      pendingMutationApplied = mutationResult.changed;
    }
    let activeTab = this.data.activeTab || "followup";
    try {
      const storedTab = wx.getStorageSync(RADAR_ENTRY_TAB_KEY);
      if (["followup", "visitors", "following", "abandoned"].includes(storedTab)) {
        activeTab = storedTab;
        wx.removeStorageSync(RADAR_ENTRY_TAB_KEY);
      }
    } catch (error) {}
    let sourceFilter = null;
    try {
      const storedFilter = wx.getStorageSync(RADAR_SOURCE_FILTER_KEY);
      const storedOwnerUserId = String((storedFilter && storedFilter.ownerUserId) || "");
      const currentUserId = String((currentUser && currentUser.id) || "");
      if (storedFilter && (!storedOwnerUserId || storedOwnerUserId === currentUserId) && Date.now() - Number(storedFilter.ts || 0) < 10 * 60 * 1000) sourceFilter = storedFilter;
      wx.removeStorageSync(RADAR_SOURCE_FILTER_KEY);
    } catch (error) {}
    const filterKey = sourceFilter ? [sourceFilter.noteId, sourceFilter.resourceId, sourceFilter.showcaseId].filter(Boolean).join(",") : "";
    const cachedDashboard = hasReusableIntelligence
      && cachedIntelligence
      && cachedIntelligence.data
      && cachedIntelligence.data.locked === false
      ? cachedIntelligence.data.dashboard || {}
      : null;
    const cachedCollections = cachedDashboard ? radarCollectionsFromDashboard(cachedDashboard, sourceFilter) : null;
    const cachedSummary = cachedCollections ? summaryFromCollections(cachedCollections, this.data.summary || {}) : null;
    const localCollections = pendingMutationApplied
      ? pendingCollections
      : {
        allRadarCards: this.data.allRadarCards || [],
        allVisitorCards: this.data.allVisitorCards || [],
        allFollowingCards: this.data.allFollowingCards || [],
        allAbandonedCards: this.data.allAbandonedCards || []
      };
    const localRadarCards = applySourceFilter(localCollections.allRadarCards, sourceFilter);
    const localVisitorCards = applySourceFilter(localCollections.allVisitorCards, sourceFilter);
    const localFollowingCards = applySourceFilter(localCollections.allFollowingCards, sourceFilter);
    const localAbandonedCards = applySourceFilter(localCollections.allAbandonedCards, sourceFilter);
    this.setData({
      workspaceMode,
      modeConfig: getModeConfig(workspaceMode),
      radarCopy: radarCopyForMode(workspaceMode),
      activeTab,
      sourceFilter,
      radarCards: pendingMutationApplied ? localRadarCards : (cachedCollections ? cachedCollections.radarCards : (hasReusableIntelligence ? (this.data.allRadarCards || this.data.radarCards || []) : [])),
      visitorCards: pendingMutationApplied ? localVisitorCards : (cachedCollections ? cachedCollections.visitorCards : (hasReusableIntelligence ? (this.data.allVisitorCards || this.data.visitorCards || []) : [])),
      followingCards: pendingMutationApplied ? localFollowingCards : (cachedCollections ? cachedCollections.followingCards : (hasReusableIntelligence ? (this.data.allFollowingCards || this.data.followingCards || []) : [])),
      abandonedCards: pendingMutationApplied ? localAbandonedCards : (cachedCollections ? cachedCollections.abandonedCards : (hasReusableIntelligence ? (this.data.allAbandonedCards || this.data.abandonedCards || []) : [])),
      insights: cachedCollections ? cachedCollections.insights : (hasReusableIntelligence ? (this.data.allInsights || this.data.insights || []) : []),
      ...(pendingMutationApplied ? {
        allRadarCards: pendingCollections.allRadarCards,
        allVisitorCards: pendingCollections.allVisitorCards,
        allFollowingCards: pendingCollections.allFollowingCards,
        allAbandonedCards: pendingCollections.allAbandonedCards,
        summary: {
          ...(this.data.summary || {}),
          pending: localRadarCards.length,
          visitors: localVisitorCards.length,
          following: localFollowingCards.length,
          abandoned: localAbandonedCards.length,
          highIntent: localRadarCards.filter((item) => item.isHighIntent).length
        },
        summaryDisplay: summaryDisplayFromSummary({
          pending: localRadarCards.length,
          visitors: localVisitorCards.length,
          following: localFollowingCards.length,
          abandoned: localAbandonedCards.length
        }),
        summaryReady: true
      } : cachedCollections ? {
        allRadarCards: cachedCollections.radarCards,
        allVisitorCards: cachedCollections.visitorCards,
        allFollowingCards: cachedCollections.followingCards,
        allAbandonedCards: cachedCollections.abandonedCards,
        allInsights: cachedCollections.insights,
        summary: cachedSummary,
        summaryDisplay: summaryDisplayFromSummary(cachedSummary),
        summaryReady: true
      } : {})
    });
    // The access check is served from the short membership cache; only cache
    // expiry or an explicit retry reaches the server.
    if (!pendingMutationApplied) this.loadRadar();
  },
  async loadRadar(options = {}) {
    const force = Boolean(options.force);
    const background = Boolean(options.background);
    const requestId = (this._radarRequestId || 0) + 1;
    this._radarRequestId = requestId;
    const currentUser = getCurrentUser();
    if (!currentUser) return;
    const mode = this.data.workspaceMode || "property";
    const sourceFilter = this.data.sourceFilter;
    const filterKey = sourceFilter ? [sourceFilter.noteId, sourceFilter.resourceId, sourceFilter.showcaseId].filter(Boolean).join(",") : "";
    const requestMode = mode === "property" ? "property" : mode;
    const cachedSnapshot = customerIntelligenceStore.peek(currentUser.id, requestMode);
    const hasCachedIntelligence = Boolean(cachedSnapshot);
    const cachedUnlocked = Boolean(cachedSnapshot && cachedSnapshot.data && cachedSnapshot.data.locked === false);
    const hasReusableIntelligence = Boolean(!force && hasCachedIntelligence);
    const cachedDashboard = hasReusableIntelligence && cachedUnlocked
      ? cachedSnapshot.data.dashboard || {}
      : null;
    const cachedCollections = cachedDashboard ? radarCollectionsFromDashboard(cachedDashboard, sourceFilter) : null;
    const cachedSummary = cachedCollections ? summaryFromCollections(cachedCollections, this.data.summary || {}) : null;
    this.setData({
      // A usable in-memory projection is already enough to paint the page.
      // Revalidation runs in the background instead of replacing the screen
      // with a spinner on every return from detail.
      loading: background ? false : !hasReusableIntelligence,
      loadError: background ? this.data.loadError : "",
      anonymous: false,
      featureDisabled: false,
      customerInfoChainEnabled: cachedUnlocked,
      customerInfoChainPaymentRequired: true,
      customerInfoAccessState: cachedUnlocked ? "allowed" : "disabled",
      ...(hasReusableIntelligence ? {} : {
        summaryDisplay: { pending: "—", visitors: "—", following: "—", abandoned: "—" },
        summaryReady: false
      }),
      ...(cachedCollections ? {
        ...visibleCollections("", cachedCollections.radarCards, cachedCollections.visitorCards, cachedCollections.insights),
        followingCards: cachedCollections.followingCards,
        abandonedCards: cachedCollections.abandonedCards,
        allRadarCards: cachedCollections.radarCards,
        allVisitorCards: cachedCollections.visitorCards,
        allFollowingCards: cachedCollections.followingCards,
        allAbandonedCards: cachedCollections.abandonedCards,
        allInsights: cachedCollections.insights,
        summary: cachedSummary,
        summaryDisplay: summaryDisplayFromSummary(cachedSummary),
        summaryReady: true,
        intelligenceLocked: false
      } : {})
    });
    try {
      // Start the small projection beside the membership check. It can paint
      // truthful counts while the full customer dashboard is still loading.
      const applySummaryResponse = (summaryResponse) => {
        if (requestId !== this._radarRequestId || (getCurrentUser() || {}).id !== currentUser.id) return;
        const summaryData = summaryResponse && summaryResponse.data;
        if (summaryData && summaryData.featureEnabled !== false && summaryData.locked === false && summaryData.summary) {
          const partialSummary = applySummaryNumbers(summaryData.summary, this.data.summary);
          this.setData({
            summary: partialSummary,
            summaryDisplay: summaryDisplayFromSummary(summaryData.summary),
            summaryReady: true
          });
        }
      };
      const summaryPromise = (!hasReusableIntelligence || force)
        ? api.fetchCustomerIntelligenceSummary(currentUser.id, currentUser.id, requestMode, { force }).catch((error) => {
          console.error("[radar] summary load failed", error);
          return null;
        })
        : Promise.resolve(null);
      const summaryReadyPromise = summaryPromise.then((summaryResponse) => {
        applySummaryResponse(summaryResponse);
        return summaryResponse;
      });
      // Membership is read through api.js's five-minute in-memory cache. This
      // keeps the access-mode check without sending a membership request on
      // every page return; the server remains authoritative on cache misses.
      const membershipRes = await api.fetchMembership(currentUser.id, { force: force && !background });
      if (requestId !== this._radarRequestId || (getCurrentUser() || {}).id !== currentUser.id) return;
      const membership = (membershipRes && membershipRes.data) || {};
      const paymentRequired = membership.paymentRequired === true;
      const paymentState = getCustomerPaymentState(membership);
      if (paymentState === "unknown") throw new Error("membership response is empty");
      if (membership.featureEnabled === false) {
        this.setData({
          customerInfoChainEnabled: false,
          customerInfoChainPaymentRequired: paymentRequired,
          customerInfoAccessState: "disabled",
          intelligenceLocked: false,
          signalPreview: [],
          hasCustomerSignals: false,
          summary: { highIntent: 0, pending: 0, visitors: 0, interactions: 0, revival: 0, filtered: 0, following: 0, abandoned: 0 },
          summaryDisplay: { pending: "0", visitors: "0", following: "0", abandoned: "0" },
          summaryReady: true,
          radarCards: [],
          visitorCards: [],
          followingCards: [],
          abandonedCards: [],
          insights: [],
          allRadarCards: [],
          allVisitorCards: [],
          allFollowingCards: [],
          allAbandonedCards: [],
          allInsights: []
        });
        return;
      }
      if (requestId !== this._radarRequestId || (getCurrentUser() || {}).id !== currentUser.id) return;
      if (force && !background) customerIntelligenceStore.clear(currentUser.id, requestMode);
      const cachedResponse = force ? null : customerIntelligenceStore.peek(currentUser.id, requestMode);
      const cachedData = cachedResponse && cachedResponse.data;
      const cachedMatchesAccess = cachedData
        && cachedData.paymentRequired === paymentRequired
        && Boolean(cachedData.locked) === (paymentRequired && membership.active !== true);
      const cachedIntelligence = cachedMatchesAccess ? cachedResponse : null;
      const businessPromise = cachedIntelligence
        ? Promise.resolve(cachedIntelligence)
        : customerIntelligenceStore.getOrFetchForAccessMode(
            currentUser.id,
            requestMode,
            paymentRequired,
            () => api.fetchCustomerIntelligence(currentUser.id, currentUser.id, requestMode, { force }),
            { force }
          );
      // The count-only projection and the full card payload are independent
      // after access is known. Do not make the slower projection delay the
      // customer cards when the summary row is dirty or rebuilding.
      const [, businessRes] = await Promise.all([summaryReadyPromise, businessPromise]);
      if (requestId !== this._radarRequestId) return;
      const intelligence = (businessRes && businessRes.data) || {};
      if (!businessRes || !businessRes.data) throw new Error("customer intelligence response is empty");
      const serverPaymentRequired = intelligence.paymentRequired === true;
      const serverPaymentState = getCustomerPaymentState(intelligence.membership || membership);
      if (serverPaymentState === "unknown" || serverPaymentRequired !== paymentRequired) {
        throw new Error("customer intelligence access state is stale");
      }
      const data = intelligence.dashboard || {};
      if (intelligence.locked !== false) {
        const lockedSummary = intelligence.summary || {};
        const radarSummary = {
          highIntent: 0,
          pending: Number(lockedSummary.pendingLeadCount || 0),
          visitors: Number(lockedSummary.visitorCount || 0),
          interactions: Number(lockedSummary.newInteractionCount || 0),
          revival: Number(lockedSummary.repeatVisitorCount || 0),
          filtered: 0,
          following: 0,
          abandoned: 0
        };
        this.setData({
          intelligenceLocked: true,
          customerInfoAccessState: serverPaymentState === "payment_required" ? "payment_required" : "refreshing",
          signalPreview: intelligence.signalPreview || [],
          hasCustomerSignals: Number(lockedSummary.visitorCount || 0) > 0
            || Number(lockedSummary.pendingLeadCount || 0) > 0
            || Number(lockedSummary.newInteractionCount || 0) > 0,
          summary: radarSummary,
          summaryDisplay: summaryDisplayFromSummary(radarSummary),
          summaryReady: true,
          radarCards: [],
          visitorCards: [],
          followingCards: [],
          abandonedCards: [],
          insights: [],
          allRadarCards: [],
          allVisitorCards: [],
          allFollowingCards: [],
          allAbandonedCards: [],
          allInsights: [],
          radarLoadedAt: Date.now(),
          radarLoadKey: `${mode}|${filterKey}`
        });
        return;
      }
      const collections = radarCollectionsFromDashboard(data, sourceFilter);
      const { radarCards, visitorCards, followingCards, abandonedCards, insights, profiles } = collections;
      const sourceSummary = data.opportunitySummary || {};
      const interactionCount = profiles.reduce((total, item) => total + Number(item.actionCount || 0) + Number(item.consultCount || 0), 0);
      const scoped = Boolean(sourceFilter);
      const radarSummary = {
        highIntent: scoped ? radarCards.filter((item) => /高/.test(item.intentLabel)).length : Number(sourceSummary.todayHighIntentCount || sourceSummary.highIntentCount || radarCards.filter((item) => /高/.test(item.intentLabel)).length || 0),
        pending: radarCards.length,
        visitors: visitorCards.length,
        interactions: Number(sourceSummary.interactionCount || interactionCount || 0),
        revival: scoped ? radarCards.filter((item) => item.stateLabel === "沉默复活").length : Number(sourceSummary.revivalCount || (data.revivalAlerts || []).length || radarCards.filter((item) => item.stateLabel === "沉默复活").length || 0),
        filtered: scoped ? rawRadarCards.filter((item) => item.isPeerLike && matchSourceFilter(item, sourceFilter)).length : Number(sourceSummary.filteredPeerCount || 0),
        following: followingCards.length,
        abandoned: abandonedCards.length
      };
      if (requestId !== this._radarRequestId) return;
      this.setData({
        anonymous: false,
        featureDisabled: false,
        customerInfoChainEnabled: true,
        customerInfoChainPaymentRequired: paymentRequired,
        customerInfoAccessState: "allowed",
        summary: radarSummary,
        summaryDisplay: summaryDisplayFromSummary(radarSummary),
        summaryReady: true,
        ...visibleCollections("", radarCards, visitorCards, insights),
        followingCards,
        abandonedCards,
        allRadarCards: radarCards,
        allVisitorCards: visitorCards,
        allFollowingCards: followingCards,
        allAbandonedCards: abandonedCards,
        allInsights: insights,
        intelligenceLocked: false,
        signalPreview: [],
        hasCustomerSignals: false,
        radarLoadedAt: Date.now(),
        radarLoadKey: `${mode}|${filterKey}`
      });
      if (cachedIntelligence && !force && requestId === this._radarRequestId) {
        // Paint the cached dashboard now, then perform a real network
        // revalidation. The forced request bypasses the cached response but
        // keeps the visible cards in place while it runs.
        this.loadRadar({ force: true, background: true });
      }
    } catch (error) {
      if (requestId !== this._radarRequestId) return;
      console.error("[radar] load failed", error);
      if (background && hasCachedIntelligence) {
        // A stale-while-revalidate failure must not blank an already usable
        // dashboard. The next foreground load or explicit retry can try
        // again, while the cached cards remain visible.
        return;
      }
      // A transport/API error is not a membership state. Keep the distinction
      // visible so users can retry instead of being sent to a false paywall.
      this.setData({
        anonymous: false,
        featureDisabled: false,
        customerInfoChainEnabled: false,
        customerInfoChainPaymentRequired: true,
        customerInfoAccessState: "error",
        loadError: "暂时无法读取客户信号，请重试。",
        intelligenceLocked: false,
        signalPreview: [],
        hasCustomerSignals: false,
        summary: this.data.summary || { highIntent: 0, pending: 0, visitors: 0, interactions: 0, revival: 0, filtered: 0, following: 0, abandoned: 0 },
        summaryDisplay: this.data.summaryReady ? this.data.summaryDisplay : { pending: "—", visitors: "—", following: "—", abandoned: "—" },
        radarCards: [],
        visitorCards: [],
        followingCards: [],
        abandonedCards: [],
        insights: [],
        allRadarCards: [],
        allVisitorCards: [],
        allFollowingCards: [],
        allAbandonedCards: [],
        allInsights: []
      });
    } finally {
      if (requestId === this._radarRequestId) this.setData({ loading: false });
    }
  },
  handleTabChange(event) {
    const requestedTab = event.currentTarget.dataset.key || "followup";
    const activeTab = ["followup", "visitors", "following", "abandoned"].includes(requestedTab) ? requestedTab : "followup";
    this.setData({
      activeTab,
      radarCards: this.data.allRadarCards || [],
      visitorCards: this.data.allVisitorCards || [],
      followingCards: this.data.allFollowingCards || [],
      abandonedCards: this.data.allAbandonedCards || [],
      insights: this.data.allInsights || []
    });
  },
  handleMetricTap(event) {
    if (this.data.loading) {
      this.handleOpenCustomerSignals();
      return;
    }
    if (this.data.featureDisabled) {
      wx.showToast({ title: "客户信息链暂未开启", icon: "none" });
      return;
    }
    if (this.data.loadError) {
      this.handleRetry();
      return;
    }
    if (this.data.intelligenceLocked) {
      this.handleOpenCustomerSignals();
      return;
    }
    const key = event.currentTarget.dataset.key || "pending";
    const metricConfig = {
      pending: { tab: "followup", label: "待跟进" },
      visitors: { tab: "visitors", label: "访客" },
      following: { tab: "following", label: "跟进中" },
      abandoned: { tab: "abandoned", label: "已放弃" }
    }[key] || { tab: "followup", label: "待跟进" };
    this.setData({
      activeTab: metricConfig.tab,
      radarCards: this.data.allRadarCards || [],
      visitorCards: this.data.allVisitorCards || [],
      followingCards: this.data.allFollowingCards || [],
      abandonedCards: this.data.allAbandonedCards || [],
      insights: this.data.allInsights || []
    });
  },
  handleRetry() {
    this.loadRadar({ force: true });
  },
  handleClearSourceFilter() {
    this.setData({ sourceFilter: null, radarLoadedAt: 0, radarLoadKey: "" });
    this.loadRadar();
  },
  async resolveCustomerInfoAccess(userId) {
    const membershipRes = await api.fetchMembership(userId, { force: true });
    const membership = (membershipRes && membershipRes.data) || {};
    const paymentState = getCustomerPaymentState(membership);
    if (paymentState === "unknown") throw new Error("membership response is empty");
    return {
      featureEnabled: membership.featureEnabled !== false,
      paymentRequired: membership.paymentRequired === true,
      paymentState,
      membership
    };
  },
  async handleOpenCustomerSignals() {
    if (this._openingCustomerSignals) return;
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this._openingCustomerSignals = true;
    try {
      // The page can stay open while either operations switch changes. The
      // click must use a fresh server decision instead of the page's loading
      // or cached state.
      const access = await this.resolveCustomerInfoAccess(currentUser.id);
      if ((getCurrentUser() || {}).id !== currentUser.id) return;
      if (!access.featureEnabled) {
        this.setData({
          featureDisabled: true,
          customerInfoChainEnabled: false,
          customerInfoChainPaymentRequired: access.paymentRequired,
          customerInfoAccessState: "disabled",
          intelligenceLocked: false
        });
        wx.showToast({ title: "客户信息链暂未开启", icon: "none" });
        return;
      }
      if (access.paymentState === "payment_required") {
        wx.navigateTo({ url: "/pages/membership/index" });
        return;
      }
      this.loadRadar({ force: true });
    } catch (error) {
      console.error("[radar] customer signal access check failed", error);
      wx.showToast({ title: "客户信息链状态暂不可用，请重试", icon: "none" });
    } finally {
      this._openingCustomerSignals = false;
    }
  },
  updateRadarCollections(next = {}) {
    const allRadarCards = next.allRadarCards || this.data.allRadarCards || [];
    const allVisitorCards = next.allVisitorCards || this.data.allVisitorCards || [];
    const allFollowingCards = next.allFollowingCards || this.data.allFollowingCards || [];
    const allAbandonedCards = next.allAbandonedCards || this.data.allAbandonedCards || [];
    const sourceFilter = this.data.sourceFilter;
    const radarCards = applySourceFilter(allRadarCards, sourceFilter);
    const visitorCards = applySourceFilter(allVisitorCards, sourceFilter);
    const followingCards = applySourceFilter(allFollowingCards, sourceFilter);
    const abandonedCards = applySourceFilter(allAbandonedCards, sourceFilter);
    const currentSummary = this.data.summary || {};
    this.setData({
      allRadarCards,
      allVisitorCards,
      allFollowingCards,
      allAbandonedCards,
      radarCards,
      visitorCards,
      followingCards,
      abandonedCards,
      summary: {
        ...currentSummary,
        pending: radarCards.length,
        visitors: visitorCards.length,
        following: followingCards.length,
        abandoned: abandonedCards.length,
        highIntent: radarCards.filter((item) => item.isHighIntent).length
      },
      summaryDisplay: summaryDisplayFromSummary({
        pending: radarCards.length,
        visitors: visitorCards.length,
        following: followingCards.length,
        abandoned: abandonedCards.length
      }),
      summaryReady: true
    });
  },
  invalidateRadarReads() {
    // A dashboard request that started before a follow-up action is no longer
    // authoritative. Advance the request epoch before the optimistic paint
    // so a late response cannot resurrect the old card.
    this._radarRequestId = (this._radarRequestId || 0) + 1;
    const currentUser = getCurrentUser();
    if (currentUser) {
      const mode = this.data.workspaceMode || "";
      customerIntelligenceStore.clear(currentUser.id, mode);
      customerDetailStore.clear(currentUser.id, mode);
    }
    return this._radarRequestId;
  },
  async reconcileFollowupAction(item, expectedStatus) {
    const currentUser = getCurrentUser();
    const leadId = String((item && item.leadReminderId) || "").trim();
    const customerId = String((item && item.customerId) || "").trim();
    if (!currentUser || (!customerId && !leadId)) return null;
    try {
      const response = await api.fetchCustomerDetail(
        currentUser.id,
        currentUser.id,
        leadId ? "" : customerId,
        this.data.workspaceMode || "",
        leadId
      );
      const lead = response && response.data && response.data.lead;
      return Boolean(lead && lead.status === expectedStatus);
    } catch (error) {
      return null;
    }
  },
  async handleFollowupActionFailure(error, item, expectedStatus, snapshot, mutationEpoch) {
    const uncertain = !error || error.errorType === "network" || error.errorType === "server" || error.statusCode === 409 || !error.statusCode;
    if (uncertain) {
      const confirmed = await this.reconcileFollowupAction(item, expectedStatus);
      if (confirmed === true) {
        const currentUser = getCurrentUser();
        if (currentUser) {
          customerIntelligenceStore.clear(currentUser.id, this.data.workspaceMode || "");
          customerDetailStore.clear(currentUser.id, this.data.workspaceMode || "");
        }
        wx.showToast({ title: "状态已保存", icon: "success" });
        return;
      }
      if (confirmed === null) {
        // Do not resurrect stale cards after an unknown outcome. The next
        // explicit refresh will reconcile with the server projection.
        const currentUser = getCurrentUser();
        if (currentUser) {
          customerIntelligenceStore.clear(currentUser.id, this.data.workspaceMode || "");
          customerDetailStore.clear(currentUser.id, this.data.workspaceMode || "");
        }
        wx.showToast({ title: "状态正在同步，请稍后刷新雷达", icon: "none" });
        return;
      }
    }
    // Do not restore a whole old snapshot if another card was acted on while
    // this request was pending. The authoritative refresh will reconcile all
    // cards without erasing the later optimistic action.
    if (mutationEpoch === this._radarMutationEpoch) this.updateRadarCollections(snapshot);
    wx.showToast({ title: error && error.detail ? error.detail : "操作失败，已恢复", icon: "none" });
  },
  async handleAbandonCustomer(event) {
    const list = event.currentTarget.dataset.list || "followup";
    const index = Number(event.currentTarget.dataset.index);
    const source = list === "visitors"
      ? (this.data.visitorCards || [])
      : list === "following"
        ? (this.data.followingCards || [])
        : (this.data.radarCards || []);
    const item = source[index];
    if (!item) return;
    const actionKey = `abandon:${item.leadReminderId || item.customerId || item.id}`;
    if (this._radarActionKeys && this._radarActionKeys[actionKey]) return;
    this._radarActionKeys = this._radarActionKeys || {};
    this._radarActionKeys[actionKey] = true;
    const mutationEpoch = (this._radarMutationEpoch || 0) + 1;
    this._radarMutationEpoch = mutationEpoch;
    this.invalidateRadarReads();
    const currentUser = getCurrentUser();
    if (!currentUser || (!item.customerId && !item.leadReminderId)) {
      delete this._radarActionKeys[actionKey];
      wx.showToast({ title: "该访客暂时无法处理", icon: "none" });
      return;
    }
    const snapshot = {
      allRadarCards: this.data.allRadarCards || [],
      allVisitorCards: this.data.allVisitorCards || [],
      allFollowingCards: this.data.allFollowingCards || [],
      allAbandonedCards: this.data.allAbandonedCards || []
    };
    const archivedItem = {
      ...item,
      leadStatus: "paused",
      leadStatusText: "已放弃跟进",
      stateLabel: "已放弃跟进",
      abandonedAt: new Date().toISOString()
    };
    const nextRadarCards = snapshot.allRadarCards.filter((candidate) => !sameRadarCustomer(candidate, item));
    const nextVisitorCards = snapshot.allVisitorCards.filter((candidate) => !sameRadarCustomer(candidate, item));
    const nextFollowingCards = snapshot.allFollowingCards.filter((candidate) => !sameRadarCustomer(candidate, item));
    const nextAbandonedCards = [
      archivedItem,
      ...snapshot.allAbandonedCards.filter((candidate) => !sameRadarCustomer(candidate, item))
    ];
    this.updateRadarCollections({
      allRadarCards: nextRadarCards,
      allVisitorCards: nextVisitorCards,
      allFollowingCards: nextFollowingCards,
      allAbandonedCards: nextAbandonedCards
    });
    try {
      const response = await api.actOnCustomerFollowup({
        ownerUserId: currentUser.id,
        requesterUserId: currentUser.id,
        ...followupActionHint(item),
        customerId: item.leadReminderId ? "" : item.customerId,
        mode: this.data.workspaceMode || "",
        leadId: item.leadReminderId || "",
        action: "abandon",
        operationId: createOperationId("abandon", item.leadReminderId || item.customerId),
        expectedVersion: item.leadVersion !== null && item.leadVersion !== undefined
          ? Number(item.leadVersion)
          : undefined
      });
      const lead = response && response.data && response.data.lead;
      if (lead && lead.id) {
        const updatedArchived = nextAbandonedCards.map((candidate) => candidate.id === archivedItem.id
          ? { ...candidate, leadReminderId: lead.id, leadStatus: lead.status || "paused" }
          : candidate);
        this.updateRadarCollections({ allAbandonedCards: updatedArchived });
      }
      customerIntelligenceStore.clear(currentUser.id, this.data.workspaceMode || "");
      customerDetailStore.clear(currentUser.id, this.data.workspaceMode || "");
      // The committed response has already updated the visible local
      // projection. A full dashboard rebuild is deferred until the next
      // normal page refresh instead of blocking this operation.
      wx.showToast({ title: "已放弃跟进", icon: "success" });
    } catch (error) {
      await this.handleFollowupActionFailure(error, item, "paused", snapshot, mutationEpoch);
    } finally {
      delete this._radarActionKeys[actionKey];
    }
  },
  async handleRestoreAbandoned(event) {
    const index = Number(event.currentTarget.dataset.index);
    const item = (this.data.abandonedCards || [])[index];
    if (!item) return;
    const leadId = item.leadReminderId || "";
    if (!leadId) {
      wx.showToast({ title: "缺少跟进档案，无法恢复", icon: "none" });
      return;
    }
    const actionKey = `restore:${leadId}`;
    if (this._radarActionKeys && this._radarActionKeys[actionKey]) return;
    this._radarActionKeys = this._radarActionKeys || {};
    this._radarActionKeys[actionKey] = true;
    const mutationEpoch = (this._radarMutationEpoch || 0) + 1;
    this._radarMutationEpoch = mutationEpoch;
    this.invalidateRadarReads();
    const currentUser = getCurrentUser();
    const snapshot = {
      allRadarCards: this.data.allRadarCards || [],
      allVisitorCards: this.data.allVisitorCards || [],
      allFollowingCards: this.data.allFollowingCards || [],
      allAbandonedCards: this.data.allAbandonedCards || []
    };
    const restored = { ...item, leadStatus: "pending", leadStatusText: "待跟进", stateLabel: "持续关注" };
    this.updateRadarCollections({
      allRadarCards: [restored, ...snapshot.allRadarCards.filter((candidate) => !sameRadarCustomer(candidate, item))],
      allAbandonedCards: snapshot.allAbandonedCards.filter((candidate) => !sameRadarCustomer(candidate, item))
    });
    try {
      await api.actOnCustomerFollowup({
        ownerUserId: currentUser.id,
        requesterUserId: currentUser.id,
        ...followupActionHint(item),
        customerId: leadId ? "" : item.customerId,
        mode: this.data.workspaceMode || "",
        leadId,
        action: "restore",
        operationId: createOperationId("restore", leadId),
        expectedVersion: item.leadVersion !== null && item.leadVersion !== undefined
          ? Number(item.leadVersion)
          : undefined
      });
      customerIntelligenceStore.clear(currentUser.id, this.data.workspaceMode || "");
      customerDetailStore.clear(currentUser.id, this.data.workspaceMode || "");
      wx.showToast({ title: "已恢复跟进", icon: "success" });
    } catch (error) {
      await this.handleFollowupActionFailure(error, item, "pending", snapshot, mutationEpoch);
    } finally {
      delete this._radarActionKeys[actionKey];
    }
  },
  async handleDeleteAbandoned(event) {
    const index = Number(event.currentTarget.dataset.index);
    const item = (this.data.abandonedCards || [])[index];
    const leadId = item && item.leadReminderId;
    if (!item || !leadId) {
      wx.showToast({ title: "缺少跟进档案，无法清空", icon: "none" });
      return;
    }
    const actionKey = `delete:${leadId}`;
    if (this._radarActionKeys && this._radarActionKeys[actionKey]) return;
    this._radarActionKeys = this._radarActionKeys || {};
    this._radarActionKeys[actionKey] = true;
    this.invalidateRadarReads();
    const currentUser = getCurrentUser();
    const snapshot = { allAbandonedCards: this.data.allAbandonedCards || [] };
    this.updateRadarCollections({
      allAbandonedCards: snapshot.allAbandonedCards.filter((candidate) => !sameRadarCustomer(candidate, item))
    });
    try {
      await api.deleteLeadReminder(leadId, currentUser.id);
      customerIntelligenceStore.clear(currentUser.id, this.data.workspaceMode || "");
      customerDetailStore.clear(currentUser.id, this.data.workspaceMode || "");
      wx.showToast({ title: "已清空", icon: "success" });
    } catch (error) {
      this.updateRadarCollections(snapshot);
      wx.showToast({ title: error.detail || "清空失败，已还原", icon: "none" });
    } finally {
      delete this._radarActionKeys[actionKey];
    }
  },
  handleOpenResource(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    navigateToNoteView(id);
  },
  async handleOpenCustomerDetail(event) {
    if (this._openingCustomerDetail) return;
    const customerId = event.currentTarget.dataset.customerId;
    const leadId = event.currentTarget.dataset.leadId || "";
    if (!customerId && !leadId) {
      wx.showToast({ title: "该访客暂时没有可查看的身份", icon: "none" });
      return;
    }
    const radarTab = event.currentTarget.dataset.radarTab;
    const sourceTab = ["followup", "visitors", "following", "abandoned"].includes(radarTab)
      ? radarTab
      : "followup";
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this._openingCustomerDetail = true;
    try {
      // A page that has already loaded the owner-scoped intelligence has an
      // allowed access decision. Avoid a second forced membership request on
      // the hot path; the detail endpoint remains the final authority.
      const access = this.data.customerInfoAccessState === "allowed"
        ? { featureEnabled: true, paymentState: "allowed" }
        : await this.resolveCustomerInfoAccess(currentUser.id);
      if ((getCurrentUser() || {}).id !== currentUser.id) return;
      if (!access.featureEnabled) {
        wx.showToast({ title: "客户信息链暂未开启", icon: "none" });
        return;
      }
      if (access.paymentState === "payment_required") {
        wx.navigateTo({ url: "/pages/membership/index" });
        return;
      }
      const params = [
        `mode=${encodeURIComponent(this.data.workspaceMode || "")}`,
        leadId ? "" : `customerId=${encodeURIComponent(customerId)}`,
        leadId ? `leadId=${encodeURIComponent(leadId)}` : "",
        `sourceTab=${encodeURIComponent(sourceTab)}`
      ]
        .filter(Boolean)
        .join("&");
      wx.navigateTo({ url: `/pages/customer-detail/index?${params}` });
    } catch (error) {
      console.error("[radar] customer detail access check failed", error);
      wx.showToast({ title: "客户信息链状态暂不可用，请重试", icon: "none" });
    } finally {
      this._openingCustomerDetail = false;
    }
  },
});
