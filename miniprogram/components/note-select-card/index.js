Component({
  properties: {
    note: {
      type: Object,
      value: {}
    },
    mode: {
      type: String,
      value: "list"
    }
  },
  methods: {
    handleToggle() {
      const note = this.properties.note || {};
      this.triggerEvent("toggle", { id: note.id });
    }
  }
});
