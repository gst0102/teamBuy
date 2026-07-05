Page({
  data: {
    src: ""
  },
  onLoad(options = {}) {
    const src = decodeURIComponent(options.src || "");
    if (!src || !/^https:\/\//i.test(src)) {
      wx.showToast({ title: "资源工具地址无效", icon: "none" });
      setTimeout(() => wx.navigateBack({ fail: () => wx.switchTab({ url: "/pages/profile/index" }) }), 800);
      return;
    }
    this.setData({ src });
  }
});
