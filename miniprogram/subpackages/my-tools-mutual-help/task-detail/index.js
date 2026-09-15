const shared = require("../shared");
const api = require("../../../services/api");
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
    commentEligible: false,
    commentSubmitting: false,
    commentPromptVisible: false,
    commentPromptText: "",
    commentPromptChoice: "",
    commentPromptSubmitting: false,
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
    this.activeTargetSession = null;
    this.targetReturnSession = null;
    this.returnNoticeText = "";
    this.loadTask();
  },

  onShow() {
    this.setData({ theme: shared.getTheme() });
    if (this.targetReturnSession && this.targetReturnSession.openedAt) {
      const session = this.targetReturnSession;
      this.targetReturnSession = null;
      this.recordTaskActivity("returned", session, {
        returnedAfterMs: Math.max(0, Date.now() - session.openedAt)
      });
      this.returnNoticeText = "已返回任务页，可提交完成记录。";
    }
    if (this.taskId && this.data.loaded) this.loadTask();
  },

  onHide() {
    if (this.activeTargetSession && !this.activeTargetSession.leftAt) {
      this.activeTargetSession.leftAt = Date.now();
    }
  },

  handleThemeChange(event) {
    this.setData({ theme: shared.saveTheme(event.currentTarget.dataset.theme) });
  },

  async loadTask() {
    const user = shared.getUser();
    const userId = shared.getUserId(user);
    let syncError = null;
    try {
      await shared.syncServerTask(this.taskId, user ? userId : "");
    } catch (error) {
      syncError = error;
      const statusCode = Number(error && error.statusCode || 0);
      const isDemoTask = String(this.taskId || "").startsWith("demo-");
      if (!isDemoTask && (statusCode === 404 || statusCode === 410)) {
        shared.removeTask(this.taskId);
        wx.showModal({
          title: "任务已不可用",
          content: String(error.detail || "任务已被发布者或管理员删除或暂停。"),
          showCancel: false,
          confirmText: "回任务大厅",
          success: () => this.handleBackToHome()
        });
        return;
      }
      // Public task details remain readable from the last snapshot during an outage.
    }
    let rawTask = shared.getTask(this.taskId);
    const task = shared.decorateTask(rawTask, userId);
    if (!task) {
      wx.showToast({ title: syncError && syncError.detail ? syncError.detail : "任务暂时无法加载，请重试", icon: "none" });
      setTimeout(() => wx.redirectTo({ url: "/subpackages/my-tools-mutual-help/index/index" }), 500);
      return;
    }
    const isOwner = Boolean(user && task.ownerUserId && task.ownerUserId === userId);
    const submission = shared.getSubmissionForTask(task, userId);
    const submissionStatus = submission && submission.status ? submission.status : "";
    const commentEligible = task.taskKind === "wool"
      ? !task.woolLocked
      : ["submitted", "reviewing", "approved", "completed"].includes(submissionStatus);
    const comments = Array.isArray(rawTask.serverComments) ? rawTask.serverComments : shared.getTaskComments(task.id, rawTask);
    const tipSent = Boolean(rawTask.serverWoolTip) || shared.getTaskTips(task.id, userId).length > 0;
    const refundRequested = Boolean(rawTask.serverWoolRefund && rawTask.serverWoolRefund.status === "pending") || shared.getTaskRefunds(task.id, "pending")
      .some((item) => String(item.requesterId || "") === userId);
    let pointBalances = user ? shared.getPointBalances(userId) : shared.getPointBalances("guest");
    if (user) {
      try {
        pointBalances = await shared.syncServerPointData(userId);
      } catch (error) {
        // Keep the last known balance visible when the optional refresh is down.
      }
    }
    const statusText = this.returnNoticeText || (task.taskKind === "wool"
      ? (isOwner ? "这是你发布的羊毛任务。" : "查看完整内容后即可使用福利；不需要提交材料。")
      : (submissionStatus === "completed" || submissionStatus === "approved"
        ? `已完成，${task.rewardText} 已到账`
        : (["submitted", "reviewing"].includes(submissionStatus) ? `已提交，${shared.AUTO_APPROVE_DAYS} 天未处理将自动通过` : "")));
    this.returnNoticeText = "";
    this.setData({
      task,
      isOwner,
      points: user ? pointBalances.total : 100,
      loaded: true,
      shareCardReady: false,
      shareCardImage: "",
      shareStatusText: "分享准备中",
      statusText,
      submissionStatus,
      commentEligible,
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

  handleBackToHome(afterNavigate) {
    if (this._navigatingToTaskHall) return;
    this._navigatingToTaskHall = true;
    const pages = typeof getCurrentPages === "function" ? getCurrentPages() : [];
    let taskHallIndex = -1;
    for (let index = pages.length - 2; index >= 0; index -= 1) {
      if (String(pages[index] && pages[index].route || "") === "subpackages/my-tools-mutual-help/index/index") {
        taskHallIndex = index;
        break;
      }
    }
    const onSuccess = () => {
      if (typeof afterNavigate === "function") afterNavigate();
    };
    const onFail = () => { this._navigatingToTaskHall = false; };
    if (taskHallIndex >= 0 && typeof wx.navigateBack === "function") {
      wx.navigateBack({ delta: pages.length - 1 - taskHallIndex, success: onSuccess, fail: onFail });
      return;
    }
    wx.redirectTo({
      url: "/subpackages/my-tools-mutual-help/index/index",
      success: onSuccess,
      fail: onFail
    });
  },

  handleSkipComment() {
    this.handleBackToHome();
  },

  noop() {},

  handleCommentPromptChoice(event) {
    this.setData({ commentPromptChoice: String(event.currentTarget.dataset.choice || "") });
  },

  handleCommentPromptInput(event) {
    this.setData({ commentPromptText: event.detail.value || "" });
  },

  handleSkipCommentPrompt() {
    if (this.data.commentPromptSubmitting) return;
    this.handleBackToHome();
  },

  async submitCommentPayload(task, user, text, recommendChoice) {
    if (String(task.id || "").indexOf("demo-") === 0) {
      const result = shared.addTaskComment(task.id, shared.getUserId(user), {
        text,
        recommendChoice,
        completed: ["submitted", "approved", "completed"].includes(this.data.submissionStatus),
        authorLabel: "互助用户"
      });
      if (!result.ok) throw new Error("评论提交失败");
      return;
    }
    await api.addMutualHelpComment(task.id, {
      userId: shared.getUserId(user),
      text,
      recommendChoice
    });
  },

  showCommentPublishedToast() {
    this.handleBackToHome(() => {
      wx.showToast({ title: "评论已发布", icon: "success", duration: 500 });
    });
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
      success: async (result = {}) => {
        if (!result.confirm) return;
        if (String(task.id || "").indexOf("demo-") === 0) {
          const outcome = shared.unlockWoolTask(task.id, shared.getUserId(user));
          if (!outcome.ok) {
            wx.showToast({ title: outcome.reason === "insufficient_points" ? "积分不足，暂时无法解锁" : "解锁失败，请稍后重试", icon: "none" });
            return;
          }
          this.loadTask();
          wx.showToast({ title: outcome.alreadyUnlocked ? "已解锁" : "解锁成功", icon: "success" });
          return;
        }
        try {
          const response = await api.unlockMutualHelpWool(task.id, shared.getUserId(user));
          const data = response && response.data ? response.data : {};
          this.loadTask();
          wx.showToast({ title: data.duplicate ? "已解锁" : "解锁成功", icon: "success" });
        } catch (error) {
          wx.showToast({ title: String((error && (error.detail || error.message)) || "解锁失败，请稍后重试"), icon: "none" });
        }
      }
    });
  },

  handleCommentChoice(event) {
    this.setData({ commentChoice: String(event.currentTarget.dataset.choice || "") });
  },

  handleCommentInput(event) {
    this.setData({ commentText: event.detail.value || "" });
  },

  async handleSubmitComment() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/task-detail/index?id=" + encodeURIComponent(this.taskId));
    if (!user) return;
    const task = this.data.task || {};
    if (!["miniapp", "ordinary", "wool"].includes(task.taskKind) || task.woolLocked) {
      wx.showToast({ title: task.taskKind === "wool" ? "解锁后才能评论" : "当前任务暂不支持评论", icon: "none" });
      return;
    }
    if (!this.data.commentEligible) {
      wx.showToast({ title: "提交完成记录后才能评论", icon: "none" });
      return;
    }
    if (this.data.commentSubmitting) return;
    const text = String(this.data.commentText || "").trim();
    const recommendChoice = String(this.data.commentChoice || "");
    if (!text && !recommendChoice) {
      wx.showToast({ title: "请先选择评价或写下评论", icon: "none" });
      return;
    }
    this.setData({ commentSubmitting: true });
    try {
      await this.submitCommentPayload(task, user, text, recommendChoice);
      this.setData({ commentSubmitting: false, commentText: "", commentChoice: "" });
      this.showCommentPublishedToast();
    } catch (error) {
      this.setData({ commentSubmitting: false });
      wx.showToast({ title: String((error && (error.detail || error.message)) || "评论提交失败"), icon: "none" });
    }
  },

  async handleSubmitCommentPrompt() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/task-detail/index?id=" + encodeURIComponent(this.taskId));
    if (!user) return;
    const task = this.data.task || {};
    const text = String(this.data.commentPromptText || "").trim();
    const recommendChoice = String(this.data.commentPromptChoice || "");
    if (!text && !recommendChoice) {
      wx.showToast({ title: "请先选择评价或写下评论", icon: "none" });
      return;
    }
    if (this.data.commentPromptSubmitting) return;
    this.setData({ commentPromptSubmitting: true });
    try {
      await this.submitCommentPayload(task, user, text, recommendChoice);
      this.setData({
        commentPromptVisible: false,
        commentPromptSubmitting: false,
        commentPromptText: "",
        commentPromptChoice: ""
      });
      this.showCommentPublishedToast();
    } catch (error) {
      this.setData({ commentPromptSubmitting: false });
      wx.showToast({ title: String((error && (error.detail || error.message)) || "评论提交失败"), icon: "none" });
    }
  },

  handleReportComment(event) {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/task-detail/index?id=" + encodeURIComponent(this.taskId));
    if (!user) return;
    const commentId = String(event.currentTarget.dataset.commentId || "");
    if (!commentId) return;
    wx.showActionSheet({
      itemList: ["内容不实", "链接失效", "疑似违规"],
      success: async (result = {}) => {
        const reasons = ["内容不实", "链接失效", "疑似违规"];
        const reason = reasons[result.tapIndex] || reasons[0];
        try {
          const report = String(this.taskId || "").indexOf("demo-") === 0
            ? shared.reportTaskComment(this.taskId, commentId, shared.getUserId(user), reason)
            : (await api.reportMutualHelpComment(this.taskId, commentId, shared.getUserId(user), reason)).data || {};
          wx.showToast({ title: report.alreadyReported || report.duplicate ? "你已举报过" : "举报已提交", icon: "none" });
        } catch (error) {
          wx.showToast({ title: String((error && (error.detail || error.message)) || "举报失败，请稍后重试"), icon: "none" });
        }
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
      success: async (result = {}) => {
        if (!result.confirm) return;
        try {
          const outcome = String(task.id || "").indexOf("demo-") === 0
            ? shared.requestWoolRefund(task.id, shared.getUserId(user), "任务内容或链接失效")
            : { ...(await api.requestMutualHelpWoolRefund(task.id, shared.getUserId(user), "任务内容或链接失效")).data, ok: true };
          if (!outcome.ok && !outcome.refund) throw new Error("请先解锁任务后再申请");
          this.setData({ refundRequested: true });
          wx.showToast({ title: outcome.alreadyRequested || outcome.duplicate ? "申请已在处理中" : "申请已提交", icon: "success" });
        } catch (error) {
          wx.showToast({ title: String((error && (error.detail || error.message)) || "请先解锁任务后再申请"), icon: "none" });
        }
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
      success: async (result = {}) => {
        const amounts = [1, 2, 5];
        const amount = amounts[result.tapIndex];
        if (!amount) return;
        try {
          const outcome = String(task.id || "").indexOf("demo-") === 0
            ? shared.tipTaskPublisher(task.id, shared.getUserId(user), amount)
            : { ...(await api.tipMutualHelpPublisher(task.id, shared.getUserId(user), amount)).data, ok: true };
          if (!outcome.ok) throw new Error(outcome.reason === "insufficient_points" ? "积分不足" : "暂时无法打赏");
          let points = shared.getPointBalances(shared.getUserId(user));
          if (String(task.id || "").indexOf("demo-") !== 0) {
            try { points = await shared.syncServerPointData(shared.getUserId(user)); } catch (error) {}
          }
          this.setData({ tipSent: true, points: points.total });
          wx.showToast({ title: "已打赏 " + amount + " 分", icon: "success" });
        } catch (error) {
          wx.showToast({ title: String((error && (error.detail || error.message)) || "暂时无法打赏"), icon: "none" });
        }
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

  recordTaskActivity(eventType, session, metadata = {}) {
    const task = this.data.task;
    const user = shared.getUser();
    if (!task || !user || !session) return;
    shared.recordActivity(eventType, task, shared.getUserId(user), {
      linkId: session.linkId || "",
      sessionId: session.sessionId || "",
      metadata
    }).catch(() => {});
  },

  createTargetSession(link) {
    return {
      sessionId: `task_session_${Date.now()}_${Math.floor(Math.random() * 100000)}`,
      linkId: String(link && link.id || ""),
      openedAt: 0,
      leftAt: 0
    };
  },

  copyLinkForBrowser(link) {
    const copyValue = String((link && (link.url || link.shortLink || link.raw)) || "").trim();
    if (!copyValue || typeof wx.setClipboardData !== "function") {
      wx.showToast({ title: "链接暂不可用", icon: "none" });
      return;
    }
    const isMiniapp = link.type === "miniapp" && !link.url;
    const isOfficialArticle = link.openMode === "official_article";
    wx.setClipboardData({
      data: copyValue,
      success: () => {
        const session = this.createTargetSession(link);
        this.recordTaskActivity("opened", session, { entryType: "copied_link" });
        wx.showModal({
          title: "链接已复制",
          content: isMiniapp
            ? "小程序暂时无法直接打开，请回到微信粘贴入口后重试。"
            : (isOfficialArticle
              ? "请回到微信打开公众号文章；也可以在手机浏览器中粘贴访问。"
              : (this.data.task && this.data.task.taskKind === "wool"
                ? "请打开手机浏览器，粘贴链接访问并按羊毛说明使用。"
                : "请打开手机浏览器，粘贴链接访问。返回后再提交任务材料。")),
          showCancel: false,
          confirmText: "知道了"
        });
      },
      fail: () => wx.showToast({ title: "复制失败，请长按链接重试", icon: "none" })
    });
  },

  openOfficialAccountArticle(link) {
    const url = String((link && link.url) || "").trim();
    if (!url || typeof wx.openOfficialAccountArticle !== "function") {
      this.copyLinkForBrowser(link);
      return;
    }
    wx.openOfficialAccountArticle({
      url,
      success: () => {
        const session = this.createTargetSession(link);
        session.openedAt = Date.now();
        this.targetReturnSession = session;
        this.recordTaskActivity("opened", session, { entryType: "official_article" });
        this.markLinkOpened(link);
        this.setData({ statusText: "已打开公众号文章，返回后可继续提交完成记录。" });
      },
      fail: () => this.copyLinkForBrowser(link)
    });
  },

  showMiniappOpenFallback(link) {
    wx.showModal({
      title: "小程序暂时无法打开",
      content: "可以复制入口，回到微信后粘贴尝试打开。",
      cancelText: "复制入口",
      confirmText: "知道了",
      success: (result = {}) => {
        if (result.cancel) this.copyLinkForBrowser(link);
      }
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
      if (link.openMode === "official_article") {
        this.openOfficialAccountArticle(link);
      } else if (link.openMode === "webview") {
        wx.navigateTo({
          url: `/subpackages/my-tools-mutual-help/web-view/index?src=${encodeURIComponent(link.url)}&title=${encodeURIComponent(link.title || "任务网页")}`,
          success: () => {
            const session = this.createTargetSession(link);
            session.openedAt = Date.now();
            this.targetReturnSession = session;
            this.recordTaskActivity("opened", session, { entryType: "webview" });
            this.markLinkOpened(link);
          },
          fail: () => this.copyLinkForBrowser(link)
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
    const session = this.createTargetSession(link);
    this.activeTargetSession = session;
    wx.navigateToMiniProgram({
      shortLink: link.shortLink,
      success: () => {
        session.openedAt = Date.now();
        this.targetReturnSession = session;
        this.markLinkOpened(link);
        this.recordTaskActivity("opened", session, { entryType: "miniapp" });
        this.setData({ statusText: "入口已打开，完成后返回提交记录。" });
      },
      fail: (error = {}) => {
        this.activeTargetSession = null;
        console.warn("[mutual-help] navigateToMiniProgram failed", error);
        const errMsg = String(error.errMsg || "");
        const wasCancelled = errMsg.toLowerCase().includes("cancel");
        this.recordTaskActivity(wasCancelled ? "open_cancelled" : "open_failed", session, { errMsg });
        if (wasCancelled) {
          wx.showToast({ title: "已取消打开", icon: "none" });
        } else {
          this.showMiniappOpenFallback(link);
        }
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

  handleOpenChat() {
    const user = shared.requireLogin(`/subpackages/my-tools-mutual-help/task-detail/index?id=${encodeURIComponent(this.taskId)}`);
    if (!user) return;
    wx.navigateTo({ url: `/subpackages/my-tools-mutual-help/chat/index?taskId=${encodeURIComponent(this.taskId)}` });
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

  async handleSubmit() {
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
    if (["submitted", "reviewing", "approved", "completed"].includes(this.data.submissionStatus)) {
      wx.showToast({ title: ["submitted", "reviewing"].includes(this.data.submissionStatus) ? "已提交，请等待处理" : "任务已完成", icon: "none" });
      return;
    }
    this.setData({ submitting: true });
    try {
      const response = await api.createMutualHelpSubmission(task.id, {
        userId: shared.getUserId(user),
        text: String(this.data.submissionText || "").trim(),
        images: this.data.submissionImages.slice()
      });
      const serverSubmission = response && response.data && response.data.submission;
      if (serverSubmission) shared.saveSubmission(serverSubmission, shared.getUserId(user));
      const settled = Boolean(response && response.data && response.data.settled);
      const userId = shared.getUserId(user);
      const balances = shared.getPointBalances(userId);
      const nextSubmissionStatus = serverSubmission && serverSubmission.status
        ? serverSubmission.status
        : (settled ? "completed" : "submitted");
      const reward = response && response.data && response.data.reward && typeof response.data.reward === "object"
        ? response.data.reward
        : {};
      const rewardPoints = Number(reward.points || task.executorReward || 0);
      const rewardPointTypeLabel = reward.pointType === shared.POINT_TYPE_REWARD
        ? shared.POINT_TYPE_LABELS[shared.POINT_TYPE_REWARD]
        : (task.rewardPointTypeLabel || shared.POINT_TYPE_LABELS[shared.POINT_TYPE_BASE]);
      const pendingStatusText = task.taskKind === "miniapp"
        ? `提交已收到，正在进行安全审核，审核通过后发放${rewardPointTypeLabel}。`
        : `已提交，预计获得 +${rewardPoints} ${rewardPointTypeLabel}；发布者 ${shared.AUTO_APPROVE_DAYS} 天未处理将自动通过`;
      this.setData({
        submitting: false,
        points: balances.total,
        submissionStatus: nextSubmissionStatus,
        commentEligible: task.taskKind === "wool" ? !task.woolLocked : ["submitted", "reviewing", "approved", "completed"].includes(nextSubmissionStatus),
        statusText: settled
          ? `任务已完成，+${rewardPoints} ${rewardPointTypeLabel}已到账`
          : pendingStatusText
      });
      shared.syncServerPointData(userId)
        .then((syncedBalances) => {
          if (!this.data.loaded || this._navigatingToTaskHall) return;
          this.setData({ points: syncedBalances.total });
        })
        .catch(() => {
          // The submission already succeeded; the next page refresh can retry
          // the optional balance synchronization.
        });
      if (settled) shared.recordActivity("completed", task, shared.getUserId(user)).catch(() => {});
      this.setData({
        commentPromptVisible: true,
        commentPromptText: "",
        commentPromptChoice: "",
        commentPromptSubmitting: false
      });
    } catch (error) {
      this.setData({ submitting: false });
      wx.showToast({ title: String((error && (error.detail || error.message)) || "提交失败，请稍后重试"), icon: "none" });
    }
  }
});
