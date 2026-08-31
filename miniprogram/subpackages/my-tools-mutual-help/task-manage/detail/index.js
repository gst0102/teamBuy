const shared = require("../../shared");
const {
  buildTaskShareMessage,
  prepareTaskShareImage
} = require("../../task-share");

function formatSubmissionTime(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) return "刚刚提交";
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${month}月${day}日 ${hour}:${minute}`;
}

Page({
  data: {
    task: null,
    points: 100,
    autoApproveDays: shared.AUTO_APPROVE_DAYS,
    submissions: [],
    comments: [],
    pendingRefundCount: 0,
    pendingReportCount: 0,
    theme: shared.getTheme(),
    loaded: false,
    statusText: "",
    shareCardReady: false,
    shareCardImage: "",
    shareStatusText: "分享准备中",
  },

  onLoad(options = {}) {
    this.taskId = String(options.id || "");
    this.loadTask();
  },

  onShow() {
    this.setData({ theme: shared.getTheme() });
    if (this.taskId && this.data.loaded) this.loadTask();
  },

  loadTask() {
    const user = shared.requireLogin(`/subpackages/my-tools-mutual-help/task-manage/detail/index?id=${encodeURIComponent(this.taskId)}`);
    if (!user) return;
    const rawTask = shared.getTask(this.taskId);
    const userId = shared.getUserId(user);
    if (!rawTask || rawTask.ownerUserId !== userId) {
      wx.showToast({ title: "只能管理自己发布的任务", icon: "none" });
      setTimeout(() => wx.redirectTo({ url: "/subpackages/my-tools-mutual-help/task-manage/index" }), 500);
      return;
    }
    shared.syncAutoApprovedSubmissions(this.taskId);
    const task = shared.decorateTask(shared.getTask(this.taskId), userId);
    const submissions = task.taskKind === "wool" ? [] : shared.getTaskSubmissions(task.id)
      .filter((item) => item.status === "submitted")
      .map((item) => ({
        ...item,
        submittedAtText: formatSubmissionTime(item.submittedAt),
        images: Array.isArray(item.images) ? item.images : []
      }));
    const comments = shared.getTaskComments(task.id, rawTask);
    this.setData({
      task,
      points: shared.getPoints(userId),
      submissions,
      comments,
      pendingRefundCount: shared.getTaskRefunds(task.id, "pending").length,
      pendingReportCount: shared.getTaskReports(task.id, "pending").length,
      loaded: true,
      shareCardReady: false,
      shareCardImage: "",
      shareStatusText: "分享准备中",
      statusText: task.status === "paused"
        ? "任务已暂停，执行者暂时无法领取。"
        : (task.taskClosed
          ? "任务已结束，新的执行者无法领取。"
          : (task.taskKind === "wool" ? "羊毛任务无需验收。" : "提交后按验收标准完成结算。"))
    }, () => {
      prepareTaskShareImage(this, task, userId).catch(() => {});
    });
  },

  handleThemeChange(event) {
    this.setData({ theme: shared.saveTheme(event.currentTarget.dataset.theme) });
  },

  handleBackToManage() {
    wx.redirectTo({ url: "/subpackages/my-tools-mutual-help/task-manage/index" });
  },

  onShareAppMessage() {
    const message = buildTaskShareMessage(this, this.data.task);
    if (!message) wx.showToast({ title: "分享准备中，请稍后再试", icon: "none" });
    return message;
  },

  getTaskLinks() {
    const task = this.data.task || {};
    return shared.normalizeTaskLinks(task.taskLinks, task.shortLink);
  },

  markLinkOpened(link) {
    const links = this.getTaskLinks().map((item) => item.id === link.id ? { ...item, opened: true } : item);
    this.setData({ "task.taskLinks": links });
  },

  copyLinkForBrowser(link) {
    if (!link || !link.url || typeof wx.setClipboardData !== "function") {
      wx.showToast({ title: "链接暂不可用", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: link.url,
      success: () => wx.showModal({
        title: "链接已复制",
        content: "请打开手机浏览器，粘贴链接访问。",
        showCancel: false,
        confirmText: "知道了"
      })
    });
  },

  handleOpenLink(event) {
    const task = this.data.task || {};
    const index = Number(event.currentTarget.dataset.index);
    const link = this.getTaskLinks()[index];
    if (!link) return;
    if (task.taskClosed) {
      wx.showToast({ title: "任务已结束", icon: "none" });
      return;
    }

    if (link.type === "web") {
      if (link.openMode === "webview") {
        wx.navigateTo({
          url: `/subpackages/my-tools-mutual-help/web-view/index?src=${encodeURIComponent(link.url)}&title=${encodeURIComponent(link.title || "任务网页")}`,
          success: () => this.markLinkOpened(link),
          fail: () => wx.showToast({ title: "网页暂时无法打开，请复制后用浏览器访问", icon: "none" })
        });
      } else {
        this.copyLinkForBrowser(link);
        this.markLinkOpened(link);
      }
      return;
    }

    if (!link.shortLink) {
      wx.showToast({ title: "暂时没有可用的小程序入口", icon: "none" });
      return;
    }
    wx.navigateToMiniProgram({
      shortLink: link.shortLink,
      success: () => {
        this.markLinkOpened(link);
        this.setData({ statusText: "已打开目标小程序，返回后可继续查看任务。" });
      },
      fail: (error = {}) => {
        console.warn("[mutual-help] navigateToMiniProgram failed", error);
        const errMsg = String(error.errMsg || "");
        wx.showToast({
          title: errMsg.includes("cancel") ? "已取消打开" : "目标小程序暂时无法打开",
          icon: "none"
        });
      }
    });
  },

  handleOpenTarget() {
    const index = this.getTaskLinks().findIndex((link) => link.type === "miniapp");
    if (index < 0) {
      wx.showToast({ title: "暂时没有可用的小程序入口", icon: "none" });
      return;
    }
    this.handleOpenLink({ currentTarget: { dataset: { index } } });
  },

  handleApproveSubmission(event) {
    const user = shared.requireLogin(`/subpackages/my-tools-mutual-help/task-manage/detail/index?id=${encodeURIComponent(this.taskId)}`);
    if (!user || !this.data.task) return;
    if (this.data.task.taskKind === "wool") {
      wx.showToast({ title: "羊毛不需要验收", icon: "none" });
      return;
    }
    const submissionId = String(event.currentTarget.dataset.submissionId || "");
    if (!submissionId) return;
    wx.showModal({
      title: "通过这次提交？",
      content: `通过后将扣除 ${Number(this.data.task.rewardPoints || 0)} 分，执行者获得 ${Number(this.data.task.executorReward || 0)} 分。`,
      confirmText: "通过验收",
      confirmColor: "#16835f",
      success: (result = {}) => {
        if (!result.confirm) return;
        const settlement = shared.approveSubmission(this.data.task.id, submissionId, shared.getUserId(user));
        if (!settlement.ok) {
          wx.showToast({ title: settlement.reason === "insufficient_publisher_points" ? "积分不足，暂时无法结算" : "提交状态已变化", icon: "none" });
          this.loadTask();
          return;
        }
        this.loadTask();
        wx.showToast({ title: "已通过并结算", icon: "success" });
      }
    });
  },

  handlePreviewExecutor() {
    if (!this.data.task || !this.data.task.id) return;
    wx.navigateTo({ url: `/subpackages/my-tools-mutual-help/task-detail/index?id=${encodeURIComponent(this.data.task.id)}&preview=1` });
  },

  handleTogglePause() {
    const task = this.data.task;
    if (!task || task.remaining === 0) {
      wx.showToast({ title: "任务已结束，不能恢复", icon: "none" });
      return;
    }
    const paused = task.status === "paused";
    wx.showModal({
      title: paused ? "恢复发布？" : "暂停发布？",
      content: paused ? "恢复后，其他用户可以继续在任务大厅看到这个任务。" : "暂停后，其他用户将不能领取这个任务；已提交的任务不受影响。",
      confirmText: paused ? "恢复发布" : "暂停发布",
      success: (result = {}) => {
        if (!result.confirm) return;
        const tasks = shared.getTasks().map((item) => item.id === task.id ? { ...item, status: paused ? "published" : "paused" } : item);
        shared.saveTasks(tasks);
        this.loadTask();
        wx.showToast({ title: paused ? "已恢复发布" : "已暂停发布", icon: "success" });
      }
    });
  },

  getTaskImageUrls() {
    const task = this.data.task || {};
    const acceptanceBlocks = task.taskKind === "wool" ? [] : (Array.isArray(task.acceptanceCriteriaBlocks) ? task.acceptanceCriteriaBlocks : []);
    return [
      ...(Array.isArray(task.contentBlocks) ? task.contentBlocks : []),
      ...acceptanceBlocks
    ]
      .filter((block) => block && block.type === "image" && String(block.url || "").trim())
      .map((block) => String(block.url).trim())
      .concat((this.data.submissions || []).flatMap((item) => Array.isArray(item.images) ? item.images : []));
  },

  handlePreviewImage(event) {
    const current = String(event.currentTarget.dataset.url || "").trim();
    const urls = this.getTaskImageUrls();
    if (!current || !urls.length || typeof wx.previewImage !== "function") return;
    wx.previewImage({ current, urls });
  },

  handleSaveImage(event) {
    const url = String(event.currentTarget.dataset.url || "").trim();
    if (!url) return;
    if (typeof wx.saveImageToPhotosAlbum !== "function") {
      wx.showToast({ title: "当前版本暂不支持保存图片", icon: "none" });
      return;
    }
    const save = (filePath) => {
      wx.saveImageToPhotosAlbum({
        filePath,
        success: () => wx.showToast({ title: "已保存到相册", icon: "success" }),
        fail: (error = {}) => {
          if (String(error.errMsg || "").includes("auth deny")) {
            wx.showModal({
              title: "需要相册权限",
              content: "请在设置中允许保存图片到相册。",
              confirmText: "去设置",
              success: (result = {}) => {
                if (result.confirm && typeof wx.openSetting === "function") wx.openSetting({});
              }
            });
            return;
          }
          wx.showToast({ title: "保存失败，请重试", icon: "none" });
        }
      });
    };
    if (/^(https?:)?\/\//.test(url) && typeof wx.downloadFile === "function") {
      if (typeof wx.showLoading === "function") wx.showLoading({ title: "准备图片" });
      wx.downloadFile({
        url,
        success: (result = {}) => {
          if (result.statusCode === 200 && result.tempFilePath) save(result.tempFilePath);
          else wx.showToast({ title: "图片下载失败", icon: "none" });
        },
        fail: () => wx.showToast({ title: "图片下载失败", icon: "none" }),
        complete: () => {
          if (typeof wx.hideLoading === "function") wx.hideLoading();
        }
      });
      return;
    }
    save(url);
  }
});
