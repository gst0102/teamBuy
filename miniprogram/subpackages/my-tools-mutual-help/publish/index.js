const shared = require("../shared");
const api = require("../../../services/api");

Page({
  data: {
    activeTab: "publish",
    tabs: shared.TAB_ITEMS,
    taskKind: "ordinary",
    categories: shared.CATEGORY_OPTIONS,
    draft: {
      title: "",
      taskLinks: [],
      linkInput: "",
      linkTitle: "",
      miniDescription: "",
      completionCriteria: "",
      repeatPolicy: "once",
      category: "互助",
      contentBlocks: [{ id: "draft-content-text", type: "text", text: "", url: "" }],
      acceptanceBlocks: [{ id: "draft-acceptance-text", type: "text", text: "", url: "" }],
      quota: "",
      rewardPoints: "5",
      rewardPointType: "base",
      woolUnlockFee: "0",
      woolAllowTip: true
    },
    currentPoints: 100,
    currentPointTypePoints: 100,
    currentPointTypeLabel: "基础积分",
    rechargeVisible: false,
    // 任务入口是可选，但不能默认藏起来；普通任务和羊毛任务都要让
    // 发布者第一眼看到可以粘贴公众号、网页或目标小程序链接。
    advancedOpen: true,
    publishing: false,
    accountLoading: false,
    kindCopy: shared.getTaskKindCopy("ordinary"),
    theme: shared.getTheme()
  },

  onShow() {
    const user = shared.getUser();
    const userId = shared.getUserId(user);
    const balances = shared.getPointBalances(userId);
    this.setData({
      currentPoints: user ? balances.total : 100,
      currentPointTypePoints: user ? balances.base : 100,
      currentPointTypeLabel: "基础积分",
      rechargeVisible: false,
      theme: shared.getTheme()
    });
    this.loadPointStatus(user);
  },

  async loadPointStatus(user) {
    if (!user || this.data.accountLoading) return;
    this.setData({ accountLoading: true });
    try {
      const response = await api.fetchMutualHelpStatus(shared.getUserId(user));
      const data = response.data || {};
      const balances = shared.saveServerPointData(data, shared.getUserId(user));
      const rechargeVisible = data.config && data.config.rechargeVisible === true;
      const pointType = rechargeVisible ? shared.taskPointType(this.data.draft || {}) : shared.POINT_TYPE_BASE;
      const draft = !rechargeVisible && this.data.draft.rewardPointType === shared.POINT_TYPE_REWARD
        ? { ...this.data.draft, rewardPointType: shared.POINT_TYPE_BASE }
        : this.data.draft;
      this.setData({
        draft,
        rechargeVisible,
        currentPoints: balances.total,
        currentPointTypePoints: balances[pointType],
        currentPointTypeLabel: shared.POINT_TYPE_LABELS[pointType]
      });
    } catch (error) {
      // Draft editing remains available when the optional refresh is down.
    } finally {
      this.setData({ accountLoading: false });
    }
  },

  handleThemeChange(event) {
    this.setData({ theme: shared.saveTheme(event.currentTarget.dataset.theme) });
  },

  handleTabChange(event) {
    shared.navigateTab(event.currentTarget.dataset.tab, this.data.activeTab);
  },

  handleTaskKindChange(event) {
    const taskKind = event.currentTarget.dataset.kind;
    const nextCategories = taskKind === "wool" ? shared.WOOL_CATEGORY_OPTIONS : shared.CATEGORY_OPTIONS;
    const nextCategory = taskKind === "wool" ? "优惠券/折扣" : "互助";
    const nextPointType = taskKind === "wool" || !this.data.rechargeVisible
      ? shared.POINT_TYPE_BASE
      : (this.data.draft.rewardPointType === shared.POINT_TYPE_REWARD ? shared.POINT_TYPE_REWARD : shared.POINT_TYPE_BASE);
    const balances = shared.getPointBalances(shared.getUserId());
    this.setData({
      taskKind,
      categories: nextCategories,
      kindCopy: shared.getTaskKindCopy(taskKind),
      "draft.category": nextCategory,
      "draft.rewardPointType": nextPointType,
      currentPointTypePoints: balances[nextPointType],
      currentPointTypeLabel: shared.POINT_TYPE_LABELS[nextPointType],
      ...(taskKind === "wool" ? { "draft.repeatPolicy": "once" } : {})
    });
  },

  handleRewardPointTypeChange(event) {
    if (event.currentTarget.dataset.pointType === shared.POINT_TYPE_REWARD && !this.data.rechargeVisible) {
      wx.showToast({ title: "充值积分奖励暂未开放", icon: "none" });
      return;
    }
    const rewardPointType = event.currentTarget.dataset.pointType === shared.POINT_TYPE_REWARD
      ? shared.POINT_TYPE_REWARD
      : shared.POINT_TYPE_BASE;
    const balances = shared.getPointBalances(shared.getUserId());
    this.setData({
      "draft.rewardPointType": rewardPointType,
      currentPointTypePoints: balances[rewardPointType],
      currentPointTypeLabel: shared.POINT_TYPE_LABELS[rewardPointType]
    });
  },

  handleRepeatPolicyChange(event) {
    const repeatPolicy = event.currentTarget.dataset.policy === "daily" ? "daily" : "once";
    this.setData({ "draft.repeatPolicy": repeatPolicy });
  },

  handleToggleAdvanced() {
    this.setData({ advancedOpen: !this.data.advancedOpen });
  },

  handleWoolUnlockMode(event) {
    const mode = event.currentTarget.dataset.mode;
    this.setData({ "draft.woolUnlockFee": mode === "paid" ? (this.data.draft.woolUnlockFee === "0" ? "2" : this.data.draft.woolUnlockFee) : "0" });
  },

  handleWoolTipToggle() {
    this.setData({ "draft.woolAllowTip": !this.data.draft.woolAllowTip });
  },

  handleInput(event) {
    const field = event.currentTarget.dataset.field;
    if (!field) return;
    this.setData({ [`draft.${field}`]: event.detail.value || "" });
  },

  handleCategoryChange(event) {
    this.setData({ "draft.category": event.currentTarget.dataset.category });
  },

  getDraftWithPendingTaskLink() {
    const draft = this.data.draft || {};
    const raw = String(draft.linkInput || "").trim();
    const title = String(draft.linkTitle || "").trim();
    if (!raw) return { ok: true, changed: false, draft };
    const result = shared.parseTaskLink(raw, title);
    if (!result.ok) return result;
    if (this.data.taskKind === "miniapp" && result.link.type !== "miniapp") {
      return { ok: false, error: "小程序任务请添加小程序短链接" };
    }
    const current = Array.isArray(draft.taskLinks) ? draft.taskLinks.slice() : [];
    if (current.some((item) => String(item.raw || item.url || "") === raw)) {
      return { ok: false, error: "这个入口已经添加" };
    }
    if (this.data.taskKind === "miniapp" && current.some((item) => item.type === "miniapp")) {
      return { ok: false, error: "小程序任务只能配置一个小程序入口" };
    }
    if (current.length >= 6) {
      return { ok: false, error: "最多添加 6 个任务入口" };
    }
    current.push({
      ...result.link,
      id: `draft_task_link_${Date.now()}_${current.length}`
    });
    return {
      ok: true,
      changed: true,
      draft: {
        ...draft,
        taskLinks: current,
        linkInput: "",
        linkTitle: ""
      }
    };
  },

  handleAddTaskLink() {
    const result = this.getDraftWithPendingTaskLink();
    if (!result.ok) {
      wx.showToast({ title: result.error, icon: "none" });
      return;
    }
    if (result.changed) this.setData({ draft: result.draft });
  },

  handleRemoveTaskLink(event) {
    const index = Number(event.currentTarget.dataset.index);
    const current = Array.isArray(this.data.draft.taskLinks) ? this.data.draft.taskLinks.slice() : [];
    if (!Number.isInteger(index) || index < 0 || index >= current.length) return;
    current.splice(index, 1);
    this.setData({ "draft.taskLinks": current });
  },

  handleAddTextBlock(event) {
    const field = event.currentTarget.dataset.blockField;
    const current = Array.isArray(this.data.draft[field]) ? this.data.draft[field].slice() : [];
    if (!field || current.length >= 12) return;
    current.push({
      id: `block_text_${Date.now()}_${current.length}`,
      type: "text",
      text: "",
      url: ""
    });
    this.setData({ [`draft.${field}`]: current });
  },

  handleChooseImages(event) {
    const field = event.currentTarget.dataset.blockField;
    const current = Array.isArray(this.data.draft[field]) ? this.data.draft[field].slice() : [];
    const imageCount = current.filter((item) => item && item.type === "image").length;
    if (!field || imageCount >= 6 || current.length >= 12 || typeof wx.chooseImage !== "function") {
      if (typeof wx.chooseImage !== "function") wx.showToast({ title: "当前版本暂不支持选图", icon: "none" });
      return;
    }
    wx.chooseImage({
      count: Math.min(6 - imageCount, 6, 12 - current.length),
      sourceType: ["album", "camera"],
      success: (result = {}) => {
        const paths = Array.isArray(result.tempFilePaths) ? result.tempFilePaths : [];
        const imageBlocks = paths.map((url, index) => ({
          id: `block_image_${Date.now()}_${index}`,
          type: "image",
          text: "",
          url
        }));
        this.setData({ [`draft.${field}`]: current.concat(imageBlocks).slice(0, 12) });
      }
    });
  },

  handleBlockInput(event) {
    const field = event.currentTarget.dataset.blockField;
    const index = Number(event.currentTarget.dataset.index);
    const blocks = Array.isArray(this.data.draft[field]) ? this.data.draft[field].slice() : [];
    if (!Number.isInteger(index) || index < 0 || index >= blocks.length || blocks[index].type !== "text") return;
    blocks[index] = { ...blocks[index], text: event.detail.value || "" };
    this.setData({ [`draft.${field}`]: blocks });
  },

  handleRemoveBlock(event) {
    const field = event.currentTarget.dataset.blockField;
    const index = Number(event.currentTarget.dataset.index);
    const blocks = Array.isArray(this.data.draft[field]) ? this.data.draft[field].slice() : [];
    if (!Number.isInteger(index) || index < 0 || index >= blocks.length) return;
    blocks.splice(index, 1);
    this.setData({ [`draft.${field}`]: blocks });
  },

  validateDraft(user, draft = this.data.draft) {
    if (!String(draft.title || "").trim()) return "请填写任务标题";
    if (draft.rewardPointType === shared.POINT_TYPE_REWARD && !this.data.rechargeVisible) return "充值积分奖励暂未开放";
    if (this.data.taskKind === "miniapp") {
      if (!shared.normalizeTaskLinks(draft.taskLinks).some((link) => link.type === "miniapp")) return "请添加小程序短链接";
      if (!String(draft.completionCriteria || "").trim()) return "请填写完成标准";
      if (draft.rewardPointType === shared.POINT_TYPE_REWARD && (!String(draft.quota || "").trim() || Number(draft.quota) < 1)) return "充值积分奖励任务必须填写任务次数";
      return "";
    }
    if (!draft.category) return "请选择任务分类";
    if (!shared.normalizeBlocks(draft.contentBlocks).length) return "请添加任务内容文字段或图片段";
    if (this.data.taskKind === "ordinary" && !shared.normalizeBlocks(draft.acceptanceBlocks).length) return "请添加完成标准文字段或图片段";
    const reward = this.data.taskKind === "wool" ? 0 : Number(draft.rewardPoints);
    if (!Number.isFinite(reward) || reward < 0) return "任务积分请填写 0 或正整数";
    if (this.data.taskKind !== "wool" && reward < 5) return "任务积分最低为 5 分";
    if (this.data.taskKind === "wool" && (!/^\d+$/.test(String(draft.woolUnlockFee || "").trim()) || Number(draft.woolUnlockFee) < 0)) return "查看费用请填写 0 或正整数";
    if (String(draft.quota || "").trim() && (!/^\d+$/.test(String(draft.quota).trim()) || Number(draft.quota) < 1)) return "任务次数请填写正整数";
    if (this.data.taskKind !== "wool" && draft.rewardPointType === shared.POINT_TYPE_REWARD && (!String(draft.quota || "").trim() || Number(draft.quota) < 1)) return "充值积分奖励任务必须填写任务次数";
    if (!user) return "";
    return "";
  },

  async handlePublish() {
    if (this.data.publishing) return;
    const returnUrl = "/subpackages/my-tools-mutual-help/publish/index";
    const user = shared.requireLogin(returnUrl);
    if (!user) return;
    const pendingLink = this.getDraftWithPendingTaskLink();
    if (!pendingLink.ok) {
      wx.showToast({ title: pendingLink.error, icon: "none" });
      return;
    }
    const draft = pendingLink.draft;
    if (pendingLink.changed) this.setData({ draft });
    const errorMessage = this.validateDraft(user, draft);
    if (errorMessage) {
      wx.showToast({ title: errorMessage, icon: "none" });
      return;
    }
    const rewardPoints = this.data.taskKind === "miniapp"
      ? 5
      : (this.data.taskKind === "wool" ? 0 : Number(draft.rewardPoints));
    const taskLinks = shared.normalizeTaskLinks(draft.taskLinks);
    const contentBlocks = this.data.taskKind === "miniapp"
      ? shared.buildBlocks(draft.miniDescription, [])
      : shared.normalizeBlocks(draft.contentBlocks);
    const acceptanceCriteriaBlocks = this.data.taskKind === "miniapp"
      ? [{ type: "text", text: String(draft.completionCriteria || "").trim() }]
      : (this.data.taskKind === "ordinary" ? shared.normalizeBlocks(draft.acceptanceBlocks) : []);
    const firstTextBlock = contentBlocks.find((block) => block.type === "text");
    const task = {
      id: `local_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
      taskKind: this.data.taskKind,
      repeatPolicy: this.data.taskKind === "wool"
        ? "once"
        : (draft.repeatPolicy === "daily" ? "daily" : "once"),
      title: String(draft.title).trim(),
      category: this.data.taskKind === "miniapp" ? "小程序任务" : draft.category,
      description: this.data.taskKind === "miniapp"
        ? String(draft.miniDescription || "").trim() || "打开页面，停留后提交体验反馈"
        : (firstTextBlock && firstTextBlock.text) || (this.data.taskKind === "wool" ? "查看福利说明并按步骤使用" : "按任务说明完成并提交材料"),
      contentBlocks,
      acceptanceCriteriaBlocks,
      taskLinks,
      rewardPointType: this.data.taskKind === "wool" ? shared.POINT_TYPE_BASE : (draft.rewardPointType === shared.POINT_TYPE_REWARD ? shared.POINT_TYPE_REWARD : shared.POINT_TYPE_BASE),
      shortLink: (taskLinks.find((link) => link.type === "miniapp") || {}).shortLink || "",
      woolPolicy: this.data.taskKind === "wool" ? {
        unlockFeePoints: Number(draft.woolUnlockFee || 0),
        allowTip: Boolean(draft.woolAllowTip)
      } : {},
      publisherPoints: shared.getPointsByType(shared.getUserId(user), this.data.taskKind === "wool" ? shared.POINT_TYPE_BASE : draft.rewardPointType),
      rewardPoints,
      executorReward: this.data.taskKind === "miniapp" ? 4 : (this.data.taskKind === "wool" ? 0 : Math.floor(rewardPoints * 0.8)),
      remaining: String(draft.quota || "").trim() ? Number(draft.quota) : null,
      deadlineText: "长期开放",
      ownerUserId: shared.getUserId(user),
      status: "published",
      createdAt: new Date().toISOString()
    };
    this.setData({ publishing: true });
    try {
      const response = await api.createMutualHelpTask(task);
      const serverTask = response && response.data && response.data.task ? response.data.task : task;
      const tasks = shared.getTasks().filter((item) => item.id !== serverTask.id);
      tasks.unshift(serverTask);
      shared.saveTasks(tasks);
      shared.recordActivity("published", serverTask, shared.getUserId(user)).catch(() => {});
      wx.showToast({ title: "任务已发布", icon: "success" });
      setTimeout(() => wx.redirectTo({
        url: `/subpackages/my-tools-mutual-help/task-manage/detail/index?id=${encodeURIComponent(serverTask.id)}`
      }), 500);
    } catch (error) {
      wx.showToast({ title: String((error && (error.detail || error.message)) || "发布失败，请稍后重试"), icon: "none" });
      this.setData({ publishing: false });
    }
  }
});
