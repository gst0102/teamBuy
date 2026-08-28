const api = require("../../services/api");
const customerIntelligenceStore = require("../../stores/customer-intelligence-store");
const { formatDateOnly } = require("../../utils/date-format");
const { getCurrentUser } = require("../../utils/dashboard");

function formatPendingCountdown(seconds) {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safeSeconds / 60).toString().padStart(2, "0");
  const remainingSeconds = Math.floor(safeSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainingSeconds}`;
}

Page({
  data: {
    membership: {
      featureEnabled: true,
      paymentRequired: true,
      active: false,
      plan: { benefits: ["客户身份与联系方式", "完整访问轨迹", "客户档案与跟进", "跨资料兴趣与提醒"] },
      expiresAtText: ""
    },
    loading: false,
    pendingOrder: null,
    pendingOrderCountdown: "",
    showMembershipGuide: false,
    benefitItems: [
      { key: "identity", title: "客户身份与联系方式", icon: "人", color: "blue" },
      { key: "timeline", title: "完整访问轨迹", icon: "轨", color: "cyan" },
      { key: "followup", title: "客户档案与跟进", icon: "档", color: "violet" },
      { key: "interest", title: "跨资料兴趣与提醒", icon: "铃", color: "teal" }
    ]
  },
  onShow() { this.loadMembership(); },
  onHide() { this.stopPendingOrderCountdown(); },
  onUnload() { this.stopPendingOrderCountdown(); },
  stopPendingOrderCountdown() {
    if (this.pendingOrderTimer) {
      clearInterval(this.pendingOrderTimer);
      this.pendingOrderTimer = null;
    }
  },
  startPendingOrderCountdown(order) {
    this.stopPendingOrderCountdown();
    if (!order || !order.expiresAt) {
      this.setData({ pendingOrder: null, pendingOrderCountdown: "" });
      return;
    }
    const update = () => {
      const remaining = Math.max(0, Math.ceil((new Date(order.expiresAt).getTime() - Date.now()) / 1000));
      if (!remaining) {
        this.stopPendingOrderCountdown();
        this.setData({ pendingOrder: null, pendingOrderCountdown: "" });
        this.loadMembership();
        return;
      }
      this.setData({
        pendingOrder: { ...order, secondsRemaining: remaining },
        pendingOrderCountdown: formatPendingCountdown(remaining)
      });
    };
    update();
    this.pendingOrderTimer = setInterval(update, 1000);
  },
  applyPendingOrder(order) {
    if (!order || !order.expiresAt) {
      this.stopPendingOrderCountdown();
      this.setData({ pendingOrder: null, pendingOrderCountdown: "" });
      return;
    }
    this.startPendingOrderCountdown(order);
  },
  async loadMembership() {
    const user = getCurrentUser();
    if (!user) return wx.reLaunch({ url: "/pages/login/index" });
    this.stopPendingOrderCountdown();
    try {
      const res = await api.fetchMembership(user.id);
      const membership = res.data || {};
      this.setData({
        membership: {
          ...membership,
          expiresAtText: formatDateOnly(membership.expiresAt)
        },
        featureEnabled: membership.featureEnabled !== false
      });
      this.applyPendingOrder(membership.pendingOrder);
    } catch (error) {
      this.setData({ featureEnabled: false, "membership.featureEnabled": false, pendingOrder: null, pendingOrderCountdown: "" });
      wx.showToast({ title: "会员状态加载失败", icon: "none" });
    }
  },
  async handleSubscribe() {
    const user = getCurrentUser();
    if (!user || this.data.loading) return;
    if (this.data.membership && this.data.membership.paymentRequired === false) {
      wx.showToast({ title: "当前可直接查看客户信息", icon: "none" });
      return;
    }
    this.setData({ loading: true });
    let pendingOrder = null;
    try {
      const res = await api.createMembershipOrder(user.id);
      const order = res.data.order;
      pendingOrder = res.data.pendingOrder || null;
      this.applyPendingOrder(pendingOrder);
      if (res.data.testMode) {
        await api.confirmTestMembershipOrder(order.id, `miniapp-test-${Date.now()}`);
        api.clearMembershipCache(user.id);
        customerIntelligenceStore.clear(user.id);
        wx.showToast({ title: "测试会员已开通", icon: "success" });
        await this.loadMembership();
      } else {
        const paymentRes = await api.createMembershipPayment(order.id, user.id);
        if (paymentRes.data && paymentRes.data.paymentRequired === false) {
          api.clearMembershipCache(user.id);
          await this.loadMembership();
          return;
        }
        try {
          await this.requestWechatPayment(paymentRes.data.payment);
        } catch (error) {
          if (this.isPaymentCancelled(error)) {
            this.applyPendingOrder(paymentRes.data.pendingOrder || pendingOrder);
            wx.showToast({ title: "已取消支付，30分钟内可继续", icon: "none" });
            return;
          }
          throw error;
        }
        const membership = await this.waitForMembership(user.id);
        api.clearMembershipCache(user.id);
        customerIntelligenceStore.clear(user.id);
        if (membership && membership.active) {
          wx.showToast({ title: "会员已开通", icon: "success" });
        } else {
          wx.showToast({ title: "支付成功，权益确认中", icon: "none" });
        }
      }
    } catch (error) {
      if (pendingOrder) this.applyPendingOrder(pendingOrder);
      wx.showToast({ title: (error && (error.detail || error.message)) || "开通失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  isPaymentCancelled(error) {
    const message = String((error && (error.errMsg || error.message || error.detail)) || "").toLowerCase();
    return message.includes("cancel") || message.includes("取消");
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
  async waitForMembership(userId) {
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const res = await api.fetchMembership(userId, { force: true });
      const membership = res.data || {};
      if (membership.active) return membership;
      if (attempt < 5) await new Promise((resolve) => setTimeout(resolve, 500));
    }
    return null;
  },
  handleToggleMembershipGuide() {
    this.setData({ showMembershipGuide: !this.data.showMembershipGuide });
  }
});
