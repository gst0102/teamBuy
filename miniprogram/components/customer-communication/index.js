Component({
  properties: {
    actions: {
      type: Array,
      value: []
    },
    primaryAction: {
      type: Object,
      value: null
    },
    hint: {
      type: String,
      value: "电话、微信、留言都可以直接发起"
    },
    shareTitle: {
      type: String,
      value: "分享资料"
    },
    shareDesc: {
      type: String,
      value: "转给好友继续查看"
    },
    shareReady: {
      type: Boolean,
      value: false
    }
  },

  methods: {
    handleAction(event) {
      const key = event.currentTarget.dataset.key;
      if (key) this.triggerEvent("action", { key });
    },
    handleShare() {
      this.triggerEvent("share");
    }
  }
});
