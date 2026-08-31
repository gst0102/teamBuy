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
    src: ""
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
    if (options.title && typeof wx.setNavigationBarTitle === "function") {
      wx.setNavigationBarTitle({ title: decodeValue(options.title) || "任务网页" });
    }
    this.setData({ src });
  },

  handleWebViewError() {
    wx.showToast({ title: "网页加载失败，请复制后用浏览器访问", icon: "none" });
  }
});
