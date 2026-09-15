const shared = require("../shared");
const api = require("../../../services/api");

function submissionStatusLabel(status) {
  if (status === "submitted") return "待验收";
  if (status === "approved" || status === "completed") return "已完成";
  return status || "未知";
}

Page({
  data: {
    activeTab: "mine",
    tabs: shared.TAB_ITEMS,
    user: null,
    points: 100,
    basePoints: 100,
    rewardPoints: 0,
    rewardPointsVisible: false,
    pointsTip: "登录后开始积累互助积分",
    publishedTasks: [],
    submittedTasks: [],
    publishedCount: 0,
    submittedCount: 0,
    rechargeVisible: false,
    rechargeEnabled: false,
    withdrawalVisible: false,
    withdrawalEnabled: false,
    accountLoading: false,
    syncError: false,
    theme: shared.getTheme()
  },

  async onShow() {
    const user = shared.getUser();
    const userId = shared.getUserId(user);
    let syncError = false;
    if (user) {
      try {
        await shared.syncServerTasks(userId);
      } catch (error) {
        // Do not present an old local snapshot as current account data.
        syncError = true;
      }
    }
    const tasks = syncError ? [] : shared.getTasks();
    const submissions = shared.getSubmissions(userId);
    const balances = shared.getPointBalances(userId);
    const submittedTasks = submissions
      .map((submission) => {
        const task = tasks.find((item) => item.id === submission.taskId);
        return task ? { ...shared.decorateTask(task, userId), submissionStatus: submissionStatusLabel(submission.status) } : null;
      })
      .filter(Boolean);
    const publishedTasks = user
      ? tasks.filter((task) => task.ownerUserId === userId).map((task) => shared.decorateTask(task, userId))
      : [];
    this.setData({
      user,
      theme: shared.getTheme(),
      points: user ? balances.total : 100,
      basePoints: user ? balances.base : 100,
      rewardPoints: user ? balances.reward : 0,
      rewardPointsVisible: false,
      pointsTip: user ? "继续积累互助积分" : "登录后开始积累互助积分",
      publishedTasks,
      submittedTasks,
      publishedCount: publishedTasks.length,
      submittedCount: submittedTasks.length,
      rechargeVisible: false,
      rechargeEnabled: false,
      withdrawalVisible: false,
      withdrawalEnabled: false,
      syncError
    });
    this.loadMutualStatus(user);
  },

  handleRetrySync() {
    this.onShow();
  },

  async loadMutualStatus(user) {
    if (!user || this.data.accountLoading) return;
    this.setData({ accountLoading: true });
    try {
      const response = await api.fetchMutualHelpStatus(shared.getUserId(user));
      const data = response.data || {};
      const config = data.config || {};
      const balances = shared.saveServerPointData(data, shared.getUserId(user));
      this.setData({
        points: balances.total,
        basePoints: balances.base,
        rewardPoints: balances.reward,
        rewardPointsVisible: Boolean(user) && config.rechargeVisible === true,
        rechargeVisible: config.rechargeVisible === true,
        rechargeEnabled: config.rechargeEnabled === true,
        withdrawalVisible: config.withdrawalVisible === true,
        withdrawalEnabled: config.withdrawalEnabled === true,
        pointsTip: config.available === false ? "积分暂时不可用，请稍后重试" : "继续积累互助积分"
      });
    } catch (error) {
      this.setData({ pointsTip: "积分服务加载失败，请稍后重试" });
    } finally {
      this.setData({ accountLoading: false });
    }
  },

  handleTabChange(event) {
    shared.navigateTab(event.currentTarget.dataset.tab, this.data.activeTab);
  },

  handleThemeChange(event) {
    this.setData({ theme: shared.saveTheme(event.currentTarget.dataset.theme) });
  },

  requireAccountAction() {
    return shared.requireLogin("/subpackages/my-tools-mutual-help/mine/index");
  },

  handleRecharge() {
    if (!this.requireAccountAction()) return;
    if (!this.data.rechargeVisible || !this.data.rechargeEnabled) {
      wx.showToast({ title: "充值积分功能暂未开放", icon: "none" });
      return;
    }
    wx.navigateTo({ url: "/subpackages/my-tools-mutual-help/recharge/index" });
  },

  handleWithdraw() {
    if (!this.requireAccountAction()) return;
    if (!this.data.rechargeVisible || !this.data.withdrawalVisible || !this.data.withdrawalEnabled) {
      wx.showToast({ title: "提现功能暂未开放", icon: "none" });
      return;
    }
    wx.navigateTo({ url: "/subpackages/my-tools-mutual-help/withdrawal/index" });
  },

  handleOpenTask(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/subpackages/my-tools-mutual-help/task-detail/index?id=${encodeURIComponent(id)}` });
  },

  handleGoTaskManage() {
    shared.navigateTab("task", this.data.activeTab);
  },

  handleGoReport() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/report/index");
    if (user) wx.navigateTo({ url: "/subpackages/my-tools-mutual-help/report/index" });
  },

  handleGoPublish() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/publish/index");
    if (user) wx.redirectTo({ url: "/subpackages/my-tools-mutual-help/publish/index" });
  }
});
