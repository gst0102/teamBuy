const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

const INTENT_FILTERS = [
  { key: "all", label: "全部" },
  { key: "高意向", label: "高意向" },
  { key: "中意向", label: "中意向" },
  { key: "低意向", label: "低意向" },
  { key: "待判断", label: "待判断" }
];

function hasProfile(item) {
  return !!(item.customerPhone || item.customerWechat || item.budgetText || item.intentLevel);
}

function matchesSearch(item, keyword) {
  if (!keyword) return true;
  const text = [
    item.nickname,
    item.customerPhone,
    item.customerWechat,
    item.budgetText,
    item.cardTitle
  ].filter(Boolean).join(" ").toLowerCase();
  return text.includes(keyword.toLowerCase());
}

function filterCustomers(customers, filter, keyword = "") {
  return customers.filter((item) => {
    const intentMatched = filter === "all" || (item.intentLevel || "待判断") === filter;
    return intentMatched && matchesSearch(item, keyword.trim());
  });
}

function sortCustomers(customers) {
  const rank = { 高意向: 0, 中意向: 1, 待判断: 2, 低意向: 3 };
  return [...customers].sort((a, b) => {
    const intentDiff = (rank[a.intentLevel || "待判断"] ?? 9) - (rank[b.intentLevel || "待判断"] ?? 9);
    if (intentDiff !== 0) return intentDiff;
    return String(b.updatedAt || "").localeCompare(String(a.updatedAt || ""));
  });
}

Page({
  data: {
    customers: [],
    filteredCustomers: [],
    activeIntent: "all",
    searchKeyword: "",
    intentFilters: INTENT_FILTERS,
    summary: {
      total: 0,
      high: 0,
      withPhone: 0,
      withWechat: 0
    }
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadCustomers();
  },
  async loadCustomers() {
    const currentUser = getCurrentUser();
    try {
      const res = await api.fetchLeadReminders(currentUser.id);
      const customers = sortCustomers((res.data || []).filter(hasProfile).map((item) => ({
        ...item,
        intentLevel: item.intentLevel || "待判断",
        updatedText: formatTime(item.updatedAt),
        lastViewedText: formatTime(item.lastViewedAt)
      })));
      this.setData({
        customers,
        filteredCustomers: filterCustomers(customers, this.data.activeIntent, this.data.searchKeyword),
        summary: {
          total: customers.length,
          high: customers.filter((item) => item.intentLevel === "高意向").length,
          withPhone: customers.filter((item) => item.customerPhone).length,
          withWechat: customers.filter((item) => item.customerWechat).length
        }
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "客户资料加载失败", icon: "none" });
    }
  },
  handleIntentFilterChange(event) {
    const activeIntent = event.currentTarget.dataset.filter;
    this.setData({
      activeIntent,
      filteredCustomers: filterCustomers(this.data.customers, activeIntent, this.data.searchKeyword)
    });
  },
  handleSearchChange(event) {
    const searchKeyword = event.detail.value;
    this.setData({
      searchKeyword,
      filteredCustomers: filterCustomers(this.data.customers, this.data.activeIntent, searchKeyword)
    });
  },
  handleClearSearch() {
    this.setData({
      searchKeyword: "",
      filteredCustomers: filterCustomers(this.data.customers, this.data.activeIntent, "")
    });
  },
  handleCopyField(event) {
    const value = event.currentTarget.dataset.value;
    if (!value) {
      wx.showToast({ title: "暂无内容", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: value,
      success: () => wx.showToast({ title: "已复制", icon: "success" })
    });
  },
  handleOpenLead(event) {
    wx.navigateTo({ url: `/pages/lead-detail/index?id=${event.currentTarget.dataset.id}` });
  },
  handleOpenCard(event) {
    wx.navigateTo({ url: `/pages/card-view/index?id=${event.currentTarget.dataset.cardId}` });
  }
});
