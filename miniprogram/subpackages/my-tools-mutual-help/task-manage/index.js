const shared = require("../shared");
const {
  buildTaskShareMessage,
  buildTaskShareSource,
  getReadyTaskSnapshot,
  isTaskShareable,
  prepareTaskShareImageForList
} = require("../task-share");

function sortTasks(tasks) {
  return tasks.slice().sort((left, right) => {
    const createdAt = String(right.createdAt || "").localeCompare(String(left.createdAt || ""));
    if (createdAt) return createdAt;
    return String(right.id || "").localeCompare(String(left.id || ""));
  });
}

Page({
  data: {
    activeTab: "task",
    tabs: shared.TAB_ITEMS,
    taskStateFilter: "all",
    theme: shared.getTheme(),
    points: 100,
    tasks: [],
    publishedCount: 0,
    shareCardReady: false,
    shareCardImage: ""
  },

  onLoad() {
    if (!shared.requireLogin("/subpackages/my-tools-mutual-help/task-manage/index")) return;
    this.refresh();
  },

  onShow() {
    this.setData({ theme: shared.getTheme() });
    if (typeof wx.hideShareMenu === "function") wx.hideShareMenu({ menus: ["shareAppMessage", "shareTimeline"] });
    if (shared.getUser()) this.refresh();
  },

  refresh() {
    shared.syncAutoApprovedSubmissions();
    const user = shared.getUser();
    if (!user) return;
    const userId = shared.getUserId(user);
    const allTasks = shared.getTasks()
      .filter((task) => task.ownerUserId === userId)
      .filter((task) => task.status !== "deleted")
      .map((task) => shared.decorateTask(task, userId));
    const tasks = allTasks.filter((task) => {
      if (this.data.taskStateFilter === "active") return !task.taskClosed;
      if (this.data.taskStateFilter === "paused") return task.status === "paused";
      if (this.data.taskStateFilter === "closed") return task.taskClosed && task.status !== "paused";
      return true;
    });
    this.setData({
      points: shared.getPoints(userId),
      publishedCount: allTasks.length,
      tasks: sortTasks(tasks).map((task) => ({
        ...task,
        previewImage: ((getReadyTaskSnapshot(task, buildTaskShareSource(task)) || {}).url || ""),
        shareReady: Boolean(getReadyTaskSnapshot(task, buildTaskShareSource(task))),
        shareStatusText: isTaskShareable(task) ? "分享准备中" : "暂不可分享"
      }))
    });
    this.prepareTaskShares(tasks, userId);
  },

  async prepareTaskShares(tasks, userId) {
    const generation = Number(this.__sharePreparationGeneration || 0) + 1;
    this.__sharePreparationGeneration = generation;
    for (const task of tasks) {
      if (generation !== this.__sharePreparationGeneration) return;
      if (!isTaskShareable(task)) continue;
      const existing = getReadyTaskSnapshot(task, buildTaskShareSource(task));
      if (existing) {
        this.markTaskShareReady(task.id, existing.url, existing);
        continue;
      }
      try {
        const imageUrl = await prepareTaskShareImageForList(this, task, userId);
        if (generation !== this.__sharePreparationGeneration) return;
        const latest = shared.decorateTask(shared.getTask(task.id), userId) || task;
        const snapshot = getReadyTaskSnapshot(latest, buildTaskShareSource(latest));
        if (imageUrl && snapshot) this.markTaskShareReady(task.id, imageUrl, snapshot);
      } catch (error) {
        if (generation !== this.__sharePreparationGeneration) return;
        this.markTaskShareReady(task.id, "", null);
      }
    }
  },

  markTaskShareReady(taskId, imageUrl, snapshot) {
    const tasks = (this.data.tasks || []).map((task) => task.id === taskId
      ? {
          ...task,
          previewImage: imageUrl || task.previewImage,
          shareReady: Boolean(imageUrl),
          shareStatusText: imageUrl ? "分享任务" : "分享暂时失败",
          shareSnapshot: snapshot || task.shareSnapshot || null
        }
      : task);
    this.setData({ tasks, shareCardImage: imageUrl || "", shareCardReady: Boolean(imageUrl) });
    if (typeof wx.hideShareMenu === "function") wx.hideShareMenu({ menus: ["shareAppMessage", "shareTimeline"] });
  },

  handleTabChange(event) {
    shared.navigateTab(event.currentTarget.dataset.tab, this.data.activeTab);
  },

  handleThemeChange(event) {
    this.setData({ theme: shared.saveTheme(event.currentTarget.dataset.theme) });
  },

  handleStateFilterChange(event) {
    this.setData({ taskStateFilter: event.currentTarget.dataset.filter }, () => this.refresh());
  },

  handleOpenTask(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/subpackages/my-tools-mutual-help/task-manage/detail/index?id=${encodeURIComponent(id)}` });
  },

  handleSelectShareTask(event) {
    this.shareTaskId = String(event.currentTarget.dataset.id || "");
  },

  onShareAppMessage(options = {}) {
    const target = options.target || {};
    const dataset = target.dataset || {};
    const taskId = String(dataset.id || this.shareTaskId || "");
    const task = (this.data.tasks || []).find((item) => item.id === taskId);
    const message = buildTaskShareMessage(this, task);
    if (!message) wx.showToast({ title: "分享准备中，请稍后再试", icon: "none" });
    return message;
  },

  handleDeleteTask(event) {
    const user = shared.getUser();
    const taskId = String(event.currentTarget.dataset.id || "");
    if (!user || !taskId) return;
    const userId = shared.getUserId(user);
    const task = shared.getTasks().find((item) => item.id === taskId);
    if (!task || task.ownerUserId !== userId) {
      wx.showToast({ title: "只能删除自己发布的任务", icon: "none" });
      return;
    }
    wx.showModal({
      title: "删除这个任务？",
      content: "删除后会从任务大厅和你的任务列表隐藏，已有记录不会被改写。",
      confirmText: "删除",
      confirmColor: "#d85d2b",
      success: (result = {}) => {
        if (!result.confirm) return;
        const tasks = shared.getTasks().map((item) => item.id === taskId
          ? { ...item, status: "deleted", deletedAt: new Date().toISOString() }
          : item);
        shared.saveTasks(tasks);
        this.refresh();
        wx.showToast({ title: "任务已删除", icon: "success" });
      }
    });
  },

  handleGoPublish() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/publish/index");
    if (user) wx.redirectTo({ url: "/subpackages/my-tools-mutual-help/publish/index" });
  }
});
