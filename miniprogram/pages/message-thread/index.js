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
    sending: false
  },
  onLoad(options) {
    this.setData({ threadId: options.id || "" });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
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
      this.setData({ thread: data.thread || null, messages });
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
    } catch (error) {
      wx.showToast({ title: error.detail || "发送失败", icon: "none" });
    } finally {
      this.setData({ sending: false });
    }
  }
});
