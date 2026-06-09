const api = require("../../services/api");
const { formatTime, statusText } = require("../../utils/dashboard");

function filterRelays(relays, filter) {
  if (filter === "pending") return relays.filter((item) => item.isPending);
  if (filter === "followed") return relays.filter((item) => item.followUpStatus === "followed");
  return relays;
}

function filterEmptyText(filter) {
  if (filter === "pending") return "暂无待跟进线索。";
  if (filter === "followed") return "暂无已跟进线索。";
  return "暂无接龙线索。";
}

function filterViewers(viewers, filter) {
  if (filter === "intent") return viewers.filter((item) => item.isHighIntent);
  return viewers;
}

function viewerEmptyText(filter) {
  if (filter === "intent") return "暂无高意向访客。";
  return "暂无登录访客，匿名访问只计入总量。";
}

Page({
  data: {
    cardId: "",
    card: null,
    stats: null,
    viewers: [],
    relays: [],
    pendingRelays: [],
    followedRelays: [],
    filteredRelays: [],
    highIntentViewers: [],
    filteredViewers: [],
    relayFilter: "pending",
    relayFilterEmptyText: "暂无待跟进线索。",
    viewerFilter: "intent",
    viewerFilterEmptyText: "暂无高意向访客。",
    summary: {
      loggedViewers: 0,
      anonymousPv: 0,
      relayCount: 0,
      pendingFollow: 0,
      highIntentViewers: 0
    }
  },
  onLoad(query) {
    this.setData({ cardId: query.id });
  },
  onShow() {
    this.loadAll();
  },
  async loadAll() {
    const currentUser = getApp().globalData.currentUser;
    const [cardRes, statsRes] = await Promise.all([
      api.fetchCard(this.data.cardId),
      api.fetchStats(this.data.cardId, currentUser.id)
    ]);
    const relays = (statsRes.data.relayEntries || []).map((item) => ({
      ...item,
      isPending: item.followUpStatus !== "followed",
      followUpText: statusText(item.followUpStatus),
      createdText: formatTime(item.createdAt)
    }));
    const pendingRelays = relays.filter((item) => item.isPending);
    const followedRelays = relays.filter((item) => item.followUpStatus === "followed");
    const relayFilter = this.data.relayFilter || "pending";
    const relayUserIds = new Set(relays.map((item) => item.userId).filter(Boolean));
    const viewers = (statsRes.data.loggedInViewers || []).map((item) => ({
      ...item,
      viewCount: Number(item.viewCount || 1),
      viewedText: formatTime(item.viewedAt),
      hasRelay: relayUserIds.has(item.userId)
    })).map((item) => ({
      ...item,
      isRepeat: item.viewCount >= 2,
      isHighIntent: item.viewCount >= 2 && !item.hasRelay,
      intentText: item.hasRelay ? "已接龙" : item.viewCount >= 2 ? "高意向" : "普通访问"
    }));
    const highIntentViewers = viewers.filter((item) => item.isHighIntent);
    const viewerFilter = this.data.viewerFilter || "intent";
    this.setData({
      card: cardRes.data,
      stats: statsRes.data,
      viewers,
      relays,
      pendingRelays,
      followedRelays,
      filteredRelays: filterRelays(relays, relayFilter),
      relayFilterEmptyText: filterEmptyText(relayFilter),
      highIntentViewers,
      filteredViewers: filterViewers(viewers, viewerFilter),
      viewerFilterEmptyText: viewerEmptyText(viewerFilter),
      summary: {
        loggedViewers: viewers.length,
        anonymousPv: statsRes.data.anonymousPv || 0,
        relayCount: statsRes.data.relayCount || relays.length,
        pendingFollow: pendingRelays.length,
        highIntentViewers: highIntentViewers.length
      }
    });
  },
  handleRelayFilterChange(event) {
    const filter = event.currentTarget.dataset.filter || "pending";
    this.setData({
      relayFilter: filter,
      filteredRelays: filterRelays(this.data.relays || [], filter),
      relayFilterEmptyText: filterEmptyText(filter)
    });
  },
  handleViewerFilterChange(event) {
    const filter = event.currentTarget.dataset.filter || "intent";
    this.setData({
      viewerFilter: filter,
      filteredViewers: filterViewers(this.data.viewers || [], filter),
      viewerFilterEmptyText: viewerEmptyText(filter)
    });
  },
  async handleDelete(event) {
    const currentUser = getApp().globalData.currentUser;
    await api.deleteRelay(event.detail.id, currentUser.id);
    wx.showToast({ title: "已删除", icon: "success" });
    this.loadAll();
  },
  async handleFollow(event) {
    const currentUser = getApp().globalData.currentUser;
    await api.followRelay(event.detail.id, currentUser.id);
    wx.showToast({ title: "已跟进", icon: "success" });
    this.loadAll();
  },
  async handleDuplicate() {
    const currentUser = getApp().globalData.currentUser;
    const res = await api.duplicateCard(this.data.cardId, currentUser.id);
    wx.navigateTo({ url: `/pages/card-edit/index?id=${res.data.id}` });
  },
  handleOpenCard() {
    wx.navigateTo({ url: `/pages/card-view/index?id=${this.data.cardId}` });
  },
  handleEditCard() {
    wx.navigateTo({ url: `/pages/card-edit/index?id=${this.data.cardId}` });
  }
});
