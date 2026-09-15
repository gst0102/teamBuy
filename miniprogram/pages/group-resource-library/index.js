const { getCurrentUser } = require("../../utils/dashboard");
const api = require("../../services/api");
const subscription = require("../../services/subscription");
const sharedPoints = require("../../utils/shared-points");

const GROUPS_KEY = "teambuy:groupResourceLibrary:mine";
const POINTS_KEY = "teambuy:groupResourceLibrary:points";
const VIEWED_KEY = "teambuy:groupResourceLibrary:viewed";
const NEW_USER_POINTS = 100;
const PUBLISH_DAILY_LIMIT = 1;
const STATE_CACHE_TTL_MS = 30000;
const DEFAULT_REGION = ["", "", ""];

const hotKeywords = ["互助", "房产", "团购", "老板资源", "本地生活", "供应链", "行业交流"];
const industryOptions = ["互助", "房产", "招聘", "电商", "教育", "本地生活", "供应链", "综合"];
const purposeOptions = ["找客户", "找同行", "找供应链", "找合作"];
const expireOptions = [
  { label: "1天", days: 1 },
  { label: "3天", days: 3 },
  { label: "5天", days: 5 },
  { label: "7天", days: 7, recommend: true }
];
const pageTitles = ["群资源库", "发布群资源", "补充群信息", "确认有效期", "发布成功"];

function storageKey(base, userId) {
  return `${base}:${userId || "guest"}`;
}

function readList(key) {
  try {
    const value = wx.getStorageSync(key);
    return Array.isArray(value) ? value : [];
  } catch (error) {
    return [];
  }
}

function readPoints(key) {
  try {
    const value = wx.getStorageSync(key);
    if (value === "" || value === undefined || value === null) {
      wx.setStorageSync(key, NEW_USER_POINTS);
      return NEW_USER_POINTS;
    }
    return Number(value || 0);
  } catch (error) {
    return NEW_USER_POINTS;
  }
}

function pointValue(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizePointBalances(data, fallback = {}) {
  const pointSummary = data && data.points ? data.points : {};
  const accounts = data && data.accounts ? data.accounts : {};
  const fallbackBase = pointValue(fallback.base, NEW_USER_POINTS);
  const fallbackReward = pointValue(fallback.reward, 0);
  const base = pointValue(
    pointSummary.base,
    pointValue(accounts.base && accounts.base.balance, fallbackBase)
  );
  const reward = pointValue(
    pointSummary.reward,
    pointValue(accounts.reward && accounts.reward.balance, fallbackReward)
  );
  return {
    total: pointValue(pointSummary.total, base + reward),
    base,
    reward
  };
}

function defaultDraft() {
  return {
    qrImage: "",
    name: "",
    cityMode: "national",
    region: DEFAULT_REGION,
    cityLabel: "全国",
    cityCode: "",
    industryIndex: 0,
    purposeIndex: 1,
    expireIndex: 3,
    remark: "",
    tags: []
  };
}

function buildPurposeChoices(selectedIndex = 1) {
  return purposeOptions.map((label, index) => ({ label, selected: index === selectedIndex }));
}

function dateText(value) {
  if (!value) return "有效期未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

function dateTimeText(value) {
  if (!value) return "时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function localDateKey(value = Date.now()) {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function countPublishedToday(groups, now = Date.now()) {
  const today = localDateKey(now);
  return groups.filter((group) => localDateKey(group.createdAt) === today).length;
}

function normalizePublishQuota(data) {
  const dailyLimit = Math.max(1, Number(data && data.dailyLimit) || PUBLISH_DAILY_LIMIT);
  const usedToday = Math.max(0, Number(data && data.usedToday) || 0);
  const remainingToday = Math.max(0, Number(data && data.remainingToday) || dailyLimit - usedToday);
  return { dailyLimit, usedToday, remainingToday };
}

function resolveExpireAt(group) {
  if (group.expiresAt) return Date.parse(group.expiresAt) || 0;
  if (group.expireAt) return Date.parse(group.expireAt) || 0;
  const createdAt = Date.parse(group.createdAt || "");
  return Number.isFinite(createdAt) ? createdAt + Number(group.expireDays || 7) * 86400000 : 0;
}

function groupStatusText(group, isExpired, rewardState) {
  if (isExpired) return "已过期";
  // Keep the internal reward state as `pending`, but normalize both the old
  // API label and the local fallback to the user-facing copy `审核中`.
  if (rewardState === "pending" || String(group.statusText || "").trim() === "待确认") return "审核中";
  return String(group.statusText || "").trim() || "已发布";
}

function decorateGroup(group, viewedIds = [], userId = "") {
  const expireAt = resolveExpireAt(group);
  const isExpired = Boolean(expireAt && expireAt <= Date.now()) || group.status === "expired";
  const rewardState = group.rewardState || "pending";
  const industry = group.industry || String(group.type || "").replace(/群$/, "") || "综合";
  const purpose = group.purpose || (Array.isArray(group.purposes) && group.purposes[0]) || "找同行";
  const rewardAmount = Number(group.rewardAmount || group.pendingReward || 0);
  const rewardText = rewardState === "pending" && rewardAmount
    ? `审核中 +${rewardAmount}`
    : (rewardState === "paid" && rewardAmount ? `已到账 +${rewardAmount}` : "");
  return {
    ...group,
    city: group.city || group.cityLabel || "全国",
    cityLabel: group.cityLabel || group.city || "全国",
    type: group.type || `${industry}群`,
    industry,
    purpose,
    purposes: group.purposes || [purpose],
    tags: Array.isArray(group.tags) ? group.tags : [],
    views: Number(group.views || 0),
    confirmCount: Number(group.confirmCount || 0),
    rewardState,
    rewardAmount,
    pendingReward: rewardState === "pending" ? rewardAmount : 0,
    rewardText,
    expireAt,
    expiresAt: group.expiresAt || (expireAt ? new Date(expireAt).toISOString() : ""),
    expireAtText: group.expireAtText || dateText(group.expiresAt || expireAt),
    isExpired,
    viewed: viewedIds.includes(group.id),
    canManage: !userId || group.ownerUserId === userId,
    statusText: groupStatusText(group, isExpired, rewardState)
  };
}

function chooseImage() {
  return new Promise((resolve, reject) => {
    let retriedLegacyPicker = false;
    const success = (res) => {
      const file = (res.tempFiles && res.tempFiles[0]) || {};
      const path = file.tempFilePath || (res.tempFilePaths && res.tempFilePaths[0]) || "";
      if (path) resolve(path);
      else reject({ detail: "没有选择图片" });
    };
    const chooseLegacy = () => wx.chooseImage({ count: 1, sourceType: ["album", "camera"], success, fail });
    const fail = (error) => {
      const rawMessage = String((error && error.errMsg) || "").toLowerCase();
      if (!retriedLegacyPicker && wx.chooseImage && /nofund|not.?found|not.?support/.test(rawMessage)) {
        retriedLegacyPicker = true;
        chooseLegacy();
        return;
      }
      reject({
        ...error,
        detail: /cancel/.test(rawMessage) ? "未选择图片" : "当前微信无法选择图片，请检查相册权限"
      });
    };
    if (wx.chooseMedia) wx.chooseMedia({ count: 1, mediaType: ["image"], sourceType: ["album", "camera"], success, fail });
    else if (wx.chooseImage) chooseLegacy();
    else reject({ detail: "当前微信版本不支持选择图片" });
  });
}

function decorateLiveQr(item) {
  const expiry = item && item.targetExpiresAt ? Date.parse(item.targetExpiresAt) : 0;
  const expired = Boolean(expiry && expiry <= Date.now()) || item.targetExpiryState === "expired";
  const expiresInDays = expired ? 0 : Number(item.targetExpiresInDays || 0);
  const expiring = !expired && expiresInDays > 0 && expiresInDays <= 2;
  return {
    ...item,
    name: String(item.name || "未命名活码").trim() || "未命名活码",
    remarkText: item.remark ? `备注：${item.remark}` : "备注：未填写备注",
    createdAtText: item.createdAtText || dateTimeText(item.createdAt || item.updatedAt),
    posterMode: item.posterMode === "source" ? "source" : "plain",
    posterModeText: item.posterMode === "source" ? "保留原图样式" : "纯二维码",
    targetExpiresInDays: expiresInDays,
    targetExpiresAtText: item.targetExpiresAtText || (item.targetExpiresAt ? dateText(item.targetExpiresAt) : "有效期未知"),
    targetExpiryState: expired ? "expired" : (item.targetExpiryState || "active"),
    statusText: expired ? "已过期" : (expiring ? "即将到期" : "使用中"),
    statusClass: expired ? "expired" : (expiring ? "expiring" : "active"),
    reminderState: item.reminderState || "pending",
    reminderText: item.reminderText || (item.reminderConfigured === false ? "到期提醒未配置" : "到期前提醒可开启")
  };
}

function errorText(error, fallback = "操作失败，请稍后重试") {
  return String((error && (error.detail || error.message)) || fallback);
}

function liveQrErrorText(error, fallback = "活码操作失败，请稍后重试") {
  const rawMessage = String((error && (error.detail || error.message || error.errMsg)) || "").toLowerCase();
  const statusCode = Number(error && error.statusCode || 0);
  if (statusCode === 404 || /活码不存在|活码服务尚未部署/.test(rawMessage)) {
    return "活码服务尚未部署，请先部署服务器后再试";
  }
  if (/nofund|not.?found|not.?support/.test(rawMessage)) {
    return "当前微信无法选择图片，请检查相册权限";
  }
  return errorText(error, fallback);
}

Page({
  data: {
    keyword: "",
    browseRegion: DEFAULT_REGION,
    browseCityLabel: "",
    browseIndustryIndex: 0,
    browsePurposeIndex: 0,
    browseIndustryOptions: ["全部行业", ...industryOptions],
    browsePurposeOptions: ["全部用途", ...purposeOptions],
    points: NEW_USER_POINTS,
    basePoints: NEW_USER_POINTS,
    rewardPoints: 0,
    rewardPointsVisible: false,
    groups: [],
    myGroups: [],
    displayGroups: [],
    liveQrCodes: [],
    liveQrView: "list",
    liveQrDetailId: "",
    liveQrDetail: null,
    activeGroupCount: 0,
    confirmedTotal: 0,
    frozenPoints: 0,
    viewedCount: 0,
    successReward: 0,
    tagInput: "",
    tagInputVisible: false,
    viewedIds: [],
    groupsCursor: "0",
    groupsHasMore: true,
    groupsLoadingMore: false,
    viewMode: "browse",
    publishStep: 0,
    pageTitle: pageTitles[0],
    draft: defaultDraft(),
    successGroup: null,
    qrViewer: null,
    rulesVisible: false,
    loading: false,
    browseError: "",
    mineError: "",
    liveQrLoading: false,
    liveQrError: "",
    liveQrStyleMode: "plain",
    isGroupResourceAdmin: false,
    publishQuota: { dailyLimit: PUBLISH_DAILY_LIMIT, usedToday: 0, remainingToday: PUBLISH_DAILY_LIMIT },
    publishQuotaReady: false,
    publishQuotaLoading: false,
    adminPublishMode: false,
    successIsAdmin: false,
    hotKeywords,
    industryOptions,
    purposeOptions,
    purposeChoices: buildPurposeChoices(),
    expireOptions
  },

  onLoad(options = {}) {
    const nextState = {};
    if (options.tab === "live-qr") {
      nextState.viewMode = "live-qr";
      nextState.pageTitle = "免费工具";
    }
    if (options.qrId) {
      nextState.liveQrView = "detail";
      nextState.liveQrDetailId = options.qrId;
    }
    if (Object.keys(nextState).length) this.setData(nextState);
  },

  onShow() {
    const currentUser = getCurrentUser();
    this.userId = currentUser && currentUser.id ? currentUser.id : "";
    this.groupsKey = storageKey(GROUPS_KEY, this.userId);
    this.pointsKey = storageKey(POINTS_KEY, this.userId);
    this.viewedKey = storageKey(VIEWED_KEY, this.userId);
    if (this.data.viewMode === "live-qr") {
      this.loadLiveQrCodes();
      return;
    }
    this.loadState();
  },

  loadState(options = {}) {
    if (this._stateRequestInFlight) return this._stateRequestInFlight;
    const force = Boolean(options && options.force);
    if (!force && this._stateLoadedAt && Date.now() - this._stateLoadedAt < STATE_CACHE_TTL_MS) {
      return Promise.resolve();
    }
    const request = this._loadStateFromServer();
    const trackedRequest = request.finally(() => {
      if (this._stateRequestInFlight === trackedRequest) this._stateRequestInFlight = null;
    });
    this._stateRequestInFlight = trackedRequest;
    return trackedRequest;
  },

  async _loadStateFromServer() {
    const viewedIds = readList(this.viewedKey);
    const localBalances = sharedPoints.getPointBalances(this.userId || "guest");
    let points = localBalances.total;
    this.setData({ loading: true, viewedIds, browseError: "", mineError: "", isGroupResourceAdmin: false, publishQuotaReady: false, publishQuotaLoading: Boolean(this.userId) });
    const requestUserId = this.userId;
    const publicResult = await api.fetchGroupResources({ cursor: "0", limit: 20 })
      .then((response) => ({ response, error: null }))
      .catch((error) => ({ response: null, error }));
    const publicPayload = publicResult && publicResult.response && publicResult.response.data;
    const publicGroups = publicPayload && Array.isArray(publicPayload.items)
      ? publicPayload.items
      : (Array.isArray(publicPayload) ? publicPayload : []);
    const publicHasMore = Boolean(publicPayload && publicPayload.hasMore);
    const publicCursor = (publicPayload && publicPayload.nextCursor) || "";
    const decoratedPublic = publicGroups.map((item) => decorateGroup(item, viewedIds));
    const browseGroups = decoratedPublic;
    // The public catalogue is the critical first paint. Account-scoped
    // requests continue below and must not hold the catalogue hostage.
    this.setData({
      loading: this.data.viewMode === "mine",
      browseError: publicResult && publicResult.error ? errorText(publicResult.error, "群资源加载失败，请点击重试") : "",
      groups: browseGroups,
      groupsCursor: publicCursor,
      groupsHasMore: publicHasMore,
      groupsLoadingMore: false,
      activeGroupCount: browseGroups.filter((item) => !item.isExpired).length
    }, () => this.applySearch());
    if (!publicResult.error) this._stateLoadedAt = Date.now();

    const [mineResult, pointsResult, adminStatusResult, quotaResult] = await Promise.all([
      requestUserId
        ? api.fetchMyGroupResources(requestUserId)
          .then((response) => ({ response, error: null }))
          .catch((error) => ({ response: null, error }))
        : Promise.resolve({ response: null, error: null }),
      requestUserId
        ? api.fetchMutualHelpStatus(requestUserId).catch(() => null)
        : Promise.resolve(null),
      requestUserId
        ? api.fetchGroupResourceAdminStatus(requestUserId).catch(() => null)
        : Promise.resolve(null),
      requestUserId
        ? api.fetchGroupResourcePublishQuota(requestUserId).then((response) => ({ response, error: null })).catch((error) => ({ response: null, error }))
        : Promise.resolve({ response: null, error: null })
    ]);
    if (this.userId !== requestUserId) {
      this.setData({ loading: false, publishQuotaLoading: false });
      return;
    }
    const mineGroups = mineResult && mineResult.response && Array.isArray(mineResult.response.data)
      ? mineResult.response.data
      : [];
    const pointBalances = pointsResult && pointsResult.data
      ? sharedPoints.saveServerPointData(pointsResult.data, requestUserId)
      : normalizePointBalances(null, localBalances);
    if (pointsResult && pointsResult.data) points = pointBalances.total;
    const publishQuota = quotaResult.response && quotaResult.response.data
      ? normalizePublishQuota(quotaResult.response.data)
      : this.data.publishQuota;
    const decoratedMine = mineGroups.map((item) => decorateGroup(item, viewedIds, requestUserId));
    this.setData({
      loading: false,
      browseError: publicResult && publicResult.error ? errorText(publicResult.error, "群资源加载失败，请点击重试") : "",
      mineError: mineResult && mineResult.error ? errorText(mineResult.error, "我的发布加载失败，请点击重试") : "",
      points,
      basePoints: pointBalances.base,
      rewardPoints: pointBalances.reward,
      rewardPointsVisible: pointBalances.reward > 0,
      isGroupResourceAdmin: Boolean(adminStatusResult && adminStatusResult.data && adminStatusResult.data.enabled),
      publishQuota,
      publishQuotaReady: Boolean(quotaResult.response && quotaResult.response.data),
      publishQuotaLoading: false,
      groups: browseGroups,
      groupsCursor: publicCursor,
      groupsHasMore: publicHasMore,
      groupsLoadingMore: false,
      myGroups: decoratedMine,
      activeGroupCount: browseGroups.filter((item) => !item.isExpired).length,
      confirmedTotal: decoratedMine.reduce((sum, item) => sum + Number(item.confirmCount || 0), 0),
      frozenPoints: decoratedMine.reduce((sum, item) => sum + Number(item.pendingReward || 0), 0),
      viewedCount: viewedIds.length
    }, () => this.applySearch());
  },

  getBrowseQuery() {
    return {
      keyword: String(this.data.keyword || "").trim(),
      cityLabel: String(this.data.browseCityLabel || "").trim(),
      industry: this.data.browseIndustryIndex ? industryOptions[this.data.browseIndustryIndex - 1] : "",
      purpose: this.data.browsePurposeIndex ? purposeOptions[this.data.browsePurposeIndex - 1] : ""
    };
  },

  async loadBrowseGroups(reset = false) {
    if (this.data.viewMode !== "browse") return;
    if (!reset && (!this.data.groupsHasMore || this.data.groupsLoadingMore)) return;
    const requestSeq = (this._browseRequestSeq || 0) + 1;
    this._browseRequestSeq = requestSeq;
    const cursor = reset ? "0" : (this.data.groupsCursor || "0");
    this.setData({ groupsLoadingMore: true, ...(reset ? { groupsCursor: "0", groupsHasMore: true, browseError: "" } : {}) });
    try {
      const response = await api.fetchGroupResources({ ...this.getBrowseQuery(), cursor, limit: 20 });
      if (requestSeq !== this._browseRequestSeq) return;
      const payload = response && response.data;
      const items = payload && Array.isArray(payload.items) ? payload.items : (Array.isArray(payload) ? payload : []);
      const viewedIds = this.data.viewedIds || [];
      const incoming = items.map((item) => decorateGroup(item, viewedIds));
      const groups = reset ? incoming : [...(this.data.groups || []), ...incoming];
      this.setData({
        groups,
        groupsCursor: payload && payload.nextCursor ? payload.nextCursor : "",
        groupsHasMore: Boolean(payload && payload.hasMore),
        groupsLoadingMore: false,
        browseError: "",
        activeGroupCount: groups.filter((item) => !item.isExpired).length
      }, () => this.applySearch());
    } catch (error) {
      if (requestSeq !== this._browseRequestSeq) return;
      this.setData({
        groups: reset ? [] : this.data.groups,
        groupsLoadingMore: false,
        browseError: reset ? errorText(error, "群资源加载失败，请点击重试") : this.data.browseError
      }, () => {
        if (reset) this.applySearch();
      });
      if (reset) wx.showToast({ title: errorText(error, "群资源加载失败"), icon: "none" });
    }
  },

  handleRetryGroups() {
    if (this.data.viewMode === "mine") {
      this.loadState({ force: true });
      return;
    }
    this.loadBrowseGroups(true);
  },

  onReachBottom() {
    if (this.data.viewMode === "browse") this.loadBrowseGroups(false);
  },

  loadLiveQrCodes() {
    if (this._liveQrRequestInFlight) return this._liveQrRequestInFlight;
    if (this._liveQrLoadedAt && Date.now() - this._liveQrLoadedAt < STATE_CACHE_TTL_MS) return Promise.resolve();
    const request = (async () => {
      this.setData({ liveQrLoading: true, liveQrError: "" });
      try {
        const response = await api.fetchLiveQrCodes(this.userId);
        const liveQrCodes = Array.isArray(response.data) ? response.data.map(decorateLiveQr) : [];
        const detailId = this.data.liveQrDetailId || "";
        const liveQrDetail = detailId ? liveQrCodes.find((item) => item.id === detailId) || null : null;
        this.setData({
          liveQrCodes,
          liveQrDetail,
          liveQrView: liveQrDetail ? "detail" : "list",
          liveQrDetailId: liveQrDetail ? detailId : ""
        });
        this._liveQrLoadedAt = Date.now();
      } catch (error) {
        this.setData({ liveQrError: liveQrErrorText(error, "活码加载失败，请稍后重试") });
      } finally {
        this.setData({ liveQrLoading: false });
      }
    })();
    const trackedRequest = request.finally(() => {
      if (this._liveQrRequestInFlight === trackedRequest) this._liveQrRequestInFlight = null;
    });
    this._liveQrRequestInFlight = trackedRequest;
    return trackedRequest;
  },

  saveGroups(groups) {
    wx.setStorageSync(this.groupsKey, groups);
  },

  savePoints(points) {
    sharedPoints.setTotalPoints(points, this.userId || "guest");
  },

  savePointBalances(balances) {
    sharedPoints.savePointBalances(balances, this.userId || "guest");
  },

  saveViewed(viewedIds) {
    wx.setStorageSync(this.viewedKey, viewedIds);
  },

  applySearch() {
    const keyword = String(this.data.keyword || "").trim().toLowerCase();
    const viewMode = this.data.viewMode || "browse";
    if (viewMode === "live-qr") {
      this.setData({ displayGroups: [] });
      return;
    }
    const source = viewMode === "mine" ? (this.data.myGroups || []) : (this.data.groups || []);
    const cityLabel = String(this.data.browseCityLabel || "").trim();
    const industry = viewMode === "browse" && this.data.browseIndustryIndex
      ? industryOptions[this.data.browseIndustryIndex - 1]
      : "";
    const purpose = viewMode === "browse" && this.data.browsePurposeIndex
      ? purposeOptions[this.data.browsePurposeIndex - 1]
      : "";
    const displayGroups = source.filter((group) => {
      if (viewMode === "browse" && group.isExpired) return false;
      if (cityLabel && group.cityMode !== "national" && !String(group.cityLabel || group.city).includes(cityLabel)) return false;
      if (industry && group.industry !== industry) return false;
      if (purpose && group.purpose !== purpose) return false;
      if (!keyword) return true;
      const text = [group.name, group.city, group.industry, group.purpose, group.remark].join(" ").toLowerCase();
      return text.includes(keyword);
    });
    this.setData({ displayGroups });
  },

  handleViewModeChange(event) {
    const viewMode = event.currentTarget.dataset.mode || "browse";
    if (viewMode !== "browse" && !this.ensureSignedIn(`/pages/group-resource-library/index?tab=${encodeURIComponent(viewMode)}`)) return;
    const nextState = { viewMode, keyword: "" };
    if (viewMode !== "live-qr" || this.data.viewMode !== "live-qr") {
      nextState.liveQrView = "list";
      nextState.liveQrDetailId = "";
      nextState.liveQrDetail = null;
    }
    this.setData(nextState, () => {
      if (viewMode === "browse") this.loadBrowseGroups(true);
      else this.applySearch();
      if (viewMode === "live-qr") this.loadLiveQrCodes();
    });
  },

  handleOpenLiveQrDetail(event) {
    const qrId = event.currentTarget.dataset.id;
    const liveQrDetail = (this.data.liveQrCodes || []).find((item) => item.id === qrId) || null;
    if (!liveQrDetail) return;
    this.setData({ liveQrView: "detail", liveQrDetailId: qrId, liveQrDetail });
  },

  handleBackLiveQrList() {
    this.setData({ liveQrView: "list", liveQrDetailId: "", liveQrDetail: null });
  },

  async handleOpenLiveQrCreator() {
    if (!this.ensureSignedIn("/pages/group-resource-library/index?tab=live-qr")) return;
    try {
      const filePath = await chooseImage();
      wx.showLoading({ title: "生成活码中", mask: true });
      const response = await api.createLiveQrCode({ filePath, ownerUserId: this.userId, styleMode: this.data.liveQrStyleMode });
      wx.hideLoading();
      const item = decorateLiveQr(response.data);
      this.setData({
        liveQrCodes: [item, ...(this.data.liveQrCodes || [])],
        liveQrView: "detail",
        liveQrDetailId: item.id,
        liveQrDetail: item
      });
      wx.showToast({ title: "活码已生成", icon: "success" });
      this.requestLiveQrReminder(item.id, "live_qr_created");
    } catch (error) {
      wx.hideLoading();
      if (error && error.detail !== "未选择图片" && error.detail !== "没有选择图片") wx.showToast({ title: liveQrErrorText(error, "活码生成失败"), icon: "none" });
    }
  },

  handleChooseLiveQrStyle(event) {
    const styleMode = event.currentTarget.dataset.mode === "source" ? "source" : "plain";
    this.setData({ liveQrStyleMode: styleMode });
  },

  async handleChangeLiveQrStyle(event) {
    if (!this.ensureSignedIn("/pages/group-resource-library/index?tab=live-qr")) return;
    const qrId = event.currentTarget.dataset.id;
    const styleMode = event.currentTarget.dataset.mode === "source" ? "source" : "plain";
    const current = (this.data.liveQrCodes || []).find((item) => item.id === qrId);
    if (!qrId || !current || current.posterMode === styleMode) return;
    wx.showLoading({ title: styleMode === "source" ? "生成投放图" : "切换样式", mask: true });
    try {
      const response = await api.updateLiveQrStyle(qrId, styleMode, this.userId);
      const item = decorateLiveQr(response.data);
      this.setData({
        liveQrCodes: (this.data.liveQrCodes || []).map((entry) => entry.id === qrId ? item : entry),
        liveQrDetail: this.data.liveQrDetailId === qrId ? item : this.data.liveQrDetail
      });
      wx.showToast({ title: styleMode === "source" ? "已保留原图样式" : "已切换为纯二维码", icon: "success" });
    } catch (error) {
      wx.showToast({ title: liveQrErrorText(error, "样式切换失败"), icon: "none" });
    } finally {
      wx.hideLoading();
    }
  },

  async handleUpdateLiveQr(event) {
    if (!this.ensureSignedIn("/pages/group-resource-library/index?tab=live-qr")) return;
    const qrId = event.currentTarget.dataset.id;
    if (!qrId) return;
    try {
      const filePath = await chooseImage();
      wx.showLoading({ title: "更新中", mask: true });
      const response = await api.updateLiveQrTarget(qrId, filePath, this.userId);
      wx.hideLoading();
      const item = decorateLiveQr(response.data);
      this.setData({
        liveQrCodes: (this.data.liveQrCodes || []).map((current) => current.id === qrId ? item : current),
        liveQrDetail: this.data.liveQrDetailId === qrId ? item : this.data.liveQrDetail
      });
      wx.showToast({ title: "入口未变，二维码已更新", icon: "success" });
      this.requestLiveQrReminder(qrId, "live_qr_updated");
    } catch (error) {
      wx.hideLoading();
      if (error && error.detail !== "未选择图片" && error.detail !== "没有选择图片") wx.showToast({ title: liveQrErrorText(error, "更新失败"), icon: "none" });
    }
  },

  async requestLiveQrReminder(qrId, source) {
    let result = null;
    try {
      result = await subscription.requestLiveQrExpiryNotificationSubscription(source);
    } catch (error) {
      return;
    }
    const accepted = Boolean(result && result.accepted);
    const reminderText = accepted ? "到期前提醒已开启" : "到期前提醒可开启";
    const liveQrCodes = (this.data.liveQrCodes || []).map((item) => item.id === qrId
      ? { ...item, reminderState: accepted ? "accepted" : "pending", reminderText }
      : item);
    this.setData({
      liveQrCodes,
      liveQrDetail: this.data.liveQrDetailId === qrId
        ? liveQrCodes.find((item) => item.id === qrId) || this.data.liveQrDetail
        : this.data.liveQrDetail
    });
  },

  handleEnableLiveQrReminder(event) {
    const qrId = event.currentTarget.dataset.id;
    if (qrId) this.requestLiveQrReminder(qrId, "live_qr_manual");
  },

  promptLiveQrReminder(qrId) {
    wx.showModal({
      title: "二维码已保存",
      content: "要开启到期提醒吗？",
      confirmText: "开启提醒",
      cancelText: "暂不开启",
      success: (res) => {
        if (res.confirm) this.requestLiveQrReminder(qrId, "live_qr_saved");
      }
    });
  },

  handleDownloadLiveQr(event) {
    const item = (this.data.liveQrCodes || []).find((qr) => qr.id === event.currentTarget.dataset.id);
    if (!item || !item.qrImageUrl) return;
    wx.showLoading({ title: "准备图片", mask: true });
    wx.downloadFile({
      url: item.qrImageUrl,
      success: (res) => {
        wx.hideLoading();
        if (res.statusCode !== 200) {
          wx.showToast({ title: "图片下载失败", icon: "none" });
          return;
        }
        wx.saveImageToPhotosAlbum({
          filePath: res.tempFilePath,
          success: () => this.promptLiveQrReminder(item.id),
          fail: () => wx.showToast({ title: "请允许保存到相册", icon: "none" })
        });
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: "图片下载失败", icon: "none" });
      }
    });
  },

  handleDeleteLiveQr(event) {
    if (!this.ensureSignedIn("/pages/group-resource-library/index?tab=live-qr")) return;
    const qrId = event.currentTarget.dataset.id;
    wx.showModal({
      title: "删除活码",
      content: "删除后固定入口将停止使用，确定删除吗？",
      confirmText: "删除",
      confirmColor: "#e5484d",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await api.deleteLiveQrCode(qrId, this.userId);
          const liveQrCodes = (this.data.liveQrCodes || []).filter((item) => item.id !== qrId);
          this.setData({
            liveQrCodes,
            liveQrView: this.data.liveQrDetailId === qrId ? "list" : this.data.liveQrView,
            liveQrDetailId: this.data.liveQrDetailId === qrId ? "" : this.data.liveQrDetailId,
            liveQrDetail: this.data.liveQrDetailId === qrId ? null : this.data.liveQrDetail
          });
          wx.showToast({ title: "已删除", icon: "success" });
        } catch (error) {
          wx.showToast({ title: errorText(error, "删除失败"), icon: "none" });
        }
      }
    });
  },

  handleKeywordInput(event) {
    this.setData({ keyword: event.detail.value });
  },

  handleSearch() {
    if (this.data.viewMode === "browse") this.loadBrowseGroups(true);
    else this.applySearch();
  },

  handleHotKeyword(event) {
    this.setData({ keyword: event.currentTarget.dataset.keyword || "" }, () => {
      if (this.data.viewMode === "browse") this.loadBrowseGroups(true);
      else this.applySearch();
    });
  },

  handleShowMine() {
    this.setData({ viewMode: "mine", keyword: "" }, () => this.applySearch());
  },

  handleBrowseRegionChange(event) {
    const region = event.detail.value || ["", "", ""];
    const city = region[1] || region[0] || "";
    this.setData({ browseRegion: region, browseCityLabel: city }, () => this.loadBrowseGroups(true));
  },

  handleClearBrowseCity() {
    this.setData({ browseRegion: DEFAULT_REGION, browseCityLabel: "" }, () => this.loadBrowseGroups(true));
  },

  handleBrowseIndustryChange(event) {
    this.setData({ browseIndustryIndex: Number(event.detail.value || 0) }, () => this.loadBrowseGroups(true));
  },

  handleBrowsePurposeChange(event) {
    this.setData({ browsePurposeIndex: Number(event.detail.value || 0) }, () => this.loadBrowseGroups(true));
  },

  handleOpenPublisher() {
    if (!this.ensureSignedIn("/pages/group-resource-library/index?tab=mine")) return;
    if (this.data.publishQuotaReady && Number(this.data.publishQuota.remainingToday) <= 0) {
      wx.showToast({ title: "今日发布额度已用完", icon: "none" });
      return;
    }
    this.setData({ publishStep: 1, pageTitle: pageTitles[1], draft: defaultDraft(), purposeChoices: buildPurposeChoices(1), adminPublishMode: false, successIsAdmin: false, tagInput: "", tagInputVisible: false });
  },

  handleOpenAdminPublisher() {
    if (!this.ensureSignedIn("/pages/group-resource-library/index?tab=mine")) return;
    if (!this.data.isGroupResourceAdmin) {
      wx.showToast({ title: "当前账号没有管理员权限", icon: "none" });
      return;
    }
    this.setData({ publishStep: 1, pageTitle: "管理员新增", draft: defaultDraft(), purposeChoices: buildPurposeChoices(1), adminPublishMode: true, successIsAdmin: false, tagInput: "", tagInputVisible: false });
  },

  handleFlowBack() {
    const step = Number(this.data.publishStep || 0);
    if (step <= 1 || step === 4) {
      this.setData({ publishStep: 0, pageTitle: pageTitles[0], adminPublishMode: false });
      return;
    }
    const nextStep = step - 1;
    this.setData({ publishStep: nextStep, pageTitle: pageTitles[nextStep] || pageTitles[0] });
  },

  handleOpenRules() {
    this.setData({ rulesVisible: true });
  },

  handleCloseRules() {
    this.setData({ rulesVisible: false });
  },

  async handleChooseQr() {
    try {
      this.setData({ "draft.qrImage": await chooseImage() });
    } catch (error) {}
  },

  handleDraftInput(event) {
    const key = event.currentTarget.dataset.key;
    if (key) this.setData({ [`draft.${key}`]: event.detail.value });
  },

  handleUseNational() {
    this.setData({ "draft.cityMode": "national", "draft.region": DEFAULT_REGION, "draft.cityLabel": "全国", "draft.cityCode": "" });
  },

  handleRegionChange(event) {
    const region = event.detail.value || DEFAULT_REGION;
    const province = region[0] || "";
    const city = region[1] || province || "";
    this.setData({
      "draft.cityMode": province || city ? "city" : "national",
      "draft.region": region,
      "draft.cityLabel": province || city ? (province && city && province !== city ? `${province} ${city}` : city) : "全国",
      "draft.cityCode": ""
    });
  },

  handleIndustryChoice(event) {
    this.setData({ "draft.industryIndex": Number(event.currentTarget.dataset.index || 0) });
  },

  handleCustomTagInput(event) {
    this.setData({ tagInput: String(event.detail.value || "") });
  },

  handleShowTagInput() {
    this.setData({ tagInputVisible: true });
  },

  handleAddCustomTag() {
    const tag = String(this.data.tagInput || "").trim().slice(0, 20);
    if (!tag) {
      wx.showToast({ title: "先填写标签", icon: "none" });
      return;
    }
    const tags = Array.isArray(this.data.draft.tags) ? this.data.draft.tags : [];
    if (tags.includes(tag)) {
      wx.showToast({ title: "标签已添加", icon: "none" });
      return;
    }
    if (tags.length >= 8) {
      wx.showToast({ title: "最多添加 8 个标签", icon: "none" });
      return;
    }
    this.setData({ "draft.tags": [...tags, tag], tagInput: "", tagInputVisible: false });
  },

  handleRemoveCustomTag(event) {
    const index = Number(event.currentTarget.dataset.index);
    const tags = Array.isArray(this.data.draft.tags) ? this.data.draft.tags : [];
    this.setData({ "draft.tags": tags.filter((_, tagIndex) => tagIndex !== index) });
  },

  handleExpireChoice(event) {
    this.setData({ "draft.expireIndex": Number(event.currentTarget.dataset.index || 0) });
  },

  handleTogglePurpose(event) {
    const index = Number(event.currentTarget.dataset.index || 0);
    this.setData({ "draft.purposeIndex": index, purposeChoices: buildPurposeChoices(index) });
  },

  handleNextFromUpload() {
    if (!this.data.draft.qrImage) {
      wx.showToast({ title: "先上传群二维码", icon: "none" });
      return;
    }
    this.setData({ publishStep: 2, pageTitle: pageTitles[2] });
  },

  handleNextFromInfo() {
    this.setData({ publishStep: 3, pageTitle: pageTitles[3] });
  },

  async handleSubmitGroup() {
    if (!this.ensureSignedIn("/pages/group-resource-library/index?tab=mine")) return;
    if (this.submitting) return;
    const draft = this.data.draft;
    const expireConfig = expireOptions[draft.expireIndex] || expireOptions[3];
    const industry = industryOptions[draft.industryIndex] || industryOptions[0];
    const purpose = purposeOptions[draft.purposeIndex] || purposeOptions[1];
    if (!draft.qrImage) {
      wx.showToast({ title: "先上传群二维码", icon: "none" });
      return;
    }
    if (!this.data.adminPublishMode && this.data.publishQuotaReady && Number(this.data.publishQuota.remainingToday) <= 0) {
      wx.showToast({ title: "今日发布额度已用完", icon: "none" });
      return;
    }
    this.submitting = true;
    wx.showLoading({ title: "发布中", mask: true });
    try {
      const asset = await api.uploadAsset({ filePath: draft.qrImage, mediaType: "image", ownerUserId: this.userId });
      const groupPayload = {
        name: String(draft.name || "").trim(),
        cityMode: draft.cityMode,
        cityLabel: draft.cityMode === "national" ? "全国" : draft.cityLabel,
        cityCode: draft.cityCode || null,
        industry,
        purpose,
        tags: Array.isArray(draft.tags) ? draft.tags : [],
        remark: String(draft.remark || "").trim(),
        qrImageUrl: asset.url,
        expiresInDays: expireConfig.days
      };
      const response = this.data.adminPublishMode
        ? await api.createAdminGroupResource({ ...groupPayload, operatorName: getCurrentUser()?.nickname || "" })
        : await api.createGroupResource({ ...groupPayload, ownerUserId: this.userId });
      wx.hideLoading();
      const group = response.data;
      this.setData({
        publishStep: 4,
        pageTitle: pageTitles[4],
        successGroup: group,
        successReward: Number(group.rewardAmount || 0),
        successIsAdmin: Boolean(this.data.adminPublishMode),
        adminPublishMode: false,
        draft: defaultDraft(),
        purposeChoices: buildPurposeChoices(1)
      }, () => this.loadState({ force: true }));
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: errorText(error, "发布失败，请稍后重试"), icon: "none" });
    } finally {
      this.submitting = false;
    }
  },

  async handleUpdateGroupQr(event) {
    if (!this.ensureSignedIn("/pages/group-resource-library/index?tab=mine")) return;
    const id = event.currentTarget.dataset.id;
    const current = (this.data.myGroups || []).find((item) => item.id === id);
    if (!current) return;
    try {
      const filePath = await chooseImage();
      wx.showLoading({ title: "更新中", mask: true });
      const asset = await api.uploadAsset({ filePath, mediaType: "image", ownerUserId: this.userId });
      await api.updateGroupResource(id, { ownerUserId: this.userId, qrImageUrl: asset.url, expiresInDays: 7 });
      wx.hideLoading();
      await this.loadState({ force: true });
      wx.showToast({ title: "二维码已更新", icon: "success" });
    } catch (error) {
      wx.hideLoading();
      if (error && error.detail !== "未选择图片" && error.detail !== "没有选择图片") wx.showToast({ title: errorText(error, "更新失败"), icon: "none" });
    }
  },

  handleDeleteGroup(event) {
    if (!this.ensureSignedIn("/pages/group-resource-library/index?tab=mine")) return;
    const id = event.currentTarget.dataset.id;
    const group = (this.data.myGroups || []).find((item) => item.id === id);
    if (!group) return;
    wx.showModal({
      title: "删除群资源",
      content: "删除后不会继续出现在找群列表中，确定删除吗？",
      confirmText: "删除",
      confirmColor: "#e5484d",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await api.deleteGroupResource(id, this.userId);
          await this.loadState({ force: true });
          wx.showToast({ title: "已删除", icon: "success" });
        } catch (error) {
          wx.showToast({ title: errorText(error, "删除失败"), icon: "none" });
        }
      }
    });
  },

  handleContinuePublish() {
    this.setData({ publishStep: 1, pageTitle: pageTitles[1], draft: defaultDraft(), successGroup: null, purposeChoices: buildPurposeChoices(1), adminPublishMode: false, successIsAdmin: false, tagInput: "", tagInputVisible: false });
  },

  handleViewResources() {
    if (!this.ensureSignedIn("/pages/group-resource-library/index?tab=mine")) return;
    this.setData({ publishStep: 0, pageTitle: pageTitles[0], successGroup: null, successIsAdmin: false, adminPublishMode: false, viewMode: "mine", keyword: "" }, () => this.loadState({ force: true }));
  },

  async handleViewQr(event) {
    if (!this.ensureSignedIn("/pages/group-resource-library/index")) return;
    const id = event.currentTarget.dataset.id;
    const group = (this.data.groups || []).find((item) => item.id === id);
    if (!group) return;
    try {
      wx.showLoading({ title: "打开中", mask: true });
      const response = await api.viewGroupResource(id, this.userId);
      wx.hideLoading();
      const data = response.data || {};
      const resource = decorateGroup(data.resource || group, this.data.viewedIds, this.userId);
      const viewedIds = this.data.viewedIds.includes(id) ? this.data.viewedIds : [...this.data.viewedIds, id];
      const pointBalances = normalizePointBalances(data, {
        base: this.data.basePoints,
        reward: this.data.rewardPoints
      });
      this.savePointBalances(pointBalances);
      this.saveViewed(viewedIds);
      this.setData({
        points: pointBalances.total,
        basePoints: pointBalances.base,
        rewardPoints: pointBalances.reward,
        rewardPointsVisible: pointBalances.reward > 0,
        viewedIds,
        viewedCount: viewedIds.length,
        qrViewer: { ...resource, qrImage: resource.qrImageUrl }
      });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: errorText(error, "暂时无法打开二维码"), icon: "none" });
    }
  },

  handleCloseQr() {
    this.setData({ qrViewer: null });
  },

  handleReportQrInvalid() {
    const viewer = this.data.qrViewer;
    if (!viewer || !viewer.id || !this.userId) return;
    wx.showModal({
      title: "举报二维码失效？",
      content: "仅在二维码无法加入群聊时提交。平台会根据不同用户的反馈暂停展示并核查。",
      confirmText: "确认举报",
      confirmColor: "#e5484d",
      success: async (result = {}) => {
        if (!result.confirm) return;
        try {
          const response = await api.fileGroupResourceComplaint(viewer.id, this.userId, "二维码失效");
          const data = response && response.data ? response.data : {};
          if (data.resource) {
            const resource = decorateGroup(data.resource, this.data.viewedIds, this.userId);
            this.setData({ qrViewer: { ...resource, qrImage: resource.qrImageUrl } });
          }
          wx.showToast({ title: data.protected ? "已触发保护，平台将核查" : (data.duplicate ? "你已举报过" : "失效举报已提交"), icon: "none" });
        } catch (error) {
          wx.showToast({ title: errorText(error, "举报失败，请稍后重试"), icon: "none" });
        }
      }
    });
  },

  ensureSignedIn(returnUrl = "/pages/group-resource-library/index") {
    const currentUser = getCurrentUser();
    if (currentUser && currentUser.id) {
      this.userId = currentUser.id;
      return true;
    }
    wx.reLaunch({ url: `/pages/login/index?returnUrl=${encodeURIComponent(returnUrl)}` });
    return false;
  },

  handleSaveViewedQr() {
    const qrImage = this.data.qrViewer && this.data.qrViewer.qrImage;
    if (!qrImage) {
      wx.showToast({ title: "二维码暂不可保存", icon: "none" });
      return;
    }
    wx.showLoading({ title: "保存中", mask: true });
    wx.downloadFile({
      url: qrImage,
      success: (response) => {
        wx.hideLoading();
        if (response.statusCode !== 200) {
          wx.showToast({ title: "图片下载失败", icon: "none" });
          return;
        }
        wx.saveImageToPhotosAlbum({
          filePath: response.tempFilePath,
          success: () => {
            wx.showToast({ title: "已保存", icon: "success" });
            this.handleCloseQr();
          },
          fail: () => wx.showToast({ title: "请允许保存到相册", icon: "none" })
        });
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: "图片下载失败", icon: "none" });
      }
    });
  },

  noop() {}
});
