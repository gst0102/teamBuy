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
  }
});
