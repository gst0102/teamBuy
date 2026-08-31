const shared = require("../shared");
const {
  buildTaskShareMessage,
  prepareTaskShareImage
} = require("../task-share");

Page({
  data: {
    activeTab: "task",
    tabs: shared.TAB_ITEMS,
    task: null,
    isOwner: false,
    points: 100,
    hasOpenedTarget: false,
    submissionText: "",
    submissionImages: [],
    submissionStatus: "",
    submitting: false,
    statusText: "",
    comments: [],
    commentText: "",
    commentChoice: "",
    commentSubmitting: false,
    tipSent: false,
    refundRequested: false,
    loaded: false,
    shareCardReady: false,
    shareCardImage: "",
    shareStatusText: "分享准备中",
    theme: shared.getTheme()
  },

  onLoad(options = {}) {
    this.taskId = String(options.id || "");
    this.loadTask();
  },

  onShow() {
    this.setData({ theme: shared.getTheme() });
    if (this.taskId && this.data.loaded) this.loadTask();
  },

  handleThemeChange(event) {
    this.setData({ theme: shared.saveTheme(event.currentTarget.dataset.theme) });
  },

  loadTask() {
    const user = shared.getUser();
    const userId = shared.getUserId(user);
    shared.syncAutoApprovedSubmissions(this.taskId);
    let rawTask = shared.getTask(this.taskId);
    if (rawTask && rawTask.taskKind === "wool" && String(rawTask.ownerUserId || "") !== userId
        && shared.normalizeWoolPolicy(rawTask.woolPolicy, rawTask).unlockFeePoints === 0) {
      shared.unlockWoolTask(rawTask.id, userId);
      rawTask = shared.getTask(this.taskId);
    }
    const task = shared.decorateTask(rawTask, userId);
    if (!task) {
      wx.showToast({ title: "任务不存在", icon: "none" });
      setTimeout(() => wx.redirectTo({ url: "/subpackages/my-tools-mutual-help/index/index" }), 500);
      return;
    }
    const isOwner = Boolean(user && task.ownerUserId && task.ownerUserId === userId);
    const submission = task.taskKind === "wool"
      ? null
      : shared.getSubmissions(userId).find((item) => item.taskId === task.id);
    const submissionStatus = submission && submission.status ? submission.status : "";
    const comments = shared.getTaskComments(task.id, rawTask);
    const tipSent = shared.getTaskTips(task.id, userId).length > 0;
    const refundRequested = shared.getTaskRefunds(task.id, "pending")
      .some((item) => String(item.requesterId || "") === userId);
    const statusText = task.taskKind === "wool"
      ? (isOwner ? "这是你发布的羊毛任务。" : "查看完整内容后即可使用福利；不需要提交材料。")
      : (submissionStatus === "completed" || submissionStatus === "approved"
        ? `已完成，+${Number(task.executorReward || 0)} 积分已到账`
        : (submissionStatus === "submitted" ? `已提交，${shared.AUTO_APPROVE_DAYS} 天未处理将自动通过` : ""));
    this.setData({
      task,
      isOwner,
      points: user ? shared.getPoints(userId) : 100,
      loaded: true,
      shareCardReady: false,
      shareCardImage: "",
      shareStatusText: "分享准备中",
      statusText,
      submissionStatus,
      comments,
      tipSent,
      refundRequested,
      submissionText: submission && submission.text ? submission.text : "",
      submissionImages: submission && Array.isArray(submission.images) ? submission.images : []
    }, () => {
      prepareTaskShareImage(this, task, task.ownerUserId || "").catch(() => {});
    });
  },

  onShareAppMessage() {
    const message = buildTaskShareMessage(this, this.data.task);
    if (!message) wx.showToast({ title: "分享准备中，请稍后再试", icon: "none" });
    return message;
  },

  handleTabChange(event) {
    shared.navigateTab(event.currentTarget.dataset.tab, this.data.activeTab, this.taskId ? `id=${encodeURIComponent(this.taskId)}` : "");
  },

  handleBackToHome() {
    wx.redirectTo({ url: "/subpackages/my-tools-mutual-help/index/index" });
  },

  handleUnlockWool() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/task-detail/index?id=" + encodeURIComponent(this.taskId));
    if (!user) return;
    const task = this.data.task || {};
    if (task.taskKind !== "wool" || !task.woolLocked) return;
    const feePoints = Number(task.woolPolicy && task.woolPolicy.unlockFeePoints || 0);
    wx.showModal({
      title: "解锁完整羊毛内容？",
      content: "将支付 " + feePoints + " 分，解锁后可查看完整福利说明和使用入口。同一任务只收费一次。",
      confirmText: "确认解锁",
      confirmColor: "#d85d2b",
      success: (result = {}) => {
        if (!result.confirm) return;
        const outcome = shared.unlockWoolTask(task.id, shared.getUserId(user));
        if (!outcome.ok) {
          const message = outcome.reason === "insufficient_points" ? "积分不足，暂时无法解锁" : "解锁失败，请稍后重试";
          wx.showToast({ title: message, icon: "none" });
          return;
        }
        this.loadTask();
        wx.showToast({ title: outcome.alreadyUnlocked ? "已解锁" : "解锁成功", icon: "success" });
      }
    });
  },

  handleCommentChoice(event) {
    this.setData({ commentChoice: String(event.currentTarget.dataset.choice || "") });
  },

  handleCommentInput(event) {
    this.setData({ commentText: event.detail.value || "" });
  },

  handleSubmitComment() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/task-detail/index?id=" + encodeURIComponent(this.taskId));
    if (!user) return;
    const task = this.data.task || {};
    if (!["ordinary", "wool"].includes(task.taskKind) || task.woolLocked) {
      wx.showToast({ title: "解锁后才能评论", icon: "none" });
      return;
    }
    if (this.data.commentSubmitting) return;
    if (!String(this.data.commentText || "").trim() && !this.data.commentChoice) {
      wx.showToast({ title: "请先选择评价或写下评论", icon: "none" });
      return;
    }
    this.setData({ commentSubmitting: true });
    const result = shared.addTaskComment(task.id, shared.getUserId(user), {
      text: this.data.commentText,
      recommendChoice: this.data.commentChoice,
      completed: ["approved", "completed"].includes(this.data.submissionStatus),
      authorLabel: "互助用户"
    });
    if (!result.ok) {
      this.setData({ commentSubmitting: false });
      wx.showToast({ title: "评论提交失败", icon: "none" });
      return;
    }
    this.setData({ commentSubmitting: false, commentText: "", commentChoice: "" });
    this.loadTask();
    wx.showToast({ title: "评论已发布", icon: "success" });
  },

  handleReportComment(event) {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/task-detail/index?id=" + encodeURIComponent(this.taskId));
    if (!user) return;
    const commentId = String(event.currentTarget.dataset.commentId || "");
    if (!commentId) return;
    wx.showActionSheet({
      itemList: ["内容不实", "链接失效", "疑似违规"],
      success: (result = {}) => {
        const reasons = ["内容不实", "链接失效", "疑似违规"];
        const report = shared.reportTaskComment(this.taskId, commentId, shared.getUserId(user), reasons[result.tapIndex] || reasons[0]);
        wx.showToast({ title: report.alreadyReported ? "你已举报过" : "举报已提交", icon: "none" });
      }
    });
  },

  handleRequestWoolRefund() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/task-detail/index?id=" + encodeURIComponent(this.taskId));
    if (!user || this.data.refundRequested) return;
    const task = this.data.task || {};
    if (task.taskKind !== "wool" || task.woolLocked) return;
    wx.showModal({
      title: "申请解锁退款",
      content: "仅适用于任务内容、入口或活动已明显失效的情况，提交后会进行审核。",
      confirmText: "提交申请",
      confirmColor: "#d85d2b",
      success: (result = {}) => {
        if (!result.confirm) return;
        const outcome = shared.requestWoolRefund(task.id, shared.getUserId(user), "任务内容或链接失效");
        if (!outcome.ok) {
          wx.showToast({ title: "请先解锁任务后再申请", icon: "none" });
          return;
        }
        this.setData({ refundRequested: true });
        wx.showToast({ title: outcome.alreadyRequested ? "申请已在处理中" : "申请已提交", icon: "success" });
      }
    });
  },

  handleTipPublisher() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/task-detail/index?id=" + encodeURIComponent(this.taskId));
    if (!user) return;
    const task = this.data.task || {};
    if (task.taskKind !== "wool" || !task.woolAllowTip || task.woolLocked || this.data.isOwner || this.data.tipSent) return;
    if (!shared.getTaskAccess(task, shared.getUserId(user)).unlocked) {
      wx.showToast({ title: "解锁后才可以打赏", icon: "none" });
      return;
    }
    wx.showActionSheet({
      itemList: ["打赏 1 分", "打赏 2 分", "打赏 5 分"],
      success: (result = {}) => {
        const amounts = [1, 2, 5];
        const amount = amounts[result.tapIndex];
        if (!amount) return;
        const outcome = shared.tipTaskPublisher(task.id, shared.getUserId(user), amount);
        if (!outcome.ok) {
          wx.showToast({ title: outcome.reason === "insufficient_points" ? "积分不足" : "暂时无法打赏", icon: "none" });
          return;
        }
        this.setData({ tipSent: true, points: shared.getPoints(shared.getUserId(user)) });
        wx.showToast({ title: "已打赏 " + amount + " 分", icon: "success" });
      }
    });
  },

  getTaskLinks() {
    const task = this.data.task || {};
    return shared.normalizeTaskLinks(task.taskLinks, task.shortLink);
  },

  markLinkOpened(link) {
    const links = this.getTaskLinks().map((item) => item.id === link.id ? { ...item, opened: true } : item);
    this.setData({
      "task.taskLinks": links,
      hasOpenedTarget: link.type === "miniapp" ? true : this.data.hasOpenedTarget
    });
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
        content: this.data.task && this.data.task.taskKind === "wool"
          ? "请打开手机浏览器，粘贴链接访问并按羊毛说明使用。"
          : "请打开手机浏览器，粘贴链接访问。返回后再提交任务材料。",
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
      wx.showToast({ title: "该任务暂时没有可用的小程序入口", icon: "none" });
      return;
    }
    wx.navigateToMiniProgram({
      shortLink: link.shortLink,
      success: () => this.markLinkOpened(link),
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
      wx.showToast({ title: "该任务暂时没有可用的小程序入口", icon: "none" });
      return;
    }
    this.handleOpenLink({ currentTarget: { dataset: { index } } });
  },

  handleSubmissionInput(event) {
    this.setData({ submissionText: event.detail.value || "" });
  },

  getTaskImageUrls() {
    const task = this.data.task || {};
    const acceptanceBlocks = task.taskKind === "wool"
      ? []
      : (Array.isArray(task.acceptanceCriteriaBlocks) ? task.acceptanceCriteriaBlocks : []);
    return [
      ...(Array.isArray(task.contentBlocks) ? task.contentBlocks : []),
      ...acceptanceBlocks
    ]
      .filter((block) => block && block.type === "image" && String(block.url || "").trim())
      .map((block) => String(block.url).trim());
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
    if (/^(https?:)?\/\//.test(url)) {
      wx.showToast({ title: "当前版本暂不支持保存网络图片", icon: "none" });
      return;
    }
    save(url);
  },

  handleChooseImages() {
    if (typeof wx.chooseImage !== "function") {
      wx.showToast({ title: "当前版本暂不支持选图", icon: "none" });
      return;
    }
    const current = Array.isArray(this.data.submissionImages) ? this.data.submissionImages.length : 0;
    wx.chooseImage({
      count: Math.max(1, Math.min(6 - current, 6)),
      sourceType: ["album", "camera"],
      success: (result = {}) => {
        const paths = Array.isArray(result.tempFilePaths) ? result.tempFilePaths : [];
        this.setData({ submissionImages: [...this.data.submissionImages, ...paths].slice(0, 6) });
      }
    });
  },

  handleRemoveImage(event) {
    const index = Number(event.currentTarget.dataset.index);
    const images = this.data.submissionImages.slice();
    if (!Number.isInteger(index) || index < 0 || index >= images.length) return;
    images.splice(index, 1);
    this.setData({ submissionImages: images });
  },

  handleSubmit() {
    const user = shared.requireLogin(`/subpackages/my-tools-mutual-help/task-detail/index?id=${encodeURIComponent(this.taskId)}`);
    if (!user) return;
    const task = this.data.task || {};
    if (task.taskKind === "wool") {
      wx.showToast({ title: "羊毛无需提交材料，打开入口即可使用", icon: "none" });
      return;
    }
    if (task.taskClosed) {
      wx.showToast({ title: "任务已结束，不能提交", icon: "none" });
      return;
    }
    if (task.taskKind === "wool" && task.woolLocked) {
      wx.showToast({ title: "请先解锁任务完整内容", icon: "none" });
      return;
    }
    if (task.taskKind === "miniapp" && !this.data.hasOpenedTarget) {
      wx.showToast({ title: "请先打开目标小程序", icon: "none" });
      return;
    }
    if (task.taskKind === "ordinary" && !String(this.data.submissionText || "").trim() && !this.data.submissionImages.length) {
      wx.showToast({ title: "请提交文字或图片材料", icon: "none" });
      return;
    }
    if (this.data.submitting) return;
    if (["submitted", "approved", "completed"].includes(this.data.submissionStatus)) {
      wx.showToast({ title: this.data.submissionStatus === "submitted" ? "已提交，请等待验收" : "任务已完成", icon: "none" });
      return;
    }
    this.setData({ submitting: true });
    const submission = shared.saveSubmission({
      taskId: task.id,
      status: task.taskKind === "miniapp" ? "completed" : "submitted",
      autoApproved: task.taskKind === "miniapp",
      text: String(this.data.submissionText || "").trim(),
      images: this.data.submissionImages.slice(),
      submittedAt: new Date().toISOString()
    }, shared.getUserId(user));
    shared.recordActivity("completed", task, shared.getUserId(user)).catch(() => {});
    if (task.taskKind === "miniapp") {
      const result = shared.settleSubmission(submission);
      if (!result.ok) {
        shared.saveSubmission({ ...submission, status: "submitted", autoApproved: false }, shared.getUserId(user));
        this.setData({ submitting: false, submissionStatus: "submitted", statusText: result.reason === "insufficient_publisher_points" ? "发布者积分不足，任务暂时无法结算" : "任务暂时无法结算，请稍后重试" });
        wx.showToast({ title: "暂时无法结算", icon: "none" });
        return;
      }
      this.setData({
        submitting: false,
        points: shared.getPoints(shared.getUserId(user)),
        submissionStatus: "completed",
        statusText: `任务已完成，+${Number(task.executorReward || 0)} 积分已到账`
      });
      wx.showToast({ title: `已完成，+${Number(task.executorReward || 0)}分`, icon: "success" });
      return;
    }
    this.setData({ submitting: false, submissionStatus: "submitted", statusText: `已提交，发布者 ${shared.AUTO_APPROVE_DAYS} 天未处理将自动通过` });
    wx.showToast({ title: "已提交，等待验收", icon: "success" });
  }
});
