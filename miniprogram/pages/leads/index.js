const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

function filterLeads(leads, filter) {
  if (filter === "pending") return leads.filter((item) => item.status === "pending");
  if (filter === "contacted") return leads.filter((item) => item.status === "contacted");
  return leads;
}

Page({
  data: {
    leads: [],
    filteredLeads: [],
    activeFilter: "pending",
    filters: [
      { key: "pending", label: "待联系" },
      { key: "contacted", label: "已联系" },
      { key: "all", label: "全部" }
    ],
    notes: {},
    summary: {
      pending: 0,
      contacted: 0,
      total: 0
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
        updatedText: formatTime(item.updatedAt),
        lastViewedText: formatTime(item.lastViewedAt)
      }));
      const notes = leads.reduce((memo, item) => {
        memo[item.id] = item.note || "";
        return memo;
      }, {});
      this.setData({
        leads,
        notes,
        filteredLeads: filterLeads(leads, this.data.activeFilter),
        summary: {
          pending: leads.filter((item) => item.status === "pending").length,
          contacted: leads.filter((item) => item.status === "contacted").length,
          total: leads.length
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
      filteredLeads: filterLeads(this.data.leads, activeFilter)
    });
  },
  handleNoteChange(event) {
    const id = event.currentTarget.dataset.id;
    this.setData({ [`notes.${id}`]: event.detail.value });
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
  handleOpenCard(event) {
    wx.navigateTo({ url: `/pages/manager/index?id=${event.currentTarget.dataset.cardId}` });
  }
});
