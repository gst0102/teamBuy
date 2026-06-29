const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

const STATUS_FILTERS = [
  { key: "all", label: "全部" },
  { key: "submitted", label: "待处理" },
  { key: "contacted", label: "已联系" },
  { key: "completed", label: "已完成" },
  { key: "cancelled", label: "已取消" }
];

function dateKey(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function orderSourceKey(order = {}) {
  return order.noteId || order.title || "未知商品";
}

function filterOrders(orders, statusFilter, sourceFilter = "all", dateFilter = "all") {
  const sourceFiltered = sourceFilter === "all"
    ? orders || []
    : (orders || []).filter((item) => orderSourceKey(item) === sourceFilter);
  const dateFiltered = dateFilter === "today"
    ? sourceFiltered.filter((item) => dateKey(item.createdAt) === dateKey(new Date()))
    : sourceFiltered;
  if (statusFilter === "all") return dateFiltered;
  return dateFiltered.filter((item) => item.status === statusFilter);
}

function decodeOption(value) {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch (error) {
    return value;
  }
}

function safeAvatarUrl(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (!/^https:\/\//i.test(text)) return "";
  if (/example\.com/i.test(text)) return "";
  if (/avatar-default/i.test(text)) return "";
  if (/^(wxfile|file|blob):/i.test(text)) return "";
  if (/^\/tmp\//i.test(text)) return "";
  return text;
}

function avatarText(name) {
  const text = String(name || "客").trim();
  return text.slice(0, 1);
}

function buildSourceGroups(orders) {
  const groups = (orders || []).reduce((memo, item) => {
    const key = orderSourceKey(item);
    if (!memo[key]) {
      memo[key] = { key, title: key, total: 0, pending: 0, completed: 0, relay: 0 };
    }
    memo[key].title = item.title || memo[key].title || "未知商品";
    memo[key].noteId = item.noteId || memo[key].noteId || "";
    memo[key].total += 1;
    if (item.status === "submitted") memo[key].pending += 1;
    if (item.status === "completed") memo[key].completed += 1;
    if (item.actionKey === "relay-intent") memo[key].relay += 1;
    return memo;
  }, {});
  return Object.values(groups)
    .sort((a, b) => (b.pending + b.total) - (a.pending + a.total))
    .slice(0, 6);
}

function buildStatusGroups(summary = {}) {
  return [
    { key: "submitted", label: "待处理", count: summary.pending || 0 },
    { key: "contacted", label: "已联系", count: summary.contacted || 0 },
    { key: "completed", label: "已完成", count: summary.completed || 0 },
    { key: "cancelled", label: "已取消", count: summary.cancelled || 0 }
  ];
}

function statusLabel(key) {
  const match = STATUS_FILTERS.find((item) => item.key === key);
  return match ? match.label : key;
}

function buildActiveOrderViewText(statusFilter, sourceFilter, dateFilter, sourceTitle = "") {
  const parts = [];
  if (dateFilter === "today") parts.push("今日接龙");
  if (sourceFilter && sourceFilter !== "all") parts.push(`来源：${sourceTitle || sourceFilter}`);
  if (statusFilter && statusFilter !== "all") parts.push(statusLabel(statusFilter));
  return parts.length ? parts.join(" · ") : "全部订单";
}

Page({
  data: {
    role: "buyer",
    title: "我的订单",
    loading: true,
    errorText: "",
    orders: [],
    filteredOrders: [],
    sourceGroups: [],
    statusGroups: [],
    statusFilters: STATUS_FILTERS,
    activeStatusFilter: "all",
    activeSourceFilter: "all",
    activeNoteId: "",
    activeDateFilter: "all",
    activeViewText: "全部订单",
    orderDetailOpen: false,
    selectedOrder: null,
    summary: {
      total: 0,
      pending: 0,
      contacted: 0,
      completed: 0,
      cancelled: 0,
      relay: 0,
      order: 0
    }
  },
  onLoad(options) {
    const role = options.role === "seller" ? "seller" : "buyer";
    const source = decodeOption(options.source);
    const noteId = decodeOption(options.noteId);
    const status = decodeOption(options.status);
    const date = decodeOption(options.date);
    const activeSourceFilter = noteId || source || "all";
    const activeStatusFilter = status || "all";
    const activeDateFilter = date === "today" ? "today" : "all";
    this.setData({
      role,
      title: role === "seller" ? "接龙/买家名单" : "我的订单",
      activeSourceFilter,
      activeNoteId: noteId || "",
      activeStatusFilter,
      activeDateFilter,
      activeViewText: buildActiveOrderViewText(activeStatusFilter, activeSourceFilter, activeDateFilter)
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
      const res = await api.fetchOrders({ userId, role: this.data.role, noteId: this.data.activeNoteId });
      const summaryData = (res.data && res.data.summary) || {};
      const orders = ((res.data && res.data.orders) || []).map((item) => ({
        ...item,
        buyerAvatarUrl: safeAvatarUrl(item.buyerAvatarUrl),
        buyerAvatarText: avatarText(item.receiverName || item.buyerName),
        buyerDisplayName: item.receiverName || item.buyerName || "客户",
        createdText: formatTime(item.createdAt),
        summary: [item.actionKindText, item.skuName, item.quantity ? `x ${item.quantity}` : ""].filter(Boolean).join(" · "),
        contactText: [item.phone, item.wechat ? `微信 ${item.wechat}` : ""].filter(Boolean).join(" / ")
      }));
      const activeSourceTitle = this.currentSourceTitle(this.data.activeSourceFilter, orders);
      this.setData({
        orders,
        filteredOrders: filterOrders(orders, this.data.activeStatusFilter, this.data.activeSourceFilter, this.data.activeDateFilter),
        sourceGroups: buildSourceGroups(orders),
        statusGroups: buildStatusGroups(summaryData),
        activeViewText: buildActiveOrderViewText(this.data.activeStatusFilter, this.data.activeSourceFilter, this.data.activeDateFilter, activeSourceTitle),
        summary: {
          ...this.data.summary,
          ...summaryData
        }
      });
    } catch (error) {
      const detail = error.detail || error.message || error.errMsg || "";
      const errorText = /not found/i.test(detail)
        ? "订单服务正在更新，请稍后再查看。"
        : detail || "订单加载失败，请稍后重试。";
      this.setData({ errorText, orders: [], filteredOrders: [] });
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
  },
  handleOpenOrderSheet(event) {
    const orderId = event.currentTarget.dataset.id;
    const order = (this.data.filteredOrders || []).find((item) => item.id === orderId);
    if (!order) return;
    this.setData({
      selectedOrder: order,
      orderDetailOpen: true
    });
  },
  handleCloseOrderSheet() {
    this.setData({
      selectedOrder: null,
      orderDetailOpen: false
    });
  },
  noop() {},
  handleOpenSelectedOrder() {
    const order = this.data.selectedOrder;
    if (!order) return;
    wx.navigateTo({ url: `/pages/order-detail/index?id=${order.id}&role=${this.data.role}` });
  },
  handleSelectedOrderPrimaryAction() {
    const order = this.data.selectedOrder;
    if (!order) return;
    if (this.data.role === "seller" && order.phone) {
      wx.makePhoneCall({
        phoneNumber: order.phone,
        fail: () => wx.showToast({ title: "拨号失败", icon: "none" })
      });
      return;
    }
    if (this.data.role === "seller" && order.wechat) {
      wx.setClipboardData({
        data: order.wechat,
        success: () => wx.showToast({ title: "微信已复制", icon: "success" })
      });
      return;
    }
    wx.navigateTo({ url: `/pages/order-detail/index?id=${order.id}&role=${this.data.role}` });
  },
  handleStatusFilterChange(event) {
    const activeStatusFilter = event.currentTarget.dataset.status || "all";
    this.setData({
      activeStatusFilter,
      filteredOrders: filterOrders(this.data.orders, activeStatusFilter, this.data.activeSourceFilter, this.data.activeDateFilter),
      activeViewText: buildActiveOrderViewText(activeStatusFilter, this.data.activeSourceFilter, this.data.activeDateFilter, this.currentSourceTitle(this.data.activeSourceFilter))
    });
  },
  handleDateFilterChange(event) {
    const activeDateFilter = event.currentTarget.dataset.date || "all";
    this.setData({
      activeDateFilter,
      filteredOrders: filterOrders(this.data.orders, this.data.activeStatusFilter, this.data.activeSourceFilter, activeDateFilter),
      activeViewText: buildActiveOrderViewText(this.data.activeStatusFilter, this.data.activeSourceFilter, activeDateFilter, this.currentSourceTitle(this.data.activeSourceFilter))
    });
  },
  handleSourceGroupTap(event) {
    const source = event.currentTarget.dataset.source;
    if (!source) return;
    this.setData({
      activeSourceFilter: source,
      activeNoteId: "",
      activeStatusFilter: "all",
      filteredOrders: filterOrders(this.data.orders, "all", source, this.data.activeDateFilter),
      activeViewText: buildActiveOrderViewText("all", source, this.data.activeDateFilter, this.currentSourceTitle(source))
    });
  },
  handleClearOrderFilters() {
    const source = this.data.activeNoteId || "all";
    this.setData({
      activeStatusFilter: "all",
      activeSourceFilter: source,
      activeDateFilter: "all",
      filteredOrders: filterOrders(this.data.orders, "all", source, "all"),
      activeViewText: buildActiveOrderViewText("all", source, "all", this.currentSourceTitle(source))
    });
  },
  currentSourceTitle(source, orders) {
    if (!source || source === "all") return "";
    const row = (orders || this.data.orders || []).find((item) => orderSourceKey(item) === source);
    return row ? row.title : "";
  },
  handleCallPhone(event) {
    const phone = event.currentTarget.dataset.phone;
    if (!phone) {
      wx.showToast({ title: "暂无电话", icon: "none" });
      return;
    }
    wx.makePhoneCall({
      phoneNumber: phone,
      fail: () => wx.showToast({ title: "拨号失败", icon: "none" })
    });
  },
  handleCopyWechat(event) {
    const wechat = event.currentTarget.dataset.wechat;
    if (!wechat) {
      wx.showToast({ title: "暂无微信号", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: wechat,
      success: () => wx.showToast({ title: "已复制", icon: "success" })
    });
  }
});
