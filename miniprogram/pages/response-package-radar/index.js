const { fetchResponsePackageRadar } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildUniversalShareMessage, prepareUniversalShareImage } = require("../../utils/universal-share");

const demoRadar = {
  opened: true,
  lastOpenedAt: "刚刚",
  eventCounts: { view: 1, copy: 0, contact_click: 0 },
  nextSuggestion: "示例反馈：对方已打开资料，可以优先电话或微信跟进。",
  events: [{ eventType: "view", createdAt: "刚刚" }],
  package: { title: "示例回应包" }
};

Page({
  data: {
    packageId: "",
    radar: demoRadar,
    loading: false,
    universalShareImage: ""
  },
  onLoad(options = {}) {
    this.packageId = options.id || "";
    this.loadRadar();
  },
  async loadRadar() {
    if (!this.packageId || this.packageId === "demo" || /^demo_pkg_/.test(this.packageId)) {
      this.setData({ packageId: this.packageId, radar: demoRadar });
      this.prepareShareImage();
      return;
    }
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ loading: true, packageId: this.packageId });
    try {
      const res = await fetchResponsePackageRadar(this.packageId, user.id);
      this.setData({ radar: res.data || demoRadar });
      this.prepareShareImage();
    } catch (error) {
      wx.showToast({ title: "反馈读取失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  prepareShareImage() {
    const radar = this.data.radar || demoRadar;
    const pack = radar.package || {};
    return prepareUniversalShareImage(this, {
      title: pack.title || "回应包反馈",
      summary: radar.nextSuggestion || "打开查看回应包反馈和跟进建议。",
      badge: "反馈",
      path: `/pages/response-package-radar/index?id=${encodeURIComponent(this.packageId || this.data.packageId || "")}`,
      shareTargetLabel: "资料"
    });
  },
  onShareAppMessage() {
    const radar = this.data.radar || demoRadar;
    const pack = radar.package || {};
    return buildUniversalShareMessage(this, {
      title: pack.title || "回应包反馈",
      summary: radar.nextSuggestion || "打开查看回应包反馈和跟进建议。",
      badge: "反馈",
      path: `/pages/response-package-radar/index?id=${encodeURIComponent(this.packageId || this.data.packageId || "")}`,
      shareTargetLabel: "资料"
    });
  }
});
