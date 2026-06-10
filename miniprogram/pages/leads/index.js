const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

function filterLeads(leads, filter) {
  if (filter === "pending") return leads.filter((item) => item.status === "pending");
  if (filter === "contacted") return leads.filter((item) => item.status === "contacted");
  return leads;
}

function todayKey() {
  const date = new Date();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function getLeadDueState(lead) {
  if (lead.status === "contacted") return "done";
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
    const rankDiff = (rank[a.dueState] || 9) - (rank[b.dueState] || 9);
    if (rankDiff !== 0) return rankDiff;
    const aDate = a.nextFollowUpValue || "9999-12-31";
    const bDate = b.nextFollowUpValue || "9999-12-31";
    if (aDate !== bDate) return aDate > bDate ? 1 : -1;
    return String(b.updatedAt || "").localeCompare(String(a.updatedAt || ""));
  });
}

function applyFilters(leads, statusFilter, scheduleFilter) {
  return filterBySchedule(filterLeads(sortLeads(leads), statusFilter), scheduleFilter);
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

Page({
  data: {
    leads: [],
    filteredLeads: [],
    activeFilter: "pending",
    activeScheduleFilter: "all",
    filters: [
      { key: "pending", label: "待联系" },
      { key: "contacted", label: "已联系" },
      { key: "all", label: "全部" }
    ],
    scheduleFilters: [
      { key: "all", label: "全部时间" },
      { key: "today", label: "今日" },
      { key: "overdue", label: "逾期" },
      { key: "future", label: "未来" },
      { key: "unset", label: "未设置" }
    ],
    notes: {},
    followUps: {},
    nextFollowUpDates: {},
    summary: {
      pending: 0,
      contacted: 0,
      total: 0,
      today: 0,
      overdue: 0,
      unhandled: 0
    }
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
        statusText: item.status === "contacted" ? "已联系" : "待联系",
        noteValue: item.note || "",
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
      const notes = leads.reduce((memo, item) => {
        memo[item.id] = item.note || "";
        return memo;
      }, {});
      const nextFollowUpDates = leads.reduce((memo, item) => {
        memo[item.id] = item.nextFollowUpAt ? String(item.nextFollowUpAt).slice(0, 10) : "";
        return memo;
      }, {});
      this.setData({
        leads,
        notes,
        followUps: {},
        nextFollowUpDates,
        filteredLeads: applyFilters(leads, this.data.activeFilter, this.data.activeScheduleFilter),
        summary: {
          pending: leads.filter((item) => item.status === "pending").length,
          contacted: leads.filter((item) => item.status === "contacted").length,
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
    this.setData({
      activeFilter,
      filteredLeads: applyFilters(this.data.leads, activeFilter, this.data.activeScheduleFilter)
    });
  },
  handleScheduleFilterChange(event) {
    const activeScheduleFilter = event.currentTarget.dataset.filter;
    this.setData({
      activeScheduleFilter,
      filteredLeads: applyFilters(this.data.leads, this.data.activeFilter, activeScheduleFilter)
    });
  },
  handleReminderShortcut(event) {
    const shortcut = event.currentTarget.dataset.shortcut;
    if (shortcut === "today") {
      this.setData({
        activeFilter: "pending",
        activeScheduleFilter: "today",
        filteredLeads: applyFilters(this.data.leads, "pending", "today")
      });
      return;
    }
    if (shortcut === "overdue") {
      this.setData({
        activeFilter: "pending",
        activeScheduleFilter: "overdue",
        filteredLeads: applyFilters(this.data.leads, "pending", "overdue")
      });
      return;
    }
    this.setData({
      activeFilter: "pending",
      activeScheduleFilter: "all",
      filteredLeads: applyFilters(this.data.leads, "pending", "all")
    });
  },
  handleNoteChange(event) {
    const id = event.currentTarget.dataset.id;
    this.setData({ [`notes.${id}`]: event.detail.value });
  },
  handleFollowUpChange(event) {
    const id = event.currentTarget.dataset.id;
    this.setData({ [`followUps.${id}`]: event.detail.value });
  },
  handleNextFollowUpChange(event) {
    const id = event.currentTarget.dataset.id;
    const value = event.detail.value;
    const leads = this.data.leads.map((item) => (
      item.id === id ? {
        ...item,
        nextFollowUpValue: value,
        nextFollowUpDisplay: value,
        dueState: getLeadDueState({ ...item, nextFollowUpValue: value }),
        dueStateText: dueStateText(getLeadDueState({ ...item, nextFollowUpValue: value }))
      } : item
    ));
    this.setData({
      leads,
      filteredLeads: applyFilters(leads, this.data.activeFilter, this.data.activeScheduleFilter),
      [`nextFollowUpDates.${id}`]: value
    });
  },
  async handleSaveNote(event) {
    const currentUser = getCurrentUser();
    const id = event.currentTarget.dataset.id;
    try {
      await api.updateLeadReminder(id, {
        ownerUserId: currentUser.id,
        note: (this.data.notes || {})[id] || ""
      });
      wx.showToast({ title: "备注已保存", icon: "success" });
      this.loadLeads();
    } catch (error) {
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
    }
  },
  async handleSaveFollowUp(event) {
    const currentUser = getCurrentUser();
    const id = event.currentTarget.dataset.id;
    const logContent = ((this.data.followUps || {})[id] || "").trim();
    const nextFollowUpAt = (this.data.nextFollowUpDates || {})[id] || "";
    if (!logContent && !nextFollowUpAt) {
      wx.showToast({ title: "请填写跟进记录或时间", icon: "none" });
      return;
    }
    try {
      await api.updateLeadReminder(id, {
        ownerUserId: currentUser.id,
        nextFollowUpAt,
        logContent
      });
      wx.showToast({ title: "跟进已保存", icon: "success" });
      this.loadLeads();
    } catch (error) {
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
    }
  },
  async handleMarkContacted(event) {
    const currentUser = getCurrentUser();
    try {
      await api.updateLeadReminder(event.currentTarget.dataset.id, {
        ownerUserId: currentUser.id,
        status: "contacted",
        note: (this.data.notes || {})[event.currentTarget.dataset.id] || ""
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
        status: "pending"
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
    wx.navigateTo({ url: `/pages/card-view/index?id=${event.currentTarget.dataset.cardId}` });
  },
  handleOpenManager(event) {
    wx.navigateTo({ url: `/pages/manager/index?id=${event.currentTarget.dataset.cardId}` });
  }
});
