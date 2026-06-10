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

function buildCustomerProfileText(lead) {
  if (!lead) return "";
  const latestLog = (lead.followUpLogs || [])[0];
  return [
    `姓名：${lead.nickname || ""}`,
    `手机号：${lead.customerPhone || ""}`,
    `微信号：${lead.customerWechat || ""}`,
    `预算：${lead.budgetText || ""}`,
    `意向等级：${lead.intentLevel || "待判断"}`,
    `来源资料：${lead.cardTitle || ""}`,
    `状态：${lead.statusText || ""}`,
    `备注：${lead.note || ""}`,
    latestLog ? `最近跟进：${latestLog.content || ""}` : ""
  ].filter(Boolean).join("\n");
}

Page({
  data: {
    leadId: "",
    lead: null,
    note: "",
    followUp: "",
    nextFollowUpAt: "",
    conclusionReason: "",
    customerPhone: "",
    customerWechat: "",
    budgetText: "",
    intentLevel: "",
    intentIndex: 3,
    intentOptions: ["高意向", "中意向", "低意向", "待判断"]
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
        conclusionReason: data.conclusionReason || "",
        customerPhone: data.customerPhone || "",
        customerWechat: data.customerWechat || "",
        budgetText: data.budgetText || "",
        intentLevel: data.intentLevel || "",
        intentIndex: Math.max(0, this.data.intentOptions.indexOf(data.intentLevel || "待判断"))
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
  handleCustomerPhoneChange(event) {
    this.setData({ customerPhone: event.detail.value });
  },
  handleCustomerWechatChange(event) {
    this.setData({ customerWechat: event.detail.value });
  },
  handleBudgetChange(event) {
    this.setData({ budgetText: event.detail.value });
  },
  handleIntentLevelChange(event) {
    const index = Number(event.detail.value || 0);
    this.setData({
      intentIndex: index,
      intentLevel: this.data.intentOptions[index] || ""
    });
  },
  async handleSaveCustomerProfile() {
    const currentUser = getCurrentUser();
    try {
      await api.updateLeadReminder(this.data.leadId, {
        ownerUserId: currentUser.id,
        customerPhone: this.data.customerPhone || "",
        customerWechat: this.data.customerWechat || "",
        budgetText: this.data.budgetText || "",
        intentLevel: this.data.intentLevel || ""
      });
      wx.showToast({ title: "客户资料已保存", icon: "success" });
      this.loadLead();
    } catch (error) {
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
    }
  },
  handleCopyCustomerProfile() {
    if (!this.data.lead) {
      wx.showToast({ title: "暂无客户资料", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: buildCustomerProfileText(this.data.lead),
      success: () => wx.showToast({ title: "客户档案已复制", icon: "success" })
    });
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
