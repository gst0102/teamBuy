const api = require("../../../services/api");
const { formatTime, getCurrentUser, safeAvatarUrl, avatarText } = require("../../../utils/dashboard");
const { navigateToResourceEdit } = require("../../../utils/resource-navigation");
const { getCustomerAccessState } = require("../../../utils/customer-access");

const TREND_RANGES = ["last7", "today"];

function typeLabel(card = {}) {
  const config = card.visibilityConfig || {};
  const type = card.categoryName || config.systemCategory || config.cardType || "资料";
  if (type === "property_listing" || type === "property") return "房源资料";
  if (type === "groupbuy_product" || type === "groupbuy") return "商品资料";
  if (type === "service_offer" || type === "service") return "服务资料";
  return type || "资料";
}

function showcaseTypeLabel(showcase = {}) {
  const scene = showcase.sceneType || showcase.activeCategory || "";
  if (scene === "property" || scene === "property_listing") return "房源合集";
  if (scene === "groupbuy" || scene === "groupbuy_product") return "商品合集";
  if (scene === "service" || scene === "service_offer") return "服务合集";
  return "资料合集";
}

function statusLabel(status) {
  if (status === "published") return "已发布";
  if (status === "archived") return "已下架";
  return "草稿";
}

function formatActionTime(value) {
  return value ? formatTime(value) : "刚刚";
}

function dateLabel(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${month}-${day}`;
}

function fallbackTrend(total = 0) {
  const today = new Date();
  const last7 = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today.getTime() - (6 - index) * 24 * 60 * 60 * 1000);
    return { label: dateLabel(date), value: index === 6 ? Number(total || 0) : 0 };
  });
  const todayPoints = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]
    .map((label, index, list) => ({ label, value: index === list.length - 1 ? Number(total || 0) : 0 }));
  return { last7, today: todayPoints };
}

function normalizeTrend(trend, total) {
  const fallback = fallbackTrend(total);
  if (!trend || typeof trend !== "object") return fallback;
  const normalize = (value, fallbackRows) => {
    if (!Array.isArray(value) || !value.length) return fallbackRows;
    return value.slice(0, fallbackRows.length).map((item, index) => {
      const numericValue = Number(item && item.value);
      return {
        label: String((item && item.label) || (fallbackRows[index] && fallbackRows[index].label) || ""),
        value: Number.isFinite(numericValue) ? Math.max(0, numericValue) : 0
      };
    });
  };
  return {
    last7: normalize(trend.last7, fallback.last7),
    today: normalize(trend.today, fallback.today)
  };
}

function buildHighIntent(stats = {}, actionData = {}) {
  const viewers = Array.isArray(stats.loggedInViewers) ? stats.loggedInViewers : [];
  const viewer = viewers
    .slice()
    .sort((left, right) => Number(right.viewCount || 0) - Number(left.viewCount || 0))[0];
  if (viewer && Number(viewer.viewCount || 0) > 1) {
    return {
      nickname: viewer.nickname || "匿名客户",
      avatarUrl: safeAvatarUrl(viewer.avatarUrl),
      avatarText: avatarText(viewer.nickname || "客", "客"),
      viewText: `最近查看 ${viewer.viewCount} 次`,
      viewedAt: formatActionTime(viewer.viewedAt || viewer.lastViewedAt),
      customerId: viewer.userId || viewer.viewerUserId || "",
      leadId: ""
    };
  }
  const action = (actionData.actions || []).find((item) => item && (item.actionKey === "consult-click" || item.actionKey === "lead-contact" || item.actionKey === "appointment"));
  if (!action) return null;
  const nickname = action.customerName || action.nickname || "匿名客户";
  return {
    nickname,
    avatarUrl: safeAvatarUrl(action.customerAvatarUrl || action.avatarUrl),
    avatarText: avatarText(nickname, "客"),
    viewText: action.actionLabel || action.statusText || "最近有客户动作",
    viewedAt: formatActionTime(action.createdAt),
    customerId: action.visitorIdentityId || action.viewerUserId || action.anonymousId || "",
    leadId: action.leadReminderId || ""
  };
}

function buildSourceActions(stats = {}, actionData = {}) {
  const summary = actionData.summary || {};
  return [
    { icon: "↗", iconClass: "share", tone: "blue", value: Number(stats.shareCount || 0), label: "分享打开" },
    { icon: "", iconClass: "chat", tone: "green", value: Number(summary.consult || 0) + Number(summary.leadContact || 0), label: "点击咨询" },
    { icon: "", iconClass: "appointment", tone: "orange", value: Number(summary.appointment || 0), label: "预约" }
  ];
}

function buildStats(resource = {}, statsPayload = {}, actionData = {}) {
  const source = statsPayload && Object.keys(statsPayload).length ? statsPayload : (resource.stats || {});
  const summary = actionData.summary || {};
  return {
    totalVisits: Number(source.pv || 0),
    visitorCount: Number(source.uv || 0),
    shareCount: Number(source.shareCount || 0),
    relayCount: Number(source.relayCount || 0),
    consultCount: Number(summary.consult || 0) + Number(summary.leadContact || 0),
    appointmentCount: Number(summary.appointment || 0),
    loggedInViewers: source.loggedInViewers || []
  };
}

function drawTrend(page) {
  if (!page || !page.data) return;
  const rows = (page.data.trend && page.data.trend[page.data.trendRange]) || [];
  wx.createSelectorQuery().in(page).select(".trend-canvas").boundingClientRect((rect) => {
    if (!rect || !rect.width || !rect.height) return;
    const ctx = wx.createCanvasContext("resourceTrendCanvas", page);
    const width = rect.width;
    const height = rect.height;
    const left = 36;
    const right = 10;
    const top = 18;
    const bottom = 34;
    const chartWidth = Math.max(width - left - right, 1);
    const chartHeight = Math.max(height - top - bottom, 1);
    const values = rows.map((item) => Number(item.value || 0));
    const maxValue = Math.max(1, ...values);
    const point = (value, index) => ({
      x: left + (rows.length <= 1 ? chartWidth / 2 : chartWidth * index / (rows.length - 1)),
      y: top + chartHeight - (value / maxValue) * chartHeight
    });

    ctx.setStrokeStyle("#e1eaf5");
    ctx.setLineWidth(1);
    [0, 0.5, 1].forEach((ratio) => {
      const y = top + chartHeight * ratio;
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(width - right, y);
      ctx.stroke();
    });
    ctx.setFillStyle("#8491a5");
    ctx.setFontSize(11);
    ctx.fillText(String(maxValue), 8, top + 4);
    ctx.fillText("0", 17, top + chartHeight + 4);

    if (rows.length) {
      const points = rows.map((item, index) => point(item.value, index));
      ctx.beginPath();
      ctx.moveTo(points[0].x, top + chartHeight);
      points.forEach((item) => ctx.lineTo(item.x, item.y));
      ctx.lineTo(points[points.length - 1].x, top + chartHeight);
      ctx.closePath();
      ctx.setFillStyle("rgba(31, 120, 255, 0.14)");
      ctx.fill();
      ctx.beginPath();
      points.forEach((item, index) => index ? ctx.lineTo(item.x, item.y) : ctx.moveTo(item.x, item.y));
      ctx.setStrokeStyle("#1f78ff");
      ctx.setLineWidth(2.5);
      ctx.stroke();
      points.forEach((item) => {
        ctx.beginPath();
        ctx.arc(item.x, item.y, 4, 0, Math.PI * 2);
        ctx.setFillStyle("#ffffff");
        ctx.fill();
        ctx.setStrokeStyle("#1f78ff");
        ctx.setLineWidth(2);
        ctx.stroke();
      });
      ctx.setFillStyle("#8491a5");
      ctx.setFontSize(10);
      rows.forEach((item, index) => {
        const itemPoint = points[index];
        const label = String(item.label || "");
        ctx.fillText(label, Math.max(0, itemPoint.x - 15), height - 10);
      });
    }
    ctx.draw();
  }).exec();
}

Page({
  data: {
    entityKind: "resource",
    resourceId: "",
    entityId: "",
    noteId: "",
    ownerUserId: "",
    title: "资料运营",
    menuVisible: false,
    loading: false,
    errorText: "",
    accessState: "unknown",
    resource: {},
    coverUrl: "",
    typeLabel: "资料",
    viewLabel: "查看资料",
    editLabel: "编辑资料",
    statusText: "已发布",
    stats: {
      totalVisits: 0,
      visitorCount: 0,
      shareCount: 0,
      relayCount: 0,
      consultCount: 0,
      appointmentCount: 0
    },
    trendRange: "last7",
    trend: fallbackTrend(0),
    highIntent: null,
    sourceActions: buildSourceActions({}, {}),
    relayEnabled: true
  },

  onLoad(options = {}) {
    const entityKind = options.entityType === "showcase" || options.showcaseId ? "showcase" : "resource";
    const entityId = entityKind === "showcase"
      ? (options.showcaseId || options.id || "")
      : (options.resourceId || options.id || "");
    this.setData({
      entityKind,
      entityId,
      resourceId: entityKind === "resource" ? entityId : "",
      noteId: options.noteId || "",
      title: options.title ? decodeURIComponent(options.title) : "资料运营"
    });
  },

  onReady() {
    drawTrend(this);
  },

  onShow() {
    if (this._loaded && !this._needsRefresh) return;
    this._needsRefresh = false;
    this.loadData();
  },

  onHide() {
    this._needsRefresh = true;
  },

  async loadData() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if (!this.data.entityId || this.data.loading) return;
    this.setData({ loading: true, errorText: "", menuVisible: false });
    try {
      const membershipRes = await api.fetchMembership(user.id);
      const accessState = getCustomerAccessState((membershipRes && membershipRes.data) || {});
      if (accessState === "unknown") throw new Error("客户资料访问状态暂时无法确认");
      if (accessState === "payment_required") {
        wx.redirectTo({ url: "/pages/membership/index" });
        return;
      }

      let resource = {};
      let statsPayload = {};
      let note = {};
      let noteId = this.data.noteId || "";
      let actionData = {};
      let viewLabel = "查看资料";
      let editLabel = "编辑资料";
      if (this.data.entityKind === "showcase") {
        const showcaseRes = await api.fetchShowcase(this.data.entityId, user.id);
        const showcase = showcaseRes.data || {};
        if (showcase.ownerUserId !== user.id) throw new Error("无权查看该合集运营数据");
        resource = {
          ...showcase,
          id: showcase.id || this.data.entityId,
          title: showcase.name || "资料合集",
          coverUrl: showcase.bannerUrl || "",
          status: showcase.status || "draft",
          relayConfig: { enabled: false }
        };
        viewLabel = "查看合集";
        editLabel = "编辑合集";
        note = { visibilityConfig: { systemCategory: showcaseTypeLabel(showcase) } };
        if (accessState !== "disabled") {
          const analyticsRes = await api.fetchShowcaseAnalytics(this.data.entityId, user.id);
          const analytics = analyticsRes.data || {};
          const summary = analytics.summary || {};
          statsPayload = {
            pv: summary.pv,
            uv: summary.uv,
            shareCount: summary.shareCount,
            loggedInViewers: analytics.recentViewers || [],
            trend: analytics.trend
          };
          const recentEvents = (analytics.recentEvents || []).filter((item) => item.eventType !== "view" && item.eventType !== "share");
          actionData = {
            summary: {
              consult: Number(summary.consultClickCount || 0),
              leadContact: 0,
              appointment: 0
            },
            actions: recentEvents.map((item) => ({
              actionKey: item.eventType === "phone_click" || item.eventType === "wechat_copy" ? "consult-click" : "",
              customerName: item.nickname,
              avatarUrl: item.avatarUrl,
              viewerUserId: item.viewerUserId,
              anonymousId: item.anonymousId,
              createdAt: item.createdAt
            }))
          };
        }
      } else {
        const resourceRes = await api.fetchCard(this.data.entityId);
        resource = resourceRes.data || {};
        if (resource.ownerUserId !== user.id) throw new Error("无权查看该资料运营数据");
        const [statsRes, noteRes] = await Promise.all([
          api.fetchStats(this.data.entityId, user.id).catch(() => ({ data: {} })),
          this.data.noteId ? api.fetchNote(this.data.noteId, user.id).catch(() => ({ data: {} })) : Promise.resolve({ data: {} })
        ]);
        statsPayload = statsRes.data || {};
        note = noteRes.data || {};
        noteId = this.data.noteId || resource.sourceNoteId || "";
      }
      if (this.data.entityKind === "resource" && accessState !== "disabled" && noteId) {
        const actionRes = await api.fetchNoteCustomerActions(noteId, user.id);
        actionData = actionRes.data || {};
      }
      const stats = buildStats(resource, statsPayload, actionData);
      const type = typeLabel({
        ...resource,
        categoryName: resource.categoryName || note.visibilityConfig?.systemCategory,
        cardType: resource.cardType || note.visibilityConfig?.cardType
      });
      const coverUrl = resource.coverUrl || resource.coverDisplayUrl || resource.imageUrl || note.coverUrl || "";
      const sourceStatus = note.shareState === "published"
        ? "published"
        : resource.sourceNoteStatus || resource.status || note.status || "published";
      const title = resource.title || resource.projectName || this.data.title || "资料运营";
      const next = {
        ownerUserId: user.id,
        noteId,
        title,
        resource,
        coverUrl,
        typeLabel: type,
        viewLabel,
        editLabel,
        statusText: statusLabel(sourceStatus),
        accessState,
        stats,
        trend: normalizeTrend(statsPayload.trend, stats.totalVisits),
        highIntent: accessState === "disabled" ? null : buildHighIntent(statsPayload, actionData),
        sourceActions: buildSourceActions(statsPayload, actionData),
        relayEnabled: resource.relayConfig ? resource.relayConfig.enabled !== false : true
      };
      this._loaded = true;
      this.setData(next, () => drawTrend(this));
    } catch (error) {
      this.setData({ errorText: error.detail || error.message || "资料运营加载失败" });
    } finally {
      this.setData({ loading: false });
    }
  },

  handleRetry() {
    this._loaded = false;
    this.loadData();
  },

  handleToggleMenu() {
    this.setData({ menuVisible: !this.data.menuVisible });
  },

  noop() {},

  handleMenuAction(event) {
    const action = event.currentTarget.dataset.action;
    this.setData({ menuVisible: false });
    if (action === "view") this.handleViewResource();
    if (action === "edit") this.handleEditResource();
  },

  handleViewResource() {
    if (!this.data.entityId) return;
    const url = this.data.entityKind === "showcase"
      ? `/pages/showcase-view/index?id=${encodeURIComponent(this.data.entityId)}&preview=1`
      : `/pages/note-preview/index?id=${encodeURIComponent(this.data.noteId || this.data.entityId)}`;
    wx.navigateTo({ url });
  },

  handleOpenResource() {
    this.handleViewResource();
  },

  handleEditResource() {
    if (!this.data.resource || !this.data.resource.id) return;
    if (this.data.entityKind === "showcase") {
      wx.navigateTo({ url: `/subpackages/workbench/showcase-edit/index?id=${encodeURIComponent(this.data.entityId)}` });
      return;
    }
    navigateToResourceEdit(this.data.resource);
  },

  handleOpenCustomer() {
    const item = this.data.highIntent;
    if (!item) return;
    const params = [];
    if (item.leadId) {
      params.push(`leadId=${encodeURIComponent(item.leadId)}`);
    } else if (item.customerId) {
      params.push(`customerId=${encodeURIComponent(item.customerId)}`);
    }
    if (!params.length) {
      wx.showToast({ title: "该访客暂未建立客户档案", icon: "none" });
      return;
    }
    wx.navigateTo({ url: `/pages/customer-detail/index?${params.join("&")}` });
  },

  handleTrendRange(event) {
    const range = event.currentTarget.dataset.range;
    if (!TREND_RANGES.includes(range) || range === this.data.trendRange) return;
    this.setData({ trendRange: range }, () => drawTrend(this));
  }
});
