const { addOpportunityFollowup, fetchSavedOpportunityLeads, saveOpportunityLead } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildUniversalShareMessage, prepareUniversalShareImage } = require("../../utils/universal-share");

const statusConfig = [
  { key: "saved", label: "待联系" },
  { key: "contacted", label: "已联系" },
  { key: "following", label: "跟进中" },
  { key: "invalid", label: "无效" }
];

const mockSavedCards = [
  {
    id: "opp_demo_1",
    statusKey: "saved",
    status: "待联系",
    title: "长沙新店找本地推广渠道",
    reminder: "今天 18:00",
    latestAction: "已保存，未生成回应包",
    note: "适合发服务介绍页和案例合集",
    packageStatus: "未生成",
    nextAction: "生成回应包"
  },
  {
    id: "opp_demo_2",
    statusKey: "following",
    status: "跟进中",
    title: "社区团购团长找稳定货源",
    reminder: "明天 10:30",
    latestAction: "已电话沟通，等样品清单",
    note: "适合发商品合集",
    packageStatus: "已生成",
    nextAction: "打开资料"
  }
];

const packageFilters = [
  { key: "", label: "全部回应包" },
  { key: "generated", label: "已生成" },
  { key: "not_generated", label: "未生成" }
];

function statusText(value) {
  if (value === "contacted") return "已联系";
  if (value === "following") return "跟进中";
  if (value === "invalid") return "无效";
  if (value === "archived") return "已归档";
  return "待联系";
}

function mapSaved(row = {}) {
  const lead = row.lead || {};
  const save = row.save || {};
  const statusKey = save.status || "saved";
  const responsePackage = row.responsePackage || null;
  const latestFollowup = row.latestFollowup || null;
  return {
    id: lead.id,
    statusKey,
    status: statusText(statusKey),
    title: lead.title || "未命名商机",
    reminder: save.reminderAt || "未设置",
    latestAction: latestFollowup ? (latestFollowup.note || latestFollowup.actionType || "已记录跟进") : (statusKey === "following" ? "正在跟进" : "已保存，待处理"),
    note: save.note || lead.summary || "暂无备注",
    packageStatus: row.packageStatusText || (responsePackage ? "已生成" : "未生成"),
    packageStatusKey: row.packageStatus || (responsePackage ? "generated" : "not_generated"),
    packageId: responsePackage && responsePackage.id,
    followupCount: row.followupCount || 0,
    nextAction: responsePackage ? "打开回应包" : "生成回应包"
  };
}

function buildTabs(cards = [], activeStatus = "saved") {
  return statusConfig.map((item) => ({
    ...item,
    count: cards.filter((card) => card.statusKey === item.key).length,
    active: activeStatus === item.key
  }));
}

function isDemoLeadId(value) {
  return /^opp_demo_/.test(String(value || ""));
}

Page({
  data: {
    statusTabs: buildTabs(mockSavedCards),
    activeStatus: "saved",
    activePackageStatus: "",
    packageFilters,
    savedCards: mockSavedCards,
    visibleCards: mockSavedCards.filter((item) => item.statusKey === "saved"),
    usingMock: true,
    universalShareImage: ""
  },
  onShow() {
    this.loadSaved();
    this.prepareShareImage();
  },
  prepareShareImage() {
    const first = (this.data.visibleCards || [])[0] || mockSavedCards[0];
    return prepareUniversalShareImage(this, {
      title: "已保存线索",
      summary: first.note || first.title || "打开查看已保存的商机跟进台。",
      badge: "跟进",
      path: "/pages/opportunity-saved/index",
      shareTargetLabel: "商机"
    });
  },
  async loadSaved() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    try {
      const res = await fetchSavedOpportunityLeads(user.id, {
        status: this.data.activeStatus,
        packageStatus: this.data.activePackageStatus
      });
      const cards = Array.isArray(res.data) ? res.data.map(mapSaved) : [];
      this.applyCards(cards.length ? cards : mockSavedCards, !cards.length);
    } catch (error) {
      this.applyCards(mockSavedCards, true);
    }
  },
  applyCards(cards, usingMock) {
    const visibleCards = this.filterCards(cards);
    this.setData({
      savedCards: cards,
      visibleCards,
      statusTabs: buildTabs(cards, this.data.activeStatus),
      usingMock
    });
    this.prepareShareImage();
  },
  filterCards(cards = []) {
    return cards.filter((item) => {
      const statusMatched = !this.data.activeStatus || item.statusKey === this.data.activeStatus;
      const packageMatched = !this.data.activePackageStatus || item.packageStatusKey === this.data.activePackageStatus;
      return statusMatched && packageMatched;
    });
  },
  handleStatusTap(event) {
    const activeStatus = event.currentTarget.dataset.key;
    this.setData({
      activeStatus,
      statusTabs: buildTabs(this.data.savedCards, activeStatus)
    });
    this.loadSaved();
  },
  handlePackageFilterTap(event) {
    this.setData({ activePackageStatus: event.currentTarget.dataset.key || "" });
    this.loadSaved();
  },
  handleOpenDetail(event) {
    wx.navigateTo({ url: `/pages/opportunity-detail/index?id=${event.currentTarget.dataset.id}` });
  },
  async handleQuickAction(event) {
    const user = getCurrentUser();
    const action = event.currentTarget.dataset.action || "已记录";
    const id = event.currentTarget.dataset.id;
    if (!user || !id) return;
    if (action === "生成回应包") {
      wx.navigateTo({ url: `/pages/response-package/index?leadId=${id}` });
      return;
    }
    if (action === "打开回应包") {
      const card = this.data.savedCards.find((item) => item.id === id);
      if (card && card.packageId) {
        wx.navigateTo({ url: `/pages/response-package/index?id=${card.packageId}` });
      } else {
        wx.navigateTo({ url: `/pages/response-package/index?leadId=${id}` });
      }
      return;
    }
    if (isDemoLeadId(id)) {
      wx.showToast({ title: action, icon: "success" });
      return;
    }
    try {
      await addOpportunityFollowup(id, {
        userId: user.id,
        actionType: action.includes("联系") ? "contacted" : "note",
        note: action
      });
      wx.showToast({ title: action, icon: "none" });
      this.loadSaved();
    } catch (error) {
      wx.showToast({ title: "记录失败，稍后再试", icon: "none" });
    }
  },
  async handleStatusEdit(event) {
    const user = getCurrentUser();
    const id = event.currentTarget.dataset.id;
    const current = event.currentTarget.dataset.status || "saved";
    if (!user || !id) return;
    const labels = ["待联系", "已联系", "跟进中", "无效"];
    const values = ["saved", "contacted", "following", "invalid"];
    wx.showActionSheet({
      itemList: labels,
      success: async (res) => {
        const status = values[res.tapIndex] || current;
        if (isDemoLeadId(id)) {
          wx.showToast({ title: labels[res.tapIndex], icon: "success" });
          return;
        }
        try {
          await saveOpportunityLead(id, {
            userId: user.id,
            status,
            note: `状态改为${labels[res.tapIndex]}`
          });
          wx.showToast({ title: "状态已更新", icon: "success" });
          this.loadSaved();
        } catch (error) {
          wx.showToast({ title: "更新失败", icon: "none" });
        }
      }
    });
  },
  async handleReminderEdit(event) {
    const user = getCurrentUser();
    const id = event.currentTarget.dataset.id;
    if (!user || !id) return;
    const now = new Date();
    const options = [
      { label: "今天 18:00", offset: 0, hour: 18 },
      { label: "明天 10:00", offset: 1, hour: 10 },
      { label: "三天后 10:00", offset: 3, hour: 10 }
    ];
    wx.showActionSheet({
      itemList: options.map((item) => item.label),
      success: async (res) => {
        const option = options[res.tapIndex] || options[0];
        const target = new Date(now.getFullYear(), now.getMonth(), now.getDate() + option.offset, option.hour, 0, 0);
        if (option.offset === 0 && target.getTime() < now.getTime()) {
          target.setDate(target.getDate() + 1);
        }
        if (isDemoLeadId(id)) {
          wx.showToast({ title: "提醒已设置", icon: "success" });
          return;
        }
        try {
          const card = this.data.savedCards.find((item) => item.id === id) || {};
          await saveOpportunityLead(id, {
            userId: user.id,
            status: card.statusKey || "saved",
            note: card.note || "",
            reminderAt: target.toISOString()
          });
          wx.showToast({ title: "提醒已设置", icon: "success" });
          this.loadSaved();
        } catch (error) {
          wx.showToast({ title: "设置失败", icon: "none" });
        }
      }
    });
  },
  onShareAppMessage() {
    return buildUniversalShareMessage(this, {
      title: "已保存线索",
      summary: "打开查看已保存的商机跟进台。",
      badge: "跟进",
      path: "/pages/opportunity-saved/index",
      shareTargetLabel: "商机"
    });
  }
});
