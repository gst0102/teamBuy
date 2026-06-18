const api = require("../../services/api");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

function actionTitle(action) {
  if (action.actionKey === "lead-contact") return "客户留资";
  if (action.actionKey === "appointment") return "预约看房";
  if (action.actionLabel) return action.actionLabel;
  return "客户动作";
}

function actionDetails(action) {
  const payload = action.payload || {};
  const details = [];
  if (payload.name) details.push(`姓名：${payload.name}`);
  if (payload.phone) details.push(`电话：${payload.phone}`);
  if (payload.wechat) details.push(`微信：${payload.wechat}`);
  if (payload.date || payload.time) details.push(`预约：${[payload.date, payload.time].filter(Boolean).join(" ")}`);
  if (payload.remark) details.push(`备注：${payload.remark}`);
  return details;
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

function isClosedLead(status) {
  return ["invalid", "paused", "completed"].includes(status);
}

Page({
  data: {
    noteId: "",
    loading: true,
    summary: {
      total: 0,
      leadContact: 0,
      appointment: 0,
      leads: 0,
      pending: 0
    },
    actions: [],
    leads: [],
    pendingLeads: [],
    appointmentActions: [],
    finishedLeads: [],
    otherActions: []
  },
  onLoad(options) {
    this.setData({ noteId: options.id || "" });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadActions(user.id);
  },
  async loadActions(ownerUserId) {
    const { noteId } = this.data;
    if (!noteId) return;
    this.setData({ loading: true });
    try {
      const res = await api.fetchNoteCustomerActions(noteId, ownerUserId);
      const data = res.data || {};
      const actions = (data.actions || []).map((item) => ({
        ...item,
        title: actionTitle(item),
        createdText: formatTime(item.createdAt),
        details: actionDetails(item)
      }));
      const leads = (data.leads || []).map((item) => ({
        ...item,
        statusText: leadStatusText(item.status),
        isClosed: isClosedLead(item.status),
        updatedText: formatTime(item.updatedAt),
        nextFollowUpText: item.nextFollowUpAt ? String(item.nextFollowUpAt).slice(0, 16).replace("T", " ") : "未设置"
      }));
      this.setData({
        summary: {
          ...this.data.summary,
          ...(data.summary || {})
        },
        actions,
        leads,
        pendingLeads: leads.filter((item) => item.status === "pending"),
        appointmentActions: actions.filter((item) => item.actionKey === "appointment"),
        finishedLeads: leads.filter((item) => item.status !== "pending"),
        otherActions: actions.filter((item) => item.actionKey !== "appointment")
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "客户动作加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleOpenLead(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/lead-detail/index?id=${id}` });
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
  confirmMarkContacted(id) {
    if (!id) return;
    wx.showModal({
      title: "是否标记已联系？",
      content: "如果这通电话已经沟通过，可以顺手记录到线索里。",
      confirmText: "标记",
      confirmColor: "#11924d",
      success: async (res) => {
        if (!res.confirm) return;
        await this.markLeadContacted(id);
      }
    });
  },
  async markLeadContacted(id) {
    const user = getCurrentUser();
    if (!user || !id) return;
    try {
      await api.updateLeadReminder(id, {
        ownerUserId: user.id,
        status: "contacted",
        logContent: "已电话联系客户"
      });
      wx.showToast({ title: "已标记联系", icon: "success" });
      this.loadActions(user.id);
    } catch (error) {
      wx.showToast({ title: error.detail || "更新失败", icon: "none" });
    }
  }
});
