const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");
const { navigateToResourceView } = require("../../utils/resource-navigation");

function filterLeads(leads, filter) {
  if (filter === "pending") return leads.filter((item) => item.status === "pending");
  if (filter === "contacted") return leads.filter((item) => item.status === "contacted");
  if (filter === "closed") return leads.filter((item) => item.isClosed);
  return leads;
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

function todayKey() {
  const date = new Date();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function getLeadDueState(lead) {
  if (lead.status === "contacted" || lead.isClosed) return "done";
  if (!lead.nextFollowUpValue) return "unset";
  const today = todayKey();
  if (lead.nextFollowUpValue < today) return "overdue";
  if (lead.nextFollowUpValue === today) return "today";
  return "future";
}

function filterBySchedule(leads, filter) {
  if (filter === "all") return leads;
  return leads.filter((item) => item.dueState === filter);
}

function sortLeads(leads) {
  const rank = { overdue: 0, today: 1, future: 2, unset: 3, done: 4 };
  return [...leads].sort((a, b) => {
    const rankDiff = (rank[a.dueState] ?? 9) - (rank[b.dueState] ?? 9);
    if (rankDiff !== 0) return rankDiff;
    const aDate = a.nextFollowUpValue || "9999-12-31";
    const bDate = b.nextFollowUpValue || "9999-12-31";
    if (aDate !== bDate) return aDate > bDate ? 1 : -1;
    return String(b.updatedAt || "").localeCompare(String(a.updatedAt || ""));
  });
}

function buildSourceGroups(leads) {
  const groups = leads.reduce((memo, item) => {
    const key = item.cardTitle || "未知来源";
    if (!memo[key]) {
      memo[key] = {
        key,
        title: key,
        total: 0,
        pending: 0,
        today: 0,
        overdue: 0,
        high: 0
      };
    }
    memo[key].total += 1;
    if (item.status === "pending") memo[key].pending += 1;
    if (item.dueState === "today") memo[key].today += 1;
    if (item.dueState === "overdue") memo[key].overdue += 1;
    if (item.intentLevel === "高意向") memo[key].high += 1;
    return memo;
  }, {});
  return Object.values(groups)
    .sort((a, b) => (b.overdue + b.today + b.pending) - (a.overdue + a.today + a.pending))
    .slice(0, 6);
}

function buildPriorityLeads(leads) {
  return sortLeads(leads)
    .filter((item) => item.status === "pending" || item.dueState === "today" || item.dueState === "overdue")
    .slice(0, 4);
}

function applyFilters(leads, statusFilter, scheduleFilter, sourceFilter = "all") {
  const sourceFiltered = sourceFilter === "all"
    ? leads
    : leads.filter((item) => (item.cardTitle || "未知来源") === sourceFilter);
  return filterBySchedule(filterLeads(sortLeads(sourceFiltered), statusFilter), scheduleFilter);
}

function filterLabel(options, key, fallback) {
  const match = options.find((item) => item.key === key);
  return match ? match.label : fallback;
}

function decodeOption(value) {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch (error) {
    return value;
  }
}

function buildActiveViewText(statusFilter, scheduleFilter, sourceFilter) {
  const parts = [];
  if (sourceFilter && sourceFilter !== "all") parts.push(`来源：${sourceFilter}`);
  if (statusFilter && statusFilter !== "all") {
    parts.push(filterLabel([
      { key: "pending", label: "待联系" },
      { key: "contacted", label: "已联系" },
      { key: "closed", label: "已归档" }
    ], statusFilter, statusFilter));
  }
  if (scheduleFilter && scheduleFilter !== "all") {
    parts.push(filterLabel([
      { key: "today", label: "今日" },
      { key: "overdue", label: "逾期" },
      { key: "future", label: "未来" },
      { key: "unset", label: "未设置时间" }
    ], scheduleFilter, scheduleFilter));
  }
  return parts.length ? parts.join(" · ") : "全部线索";
}

function formatDate(value) {
  if (!value) return "设置下次跟进";
  return String(value).slice(0, 10);
}

function dueStateText(state) {
  if (state === "overdue") return "已逾期";
  if (state === "today") return "今日跟进";
  if (state === "future") return "未来跟进";
  if (state === "done") return "已联系";
  return "未设置跟进时间";
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

Page({
  data: {
    leads: [],
    filteredLeads: [],
    activeFilter: "pending",
    activeScheduleFilter: "all",
    activeSourceFilter: "all",
    activeViewText: "待联系",
    filters: [
      { key: "pending", label: "待联系" },
      { key: "contacted", label: "已联系" },
      { key: "closed", label: "已归档" },
      { key: "all", label: "全部" }
    ],
    scheduleFilters: [
      { key: "all", label: "全部时间" },
      { key: "today", label: "今日" },
      { key: "overdue", label: "逾期" },
      { key: "future", label: "未来" },
      { key: "unset", label: "未设置" }
    ],
    summary: {
      pending: 0,
      contacted: 0,
      total: 0,
      today: 0,
      overdue: 0,
      unhandled: 0
    },
    sourceGroups: [],
    priorityLeads: [],
    leadDetailOpen: false,
    selectedLead: null
  },
  onLoad(options = {}) {
    const source = decodeOption(options.source);
    const status = decodeOption(options.status);
    const schedule = decodeOption(options.schedule);
    const activeFilter = status || this.data.activeFilter;
    const activeScheduleFilter = schedule || this.data.activeScheduleFilter;
    const activeSourceFilter = source || this.data.activeSourceFilter;
    this.setData({
      activeFilter,
      activeScheduleFilter,
      activeSourceFilter,
      activeViewText: buildActiveViewText(activeFilter, activeScheduleFilter, activeSourceFilter)
    });
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadLeads();
  },
  async loadLeads() {
    const currentUser = getCurrentUser();
    try {
      const res = await api.fetchLeadReminders(currentUser.id);
      const leads = (res.data || []).map((item) => ({
        ...item,
        avatarUrl: safeAvatarUrl(item.avatarUrl),
        avatarText: avatarText(item.nickname),
        isClosed: ["invalid", "paused", "completed"].includes(item.status),
        statusText: leadStatusText(item.status),
        noteValue: item.note || "",
        conclusionReasonValue: item.conclusionReason || "",
        nextFollowUpValue: item.nextFollowUpAt ? String(item.nextFollowUpAt).slice(0, 10) : "",
        nextFollowUpDisplay: formatDate(item.nextFollowUpAt),
        latestFollowUp: (item.followUpLogs || [])[0] || null,
        followUpLogsPreview: (item.followUpLogs || []).slice(0, 3).map((log) => ({
          ...log,
          createdText: formatTime(log.createdAt)
        })),
        updatedText: formatTime(item.updatedAt),
        lastViewedText: formatTime(item.lastViewedAt)
      })).map((item) => ({
        ...item,
        dueState: getLeadDueState(item),
        dueStateText: dueStateText(getLeadDueState(item))
      }));
      this.setData({
        leads,
        filteredLeads: applyFilters(leads, this.data.activeFilter, this.data.activeScheduleFilter, this.data.activeSourceFilter),
        activeViewText: buildActiveViewText(this.data.activeFilter, this.data.activeScheduleFilter, this.data.activeSourceFilter),
        sourceGroups: buildSourceGroups(leads),
        priorityLeads: buildPriorityLeads(leads),
        summary: {
          pending: leads.filter((item) => item.status === "pending").length,
          contacted: leads.filter((item) => item.status === "contacted").length,
          closed: leads.filter((item) => item.isClosed).length,
          total: leads.length,
          today: leads.filter((item) => item.dueState === "today").length,
          overdue: leads.filter((item) => item.dueState === "overdue").length,
          unhandled: leads.filter((item) => item.status === "pending").length
        }
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "待联系加载失败", icon: "none" });
    }
  },
  handleFilterChange(event) {
    const activeFilter = event.currentTarget.dataset.filter;
    const activeScheduleFilter = ["contacted", "closed"].includes(activeFilter) ? "all" : this.data.activeScheduleFilter;
    this.setData({
      activeFilter,
      activeScheduleFilter,
      filteredLeads: applyFilters(this.data.leads, activeFilter, activeScheduleFilter, this.data.activeSourceFilter),
      activeViewText: buildActiveViewText(activeFilter, activeScheduleFilter, this.data.activeSourceFilter)
    });
  },
  handleScheduleFilterChange(event) {
    const activeScheduleFilter = event.currentTarget.dataset.filter;
    this.setData({
      activeScheduleFilter,
      filteredLeads: applyFilters(this.data.leads, this.data.activeFilter, activeScheduleFilter, this.data.activeSourceFilter),
      activeViewText: buildActiveViewText(this.data.activeFilter, activeScheduleFilter, this.data.activeSourceFilter)
    });
  },
  handleReminderShortcut(event) {
    const shortcut = event.currentTarget.dataset.shortcut;
    if (shortcut === "today") {
      this.setData({
        activeFilter: "pending",
        activeScheduleFilter: "today",
        activeSourceFilter: "all",
        filteredLeads: applyFilters(this.data.leads, "pending", "today", "all"),
        activeViewText: buildActiveViewText("pending", "today", "all")
      });
      return;
    }
    if (shortcut === "overdue") {
      this.setData({
        activeFilter: "pending",
        activeScheduleFilter: "overdue",
        activeSourceFilter: "all",
        filteredLeads: applyFilters(this.data.leads, "pending", "overdue", "all"),
        activeViewText: buildActiveViewText("pending", "overdue", "all")
      });
      return;
    }
    this.setData({
      activeFilter: "pending",
      activeScheduleFilter: "all",
      activeSourceFilter: "all",
      filteredLeads: applyFilters(this.data.leads, "pending", "all", "all"),
      activeViewText: buildActiveViewText("pending", "all", "all")
    });
  },
  handleSourceGroupTap(event) {
    const source = event.currentTarget.dataset.source;
    if (!source) return;
    this.setData({
      activeFilter: "all",
      activeScheduleFilter: "all",
      activeSourceFilter: source,
      filteredLeads: applyFilters(this.data.leads, "all", "all", source),
      activeViewText: buildActiveViewText("all", "all", source)
    });
  },
  handleClearLeadFilters() {
    this.setData({
      activeFilter: "pending",
      activeScheduleFilter: "all",
      activeSourceFilter: "all",
      filteredLeads: applyFilters(this.data.leads, "pending", "all", "all"),
      activeViewText: buildActiveViewText("pending", "all", "all")
    });
  },
  async handleMarkContacted(event) {
    const currentUser = getCurrentUser();
    try {
      await api.updateLeadReminder(event.currentTarget.dataset.id, {
        ownerUserId: currentUser.id,
        status: "contacted"
      });
      wx.showToast({ title: "已联系", icon: "success" });
      this.loadLeads();
    } catch (error) {
      wx.showToast({ title: error.detail || "操作失败", icon: "none" });
    }
  },
  async handleRestorePending(event) {
    const currentUser = getCurrentUser();
    try {
      await api.updateLeadReminder(event.currentTarget.dataset.id, {
        ownerUserId: currentUser.id,
        status: "pending",
        conclusionReason: ""
      });
      wx.showToast({ title: "已恢复待联系", icon: "success" });
      this.loadLeads();
    } catch (error) {
      wx.showToast({ title: error.detail || "操作失败", icon: "none" });
    }
  },
  async handleDelete(event) {
    const currentUser = getCurrentUser();
    try {
      await api.deleteLeadReminder(event.currentTarget.dataset.id, currentUser.id);
      wx.showToast({ title: "已清除", icon: "success" });
      this.loadLeads();
    } catch (error) {
      wx.showToast({ title: error.detail || "清除失败", icon: "none" });
    }
  },
  handleOpenDetail(event) {
    navigateToResourceView(event.currentTarget.dataset.cardId);
  },
  handleOpenManager(event) {
    wx.navigateTo({ url: `/pages/manager/index?id=${event.currentTarget.dataset.cardId}` });
  },
  handleOpenLeadDetail(event) {
    wx.navigateTo({ url: `/pages/lead-detail/index?id=${event.currentTarget.dataset.id}` });
  },
  handleOpenLeadSheet(event) {
    const leadId = event.currentTarget.dataset.id;
    const lead = (this.data.filteredLeads || []).find((item) => item.id === leadId);
    if (!lead) return;
    this.setData({
      selectedLead: lead,
      leadDetailOpen: true
    });
  },
  handleCloseLeadSheet() {
    this.setData({
      selectedLead: null,
      leadDetailOpen: false
    });
  },
  noop() {},
  handleOpenSelectedLeadDetail() {
    const lead = this.data.selectedLead;
    if (!lead) return;
    wx.navigateTo({ url: `/pages/lead-detail/index?id=${lead.id}` });
  },
  handleOpenSelectedSource() {
    const lead = this.data.selectedLead;
    if (!lead || !lead.cardId) return;
    navigateToResourceView(lead.cardId);
  },
  handleSelectedLeadPrimaryAction() {
    const lead = this.data.selectedLead;
    if (!lead) return;
    if (lead.customerPhone) {
      wx.makePhoneCall({
        phoneNumber: lead.customerPhone,
        success: () => this.confirmMarkContacted(lead.id),
        fail: () => wx.showToast({ title: "拨号失败", icon: "none" })
      });
      return;
    }
    if (lead.customerWechat) {
      wx.setClipboardData({
        data: lead.customerWechat,
        success: () => wx.showToast({ title: "微信已复制", icon: "success" })
      });
      return;
    }
    wx.navigateTo({ url: `/pages/lead-detail/index?id=${lead.id}` });
  },
  handleCallPhone(event) {
    const phone = event.currentTarget.dataset.phone;
    const id = event.currentTarget.dataset.id;
    if (!phone) {
      wx.showToast({ title: "暂无手机号", icon: "none" });
      return;
    }
    wx.makePhoneCall({
      phoneNumber: phone,
      success: () => this.confirmMarkContacted(id),
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
  },
  confirmMarkContacted(id) {
    if (!id) return;
    wx.showModal({
      title: "是否标记已联系？",
      content: "如果这通电话已经沟通过，可以顺手记录到线索里。",
      confirmText: "标记",
      confirmColor: "#11924d",
      success: async (res) => {
        if (!res.confirm) return;
        const currentUser = getCurrentUser();
        try {
          await api.updateLeadReminder(id, {
            ownerUserId: currentUser.id,
            status: "contacted",
            logContent: "已电话联系客户"
          });
          wx.showToast({ title: "已标记联系", icon: "success" });
          this.loadLeads();
        } catch (error) {
          wx.showToast({ title: error.detail || "更新失败", icon: "none" });
        }
      }
    });
  },
  handleOpenCustomers() {
    wx.navigateTo({ url: "/pages/customers/index" });
  }
});
