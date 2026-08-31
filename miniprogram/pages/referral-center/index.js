const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { normalizeCenter } = require("../../utils/referral-view");

Page({
  data: {
    loading: true,
    loaded: false,
    refreshing: false,
    loadError: "",
    refreshError: "",
    showCommissionRules: true,
    center: { totals: {}, rewards: [], withdrawals: [], directReferrals: [], withdrawalRules: {} }
  },

  onShow() {
    this.loadCenter();
  },

  async loadCenter() {
    const user = getCurrentUser();
    if (!user) return wx.reLaunch({ url: "/pages/login/index" });
    const requestId = (this._loadRequestId || 0) + 1;
    this._loadRequestId = requestId;
    const initialLoad = !this.data.loaded;
    this.setData({
      loading: initialLoad,
      refreshing: !initialLoad,
      loadError: initialLoad ? "" : this.data.loadError,
      refreshError: ""
    });
    try {
      const response = await api.fetchReferralCenter(user.id);
      if (requestId !== this._loadRequestId) return;
      this.setData({
        loading: false,
        loaded: true,
        refreshing: false,
        loadError: "",
        refreshError: "",
        center: normalizeCenter(response.data)
      });
    } catch (error) {
      if (requestId !== this._loadRequestId) return;
      const message = (error && (error.detail || error.message)) || "请检查网络后重试";
      if (initialLoad) {
        this.setData({ loading: false, loaded: false, refreshing: false, loadError: message });
      } else {
        this.setData({ loading: false, refreshing: false, refreshError: `更新失败，当前显示上次数据：${message}` });
      }
    }
  },

  retryLoad() {
    this.loadCenter();
  },

  goToLibrary() {
    wx.switchTab({ url: "/pages/library/index" });
  },

  goToDetail(event) {
    const tab = event && event.currentTarget && event.currentTarget.dataset.tab === "friends" ? "friends" : "earnings";
    wx.navigateTo({ url: `/pages/referral-detail/index?tab=${tab}` });
  },

  goToWithdrawal() {
    wx.navigateTo({ url: "/pages/referral-detail/index?tab=earnings&focus=withdraw" });
  },

  toggleCommissionRules() {
    this.setData({ showCommissionRules: !this.data.showCommissionRules });
  }
});

module.exports = { normalizeCenter };
