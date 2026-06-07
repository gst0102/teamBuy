Component({
  properties: {
    card: {
      type: Object,
      value: {}
    }
  },
  methods: {
    handleOpen() {
      this.triggerEvent("open", { id: this.properties.card.id });
    },
    handleManage() {
      this.triggerEvent("manage", { id: this.properties.card.id });
    }
  }
});

