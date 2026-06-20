const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

function statusText(status) {
  if (status === "published") return "已发布";
  if (status === "archived") return "已下架";
  return "草稿";
}

function decorateShowcase(item) {
  return {
    ...item,
    initial: String(item.name || "展").slice(0, 1),
    statusText: statusText(item.status),
    descText: item.description || "还没有填写简介",
    itemCountText: `${item.itemCount || (item.items || []).length || 0} 条资料`
  };
}

Page({
  data: {
    user: null,
    showcases: [],
    loading: false
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    this.loadShowcases();
  },
  async loadShowcases() {
    const { user } = this.data;
    if (!user) return;
    this.setData({ loading: true });
    try {
      const res = await api.fetchShowcases(user.id);
      this.setData({ showcases: (res.data || []).map(decorateShowcase) });
    } catch (error) {
      wx.showToast({ title: error.detail || "展示页加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleCreate() {
    wx.navigateTo({ url: "/pages/showcase-edit/index" });
  },
  handleEdit(event) {
    const id = event.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/showcase-edit/index?id=${id}` });
  },
  handlePreview(event) {
    const id = event.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/showcase-view/index?id=${id}&preview=1` });
  }
});
