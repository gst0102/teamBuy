function padTime(value) {
  return String(value).padStart(2, "0");
}

function formatRelayTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日 ${padTime(date.getHours())}:${padTime(date.getMinutes())}`;
}

function relayStatusText(value) {
  if (value === "followed") return "已跟进";
  if (value === "pending") return "待跟进";
  if (value === "deleted") return "已删除";
  return value || "待跟进";
}

function safeAvatarUrl(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (!/^https:\/\//i.test(text)) return "";
  if (/example\.com/i.test(text)) return "";
  if (/avatar-default/i.test(text)) return "";
  if (/^(wxfile|file|blob):/i.test(text)) return "";
  if (/^\/tmp\//i.test(text)) return "";
  return text;
}

function avatarText(value) {
  const text = String(value || "客").trim();
  return text.slice(0, 1);
}

function normalizeRelay(item = {}) {
  const followUpStatus = item.followUpStatus || "pending";
  return {
    ...item,
    avatarUrl: safeAvatarUrl(item.avatarUrl),
    avatarText: avatarText(item.nickname),
    followUpStatus,
    isPending: followUpStatus !== "followed",
    createdText: item.createdText || formatRelayTime(item.createdAt),
    followUpText: item.followUpText || relayStatusText(followUpStatus)
  };
}

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
  data: {
    displayRelays: []
  },
  observers: {
    relays(value) {
      this.setData({
        displayRelays: (value || []).map(normalizeRelay)
      });
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
