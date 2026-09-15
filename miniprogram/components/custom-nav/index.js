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
    fallbackUrl: {
      type: String,
      value: ""
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
      if (!this.data.showBack) return;
      if (this.data.canGoBack) {
        wx.navigateBack();
        return;
      }

      if (!this.data.fallbackUrl) return;
      const tabPages = [
        "/pages/home/index",
        "/pages/library/index",
        "/pages/profile/index",
        "/pages/visits/index"
      ];
      const target = this.data.fallbackUrl.split("?")[0];
      if (tabPages.includes(target)) {
        wx.switchTab({ url: this.data.fallbackUrl });
        return;
      }
      wx.redirectTo({ url: this.data.fallbackUrl });
    }
  }
});
