Component({
  properties: {
    relays: {
      type: Array,
      value: []
    },
    isOwner: {
      type: Boolean,
      value: false
    }
  },
  methods: {
    handleCall(event) {
      const phone = event.currentTarget.dataset.phone;
      if (!phone) {
        wx.showToast({ title: "暂无电话", icon: "none" });
        return;
      }
      wx.makePhoneCall({ phoneNumber: phone });
    },
    handleCopyPhone(event) {
      const phone = event.currentTarget.dataset.phone;
      if (!phone) {
        wx.showToast({ title: "暂无电话", icon: "none" });
        return;
      }
      wx.setClipboardData({ data: phone });
    },
    handleCopyAddress(event) {
      const address = event.currentTarget.dataset.address;
      if (!address) {
        wx.showToast({ title: "暂无地址", icon: "none" });
        return;
      }
      wx.setClipboardData({ data: address });
    },
    handleDelete(event) {
      this.triggerEvent("delete", { id: event.currentTarget.dataset.id });
    },
    handleFollow(event) {
      this.triggerEvent("follow", { id: event.currentTarget.dataset.id });
    }
  }
});
