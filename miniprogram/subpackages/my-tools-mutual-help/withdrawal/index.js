const { getCurrentUser } = require("../../../utils/dashboard");
const api = require("../../../services/api");
const shared = require("../shared");

const STATUS_LABELS = {
  pending: "待审核",
  approved: "已审核",
  waiting_user_confirm: "待用户确认",
  processing: "转账处理中",
  paid: "已到账",
  failed: "转账失败",
  cancelled: "已撤销",
  rejected: "已拒绝"
};

function calculate(points, rules = {}) {
  const value = Math.max(0, Math.floor(Number(points) || 0));
  const pointsPerYuan = Math.max(1, Number(rules.pointsPerYuan) || 10);
  const feeRate = Math.max(0, Number(rules.feeRateBasisPoints) || 2000);
  const grossFen = Math.floor(value * 100 / pointsPerYuan);
  const feeFen = Math.floor(grossFen * feeRate / 10000);
  const amountFen = Math.max(0, grossFen - feeFen);
  return {
    grossYuan: (grossFen / 100).toFixed(2),
    feeYuan: (feeFen / 100).toFixed(2),
    amountYuan: (amountFen / 100).toFixed(2)
  };
}

Page({
  data: {
    balances: { total: 0, base: 0, reward: 0 },
    rules: { minimumPoints: 100, pointsPerYuan: 10, feePercent: 20 },
    withdrawalPoints: "100",
    calculation: { grossYuan: "10.00", feeYuan: "2.00", amountYuan: "8.00" },
    withdrawals: [],
    rechargeVisible: false,
    withdrawalEnabled: false,
    withdrawalVisible: false,
    loading: false,
    submitting: false,
    statusText: ""
  },

  onLoad() {
    if (!shared.requireLogin("/subpackages/my-tools-mutual-help/withdrawal/index")) return;
    this.loadStatus();
  },

  async loadStatus() {
    const user = getCurrentUser();
    if (!user) return;
    this.setData({ loading: true });
    try {
      const response = await api.fetchMutualHelpStatus(user.id);
      const data = response.data || {};
      const config = data.config || {};
      const rules = data.withdrawalRules || {};
      const balances = shared.saveServerPointData(data, user.id);
      const points = String(this.data.withdrawalPoints || rules.minimumPoints || 100);
      this.setData({
        balances,
        rules: { ...this.data.rules, ...rules },
        calculation: calculate(points, rules),
        withdrawals: (Array.isArray(data.withdrawals) ? data.withdrawals : []).map((item) => ({
          ...item,
          amountYuan: (Number(item.amountFen || 0) / 100).toFixed(2)
        })),
        rechargeVisible: config.rechargeVisible === true,
        withdrawalEnabled: config.withdrawalEnabled === true,
        withdrawalVisible: config.withdrawalVisible === true,
        statusText: config.available === false
          ? "提现服务暂时不可用，请稍后重试"
          : (config.withdrawalEnabled ? "提交后由 PC 审核，审核通过才会发起微信转账。" : "提现入口暂未开放")
      });
    } catch (error) {
      this.setData({ statusText: error.detail || error.message || "提现状态加载失败，请稍后重试" });
    } finally {
      this.setData({ loading: false });
    }
  },

  handleInput(event) {
    const value = String(event.detail.value || "").replace(/\D/g, "");
    this.setData({
      withdrawalPoints: value,
      calculation: calculate(value, this.data.rules)
    });
  },

  handleAll() {
    const points = String(this.data.balances.reward || 0);
    this.setData({ withdrawalPoints: points, calculation: calculate(points, this.data.rules) });
  },

  async handleSubmit() {
    if (this.data.submitting) return;
    if (!this.data.rechargeVisible || !this.data.withdrawalVisible || !this.data.withdrawalEnabled) {
      wx.showToast({ title: "提现功能暂未开放", icon: "none" });
      return;
    }
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/withdrawal/index");
    if (!user) return;
    const points = Number(this.data.withdrawalPoints);
    const minimum = Number(this.data.rules.minimumPoints) || 100;
    if (!Number.isInteger(points) || points < minimum) {
      wx.showToast({ title: `最低提现 ${minimum} 充值积分`, icon: "none" });
      return;
    }
    if (points > Number(this.data.balances.reward || 0)) {
      wx.showToast({ title: "充值积分余额不足", icon: "none" });
      return;
    }
    this.setData({ submitting: true, statusText: "正在提交提现申请…" });
    try {
      const response = await api.createMutualPointWithdrawal(user.id, points);
      const withdrawal = response.data && response.data.withdrawal
        ? {
            ...response.data.withdrawal,
            amountYuan: (Number(response.data.withdrawal.amountFen || 0) / 100).toFixed(2)
          }
        : null;
      this.setData({
        balances: { ...this.data.balances, reward: Math.max(0, this.data.balances.reward - points), total: Math.max(0, this.data.balances.total - points) },
        withdrawals: withdrawal ? [withdrawal, ...this.data.withdrawals] : this.data.withdrawals,
        statusText: "已提交 PC 审核；审核通过后会发起微信转账。"
      });
      wx.showToast({ title: "已提交审核", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "提交提现失败", icon: "none" });
    } finally {
      this.setData({ submitting: false });
    }
  }
});
