const messagePlugin = require("../../plugins/message-plugin/index");

Component({
  properties: {
    mode: {
      type: String,
      value: "thread"
    },
    noteId: {
      type: String,
      value: ""
    },
    orderActionId: {
      type: String,
      value: ""
    },
    buyerUserId: {
      type: String,
      value: ""
    },
    title: {
      type: String,
      value: "发消息"
    },
    desc: {
      type: String,
      value: "站内留言"
    },
    unreadCount: {
      type: Number,
      value: 0
    },
    variant: {
      type: String,
      value: "card"
    },
    disabled: {
      type: Boolean,
      value: false
    }
  },
  methods: {
    async handleTap() {
      if (this.properties.disabled) return;
      if (this.properties.mode === "center") {
        messagePlugin.openMessageCenter();
        this.triggerEvent("opened", { mode: "center" });
        return;
      }
      const thread = await messagePlugin.openMessageThread({
        noteId: this.properties.noteId,
        orderActionId: this.properties.orderActionId,
        buyerUserId: this.properties.buyerUserId
      });
      if (thread) {
        this.triggerEvent("opened", { mode: "thread", thread });
      }
    }
  }
});
