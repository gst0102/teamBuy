const shared = require("../shared");
const api = require("../../../services/api");
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

function maskRewardLabels(task, showRewardPoints) {
  const rewardText = task._rewardText || task.rewardText || "";
  const rewardPointTypeLabel = task._rewardPointTypeLabel || task.rewardPointTypeLabel || "";
  return {
    ...task,
    _rewardText: rewardText,
    _rewardPointTypeLabel: rewardPointTypeLabel,
    rewardText: showRewardPoints ? rewardText : String(rewardText).replace(/充值积分/g, "积分"),
    rewardPointTypeLabel: showRewardPoints ? rewardPointTypeLabel : String(rewardPointTypeLabel).replace(/充值积分/g, "积分")
  };
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
    basePoints: 100,
    rewardPoints: 0,
    rewardPointsVisible: false,
    pointsLabel: "我的互助积分",
    tasks: [],
    loading: false,
    accountLoading: false,
    syncing: false,
    syncError: false
  },

  onShow() {
    this.setData({
      theme: shared.getTheme(),
      listColumns: shared.getTaskColumns(),
      rewardPointsVisible: false
    });
    this.refresh();
    setTimeout(() => this.loadMutualStatus(shared.getUser()), 0);
  },

  onShareAppMessage() {
    return buildPageShareMessage({
      title: "完成任务赚积分，平台统一记录",
      path: "/subpackages/my-tools-mutual-help/index/index"
    });
  },

  async refresh() {
    const user = shared.getUser();
    const userId = shared.getUserId(user);
    const refreshSeq = (this._refreshSeq || 0) + 1;
    this._refreshSeq = refreshSeq;
    const paintTasks = () => {
      if (refreshSeq !== this._refreshSeq) return;
      const tasks = shared.getTasks()
        .map((task) => shared.decorateTask(task, userId))
        .filter((task) => task.status !== "deleted")
        .filter((task) => (!task.submitted || task.repeatPolicy === "daily") && (!task.taskClosed || (userId !== "guest" && task.ownerUserId === userId)))
        .filter((task) => this.data.taskFilter === "all" || task.taskKind === this.data.taskFilter);
      const balances = shared.getPointBalances(userId);
      this.setData({
        points: user ? balances.total : 100,
        basePoints: user ? balances.base : 100,
        rewardPoints: user ? balances.reward : 0,
        rewardPointsVisible: Boolean(user) && this.data.rewardPointsVisible,
        pointsLabel: user ? "我的互助积分" : "登录后获取互助积分",
        tasks: sortTasks(tasks, this.data.sortMode).map((task) => maskRewardLabels(task, this.data.rewardPointsVisible)),
        loading: false
      });
    };
    // A local task snapshot is safe to show immediately.  Synchronization is
    // a background freshness operation and must not decide whether the hall
    // has a first paint.
    this.setData({ loading: false, syncing: Boolean(userId && userId !== "guest"), syncError: false });
    paintTasks();
    if (!userId || userId === "guest") return;
    // Let the cached hall paint and the page transition complete before
    // starting the optional freshness requests.
    setTimeout(async () => {
      if (refreshSeq !== this._refreshSeq) return;
      try {
        if (this._syncPromise) {
          await this._syncPromise;
        } else {
          this._syncPromise = shared.syncServerTasks(userId).finally(() => {
            this._syncPromise = null;
          });
          await this._syncPromise;
        }
        paintTasks();
      } catch (error) {
        // Keep the local snapshot visible if the API is temporarily down, but
        // expose the freshness failure instead of pretending the snapshot is
        // the current server result.
        if (refreshSeq === this._refreshSeq) this.setData({ syncError: true });
      } finally {
        if (refreshSeq === this._refreshSeq) this.setData({ syncing: false });
      }
    }, 0);
  },

  async loadMutualStatus(user) {
    if (!user || this.data.accountLoading) return;
    this.setData({ accountLoading: true });
    try {
      const response = await api.fetchMutualHelpStatus(shared.getUserId(user));
      const data = response.data || {};
      const balances = shared.saveServerPointData(data, shared.getUserId(user));
      const config = data.config || {};
      this.setData({
        points: balances.total,
        basePoints: balances.base,
        rewardPoints: balances.reward,
        rewardPointsVisible: Boolean(user) && config.rechargeVisible === true,
        tasks: (this.data.tasks || []).map((task) => maskRewardLabels(task, Boolean(user) && config.rechargeVisible === true))
      });
    } catch (error) {
      // The local snapshot remains usable when the optional status refresh is
      // unavailable; it must not overwrite a known balance with zero.
    } finally {
      this.setData({ accountLoading: false });
    }
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
    if (this.data.syncing || this.data.syncError) {
      wx.showToast({ title: "正在确认最新任务，请稍后再试", icon: "none" });
      if (this.data.syncError) this.refresh();
      return;
    }
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
