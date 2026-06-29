const api = require("../../services/api");
const { avatarText, getCurrentUser, safeAvatarUrl } = require("../../utils/dashboard");

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

function sceneText(value) {
  if (value === "showcase_list_share") return "展示页列表";
  if (value === "showcase_preview_share") return "预览分享";
  if (value === "public_showcase_share") return "客户转发";
  return "分享来源";
}

function shareStatusText(item) {
  if ((item.consultCount || 0) > 0) return "已有咨询";
  if ((item.noteClickCount || 0) > 0) return "看过资料";
  if ((item.openCount || 0) > 0) return "已打开";
  return "已发出";
}

function shareStatusTone(item) {
  if ((item.consultCount || 0) > 0) return "green";
  if ((item.noteClickCount || 0) > 0) return "blue";
  if ((item.openCount || 0) > 0) return "orange";
  return "gray";
}

function normalizeAnalytics(data = {}) {
  const recentEvents = (data.recentEvents || []).map((item, index) => ({
    ...item,
    avatarUrl: safeAvatarUrl(item.avatarUrl),
    avatarText: avatarText(item.nickname),
    eventInitial: avatarText(item.eventLabel),
    timeText: formatTime(item.createdAt),
    tone: index % 4
  }));
  const summary = data.summary || {};
  return {
    summary: {
      pv: summary.pv || 0,
      uv: summary.uv || 0,
      noteClickCount: summary.noteClickCount || 0,
      consultClickCount: summary.consultClickCount || 0,
      phoneClickCount: summary.phoneClickCount || 0,
      wechatCopyCount: summary.wechatCopyCount || 0,
      shareCount: summary.shareCount || 0,
      shareSourceCount: summary.shareSourceCount || 0,
      anonymousUv: summary.anonymousUv || 0
    },
    recentViewers: (data.recentViewers || []).map((item, index) => ({
      ...item,
      avatarUrl: safeAvatarUrl(item.avatarUrl),
      avatarText: avatarText(item.nickname),
      timeText: formatTime(item.lastViewedAt),
      tone: index % 4
    })),
    recentEvents,
    customerTrails: recentEvents.filter((item) => item.noteTitle || item.eventLabel).slice(0, 8),
    topNotes: (data.topNotes || []).map((item) => ({
      ...item,
      actionText: item.noteId ? "查看客户" : ""
    })),
    topShares: (data.topShares || []).map((item, index) => ({
      ...item,
      sceneText: sceneText(item.scene),
      timeText: formatTime(item.lastEventAt),
      shortId: item.shareId ? String(item.shareId).slice(-8) : `分享${index + 1}`,
      shareTitle: `第 ${index + 1} 次发给客户`,
      statusText: shareStatusText(item),
      statusTone: shareStatusTone(item)
    }))
  };
}

Page({
  data: {
    id: "",
    loading: false,
    showcase: null,
    analytics: normalizeAnalytics({})
  },
  onLoad(options) {
    this.setData({ id: options.id || "" });
  },
  onShow() {
    this.loadAnalytics();
  },
  async loadAnalytics() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if (!this.data.id) return;
    this.setData({ loading: true });
    try {
      const [showcaseRes, analyticsRes] = await Promise.all([
        api.fetchShowcase(this.data.id, user.id),
        api.fetchShowcaseAnalytics(this.data.id, user.id)
      ]);
      this.setData({
        showcase: showcaseRes.data || null,
        analytics: normalizeAnalytics(analyticsRes.data || {})
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "效果加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleOpenShowcase() {
    if (!this.data.id) return;
    wx.navigateTo({ url: `/pages/showcase-view/index?id=${this.data.id}&preview=1` });
  },
  handleOpenNoteActions(event) {
    const noteId = event.currentTarget.dataset.noteId;
    if (!noteId) return;
    wx.navigateTo({ url: `/pages/note-actions/index?id=${noteId}` });
  },
  handleOpenEventTarget(event) {
    const noteId = event.currentTarget.dataset.noteId;
    if (!noteId) return;
    wx.navigateTo({ url: `/pages/note-actions/index?id=${noteId}` });
  },
  handleOpenViewerCustomer(event) {
    const keyword = event.currentTarget.dataset.keyword || "";
    wx.navigateTo({ url: `/pages/customers/index?keyword=${encodeURIComponent(keyword)}` });
  }
});
