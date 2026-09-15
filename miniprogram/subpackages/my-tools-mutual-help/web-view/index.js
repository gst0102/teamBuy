const { isWebViewBusinessDomain, getWebHost } = require("../task-links");

function decodeValue(value) {
  try {
    return decodeURIComponent(String(value || ""));
  } catch (error) {
    return String(value || "");
  }
}

Page({
  data: {
    src: "",
    title: "任务网页",
    loadError: false
  },

  onLoad(options = {}) {
    const src = decodeValue(options.src);
    const host = getWebHost(src);
    if (!/^https:\/\//i.test(src) || !host || !isWebViewBusinessDomain(host)) {
      wx.showModal({
        title: "网页暂不可打开",
        content: "当前网页暂不能在小程序内打开，请复制链接后用手机浏览器访问。",
        showCancel: false,
        confirmText: "知道了",
        success: () => wx.navigateBack({ fail: () => wx.redirectTo({ url: "/subpackages/my-tools-mutual-help/index/index" }) })
      });
      return;
    }
    const title = decodeValue(options.title) || "任务网页";
    if (options.title && typeof wx.setNavigationBarTitle === "function") {
      wx.setNavigationBarTitle({ title });
    }
    this.setData({ src, title });
  },

  handleWebViewError() {
    this.setData({ loadError: true });
    wx.showToast({ title: "网页加载失败，可复制后用浏览器访问", icon: "none" });
  },

  handleCopyLink() {
    if (!this.data.src || typeof wx.setClipboardData !== "function") {
      wx.showToast({ title: "链接暂不可用", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: this.data.src,
      success: () => wx.showModal({
        title: "链接已复制",
        content: "请打开手机浏览器，粘贴链接访问。",
        showCancel: false,
        confirmText: "知道了"
      }),
      fail: () => wx.showToast({ title: "复制失败，请长按链接重试", icon: "none" })
    });
  }
});
