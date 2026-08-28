const api = require("../../services/api");
const { getCurrentUser, formatTime, safeAvatarUrl } = require("../../utils/dashboard");

function firstChar(value, fallback) {
  const text = String(value || fallback || "").trim();
  return text ? text.slice(0, 1) : "信";
}

function buildParticipantMap(thread) {
  return (thread && thread.participants) || {};
}

function hydrateMessages(messages, thread, userId) {
  const participants = buildParticipantMap(thread);
  return (messages || []).map((item) => {
    const sender = participants[item.senderUserId] || {};
    const mine = item.senderUserId === userId;
    const senderName = sender.nickname || (mine ? "我" : "对方");
    return {
      ...item,
      mine,
      senderName,
      senderAvatarUrl: safeAvatarUrl(sender.avatarUrl),
      senderInitial: firstChar(senderName, mine ? "我" : "客"),
      timeText: formatTime(item.createdAt)
    };
  });
}

Page({
  data: {
    threadId: "",
    thread: null,
    messages: [],
    inputText: "",
    sending: false,
    canOpenCustomerRadar: false,
    fromSubscription: false,
    autoHomeAfterSend: false
  },
  onLoad(options = {}) {
    const fromSubscription = options.source === "subscription" || options.autoHome === "1";
    this.setData({
      threadId: options.id || "",
      fromSubscription,
      autoHomeAfterSend: fromSubscription
    });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      const params = [`id=${encodeURIComponent(this.data.threadId || "")}`];
      if (this.data.fromSubscription) {
        params.push("source=subscription", "autoHome=1");
      }
      const returnUrl = `/pages/message-thread/index?${params.join("&")}`;
      wx.reLaunch({ url: `/pages/login/index?returnUrl=${encodeURIComponent(returnUrl)}` });
      return;
    }
    this.loadMessages(user.id);
  },
  async loadMessages(userId) {
    if (!this.data.threadId) return;
    try {
      const res = await api.fetchThreadMessages(this.data.threadId, userId);
      const data = res.data || {};
      const messages = hydrateMessages(data.messages || [], data.thread || null, userId);
      const thread = data.thread || null;
      this.setData({
        thread,
        messages,
        canOpenCustomerRadar: Boolean(thread && thread.ownerUserId === userId && thread.peerUserId)
      });
      await api.markThreadRead(this.data.threadId, userId);
    } catch (error) {
      wx.showToast({ title: error.detail || "消息加载失败", icon: "none" });
    }
  },
  handleInput(event) {
    this.setData({ inputText: event.detail.value });
  },
  async handleSend() {
    const user = getCurrentUser();
    const content = String(this.data.inputText || "").trim();
    if (!user || !content || this.data.sending) return;
    this.setData({ sending: true });
    try {
      await api.sendThreadMessage(this.data.threadId, {
        userId: user.id,
        content
      });
      this.setData({ inputText: "" });
      await this.loadMessages(user.id);
      if (this.data.autoHomeAfterSend) {
        wx.showToast({ title: "已发送，正在回到首页", icon: "success", duration: 700 });
        this._homeTimer = setTimeout(() => this.handleBackHome(), 750);
      }
    } catch (error) {
      wx.showToast({ title: error.detail || "发送失败", icon: "none" });
    } finally {
      this.setData({ sending: false });
    }
  },
  handleBackHome() {
    if (this._homeTimer) {
      clearTimeout(this._homeTimer);
      this._homeTimer = null;
    }
    wx.switchTab({
      url: "/pages/home/index",
      fail: () => wx.reLaunch({ url: "/pages/home/index" })
    });
  },
  handleOpenCustomerRadar() {
    const thread = this.data.thread || {};
    const user = getCurrentUser();
    if (!user || thread.ownerUserId !== user.id || !thread.peerUserId) {
      wx.showToast({ title: "当前账号不能打开客户雷达", icon: "none" });
      return;
    }
    wx.navigateTo({
      url: `/pages/customer-detail/index?threadId=${encodeURIComponent(thread.id || this.data.threadId)}&source=message`
    });
  },
  onUnload() {
    if (this._homeTimer) clearTimeout(this._homeTimer);
  }
});
