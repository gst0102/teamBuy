const shared = require("../../shared");
const api = require("../../../../services/api");
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
    basePoints: 100,
    rewardPoints: 0,
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

  async loadTask() {
    const user = shared.requireLogin(`/subpackages/my-tools-mutual-help/task-manage/detail/index?id=${encodeURIComponent(this.taskId)}`);
    if (!user) return;
    const userId = shared.getUserId(user);
    try {
      await shared.syncServerTask(this.taskId, userId);
    } catch (error) {
      // Use the local snapshot only while the server is temporarily unavailable.
    }
    const rawTask = shared.getTask(this.taskId);
    if (!rawTask || rawTask.ownerUserId !== userId) {
      wx.showToast({ title: "只能管理自己发布的任务", icon: "none" });
      setTimeout(() => wx.redirectTo({ url: "/subpackages/my-tools-mutual-help/task-manage/index" }), 500);
      return;
    }
    const task = shared.decorateTask(shared.getTask(this.taskId), userId);
    let balances = shared.getPointBalances(userId);
    try {
      balances = await shared.syncServerPointData(userId);
    } catch (error) {
      // Keep the last known balance visible during a transient outage.
    }
    const submissions = task.taskKind === "wool" ? [] : shared.getTaskSubmissions(task.id)
      .map((item) => ({
        ...item,
        executorLabel: item.executorLabel || "互助用户",
        statusLabel: item.statusLabel || (item.rewardSettled
          ? "已结算"
          : (item.status === "submitted" ? "待验收" : (item.status === "approved" || item.status === "completed" ? "已验收" : "处理中"))),
        submittedAtText: formatSubmissionTime(item.submittedAt),
        statusAtText: formatSubmissionTime(item.approvedAt || item.completedAt || item.updatedAt || item.submittedAt),
        images: Array.isArray(item.images) ? item.images : []
      }));
    const comments = Array.isArray(rawTask.serverComments) ? rawTask.serverComments : shared.getTaskComments(task.id, rawTask);
    let chatParticipants = [];
    try {
      const participantResponse = await api.fetchMutualHelpChatParticipants(task.id, userId);
      chatParticipants = Array.isArray(participantResponse.data && participantResponse.data.items)
        ? participantResponse.data.items.map((item) => ({
          ...item,
          executorUserId: item.executor && item.executor.id || "",
          avatarInitial: String((item.executor && item.executor.nickname) || "互").slice(0, 1)
        }))
        : [];
    } catch (error) {
      // Chat availability must not prevent task review and acceptance.
    }
    this.setData({
      task,
      points: balances.total,
      basePoints: balances.base,
      rewardPoints: balances.reward,
      submissions,
      chatParticipants,
      comments,
      pendingRefundCount: Array.isArray(task.serverPendingRefunds) && task.serverPendingRefunds.length
        ? task.serverPendingRefunds.length
        : shared.getTaskRefunds(task.id, "pending").length,
      pendingReportCount: Number(task.serverPendingCommentReports || 0) || shared.getTaskReports(task.id, "pending").length,
      loaded: true,
      shareCardReady: false,
      shareCardImage: "",
      shareStatusText: "分享准备中",
      statusText: task.status === "paused"
        ? "任务已暂停，执行者暂时无法领取。"
        : (task.taskClosed
          ? "任务已结束，新的执行者无法领取。"
          : (task.taskKind === "wool" ? "羊毛任务无需验收。" : "提交后按完成标准完成结算。"))
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

  handleOpenChat(event) {
    const executorUserId = String(event.currentTarget.dataset.executorId || "");
    if (!executorUserId || !this.data.task) return;
    wx.navigateTo({
      url: `/subpackages/my-tools-mutual-help/chat/index?taskId=${encodeURIComponent(this.data.task.id)}&executorUserId=${encodeURIComponent(executorUserId)}`
    });
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
    const copyValue = String((link && (link.url || link.shortLink || link.raw)) || "").trim();
    if (!copyValue || typeof wx.setClipboardData !== "function") {
      wx.showToast({ title: "链接暂不可用", icon: "none" });
      return;
    }
    const isMiniapp = link.type === "miniapp" && !link.url;
    const isOfficialArticle = link.openMode === "official_article";
    wx.setClipboardData({
      data: copyValue,
      success: () => wx.showModal({
        title: "链接已复制",
        content: isMiniapp
          ? "小程序暂时无法直接打开，请回到微信粘贴入口后重试。"
          : (isOfficialArticle
            ? "请回到微信打开公众号文章；也可以在手机浏览器中粘贴访问。"
            : "请打开手机浏览器，粘贴链接访问。"),
        showCancel: false,
        confirmText: "知道了"
      }),
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
        this.markLinkOpened(link);
        this.setData({ statusText: "已打开公众号文章，返回后可继续查看任务。" });
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
          success: () => this.markLinkOpened(link),
          fail: () => this.copyLinkForBrowser(link)
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
        if (errMsg.toLowerCase().includes("cancel")) {
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
      content: `这次提交通过后，执行者将获得 ${Number(this.data.task.executorReward || 0)} ${this.data.task.rewardPointTypeLabel || "积分"}；发布者的 ${Number(this.data.task.rewardPoints || 0)} 分结算积分已在提交时预留。`,
      confirmText: "通过验收",
      confirmColor: "#16835f",
      success: (result = {}) => {
        if (!result.confirm) return;
        api.approveMutualHelpSubmission(this.data.task.id, submissionId, shared.getUserId(user)).then(() => {
          this.loadTask();
          wx.showToast({ title: "已通过并结算", icon: "success" });
        }).catch((error) => {
          wx.showToast({ title: String((error && (error.detail || error.message)) || "提交状态已变化"), icon: "none" });
          this.loadTask();
        });
      }
    });
  },

  handleRejectSubmission(event) {
    const user = shared.requireLogin(`/subpackages/my-tools-mutual-help/task-manage/detail/index?id=${encodeURIComponent(this.taskId)}`);
    if (!user || !this.data.task) return;
    const submissionId = String(event.currentTarget.dataset.submissionId || "");
    if (!submissionId) return;
    wx.showModal({
      title: "退回这次提交？",
      content: "请写明需要补充或修改的地方，发布者预留的结算积分会暂时释放。",
      editable: true,
      placeholderText: "例如：请补充第 2 步的截图或结果说明",
      confirmText: "退回提交",
      confirmColor: "#bd5a43",
      success: async (result = {}) => {
        if (!result.confirm) return;
        const reason = String(result.content || "").trim();
        if (!reason) {
          wx.showToast({ title: "请填写退回原因", icon: "none" });
          return;
        }
        try {
          await api.rejectMutualHelpSubmission(this.data.task.id, submissionId, shared.getUserId(user), reason);
          this.loadTask();
          wx.showToast({ title: "已退回提交，预留积分已释放", icon: "success" });
        } catch (error) {
          wx.showToast({ title: String((error && (error.detail || error.message)) || "提交状态已变化"), icon: "none" });
          this.loadTask();
        }
      }
    });
  },

  handlePreviewExecutor() {
    if (!this.data.task || !this.data.task.id) return;
    wx.navigateTo({ url: `/subpackages/my-tools-mutual-help/task-detail/index?id=${encodeURIComponent(this.data.task.id)}&preview=1` });
  },

  handleTogglePause() {
    const user = shared.requireLogin(`/subpackages/my-tools-mutual-help/task-manage/detail/index?id=${encodeURIComponent(this.taskId)}`);
    if (!user) return;
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
        api.updateMutualHelpTask(task.id, { ownerUserId: shared.getUserId(user), status: paused ? "published" : "paused" })
          .then(() => {
            this.loadTask();
            wx.showToast({ title: paused ? "已恢复发布" : "已暂停发布", icon: "success" });
          })
          .catch((error) => wx.showToast({ title: String((error && (error.detail || error.message)) || "操作失败，请稍后重试"), icon: "none" }));
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
