const api = require("../../services/api");
const { formatTime, statusText } = require("../../utils/dashboard");

Page({
  data: {
    cardId: "",
    card: null,
    stats: null,
    viewers: [],
    relays: [],
    pendingRelays: [],
    summary: {
      loggedViewers: 0,
      anonymousPv: 0,
      relayCount: 0,
      pendingFollow: 0
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
    const viewers = (statsRes.data.loggedInViewers || []).map((item) => ({
      ...item,
      viewedText: formatTime(item.viewedAt)
    }));
    this.setData({
      card: cardRes.data,
      stats: statsRes.data,
      viewers,
      relays,
      pendingRelays,
      summary: {
        loggedViewers: viewers.length,
        anonymousPv: statsRes.data.anonymousPv || 0,
        relayCount: statsRes.data.relayCount || relays.length,
        pendingFollow: pendingRelays.length
      }
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
