const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");
const { navigateToResourceView } = require("../../utils/resource-navigation");

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

const STAGE_FILTERS = [
  { key: "all", label: "全部" },
  { key: "todo", label: "待处理" },
  { key: "today", label: "今日跟进" },
  { key: "contacted", label: "已联系" },
  { key: "closed", label: "已归档" }
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
  activeStageFilter: "all",
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

function decodeOption(value) {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch (error) {
    return value;
  }
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

function leadStatusText(status) {
  const map = {
    pending: "待联系",
    contacted: "已联系",
    invalid: "无效",
    paused: "暂不跟进",
    completed: "已完成"
  };
  return map[status] || "待联系";
}

function customerStage(item) {
  if (["invalid", "paused", "completed"].includes(item.status)) return "closed";
  if (item.status === "contacted") return "contacted";
  if (item.nextFollowUpAt && String(item.nextFollowUpAt).slice(0, 10) === todayValue()) return "today";
  return "todo";
}

function customerStageText(stage) {
  if (stage === "closed") return "已归档";
  if (stage === "contacted") return "已联系";
  if (stage === "today") return "今日跟进";
  return "待处理";
}

function nextActionText(item) {
  if (item.latestOrderId) return item.latestOrderStatus === "completed" ? "查看成交" : "处理订单";
  if (item.stage === "closed") return "查看归档";
  if (item.stage === "contacted") return "继续跟进";
  if (item.stage === "today") return "今日联系";
  if (item.customerPhone) return "立即外呼";
  if (item.customerWechat) return "复制微信";
  return "补充资料";
}

function normalizeSellerOrder(order = {}, index = 0) {
  const phone = String(order.phone || "").replace(/\s/g, "");
  const wechat = String(order.wechat || "").replace(/\s/g, "");
  const name = order.receiverName || order.buyerName || "客户";
  return {
    ...order,
    buyerDisplayName: name,
    avatarUrl: safeAvatarUrl(order.buyerAvatarUrl),
    avatarText: avatarText(name),
    displayPhone: phone,
    displayWechat: wechat,
    createdText: formatTime(order.createdAt),
    summaryText: [order.actionKindText, order.skuName, order.quantity ? `x ${order.quantity}` : ""].filter(Boolean).join(" · "),
    sourceText: order.title || "商品资料",
    tone: index % 4
  };
}

function buildOrderStageSummary(orders) {
  return [
    { key: "submitted", label: "待处理", count: orders.filter((item) => item.status === "submitted").length },
    { key: "contacted", label: "已联系", count: orders.filter((item) => item.status === "contacted").length },
    { key: "completed", label: "已成交", count: orders.filter((item) => item.status === "completed").length },
    { key: "cancelled", label: "已取消", count: orders.filter((item) => item.status === "cancelled").length }
  ];
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

function matchesStageFilter(item, filter) {
  return filter === "all" || item.stage === filter;
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

function buildSourceGroups(customers) {
  return buildCountFilters(customers, (item) => item.cardTitle || "未知来源", "全部来源")
    .filter((item) => item.key !== "all")
    .slice(0, 6)
    .map((item) => ({
      ...item,
      high: customers.filter((customer) => (customer.cardTitle || "未知来源") === item.key && customer.intentLevel === "高意向").length,
      pending: customers.filter((customer) => (customer.cardTitle || "未知来源") === item.key && customer.stage === "todo").length
    }));
}

function buildStageSummary(customers) {
  const counts = customers.reduce((memo, item) => {
    memo[item.stage] = (memo[item.stage] || 0) + 1;
    return memo;
  }, {});
  return STAGE_FILTERS.filter((item) => item.key !== "all").map((item) => ({
    ...item,
    count: counts[item.key] || 0
  }));
}

function filterCustomers(customers, intentFilter, keyword = "", profileFilter = "all", sourceFilter = "all", tagFilter = "all", activityFilter = "all", stageFilter = "all") {
  return customers.filter((item) => {
    const intentMatched = intentFilter === "all" || (item.intentLevel || "待判断") === intentFilter;
    return intentMatched &&
      matchesStageFilter(item, stageFilter) &&
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

function applyCustomerView(customers, intentFilter, profileFilter, keyword, sortMode, sourceFilter, tagFilter, activityFilter, stageFilter = "all") {
  return sortCustomers(filterCustomers(customers, intentFilter, keyword, profileFilter, sourceFilter, tagFilter, activityFilter, stageFilter), sortMode);
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

function buildActiveCustomerViewText(filters) {
  const profileOption = PROFILE_FILTERS.find((item) => item.key === filters.activeProfileFilter);
  const activityOption = ACTIVITY_FILTERS.find((item) => item.key === filters.activeActivityFilter);
  const stageOption = STAGE_FILTERS.find((item) => item.key === filters.activeStageFilter);
  const parts = [
    filters.activeSourceFilter !== "all" ? `来源：${filters.activeSourceFilter}` : "",
    filters.activeStageFilter !== "all" && stageOption ? stageOption.label : "",
    filters.activeIntent !== "all" ? filters.activeIntent : "",
    filters.activeProfileFilter !== "all" && profileOption ? profileOption.label : "",
    filters.activeActivityFilter !== "all" && activityOption ? activityOption.label : "",
    filters.activeTagFilter !== "all" ? `标签：${filters.activeTagFilter}` : "",
    filters.searchKeyword ? `搜索：${filters.searchKeyword}` : ""
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "全部客户";
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
  activeStageFilter: "all",
  activeSort: "intent",
    activeViewText: "全部客户",
    searchKeyword: "",
    intentFilters: INTENT_FILTERS,
    profileFilters: PROFILE_FILTERS,
    activityFilters: ACTIVITY_FILTERS,
    stageFilters: STAGE_FILTERS,
    sourceFilters: [],
    tagFilters: [],
    sourceGroups: [],
    stageSummary: [],
    sellerOrders: [],
    orderStageSummary: [],
    orderCustomerPreview: [],
    sortOptions: SORT_OPTIONS,
    savedViews: [],
    summary: {
      total: 0,
      high: 0,
      withPhone: 0,
      withWechat: 0,
      orderCount: 0,
      completedOrderCount: 0
    },
    customerDetailOpen: false,
    selectedCustomer: null
  },
  onLoad(options = {}) {
    const patch = {};
    const keyword = decodeOption(options.keyword);
    const source = decodeOption(options.source);
    const stage = decodeOption(options.stage);
    const intent = decodeOption(options.intent);
    if (keyword) patch.searchKeyword = keyword;
    if (source) patch.activeSourceFilter = source;
    if (stage) patch.activeStageFilter = stage;
    if (intent) patch.activeIntent = intent;
    if (Object.keys(patch).length) {
      this.setData({
        ...patch,
        activeViewText: buildActiveCustomerViewText({ ...this.getCurrentViewFilters(), ...patch })
      });
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
      const [leadRes, orderRes] = await Promise.all([
        api.fetchLeadReminders(currentUser.id),
        api.fetchOrders({ userId: currentUser.id, role: "seller" }).catch(() => ({ data: { orders: [] } }))
      ]);
      const sellerOrders = (((orderRes.data && orderRes.data.orders) || [])).map(normalizeSellerOrder);
      const ordersByContact = sellerOrders.reduce((memo, order) => {
        const keys = [order.displayPhone, order.displayWechat, order.buyerDisplayName].filter(Boolean);
        keys.forEach((key) => {
          if (!memo[key]) memo[key] = [];
          memo[key].push(order);
        });
        return memo;
      }, {});
      const customers = sortCustomers((leadRes.data || []).filter(hasProfile).map((item) => {
        const matchedOrders = [
          ...(ordersByContact[item.customerPhone] || []),
          ...(ordersByContact[item.customerWechat] || []),
          ...(ordersByContact[item.nickname] || [])
        ].filter((order, index, source) => source.findIndex((candidate) => candidate.id === order.id) === index);
        const latestOrder = matchedOrders[0] || null;
        return {
        ...item,
        avatarUrl: safeAvatarUrl(item.avatarUrl),
        avatarText: avatarText(item.nickname),
        statusText: leadStatusText(item.status),
        stage: customerStage(item),
        stageText: customerStageText(customerStage(item)),
        orderCount: matchedOrders.length,
        latestOrderId: latestOrder ? latestOrder.id : "",
        latestOrderStatus: latestOrder ? latestOrder.status : "",
        latestOrderText: latestOrder ? `${latestOrder.statusText} · ${latestOrder.summaryText}` : "",
        nextActionText: nextActionText({ ...item, stage: customerStage(item), latestOrderId: latestOrder ? latestOrder.id : "", latestOrderStatus: latestOrder ? latestOrder.status : "" }),
        customerTags: item.customerTags || [],
        intentLevel: item.intentLevel || "待判断",
        updatedText: formatTime(item.updatedAt),
        lastViewedText: item.lastViewedAt ? formatTime(item.lastViewedAt) : "",
        latestFollowUpText: getLatestFollowUpAt(item) ? formatTime(getLatestFollowUpAt(item)) : "",
        nextFollowUpText: item.nextFollowUpAt ? String(item.nextFollowUpAt).slice(0, 10) : "",
        latestFollowUp: (item.followUpLogs || [])[0] ? (item.followUpLogs || [])[0].content : ""
        };
      }));
      const viewFilters = this.getCurrentViewFilters();
      const filteredCustomers = applyCustomerView(
        customers,
        viewFilters.activeIntent,
        viewFilters.activeProfileFilter,
        viewFilters.searchKeyword,
        viewFilters.activeSort,
        viewFilters.activeSourceFilter,
        viewFilters.activeTagFilter,
        viewFilters.activeActivityFilter,
        viewFilters.activeStageFilter
      );
      this.setData({
        customers,
        filteredCustomers,
        activeViewText: buildActiveCustomerViewText(viewFilters),
        sourceFilters: buildCountFilters(customers, (item) => item.cardTitle, "全部来源"),
        tagFilters: buildTagFilters(customers),
        sourceGroups: buildSourceGroups(customers),
        stageSummary: buildStageSummary(customers),
        sellerOrders,
        orderStageSummary: buildOrderStageSummary(sellerOrders),
        orderCustomerPreview: sellerOrders.slice(0, 4),
        summary: {
          total: customers.length,
          high: customers.filter((item) => item.intentLevel === "高意向").length,
          withPhone: customers.filter((item) => item.customerPhone).length,
          withWechat: customers.filter((item) => item.customerWechat).length,
          orderCount: sellerOrders.length,
          completedOrderCount: sellerOrders.filter((item) => item.status === "completed").length
        }
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "客户资料加载失败", icon: "none" });
    }
  },
  handleIntentFilterChange(event) {
    this.commitCustomerView({ activeIntent: event.currentTarget.dataset.filter });
  },
  handleProfileFilterChange(event) {
    this.commitCustomerView({ activeProfileFilter: event.currentTarget.dataset.filter });
  },
  handleActivityFilterChange(event) {
    this.commitCustomerView({ activeActivityFilter: event.currentTarget.dataset.filter });
  },
  handleStageFilterChange(event) {
    this.commitCustomerView({ activeStageFilter: event.currentTarget.dataset.filter });
  },
  handleSourceFilterChange(event) {
    this.commitCustomerView({ activeSourceFilter: event.currentTarget.dataset.filter });
  },
  handleTagFilterChange(event) {
    this.commitCustomerView({ activeTagFilter: event.currentTarget.dataset.filter });
  },
  handleSortChange(event) {
    this.commitCustomerView({ activeSort: event.currentTarget.dataset.sort });
  },
  handleSearchChange(event) {
    this.commitCustomerView({ searchKeyword: event.detail.value });
  },
  handleClearSearch() {
    this.commitCustomerView({ searchKeyword: "" });
  },
  handleResetFilters() {
    this.commitCustomerView({ ...DEFAULT_VIEW_FILTERS });
  },
  commitCustomerView(nextFilters = {}) {
    const filters = { ...this.getCurrentViewFilters(), ...nextFilters };
    this.setData({
      ...nextFilters,
      filteredCustomers: applyCustomerView(
        this.data.customers,
        filters.activeIntent,
        filters.activeProfileFilter,
        filters.searchKeyword,
        filters.activeSort,
        filters.activeSourceFilter,
        filters.activeTagFilter,
        filters.activeActivityFilter,
        filters.activeStageFilter || "all"
      ),
      activeViewText: buildActiveCustomerViewText(filters)
    });
  },
  getCurrentViewFilters() {
    return {
      activeIntent: this.data.activeIntent,
      activeProfileFilter: this.data.activeProfileFilter,
      activeSourceFilter: this.data.activeSourceFilter,
      activeTagFilter: this.data.activeTagFilter,
      activeActivityFilter: this.data.activeActivityFilter,
      activeStageFilter: this.data.activeStageFilter,
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
    this.commitCustomerView(filters);
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
  handleOpenCustomerSheet(event) {
    const customerId = event.currentTarget.dataset.id;
    const customer = (this.data.filteredCustomers || []).find((item) => item.id === customerId);
    if (!customer) return;
    this.setData({
      selectedCustomer: customer,
      customerDetailOpen: true
    });
  },
  handleCloseCustomerSheet() {
    this.setData({
      selectedCustomer: null,
      customerDetailOpen: false
    });
  },
  noop() {},
  handleSelectedPrimaryAction() {
    const customer = this.data.selectedCustomer;
    if (!customer) return;
    if (customer.latestOrderId) {
      wx.navigateTo({ url: `/pages/order-detail/index?id=${customer.latestOrderId}&role=seller` });
      return;
    }
    if (customer.customerPhone) {
      wx.makePhoneCall({
        phoneNumber: customer.customerPhone,
        fail: () => wx.showToast({ title: "拨号失败", icon: "none" })
      });
      return;
    }
    if (customer.customerWechat) {
      wx.setClipboardData({
        data: customer.customerWechat,
        success: () => wx.showToast({ title: "微信已复制", icon: "success" })
      });
      return;
    }
    wx.navigateTo({ url: `/pages/lead-detail/index?id=${customer.id}` });
  },
  handleOpenSelectedLead() {
    const customer = this.data.selectedCustomer;
    if (!customer) return;
    wx.navigateTo({ url: `/pages/lead-detail/index?id=${customer.id}` });
  },
  handleOpenSelectedCard() {
    const customer = this.data.selectedCustomer;
    if (!customer || !customer.cardId) return;
    navigateToResourceView(customer.cardId);
  },
  handleOpenOrder(event) {
    const orderId = event.currentTarget.dataset.id;
    if (!orderId) return;
    wx.navigateTo({ url: `/pages/order-detail/index?id=${orderId}&role=seller` });
  },
  handleOpenLatestOrder(event) {
    const customer = (this.data.filteredCustomers || []).find((item) => item.id === event.currentTarget.dataset.id);
    if (!customer || !customer.latestOrderId) {
      this.handleOpenLead(event);
      return;
    }
    wx.navigateTo({ url: `/pages/order-detail/index?id=${customer.latestOrderId}&role=seller` });
  },
  handleSourceGroupTap(event) {
    const source = event.currentTarget.dataset.source;
    this.commitCustomerView({ activeSourceFilter: source });
  },
  handleOpenFilteredLeads() {
    const source = this.data.activeSourceFilter !== "all" ? this.data.activeSourceFilter : "";
    const stage = this.data.activeStageFilter;
    const statusMap = {
      todo: "pending",
      contacted: "contacted",
      closed: "closed"
    };
    const query = [
      source ? `source=${encodeURIComponent(source)}` : "",
      statusMap[stage] ? `status=${statusMap[stage]}` : "",
      stage === "today" ? "schedule=today" : ""
    ].filter(Boolean).join("&");
    wx.navigateTo({ url: `/pages/leads/index${query ? `?${query}` : ""}` });
  },
  handleOpenFilteredOrders() {
    const source = this.data.activeSourceFilter !== "all" ? this.data.activeSourceFilter : "";
    const query = source ? `?role=seller&source=${encodeURIComponent(source)}` : "?role=seller";
    wx.navigateTo({ url: `/pages/orders/index${query}` });
  },
  handleStageSummaryTap(event) {
    this.handleStageFilterChange(event);
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
    navigateToResourceView(event.currentTarget.dataset.cardId);
  }
});
