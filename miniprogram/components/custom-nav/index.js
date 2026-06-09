const { getButtonPositionData } = require("../../utils/nav");

Component({
  properties: {
    title: {
      type: String,
      value: ""
    },
    showBack: {
      type: Boolean,
      value: false
    }
  },
  data: {
    nav: getButtonPositionData(),
    canGoBack: false
  },
  lifetimes: {
    attached() {
      this.setData({
        nav: getButtonPositionData(),
        canGoBack: getCurrentPages().length > 1
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
