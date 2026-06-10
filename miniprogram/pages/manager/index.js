const api = require("../../services/api");
const resourceStore = require("../../stores/resource-store");
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

function leadReminderStatusText(status) {
  const map = {
    pending: "待联系",
    contacted: "已联系",
    invalid: "无效",
    paused: "暂不跟进",
    completed: "已完成"
  };
  return map[status] || "";
}

function applyViewerReminders(viewers, reminderMap) {
  return viewers.map((item) => ({
    ...item,
    reminder: reminderMap[item.userId] || null,
    reminderId: reminderMap[item.userId] ? reminderMap[item.userId].id : "",
    reminderStatus: reminderMap[item.userId] ? reminderMap[item.userId].status : "",
    reminderStatusText: reminderMap[item.userId] ? leadReminderStatusText(reminderMap[item.userId].status) : "",
    reminderNote: reminderMap[item.userId] ? reminderMap[item.userId].note || "" : "",
    leadNoteValue: reminderMap[item.userId] ? reminderMap[item.userId].note || "" : "",
    isReminded: reminderMap[item.userId] && reminderMap[item.userId].status === "pending",
    isContacted: reminderMap[item.userId] && reminderMap[item.userId].status === "contacted"
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
    leadNotes: {},
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
    const [cardRes, statsRes, reminderRes] = await Promise.all([
      resourceStore.getCard(this.data.cardId, { force: true }),
      api.fetchStats(this.data.cardId, currentUser.id),
      api.fetchLeadReminders(currentUser.id)
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
    const reminderMap = (reminderRes.data || [])
      .filter((item) => item.cardId === this.data.cardId)
      .reduce((memo, item) => {
        memo[item.viewerUserId] = item;
        return memo;
      }, {});
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
      card: cardRes,
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
      leadNotes: viewers.reduce((memo, item) => {
        memo[item.userId] = item.reminderNote || "";
        return memo;
      }, {}),
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
    this.saveViewerReminder(userId, "pending", "已加入待联系");
  },
  handleMarkViewerContacted(event) {
    const userId = event.currentTarget.dataset.userId;
    if (!userId) return;
    this.saveViewerReminder(userId, "contacted", "已标记联系");
  },
  handleCancelViewerReminder(event) {
    const userId = event.currentTarget.dataset.userId;
    if (!userId) return;
    this.deleteViewerReminder(userId, "已清除");
  },
  handleLeadNoteChange(event) {
    const userId = event.currentTarget.dataset.userId;
    this.setData({
      [`leadNotes.${userId}`]: event.detail.value
    });
  },
  async saveViewerReminder(userId, status, toastTitle) {
    const currentUser = getApp().globalData.currentUser;
    const viewer = (this.data.viewers || []).find((item) => item.userId === userId);
    if (!currentUser || !viewer) return;
    try {
      const res = await api.upsertLeadReminder({
        ownerUserId: currentUser.id,
        cardId: this.data.cardId,
        viewerUserId: userId,
        nickname: viewer.nickname,
        avatarUrl: viewer.avatarUrl,
        status,
        note: (this.data.leadNotes || {})[userId] || viewer.reminderNote || "",
        viewCount: viewer.viewCount,
        lastViewedAt: viewer.viewedAt
      });
      this.applyReminderChange(res.data, toastTitle);
    } catch (error) {
      wx.showToast({ title: error.detail || "线索保存失败", icon: "none" });
    }
  },
  async deleteViewerReminder(userId, toastTitle) {
    const reminder = (this.data.viewerReminderMap || {})[userId];
    const currentUser = getApp().globalData.currentUser;
    if (!reminder || !currentUser) return;
    try {
      await api.deleteLeadReminder(reminder.id, currentUser.id);
      this.applyReminderChange(null, toastTitle, userId);
    } catch (error) {
      wx.showToast({ title: error.detail || "线索清除失败", icon: "none" });
    }
  },
  applyReminderChange(reminder, toastTitle, deletedUserId = "") {
    const nextMap = { ...(this.data.viewerReminderMap || {}) };
    if (reminder && reminder.viewerUserId) {
      nextMap[reminder.viewerUserId] = reminder;
    }
    if (deletedUserId) {
      delete nextMap[deletedUserId];
    }
    const viewers = applyViewerReminders(this.data.viewers || [], nextMap);
    this.setData({
      viewerReminderMap: nextMap,
      viewers,
      highIntentViewers: viewers.filter((item) => item.isHighIntent),
      filteredViewers: filterViewers(viewers, this.data.viewerFilter),
      leadNotes: viewers.reduce((memo, item) => {
        memo[item.userId] = item.reminderNote || (this.data.leadNotes || {})[item.userId] || "";
        return memo;
      }, {}),
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
