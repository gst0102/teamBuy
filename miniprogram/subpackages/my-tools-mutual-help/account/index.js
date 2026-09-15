const { getCurrentUser } = require("../../../utils/dashboard");
const api = require("../../../services/api");
const shared = require("../shared");

function pointTypeLabel(pointType) {
  return pointType === shared.POINT_TYPE_REWARD ? "充值积分" : "基础积分";
}

function formatLedgerTime(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) return "时间未知";
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function normalizeLedger(item = {}, showPointTypes = true) {
  const delta = Number(item.pointsDelta || 0);
  const reason = String(item.reason || "积分变动").trim() || "积分变动";
  const hiddenReason = delta > 0 ? "积分增加" : delta < 0 ? "积分扣除" : "积分变动";
  const isReward = item.pointType === shared.POINT_TYPE_REWARD;
  return {
    ...item,
    delta,
    deltaText: `${delta >= 0 ? "+" : ""}${delta}`,
    deltaClass: delta >= 0 ? "positive" : "negative",
    pointTypeLabel: showPointTypes ? pointTypeLabel(item.pointType) : "积分",
    timeText: formatLedgerTime(item.createdAt),
    reason: !showPointTypes && (isReward || reason.includes("充值积分")) ? hiddenReason : reason
  };
}

Page({
  data: {
    balances: { total: 0, base: 0, reward: 0 },
    config: { rechargeEnabled: false, rechargeVisible: false, withdrawalEnabled: false, withdrawalVisible: false },
    rules: {},
    ledgers: [],
    loading: false,
    statusText: ""
  },

  onLoad() {
    if (!shared.requireLogin("/subpackages/my-tools-mutual-help/account/index")) return;
    this.loadStatus();
  },

  onShow() {
    if (this.data.loading) return;
    if (getCurrentUser()) {
      this.setData({
        config: { ...this.data.config, rechargeEnabled: false, rechargeVisible: false, withdrawalEnabled: false, withdrawalVisible: false },
        rules: {},
        ledgers: this.data.ledgers.map((item) => normalizeLedger(item, false))
      });
      this.loadStatus();
    }
  },

  async loadStatus() {
    const user = getCurrentUser();
    if (!user || this.data.loading) return;
    this.setData({ loading: true });
    try {
      const response = await api.fetchMutualHelpStatus(user.id);
      const data = response.data || {};
      const balances = shared.saveServerPointData(data, user.id);
      const config = data.config || {};
      const rules = data.withdrawalRules || {};
      const showRecharge = config.rechargeVisible === true;
      this.setData({
        balances,
        config,
        rules,
        ledgers: (Array.isArray(data.recentLedgers) ? data.recentLedgers : [])
          .slice(0, 8)
          .map((item) => normalizeLedger(item, showRecharge)),
        statusText: config.available === false ? "积分服务暂时不可用，请稍后重试" : ""
      });
    } catch (error) {
      this.setData({ statusText: error.detail || error.message || "账户信息加载失败，请稍后重试" });
    } finally {
      this.setData({ loading: false });
    }
  },

  handleRecharge() {
    if (!this.data.config.rechargeVisible || !this.data.config.rechargeEnabled) {
      wx.showToast({ title: "充值积分功能暂未开放", icon: "none" });
      return;
    }
    wx.navigateTo({ url: "/subpackages/my-tools-mutual-help/recharge/index" });
  },

  handleWithdraw() {
    if (!this.data.config.rechargeVisible || !this.data.config.withdrawalVisible || !this.data.config.withdrawalEnabled) {
      wx.showToast({ title: "提现功能暂未开放", icon: "none" });
      return;
    }
    wx.navigateTo({ url: "/subpackages/my-tools-mutual-help/withdrawal/index" });
  }
});
