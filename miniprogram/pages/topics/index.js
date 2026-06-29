const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    user: null,
    topics: [],
    name: "",
    loading: false
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    this.loadTopics();
  },
  async loadTopics() {
    const { user } = this.data;
    if (!user) return;
    this.setData({ loading: true });
    try {
      const res = await api.fetchTopics(user.id);
      this.setData({ topics: res.data || [] });
    } catch (error) {
      wx.showToast({ title: error.detail || "专题加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleNameChange(event) {
    this.setData({ name: event.detail.value });
  },
  async handleCreate() {
    const name = this.data.name.trim();
    const { user } = this.data;
    if (!name) {
      wx.showToast({ title: "请输入专题名称", icon: "none" });
      return;
    }
    try {
      await api.createTopic({ ownerUserId: user.id, name });
      this.setData({ name: "" });
      wx.showToast({ title: "已创建", icon: "success" });
      this.loadTopics();
    } catch (error) {
      wx.showToast({ title: error.detail || "创建失败", icon: "none" });
    }
  },
  handleOpen(event) {
    wx.navigateTo({ url: `/pages/notes/index?topicId=${event.currentTarget.dataset.id}` });
  },
  handleCreateCollection(event) {
    const { id, name } = event.currentTarget.dataset;
    if (!id) return;
    wx.navigateTo({
      url: `/pages/showcase-edit/index?mode=notes&topicId=${encodeURIComponent(id)}&topicName=${encodeURIComponent(name || "专题")}`
    });
  },
  handleDelete(event) {
    const { id, name, count } = event.currentTarget.dataset;
    const { user } = this.data;
    if (!id || !user) return;
    wx.showModal({
      title: "删除专题",
      content: Number(count || 0) > 0
        ? `会从 ${count} 条资料中移除“${name || "这个专题"}”，资料本身不会删除。`
        : `确认删除“${name || "这个专题"}”？`,
      confirmText: "删除",
      confirmColor: "#e5484d",
      success: async ({ confirm }) => {
        if (!confirm) return;
        try {
          await api.deleteTopic(id, user.id);
          wx.showToast({ title: "已删除", icon: "success" });
          this.loadTopics();
        } catch (error) {
          wx.showToast({ title: error.detail || "删除失败", icon: "none" });
        }
      }
    });
  }
});
