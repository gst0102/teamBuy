const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

const INTENT_FILTERS = [
  { key: "all", label: "全部" },
  { key: "高意向", label: "高意向" },
  { key: "中意向", label: "中意向" },
  { key: "低意向", label: "低意向" },
  { key: "待判断", label: "待判断" }
];

const PROFILE_FILTERS = [
  { key: "all", label: "全部资料" },
  { key: "phone", label: "有电话" },
  { key: "wechat", label: "有微信" },
  { key: "budget", label: "有预算" }
];

const SORT_OPTIONS = [
  { key: "intent", label: "高意向优先" },
  { key: "updated", label: "最近更新" }
];

function hasProfile(item) {
  return !!(item.customerPhone || item.customerWechat || item.budgetText || item.intentLevel || (item.customerTags || []).length);
}

function matchesSearch(item, keyword) {
  if (!keyword) return true;
  const text = [
    item.nickname,
    item.customerPhone,
    item.customerWechat,
    item.budgetText,
    item.cardTitle,
    ...(item.customerTags || [])
  ].filter(Boolean).join(" ").toLowerCase();
  return text.includes(keyword.toLowerCase());
}

function matchesProfileFilter(item, filter) {
  if (filter === "phone") return !!item.customerPhone;
  if (filter === "wechat") return !!item.customerWechat;
  if (filter === "budget") return !!item.budgetText;
  return true;
}

function matchesSourceFilter(item, filter) {
  return filter === "all" || item.cardTitle === filter;
}

function matchesTagFilter(item, filter) {
  return filter === "all" || (item.customerTags || []).includes(filter);
}

function buildCountFilters(items, pickValue, allLabel) {
  const counts = items.reduce((memo, item) => {
    const value = pickValue(item);
    if (value) memo[value] = (memo[value] || 0) + 1;
    return memo;
  }, {});
  return [
    { key: "all", label: allLabel, count: items.length },
    ...Object.keys(counts).sort().map((key) => ({ key, label: key, count: counts[key] }))
  ];
}

function buildTagFilters(customers) {
  const tags = customers.flatMap((item) => item.customerTags || []);
  const counts = tags.reduce((memo, tag) => {
    memo[tag] = (memo[tag] || 0) + 1;
    return memo;
  }, {});
  return [
    { key: "all", label: "全部标签", count: customers.length },
    ...Object.keys(counts).sort().map((key) => ({ key, label: key, count: counts[key] }))
  ];
}

function filterCustomers(customers, intentFilter, keyword = "", profileFilter = "all", sourceFilter = "all", tagFilter = "all") {
  return customers.filter((item) => {
    const intentMatched = intentFilter === "all" || (item.intentLevel || "待判断") === intentFilter;
    return intentMatched &&
      matchesProfileFilter(item, profileFilter) &&
      matchesSourceFilter(item, sourceFilter) &&
      matchesTagFilter(item, tagFilter) &&
      matchesSearch(item, keyword.trim());
  });
}

function sortCustomers(customers, sortMode = "intent") {
  const rank = { 高意向: 0, 中意向: 1, 待判断: 2, 低意向: 3 };
  return [...customers].sort((a, b) => {
    if (sortMode === "updated") {
      return String(b.updatedAt || "").localeCompare(String(a.updatedAt || ""));
    }
    const intentDiff = (rank[a.intentLevel || "待判断"] ?? 9) - (rank[b.intentLevel || "待判断"] ?? 9);
    if (intentDiff !== 0) return intentDiff;
    return String(b.updatedAt || "").localeCompare(String(a.updatedAt || ""));
  });
}

function applyCustomerView(customers, intentFilter, profileFilter, keyword, sortMode, sourceFilter, tagFilter) {
  return sortCustomers(filterCustomers(customers, intentFilter, keyword, profileFilter, sourceFilter, tagFilter), sortMode);
}

function buildCustomerSummary(customers) {
  const header = "姓名\t手机号\t微信号\t预算\t意向等级\t客户标签\t来源资料";
  const rows = customers.map((item) => [
    item.nickname || "",
    item.customerPhone || "",
    item.customerWechat || "",
    item.budgetText || "",
    item.intentLevel || "待判断",
    (item.customerTags || []).join("、"),
    item.cardTitle || ""
  ].join("\t"));
  return [header, ...rows].join("\n");
}

Page({
  data: {
    customers: [],
    filteredCustomers: [],
    activeIntent: "all",
    activeProfileFilter: "all",
    activeSourceFilter: "all",
    activeTagFilter: "all",
    activeSort: "intent",
    searchKeyword: "",
    intentFilters: INTENT_FILTERS,
    profileFilters: PROFILE_FILTERS,
    sourceFilters: [],
    tagFilters: [],
    sortOptions: SORT_OPTIONS,
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
        customerTags: item.customerTags || [],
        intentLevel: item.intentLevel || "待判断",
        updatedText: formatTime(item.updatedAt),
        lastViewedText: formatTime(item.lastViewedAt)
      })));
      this.setData({
        customers,
        filteredCustomers: applyCustomerView(
          customers,
          this.data.activeIntent,
          this.data.activeProfileFilter,
          this.data.searchKeyword,
          this.data.activeSort,
          this.data.activeSourceFilter,
          this.data.activeTagFilter
        ),
        sourceFilters: buildCountFilters(customers, (item) => item.cardTitle, "全部来源"),
        tagFilters: buildTagFilters(customers),
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
      filteredCustomers: applyCustomerView(
        this.data.customers,
        activeIntent,
        this.data.activeProfileFilter,
        this.data.searchKeyword,
        this.data.activeSort,
        this.data.activeSourceFilter,
        this.data.activeTagFilter
      )
    });
  },
  handleProfileFilterChange(event) {
    const activeProfileFilter = event.currentTarget.dataset.filter;
    this.setData({
      activeProfileFilter,
      filteredCustomers: applyCustomerView(
        this.data.customers,
        this.data.activeIntent,
        activeProfileFilter,
        this.data.searchKeyword,
        this.data.activeSort,
        this.data.activeSourceFilter,
        this.data.activeTagFilter
      )
    });
  },
  handleSourceFilterChange(event) {
    const activeSourceFilter = event.currentTarget.dataset.filter;
    this.setData({
      activeSourceFilter,
      filteredCustomers: applyCustomerView(
        this.data.customers,
        this.data.activeIntent,
        this.data.activeProfileFilter,
        this.data.searchKeyword,
        this.data.activeSort,
        activeSourceFilter,
        this.data.activeTagFilter
      )
    });
  },
  handleTagFilterChange(event) {
    const activeTagFilter = event.currentTarget.dataset.filter;
    this.setData({
      activeTagFilter,
      filteredCustomers: applyCustomerView(
        this.data.customers,
        this.data.activeIntent,
        this.data.activeProfileFilter,
        this.data.searchKeyword,
        this.data.activeSort,
        this.data.activeSourceFilter,
        activeTagFilter
      )
    });
  },
  handleSortChange(event) {
    const activeSort = event.currentTarget.dataset.sort;
    this.setData({
      activeSort,
      filteredCustomers: applyCustomerView(
        this.data.customers,
        this.data.activeIntent,
        this.data.activeProfileFilter,
        this.data.searchKeyword,
        activeSort,
        this.data.activeSourceFilter,
        this.data.activeTagFilter
      )
    });
  },
  handleSearchChange(event) {
    const searchKeyword = event.detail.value;
    this.setData({
      searchKeyword,
      filteredCustomers: applyCustomerView(
        this.data.customers,
        this.data.activeIntent,
        this.data.activeProfileFilter,
        searchKeyword,
        this.data.activeSort,
        this.data.activeSourceFilter,
        this.data.activeTagFilter
      )
    });
  },
  handleClearSearch() {
    this.setData({
      searchKeyword: "",
      filteredCustomers: applyCustomerView(
        this.data.customers,
        this.data.activeIntent,
        this.data.activeProfileFilter,
        "",
        this.data.activeSort,
        this.data.activeSourceFilter,
        this.data.activeTagFilter
      )
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
  handleCopySummary() {
    const customers = this.data.filteredCustomers || [];
    if (!customers.length) {
      wx.showToast({ title: "暂无可复制客户", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: buildCustomerSummary(customers),
      success: () => wx.showToast({ title: `已复制${customers.length}条`, icon: "success" })
    });
  },
  handleOpenLead(event) {
    wx.navigateTo({ url: `/pages/lead-detail/index?id=${event.currentTarget.dataset.id}` });
  },
  handleOpenCard(event) {
    wx.navigateTo({ url: `/pages/card-view/index?id=${event.currentTarget.dataset.cardId}` });
  }
});
