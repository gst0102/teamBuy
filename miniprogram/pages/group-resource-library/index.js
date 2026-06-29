const { getCurrentUser } = require("../../utils/dashboard");

const GROUPS_KEY = "teambuy:groupResourceLibrary:groups";
const POINTS_KEY = "teambuy:groupResourceLibrary:points";
const VIEWED_KEY = "teambuy:groupResourceLibrary:viewed";
const NEW_USER_POINTS = 100;
const PUBLISH_REWARD = 20;
const VIEW_COST = 30;
const DEFAULT_REGION = ["湖南省", "长沙市", ""];

const hotKeywords = ["房源对盘", "团购宝妈", "老板资源", "本地商家", "供应链", "行业交流"];
const typeOptions = ["房源", "团购", "老板", "本地生活", "服务", "自定义"];
const purposeOptions = ["找客户", "找同行", "找供应链", "找合作", "自定义"];
const memberOptions = ["50以下", "50-100", "100-300", "300+"];
const activeOptions = ["高", "中", "低", "不确定"];
const expireOptions = [
  { label: "1天", days: 1 },
  { label: "3天", days: 3 },
  { label: "5天", days: 5, recommend: true },
  { label: "7天", days: 7 }
];
const pageTitles = ["群资源库", "发布群资源", "补充群信息", "确认有效期", "发布成功"];

function storageKey(base, userId) {
  return `${base}:${userId || "guest"}`;
}

function readList(key) {
  try {
    const value = wx.getStorageSync(key);
    return Array.isArray(value) ? value : [];
  } catch (error) {
    return [];
  }
}

function readPoints(key) {
  try {
    const value = wx.getStorageSync(key);
    if (value === "" || value === undefined || value === null) {
      wx.setStorageSync(key, NEW_USER_POINTS);
      return NEW_USER_POINTS;
    }
    return Number(value || 0);
  } catch (error) {
    return NEW_USER_POINTS;
  }
}

function defaultDraft() {
  return {
    qrImage: "",
    name: "",
    cityMode: "city",
    region: DEFAULT_REGION,
    cityLabel: "长沙市",
    typeIndex: 0,
    purposes: ["找同行"],
    memberIndex: 2,
    activeIndex: 0,
    expireIndex: 2,
    remark: "",
    customTags: ["金融", "爱好者"]
  };
}

function buildPurposeChoices(selected = []) {
  return purposeOptions.map((label) => ({
    label,
    selected: selected.includes(label)
  }));
}

function groupTitle(draft) {
  const city = draft.cityMode === "national" ? "全国" : (draft.cityLabel || "本地");
  const type = typeOptions[draft.typeIndex] || "微信群";
  const name = String(draft.name || "").trim();
  return name || `${city || "本地"}${type}`;
}

function expireText(days) {
  const date = new Date(Date.now() + Number(days || 5) * 24 * 60 * 60 * 1000);
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

function decorateGroup(group, viewedIds = [], userId = "") {
  const viewed = viewedIds.includes(group.id);
  const rewardState = group.rewardState || "pending";
  return {
    ...group,
    rewardState,
    pendingReward: Number(group.pendingReward || (rewardState === "pending" ? PUBLISH_REWARD : 0)),
    canDelete: !userId || group.ownerUserId === userId,
    viewed,
    statusText: rewardState === "paid" ? "可查看" : "待确认"
  };
}

Page({
  data: {
    keyword: "",
    points: NEW_USER_POINTS,
    groups: [],
    myGroups: [],
    displayGroups: [],
    confirmedTotal: 0,
    frozenPoints: 0,
    viewedCount: 0,
    viewedIds: [],
    publishStep: 0,
    pageTitle: pageTitles[0],
    draft: defaultDraft(),
    successGroup: null,
    qrViewer: null,
    rulesVisible: false,
    hotKeywords,
    typeOptions,
    purposeChoices: buildPurposeChoices(["找同行"]),
    memberOptions,
    activeOptions,
    expireOptions
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.userId = currentUser.id;
    this.groupsKey = storageKey(GROUPS_KEY, this.userId);
    this.pointsKey = storageKey(POINTS_KEY, this.userId);
    this.viewedKey = storageKey(VIEWED_KEY, this.userId);
    this.loadState();
  },
  loadState() {
    let points = readPoints(this.pointsKey);
    const groups = readList(this.groupsKey).map((group) => {
      if (group.rewardState) return group;
      const next = {
        ...group,
        rewardState: "pending",
        pendingReward: PUBLISH_REWARD
      };
      if (!group.rewardMigratedFromImmediate && points > NEW_USER_POINTS) {
        points = Math.max(NEW_USER_POINTS, points - PUBLISH_REWARD);
        next.rewardMigratedFromImmediate = true;
      }
      return next;
    });
    this.saveGroups(groups);
    this.savePoints(points);
    const viewedIds = readList(this.viewedKey);
    const decorated = groups.map((item) => decorateGroup(item, viewedIds, this.userId));
    this.setData({
      points,
      groups: decorated,
      myGroups: decorated,
      confirmedTotal: decorated.reduce((sum, item) => sum + Number(item.confirmCount || 0), 0),
      frozenPoints: decorated.reduce((sum, item) => sum + Number(item.pendingReward || 0), 0),
      viewedIds,
      viewedCount: viewedIds.length
    }, () => this.applySearch());
  },
  saveGroups(groups) {
    wx.setStorageSync(this.groupsKey, groups);
  },
  savePoints(points) {
    wx.setStorageSync(this.pointsKey, points);
  },
  saveViewed(viewedIds) {
    wx.setStorageSync(this.viewedKey, viewedIds);
  },
  applySearch() {
    const keyword = String(this.data.keyword || "").trim().toLowerCase();
    const groups = this.data.groups || [];
    const displayGroups = !keyword
      ? groups
      : groups.filter((group) => {
        const text = [
          group.name,
          group.city,
          group.type,
          group.members,
          group.activeLevel,
          group.remark,
          ...(group.purposes || [])
        ].join(" ").toLowerCase();
        return text.includes(keyword);
      });
    this.setData({ displayGroups });
  },
  handleKeywordInput(event) {
    this.setData({ keyword: event.detail.value });
  },
  handleSearch() {
    this.applySearch();
  },
  handleHotKeyword(event) {
    this.setData({ keyword: event.currentTarget.dataset.keyword || "" }, () => this.applySearch());
  },
  handleShowMine() {
    this.setData({ keyword: "" }, () => this.applySearch());
    wx.showToast({ title: `我发布 ${this.data.myGroups.length} 个群`, icon: "none" });
  },
  handleOpenPublisher() {
    this.setData({
      publishStep: 1,
      pageTitle: pageTitles[1],
      draft: defaultDraft(),
      purposeChoices: buildPurposeChoices(["找同行"])
    });
  },
  handleFlowBack() {
    const step = Number(this.data.publishStep || 0);
    if (step <= 1 || step === 4) {
      this.setData({ publishStep: 0, pageTitle: pageTitles[0] });
      return;
    }
    const nextStep = step - 1;
    this.setData({ publishStep: nextStep, pageTitle: pageTitles[nextStep] || pageTitles[0] });
  },
  handleOpenRules() {
    this.setData({ rulesVisible: true });
  },
  handleCloseRules() {
    this.setData({ rulesVisible: false });
  },
  handleChooseQr() {
    if (wx.chooseMedia) {
      wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sourceType: ["album", "camera"],
        success: (res) => {
          const file = (res.tempFiles && res.tempFiles[0]) || {};
          const path = file.tempFilePath || "";
          if (!path) return;
          this.setData({ "draft.qrImage": path });
        }
      });
      return;
    }
    wx.chooseImage({
      count: 1,
      sourceType: ["album", "camera"],
      success: (res) => {
        const path = (res.tempFilePaths && res.tempFilePaths[0]) || "";
        if (!path) return;
        this.setData({ "draft.qrImage": path });
      }
    });
  },
  handleDraftInput(event) {
    const key = event.currentTarget.dataset.key;
    if (!key) return;
    this.setData({ [`draft.${key}`]: event.detail.value });
  },
  handleTypeChange(event) {
    this.setData({ "draft.typeIndex": Number(event.detail.value || 0) });
  },
  handleUseNational() {
    this.setData({
      "draft.cityMode": "national",
      "draft.cityLabel": "全国"
    });
  },
  handleRegionChange(event) {
    const region = event.detail.value || DEFAULT_REGION;
    const province = region[0] || "";
    const city = region[1] || province || "长沙市";
    const cityLabel = province && city && province !== city ? `${province} ${city}` : city;
    this.setData({
      "draft.cityMode": "city",
      "draft.region": region,
      "draft.cityLabel": cityLabel
    });
  },
  handleTypeChoice(event) {
    this.setData({ "draft.typeIndex": Number(event.currentTarget.dataset.index || 0) });
  },
  handleMemberChange(event) {
    this.setData({ "draft.memberIndex": Number(event.detail.value || 0) });
  },
  handleMemberChoice(event) {
    this.setData({ "draft.memberIndex": Number(event.currentTarget.dataset.index || 0) });
  },
  handleActiveChange(event) {
    this.setData({ "draft.activeIndex": Number(event.detail.value || 0) });
  },
  handleActiveChoice(event) {
    this.setData({ "draft.activeIndex": Number(event.currentTarget.dataset.index || 0) });
  },
  handleExpireChoice(event) {
    this.setData({ "draft.expireIndex": Number(event.currentTarget.dataset.index || 0) });
  },
  handleTogglePurpose(event) {
    const value = event.currentTarget.dataset.value;
    const purposes = [...(this.data.draft.purposes || [])];
    const index = purposes.indexOf(value);
    if (index >= 0) purposes.splice(index, 1);
    else purposes.push(value);
    const nextPurposes = purposes.slice(0, 4);
    this.setData({
      "draft.purposes": nextPurposes,
      purposeChoices: buildPurposeChoices(nextPurposes)
    });
  },
  handleAddTag() {
    const tags = this.data.draft.customTags || [];
    if (tags.length >= 4) {
      wx.showToast({ title: "最多 4 个自定义标签", icon: "none" });
      return;
    }
    const next = tags.length === 0 ? "金融" : tags.length === 1 ? "爱好者" : tags.length === 2 ? "母婴" : "课程";
    this.setData({ "draft.customTags": [...tags, next] });
  },
  handleNextFromUpload() {
    if (!this.data.draft.qrImage) {
      wx.showToast({ title: "先上传群二维码", icon: "none" });
      return;
    }
    this.setData({ publishStep: 2, pageTitle: pageTitles[2] });
  },
  handleNextFromInfo() {
    if (!this.data.draft.purposes.length) {
      wx.showToast({ title: "至少选择一个用途", icon: "none" });
      return;
    }
    this.setData({ publishStep: 3, pageTitle: pageTitles[3] });
  },
  handleSubmitGroup() {
    const draft = this.data.draft;
    const city = draft.cityMode === "national"
      ? "全国"
      : (draft.cityLabel || (draft.region && draft.region[1]) || "长沙市");
    const expireConfig = expireOptions[draft.expireIndex] || expireOptions[2];
    if (!draft.qrImage) {
      wx.showToast({ title: "先上传群二维码", icon: "none" });
      return;
    }
    if (!draft.purposes.length) {
      wx.showToast({ title: "至少选择一个用途", icon: "none" });
      return;
    }
    const now = Date.now();
    const group = {
      id: `group_${now}_${Math.floor(Math.random() * 100000)}`,
      ownerUserId: this.userId,
      name: groupTitle(draft),
      city,
      type: `${typeOptions[draft.typeIndex] || typeOptions[0]}群`,
      purposes: [...draft.purposes, ...(draft.customTags || [])].slice(0, 5),
      members: memberOptions[draft.memberIndex] || memberOptions[0],
      activeLevel: activeOptions[draft.activeIndex] || activeOptions[0],
      remark: String(draft.remark || "").trim(),
      qrImage: draft.qrImage,
      views: 0,
      confirmCount: 0,
      rewardState: "pending",
      pendingReward: PUBLISH_REWARD,
      createdAt: new Date(now).toISOString(),
      expireDays: expireConfig.days,
      expireText: expireText(expireConfig.days)
    };
    const groups = [group, ...readList(this.groupsKey)];
    this.saveGroups(groups);
    this.setData({
      publishStep: 4,
      pageTitle: pageTitles[4],
      successGroup: group,
      draft: defaultDraft(),
      purposeChoices: buildPurposeChoices(["找同行"])
    }, () => this.loadState());
  },
  handleDeleteGroup(event) {
    const id = event.currentTarget.dataset.id;
    const group = (this.data.groups || []).find((item) => item.id === id);
    if (!group || !group.canDelete) return;
    wx.showModal({
      title: "删除群资源",
      content: "删除后不会继续展示，也不会获得这条群的确认积分。",
      confirmText: "删除",
      confirmColor: "#e5484d",
      success: (res) => {
        if (!res.confirm) return;
        const groups = readList(this.groupsKey).filter((item) => item.id !== id);
        const viewedIds = readList(this.viewedKey).filter((item) => item !== id);
        this.saveGroups(groups);
        this.saveViewed(viewedIds);
        this.loadState();
        wx.showToast({ title: "已删除", icon: "success" });
      }
    });
  },
  handleContinuePublish() {
    this.setData({
      publishStep: 1,
      pageTitle: pageTitles[1],
      draft: defaultDraft(),
      successGroup: null,
      purposeChoices: buildPurposeChoices(["找同行"])
    });
  },
  handleViewResources() {
    this.setData({
      publishStep: 0,
      pageTitle: pageTitles[0],
      successGroup: null
    }, () => this.loadState());
  },
  handleViewQr(event) {
    const id = event.currentTarget.dataset.id;
    const groups = readList(this.groupsKey);
    const group = groups.find((item) => item.id === id);
    if (!group) return;
    const viewedIds = [...this.data.viewedIds];
    const viewed = viewedIds.includes(id);
    let points = Number(this.data.points || 0);
    if (!viewed) {
      if (points < VIEW_COST) {
        wx.showToast({ title: "积分不足，先发布群赚积分", icon: "none" });
        return;
      }
      points -= VIEW_COST;
      viewedIds.push(id);
      group.views = Number(group.views || 0) + 1;
      this.saveGroups(groups);
      this.savePoints(points);
      this.saveViewed(viewedIds);
    }
    this.setData({
      points,
      viewedIds,
      viewedCount: viewedIds.length,
      qrViewer: group
    }, () => this.loadState());
  },
  handleCloseQr() {
    this.setData({ qrViewer: null });
  },
  noop() {}
});
