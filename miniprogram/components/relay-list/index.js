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
    handleDelete(event) {
      this.triggerEvent("delete", { id: event.currentTarget.dataset.id });
    },
    handleFollow(event) {
      this.triggerEvent("follow", { id: event.currentTarget.dataset.id });
    }
  }
});

