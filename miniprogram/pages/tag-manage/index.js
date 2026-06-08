const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    name: "",
    categories: [],
    loading: false
  },
  onShow() {
    if (!getCurrentUser()) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadCategories();
  },
  async loadCategories() {
    const currentUser = getCurrentUser();
    this.setData({ loading: true });
    try {
      const res = await api.fetchCategories(currentUser.id);
      this.setData({ categories: res.data || [] });
    } catch (error) {
      wx.showToast({ title: "标签加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleNameChange(event) {
    this.setData({ name: event.detail.value });
  },
  async handleCreate() {
    const currentUser = getCurrentUser();
    const name = this.data.name.trim();
    if (!name) {
      wx.showToast({ title: "请输入标签名称", icon: "none" });
      return;
    }
    try {
      await api.createCategory({ ownerUserId: currentUser.id, name });
      this.setData({ name: "" });
      wx.showToast({ title: "已添加", icon: "success" });
      this.loadCategories();
    } catch (error) {
      wx.showToast({ title: error.detail || "添加失败", icon: "none" });
    }
  },
  async handleDelete(event) {
    const currentUser = getCurrentUser();
    const id = event.currentTarget.dataset.id;
    try {
      await api.deleteCategory(id, currentUser.id);
      wx.showToast({ title: "已删除", icon: "success" });
      this.loadCategories();
    } catch (error) {
      wx.showToast({ title: error.detail || "删除失败", icon: "none" });
    }
  }
});
