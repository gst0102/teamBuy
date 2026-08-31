const { getButtonPositionData } = require("../../utils/nav");

const ROUTE_TITLES = {
  "pages/home/index": "首页",
  "pages/library/index": "资料",
  "pages/imports/index": "待认领导入",
  "pages/visits/index": "客户雷达",
  "pages/profile/index": "我的",
  "pages/group-resource-library/index": "群资源库",
  "pages/enterprise-resource-search/index": "企业资源搜索",
  "pages/help-feedback/index": "帮助与反馈",
  "pages/login/index": "登录",
  "subpackages/workbench/resource-create/index": "添加资源",
  "pages/tag-manage/index": "标签管理",
  "subpackages/workbench/card-edit/index": "资源编辑",
  "pages/leads/index": "待联系",
  "pages/customers/index": "客户资料库",
  "pages/topics/index": "专题"
};

Component({
  properties: {
    title: {
      type: String,
      value: ""
    },
    showBack: {
      type: Boolean,
      value: false
    },
    rightText: {
      type: String,
      value: ""
    },
    theme: {
      type: String,
      value: "light"
    }
  },
  data: {
    nav: getButtonPositionData(),
    canGoBack: false,
    resolvedTitle: ""
  },
  lifetimes: {
    attached() {
      const pages = getCurrentPages();
      const currentPage = pages[pages.length - 1];
      this.setData({
        nav: getButtonPositionData(),
        canGoBack: pages.length > 1,
        resolvedTitle: this.data.title || ROUTE_TITLES[currentPage && currentPage.route] || ""
      });
    }
  },
  methods: {
    handleBack() {
      if (!this.data.showBack || !this.data.canGoBack) return;
      wx.navigateBack();
    }
  }
});
