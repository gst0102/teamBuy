const { buildPageShareMessage } = require("../../../utils/page-share");

Page({
  data: {
    tools: [
      {
        key: "mutual-help",
        icon: "互",
        title: "互帮互助",
        description: "用互助积分交换真实的帮助",
        available: true
      },
      {
        key: "wechat-groups",
        icon: "群",
        title: "微信群工具",
        description: "整理群资源、活码和群运营动作",
        status: "即将上线",
        available: false
      }
    ]
  },

  onShareAppMessage() {
    return buildPageShareMessage({
      title: "资料整理助手｜我的工具",
      path: "/subpackages/my-tools/index/index"
    });
  },

  handleOpenTool(event) {
    const tool = this.data.tools[Number(event.currentTarget.dataset.index)];
    if (!tool || !tool.available) {
      wx.showToast({ title: "这个工具还在准备中", icon: "none" });
      return;
    }
    if (tool.key === "mutual-help") {
      wx.navigateTo({ url: "/subpackages/my-tools-mutual-help/index/index" });
    }
  }
});
