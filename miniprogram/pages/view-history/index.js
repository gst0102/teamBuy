const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

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

function normalizeHistoryItem(item = {}) {
  return {
    id: item.id || "",
    targetType: item.targetType || "",
    title: String(item.title || "公开资料").trim() || "公开资料",
    coverUrl: absoluteMediaUrl(item.coverUrl),
    viewedAtText: formatViewedAt(item.viewedAt),
    historyKey: `${item.targetType || "item"}:${item.id || ""}`
  };
}

Page({
  data: {
    user: null,
    items: [],
    loading: true,
    loadError: false
  },
  onShow() {
    this.loadHistory();
  },
  onPullDownRefresh() {
    this.loadHistory();
  },
  async loadHistory() {
    const currentUser = getCurrentUser();
    const requestSeq = (this._requestSeq || 0) + 1;
    this._requestSeq = requestSeq;
    if (!currentUser || !currentUser.id) {
      this.setData({ user: null, items: [], loading: false, loadError: false });
      wx.stopPullDownRefresh();
      return;
    }
    this.setData({ user: { id: currentUser.id }, loading: true, loadError: false });
    try {
      const res = await api.fetchViewHistory(currentUser.id, 50);
      if (requestSeq !== this._requestSeq || (getCurrentUser() || {}).id !== currentUser.id) return;
      const rows = Array.isArray(res.data) ? res.data : [];
      this.setData({
        items: rows.map(normalizeHistoryItem).filter((item) => item.id && ["note", "card"].includes(item.targetType)),
        loadError: false
      });
    } catch (error) {
      if (requestSeq !== this._requestSeq) return;
      this.setData({ items: [], loadError: true });
    } finally {
      if (requestSeq === this._requestSeq) {
        this.setData({ loading: false });
        wx.stopPullDownRefresh();
      }
    }
  },
  handleOpenItem(event) {
    const type = event.currentTarget.dataset.type;
    const id = event.currentTarget.dataset.id;
    if (!id || !["note", "card"].includes(type)) return;
    const path = `/pages/note-preview/index?id=${encodeURIComponent(id)}`;
    wx.navigateTo({ url: path });
  },
  handleRetry() {
    this.loadHistory();
  },
  handleGoLogin() {
    wx.navigateTo({
      url: `/pages/login/index?returnUrl=${encodeURIComponent("/pages/view-history/index")}`
    });
  },
  handleBack() {
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: "/pages/profile/index" });
  }
});
