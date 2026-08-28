Page({
  onLoad(options = {}) {
    const showcaseId = options.showcaseId || options.id || "";
    if (!showcaseId) return;
    wx.redirectTo({
      url: `/subpackages/workbench/resource-analytics/index?entityType=showcase&showcaseId=${encodeURIComponent(showcaseId)}`
    });
  }
});
