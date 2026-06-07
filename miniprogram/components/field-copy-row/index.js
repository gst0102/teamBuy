Component({
  properties: {
    label: String,
    value: String
  },
  methods: {
    handleCopy() {
      if (!this.properties.value) {
        return;
      }
      wx.setClipboardData({
        data: this.properties.value
      });
    }
  }
});

