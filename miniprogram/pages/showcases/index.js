const api = require("../../services/api");
const { avatarText, formatTime, getCurrentUser, safeAvatarUrl } = require("../../utils/dashboard");
const { buildShowcaseShareSource, createShareSnapshotFingerprint, ensureShareSnapshot, getShareSnapshot, getShareSourceRevision, isShareImageUrl, renderShareCard, setShareMenuEnabled, SHARE_CARD_STYLE_VERSION } = require("../../plugins/share-snapshot/index");
const { getModeConfig, readWorkspaceMode } = require("../../utils/workspace-mode");
const { buildTitleCoverData } = require("../../utils/title-cover");
const cachePolicy = require("../../utils/cache-policy");
const subscription = require("../../services/subscription");

const SHOWCASE_CACHE_TTL = cachePolicy.showcaseListTtlMs;
const SHOWCASE_SHARE_CANVAS_ID = "showcaseListShareCanvas";
const SHOWCASE_FILTERS = [
  { key: "recent", label: "最近" },
  { key: "frequent", label: "常发" },
  { key: "feedback", label: "高反馈" },
  { key: "draft", label: "草稿" }
];

const SHOWCASE_STATUS_FILTERS = [
  { key: "all", label: "全部状态" },
  { key: "published", label: "已发布" },
  { key: "draft", label: "草稿" },
  { key: "archived", label: "已下架" }
];

const SHOWCASE_TYPE_FILTERS = [
  { key: "all", label: "全部类型" },
  { key: "property", label: "房源" },
  { key: "service", label: "服务" },
  { key: "groupbuy", label: "商品" },
  { key: "notes", label: "日常" }
];

const COLLECTION_DIRECTIONS = {
  notes: [
    { key: "notes", icon: "资", tone: "blue", title: "日常合集", desc: "文章、图片、笔记一起发" }
  ],
  property: [
    { key: "property", icon: "房", tone: "green", title: "房源合集", desc: "多套房源一起推荐" }
  ],
  service: [
    { key: "service", icon: "案", tone: "teal", title: "案例合集", desc: "服务方案和案例组合" }
  ],
  groupbuy: [
    { key: "groupbuy", icon: "商", tone: "orange", title: "商品合集", desc: "多个商品一起分享" }
  ]
};

function collectionCopyForMode(mode) {
  if (mode === "property") {
    return {
      title: "房源合集",
      sub: "把多套房源组合成一个推荐包，发给客户快速对比。",
      createText: "新建房源合集",
      emptySub: "先选几条资料，打包成一页。"
    };
  }
  if (mode === "groupbuy") {
    return {
      title: "商品合集",
      sub: "把多个商品组合成一个可分享合集，方便发群和复用。",
      createText: "新建商品合集",
      emptySub: "先选几条资料，打包成一页。"
    };
  }
  if (mode === "service") {
    return {
      title: "案例合集",
      sub: "把名片、服务方案和案例组合成一个可分享合集。",
      createText: "新建案例合集",
      emptySub: "先选几条资料，打包成一页。"
    };
  }
  return {
    title: "日常合集",
    sub: "把多条资料打包成一个可分享、可复用的合集。",
    createText: "新建日常合集",
    emptySub: "先选几条资料，打包成一页。"
  };
}

function createShareId(showcaseId) {
  return `share_${showcaseId || "showcase"}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function buildCustomerShareTitle(title) {
  const cleanTitle = String(title || "这份合集").replace(/\s+/g, " ").trim();
  return `${cleanTitle}｜点开查看完整资料`;
}

function hasCurrentShowcaseSnapshot(item = {}) {
  const snapshot = getShareSnapshot("showcase", item);
  const sourceRevision = getShareSourceRevision("showcase", item);
  const expectedFingerprint = item.id
    ? createShareSnapshotFingerprint("showcase", item.id, sourceRevision, SHARE_CARD_STYLE_VERSION, buildShowcaseShareSource(item))
    : "";
  return Boolean(
    snapshot
      && snapshot.status === "ready"
      && isShareImageUrl(snapshot.url)
      && String(snapshot.sourceRevision || "") === sourceRevision
      && String(snapshot.styleId || "") === SHARE_CARD_STYLE_VERSION
      && String(snapshot.fingerprint || "") === expectedFingerprint
  );
}

function getLocalShowcaseShareImage(item = {}, shareImages = {}) {
  const entry = shareImages[item.id];
  const snapshot = getShareSnapshot("showcase", item);
  const sourceRevision = getShareSourceRevision("showcase", item);
  const expectedFingerprint = item.id
    ? createShareSnapshotFingerprint("showcase", item.id, sourceRevision, SHARE_CARD_STYLE_VERSION, buildShowcaseShareSource(item))
    : "";
  if (entry && typeof entry === "object") {
    const sameSource = String(entry.sourceRevision || "") === sourceRevision;
    const sameSnapshot = !snapshot || (
      snapshot.url === entry.url
      && snapshot.fingerprint === entry.fingerprint
      && String(snapshot.styleId || "") === SHARE_CARD_STYLE_VERSION
      && String(snapshot.fingerprint || "") === expectedFingerprint
    );
    return sameSource && sameSnapshot && isShareImageUrl(entry.url) ? entry.url : "";
  }
  return entry && snapshot && snapshot.url === entry
    && String(snapshot.sourceRevision || "") === sourceRevision
    && String(snapshot.styleId || "") === SHARE_CARD_STYLE_VERSION
    && String(snapshot.fingerprint || "") === expectedFingerprint
    && isShareImageUrl(entry)
    ? entry
    : "";
}

function showcaseCacheKey(userId, mode) {
  const app = getApp();
  const globalData = (app && app.globalData) || {};
  const scope = [globalData.environmentName, globalData.apiBaseUrl, globalData.apiRoutePrefix]
    .join("|")
    .replace(/[^a-zA-Z0-9_.:-]/g, "_");
  return `teambuy_showcases_v2_${scope}_${userId || "guest"}_${mode || "notes"}`;
}

function readShowcaseCache(userId, mode) {
  try {
    const cached = wx.getStorageSync(showcaseCacheKey(userId, mode));
    if (!cached || !Array.isArray(cached.items)) return null;
    return cached;
  } catch (error) {
    return null;
  }
}

function writeShowcaseCache(userId, mode, items) {
  try {
    wx.setStorageSync(showcaseCacheKey(userId, mode), {
      items: Array.isArray(items) ? items : [],
      updatedAt: Date.now()
    });
  } catch (error) {}
}

function statusText(status) {
  if (status === "published") return "已发布";
  if (status === "archived") return "已下架";
  return "草稿";
}

function showcaseMatchesMode(item = {}, mode = "notes") {
  const display = item.displayConfig || {};
  const category = display.activeCategory || "";
  const itemTypes = (item.items || []).map((row) => row.cardType || "");
  const hasProperty = category === "房源" || category === "房产" || itemTypes.includes("property_listing");
  const hasGroupbuy = category === "团购" || category === "商品" || itemTypes.includes("groupbuy_product");
  const hasService = category === "服务" || itemTypes.includes("business_card") || itemTypes.includes("service_offer");
  if (mode === "property") return hasProperty;
  if (mode === "groupbuy") return hasGroupbuy;
  if (mode === "service") return hasService;
  return !hasProperty && !hasGroupbuy && !hasService;
}

function showcasePurpose(item = {}, summary = {}) {
  const display = item.displayConfig || {};
  const category = display.activeCategory || "";
  const itemTypes = (item.items || []).map((row) => row.cardType || "");
  const text = `${item.name || ""} ${item.description || ""} ${category}`;
  if (/对比|比较|同价|相似/.test(text)) {
    return { text: "对比包", tone: "compare", hint: "适合发给正在比较的客户" };
  }
  if (category === "团购" || category === "商品" || itemTypes.includes("groupbuy_product")) {
    return { text: "商品包", tone: "product", hint: "适合发群、收接龙和看买家" };
  }
  if (category === "服务" || itemTypes.includes("business_card") || itemTypes.includes("service_offer")) {
    return { text: "方案包", tone: "service", hint: "适合发给正在了解服务的客户" };
  }
  if (category === "房源" || category === "房产" || itemTypes.includes("property_listing")) {
    return { text: "推荐包", tone: "property", hint: "适合发给第一次了解或想对比的客户" };
  }
  if ((summary.pv || 0) > 3 && !(summary.consultClickCount || 0)) {
    return { text: "复访包", tone: "compare", hint: "打开多咨询少，适合补重点说明" };
  }
  return { text: "资料包", tone: "notes", hint: "适合把相关资料一次发给客户" };
}

function showcaseType(item = {}) {
  const display = item.displayConfig || {};
  const category = display.activeCategory || "";
  const itemTypes = (item.items || []).map((row) => row.cardType || "");
  if (category === "房源" || category === "房产" || itemTypes.includes("property_listing")) {
    return { key: "property", label: "房源合集", tone: "blue" };
  }
  if (category === "团购" || category === "商品" || itemTypes.includes("groupbuy_product")) {
    return { key: "groupbuy", label: "商品合集", tone: "orange" };
  }
  if (category === "服务" || itemTypes.includes("business_card") || itemTypes.includes("service_offer")) {
    return { key: "service", label: "服务合集", tone: "purple" };
  }
  return { key: "notes", label: "资料合集", tone: "green" };
}

function decorateShowcase(item) {
  const analytics = item.analytics || {};
  const summary = analytics.summary || {};
  const firstItemCover = ((item.items || []).find((row) => row && row.coverUrl) || {}).coverUrl || "";
  const pv = summary.pv || 0;
  const uv = summary.uv || 0;
  const consult = summary.consultClickCount || 0;
  const shareCount = summary.shareCount || 0;
  const type = showcaseType(item);
  const deliveryStatus = item.status !== "published"
    ? { text: "草稿待发", tone: "idle", hint: "发布后即可发客户并追踪反馈" }
    : consult
      ? { text: `建议跟进 ${consult}`, tone: "hot", hint: "客户有咨询动作，去雷达看详情" }
      : uv
        ? { text: uv > 1 || pv > 2 ? "客户重复查看" : "客户已打开", tone: uv > 1 || pv > 2 ? "warm" : "view", hint: uv > 1 || pv > 2 ? "适合补一个对比或预约入口" : "继续观察客户动作" }
        : { text: "等待客户打开", tone: "idle", hint: "发出后客户反馈会进入雷达" };
  const recentViewers = (analytics.recentViewers || []).map((viewer) => ({
    ...viewer,
    avatarUrl: safeAvatarUrl(viewer.avatarUrl),
    avatarText: avatarText(viewer.nickname)
  }));
  return {
    ...item,
    initial: String(item.name || "展").slice(0, 1),
    titleCover: buildTitleCoverData(item.name || item.shareTitle || "合集", "合集"),
    shareCoverUrl: firstItemCover || item.bannerUrl,
    statusText: statusText(item.status),
    descText: item.description || "还没有填写简介",
    itemCountText: `${item.itemCount || (item.items || []).length || 0} 条资料`,
    createdText: item.createdAt ? `创建于 ${formatTime(item.createdAt)}` : "",
    shareTitle: item.shareTitle || item.name || "合集",
    analytics: {
      ...analytics,
      recentViewers
    },
    deliveryStatus,
    type,
    purpose: showcasePurpose(item, summary),
    hasFeedback: Boolean(pv || uv || summary.noteClickCount || consult),
    effectText: shareCount
      ? `发送 ${shareCount} 次 · 打开 ${pv}${uv ? ` · 访客 ${uv}` : ""}`
      : pv
        ? `打开 ${pv}${uv ? ` · 访客 ${uv}` : ""}`
        : item.status === "published"
          ? "还没有客户打开"
          : item.status === "archived"
            ? "已下架，客户无法继续打开"
            : "发布后才能发给客户"
  };
}

function findLatestPublished(showcases = []) {
  return showcases.find((item) => item.status === "published") || null;
}

function parseShowcaseActivityTimestamp(value) {
  const parsed = typeof value === "number" ? value : Date.parse(String(value || ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function getShowcaseActivityTimestamp(item = {}) {
  const summary = ((item.analytics || {}).summary) || {};
  return Math.max(
    parseShowcaseActivityTimestamp(summary.latestShareAt),
    parseShowcaseActivityTimestamp(item.updatedAt),
    parseShowcaseActivityTimestamp(item.createdAt)
  );
}

function sortShowcases(items = []) {
  return items.slice().sort((a, b) => {
    const activityDiff = getShowcaseActivityTimestamp(b) - getShowcaseActivityTimestamp(a);
    if (activityDiff) return activityDiff;
    const sameStyleRank = Number(Boolean(b.isSameStyle)) - Number(Boolean(a.isSameStyle));
    if (sameStyleRank) return sameStyleRank;
    const left = a.isSameStyle ? a.sameStyleGeneratedAt : (a.updatedAt || a.createdAt || "");
    const right = b.isSameStyle ? b.sameStyleGeneratedAt : (b.updatedAt || b.createdAt || "");
    return String(right).localeCompare(String(left));
  });
}

function filterShowcases(items = [], options = {}) {
  const quick = options.quick || "recent";
  const status = options.status || "all";
  const type = options.type || "all";
  const keyword = String(options.keyword || "").trim().toLowerCase();
  return items.filter((item) => {
    const summary = ((item.analytics || {}).summary) || {};
    const matchQuick = quick === "draft"
      ? item.status === "draft"
      : quick === "frequent"
        ? Number(summary.shareCount || 0) >= 2
        : quick === "feedback"
          ? Boolean(summary.pv || summary.uv || summary.noteClickCount || summary.consultClickCount)
          : true;
    const matchStatus = status === "all" || item.status === status;
    const matchType = type === "all" || ((item.type || showcaseType(item)).key === type);
    const haystack = `${item.name || ""} ${item.description || ""} ${(item.type || {}).label || ""}`.toLowerCase();
    return matchQuick && matchStatus && matchType && (!keyword || haystack.includes(keyword));
  }).sort((a, b) => {
    if (quick === "frequent") {
      const diff = Number((((b.analytics || {}).summary) || {}).shareCount || 0) - Number((((a.analytics || {}).summary) || {}).shareCount || 0);
      if (diff) return diff;
    }
    if (quick === "feedback") {
      const score = (row) => {
        const summary = ((row.analytics || {}).summary) || {};
        return Number(summary.consultClickCount || 0) * 5 + Number(summary.noteClickCount || 0) * 2 + Number(summary.pv || 0);
      };
      const diff = score(b) - score(a);
      if (diff) return diff;
    }
    return getShowcaseActivityTimestamp(b) - getShowcaseActivityTimestamp(a);
  });
}

Page({
  data: {
    user: null,
    allShowcases: [],
    showcases: [],
    showcaseShareImages: {},
    latestPublished: null,
    loading: true,
    refreshing: false,
    expandedAnalyticsId: "",
    pendingShare: null,
    openingSharedShowcase: false,
    loadError: false,
    keyword: "",
    filterPanelVisible: false,
    activeStatusFilter: "all",
    activeTypeFilter: "all",
    mode: "notes",
    modeName: "日常资料",
    collectionCopy: collectionCopyForMode("notes"),
    directionCards: COLLECTION_DIRECTIONS.notes,
    showcaseFilters: SHOWCASE_FILTERS,
    statusFilters: SHOWCASE_STATUS_FILTERS,
    typeFilters: SHOWCASE_TYPE_FILTERS,
    activeShowcaseFilter: "recent"
    ,selectMode: false
    ,pendingNoteId: ""
    ,requestedMode: ""
  },
  onLoad(options) {
    if (options && options.select === "1") {
      this.setData({ selectMode: true, pendingNoteId: options.noteId || "", requestedMode: options.scene || "" });
      if (options.scene) this.setData({ mode: options.scene });
    }
    if (options && options.shareTarget === "showcase" && (options.showcaseId || options.id)) {
      this.openSharedShowcase(options);
    }
  },
  onShow() {
    setShareMenuEnabled(false);
    if (this.openingSharedShowcase || this.data.openingSharedShowcase) return;
    const requestSeq = (this._showcaseRequestSeq || 0) + 1;
    this._showcaseRequestSeq = requestSeq;
    const user = getCurrentUser();
    if (!user) {
      this.setData({
        user: null,
        allShowcases: [],
        showcases: [],
        latestPublished: null,
        showcaseShareImages: {},
        pendingShare: null,
        loading: false,
        refreshing: false,
        loadError: false,
        expandedAnalyticsId: "",
        mode: "notes",
        modeName: "日常资料",
        collectionCopy: collectionCopyForMode("notes"),
        directionCards: COLLECTION_DIRECTIONS.notes,
        selectMode: false,
        pendingNoteId: "",
        requestedMode: ""
      });
      return;
    }
    const mode = (this.data.selectMode && this.data.requestedMode) || readWorkspaceMode(user.id) || "notes";
    const modeConfig = getModeConfig(mode);
    this.setData({
      user,
      mode,
      modeName: modeConfig.shortName || modeConfig.name,
      collectionCopy: collectionCopyForMode(mode),
      directionCards: COLLECTION_DIRECTIONS[mode] || COLLECTION_DIRECTIONS.notes
    });
    const forceReload = Boolean(this.shouldForceReload);
    this.shouldForceReload = false;
    this.loadShowcases({ force: forceReload, requestSeq });
  },
  async loadShowcases(options = {}) {
    const { user, mode } = this.data;
    if (!user) return;
    const requestSeq = options.requestSeq || this._showcaseRequestSeq || 0;
    const ownerUserId = user.id;
    const isCurrentRequest = () => requestSeq === this._showcaseRequestSeq
      && (getCurrentUser() || {}).id === ownerUserId;
    if (!isCurrentRequest()) return;
    const cached = options.force ? null : readShowcaseCache(user.id, mode);
    const hasCached = cached && Array.isArray(cached.items);
    const hasFreshCache = cached && Date.now() - Number(cached.updatedAt || 0) < SHOWCASE_CACHE_TTL;
    if (hasCached && isCurrentRequest()) {
      const allShowcases = sortShowcases(cached.items).map(decorateShowcase);
      const showcases = this.filterVisibleShowcases(allShowcases);
      this.setData({
        allShowcases,
        showcases: this.withShowcaseShareState(showcases),
        latestPublished: findLatestPublished(allShowcases),
        loading: false,
        loadError: false,
        refreshing: !hasFreshCache
      });
      // Warm only the first few visible no-cover collections in the
      // background. List rendering never waits for Canvas or upload, while a
      // later share tap can usually reuse the ready snapshot.
      this.prepareShowcaseShareImages(showcases.slice(0, 3));
    } else {
      this.setData({ loading: true, loadError: false, refreshing: false });
    }
    if (hasFreshCache && !options.force) return;
    try {
      const res = await api.fetchShowcases(user.id, { force: Boolean(options.force) });
      if (!isCurrentRequest()) return;
      const rawItems = sortShowcases(res.data || []);
      const allShowcases = rawItems.map(decorateShowcase);
      const showcases = this.filterVisibleShowcases(allShowcases);
      writeShowcaseCache(user.id, mode, rawItems);
      this.setData({
        allShowcases,
        showcases: this.withShowcaseShareState(showcases),
        latestPublished: findLatestPublished(allShowcases),
        loadError: false
      });
      this.prepareShowcaseShareImages(showcases.slice(0, 3));
    } catch (error) {
      if (!isCurrentRequest()) return;
      if (!cached || !cached.items.length) {
        this.setData({ loadError: true });
        wx.showToast({ title: error.detail || "合集加载失败", icon: "none" });
      }
    } finally {
      if (!isCurrentRequest()) return;
      this.setData({ loading: false, refreshing: false });
    }
  },
  filterVisibleShowcases(items = this.data.allShowcases || []) {
    const filtered = filterShowcases(items, {
      quick: this.data.activeShowcaseFilter,
      status: this.data.activeStatusFilter,
      type: this.data.activeTypeFilter,
      keyword: this.data.keyword
    });
    if (!this.data.selectMode || !this.data.requestedMode) return filtered;
    return filtered.filter((item) => {
      const scene = item.sceneType || ((item.type || {}).key) || "notes";
      return scene === this.data.requestedMode || showcaseMatchesMode(item, this.data.requestedMode);
    });
  },
  refreshVisibleShowcases() {
    const showcases = this.filterVisibleShowcases();
    this.setData({ showcases: this.withShowcaseShareState(showcases) });
  },
  handleShowcaseFilter(event) {
    const activeShowcaseFilter = event.currentTarget.dataset.key || "recent";
    this.setData({ activeShowcaseFilter }, () => this.refreshVisibleShowcases());
  },
  handleKeywordChange(event) {
    this.setData({ keyword: event.detail.value || "" });
  },
  handleSearch() {
    this.refreshVisibleShowcases();
  },
  handleToggleFilterPanel() {
    this.setData({ filterPanelVisible: !this.data.filterPanelVisible });
  },
  handleCloseFilterPanel() {
    this.setData({ filterPanelVisible: false });
  },
  handleStatusFilter(event) {
    this.setData({ activeStatusFilter: event.currentTarget.dataset.key || "all" }, () => this.refreshVisibleShowcases());
  },
  handleTypeFilter(event) {
    this.setData({ activeTypeFilter: event.currentTarget.dataset.key || "all" }, () => this.refreshVisibleShowcases());
  },
  handleResetFilters() {
    this.setData({
      keyword: "",
      activeShowcaseFilter: "recent",
      activeStatusFilter: "all",
      activeTypeFilter: "all"
    }, () => this.refreshVisibleShowcases());
  },
  handleRetry() {
    this.loadShowcases({ force: true });
  },
  handleGoLibrary() {
    wx.switchTab({ url: "/pages/library/index" });
  },
  handleBottomTab(event) {
    const path = event.currentTarget.dataset.path;
    if (!path) return;
    wx.switchTab({ url: path });
  },
  handleOpenShowcaseOperations(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/subpackages/workbench/resource-analytics/index?entityType=showcase&showcaseId=${encodeURIComponent(id)}` });
  },
  noop() {},
  openSharedShowcase(options = {}) {
    const showcaseId = options.showcaseId || options.id || "";
    if (!showcaseId) {
      wx.showToast({ title: "合集链接缺少编号", icon: "none" });
      return;
    }
    this.openingSharedShowcase = true;
    this.setData({ openingSharedShowcase: true });
    const query = [
      `id=${encodeURIComponent(showcaseId)}`,
      `showcaseId=${encodeURIComponent(showcaseId)}`,
      options.sid ? `sid=${encodeURIComponent(options.sid)}` : "",
      options.from ? `from=${encodeURIComponent(options.from)}` : "",
      options.src ? `src=${encodeURIComponent(options.src)}` : "",
      options.ref ? `ref=${encodeURIComponent(options.ref)}` : ""
    ].filter(Boolean).join("&");
    wx.redirectTo({
      url: `/pages/showcase-view/index?${query}`,
      fail: () => {
        wx.navigateTo({
          url: `/pages/showcase-view/index?${query}`,
          fail: () => {
            this.openingSharedShowcase = false;
            this.setData({ openingSharedShowcase: false });
            wx.showToast({ title: "合集打开失败", icon: "none" });
          }
        });
      }
    });
  },
  handleCreate() {
    const note = this.data.pendingNoteId ? `&noteId=${encodeURIComponent(this.data.pendingNoteId)}` : "";
    const targetUrl = `/subpackages/workbench/showcase-edit/index?mode=${this.data.mode}${note}`;
    const user = getCurrentUser();
    if (!user || !user.id) {
      wx.navigateTo({ url: `/pages/login/index?returnUrl=${encodeURIComponent(targetUrl)}` });
      return;
    }
    this.shouldForceReload = true;
    wx.navigateTo({ url: targetUrl });
  },
  handleSelectShowcase(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    if (!this.data.selectMode) {
      const item = (this.data.allShowcases || []).find((row) => row.id === id) || {};
      if (item.status === "draft") this.handleEdit(event);
      else this.handlePreview(event);
      return;
    }
    if (!this.data.pendingNoteId) {
      this.handleEdit(event);
      return;
    }
    this.shouldForceReload = true;
    wx.navigateTo({ url: `/subpackages/workbench/showcase-edit/index?id=${encodeURIComponent(id)}&addNoteId=${encodeURIComponent(this.data.pendingNoteId)}` });
  },
  handleCreateProduct() {
    wx.navigateTo({ url: "/subpackages/workbench/resource-create/index?workspaceMode=groupbuy&scene=groupbuy_product" });
  },
  handleGoServiceLibrary() {
    wx.setStorageSync("teambuy:libraryEntryFilter", {
      ts: Date.now(),
      mode: "service",
      cardType: "service_workspace",
      label: "名片/服务方案"
    });
    wx.switchTab({
      url: "/pages/library/index"
    });
  },
  handleEdit(event) {
    const id = event.currentTarget.dataset.id;
    if (this.data.selectMode) {
      this.handleSelectShowcase(event);
      return;
    }
    this.shouldForceReload = true;
    wx.navigateTo({ url: `/subpackages/workbench/showcase-edit/index?id=${id}` });
  },
  async handleRestore(event) {
    const id = event.currentTarget.dataset.id;
    const user = this.data.user;
    if (!id || !user) return;
    try {
      await api.publishShowcase(id, user.id);
      wx.showToast({ title: "已重新发布", icon: "success" });
      this.loadShowcases({ force: true });
    } catch (error) {
      wx.showToast({ title: error.detail || "重新发布失败", icon: "none" });
    }
  },
  async handleArchive(id) {
    const user = this.data.user;
    if (!id || !user) return;
    try {
      await api.archiveShowcase(id, user.id);
      wx.showToast({ title: "已下架", icon: "success" });
      this.loadShowcases({ force: true });
    } catch (error) {
      wx.showToast({ title: error.detail || "下架失败", icon: "none" });
    }
  },
  handlePreview(event) {
    const id = event.currentTarget.dataset.id;
    if (this.data.selectMode) {
      this.handleSelectShowcase(event);
      return;
    }
    wx.navigateTo({ url: `/pages/showcase-view/index?id=${id}&preview=1` });
  },
  async prepareShare(event) {
    const dataset = (event && event.currentTarget && event.currentTarget.dataset) || {};
    const item = (this.data.allShowcases || []).find((row) => row && row.id === dataset.id) || {};
    const source = buildShowcaseShareSource(item.id ? item : dataset);
    const persistedSnapshot = hasCurrentShowcaseSnapshot(item) ? getShareSnapshot("showcase", item) : null;
    const existingImage = getLocalShowcaseShareImage(item, this.data.showcaseShareImages || {}) || (persistedSnapshot && persistedSnapshot.url) || "";
    const pendingShare = {
      id: dataset.id || "",
      title: dataset.title || "合集",
      banner: dataset.banner || "",
      imageUrl: existingImage,
      sourceRevision: getShareSourceRevision("showcase", item)
    };
    this.setData({ pendingShare });
    this.updateShowcaseShareState(dataset.id, {
      shareImageReady: false,
      shareDisabled: true,
      shareStatusText: "正在准备"
    });
    if (existingImage) {
      subscription.requestViewNotificationSubscription("showcase_share");
      this.updateShowcaseShareState(dataset.id, { shareImageReady: true, shareDisabled: false, shareStatusText: "发客户" });
      return;
    }
    try {
      const snapshotSource = buildShowcaseShareSource(item.id ? item : pendingShare);
      const fingerprint = createShareSnapshotFingerprint("showcase", item.id || pendingShare.id, getShareSourceRevision("showcase", item), SHARE_CARD_STYLE_VERSION, snapshotSource);
      const result = await ensureShareSnapshot({
        entityType: "showcase",
        entity: item,
        ownerUserId: (this.data.user || getCurrentUser() || {}).id,
        styleId: SHARE_CARD_STYLE_VERSION,
        fingerprint,
        generate: () => renderShareCard({ page: this, canvasId: SHOWCASE_SHARE_CANVAS_ID, source: snapshotSource, variant: "resource", upload: true, ownerUserId: (this.data.user || getCurrentUser() || {}).id })
      });
      const imagePath = result.snapshot.url;
      if (imagePath && this.data.pendingShare && this.data.pendingShare.id === pendingShare.id) {
        this.setData({
          showcaseShareImages: {
            ...(this.data.showcaseShareImages || {}),
            [pendingShare.id]: {
              url: imagePath,
              sourceRevision: getShareSourceRevision("showcase", item),
              fingerprint
            }
          },
          pendingShare: {
            ...this.data.pendingShare,
            imageUrl: imagePath
          }
        });
        this.updateShowcaseShareState(pendingShare.id, { shareSnapshot: result.entity.shareSnapshot });
        this.updateShowcaseShareState(pendingShare.id, {
          shareImageReady: true,
          shareDisabled: false,
          shareStatusText: "发客户"
        });
      } else {
        this.updateShowcaseShareState(pendingShare.id, {
          shareImageReady: false,
          shareDisabled: false,
          shareStatusText: "重新准备"
        });
      }
    } catch (error) {
      this.updateShowcaseShareState(pendingShare.id, {
        shareImageReady: false,
        shareDisabled: false,
        shareStatusText: "重新准备"
      });
    }
  },
  updateShowcaseShareState(id, patch = {}) {
    if (!id) return;
    const update = (row) => row && row.id === id ? { ...row, ...patch } : row;
    this.setData({
      allShowcases: (this.data.allShowcases || []).map(update),
      showcases: (this.data.showcases || []).map(update)
    });
  },
  withShowcaseShareState(items = []) {
    const images = this.data.showcaseShareImages || {};
    return (items || []).map((item) => {
      const snapshot = hasCurrentShowcaseSnapshot(item) ? getShareSnapshot("showcase", item) : null;
      const source = buildShowcaseShareSource(item);
      const ready = Boolean(getLocalShowcaseShareImage(item, images) || (snapshot && snapshot.url));
      return {
        ...item,
        shareImageReady: ready,
        shareDisabled: false,
        shareStatusText: item.status === "published" ? (ready ? "发客户" : "准备发送") : item.status === "archived" ? "重新发布" : "继续编辑"
      };
    });
  },
  async prepareShowcaseShareImages(items = []) {
    const pending = (items || []).filter((item) => item && item.status === "published" && item.id && !hasCurrentShowcaseSnapshot(item));
    if (!pending.length) return;
    this.showcaseShareGenerating = this.showcaseShareGenerating || {};
    for (const item of pending) {
      if (this.showcaseShareGenerating[item.id]) continue;
      this.showcaseShareGenerating[item.id] = true;
      this.updateShowcaseShareState(item.id, {
        shareImageReady: false,
        shareDisabled: true,
        shareStatusText: "正在准备"
      });
      try {
        const source = buildShowcaseShareSource(item);
        const fingerprint = createShareSnapshotFingerprint("showcase", item.id, getShareSourceRevision("showcase", item), SHARE_CARD_STYLE_VERSION, source);
        const result = await ensureShareSnapshot({
          entityType: "showcase",
          entity: item,
          ownerUserId: (this.data.user || getCurrentUser() || {}).id,
          styleId: SHARE_CARD_STYLE_VERSION,
          fingerprint,
          generate: () => renderShareCard({ page: this, canvasId: SHOWCASE_SHARE_CANVAS_ID, source, variant: "resource", upload: true, ownerUserId: (this.data.user || getCurrentUser() || {}).id })
        });
        const imagePath = result.snapshot.url;
        if (imagePath) {
          const showcaseShareImages = {
            ...(this.data.showcaseShareImages || {}),
            [item.id]: {
              url: imagePath,
              sourceRevision: getShareSourceRevision("showcase", item),
              fingerprint
            }
          };
          this.setData({
            showcaseShareImages,
            allShowcases: this.withShowcaseShareState((this.data.allShowcases || []).map((row) => row.id === item.id ? { ...row, shareSnapshot: result.entity.shareSnapshot } : row)),
            showcases: this.withShowcaseShareState((this.data.showcases || []).map((row) => row.id === item.id ? { ...row, shareSnapshot: result.entity.shareSnapshot } : row))
          });
        }
      } catch (error) {
        const markFailed = (row) => row && row.id === item.id
          ? { ...row, shareImageReady: false, shareDisabled: false, shareStatusText: "重新准备" }
          : row;
        this.setData({
          allShowcases: (this.data.allShowcases || []).map(markFailed),
          showcases: (this.data.showcases || []).map(markFailed)
        });
      } finally {
        this.showcaseShareGenerating[item.id] = false;
      }
    }
  },
  markShowcaseShared(id) {
    if (!id) return;
    const updateItem = (item) => {
      if (!item || item.id !== id) return item;
      const summary = {
        ...(((item.analytics || {}).summary) || {}),
        shareCount: Number((((item.analytics || {}).summary) || {}).shareCount || 0) + 1,
        latestShareAt: new Date().toISOString()
      };
      return {
        ...item,
        analytics: {
          ...(item.analytics || {}),
          summary
        },
        effectText: `发送 ${summary.shareCount} 次 · 打开 ${Number(summary.pv || 0)}${Number(summary.uv || 0) ? ` · 访客 ${Number(summary.uv || 0)}` : ""}`,
        deliveryStatus: {
          text: "已发出，等待打开",
          tone: "sent",
          hint: "客户打开后会进入雷达"
        }
      };
    };
    const allShowcases = sortShowcases((this.data.allShowcases || []).map(updateItem));
    const user = this.data.user || getCurrentUser();
    const mode = this.data.mode || "notes";
    const cached = user && readShowcaseCache(user.id, mode);
    if (user && cached && Array.isArray(cached.items)) {
      writeShowcaseCache(user.id, mode, sortShowcases(cached.items.map(updateItem)));
    }
    this.setData({
      allShowcases,
      showcases: this.withShowcaseShareState(this.filterVisibleShowcases(allShowcases)),
      latestPublished: findLatestPublished(allShowcases)
    });
  },
  handleMore(event) {
    const id = event.currentTarget.dataset.id;
    const status = event.currentTarget.dataset.status;
    if (!id) return;
    // 发客户是卡片唯一主动作；更多菜单只承接反馈、编辑和生命周期管理。
    // 已发布卡片本身可直接进入客户页，因此不再重复放“效果/预览”两个同义入口。
    const itemList = status === "published"
      ? ["资料运营", "编辑", "停止分享", "删除"]
      : status === "archived"
        ? ["资料运营", "编辑", "预览", "重新发布", "删除"]
        : ["继续编辑", "预览", "删除"];
    wx.showActionSheet({
      itemList,
      success: ({ tapIndex }) => {
        const action = itemList[tapIndex];
        if (action === "资料运营") {
          wx.navigateTo({ url: `/subpackages/workbench/resource-analytics/index?entityType=showcase&showcaseId=${encodeURIComponent(id)}` });
          return;
        }
        if (action === "编辑" || action === "继续编辑") {
          this.shouldForceReload = true;
          wx.navigateTo({ url: `/subpackages/workbench/showcase-edit/index?id=${id}` });
          return;
        }
        if (action === "预览") {
          wx.navigateTo({ url: `/pages/showcase-view/index?id=${id}&preview=1` });
          return;
        }
        if (action === "停止分享") {
          this.handleArchive(id);
          return;
        }
        if (action === "重新发布") {
          this.handleRestore({ currentTarget: { dataset: { id } } });
          return;
        }
        if (action === "删除") {
          this.confirmDelete(id);
        }
      }
    });
  },
  toggleAnalytics(id) {
    this.setData({ expandedAnalyticsId: this.data.expandedAnalyticsId === id ? "" : id });
  },
  handleOpenNoteActions(event) {
    const noteId = event.currentTarget.dataset.noteId;
    if (!noteId) return;
    wx.navigateTo({ url: `/subpackages/workbench/note-actions/index?id=${noteId}` });
  },
  handleDelete(event) {
    const id = event.currentTarget.dataset.id;
    this.confirmDelete(id);
  },
  confirmDelete(id) {
    const { user } = this.data;
    if (!id || !user) return;
    wx.showModal({
      title: "删除合集",
      content: "删除后客户将无法再打开这个合集，确认删除吗？",
      confirmColor: "#e5484d",
      success: async ({ confirm }) => {
        if (!confirm) return;
        try {
          await api.deleteShowcase(id, user.id);
          wx.showToast({ title: "已删除", icon: "success" });
          this.loadShowcases({ force: true });
        } catch (error) {
          wx.showToast({ title: error.detail || "删除失败", icon: "none" });
        }
      }
    });
  },
  onShareAppMessage(options) {
    const dataset = options && options.target && options.target.dataset ? options.target.dataset : {};
    const pending = this.data.pendingShare || {};
    const id = dataset.id || pending.id || "";
    const title = dataset.title || pending.title || "合集";
    const row = (this.data.allShowcases || []).find((item) => item && item.id === id) || {};
    const persistedSnapshot = hasCurrentShowcaseSnapshot(row) ? getShareSnapshot("showcase", row) : null;
    const pendingImage = pending.sourceRevision === getShareSourceRevision("showcase", row) ? pending.imageUrl : "";
    const imageUrl = pendingImage || getLocalShowcaseShareImage(row, this.data.showcaseShareImages || {}) || (persistedSnapshot && persistedSnapshot.url) || "";
    const user = this.data.user || getCurrentUser();
    if (!id) {
      wx.showToast({ title: "请重新点击发给客户", icon: "none" });
      setShareMenuEnabled(false);
      return null;
    }
    if (!isShareImageUrl(imageUrl)) {
      wx.showToast({ title: "分享内容正在准备，请稍后再发", icon: "none" });
      setShareMenuEnabled(false);
      return null;
    }
    const shareId = createShareId(id);
    if (id && user) {
      api.recordShowcaseEvent(id, {
        eventType: "share",
        shareId,
        shareFromUserId: user.id,
        scene: "showcase_list_share",
        referrer: "showcases"
      }).catch(() => {});
    }
    this.markShowcaseShared(id);
    wx.showToast({ title: "已生成可追踪合集", icon: "none" });
    return {
      title: buildCustomerShareTitle(title),
      path: `/pages/showcase-view/index?id=${encodeURIComponent(id)}&showcaseId=${encodeURIComponent(id)}&sid=${encodeURIComponent(shareId)}&from=${encodeURIComponent(user ? user.id : "")}&src=showcase_list_share`,
      imageUrl
    };
  }
});
