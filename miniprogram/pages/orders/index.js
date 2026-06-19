const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

Page({
  data: {
    role: "buyer",
    title: "我的订单",
    loading: true,
    errorText: "",
    orders: []
  },
  onLoad(options) {
    const role = options.role === "seller" ? "seller" : "buyer";
    this.setData({
      role,
      title: role === "seller" ? "商家订单中心" : "我的订单"
    });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadOrders(user.id);
  },
  async loadOrders(userId) {
    this.setData({ loading: true, errorText: "" });
    try {
      const res = await api.fetchOrders({ userId, role: this.data.role });
      const orders = ((res.data && res.data.orders) || []).map((item) => ({
        ...item,
        createdText: formatTime(item.createdAt),
        summary: [item.skuName, item.quantity ? `x ${item.quantity}` : ""].filter(Boolean).join(" · "),
        contactText: [item.phone, item.wechat ? `微信 ${item.wechat}` : ""].filter(Boolean).join(" / ")
      }));
      this.setData({ orders });
    } catch (error) {
      const detail = error.detail || error.message || error.errMsg || "";
      const errorText = /not found/i.test(detail)
        ? "订单接口还没有更新到当前后端，请先部署后端后再查看。"
        : detail || "订单加载失败，请稍后重试。";
      this.setData({ errorText, orders: [] });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleRetry() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadOrders(user.id);
  },
  handleOpenOrder(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/order-detail/index?id=${id}&role=${this.data.role}` });
  }
});
