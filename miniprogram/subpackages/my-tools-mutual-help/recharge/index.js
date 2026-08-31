const { getCurrentUser } = require("../../../utils/dashboard");
const api = require("../../../services/api");
const shared = require("../shared");

const FALLBACK_PACKAGES = [100, 500, 1000, 2000].map((points) => ({
  points,
  amountFen: points * 10,
  amountYuan: points / 10
}));

Page({
  data: {
    account: null,
    packages: FALLBACK_PACKAGES,
    selectedPoints: 100,
    rechargeEnabled: false,
    rechargeVisible: false,
    loading: false,
    statusText: ""
  },

  onLoad() {
    if (!shared.requireLogin("/subpackages/my-tools-mutual-help/recharge/index")) return;
    this.loadStatus();
  },

  async loadStatus() {
    const user = getCurrentUser();
    if (!user) return;
    try {
      const response = await api.fetchMutualHelpStatus(user.id);
      const data = response.data || {};
      const config = data.config || {};
      const account = data.account || null;
      if (account) shared.savePoints(account.balance, user.id);
      this.setData({
        account,
        packages: Array.isArray(data.rechargePackages) && data.rechargePackages.length ? data.rechargePackages : FALLBACK_PACKAGES,
        rechargeEnabled: Boolean(config.rechargeEnabled),
        rechargeVisible: Boolean(config.rechargeVisible),
        statusText: config.available === false ? "充值暂时不可用，请稍后重试" : ""
      });
    } catch (error) {
      this.setData({ statusText: error.detail || "积分状态加载失败，请稍后重试" });
    }
  },

  handleSelectPackage(event) {
    this.setData({ selectedPoints: Number(event.currentTarget.dataset.points || 100) });
  },

  requestWechatPayment(payment = {}) {
    return new Promise((resolve, reject) => {
      wx.requestPayment({
        timeStamp: String(payment.timeStamp || ""),
        nonceStr: String(payment.nonceStr || ""),
        package: String(payment.package || ""),
        signType: String(payment.signType || "RSA"),
        paySign: String(payment.paySign || ""),
        success: resolve,
        fail: reject
      });
    });
  },

  isPaymentCancelled(error) {
    const message = String((error && (error.errMsg || error.message || error.detail)) || "").toLowerCase();
    return message.includes("cancel") || message.includes("取消");
  },

  async waitForRecharge(userId, orderId) {
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const response = await api.fetchMutualHelpStatus(userId);
      const data = response.data || {};
      const paid = (data.orders || []).find((item) => item.id === orderId && item.status === "paid");
      if (paid) return data;
      if (attempt < 5) await new Promise((resolve) => setTimeout(resolve, 500));
    }
    return null;
  },

  async handleRecharge() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/recharge/index");
    if (!user || this.data.loading) return;
    if (!this.data.rechargeEnabled) {
      wx.showToast({ title: "充值功能暂未开放", icon: "none" });
      return;
    }
    this.setData({ loading: true, statusText: "正在准备充值…" });
    try {
      const response = await api.createMutualHelpRechargeOrder(user.id, this.data.selectedPoints);
      const result = response.data || {};
      if (result.testMode) {
        const confirmed = await api.confirmTestMutualHelpRechargeOrder(result.order.id, `mutual-test-${Date.now()}`);
        const account = confirmed.data && confirmed.data.account;
        if (account) {
          shared.savePoints(account.balance, user.id);
          this.setData({ account });
        }
        wx.showToast({ title: "充值成功", icon: "success" });
        return;
      }
      const paymentResponse = await api.createMutualHelpRechargePayment(result.order.id, user.id);
      try {
        await this.requestWechatPayment(paymentResponse.data && paymentResponse.data.payment);
      } catch (error) {
        if (this.isPaymentCancelled(error)) {
          wx.showToast({ title: "已取消支付，订单仍可继续支付", icon: "none" });
          return;
        }
        throw error;
      }
      const latest = await this.waitForRecharge(user.id, result.order.id);
      const account = latest && latest.account;
      if (account) {
        shared.savePoints(account.balance, user.id);
        this.setData({ account });
        wx.showToast({ title: "充值成功", icon: "success" });
      } else {
        wx.showToast({ title: "支付成功，积分到账确认中", icon: "none" });
      }
    } catch (error) {
      this.setData({ statusText: error.detail || error.message || "充值失败，请稍后重试" });
      wx.showToast({ title: error.detail || error.message || "充值失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  }
});
