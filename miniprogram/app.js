const { cacheButtonPosition } = require("./utils/nav");
const customerIntelligenceStore = require("./stores/customer-intelligence-store");
const customerDetailStore = require("./stores/customer-detail-store");
const resourceStore = require("./stores/resource-store");
const { clearAllCachedMedia } = require("./utils/media-cache");

const CLIENT_BUILD_VERSION = "20260907-server-share-card-v1";

App({
  globalData: {
    apiBaseUrl: "https://teambuy.lifelove.top",
    apiRoutePrefix: "",
    mediaRoutePrefix: "",
    environmentName: "production",
    clientBuildVersion: CLIENT_BUILD_VERSION,
    currentUser: null,
    buttonPosition: null,
    authRecoveryInFlight: false
  },
  onLaunch() {
    this.globalData.buttonPosition = cacheButtonPosition();
    const user = wx.getStorageSync("currentUser");
    const isProductionApi = /^https:\/\//i.test(this.globalData.apiBaseUrl || "");
    const isMockUser = user && (user.openid === "openid_本地测试用户" || /^mock_/.test(user.openid || ""));
    const authToken = String((user && user.authToken) || "").trim();
    const authTokenExpiresAt = Date.parse((user && user.authTokenExpiresAt) || "");
    const tokenExpired = Number.isFinite(authTokenExpiresAt) && authTokenExpiresAt <= Date.now();
    if (user && (
      (isProductionApi && (isMockUser || !authToken || tokenExpired))
      || user.apiBaseUrl !== this.globalData.apiBaseUrl
      || user.apiRoutePrefix !== this.globalData.apiRoutePrefix
    )) {
      this.clearExpiredSession();
      return;
    }
    if (user) {
      this.globalData.currentUser = user;
      require("./services/subscription").preloadViewNotificationSubscriptionConfig(user.id);
    }
  },
  clearExpiredSession(options = {}) {
    const storedUser = wx.getStorageSync("currentUser") || {};
    const activeUser = this.globalData.currentUser || storedUser || {};
    const hadAuthSession = Boolean(String(activeUser.authToken || "").trim());
    this.globalData.currentUser = null;
    wx.removeStorageSync("currentUser");
    customerIntelligenceStore.clearAll();
    customerDetailStore.clearAll();
    resourceStore.clearAll();
    clearAllCachedMedia();
    try {
      const api = require("./services/api");
      if (typeof api.clearUserScopedCaches === "function") api.clearUserScopedCaches();
    } catch (error) {}
    if (options.redirect && hadAuthSession) this.redirectToLoginAfterAuthExpiry();
  },
  redirectToLoginAfterAuthExpiry() {
    if (this.globalData.authRecoveryInFlight) return;
    const pages = typeof getCurrentPages === "function" ? getCurrentPages() : [];
    const currentPage = pages && pages.length ? pages[pages.length - 1] : null;
    const route = currentPage && currentPage.route ? `/${currentPage.route}` : "/pages/home/index";
    if (route === "/pages/login/index") return;
    const options = currentPage && currentPage.options && typeof currentPage.options === "object"
      ? currentPage.options
      : {};
    const query = Object.keys(options)
      .filter((key) => options[key] !== undefined && options[key] !== null && options[key] !== "")
      .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(options[key])}`)
      .join("&");
    const returnUrl = `${route}${query ? `?${query}` : ""}`;
    this.globalData.authRecoveryInFlight = true;
    wx.reLaunch({
      url: `/pages/login/index?returnUrl=${encodeURIComponent(returnUrl)}`,
      fail: () => {
        this.globalData.authRecoveryInFlight = false;
      }
    });
  }
});
