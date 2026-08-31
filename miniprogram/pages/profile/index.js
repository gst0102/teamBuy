const api = require("../../services/api");
const customerIntelligenceStore = require("../../stores/customer-intelligence-store");
const resourceStore = require("../../stores/resource-store");
const { clearAllCachedMedia } = require("../../utils/media-cache");
const messagePlugin = require("../../plugins/message-plugin/index");
const { getCurrentUser } = require("../../utils/dashboard");
const { formatDateOnly } = require("../../utils/date-format");
const cachePolicy = require("../../utils/cache-policy");
const subscription = require("../../services/subscription");
const {
  buildBusinessCardShareSource,
  buildBusinessCardShareTitle
} = require("../../utils/business-card-share");
const {
  ensureShareSnapshot,
  getNoteShareSnapshot,
  getShareSourceRevision,
  isShareImageUrl,
  isShareSnapshotReady,
  renderShareCard,
  setShareMenuEnabled,
  SHARE_CARD_STYLE_VERSION,
  buildNoteSharePlan
} = require("../../plugins/share-snapshot/index");

const GROUP_POINTS_KEY = "teambuy:groupResourceLibrary:points";
const GROUPS_KEY = "teambuy:groupResourceLibrary:groups";
const DEFAULT_RESOURCE_POINTS = 100;
const PROFILE_BUSINESS_CARD_CANVAS_ID = "profileBusinessCardShareCanvas";
const PROFILE_CARDS_CACHE_TTL_MS = cachePolicy.profileSummaryTtlMs;
const PROFILE_CARDS_STALE_TTL_MS = cachePolicy.profileSummaryStaleTtlMs;
const profileSummaryMemoryCache = {};
const profileSummaryInFlight = {};

function scopedStorageKey(base, userId) {
  return `${base}:${userId || "guest"}`;
}

function readStorageNumber(key, fallback) {
  try {
    const value = wx.getStorageSync(key);
    if (value === "" || value === undefined || value === null) return fallback;
    return Number(value || 0);
  } catch (error) {
    return fallback;
  }
}

function readStorageList(key) {
  try {
    const value = wx.getStorageSync(key);
    return Array.isArray(value) ? value : [];
  } catch (error) {
    return [];
  }
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

function isRemoteAvatarUrl(value) {
  return /^https:\/\//i.test(String(value || "").trim());
}

function isLocalAvatarPath(value) {
  const text = String(value || "").trim();
  return /^(wxfile|file):/i.test(text) || /^\/tmp\//i.test(text) || /^http:\/\/tmp\//i.test(text);
}

function avatarText(name) {
  const text = String(name || "我").trim();
  return text.slice(0, 1);
}

function formatViewedAt(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) return "时间未知";
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function absoluteMediaUrl(value) {
  const text = String(value || "").trim();
  if (!text || /^https?:\/\//i.test(text)) return text;
  const app = getApp();
  const globalData = (app && app.globalData) || {};
  const baseUrl = globalData.apiBaseUrl || "";
  const mediaRoutePrefix = globalData.mediaRoutePrefix || "";
  if (!baseUrl) return text;
  if (mediaRoutePrefix && text.startsWith("/media")) {
    return `${baseUrl}${mediaRoutePrefix}${text.slice("/media".length)}`;
  }
  return `${baseUrl}${text.startsWith("/") ? "" : "/"}${text}`;
}

function profileSubtitle(user) {
  const salesProfile = (user && user.salesProfile) || {};
  const role = String(salesProfile.jobTitle || salesProfile.role || "").trim();
  const city = String(salesProfile.city || "").trim();
  return [role, city].filter(Boolean).join(" · ") || "资料、资源和消息。";
}

function normalizeUser(user) {
  if (!user) return null;
  return {
    ...user,
    avatarUrl: safeAvatarUrl(user.avatarUrl),
    avatarText: avatarText(user.nickname),
    profileSubtitle: profileSubtitle(user),
    wechat: String(user.wechat || "").trim()
  };
}

function isBusinessCardResource(card = {}) {
  const config = card.visibilityConfig || {};
  const cardType = card.cardType || config.cardType || "";
  return cardType === "business_card" || card.categoryName === "名片";
}

function getCardShareState(card = {}) {
  const config = card.visibilityConfig || {};
  return card.shareState
    || card.sourceNoteShareState
    || config.shareState
    || (card.sharePublished ? "published" : "private");
}

function createNoteShareId(noteId) {
  return `share_note_${noteId || "note"}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function profileCardsCacheKey(ownerUserId) {
  const app = getApp();
  const globalData = (app && app.globalData) || {};
  return [
    globalData.environmentName || "",
    globalData.apiBaseUrl || "",
    ownerUserId || ""
  ].join("|");
}

function peekProfileCardsCache(ownerUserId) {
  const cached = profileSummaryMemoryCache[profileCardsCacheKey(ownerUserId)];
  if (!cached || !cached.data || typeof cached.data !== "object" || Array.isArray(cached.data)) return null;
  if (Date.now() - Number(cached.savedAt || 0) > PROFILE_CARDS_STALE_TTL_MS) return null;
  return cached;
}

function fetchProfileSummary(ownerUserId, forceRefresh = false) {
  const key = profileCardsCacheKey(ownerUserId);
  const cached = peekProfileCardsCache(ownerUserId);
  if (!forceRefresh && cached && Date.now() - Number(cached.savedAt || 0) <= PROFILE_CARDS_CACHE_TTL_MS) {
    return Promise.resolve({ data: cached.data, cached: true });
  }
  if (profileSummaryInFlight[key]) return profileSummaryInFlight[key];
  const request = api.fetchBusinessCardSummary(ownerUserId)
    .catch((error) => {
      if (Number(error && error.statusCode) !== 404) throw error;
      return api.fetchCardsMetadata({ ownerUserId }).then((res) => {
        const cards = Array.isArray(res.data) ? res.data : [];
        const businessCard = cards
          .filter((item) => isBusinessCardResource(item))
          .sort((left, right) => Date.parse(right.updatedAt || right.createdAt || 0) - Date.parse(left.updatedAt || left.createdAt || 0))[0] || null;
        return {
          ...res,
          data: {
            totalResources: cards.length,
            totalPv: 0,
            totalRelay: 0,
            businessCard
          }
        };
      });
    })
    .then((res) => {
      const data = res.data || { totalResources: 0, businessCard: null };
      profileSummaryMemoryCache[key] = { savedAt: Date.now(), data };
      return { ...res, data };
    })
    .finally(() => {
      delete profileSummaryInFlight[key];
    });
  profileSummaryInFlight[key] = request;
  return request;
}

function clearProfileCardsCache(ownerUserId) {
  delete profileSummaryMemoryCache[profileCardsCacheKey(ownerUserId)];
}

function buildResourceToolsH5Url(ticket) {
  const app = getApp();
  const globalData = (app && app.globalData) || {};
  const baseUrl = globalData.apiBaseUrl || "";
  const apiPrefix = globalData.apiRoutePrefix || "/api";
  const h5Prefix = globalData.apiRoutePrefix || "";
  const params = [
    `ticket=${encodeURIComponent(ticket || "")}`,
    `apiPrefix=${encodeURIComponent(apiPrefix || "/api")}`,
    `env=${encodeURIComponent(globalData.environmentName || "")}`
  ];
  return `${baseUrl}${h5Prefix}/h5/resource-tools/?${params.join("&")}`;
}

Page({
  data: {
    user: null,
    showProfileEditor: false,
    profileDraft: {
      nickname: "",
      avatarUrl: "",
      wechat: "",
      phone: ""
    },
    totalResources: 0,
    totalPv: 0,
    totalRelay: 0,
    viewHistory: [],
    viewHistoryHasMore: false,
    viewHistoryLoading: false,
    viewHistoryLoadError: false,
    messageUnread: 0,
    resourcePoints: DEFAULT_RESOURCE_POINTS,
    frozenResourcePoints: 0,
    showResourceRules: false,
    profileLegalAgreed: false,
    membership: { active: false, status: "free", plan: { priceFen: 1990 }, expiresAtText: "" },
    customerInfoChainEnabled: true,
    customerInfoChainPaymentRequired: true,
    membershipVisible: false,
    hasCustomerSignals: false,
    businessCardShareReady: false,
    businessCardShareGenerating: false,
    businessCardShareError: false,
    businessCardShareImage: "",
    businessCardShareKey: "",
    businessCardActionLabel: "读取中",
    businessCardShare: {
      noteId: "",
      title: "电子名片",
      coverUrl: ""
    }
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      setShareMenuEnabled(false);
      // The profile tab is browsable. Only account-owned actions such as
      // editing profile data or creating a business card should request login.
      this._profileStatsRequestSeq = (this._profileStatsRequestSeq || 0) + 1;
      this._salesScrmRequestSeq = (this._salesScrmRequestSeq || 0) + 1;
      this._businessCardShareSource = null;
      this._businessCardShareCard = null;
      this.setData({
        user: null,
        showProfileEditor: false,
        profileLegalAgreed: false,
        profileDraft: { nickname: "", avatarUrl: "", wechat: "", phone: "" },
        totalResources: 0,
        totalPv: 0,
        totalRelay: 0,
        viewHistory: [],
        viewHistoryHasMore: false,
        viewHistoryLoading: false,
        viewHistoryLoadError: false,
        messageUnread: 0,
        resourcePoints: DEFAULT_RESOURCE_POINTS,
        frozenResourcePoints: 0,
        showResourceRules: false,
        membership: { active: false, status: "free", plan: { priceFen: 1990 }, expiresAtText: "" },
        customerInfoChainEnabled: false,
        customerInfoChainPaymentRequired: true,
        membershipVisible: false,
        hasCustomerSignals: false,
        businessCardShareReady: false,
        businessCardShareGenerating: false,
        businessCardShareError: false,
        businessCardShareImage: "",
        businessCardShareKey: "",
        businessCardActionLabel: "登录后制作",
        businessCardShare: { noteId: "", title: "电子名片", coverUrl: "" }
      });
      return;
    }
    const salesRequestSeq = (this._salesScrmRequestSeq || 0) + 1;
    this._salesScrmRequestSeq = salesRequestSeq;
    this.setData({
      user: normalizeUser(currentUser),
      totalResources: 0,
      totalPv: 0,
      totalRelay: 0,
      viewHistory: [],
      viewHistoryHasMore: false,
      viewHistoryLoading: false,
      viewHistoryLoadError: false,
      messageUnread: 0,
      resourcePoints: DEFAULT_RESOURCE_POINTS,
      frozenResourcePoints: 0,
      showProfileEditor: false,
      membership: { active: false, status: "free", plan: { priceFen: 1990 }, expiresAtText: "" },
      customerInfoChainEnabled: false,
      customerInfoChainPaymentRequired: true,
      membershipVisible: false,
      hasCustomerSignals: false,
      businessCardShareReady: false,
      businessCardShareGenerating: false,
      businessCardShareError: false,
      businessCardShareImage: "",
      businessCardShareKey: "",
      businessCardActionLabel: "读取中",
      businessCardShare: { noteId: "", title: "电子名片", coverUrl: "" }
    });
    subscription.preloadViewNotificationSubscriptionConfig(currentUser.id);
    const refreshAfterHide = Boolean(this._profileNeedsRefresh);
    this._profileNeedsRefresh = false;
    this.loadProfileStats(refreshAfterHide);
    this.loadViewHistory(currentUser.id);
    setTimeout(() => {
      const latestUser = getCurrentUser();
      if (latestUser && latestUser.id === currentUser.id) this.loadSalesScrm(currentUser.id, salesRequestSeq);
    }, 0);
  },
  onHide() {
    this._profileNeedsRefresh = true;
  },
  async loadViewHistory(userId) {
    const requestSeq = (this._viewHistoryRequestSeq || 0) + 1;
    this._viewHistoryRequestSeq = requestSeq;
    this.setData({ viewHistoryLoading: true, viewHistoryLoadError: false });
    try {
      const res = await api.fetchViewHistory(userId, 30);
      if (requestSeq !== this._viewHistoryRequestSeq || (getCurrentUser() || {}).id !== userId) return;
      const rows = Array.isArray(res.data) ? res.data : [];
      const normalizedRows = rows.map((item) => ({
        ...item,
        historyKey: `${item.targetType || "item"}:${item.id || ""}`,
        coverUrl: absoluteMediaUrl(item.coverUrl),
        viewedAtText: formatViewedAt(item.viewedAt)
      }));
      this.setData({
        viewHistory: normalizedRows.slice(0, 1),
        viewHistoryHasMore: normalizedRows.length > 1,
        viewHistoryLoadError: false
      });
    } catch (error) {
      if (requestSeq !== this._viewHistoryRequestSeq) return;
      this.setData({ viewHistory: [], viewHistoryHasMore: false, viewHistoryLoadError: true });
    } finally {
      if (requestSeq === this._viewHistoryRequestSeq) this.setData({ viewHistoryLoading: false });
    }
  },
  handleOpenViewedItem(event) {
    const type = event.currentTarget.dataset.type;
    const id = event.currentTarget.dataset.id;
    if (!id || !["note", "card"].includes(type)) return;
    const path = `/pages/note-preview/index?id=${encodeURIComponent(id)}`;
    wx.navigateTo({ url: path });
  },
  handleOpenViewHistory() {
    if (!getCurrentUser()) {
      wx.showToast({ title: "登录后保存浏览记录", icon: "none" });
      return;
    }
    wx.navigateTo({ url: "/pages/view-history/index" });
  },
  handleRetryViewHistory() {
    const currentUser = getCurrentUser();
    if (currentUser && currentUser.id) this.loadViewHistory(currentUser.id);
  },
  async loadSalesScrm(userId, requestSeq = this._salesScrmRequestSeq) {
    const membershipRes = await api.fetchMembership(userId).catch(() => null);
    if (requestSeq !== this._salesScrmRequestSeq || (getCurrentUser() || {}).id !== userId) return;
    if (!membershipRes || !membershipRes.data) {
      this.setData({
        customerInfoChainEnabled: false,
        membershipVisible: false,
        hasCustomerSignals: false,
      });
      return;
    }
    const membershipData = (membershipRes && membershipRes.data) || this.data.membership;
    const membership = {
      ...membershipData,
      expiresAtText: formatDateOnly(membershipData.expiresAt)
    };
    const customerInfoChainEnabled = membershipData.featureEnabled !== false;
    const paymentRequired = membershipData.paymentRequired !== false;
    if (!customerInfoChainEnabled) {
      this.setData({
        membership,
        customerInfoChainEnabled: false,
        customerInfoChainPaymentRequired: paymentRequired,
        hasCustomerSignals: false,
        membershipVisible: false,
      });
      return;
    }
    // The profile tab only needs to know whether the customer entry should be
    // shown. Do not wait for the full radar/dashboard payload here; the radar
    // tab owns that heavier read and shares its in-memory cache separately.
    const intelligenceRes = await api.fetchCustomerIntelligenceSummary(
      userId,
      userId,
      "property"
    ).catch(() => null);
    if (requestSeq !== this._salesScrmRequestSeq || (getCurrentUser() || {}).id !== userId) return;
    const intelligence = (intelligenceRes && intelligenceRes.data) || {};
    const summary = intelligence.summary || {};
    const dashboard = intelligence.dashboard || {};
    const hasCustomerSignals = Number(summary.visitorCount || 0) > 0
      || Number(summary.pendingLeadCount || 0) > 0
      || Number(summary.newInteractionCount || 0) > 0
      || Number(summary.repeatVisitorCount || 0) > 0
      || Number(summary.feedbackResourceCount || 0) > 0
      || Number(summary.visitors || 0) > 0
      || Number(summary.pending || 0) > 0
      || Number(summary.following || 0) > 0
      || Number(summary.abandoned || 0) > 0
      || Number(summary.interactions || 0) > 0
      || ["radarProfiles", "opportunityAlerts", "customerTimelines"]
        .some((key) => Array.isArray(dashboard[key]) && dashboard[key].length > 0)
      || (Array.isArray(intelligence.signalPreview) && intelligence.signalPreview.length > 0);
    this.setData({
      membership,
      customerInfoChainEnabled: true,
      customerInfoChainPaymentRequired: paymentRequired,
      hasCustomerSignals,
      membershipVisible: Boolean(customerInfoChainEnabled && paymentRequired && hasCustomerSignals)
    });
  },
  handleOpenMembership() {
    if (!this.data.membershipVisible) {
      wx.showToast({ title: "暂时还没有客户信号", icon: "none" });
      return;
    }
    if (this.data.membership && this.data.membership.active) {
      wx.navigateTo({ url: "/pages/membership/index" });
      return;
    }
    wx.showModal({
      title: "发现客户信号",
      content: "已有客户产生浏览或互动，开通客户信息链会员后可查看客户身份、联系方式和完整轨迹。",
      confirmText: "查看权益",
      cancelText: "稍后再说",
      success: (result) => {
        if (result.confirm) wx.navigateTo({ url: "/pages/membership/index" });
      }
    });
  },
  handleOpenReferralCenter() {
    if (!getCurrentUser()) {
      return wx.reLaunch({ url: "/pages/login/index?returnUrl=%2Fpages%2Freferral-center%2Findex" });
    }
    wx.navigateTo({ url: "/pages/referral-center/index" });
  },
  loadResourcePoints(userId) {
    const points = readStorageNumber(scopedStorageKey(GROUP_POINTS_KEY, userId), DEFAULT_RESOURCE_POINTS);
    const groups = readStorageList(scopedStorageKey(GROUPS_KEY, userId));
    const frozen = groups.reduce((sum, item) => sum + Number(item.pendingReward || 0), 0);
    this.setData({
      resourcePoints: points,
      frozenResourcePoints: frozen
    });
  },
  async loadProfileStats(forceRefresh = false) {
    const currentUser = getCurrentUser();
    if (!currentUser || !currentUser.id) return;
    const requestSeq = (this._profileStatsRequestSeq || 0) + 1;
    this._profileStatsRequestSeq = requestSeq;
    const cached = peekProfileCardsCache(currentUser.id);
    if (cached) {
      const cacheFresh = Date.now() - Number(cached.savedAt || 0) <= PROFILE_CARDS_CACHE_TTL_MS;
      this.applyProfileStats(cached.data, currentUser);
      this.loadMessageUnread(currentUser.id);
      if (cacheFresh && !forceRefresh) return;
      fetchProfileSummary(currentUser.id, true)
        .then((res) => {
          if (requestSeq !== this._profileStatsRequestSeq) return;
          this.applyProfileStats(res.data || [], currentUser);
        })
        .catch(() => {});
      return;
    }
    this.setData({
      businessCardShareReady: false,
      businessCardShareGenerating: false,
      businessCardShareError: false,
      businessCardShareImage: "",
      businessCardShareKey: "",
      businessCardActionLabel: "读取中"
    });
    try {
      const res = await fetchProfileSummary(currentUser.id);
      if (requestSeq !== this._profileStatsRequestSeq) return;
      this.applyProfileStats(res.data || [], currentUser);
    } catch (error) {
      if (requestSeq !== this._profileStatsRequestSeq) return;
      this.setData({
        businessCardShareReady: false,
        businessCardShareGenerating: false,
        businessCardShareError: false,
        businessCardShareImage: "",
        businessCardActionLabel: "制作名片"
      });
      wx.showToast({ title: "我的数据加载失败", icon: "none" });
      return;
    }
    this.loadMessageUnread(currentUser.id);
  },
  applyProfileStats(summary, currentUser) {
    const profileSummary = summary && typeof summary === "object" ? summary : {};
    const dashboard = {
      totalResources: Number(profileSummary.totalResources || 0),
      totalPv: Number(profileSummary.totalPv || 0),
      totalRelay: Number(profileSummary.totalRelay || 0)
    };
    const businessCard = profileSummary.businessCard || null;
    const noteId = businessCard && businessCard.sourceNoteId || "";
    const shareState = getCardShareState(businessCard || {});
    const shareReady = Boolean(noteId && shareState === "published");
    const shareSource = shareReady ? buildBusinessCardShareSource(businessCard, currentUser) : null;
    const shareEntity = shareReady ? {
      ...businessCard,
      id: noteId,
      revision: businessCard.revision || 0,
      visibilityConfig: businessCard.visibilityConfig || {}
    } : null;
    const sharePlan = shareReady ? buildNoteSharePlan(shareEntity, currentUser) : null;
    const shareStyleId = sharePlan ? sharePlan.styleId : SHARE_CARD_STYLE_VERSION;
    const shareSourceForSnapshot = sharePlan ? sharePlan.source : null;
    const shareFingerprint = sharePlan ? sharePlan.fingerprint : "";
    const existingSnapshot = shareReady ? getNoteShareSnapshot(shareEntity) : null;
    const existingSnapshotImage = isShareSnapshotReady(
      existingSnapshot,
      shareEntity && getShareSourceRevision("note", shareEntity),
      shareFingerprint
    ) && isShareImageUrl(existingSnapshot.url)
      ? existingSnapshot.url
      : "";
    const shareKey = shareReady
      ? [
          noteId,
          businessCard.revision || "",
          businessCard.updatedAt || businessCard.createdAt || "",
          shareStyleId,
          shareFingerprint
        ].join("|")
      : "";
    const sameShare = Boolean(shareKey && shareKey === this.data.businessCardShareKey);
    const existingImage = sameShare ? (this.data.businessCardShareImage || existingSnapshotImage) : existingSnapshotImage;
    const existingError = sameShare && this.data.businessCardShareError;
    const wasGenerating = sameShare && this.data.businessCardShareGenerating;
    const businessCardShare = {
      noteId,
      title: shareSource ? buildBusinessCardShareTitle(shareSource) : businessCard && businessCard.title || "电子名片",
      coverUrl: businessCard && businessCard.coverUrl || ""
    };
    this._businessCardShareSource = shareSource;
    this._businessCardShareCard = businessCard;
    this._businessCardShareEntity = shareEntity;
    this._businessCardShareSnapshotSource = shareSourceForSnapshot;
    this._businessCardShareFingerprint = shareFingerprint;
    this._businessCardShareStyleId = shareStyleId;
    if (noteId) wx.setStorageSync(`businessCardNoteId:${currentUser.id}`, noteId);
    this.setData({
      totalResources: dashboard.totalResources,
      totalPv: dashboard.totalPv,
      totalRelay: dashboard.totalRelay,
      businessCardShare,
      businessCardShareKey: shareKey,
      businessCardShareImage: existingImage,
      businessCardShareReady: Boolean(shareReady && existingImage),
      businessCardShareGenerating: Boolean(shareReady && !existingImage && !existingError),
      businessCardShareError: Boolean(shareReady && !existingImage && existingError),
      businessCardActionLabel: existingImage
        ? "发名片"
        : existingError
          ? "重试分享图"
          : shareReady
            ? "准备中"
            : businessCard
              ? "完善名片"
              : "制作名片"
    }, () => {
      setShareMenuEnabled(Boolean(shareReady && existingImage));
      if (shareReady && !existingImage && !existingError && !wasGenerating) {
        this.prepareBusinessCardShareImage(shareSource, shareKey);
      }
    });
  },
  async prepareBusinessCardShareImage(source, shareKey) {
    if (!source || !shareKey || shareKey !== this.data.businessCardShareKey) return;
    this.setData({
      businessCardShareReady: false,
      businessCardShareGenerating: true,
      businessCardShareError: false,
      businessCardActionLabel: "准备中"
    });
    try {
      const ownerUserId = (getCurrentUser() || {}).id;
      const sourceForSnapshot = this._businessCardShareSnapshotSource || source;
      const result = await ensureShareSnapshot({
        entityType: "note",
        entity: this._businessCardShareEntity,
        ownerUserId,
        styleId: this._businessCardShareStyleId || SHARE_CARD_STYLE_VERSION,
        fingerprint: this._businessCardShareFingerprint,
        generate: () => renderShareCard({
          page: this,
          canvasId: PROFILE_BUSINESS_CARD_CANVAS_ID,
          source: sourceForSnapshot,
          variant: "business_card",
          upload: true,
          ownerUserId
        })
      });
      const imagePath = result.snapshot.url;
      if (shareKey !== this.data.businessCardShareKey) return;
      const ready = Boolean(imagePath);
      this.setData({
        businessCardShareImage: imagePath || "",
        businessCardShareReady: ready,
        businessCardShareGenerating: false,
        businessCardShareError: !ready,
        businessCardActionLabel: ready ? "发名片" : "重试分享图"
      });
    } catch (error) {
      if (shareKey !== this.data.businessCardShareKey) return;
      this.setData({
        businessCardShareReady: false,
        businessCardShareGenerating: false,
        businessCardShareError: true,
        businessCardActionLabel: "重试分享图"
      });
    }
  },
  async loadMessageUnread(ownerUserId) {
    try {
      const messageUnread = await messagePlugin.fetchUnreadTotal(ownerUserId);
      if ((getCurrentUser() || {}).id !== ownerUserId) return;
      this.setData({ messageUnread });
    } catch (error) {
      this.setData({ messageUnread: 0 });
    }
  },
  handleGoLibrary() {
    wx.switchTab({ url: "/pages/library/index" });
  },
  handleOpenMutualHelp() {
    wx.navigateTo({ url: "/subpackages/my-tools-mutual-help/index/index" });
  },
  handleOpenUnavailableTool() {
    wx.showToast({ title: "微信群工具即将上线", icon: "none" });
  },
  handleGoBusinessCardEditor() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const loadedNoteId = this.data.businessCardShare && this.data.businessCardShare.noteId;
    if (loadedNoteId) {
      wx.navigateTo({ url: `/subpackages/workbench/business-card-studio/index?id=${encodeURIComponent(loadedNoteId)}` });
      return;
    }
    // 资料列表失败或页面首次进入时，仍优先复用名片 noteId 缓存。
    let cachedNoteId = "";
    try {
      cachedNoteId = wx.getStorageSync(`businessCardNoteId:${currentUser.id}`) || "";
    } catch (error) {}
    if (cachedNoteId) {
      wx.navigateTo({ url: `/subpackages/workbench/business-card-studio/index?id=${encodeURIComponent(cachedNoteId)}` });
      return;
    }
    wx.navigateTo({ url: "/subpackages/workbench/business-card-studio/index" });
  },
  handleBusinessCardAction() {
    if (this.data.businessCardShareGenerating) return;
    if (this.data.businessCardShareError && this._businessCardShareSource) {
      this.prepareBusinessCardShareImage(
        this._businessCardShareSource,
        this.data.businessCardShareKey
      );
      return;
    }
    this.handleGoBusinessCardEditor();
  },
  handleShareTap() {
    subscription.requestViewNotificationSubscription("profile_business_card_share");
  },
  onShareAppMessage() {
    const share = this.data.businessCardShare || {};
    const user = getCurrentUser();
    if (!this.data.businessCardShareReady || !share.noteId || !isShareImageUrl(this.data.businessCardShareImage)) {
      wx.showToast({ title: "名片还没准备好，请先完善", icon: "none" });
      setShareMenuEnabled(false);
      return null;
    }
    const shareId = createNoteShareId(share.noteId);
    const shareFromUserId = user ? user.id : "";
    api.recordNoteView(share.noteId, {
      eventType: "share",
      viewerUserId: shareFromUserId,
      shareId,
      shareFromUserId,
      scene: "profile_business_card_share",
      referrer: "profile"
    }).catch(() => {});
    return {
      title: `${share.title || "电子名片"}｜点开查看完整资料`,
      path: `/pages/note-preview/index?id=${encodeURIComponent(share.noteId)}&sid=${encodeURIComponent(shareId)}&from=${encodeURIComponent(shareFromUserId)}&src=profile_business_card_share`,
      imageUrl: this.data.businessCardShareImage
    };
  },
  handleGoMessages() {
    messagePlugin.openMessageCenter();
  },
  handleGoShowcases() {
    wx.navigateTo({ url: "/pages/showcases/index" });
  },
  handleOpenResourceHub() {
    wx.navigateTo({ url: "/pages/group-resource-library/index" });
  },
  handleOpenEnterpriseSearch() {
    wx.navigateTo({ url: "/pages/enterprise-resource-search/index" });
  },
  async handleOpenOpportunityRadar() {
    const currentUser = getCurrentUser();
    if (!currentUser || !currentUser.id) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    try {
      wx.showLoading({ title: "打开资源工具" });
      const res = await api.createH5Ticket({ userId: currentUser.id, entry: "resource-tools" });
      const ticket = res && res.data && res.data.ticket;
      const h5Url = buildResourceToolsH5Url(ticket);
      wx.hideLoading();
      wx.navigateTo({ url: `/pages/resource-tools-webview/index?src=${encodeURIComponent(h5Url)}` });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: "资源工具升级中，已打开旧版", icon: "none" });
      setTimeout(() => wx.navigateTo({ url: "/pages/opportunity-radar/index" }), 700);
    }
  },
  handleOpenResourceRules() {
    this.setData({ showResourceRules: true });
  },
  handleCloseResourceRules() {
    this.setData({ showResourceRules: false });
  },
  handleOpenHelp() {
    wx.navigateTo({ url: "/pages/help-feedback/index" });
  },
  handleOpenProfileEditor() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({
      showProfileEditor: true,
      profileLegalAgreed: false,
      profileDraft: {
        nickname: currentUser.nickname || "",
        avatarUrl: safeAvatarUrl(currentUser.avatarUrl),
        wechat: String(currentUser.wechat || "").trim(),
        phone: currentUser.phone || ""
      }
    });
  },
  handleCloseProfileEditor() {
    this.setData({ showProfileEditor: false });
  },
  noop() {},
  handleToggleProfileLegalAgree() {
    this.setData({ profileLegalAgreed: !this.data.profileLegalAgreed });
  },
  handleOpenTerms() {
    wx.navigateTo({ url: "/pages/legal/terms/index" });
  },
  handleOpenPrivacy() {
    wx.navigateTo({ url: "/pages/legal/privacy/index" });
  },
  handleProfileNicknameInput(event) {
    this.setData({ "profileDraft.nickname": event.detail.value });
  },
  handleProfileWechatInput(event) {
    this.setData({ "profileDraft.wechat": event.detail.value });
  },
  handleProfilePhoneInput(event) {
    this.setData({ "profileDraft.phone": event.detail.value });
  },
  handleUsePhoneAsWechat() {
    const phone = String(this.data.profileDraft.phone || "").trim();
    if (!phone) {
      wx.showToast({ title: "请先填写手机号", icon: "none" });
      return;
    }
    this.setData({ "profileDraft.wechat": phone }, () => {
      wx.showToast({ title: "已填入微信号", icon: "success" });
    });
  },
  handleChooseAvatarFromAlbum() {
    const handleSuccess = (result = {}) => {
      const firstFile = Array.isArray(result.tempFiles) ? result.tempFiles[0] : null;
      const avatarUrl = String((firstFile && firstFile.tempFilePath) || (result.tempFilePaths || [])[0] || "").trim();
      if (!avatarUrl) {
        wx.showToast({ title: "未选择头像", icon: "none" });
        return;
      }
      this.setData({ "profileDraft.avatarUrl": avatarUrl }, () => {
        wx.showToast({ title: "头像已选择，请保存资料", icon: "success" });
      });
    };
    const handleFail = (error = {}) => {
      if (/cancel/i.test(String(error.errMsg || ""))) return;
      wx.showToast({ title: "选择头像失败，请重试", icon: "none" });
    };
    if (typeof wx.chooseMedia === "function") {
      wx.chooseMedia({ count: 1, mediaType: ["image"], sourceType: ["album"], success: handleSuccess, fail: handleFail });
      return;
    }
    if (typeof wx.chooseImage !== "function") {
      wx.showToast({ title: "当前版本暂不支持选择头像", icon: "none" });
      return;
    }
    wx.chooseImage({ count: 1, sourceType: ["album"], success: handleSuccess, fail: handleFail });
  },
  async handleSaveProfile() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const nickname = String(this.data.profileDraft.nickname || "").trim();
    if (!nickname) {
      wx.showToast({ title: "请填写昵称", icon: "none" });
      return;
    }
    if (!this.data.profileLegalAgreed) {
      wx.showToast({ title: "请先阅读并同意协议", icon: "none" });
      return;
    }
    try {
      wx.showLoading({ title: "保存中" });
      let avatarUrl = String(this.data.profileDraft.avatarUrl || "").trim();
      if (avatarUrl && isLocalAvatarPath(avatarUrl)) {
        const uploaded = await api.uploadAsset({
          filePath: avatarUrl,
          mediaType: "image",
          ownerUserId: currentUser.id
        });
        avatarUrl = uploaded.url || "";
      }
      if (avatarUrl && !isRemoteAvatarUrl(avatarUrl)) {
        wx.hideLoading();
        wx.showToast({ title: "请重新从相册选择头像", icon: "none" });
        return;
      }
      const res = await api.updateUserProfile(currentUser.id, {
        nickname,
        avatarUrl,
        wechat: String(this.data.profileDraft.wechat || "").trim(),
        phone: String(this.data.profileDraft.phone || "").trim()
      });
      const app = getApp();
      const userWithBase = {
        ...(res.data || {}),
        apiBaseUrl: app.globalData.apiBaseUrl,
        apiRoutePrefix: app.globalData.apiRoutePrefix || "",
        environmentName: app.globalData.environmentName || ""
      };
      app.globalData.currentUser = userWithBase;
      wx.setStorageSync("currentUser", userWithBase);
      wx.hideLoading();
      this.setData({
        user: normalizeUser(userWithBase),
        showProfileEditor: false,
        businessCardShareImage: "",
        businessCardShareReady: false,
        businessCardShareGenerating: false,
        businessCardShareError: false
      });
      this.loadProfileStats(true);
      wx.showToast({ title: "已保存", icon: "success" });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
    }
  },
  handleLogout() {
    const currentUser = getCurrentUser();
    if (currentUser && currentUser.id) clearProfileCardsCache(currentUser.id);
    wx.removeStorageSync("currentUser");
    getApp().globalData.currentUser = null;
    customerIntelligenceStore.clearAll();
    resourceStore.clearAll();
    clearAllCachedMedia();
    if (typeof api.clearUserScopedCaches === "function") api.clearUserScopedCaches();
    wx.reLaunch({ url: "/pages/login/index" });
  }
});
