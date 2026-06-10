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

const ACTIVITY_FILTERS = [
  { key: "all", label: "全部活跃" },
  { key: "recent-viewed", label: "近7天查看" },
  { key: "recent-followed", label: "近7天跟进" },
  { key: "dormant", label: "14天未跟进" }
];

const RECENT_DAYS = 7;
const DORMANT_DAYS = 14;
const DAY_MS = 24 * 60 * 60 * 1000;

const DEFAULT_VIEW_FILTERS = {
  activeIntent: "all",
  activeProfileFilter: "all",
  activeSourceFilter: "all",
  activeTagFilter: "all",
  activeActivityFilter: "all",
  activeSort: "intent",
  searchKeyword: ""
};

function savedViewsKey(ownerUserId) {
  return `customerSavedViews_${ownerUserId || "guest"}`;
}

function todayValue() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function daysSince(value) {
  if (!value) return null;
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return null;
  return Math.floor((Date.now() - time) / DAY_MS);
}

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

function getLatestFollowUpAt(item) {
  const latestLog = (item.followUpLogs || [])[0];
  return latestLog ? latestLog.createdAt : "";
}

function matchesActivityFilter(item, filter) {
  if (filter === "recent-viewed") {
    const viewedDays = daysSince(item.lastViewedAt);
    return viewedDays !== null && viewedDays <= RECENT_DAYS;
  }
  if (filter === "recent-followed") {
    const followUpDays = daysSince(getLatestFollowUpAt(item));
    return followUpDays !== null && followUpDays <= RECENT_DAYS;
  }
  if (filter === "dormant") {
    const followUpDays = daysSince(getLatestFollowUpAt(item));
    return !["invalid", "completed"].includes(item.status) && (followUpDays === null || followUpDays >= DORMANT_DAYS);
  }
  return true;
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

function filterCustomers(customers, intentFilter, keyword = "", profileFilter = "all", sourceFilter = "all", tagFilter = "all", activityFilter = "all") {
  return customers.filter((item) => {
    const intentMatched = intentFilter === "all" || (item.intentLevel || "待判断") === intentFilter;
    return intentMatched &&
      matchesProfileFilter(item, profileFilter) &&
      matchesSourceFilter(item, sourceFilter) &&
      matchesTagFilter(item, tagFilter) &&
      matchesActivityFilter(item, activityFilter) &&
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

function applyCustomerView(customers, intentFilter, profileFilter, keyword, sortMode, sourceFilter, tagFilter, activityFilter) {
  return sortCustomers(filterCustomers(customers, intentFilter, keyword, profileFilter, sourceFilter, tagFilter, activityFilter), sortMode);
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

function buildFollowUpList(customers) {
  return customers.map((item, index) => [
    `${index + 1}. ${item.nickname || "未命名客户"}（${item.intentLevel || "待判断"}）`,
    item.customerPhone ? `电话：${item.customerPhone}` : "",
    item.customerWechat ? `微信：${item.customerWechat}` : "",
    item.latestFollowUp ? `最近跟进：${item.latestFollowUp}` : "最近跟进：暂无",
    item.nextFollowUpText ? `下次跟进：${item.nextFollowUpText}` : "下次跟进：未设置",
    item.cardTitle ? `来源：${item.cardTitle}` : ""
  ].filter(Boolean).join("\n"));
}

function buildViewName(filters) {
  const profileOption = PROFILE_FILTERS.find((item) => item.key === filters.activeProfileFilter);
  const activityOption = ACTIVITY_FILTERS.find((item) => item.key === filters.activeActivityFilter);
  const parts = [
    filters.activeIntent !== "all" ? filters.activeIntent : "",
    filters.activeProfileFilter !== "all" && profileOption ? profileOption.label : "",
    filters.activeActivityFilter !== "all" && activityOption ? activityOption.label : "",
    filters.activeSourceFilter !== "all" ? filters.activeSourceFilter : "",
    filters.activeTagFilter !== "all" ? filters.activeTagFilter : "",
    filters.searchKeyword ? `搜索:${filters.searchKeyword}` : ""
  ].filter(Boolean);
  return parts.length ? parts.join(" + ") : "全部客户";
}

Page({
  data: {
    customers: [],
    filteredCustomers: [],
    activeIntent: "all",
    activeProfileFilter: "all",
    activeSourceFilter: "all",
    activeTagFilter: "all",
    activeActivityFilter: "all",
    activeSort: "intent",
    searchKeyword: "",
    intentFilters: INTENT_FILTERS,
    profileFilters: PROFILE_FILTERS,
    activityFilters: ACTIVITY_FILTERS,
    sourceFilters: [],
    tagFilters: [],
    sortOptions: SORT_OPTIONS,
    savedViews: [],
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
    this.loadSavedViews(currentUser.id);
    this.loadCustomers();
  },
  loadSavedViews(ownerUserId) {
    const savedViews = wx.getStorageSync(savedViewsKey(ownerUserId)) || [];
    this.setData({ savedViews });
  },
  persistSavedViews(savedViews) {
    const currentUser = getCurrentUser();
    wx.setStorageSync(savedViewsKey(currentUser ? currentUser.id : ""), savedViews);
    this.setData({ savedViews });
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
        lastViewedText: item.lastViewedAt ? formatTime(item.lastViewedAt) : "",
        latestFollowUpText: getLatestFollowUpAt(item) ? formatTime(getLatestFollowUpAt(item)) : "",
        nextFollowUpText: item.nextFollowUpAt ? String(item.nextFollowUpAt).slice(0, 10) : "",
        latestFollowUp: (item.followUpLogs || [])[0] ? (item.followUpLogs || [])[0].content : ""
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
          this.data.activeTagFilter,
          this.data.activeActivityFilter
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
        this.data.activeTagFilter,
        this.data.activeActivityFilter
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
        this.data.activeTagFilter,
        this.data.activeActivityFilter
      )
    });
  },
  handleActivityFilterChange(event) {
    const activeActivityFilter = event.currentTarget.dataset.filter;
    this.setData({
      activeActivityFilter,
      filteredCustomers: applyCustomerView(
        this.data.customers,
        this.data.activeIntent,
        this.data.activeProfileFilter,
        this.data.searchKeyword,
        this.data.activeSort,
        this.data.activeSourceFilter,
        this.data.activeTagFilter,
        activeActivityFilter
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
        this.data.activeTagFilter,
        this.data.activeActivityFilter
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
        activeTagFilter,
        this.data.activeActivityFilter
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
        this.data.activeTagFilter,
        this.data.activeActivityFilter
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
        this.data.activeTagFilter,
        this.data.activeActivityFilter
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
        this.data.activeTagFilter,
        this.data.activeActivityFilter
      )
    });
  },
  handleResetFilters() {
    this.setData({
      ...DEFAULT_VIEW_FILTERS,
      filteredCustomers: applyCustomerView(
        this.data.customers,
        DEFAULT_VIEW_FILTERS.activeIntent,
        DEFAULT_VIEW_FILTERS.activeProfileFilter,
        DEFAULT_VIEW_FILTERS.searchKeyword,
        DEFAULT_VIEW_FILTERS.activeSort,
        DEFAULT_VIEW_FILTERS.activeSourceFilter,
        DEFAULT_VIEW_FILTERS.activeTagFilter,
        DEFAULT_VIEW_FILTERS.activeActivityFilter
      )
    });
  },
  getCurrentViewFilters() {
    return {
      activeIntent: this.data.activeIntent,
      activeProfileFilter: this.data.activeProfileFilter,
      activeSourceFilter: this.data.activeSourceFilter,
      activeTagFilter: this.data.activeTagFilter,
      activeActivityFilter: this.data.activeActivityFilter,
      activeSort: this.data.activeSort,
      searchKeyword: this.data.searchKeyword
    };
  },
  handleSaveCurrentView() {
    const filters = this.getCurrentViewFilters();
    wx.showModal({
      title: "保存常用视图",
      editable: true,
      placeholderText: buildViewName(filters),
      confirmText: "保存",
      success: (res) => {
        if (!res.confirm) return;
        const name = String(res.content || "").trim() || buildViewName(filters);
        const savedViews = [
          { id: `view_${Date.now()}`, name, filters },
          ...(this.data.savedViews || []).filter((item) => item.name !== name)
        ].slice(0, 8);
        this.persistSavedViews(savedViews);
        wx.showToast({ title: "视图已保存", icon: "success" });
      }
    });
  },
  handleApplySavedView(event) {
    const viewId = event.currentTarget.dataset.id;
    const view = (this.data.savedViews || []).find((item) => item.id === viewId);
    if (!view) return;
    const filters = { ...DEFAULT_VIEW_FILTERS, ...(view.filters || {}) };
    this.setData({
      ...filters,
      filteredCustomers: applyCustomerView(
        this.data.customers,
        filters.activeIntent,
        filters.activeProfileFilter,
        filters.searchKeyword,
        filters.activeSort,
        filters.activeSourceFilter,
        filters.activeTagFilter,
        filters.activeActivityFilter
      )
    });
  },
  handleRemoveSavedView(event) {
    const viewId = event.currentTarget.dataset.id;
    const savedViews = (this.data.savedViews || []).filter((item) => item.id !== viewId);
    this.persistSavedViews(savedViews);
    wx.showToast({ title: "已移除视图", icon: "success" });
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
  handleCopyFollowUpList() {
    const customers = this.data.filteredCustomers || [];
    if (!customers.length) {
      wx.showToast({ title: "暂无可复制清单", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: buildFollowUpList(customers).join("\n\n"),
      success: () => wx.showToast({ title: `已复制${customers.length}条`, icon: "success" })
    });
  },
  async updateCustomerLead(reminderId, payload, successTitle) {
    const currentUser = getCurrentUser();
    try {
      await api.updateLeadReminder(reminderId, {
        ownerUserId: currentUser.id,
        ...payload
      });
      wx.showToast({ title: successTitle, icon: "success" });
      this.loadCustomers();
    } catch (error) {
      wx.showToast({ title: error.detail || "操作失败", icon: "none" });
    }
  },
  handleSetTodayFollowUp(event) {
    const reminderId = event.currentTarget.dataset.id;
    this.updateCustomerLead(reminderId, { nextFollowUpAt: todayValue() }, "已设今日跟进");
  },
  handleQuickFollowUp(event) {
    const reminderId = event.currentTarget.dataset.id;
    wx.showModal({
      title: "添加跟进记录",
      editable: true,
      placeholderText: "例如：已电话沟通，约明天看资料",
      confirmText: "保存",
      success: (res) => {
        const content = String(res.content || "").trim();
        if (!res.confirm) return;
        if (!content) {
          wx.showToast({ title: "请填写跟进记录", icon: "none" });
          return;
        }
        this.updateCustomerLead(reminderId, { logContent: content }, "跟进已保存");
      }
    });
  },
  handleMarkContacted(event) {
    const reminderId = event.currentTarget.dataset.id;
    this.updateCustomerLead(reminderId, { status: "contacted" }, "已标记联系");
  },
  handleOpenLead(event) {
    wx.navigateTo({ url: `/pages/lead-detail/index?id=${event.currentTarget.dataset.id}` });
  },
  handleOpenCard(event) {
    wx.navigateTo({ url: `/pages/card-view/index?id=${event.currentTarget.dataset.cardId}` });
  }
});
