const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

const STATUS_OPTIONS = [
  { value: "submitted", label: "已下单" },
  { value: "contacted", label: "已联系" },
  { value: "completed", label: "已完成" },
  { value: "cancelled", label: "已取消" }
];

Page({
  data: {
    orderId: "",
    role: "buyer",
    order: null,
    rows: [],
    statusOptions: STATUS_OPTIONS
  },
  onLoad(options) {
    this.setData({ orderId: options.id || "", role: options.role === "seller" ? "seller" : "buyer" });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadOrder(user.id);
  },
  async loadOrder(userId) {
    try {
      const res = await api.fetchOrder(this.data.orderId, userId);
      const order = res.data || {};
      const rows = [
        ["类型", order.actionKindText],
        ["规格", order.skuName],
        ["单价", order.skuPrice],
        ["数量", order.quantity],
        ["收货人", order.receiverName],
        ["电话", order.phone],
        ["地址", order.address],
        ["微信", order.wechat],
        ["备注", order.remark],
        ["提交时间", formatTime(order.createdAt)]
      ].filter((item) => item[1] !== undefined && item[1] !== null && item[1] !== "");
      this.setData({ order, rows });
    } catch (error) {
      wx.showToast({ title: error.detail || "订单加载失败", icon: "none" });
    }
  },
  async handleSetStatus(event) {
    const status = event.currentTarget.dataset.status;
    const user = getCurrentUser();
    if (!status || !user || this.data.role !== "seller") return;
    try {
      const res = await api.updateOrderStatus(this.data.orderId, { userId: user.id, status });
      this.setData({ order: res.data || this.data.order });
      wx.showToast({ title: "状态已更新", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "更新失败", icon: "none" });
    }
  },
  handleCallPhone() {
    const phone = this.data.order && this.data.order.phone;
    if (!phone) {
      wx.showToast({ title: "暂无电话", icon: "none" });
      return;
    }
    wx.makePhoneCall({ phoneNumber: phone });
  },
  handleCopyAddress() {
    const address = this.data.order && this.data.order.address;
    if (!address) return;
    wx.setClipboardData({ data: address, success: () => wx.showToast({ title: "地址已复制", icon: "success" }) });
  },
  handleCopyWechat() {
    const wechat = this.data.order && this.data.order.wechat;
    if (!wechat) {
      wx.showToast({ title: "暂无微信号", icon: "none" });
      return;
    }
    wx.setClipboardData({ data: wechat, success: () => wx.showToast({ title: "微信已复制", icon: "success" }) });
  },
  async handleOpenMessage() {
    const order = this.data.order || {};
    if (!order.noteId) return;
    await messagePlugin.openMessageThread({ noteId: order.noteId, orderActionId: order.id });
  }
});
