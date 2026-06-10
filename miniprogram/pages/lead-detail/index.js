const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

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

function formatDate(value) {
  return value ? String(value).slice(0, 10) : "设置下次跟进";
}

Page({
  data: {
    leadId: "",
    lead: null,
    note: "",
    followUp: "",
    nextFollowUpAt: "",
    conclusionReason: ""
  },
  onLoad(query) {
    this.setData({ leadId: query.id || "" });
  },
  onShow() {
    this.loadLead();
  },
  async loadLead() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    try {
      const res = await api.fetchLeadReminder(this.data.leadId, currentUser.id);
      const data = res.data;
      const lead = {
        ...data,
        statusText: leadStatusText(data.status),
        isClosed: ["invalid", "paused", "completed"].includes(data.status),
        updatedText: formatTime(data.updatedAt),
        lastViewedText: formatTime(data.lastViewedAt),
        nextFollowUpDisplay: formatDate(data.nextFollowUpAt),
        followUpLogsDisplay: (data.followUpLogs || []).map((log) => ({
          ...log,
          createdText: formatTime(log.createdAt)
        }))
      };
      this.setData({
        lead,
        note: data.note || "",
        followUp: "",
        nextFollowUpAt: data.nextFollowUpAt ? String(data.nextFollowUpAt).slice(0, 10) : "",
        conclusionReason: data.conclusionReason || ""
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "线索加载失败", icon: "none" });
    }
  },
  handleNoteChange(event) {
    this.setData({ note: event.detail.value });
  },
  handleFollowUpChange(event) {
    this.setData({ followUp: event.detail.value });
  },
  handleNextFollowUpChange(event) {
    this.setData({ nextFollowUpAt: event.detail.value });
  },
  handleConclusionReasonChange(event) {
    this.setData({ conclusionReason: event.detail.value });
  },
  async handleSaveNote() {
    const currentUser = getCurrentUser();
    try {
      await api.updateLeadReminder(this.data.leadId, {
        ownerUserId: currentUser.id,
        note: this.data.note || ""
      });
      wx.showToast({ title: "备注已保存", icon: "success" });
      this.loadLead();
    } catch (error) {
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
    }
  },
  async handleSaveFollowUp() {
    const currentUser = getCurrentUser();
    const logContent = (this.data.followUp || "").trim();
    const nextFollowUpAt = this.data.nextFollowUpAt || "";
    if (!logContent && !nextFollowUpAt) {
      wx.showToast({ title: "请填写跟进记录或时间", icon: "none" });
      return;
    }
    try {
      await api.updateLeadReminder(this.data.leadId, {
        ownerUserId: currentUser.id,
        nextFollowUpAt,
        logContent
      });
      wx.showToast({ title: "跟进已保存", icon: "success" });
      this.loadLead();
    } catch (error) {
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
    }
  },
  async handleSetStatus(event) {
    const currentUser = getCurrentUser();
    const status = event.currentTarget.dataset.status;
    const payload = { ownerUserId: currentUser.id, status };
    if (["invalid", "paused", "completed"].includes(status)) {
      payload.conclusionReason = this.data.conclusionReason || "";
    }
    if (status === "pending") {
      payload.conclusionReason = "";
    }
    try {
      await api.updateLeadReminder(this.data.leadId, payload);
      wx.showToast({ title: "状态已更新", icon: "success" });
      this.loadLead();
    } catch (error) {
      wx.showToast({ title: error.detail || "操作失败", icon: "none" });
    }
  },
  handleOpenDetail() {
    if (!this.data.lead) return;
    wx.navigateTo({ url: `/pages/card-view/index?id=${this.data.lead.cardId}` });
  },
  handleOpenManager() {
    if (!this.data.lead) return;
    wx.navigateTo({ url: `/pages/manager/index?id=${this.data.lead.cardId}` });
  }
});
