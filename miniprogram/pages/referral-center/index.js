const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

function moneyYuan(fen) {
  return (Number(fen || 0) / 100).toFixed(2);
}

function pad2(value) {
  return String(value).padStart(2, "0");
}

function formatChineseDateTime(value) {
  if (!value) return "";
  const raw = String(value);
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return `${date.getFullYear()}年${pad2(date.getMonth() + 1)}月${pad2(date.getDate())}日 ${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function productionFallbackMinimumFen() {
  const app = getApp();
  return app && app.globalData && app.globalData.environmentName === "production" ? 1000 : 10;
}

function withdrawalStatusLabel(status) {
  return {
    pending: "审核中",
    approved: "已审核",
    waiting_user_confirm: "待确认收款",
    processing: "转账处理中",
    paid: "已到账",
    failed: "转账失败",
    cancelled: "已撤销",
    rejected: "已拒绝"
  }[status] || "处理中";
}

function rewardStatusLabel(status) {
  return {
    pending: "待生效",
    available: "可提现",
    reserved: "提现处理中",
    withdrawn: "已提现",
    revoked: "已撤销"
  }[status] || "处理中";
}

function normalizeCenter(center, selectedAmountFen = 0) {
  const value = center || {};
  const rules = value.withdrawalRules || {};
  const totals = value.totals || {};
  const configuredMinimumFen = Number(value.minimumWithdrawalFen || rules.minimumWithdrawalFen || 0);
  const minimumFen = configuredMinimumFen > 0 ? configuredMinimumFen : productionFallbackMinimumFen();
  const availableFen = Number(totals.available || 0);
  const withdrawalOptions = [1000, 5000, 20000].map((amountFen) => ({
    amountFen,
    amountYuan: moneyYuan(amountFen),
    selectable: amountFen >= minimumFen && availableFen >= amountFen,
    selected: amountFen === selectedAmountFen && amountFen >= minimumFen && availableFen >= amountFen
  }));
  return {
    ...value,
    minimumWithdrawalFen: minimumFen,
    minimumWithdrawalYuan: moneyYuan(minimumFen),
    dailyWithdrawalLimit: Number(value.dailyWithdrawalLimit || rules.dailyWithdrawalLimit || 1),
    totals: { ...totals, availableYuan: moneyYuan(availableFen) },
    withdrawalOptions,
    withdrawalRules: {
      ...rules,
      minimumWithdrawalFen: minimumFen,
      minimumWithdrawalYuan: moneyYuan(minimumFen)
    },
    rewards: (value.rewards || []).map((item) => ({
      ...item,
      amountYuan: moneyYuan(item.amountFen),
      createdAtText: formatChineseDateTime(item.createdAt),
      updatedAtText: formatChineseDateTime(item.updatedAt),
      statusLabel: rewardStatusLabel(item.status)
    })),
    withdrawals: (value.withdrawals || []).map((item) => ({
      ...item,
      amountYuan: moneyYuan(item.amountFen),
      createdAtText: formatChineseDateTime(item.createdAt),
      paidAtText: formatChineseDateTime(item.paidAt),
      displayStatus: item.paidAt || item.transferState === "SUCCESS" ? "paid" : item.status,
      statusLabel: withdrawalStatusLabel(item.paidAt || item.transferState === "SUCCESS" ? "paid" : item.status),
      canConfirm: item.status === "waiting_user_confirm" && Boolean(item.packageInfo)
    }))
  };
}

Page({
  data: { center: { totals: {}, rewards: [], withdrawals: [], withdrawalRules: {}, withdrawalOptions: [] }, selectedWithdrawalFen: 0, selectedWithdrawalYuan: "0.00" },
  onShow() { this.loadCenter(); },
  async loadCenter() {
    const user = getCurrentUser();
    if (!user) return wx.reLaunch({ url: "/pages/login/index" });
    try {
      const res = await api.fetchReferralCenter(user.id);
      const previous = Number(this.data.selectedWithdrawalFen || 0);
      const provisional = normalizeCenter(res.data, previous);
      const selected = provisional.withdrawalOptions.some((item) => item.selected)
        ? previous
        : (provisional.withdrawalOptions.find((item) => item.selectable) || {}).amountFen || 0;
      this.setData({ center: normalizeCenter(res.data, selected), selectedWithdrawalFen: selected, selectedWithdrawalYuan: moneyYuan(selected) });
    } catch (error) {
      wx.showToast({ title: "推广数据加载失败", icon: "none" });
    }
  },
  handleSelectWithdrawalAmount(event) {
    const amountFen = Number(event.currentTarget.dataset.amountFen || 0);
    const option = (this.data.center.withdrawalOptions || []).find((item) => item.amountFen === amountFen);
    if (!option || !option.selectable) {
      return wx.showToast({ title: `可提现余额不足 ¥${moneyYuan(amountFen)}`, icon: "none" });
    }
    const options = (this.data.center.withdrawalOptions || []).map((item) => ({
      ...item,
      selected: item.amountFen === amountFen
    }));
    this.setData({ selectedWithdrawalFen: amountFen, selectedWithdrawalYuan: moneyYuan(amountFen), "center.withdrawalOptions": options });
  },
  async handleWithdraw() {
    const available = Number((this.data.center.totals || {}).available || 0);
    const minimum = Number(this.data.center.minimumWithdrawalFen || 0);
    const amount = Number(this.data.selectedWithdrawalFen || 0);
    if (minimum > 0 && available < minimum) {
      return wx.showToast({ title: `满 ${moneyYuan(minimum)} 元可提现`, icon: "none" });
    }
    if (!amount || amount > available) {
      return wx.showToast({ title: "请选择可提现金额", icon: "none" });
    }
    const user = getCurrentUser();
    const rules = this.data.center.withdrawalRules || {};
    wx.showModal({
      title: "确认申请提现",
      content: `本次申请 ¥${moneyYuan(amount)}。每日最多提现 ${rules.dailyWithdrawalLimit || 1} 次，提交后进入平台审核；审核通过并完成微信确认后，以微信实际到账时间为准，基本秒到。`,
      confirmText: "确认申请",
      success: async (modal) => {
        if (!modal.confirm) return;
        try {
          await api.createReferralWithdrawal(user.id, amount);
          wx.showToast({ title: "提现申请已提交", icon: "success" });
          this.loadCenter();
        } catch (error) {
          wx.showToast({ title: (error && (error.detail || error.message)) || "申请失败", icon: "none" });
        }
      }
    });
  },
  handleConfirmTransfer(event) {
    const withdrawalId = event.currentTarget.dataset.withdrawalId;
    const withdrawal = (this.data.center.withdrawals || []).find((item) => item.id === withdrawalId);
    if (!withdrawal || !withdrawal.packageInfo) {
      return wx.showToast({ title: "收款确认信息暂未准备好，请刷新后重试", icon: "none" });
    }
    if (!wx.canIUse || !wx.canIUse("requestMerchantTransfer")) {
      return wx.showModal({
        title: "微信版本不支持",
        content: "当前微信版本暂不支持商家转账确认，请升级微信后重试。",
        showCancel: false
      });
    }
    const accountInfo = wx.getAccountInfoSync ? wx.getAccountInfoSync() : null;
    const appId = accountInfo && accountInfo.miniProgram && accountInfo.miniProgram.appId;
    const mchId = this.data.center.merchantTransferMchId;
    if (!appId || !mchId) {
      return wx.showToast({ title: "提现收款配置未完成，请联系管理员", icon: "none" });
    }
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
