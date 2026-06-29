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

function avatarText(value, fallback = "客") {
  const text = String(value || fallback).trim();
  return text.slice(0, 1);
}

function normalizeDashboard(value = {}) {
  const recentVisitors = (value.recentVisitors || []).map((item) => ({
    ...item,
    avatarUrl: safeAvatarUrl(item.avatarUrl),
    avatarText: item.anonymous ? "匿" : avatarText(item.nickname)
  }));
  return {
    summary: {},
    entries: [],
    topShares: [],
    topNotes: [],
    latestActions: [],
    ...value,
    recentVisitors
  };
}

Component({
  properties: {
    dashboard: {
      type: Object,
      value: {}
    }
  },
  data: {
    displayDashboard: normalizeDashboard({})
  },
  observers: {
    dashboard(value) {
      this.setData({ displayDashboard: normalizeDashboard(value || {}) });
    }
  },
  methods: {
    handleOpen(event) {
      const target = event.currentTarget.dataset.target || "";
      this.triggerEvent("open", { target });
    }
  }
});
