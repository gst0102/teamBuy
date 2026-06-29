function buildShowcaseUrl(options = {}) {
  const showcaseId = options.showcaseId || options.id || "";
  if (!showcaseId) return "";
  const query = [
    `id=${encodeURIComponent(showcaseId)}`,
    `showcaseId=${encodeURIComponent(showcaseId)}`,
    options.sid ? `sid=${encodeURIComponent(options.sid)}` : "",
    options.from ? `from=${encodeURIComponent(options.from)}` : "",
    options.src ? `src=${encodeURIComponent(options.src)}` : "",
    options.scene ? `scene=${encodeURIComponent(options.scene)}` : "",
    options.ref ? `ref=${encodeURIComponent(options.ref)}` : ""
  ].filter(Boolean).join("&");
  return `/pages/showcase-view/index?${query}`;
}

Page({
  data: {
    errorText: ""
  },
  onLoad(options) {
    this.openShowcase(options || {});
  },
  openShowcase(options) {
    const url = buildShowcaseUrl(options);
    if (!url) {
      this.setData({ errorText: "展示页链接缺少页面编号，请让发布者重新发送。" });
      return;
    }
    wx.redirectTo({
      url,
      fail: () => {
        wx.navigateTo({
          url,
          fail: () => {
            this.setData({ errorText: "展示页打开失败，请让发布者重新发送。" });
          }
        });
      }
    });
  }
});
