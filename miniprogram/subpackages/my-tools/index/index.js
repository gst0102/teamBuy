const { buildPageShareMessage } = require("../../../utils/page-share");

Page({
  data: {
    tools: [
      {
        key: "group-resource-library",
        icon: "群",
        title: "群资源库",
        description: "发布群资源，找群并赚取积分",
        tag: "积分",
        available: true
      },
      {
        key: "live-qr",
        icon: "码",
        title: "我的活码",
        description: "免费管理微信群二维码，定期更新",
        tag: "免费",
        available: true
      }
    ]
  },

  onLoad() {
    wx.redirectTo({ url: "/pages/group-resource-library/index" });
  },

  onShareAppMessage() {
    return buildPageShareMessage({
      title: "资料整理助手｜群资源库",
      path: "/pages/group-resource-library/index"
    });
  },

  handleOpenTool(event) {
    const tool = this.data.tools[Number(event.currentTarget.dataset.index)];
    if (!tool || !tool.available) {
      wx.showToast({ title: "活码功能正在准备中", icon: "none" });
      return;
    }
    if (tool.key === "group-resource-library") {
      wx.navigateTo({ url: "/pages/group-resource-library/index" });
    }
  }
});
