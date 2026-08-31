const shared = require("../shared");
const { buildPageShareMessage } = require("../../../utils/page-share");

function sortTasks(tasks, sortMode) {
  return tasks.slice().sort((left, right) => {
    const primary = sortMode === "reward"
      ? Number(right.executorReward || 0) - Number(left.executorReward || 0)
      : Number(right.publisherPoints || 0) - Number(left.publisherPoints || 0);
    if (primary) return primary;
    const remaining = (right.remaining === null ? 999999 : Number(right.remaining || 0))
      - (left.remaining === null ? 999999 : Number(left.remaining || 0));
    if (remaining) return remaining;
    return String(right.id || "").localeCompare(String(left.id || ""));
  });
}

Page({
  data: {
    activeTab: "home",
    tabs: shared.TAB_ITEMS,
    taskFilter: "all",
    sortMode: "publisher",
    listColumns: shared.getTaskColumns(),
    theme: shared.getTheme(),
    points: 100,
    pointsLabel: "我的互助积分",
    tasks: [],
    loading: false
  },

  onShow() {
    this.setData({
      theme: shared.getTheme(),
      listColumns: shared.getTaskColumns()
    });
    this.refresh();
  },

  onShareAppMessage() {
    return buildPageShareMessage({
      title: "互助赚积分，让别人帮你完成",
      path: "/subpackages/my-tools-mutual-help/index/index"
    });
  },

  refresh() {
    shared.syncAutoApprovedSubmissions();
    const user = shared.getUser();
    const userId = shared.getUserId(user);
    const tasks = shared.getTasks()
      .map((task) => shared.decorateTask(task, userId))
      .filter((task) => task.status !== "deleted")
      .filter((task) => !task.submitted && (!task.taskClosed || (userId !== "guest" && task.ownerUserId === userId)))
      .filter((task) => this.data.taskFilter === "all" || task.taskKind === this.data.taskFilter);
    this.setData({
      points: user ? shared.getPoints(userId) : 100,
      pointsLabel: user ? "我的互助积分" : "登录后获取互助积分",
      tasks: sortTasks(tasks, this.data.sortMode)
    });
  },

  handleTabChange(event) {
    shared.navigateTab(event.currentTarget.dataset.tab, this.data.activeTab);
  },

  handleFilterChange(event) {
    this.setData({ taskFilter: event.currentTarget.dataset.filter }, () => this.refresh());
  },

  handleSortChange(event) {
    this.setData({ sortMode: event.currentTarget.dataset.sort }, () => this.refresh());
  },

  handleColumnsChange(event) {
    const columns = shared.saveTaskColumns(event.currentTarget.dataset.columns);
    this.setData({ listColumns: columns });
  },

  handleThemeChange(event) {
    this.setData({ theme: shared.saveTheme(event.currentTarget.dataset.theme) });
  },

  handleOpenTask(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/subpackages/my-tools-mutual-help/task-detail/index?id=${encodeURIComponent(id)}` });
  },

  handleOpenRules() {
    wx.showModal({
      title: "互帮互助规则",
      content: "首次进入赠送 100 分。完成任务可以赚取积分，也可以用积分发布自己的任务；具体奖励以任务详情为准。",
      showCancel: false,
      confirmText: "知道了"
    });
  }
});
