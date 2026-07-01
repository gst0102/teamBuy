const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { buildDashboard, getCurrentUser } = require("../../utils/dashboard");
const { navigateToResourceView } = require("../../utils/resource-navigation");
const { buildModeOptions, getModeConfig, readWorkspaceMode, saveWorkspaceMode } = require("../../utils/workspace-mode");

const GROUP_POINTS_KEY = "teambuy:groupResourceLibrary:points";
const GROUPS_KEY = "teambuy:groupResourceLibrary:groups";
const DEFAULT_RESOURCE_POINTS = 100;

function scopedStorageKey(base, userId) {
  return `${base}:${userId || "guest"}`;
}

function readStorageNumber(key, fallback) {
  try {
    const value = wx.getStorageSync(key);
    if (value === "" || value === undefined || value === null) return fallback;
    return Number(value || 0);
  } catch (error) {
    return fallback;
  }
}

function readStorageList(key) {
  try {
    const value = wx.getStorageSync(key);
    return Array.isArray(value) ? value : [];
  } catch (error) {
    return [];
  }
}

function safeAvatarUrl(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (!/^https:\/\//i.test(text)) return "";
  if (/example\.com/i.test(text)) return "";
  if (/avatar-default/i.test(text)) return "";
  if (/^(wxfile|file|blob):/i.test(text)) return "";
  if (/^\/tmp\//i.test(text)) return "";
  return text;
}

function isRemoteAvatarUrl(value) {
  return /^https:\/\//i.test(String(value || "").trim());
}

function isLocalAvatarPath(value) {
  const text = String(value || "").trim();
  return /^(wxfile|file):/i.test(text) || /^\/tmp\//i.test(text) || /^http:\/\/tmp\//i.test(text);
}

function avatarText(name) {
  const text = String(name || "我").trim();
  return text.slice(0, 1);
}

function normalizeUser(user) {
  if (!user) return null;
  return {
    ...user,
    avatarUrl: safeAvatarUrl(user.avatarUrl),
    avatarText: avatarText(user.nickname),
    wechat: String(user.wechat || "").trim()
  };
}

function isBusinessCardResource(card = {}) {
  const config = card.visibilityConfig || {};
  const cardType = card.cardType || config.cardType || "";
  return cardType === "business_card" || card.categoryName === "名片";
}

Page({
  data: {
    user: null,
    showProfileEditor: false,
    profileDraft: {
      nickname: "",
      avatarUrl: "",
      wechat: "",
      phone: ""
    },
    totalResources: 0,
    totalPv: 0,
    totalRelay: 0,
    messageUnread: 0,
    resourcePoints: DEFAULT_RESOURCE_POINTS,
    frozenResourcePoints: 0,
    showResourceRules: false,
    workspaceMode: "notes",
    modeConfig: getModeConfig("notes"),
    modeOptions: buildModeOptions("notes")
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const workspaceMode = readWorkspaceMode(currentUser.id) || "notes";
    this.setData({
      user: normalizeUser(currentUser),
      workspaceMode,
      modeConfig: getModeConfig(workspaceMode),
      modeOptions: buildModeOptions(workspaceMode)
    });
    this.loadProfileStats();
    this.loadResourcePoints(currentUser.id);
  },
  loadResourcePoints(userId) {
    const points = readStorageNumber(scopedStorageKey(GROUP_POINTS_KEY, userId), DEFAULT_RESOURCE_POINTS);
    const groups = readStorageList(scopedStorageKey(GROUPS_KEY, userId));
    const frozen = groups.reduce((sum, item) => sum + Number(item.pendingReward || 0), 0);
    this.setData({
      resourcePoints: points,
      frozenResourcePoints: frozen
    });
  },
  async loadProfileStats() {
    const currentUser = getCurrentUser();
    try {
      const res = await api.fetchCards({ ownerUserId: currentUser.id });
      const dashboard = buildDashboard(res.data || []);
      this.setData({
        totalResources: dashboard.totalResources,
        totalPv: dashboard.totalPv,
        totalRelay: dashboard.totalRelay
      });
    } catch (error) {
      wx.showToast({ title: "我的数据加载失败", icon: "none" });
      return;
    }
    this.loadMessageUnread(currentUser.id);
  },
  async loadMessageUnread(ownerUserId) {
    try {
      const messageUnread = await messagePlugin.fetchUnreadTotal(ownerUserId);
      this.setData({ messageUnread });
    } catch (error) {
      this.setData({ messageUnread: 0 });
    }
  },
  handleGoLibrary() {
    wx.switchTab({ url: "/pages/library/index" });
  },
  async handleGoBusinessCards() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    try {
      wx.showLoading({ title: "打开名片" });
      const res = await api.fetchCards({ ownerUserId: currentUser.id });
      const businessCards = (res.data || []).filter(isBusinessCardResource);
      wx.hideLoading();
      if (businessCards.length) {
        const firstCard = businessCards
          .slice()
          .sort((a, b) => new Date(b.updatedAt || b.createdAt || 0) - new Date(a.updatedAt || a.createdAt || 0))[0];
        navigateToResourceView(firstCard);
        return;
      }
      wx.navigateTo({ url: "/pages/business-card-studio/index" });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: "名片读取失败，先进入编辑页", icon: "none" });
      wx.navigateTo({ url: "/pages/business-card-studio/index" });
    }
  },
  handleGoMessages() {
    messagePlugin.openMessageCenter();
  },
  handleGoShowcases() {
    wx.switchTab({ url: "/pages/showcases/index" });
  },
  handleModeTap(event) {
    const currentUser = getCurrentUser();
    const mode = event.currentTarget.dataset.mode || "notes";
    const modeConfig = saveWorkspaceMode(mode, currentUser && currentUser.id);
    this.setData({
      workspaceMode: modeConfig.key,
      modeConfig,
      modeOptions: buildModeOptions(modeConfig.key)
    });
    wx.showToast({ title: "已切换常用场景", icon: "success" });
  },
  handleOpenResourceHub() {
    wx.navigateTo({ url: "/pages/group-resource-library/index" });
  },
  handleOpenEnterpriseSearch() {
    wx.navigateTo({ url: "/pages/enterprise-resource-search/index" });
  },
  handleOpenResourceRules() {
    this.setData({ showResourceRules: true });
  },
  handleCloseResourceRules() {
    this.setData({ showResourceRules: false });
  },
  handleOpenHelp() {
    wx.navigateTo({ url: "/pages/help-feedback/index" });
  },
  handleOpenProfileEditor() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({
      showProfileEditor: true,
      profileDraft: {
        nickname: currentUser.nickname || "",
        avatarUrl: safeAvatarUrl(currentUser.avatarUrl),
        wechat: String(currentUser.wechat || "").trim(),
        phone: currentUser.phone || ""
      }
    });
  },
  handleCloseProfileEditor() {
    this.setData({ showProfileEditor: false });
  },
  noop() {},
  handleProfileNicknameInput(event) {
    this.setData({ "profileDraft.nickname": event.detail.value });
  },
  handleProfileWechatInput(event) {
    this.setData({ "profileDraft.wechat": event.detail.value });
  },
  handleProfilePhoneInput(event) {
    this.setData({ "profileDraft.phone": event.detail.value });
  },
  handleChooseAvatar(event) {
    const avatarUrl = event.detail && event.detail.avatarUrl;
    if (!avatarUrl) return;
    this.setData({ "profileDraft.avatarUrl": avatarUrl });
  },
  async handleSaveProfile() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const nickname = String(this.data.profileDraft.nickname || "").trim();
    if (!nickname) {
      wx.showToast({ title: "请填写昵称", icon: "none" });
      return;
    }
    try {
      wx.showLoading({ title: "保存中" });
      let avatarUrl = String(this.data.profileDraft.avatarUrl || "").trim();
      if (avatarUrl && isLocalAvatarPath(avatarUrl)) {
        const uploaded = await api.uploadAsset({
          filePath: avatarUrl,
          mediaType: "image",
          ownerUserId: currentUser.id
        });
        avatarUrl = uploaded.url || "";
      }
      if (avatarUrl && !isRemoteAvatarUrl(avatarUrl)) {
        wx.hideLoading();
        wx.showToast({ title: "请选择微信头像或留空", icon: "none" });
        return;
      }
      const res = await api.updateUserProfile(currentUser.id, {
        nickname,
        avatarUrl,
        wechat: String(this.data.profileDraft.wechat || "").trim(),
        phone: String(this.data.profileDraft.phone || "").trim()
      });
      const app = getApp();
      const userWithBase = {
        ...(res.data || {}),
        apiBaseUrl: app.globalData.apiBaseUrl,
        apiRoutePrefix: app.globalData.apiRoutePrefix || "",
        environmentName: app.globalData.environmentName || ""
      };
      app.globalData.currentUser = userWithBase;
      wx.setStorageSync("currentUser", userWithBase);
      wx.hideLoading();
      this.setData({
        user: normalizeUser(userWithBase),
        showProfileEditor: false
      });
      wx.showToast({ title: "已保存", icon: "success" });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
    }
  },
  handleLogout() {
    wx.removeStorageSync("currentUser");
    getApp().globalData.currentUser = null;
    wx.reLaunch({ url: "/pages/login/index" });
  }
});
