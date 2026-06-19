const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

Page({
  data: {
    loading: true,
    unreadTotal: 0,
    threads: []
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadThreads(user.id);
  },
  async loadThreads(userId) {
    this.setData({ loading: true });
    try {
      const res = await api.fetchMessageThreads(userId);
      const data = res.data || {};
      const threads = (data.threads || []).map((item) => ({
        ...item,
        timeText: formatTime(item.lastMessageAt || item.updatedAt),
        titleText: item.noteTitle || item.title || "站内消息",
        subtitle: item.orderSkuName ? `订单：${item.orderSkuName}` : "资料咨询",
        lastText: item.lastMessage || "暂无消息"
      }));
      this.setData({
        unreadTotal: data.unreadTotal || 0,
        threads
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "消息加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleOpenThread(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/message-thread/index?id=${id}` });
  }
});
