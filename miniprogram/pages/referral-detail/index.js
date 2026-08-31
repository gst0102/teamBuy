const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { normalizeCenter, moneyYuan } = require("../../utils/referral-view");

function filterReferrals(referrals, filter) {
  if (filter === "paid") return referrals.filter((item) => item.relationStatus === "paid");
  if (filter === "unpaid") return referrals.filter((item) => item.relationStatus === "bound" || item.relationStatus === "pending");
  return referrals;
}

Page({
  data: {
    activeTab: "earnings",
    friendFilter: "all",
    loading: true,
    loaded: false,
    refreshing: false,
    loadError: "",
    refreshError: "",
    withdrawSubmitting: false,
    center: { totals: {}, rewards: [], withdrawals: [], directReferrals: [], withdrawalRules: {}, withdrawalOptions: [] },
    visibleReferrals: [],
    selectedWithdrawalFen: 0,
    selectedWithdrawalYuan: "0.00"
  },

  onLoad(options) {
    const activeTab = options && options.tab === "friends" ? "friends" : "earnings";
    this._focusWithdraw = Boolean(options && options.focus === "withdraw");
    this.setData({ activeTab });
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
      const previous = Number(this.data.selectedWithdrawalFen || 0);
      const provisional = normalizeCenter(response.data, previous);
      const selected = provisional.withdrawalOptions.some((item) => item.selected)
        ? previous
        : (provisional.withdrawalOptions.find((item) => item.selectable) || {}).amountFen || 0;
      const center = normalizeCenter(response.data, selected);
      this.setData({
        loading: false,
        loaded: true,
        refreshing: false,
        loadError: "",
        refreshError: "",
        center,
        visibleReferrals: filterReferrals(center.directReferrals, this.data.friendFilter),
        selectedWithdrawalFen: selected,
        selectedWithdrawalYuan: moneyYuan(selected)
      }, () => {
        if (this._focusWithdraw && this.data.activeTab === "earnings") {
          this._focusWithdraw = false;
          this.scrollToWithdraw();
        }
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

  setTab(event) {
    const tab = event.currentTarget.dataset.tab === "friends" ? "friends" : "earnings";
    this.setData({ activeTab: tab });
  },

  setFriendFilter(event) {
    const filter = event.currentTarget.dataset.filter || "all";
    this.setData({
      friendFilter: filter,
      visibleReferrals: filterReferrals(this.data.center.directReferrals || [], filter)
    });
  },

  scrollToWithdraw() {
    if (!wx.createSelectorQuery || !wx.pageScrollTo) return;
    const query = wx.createSelectorQuery();
    query.selectViewport().scrollOffset();
    query.select("#withdraw-section").boundingClientRect();
    query.exec((result) => {
      const viewport = result && result[0];
      const section = result && result[1];
      if (!section) return;
      wx.pageScrollTo({
        scrollTop: Math.max(0, Number(viewport && viewport.scrollTop || 0) + section.top - 24),
        duration: 220
      });
    });
  },

  goToWithdrawal() {
    this.setData({ activeTab: "earnings" }, () => this.scrollToWithdraw());
  },

  goToLibrary() {
    wx.switchTab({ url: "/pages/library/index" });
  },

  handleSelectWithdrawalAmount(event) {
    const amountFen = Number(event.currentTarget.dataset.amountFen || 0);
    const center = this.data.center || {};
    const option = (center.withdrawalOptions || []).find((item) => item.amountFen === amountFen);
    if (!center.rulesReady) return wx.showToast({ title: "提现规则暂不可用，请刷新", icon: "none" });
    if (!center.balanceReady) return wx.showToast({ title: "余额数据暂不可用，请刷新", icon: "none" });
    if (!option || !option.selectable) return wx.showToast({ title: `可提现余额不足 ¥${moneyYuan(amountFen)}`, icon: "none" });
    this.setData({
      selectedWithdrawalFen: amountFen,
      selectedWithdrawalYuan: moneyYuan(amountFen),
      "center.withdrawalOptions": (center.withdrawalOptions || []).map((item) => ({
        ...item,
        selected: item.amountFen === amountFen
      }))
    });
  },

  handleWithdraw() {
    const center = this.data.center || {};
    if (!this.data.loaded || this.data.loading || this.data.refreshing || this.data.withdrawSubmitting) return;
    if (!center.rulesReady) return wx.showToast({ title: "提现规则暂不可用，请刷新", icon: "none" });
    if (!center.balanceReady) return wx.showToast({ title: "余额数据暂不可用，请刷新", icon: "none" });
    const available = Number((center.totals || {}).available || 0);
    const minimum = Number(center.minimumWithdrawalFen || 0);
    const amount = Number(this.data.selectedWithdrawalFen || 0);
    if (available < minimum) return wx.showToast({ title: `满 ${moneyYuan(minimum)} 元可提现`, icon: "none" });
    if (!amount || amount < minimum || amount > available) return wx.showToast({ title: "请选择可提现金额", icon: "none" });
    const user = getCurrentUser();
    const rules = center.withdrawalRules || {};
    wx.showModal({
      title: "确认申请提现",
      content: `本次申请 ¥${moneyYuan(amount)}。${rules.reviewTimeText || "提交后进入平台审核"}；${rules.arrivalTimeText || "到账以微信实际处理结果为准"}。`,
      confirmText: "确认申请",
      success: async (modal) => {
        if (!modal.confirm || this.data.withdrawSubmitting) return;
        this.setData({ withdrawSubmitting: true });
        try {
          await api.createReferralWithdrawal(user.id, amount);
          wx.showToast({ title: "提现申请已提交", icon: "success" });
          this.loadCenter();
        } catch (error) {
          wx.showToast({ title: (error && (error.detail || error.message)) || "申请失败，请稍后重试", icon: "none" });
        } finally {
          this.setData({ withdrawSubmitting: false });
        }
      }
    });
  },

  handleConfirmTransfer(event) {
    const withdrawalId = event.currentTarget.dataset.withdrawalId;
    const withdrawal = (this.data.center.withdrawals || []).find((item) => item.id === withdrawalId);
    if (!withdrawal || !withdrawal.packageInfo) return wx.showToast({ title: "收款确认信息暂未准备好，请刷新后重试", icon: "none" });
    if (!wx.canIUse || !wx.canIUse("requestMerchantTransfer")) {
      return wx.showModal({ title: "微信版本不支持", content: "当前微信版本暂不支持商家转账确认，请升级微信后重试。", showCancel: false });
    }
    const accountInfo = wx.getAccountInfoSync ? wx.getAccountInfoSync() : null;
    const appId = accountInfo && accountInfo.miniProgram && accountInfo.miniProgram.appId;
    const mchId = this.data.center.merchantTransferMchId;
    if (!appId || !mchId) return wx.showToast({ title: "提现收款配置未完成，请联系管理员", icon: "none" });
    wx.requestMerchantTransfer({
      mchId: String(mchId),
      appId: String(appId),
      package: withdrawal.packageInfo,
      success: () => {
        wx.showToast({ title: "请在微信页面确认收款", icon: "none" });
        this.loadCenter();
      },
      fail: (error) => {
        const message = String((error && error.errMsg) || "");
        if (/cancel/i.test(message)) return wx.showToast({ title: "你已取消收款确认", icon: "none" });
        wx.showToast({ title: "收款确认未完成，请稍后重试", icon: "none" });
      }
    });
  }
});
