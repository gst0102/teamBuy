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

function viewerReminderKey(cardId) {
  return `viewerReminders_${cardId}`;
}

function normalizeViewerReminderMap(value) {
  if (Array.isArray(value)) {
    return value.reduce((memo, userId) => {
      if (userId) memo[userId] = "pending";
      return memo;
    }, {});
  }
  if (!value || typeof value !== "object") return {};
  return Object.keys(value).reduce((memo, userId) => {
    if (value[userId] === "pending" || value[userId] === "contacted") {
      memo[userId] = value[userId];
    }
    return memo;
  }, {});
}

function applyViewerReminders(viewers, reminderMap) {
  return viewers.map((item) => ({
    ...item,
    reminderStatus: reminderMap[item.userId] || "",
    isReminded: reminderMap[item.userId] === "pending",
    isContacted: reminderMap[item.userId] === "contacted"
  }));
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
    viewerReminderMap: {},
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
    const reminderMap = normalizeViewerReminderMap(wx.getStorageSync(viewerReminderKey(this.data.cardId)));
    const viewers = applyViewerReminders((statsRes.data.loggedInViewers || []).map((item) => ({
      ...item,
      viewCount: Number(item.viewCount || 1),
      viewedText: formatTime(item.viewedAt),
      hasRelay: relayUserIds.has(item.userId)
    })).map((item) => ({
      ...item,
      isRepeat: item.viewCount >= 2,
      isHighIntent: item.viewCount >= 2 && !item.hasRelay,
      intentText: item.hasRelay ? "已接龙" : item.viewCount >= 2 ? "高意向" : "普通访问"
    })), reminderMap);
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
      viewerReminderMap: reminderMap,
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
  handleCopyViewerNickname(event) {
    const nickname = event.currentTarget.dataset.nickname;
    if (!nickname) {
      wx.showToast({ title: "暂无昵称", icon: "none" });
      return;
    }
    wx.setClipboardData({ data: nickname });
  },
  handleAddViewerReminder(event) {
    const userId = event.currentTarget.dataset.userId;
    if (!userId) return;
    this.updateViewerReminder(userId, "pending", "已加入待联系");
  },
  handleMarkViewerContacted(event) {
    const userId = event.currentTarget.dataset.userId;
    if (!userId) return;
    this.updateViewerReminder(userId, "contacted", "已标记联系");
  },
  handleCancelViewerReminder(event) {
    const userId = event.currentTarget.dataset.userId;
    if (!userId) return;
    this.updateViewerReminder(userId, "", "已取消待联系");
  },
  updateViewerReminder(userId, status, toastTitle) {
    const nextMap = { ...(this.data.viewerReminderMap || {}) };
    if (status) {
      nextMap[userId] = status;
    } else {
      delete nextMap[userId];
    }
    wx.setStorageSync(viewerReminderKey(this.data.cardId), nextMap);
    const viewers = applyViewerReminders(this.data.viewers || [], nextMap);
    this.setData({
      viewerReminderMap: nextMap,
      viewers,
      highIntentViewers: viewers.filter((item) => item.isHighIntent),
      filteredViewers: filterViewers(viewers, this.data.viewerFilter),
      summary: {
        ...this.data.summary,
        highIntentViewers: viewers.filter((item) => item.isHighIntent).length
      }
    });
    wx.showToast({ title: toastTitle, icon: "success" });
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
