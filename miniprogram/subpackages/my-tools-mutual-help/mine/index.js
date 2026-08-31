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
    pointsTip: "登录后开始积累互助积分",
    publishedTasks: [],
    submittedTasks: [],
    publishedCount: 0,
    submittedCount: 0,
    rechargeVisible: true,
    rechargeEnabled: true,
    withdrawalVisible: false,
    withdrawalEnabled: false,
    accountLoading: false,
    theme: shared.getTheme()
  },

  onShow() {
    shared.syncAutoApprovedSubmissions();
    const user = shared.getUser();
    const userId = shared.getUserId(user);
    const tasks = shared.getTasks();
    const submissions = shared.getSubmissions(userId);
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
      points: user ? shared.getPoints(userId) : 100,
      pointsTip: user ? "继续积累互助积分" : "登录后开始积累互助积分",
      publishedTasks,
      submittedTasks,
      publishedCount: publishedTasks.length,
      submittedCount: submittedTasks.length
    });
    this.loadMutualStatus(user);
  },

  async loadMutualStatus(user) {
    if (!user || this.data.accountLoading) return;
    this.setData({ accountLoading: true });
    try {
      const response = await api.fetchMutualHelpStatus(shared.getUserId(user));
      const data = response.data || {};
      const config = data.config || {};
      if (data.account) shared.savePoints(data.account.balance, shared.getUserId(user));
      this.setData({
        points: data.account ? data.account.balance : this.data.points,
        rechargeVisible: config.rechargeVisible !== false,
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
      wx.showToast({ title: "充值功能暂未开放", icon: "none" });
      return;
    }
    wx.navigateTo({ url: "/subpackages/my-tools-mutual-help/recharge/index" });
  },

  handleWithdraw() {
    if (!this.requireAccountAction()) return;
    if (!this.data.withdrawalVisible || !this.data.withdrawalEnabled) {
      wx.showToast({ title: "提现功能暂未开放", icon: "none" });
      return;
    }
    wx.showToast({ title: "提现功能暂未开放", icon: "none" });
  },

  handleOpenTask(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/subpackages/my-tools-mutual-help/task-detail/index?id=${encodeURIComponent(id)}` });
  },

  handleGoTaskManage() {
    shared.navigateTab("task", this.data.activeTab);
  },

  handleGoPublish() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/publish/index");
    if (user) wx.redirectTo({ url: "/subpackages/my-tools-mutual-help/publish/index" });
  }
});
