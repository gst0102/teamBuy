const api = require("../../services/api");
const customerIntelligenceStore = require("../../stores/customer-intelligence-store");
const customerDetailStore = require("../../stores/customer-detail-store");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");
const { navigateToNoteView } = require("../../utils/resource-navigation");

const RADAR_ENTRY_TAB_KEY = "teambuy:radarEntryTab";
const RADAR_TABS = ["followup", "visitors", "following", "abandoned"];
const QUICK_FOLLOW_UP_TAGS = ["已电话沟通", "已微信联系", "需求已确认", "待报价", "待回访"];

function createOperationId(action, target) {
  return `${action}:${target || "customer"}:${Date.now()}:${Math.random().toString(36).slice(2, 10)}`;
}

function normalizeRadarTab(value) {
  return RADAR_TABS.includes(value) ? value : "followup";
}

function buildFollowUpTagOptions(tags = []) {
  const selectedTags = new Set(uniqueTexts(tags));
  return QUICK_FOLLOW_UP_TAGS.map((label) => ({
    label,
    selected: selectedTags.has(label)
  }));
}

function uniqueTexts(values = []) {
  return values
    .map((item) => String(item || "").trim())
    .filter((item, index, list) => item && list.indexOf(item) === index);
}

function identityLabel(profile = {}) {
  const map = {
    customer: "微信客户",
    anonymous: "匿名访客",
    peer_agent: "疑似同行",
    upstream: "疑似上游"
  };
  return profile.visitorIdentityLabel || map[profile.visitorIdentityType] || "访客";
}

function identityAliases(value) {
  const text = String(value || "").trim();
  if (!text) return [];
  const separator = text.indexOf(":");
  if (separator > 0 && text.slice(separator + 1)) {
    return [text, text.slice(separator + 1)];
  }
  return [text, `user:${text}`, `anon:${text}`];
}

function matchesCustomer(item = {}, targetValues = []) {
  const itemValues = [
    item.id,
    item.customerId,
    item.visitorIdentityId,
    item.viewerUserId,
    item.anonymousId,
    item.leadReminderId
  ].filter(Boolean);
  const itemAliases = new Set(itemValues.flatMap(identityAliases));
  return targetValues.some((target) => identityAliases(target).some((alias) => itemAliases.has(alias)));
}

function cachedProfileForTargets(dashboard = {}, targetValues = []) {
  for (const source of ["radarProfiles", "visitorProfiles", "followingProfiles", "abandonedProfiles", "opportunityAlerts"]) {
    const profile = (dashboard[source] || []).find((item) => matchesCustomer(item, targetValues));
    if (profile) return profile;
  }
  return null;
}

function buildCachedDetailFromIntelligence(response, targetValues = []) {
  const data = response && response.data;
  if (!data || data.locked !== false || !targetValues.length) return null;
  const dashboard = data.dashboard || {};
  const profile = cachedProfileForTargets(dashboard, targetValues);
  if (!profile) return null;
  const profileTargets = [
    profile.id,
    profile.customerId,
    profile.visitorIdentityId,
    profile.viewerUserId,
    profile.anonymousId,
    profile.leadReminderId
  ].filter(Boolean);
  const timeline = (data.customerTimelines || []).find((item) => matchesCustomer(item, targetValues))
    || (data.customerTimelines || []).find((item) => matchesCustomer(item, profileTargets))
    || {};
  const leadId = String(profile.leadReminderId || "").trim();
  const lead = leadId
    ? {
      id: leadId,
      status: profile.leadStatus || "pending",
      customerPhone: profile.phone || "",
      customerWechat: profile.wechat || "",
      customerEmail: profile.email || "",
      customerTags: profile.customerTags || [],
      version: profile.leadVersion !== undefined && profile.leadVersion !== null
        ? Number(profile.leadVersion)
        : Number(profile.version || 0),
      budgetText: profile.budgetText || "",
      nextFollowUpAt: profile.nextFollowUpAt || "",
      // Radar snapshots intentionally do not contain history. The detail
      // request below is authoritative for followUpLogs.
      followUpLogs: []
    }
    : null;
  return {
    featureEnabled: data.featureEnabled !== false,
    paymentRequired: data.paymentRequired === true,
    locked: false,
    membership: data.membership || {},
    customer: profile,
    timeline,
    lead
  };
}

function buildTags(profile = {}, lead = {}) {
  const tags = [...(profile.customerTags || []), ...(lead.customerTags || [])];
  (profile.focusSections || []).forEach((section) => {
    if (/价格|优惠/.test(section)) tags.push("预算敏感");
    if (/地址|位置|地铁/.test(section)) tags.push("关注地铁");
    if (/联系方式/.test(section)) tags.push("联系意向");
    if (/案例|成果|保障|FAQ/.test(section)) tags.push("需要信任");
  });
  if (Number(profile.noteIds && profile.noteIds.length) > 1) tags.push("正在对比");
  if (Number(profile.viewCount || 0) >= 2) tags.push("反复查看");
  if (Number(profile.noteClickCount || 0) > 0) tags.push("已看资料");
  return uniqueTexts(tags).slice(0, 6);
}

function buildMaterials(profile = {}) {
  const ids = Array.isArray(profile.noteIds) ? profile.noteIds : [];
  const titles = Array.isArray(profile.noteTitles) ? profile.noteTitles : [];
  const covers = Array.isArray(profile.noteCoverUrls) ? profile.noteCoverUrls : [];
  const rows = [];
  const length = Math.max(ids.length, titles.length);
  for (let index = 0; index < length; index += 1) {
    const id = ids[index] || ids[0] || "";
    const title = titles[index] || titles[0] || "相关资料";
    if (!id && !title) continue;
    if (rows.some((item) => item.id === id && item.title === title)) continue;
    rows.push({
      key: `${id || "material"}-${index}`,
      id,
      title,
      type: "资料",
      coverUrl: covers[index] || covers[0] || profile.noteCoverUrl || "",
      meta: index === 0 ? `最近查看 ${Number(profile.viewCount || 0)} 次` : "最近查看"
    });
  }
  return rows.slice(0, 6);
}

function buildTimeline(profile = {}, timelineRow = {}, lead = {}) {
  const rows = [];
  (lead.followUpLogs || []).forEach((log, index) => {
    rows.push({
      id: `followup-${log.id || index}`,
      title: log.content || "已记录跟进",
      desc: "已记录在客户跟进档案",
      timeText: formatTime(log.createdAt)
    });
  });
  (timelineRow.events || []).forEach((event) => {
    rows.push({
      id: `event-${rows.length}`,
      title: event.title || "发生资料动作",
      desc: "基于真实浏览或跟进记录",
      timeText: formatTime(event.createdAt)
    });
  });
  if (profile.lastActivityAt && !rows.some((item) => item.timeText === formatTime(profile.lastActivityAt))) {
    rows.unshift({
      id: "latest-activity",
      title: profile.lastActionLabel || "查看资料",
      desc: profile.intentExplanation || "有新的资料行为",
      timeText: formatTime(profile.lastActivityAt)
    });
  }
  if (Number(profile.noteClickCount || 0) > 0) {
    rows.push({
      id: "note-clicks",
      title: "打开资料详情",
      desc: `累计打开 ${profile.noteClickCount} 次`,
      timeText: "累计"
    });
  }
  if (Number(profile.viewCount || 0) > 0) {
    rows.push({
      id: "views",
      title: "查看资料",
      desc: `累计查看 ${profile.viewCount} 次`,
      timeText: "累计"
    });
  }
  return rows.slice(0, 4);
}

function buildScript(profile = {}, materials = []) {
  if (profile.followupScript) return profile.followupScript;
  const title = materials[0] ? materials[0].title : "这份资料";
  return `您好，刚看到你打开了《${title}》，我可以把重点和下一步安排发你。`;
}

function leadStatusText(status) {
  const map = {
    pending: "待联系",
    contacted: "已联系",
    invalid: "无效",
    paused: "已放弃跟进",
    completed: "已完成",
    following: "跟进中"
  };
  return map[status] || "";
}

function formatFollowUpCreatedAt(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return formatTime(value);
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatFollowUpDate(value) {
  const text = String(value || "").trim();
  const dateOnly = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (dateOnly) return `${dateOnly[1]}-${dateOnly[2]}-${dateOnly[3]}`;
  if (!text) return "";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function followUpActionLabel(log = {}) {
  if (log.actionLabel) return String(log.actionLabel);
  return {
    start: "开始跟进",
    continue: "继续跟进",
    abandon: "放弃跟进",
    restore: "恢复跟进",
    record: "跟进记录"
  }[log.action] || "跟进记录";
}

function normalizeFollowUpLead(lead = {}) {
  return {
    id: lead.id || "",
    status: lead.status || "pending",
    version: Number.isFinite(Number(lead.version)) ? Number(lead.version) : 0,
    statusText: leadStatusText(lead.status) || "待联系",
    note: lead.note || "",
    customerTags: uniqueTexts(lead.customerTags || []),
    // The date picker accepts YYYY-MM-DD. Keep the full timestamp on each
    // history row, but expose only the calendar date for the current reminder.
    nextFollowUpAt: formatFollowUpDate(lead.nextFollowUpAt),
    logs: (lead.followUpLogs || []).slice(0, 10).map((log) => {
      const tags = uniqueTexts(Array.isArray(log.tags) ? log.tags : []);
      const note = String(log.note || (!log.action ? log.content : "") || "").trim();
      const nextFollowUpAt = log.nextFollowUpAt ? String(log.nextFollowUpAt).trim() : "";
      return {
        ...log,
        actionLabel: followUpActionLabel(log),
        tags,
        note,
        nextFollowUpAt,
        nextFollowUpText: formatFollowUpDate(nextFollowUpAt),
        createdText: formatFollowUpCreatedAt(log.createdAt)
      };
    })
  };
}

function normalizeMessageSummary(summary = {}) {
  const messages = Array.isArray(summary.messages) ? summary.messages : [];
  return {
    hasMessages: Boolean(summary.hasMessages || messages.length),
    unreadCount: Number(summary.unreadCount || 0),
    threadCount: Number(summary.threadCount || 0),
    latestThreadId: summary.latestThreadId || (messages[0] && messages[0].threadId) || "",
    latestMessage: summary.latestMessage || messages[0] || null,
    messages: messages.slice(0, 3).map((item) => ({
      ...item,
      createdText: formatTime(item.createdAt)
    }))
  };
}

function profileLeadVersion(profile = {}) {
  return profile.leadVersion === null || profile.leadVersion === undefined
    ? undefined
    : Number(profile.leadVersion);
}

function followupActionHint(profile = {}) {
  const firstMaterial = profile.primaryMaterial || (profile.materials && profile.materials[0]) || {};
  return {
    visitorIdentityId: profile.visitorIdentityId || profile.customerId || "",
    viewerUserId: profile.viewerUserId || "",
    anonymousId: profile.anonymousId || "",
    sourceNoteId: profile.sourceNoteId || firstMaterial.id || (profile.noteIds && profile.noteIds[0]) || "",
    nickname: profile.nickname || profile.name || "",
    avatarUrl: profile.avatarUrl || "",
    viewCount: Number(profile.viewCount || 0),
    lastActivityAt: profile.lastActivityAt || ""
  };
}

function radarMutationIdentity(profile = {}, lead = {}, customerId = "") {
  // A detail route with leadId intentionally does not send the legacy
  // customerId to the API. For the in-memory radar projection we still need
  // one stable owner-scoped identity so a first-time visitor card and its new
  // lead row can be reconciled immediately after the action succeeds.
  const visitorIdentityId = String(
    lead.visitorIdentityId
      || profile.visitorIdentityId
      || profile.customerId
      || customerId
      || ""
  ).trim();
  const viewerUserId = String(lead.viewerUserId || profile.viewerUserId || "").trim();
  const anonymousId = String(lead.anonymousId || profile.anonymousId || "").trim();
  return {
    customerId: visitorIdentityId,
    visitorIdentityId,
    viewerUserId,
    anonymousId
  };
}

function normalizeProfile(profile = {}, timelineRow = {}, lead = {}, messageSummary = {}) {
  const identityType = profile.visitorIdentityType || timelineRow.identityType || "customer";
  const name = profile.nickname || timelineRow.displayName || (identityType === "anonymous" ? "匿名访客" : "微信客户");
  const materials = buildMaterials(profile);
  const phone = lead.customerPhone || profile.phone || timelineRow.phone || "";
  const wechat = lead.customerWechat || profile.wechat || timelineRow.wechat || "";
  const email = lead.customerEmail || profile.email || timelineRow.email || "";
  const intentLabel = profile.intentLabel || (profile.intentLevel ? `${profile.intentLevel}意向` : "待判断");
  const customerTags = uniqueTexts([...(profile.customerTags || []), ...(lead.customerTags || [])]).slice(0, 8);
  const tags = buildTags(profile, lead);
  return {
    ...profile,
    name,
    avatarText: name.slice(0, 1),
    identityLabel: identityLabel({ ...profile, visitorIdentityType: identityType }),
    identityType,
    intentLabel,
    stateLabel: profile.isRevival ? "沉默复活" : (profile.intentLevel === "高" ? "高意向" : "持续关注"),
    sourceTitle: materials[0] ? materials[0].title : "资料",
    lastActiveText: formatTime(profile.lastActivityAt || lead.lastViewedAt),
    sourceLine: `来自：${materials[0] ? materials[0].title : "资料"}`,
    primaryMaterial: materials[0] || null,
    reason: profile.intentExplanation || profile.reasonText || timelineRow.reason || "有新的资料行为",
    nextAction: profile.suggestedAction || timelineRow.nextAction || "继续观察或轻触达",
    nextActionHint: profile.followupWindow || "可稍后跟进",
    script: buildScript(profile, materials),
    avatarUrl: profile.avatarUrl || "",
    phone,
    wechat,
    email,
    budgetText: lead.budgetText || profile.budgetText || "",
    customerTags,
    tags,
    materials,
    timeline: buildTimeline(profile, timelineRow, lead),
    hasContact: Boolean(phone || wechat || email),
    contactSourceNote: "客户主动提交或个人资料授权后显示",
    hasLeadRecord: Boolean(lead.id || profile.leadReminderId),
    leadStatus: lead.status || "",
    leadStatusText: leadStatusText(lead.status),
    isRestrictedIdentity: ["anonymous", "peer_agent", "upstream"].includes(identityType),
    canCompare: materials.length > 1,
    leadVersion: lead.version !== undefined ? Number(lead.version) : null,
    messageSummary: normalizeMessageSummary(messageSummary)
  };
}

Page({
  data: {
    loading: true,
    error: "",
    errorKind: "retryable",
    errorTitle: "暂时无法读取客户详情",
    errorActionText: "重新读取",
    customerId: "",
    threadId: "",
    leadId: "",
    sourceTab: "followup",
    creatingFollowUp: false,
    updatingFollowUpStatus: false,
    mode: "",
    profile: null,
    followUpVisible: false,
    activityExpanded: false,
    materialsExpanded: false,
    followUpText: "",
    nextFollowUpAt: "",
    followUpStatusText: "",
    followUpLogs: [],
    followUpTags: [],
    followUpTagOptions: buildFollowUpTagOptions()
  },

  onLoad(query = {}) {
    const routeParams = {
      customerId: query.customerId || "",
      threadId: query.threadId || "",
      leadId: query.leadId || "",
      mode: query.mode || "",
      sourceTab: normalizeRadarTab(query.sourceTab || "followup")
    };
    this.setData(routeParams);
    // setData is asynchronous in the mini-program runtime. Pass the route
    // snapshot directly on first load so the detail request cannot fall back
    // to an older customerId/mode from the page instance or cache.
    this.loadDetail(routeParams);
  },

  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) return;
    if (this._refreshOnShow) {
      this._refreshOnShow = false;
      this.loadDetail({
        customerId: this.data.customerId,
        threadId: this.data.threadId,
        leadId: this.data.leadId,
        mode: this.data.mode,
        force: true
      });
    }
    if (this._loadedOwnerUserId && this._loadedOwnerUserId !== currentUser.id) {
      this.setData({
        loading: true,
        error: "",
        profile: null,
        followUpVisible: false,
        activityExpanded: false,
        materialsExpanded: false,
        followUpText: "",
        followUpLogs: [],
        followUpTags: [],
        followUpTagOptions: buildFollowUpTagOptions()
      });
      this.loadDetail();
    }
  },

  onUnload() {
    // Ignore a late background refresh after the page has been removed.
    this._detailRequestSeq = (this._detailRequestSeq || 0) + 1;
  },

  async loadDetail(routeParams = {}) {
    const requestId = (this._detailRequestSeq || 0) + 1;
    this._detailRequestSeq = requestId;
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this._loadedOwnerUserId = currentUser.id;
    const routeCustomerId = routeParams.customerId !== undefined ? routeParams.customerId : this.data.customerId;
    const routeThreadId = routeParams.threadId !== undefined ? routeParams.threadId : this.data.threadId;
    const routeLeadId = routeParams.leadId !== undefined ? routeParams.leadId : this.data.leadId;
    const routeMode = routeParams.mode !== undefined ? routeParams.mode : this.data.mode;
    let customerId = String(routeCustomerId || "").trim();
    if (!customerId && routeThreadId) {
      try {
        const threadRes = await api.fetchThreadMessages(routeThreadId, currentUser.id);
        const thread = (threadRes && threadRes.data && threadRes.data.thread) || null;
        if (!thread || thread.ownerUserId !== currentUser.id || !thread.peerUserId) {
          this.setData({
            loading: false,
            errorKind: "navigation",
            errorTitle: "无法打开这条客户信号",
            errorActionText: "返回客户雷达",
            error: "当前账号不能查看该客户雷达。"
          });
          return;
        }
        customerId = String(thread.peerUserId);
        this.setData({ customerId });
      } catch (error) {
        if (requestId !== this._detailRequestSeq || (getCurrentUser() || {}).id !== currentUser.id) return;
        this.setData({
          loading: false,
          errorKind: "retryable",
          errorTitle: "暂时无法读取客户会话",
          errorActionText: "重新读取",
          error: error.detail || "暂时无法读取客户会话，请稍后重试。"
        });
        return;
      }
    }
    if (requestId !== this._detailRequestSeq || (getCurrentUser() || {}).id !== currentUser.id) return;
    if (!customerId && !routeLeadId) {
      this.setData({
        loading: false,
        errorKind: "navigation",
        errorTitle: "无法打开这条客户信号",
        errorActionText: "返回客户雷达",
        error: "缺少客户身份，请返回客户雷达重新选择。"
      });
      return;
    }
    const requestMode = String(routeMode || "");
    const cacheCustomerId = customerId;
    const cacheLeadId = String(routeLeadId || "").trim();
    const cachedDetail = routeParams.force ? null : customerDetailStore.peek(
      currentUser.id,
      requestMode,
      cacheCustomerId,
      cacheLeadId
    ) || buildCachedDetailFromIntelligence(
      customerIntelligenceStore.peek(currentUser.id, requestMode),
      [customerId, cacheLeadId].filter(Boolean)
    );
    if (cachedDetail && this.applyDetailResponse(cachedDetail, requestId)) {
      // Paint the in-memory projection immediately. Revalidation never blanks
      // the page or replaces the visible skeleton on this hot path.
      this.refreshDetailInBackground({
        requestId,
        ownerUserId: currentUser.id,
        customerId,
        mode: requestMode,
        leadId: cacheLeadId
      });
      customerDetailStore.remember(
        currentUser.id,
        requestMode,
        cacheCustomerId,
        cacheLeadId,
        cachedDetail
      );
      return;
    }
    this.setData({
      loading: true,
      error: "",
      errorKind: "retryable",
      errorTitle: "暂时无法读取客户详情",
      errorActionText: "重新读取",
      activityExpanded: false,
      materialsExpanded: false
    });
    try {
      // Resolve the tapped customer on the server. The detail endpoint owns
      // identity matching and returns only this customer projection.
      const detailRes = await api.fetchCustomerDetail(
        currentUser.id,
        currentUser.id,
        routeLeadId ? "" : customerId,
        requestMode,
        routeLeadId
      );
      const detail = detailRes && detailRes.data;
      if (!detail) throw new Error("customer detail response is empty");
      if (requestId !== this._detailRequestSeq || (getCurrentUser() || {}).id !== currentUser.id) return;
      if (detail.locked !== false) {
        if (detail.paymentRequired === true) {
          wx.redirectTo({ url: "/pages/membership/index" });
          return;
        }
        this.setData({
          loading: false,
          errorKind: "retryable",
          errorTitle: "暂时无法读取客户详情",
          errorActionText: "重新读取",
          error: "暂时无法读取客户详情，请重试。"
        });
        return;
      }
      customerDetailStore.remember(currentUser.id, requestMode, cacheCustomerId, cacheLeadId, detailRes);
      this.applyDetailResponse(detailRes, requestId);
    } catch (error) {
      if (requestId !== this._detailRequestSeq || (getCurrentUser() || {}).id !== currentUser.id) return;
      console.error("[customer-detail] load failed", error);
      this.setData({
        loading: false,
        errorKind: "retryable",
        errorTitle: "暂时无法读取客户详情",
        errorActionText: "重新读取",
        error: error.detail || "暂时无法读取客户详情，请稍后重试。"
      });
    }
  },

  applyDetailResponse(response, requestId = this._detailRequestSeq, options = {}) {
    const detail = response && response.data ? response.data : response;
    if (requestId !== this._detailRequestSeq || !detail || detail.locked !== false) return false;
    const preserveUi = Boolean(options.preserveUi);
    const rawProfile = detail.customer || {};
    const timelineRow = detail.timeline || {};
    const lead = detail.lead || null;
    const resolvedLeadId = (lead && lead.id) || rawProfile.leadReminderId || this.data.leadId || "";
    const profile = normalizeProfile(rawProfile, timelineRow, lead || {}, detail.messageSummary || {});
    const followUp = normalizeFollowUpLead({
      ...(lead || {}),
      customerTags: lead && lead.customerTags !== undefined ? lead.customerTags : rawProfile.customerTags || []
    });
    this.setData({
      loading: false,
      error: "",
      profile,
      leadId: resolvedLeadId || profile.leadReminderId || "",
      // A visitor without a lead still needs the same draft form so the
      // bottom "保存并开始跟进" action can submit tags, note and next date in
      // its first atomic request.
      followUpVisible: Boolean(profile),
      activityExpanded: preserveUi ? this.data.activityExpanded : false,
      materialsExpanded: preserveUi ? this.data.materialsExpanded : false,
      followUpText: preserveUi ? this.data.followUpText : "",
      nextFollowUpAt: preserveUi && this.data.nextFollowUpAt ? this.data.nextFollowUpAt : followUp.nextFollowUpAt,
      followUpStatusText: followUp.statusText,
      followUpLogs: followUp.logs,
      followUpTags: preserveUi ? this.data.followUpTags : followUp.customerTags,
      followUpTagOptions: buildFollowUpTagOptions(preserveUi ? this.data.followUpTags : followUp.customerTags)
    });
    return true;
  },

  async refreshDetailInBackground({ requestId, ownerUserId, customerId, mode, leadId }) {
    try {
      const detailRes = await api.fetchCustomerDetail(
        ownerUserId,
        ownerUserId,
        leadId ? "" : customerId,
        mode,
        leadId
      );
      if (requestId !== this._detailRequestSeq || (getCurrentUser() || {}).id !== ownerUserId) return;
      const detail = detailRes && detailRes.data;
      if (!detail || detail.locked !== false) {
        customerDetailStore.clear(ownerUserId, mode);
        return;
      }
      customerDetailStore.remember(ownerUserId, mode, customerId, leadId, detailRes);
      this.applyDetailResponse(detailRes, requestId, { preserveUi: true });
    } catch (error) {
      // The cached projection remains visible if revalidation is unavailable.
      console.warn("[customer-detail] background refresh failed", error);
    }
  },

  async reconcileFollowUpFromServer() {
    const currentUser = getCurrentUser();
    if (!currentUser) return null;
    try {
      return await api.fetchCustomerDetail(
        currentUser.id,
        currentUser.id,
        this.data.leadId ? "" : (this.data.customerId || ""),
        this.data.mode || "",
        this.data.leadId || (this.data.profile && this.data.profile.leadReminderId) || ""
      );
    } catch (error) {
      return null;
    }
  },

  handleRetry() {
    this.loadDetail();
  },

  handleBackToRadar() {
    this.returnToRadar();
  },

  returnToRadar(title = "", targetTab = "") {
    try {
      wx.setStorageSync(
        RADAR_ENTRY_TAB_KEY,
        normalizeRadarTab(targetTab || this.data.sourceTab)
      );
    } catch (error) {
      // The tab preference is non-critical; navigation must still proceed.
    }
    wx.switchTab({
      url: "/pages/visits/index",
      success: () => {
        if (title) wx.showToast({ title, icon: "success" });
      },
      fail: (navigationError) => {
        console.error("[customer-detail] switch to radar failed", navigationError);
        wx.showToast({ title: title ? `${title}，请返回雷达查看` : "请返回客户雷达查看", icon: "none" });
      }
    });
  },

  handleOpenMaterial(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) {
      wx.showToast({ title: "资料来源暂不可打开", icon: "none" });
      return;
    }
    navigateToNoteView(id);
  },

  handleOpenCustomerMessage() {
    const threadId = this.data.profile
      && this.data.profile.messageSummary
      && this.data.profile.messageSummary.latestThreadId;
    if (!threadId) {
      wx.showToast({ title: "暂无可打开的留言", icon: "none" });
      return;
    }
    this._refreshOnShow = true;
    wx.navigateTo({
      url: `/pages/message-thread/index?id=${encodeURIComponent(threadId)}&source=customer-detail`
    });
  },

  handleToggleActivity() {
    this.setData({ activityExpanded: !this.data.activityExpanded });
  },

  handleToggleMaterials() {
    this.setData({ materialsExpanded: !this.data.materialsExpanded });
  },

  handleCopyScript() {
    const script = this.data.profile && this.data.profile.script;
    if (!script) return;
    wx.setClipboardData({ data: script, success: () => wx.showToast({ title: "话术已复制", icon: "success" }) });
  },

  handleCopyContact(event) {
    const type = event.currentTarget.dataset.type;
    const profile = this.data.profile || {};
    const value = String(profile[type] || "").trim();
    if (!value) return;
    wx.setClipboardData({
      data: value,
      success: () => wx.showToast({ title: "已复制", icon: "success" })
    });
  },

  handleCallContact() {
    const phone = String((this.data.profile && this.data.profile.phone) || "").trim();
    if (!phone) {
      wx.showToast({ title: "暂无手机号", icon: "none" });
      return;
    }
    wx.makePhoneCall({
      phoneNumber: phone,
      fail: () => wx.showToast({ title: "拨号失败", icon: "none" })
    });
  },

  handleGenerateCompare() {
    const profile = this.data.profile || {};
    const noteId = profile.materials && profile.materials[0] && profile.materials[0].id;
    if (!noteId) {
      wx.showToast({ title: "暂无足够资料可生成对比", icon: "none" });
      return;
    }
    const mode = this.data.mode || "property";
    wx.navigateTo({ url: `/subpackages/workbench/showcase-edit/index?mode=${encodeURIComponent(mode)}&method=radar_compare&noteId=${encodeURIComponent(noteId)}` });
  },

  async handleRecordFollowUp() {
    const currentUser = getCurrentUser();
    const customerId = String(this.data.customerId || "").trim();
    const leadId = String(this.data.leadId || (this.data.profile && this.data.profile.leadReminderId) || "").trim();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if ((!customerId && !leadId) || this.data.creatingFollowUp || this.data.updatingFollowUpStatus) {
      wx.showToast({ title: "缺少客户身份，暂时无法开始跟进", icon: "none" });
      return;
    }
    const currentStatus = String((this.data.profile && this.data.profile.leadStatus) || "").trim();
    const action = ["following", "contacted"].includes(currentStatus) ? "continue" : "start";
    this.setData({ creatingFollowUp: true });
    try {
      const response = await api.actOnCustomerFollowup({
        ownerUserId: currentUser.id,
        requesterUserId: currentUser.id,
        ...followupActionHint(this.data.profile || {}),
        // A persisted leadId is the canonical target. Do not mix it with a
        // legacy/source customer alias, which can trigger a false mismatch.
        customerId: leadId ? "" : customerId,
        mode: this.data.mode || "",
        leadId,
        action,
        operationId: createOperationId(action, leadId || customerId),
        expectedVersion: profileLeadVersion(this.data.profile),
        followUpTags: this.data.followUpTags || [],
        logContent: String(this.data.followUpText || "").trim(),
        nextFollowUpAt: this.data.nextFollowUpAt || ""
      });
      // The action endpoint is the source of truth. Once it returns, the
      // server has committed the new state; invalidate local projections and
      // let the radar page render the authoritative list instead of doing a
      // second, slow customer-detail read here.
      customerIntelligenceStore.clear(currentUser.id, this.data.mode || "");
      api.clearCustomerIntelligenceSummaryCache(currentUser.id);
      customerDetailStore.clear(currentUser.id, this.data.mode || "");
      this._detailRequestSeq = (this._detailRequestSeq || 0) + 1;
      const savedLead = response && response.data && response.data.lead;
      const mutationIdentity = radarMutationIdentity(
        this.data.profile || {},
        savedLead || {},
        customerId
      );
      customerIntelligenceStore.queueRadarMutation(currentUser.id, this.data.mode || "", {
        action,
        ...mutationIdentity,
        leadId: (savedLead && savedLead.id) || leadId,
        leadVersion: savedLead && savedLead.version,
        nextFollowUpAt: savedLead && savedLead.nextFollowUpAt,
        status: (savedLead && savedLead.status) || (action === "continue" ? "following" : "following"),
        sourceTab: this.data.sourceTab || "followup"
      });
      this.returnToRadar(
        action === "continue" ? "已继续跟进" : "已开始跟进",
        "following"
      );
    } catch (error) {
      if (Number(error && error.statusCode) === 402) {
        wx.redirectTo({ url: "/pages/membership/index" });
        return;
      }
      const uncertain = !error || error.errorType === "network" || error.errorType === "server" || error.statusCode === 409 || !error.statusCode;
      if (uncertain) {
        const reconciled = await this.reconcileFollowUpFromServer();
        const reconciledLead = reconciled && reconciled.data && reconciled.data.lead;
        if (reconciledLead && ["following", "contacted"].includes(reconciledLead.status)) {
          customerIntelligenceStore.clear(currentUser.id, this.data.mode || "");
          api.clearCustomerIntelligenceSummaryCache(currentUser.id);
          customerDetailStore.clear(currentUser.id, this.data.mode || "");
          customerIntelligenceStore.queueRadarMutation(currentUser.id, this.data.mode || "", {
            action,
            ...radarMutationIdentity(this.data.profile || {}, reconciledLead, customerId),
            leadId: reconciledLead.id || leadId,
            leadVersion: reconciledLead.version,
            nextFollowUpAt: reconciledLead.nextFollowUpAt,
            status: reconciledLead.status,
            sourceTab: this.data.sourceTab || "followup"
          });
          this.returnToRadar("跟进状态已保存", "following");
          return;
        }
      }
      wx.showToast({ title: error.detail || "暂时无法建立跟进档案", icon: "none" });
    } finally {
      this.setData({ creatingFollowUp: false });
    }
  },

  async handleFollowUpStatusAction() {
    const currentUser = getCurrentUser();
    const profile = this.data.profile || {};
    const customerId = String(this.data.customerId || "").trim();
    const leadId = String(this.data.leadId || profile.leadReminderId || "").trim();
    const action = profile.leadStatus === "paused" ? "restore" : "abandon";
    const expectedStatus = action === "restore" ? "pending" : "paused";
    const targetTab = action === "restore" ? "followup" : "abandoned";
    const successTitle = action === "restore" ? "已恢复跟进" : "已放弃跟进";
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if ((!customerId && !leadId) || this.data.creatingFollowUp || this.data.updatingFollowUpStatus) {
      wx.showToast({ title: "缺少客户身份，暂时无法更新跟进状态", icon: "none" });
      return;
    }
    this.setData({ updatingFollowUpStatus: true });
    try {
      const response = await api.actOnCustomerFollowup({
        ownerUserId: currentUser.id,
        requesterUserId: currentUser.id,
        ...followupActionHint(profile),
        customerId: leadId ? "" : customerId,
        mode: this.data.mode || "",
        leadId,
        action,
        operationId: createOperationId(action, leadId || customerId),
        expectedVersion: profileLeadVersion(profile),
        followUpTags: this.data.followUpTags || [],
        logContent: String(this.data.followUpText || "").trim(),
        nextFollowUpAt: this.data.nextFollowUpAt || ""
      });
      const savedLead = response && response.data && response.data.lead;
      customerIntelligenceStore.clear(currentUser.id, this.data.mode || "");
      api.clearCustomerIntelligenceSummaryCache(currentUser.id);
      customerDetailStore.clear(currentUser.id, this.data.mode || "");
      this._detailRequestSeq = (this._detailRequestSeq || 0) + 1;
      const mutationIdentity = radarMutationIdentity(profile, savedLead || {}, customerId);
      customerIntelligenceStore.queueRadarMutation(currentUser.id, this.data.mode || "", {
        action,
        ...mutationIdentity,
        leadId: (savedLead && savedLead.id) || leadId,
        leadVersion: savedLead && savedLead.version,
        nextFollowUpAt: savedLead && savedLead.nextFollowUpAt,
        status: (savedLead && savedLead.status) || expectedStatus,
        sourceTab: this.data.sourceTab || "followup"
      });
      this.returnToRadar(successTitle, targetTab);
    } catch (error) {
      if (Number(error && error.statusCode) === 402) {
        wx.redirectTo({ url: "/pages/membership/index" });
        return;
      }
      const uncertain = !error || error.errorType === "network" || error.errorType === "server" || error.statusCode === 409 || !error.statusCode;
      if (uncertain) {
        const reconciled = await this.reconcileFollowUpFromServer();
        const reconciledLead = reconciled && reconciled.data && reconciled.data.lead;
        if (reconciledLead && reconciledLead.status === expectedStatus) {
          customerIntelligenceStore.clear(currentUser.id, this.data.mode || "");
          api.clearCustomerIntelligenceSummaryCache(currentUser.id);
          customerDetailStore.clear(currentUser.id, this.data.mode || "");
          customerIntelligenceStore.queueRadarMutation(currentUser.id, this.data.mode || "", {
            action,
            ...radarMutationIdentity(profile, reconciledLead, customerId),
            leadId: reconciledLead.id || leadId,
            leadVersion: reconciledLead.version,
            nextFollowUpAt: reconciledLead.nextFollowUpAt,
            status: reconciledLead.status,
            sourceTab: this.data.sourceTab || "followup"
          });
          this.returnToRadar("跟进状态已保存", targetTab);
          return;
        }
      }
      wx.showToast({ title: error.detail || "暂时无法更新跟进状态", icon: "none" });
    } finally {
      this.setData({ updatingFollowUpStatus: false });
    }
  },

  handleFollowUpChange(event) {
    this.setData({ followUpText: event.detail.value });
  },

  handleNextFollowUpChange(event) {
    this.setData({ nextFollowUpAt: event.detail.value || "" });
  },

  handleToggleFollowUpTag(event) {
    const tag = String(event.currentTarget.dataset.tag || "").trim();
    if (!tag) return;
    const currentTags = this.data.followUpTags || [];
    const nextTags = currentTags.includes(tag)
      ? currentTags.filter((item) => item !== tag)
      : [...currentTags, tag];
    this.setData({
      followUpTags: nextTags,
      followUpTagOptions: buildFollowUpTagOptions(nextTags)
    });
  },

});
