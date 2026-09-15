const { addOpportunityFollowup, fetchSavedOpportunityLeads, saveOpportunityLead } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildShareCardMessage, prepareShareCardImage } = require("../../plugins/share-snapshot/index");

const statusConfig = [
  { key: "saved", label: "待联系" },
  { key: "contacted", label: "已联系" },
  { key: "following", label: "跟进中" },
  { key: "invalid", label: "无效" }
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

function buildTabs(cards = [], activeStatus = "saved", statusCounts = null) {
  return statusConfig.map((item) => ({
    ...item,
    count: statusCounts && statusCounts[item.key] !== undefined
      ? Number(statusCounts[item.key] || 0)
      : cards.filter((card) => card.statusKey === item.key).length,
    active: activeStatus === item.key
  }));
}

Page({
  data: {
    statusTabs: buildTabs([]),
    activeStatus: "saved",
    activePackageStatus: "",
    packageFilters,
    savedCards: [],
    visibleCards: [],
    loading: true,
    loadingMore: false,
    loadError: false,
    loadEmpty: false,
    hasMore: false,
    nextCursor: "",
    shareCardImage: ""
  },
  onShow() {
    this.loadSaved(true);
    this.prepareShareImage();
  },
  prepareShareImage() {
    const first = (this.data.visibleCards || [])[0];
    if (!first) return Promise.resolve(null);
    return prepareShareCardImage(this, {
      title: "已保存线索",
      summary: first.note || first.title || "打开查看已保存的商机跟进台。",
      badge: "跟进",
      path: "/pages/opportunity-saved/index",
      shareTargetLabel: "商机"
    });
  },
  async loadSaved(reset = true) {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if (!reset && (this.data.loading || this.data.loadingMore || !this.data.hasMore)) return;
    const requestSeq = (this._savedRequestSeq || 0) + 1;
    this._savedRequestSeq = requestSeq;
    const cursor = reset ? "" : (this.data.nextCursor || "");
    this.setData(reset
      ? { loading: true, loadingMore: false, loadError: false, loadEmpty: false, nextCursor: "", hasMore: false }
      : { loadingMore: true, loadError: false });
    try {
      const res = await fetchSavedOpportunityLeads(user.id, {
        status: this.data.activeStatus,
        packageStatus: this.data.activePackageStatus,
        cursor,
        limit: 20
      });
      if (requestSeq !== this._savedRequestSeq) return;
      const payload = res.data || {};
      const incoming = (Array.isArray(payload) ? payload : (payload.items || [])).map(mapSaved);
      const cards = reset
        ? incoming
        : [...(this.data.savedCards || []), ...incoming.filter((item) => !(this.data.savedCards || []).some((old) => old.id === item.id))];
      const statusCounts = Array.isArray(payload) ? null : payload.statusCounts;
      this.applyCards(cards, statusCounts);
      this.setData({
        loading: false,
        loadingMore: false,
        loadError: false,
        loadEmpty: reset && !cards.length,
        nextCursor: Array.isArray(payload) ? "" : (payload.nextCursor || ""),
        hasMore: Boolean(!Array.isArray(payload) && payload.hasMore)
      });
    } catch (error) {
      if (requestSeq !== this._savedRequestSeq) return;
      this.setData(reset
        ? { loading: false, loadingMore: false, loadError: true, loadEmpty: false, hasMore: false }
        : { loadingMore: false, loadError: true });
    }
  },
  applyCards(cards, statusCounts) {
    const visibleCards = this.filterCards(cards);
    this.setData({
      savedCards: cards,
      visibleCards,
      statusTabs: buildTabs(cards, this.data.activeStatus, statusCounts)
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
    this.loadSaved(true);
  },
  handlePackageFilterTap(event) {
    this.setData({ activePackageStatus: event.currentTarget.dataset.key || "" });
    this.loadSaved(true);
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
        try {
          await saveOpportunityLead(id, {
            userId: user.id,
            status,
            note: `状态改为${labels[res.tapIndex]}`
          });
          wx.showToast({ title: "状态已更新", icon: "success" });
          this.loadSaved(true);
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
        try {
          const card = this.data.savedCards.find((item) => item.id === id) || {};
          await saveOpportunityLead(id, {
            userId: user.id,
            status: card.statusKey || "saved",
            note: card.note || "",
            reminderAt: target.toISOString()
          });
          wx.showToast({ title: "提醒已设置", icon: "success" });
          this.loadSaved(true);
        } catch (error) {
          wx.showToast({ title: "设置失败", icon: "none" });
        }
      }
    });
  },
  onReachBottom() {
    this.loadSaved(false);
  },
  onShareAppMessage() {
    return buildShareCardMessage(this, {
      title: "已保存线索",
      summary: "打开查看已保存的商机跟进台。",
      badge: "跟进",
      path: "/pages/opportunity-saved/index",
      shareTargetLabel: "商机"
    });
  }
});
