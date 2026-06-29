const api = require("../../services/api");
const { avatarText, formatTime, getCurrentUser, safeAvatarUrl } = require("../../utils/dashboard");
const { generateTitleShareImage } = require("../../utils/business-card-share");
const { getModeConfig, readWorkspaceMode } = require("../../utils/workspace-mode");
const { buildTitleCoverData } = require("../../utils/title-cover");

const SHOWCASE_CACHE_TTL = 5 * 60 * 1000;
const SHOWCASE_SHARE_CANVAS_ID = "showcaseListShareCanvas";
const RADAR_ENTRY_TAB_KEY = "teambuy:radarEntryTab";
const RADAR_SOURCE_FILTER_KEY = "teambuy:radarSourceFilter";
const SHOWCASE_FILTERS = [
  { key: "all", label: "全部" },
  { key: "draft", label: "草稿" },
  { key: "published", label: "已发布" },
  { key: "feedback", label: "有反馈" }
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

function showcaseCacheKey(userId, mode) {
  return `teambuy_showcases_${userId || "guest"}_${mode || "notes"}`;
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

function decorateShowcase(item) {
  const analytics = item.analytics || {};
  const summary = analytics.summary || {};
  const firstItemCover = ((item.items || []).find((row) => row && row.coverUrl) || {}).coverUrl || "";
  const pv = summary.pv || 0;
  const uv = summary.uv || 0;
  const consult = summary.consultClickCount || 0;
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
    purpose: showcasePurpose(item, summary),
    effectText: `打开 ${pv} · 访客 ${uv} · 咨询 ${consult}`
  };
}

function findLatestPublished(showcases = []) {
  return showcases.find((item) => item.status === "published") || null;
}

function sortShowcases(items = []) {
  return items.slice().sort((a, b) => String(b.updatedAt || b.createdAt || "").localeCompare(String(a.updatedAt || a.createdAt || "")));
}

function filterShowcases(items = [], filter = "all") {
  if (filter === "draft") return items.filter((item) => item.status !== "published");
  if (filter === "published") return items.filter((item) => item.status === "published");
  if (filter === "feedback") {
    return items.filter((item) => {
      const summary = ((item.analytics || {}).summary) || {};
      return (summary.pv || 0) || (summary.uv || 0) || (summary.consultClickCount || 0);
    });
  }
  return items;
}

Page({
  data: {
    user: null,
    allShowcases: [],
    showcases: [],
    latestPublished: null,
    loading: false,
    refreshing: false,
    expandedAnalyticsId: "",
    pendingShare: null,
    openingSharedShowcase: false,
    mode: "notes",
    modeName: "日常资料",
    collectionCopy: collectionCopyForMode("notes"),
    directionCards: COLLECTION_DIRECTIONS.notes,
    showcaseFilters: SHOWCASE_FILTERS,
    activeShowcaseFilter: "all"
  },
  onLoad(options) {
    if (options && options.shareTarget === "showcase" && (options.showcaseId || options.id)) {
      this.openSharedShowcase(options);
    }
  },
  onShow() {
    if (this.openingSharedShowcase || this.data.openingSharedShowcase) return;
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const mode = readWorkspaceMode(user.id) || "notes";
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
    this.loadShowcases({ force: forceReload });
  },
  async loadShowcases(options = {}) {
    const { user, mode } = this.data;
    if (!user) return;
    const cached = options.force ? null : readShowcaseCache(user.id, mode);
    const hasCached = cached && Array.isArray(cached.items);
    const hasFreshCache = cached && Date.now() - Number(cached.updatedAt || 0) < SHOWCASE_CACHE_TTL;
    if (hasCached) {
      const allShowcases = sortShowcases(cached.items.filter((item) => showcaseMatchesMode(item, mode))).map(decorateShowcase);
      const showcases = filterShowcases(allShowcases, this.data.activeShowcaseFilter);
      this.setData({
        allShowcases,
        showcases,
        latestPublished: findLatestPublished(allShowcases),
        loading: false,
        refreshing: !hasFreshCache
      });
    } else {
      this.setData({ loading: true, refreshing: false });
    }
    if (hasFreshCache && !options.force) return;
    try {
      const res = await api.fetchShowcases(user.id);
      const rawItems = sortShowcases((res.data || []).filter((item) => showcaseMatchesMode(item, mode)));
      const allShowcases = rawItems.map(decorateShowcase);
      const showcases = filterShowcases(allShowcases, this.data.activeShowcaseFilter);
      writeShowcaseCache(user.id, mode, rawItems);
      this.setData({
        allShowcases,
        showcases,
        latestPublished: findLatestPublished(allShowcases)
      });
    } catch (error) {
      if (!cached || !cached.items.length) {
        wx.showToast({ title: error.detail || "合集加载失败", icon: "none" });
      }
    } finally {
      this.setData({ loading: false, refreshing: false });
    }
  },
  handleShowcaseFilter(event) {
    const activeShowcaseFilter = event.currentTarget.dataset.key || "all";
    this.setData({
      activeShowcaseFilter,
      showcases: filterShowcases(this.data.allShowcases || [], activeShowcaseFilter)
    });
  },
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
    this.shouldForceReload = true;
    wx.navigateTo({ url: `/pages/showcase-edit/index?mode=${this.data.mode}` });
  },
  handleCreateProduct() {
    wx.navigateTo({ url: "/pages/resource-create/index?workspaceMode=groupbuy&scene=groupbuy_product" });
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
    this.shouldForceReload = true;
    wx.navigateTo({ url: `/pages/showcase-edit/index?id=${id}` });
  },
  handlePreview(event) {
    const id = event.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/showcase-view/index?id=${id}&preview=1` });
  },
  async prepareShare(event) {
    const dataset = (event && event.currentTarget && event.currentTarget.dataset) || {};
    const pendingShare = {
      id: dataset.id || "",
      title: dataset.title || "合集",
      banner: dataset.banner || "",
      imageUrl: ""
    };
    this.setData({ pendingShare });
    try {
      const imagePath = await generateTitleShareImage(this, SHOWCASE_SHARE_CANVAS_ID, {
        title: pendingShare.title,
        badge: "合集",
        coverUrl: pendingShare.banner,
        hint: "打开小程序查看完整合集",
        growthHint: "我也想做同款",
        shareTargetLabel: "合集"
      });
      if (imagePath && this.data.pendingShare && this.data.pendingShare.id === pendingShare.id) {
        this.setData({
          pendingShare: {
            ...this.data.pendingShare,
            imageUrl: imagePath
          }
        });
      }
    } catch (error) {}
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
        deliveryStatus: {
          text: "已发出，等待打开",
          tone: "sent",
          hint: "客户打开后会进入雷达"
        }
      };
    };
    const allShowcases = (this.data.allShowcases || []).map(updateItem);
    this.setData({
      allShowcases,
      showcases: filterShowcases(allShowcases, this.data.activeShowcaseFilter),
      latestPublished: findLatestPublished(allShowcases)
    });
  },
  handleMore(event) {
    const id = event.currentTarget.dataset.id;
    const status = event.currentTarget.dataset.status;
    if (!id) return;
    const itemList = status === "published" ? ["雷达", "效果", "编辑", "预览", "删除"] : ["预览", "删除"];
    wx.showActionSheet({
      itemList,
      success: ({ tapIndex }) => {
        const action = itemList[tapIndex];
        if (action === "雷达") {
          const showcase = (this.data.allShowcases || []).find((item) => item.id === id) || {};
          try {
            wx.setStorageSync(RADAR_ENTRY_TAB_KEY, "followup");
            wx.setStorageSync(RADAR_SOURCE_FILTER_KEY, {
              ts: Date.now(),
              resourceId: id,
              showcaseId: id,
              title: showcase.name || "这份合集"
            });
          } catch (error) {}
          wx.switchTab({ url: "/pages/visits/index" });
          return;
        }
        if (action === "效果") {
          wx.navigateTo({ url: `/pages/showcase-analytics/index?id=${id}` });
          return;
        }
        if (action === "编辑") {
          this.shouldForceReload = true;
          wx.navigateTo({ url: `/pages/showcase-edit/index?id=${id}` });
          return;
        }
        if (action === "预览") {
          wx.navigateTo({ url: `/pages/showcase-view/index?id=${id}&preview=1` });
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
    wx.navigateTo({ url: `/pages/note-actions/index?id=${noteId}` });
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
    const imageUrl = pending.imageUrl || "";
    const user = this.data.user || getCurrentUser();
    if (!id) {
      wx.showToast({ title: "请重新点击发给客户", icon: "none" });
      return {
        title: "合集",
        path: "/pages/showcases/index"
      };
    }
    if (!imageUrl) {
      wx.showToast({ title: "封面还在生成，请稍后再发", icon: "none" });
      return {
        title: buildCustomerShareTitle(title),
        path: "/pages/showcases/index"
      };
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
      path: `/pages/showcases/index?shareTarget=showcase&showcaseId=${id}&sid=${shareId}&from=${user ? user.id : ""}&src=showcase_list_share`,
      imageUrl
    };
  }
});
