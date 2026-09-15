const shared = require("../shared");
const api = require("../../../services/api");

function formatDate(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) return "进行中";
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

Page({
  data: {
    theme: shared.getTheme(),
    loading: true,
    summary: {},
    items: [],
    errorText: ""
  },

  onShow() {
    this.setData({ theme: shared.getTheme() });
    this.loadReport();
  },

  async loadReport() {
    const user = shared.requireLogin("/subpackages/my-tools-mutual-help/report/index");
    if (!user) return;
    this.setData({ loading: true, errorText: "" });
    try {
      const response = await api.fetchMutualHelpExecutorReport(shared.getUserId(user));
      const data = response.data || {};
      const items = (Array.isArray(data.items) ? data.items : []).map((item) => ({
        ...item,
        dateText: formatDate(item.updatedAt || item.submittedAt),
        rewardText: item.rewardSettled ? `+${item.executorReward} 分已到账` : (item.status === "submitted" || item.status === "reviewing" ? `待验收 · ${item.executorReward} 分` : "")
      }));
      this.setData({ summary: data.summary || {}, items, loading: false });
    } catch (error) {
      this.setData({ loading: false, errorText: String((error && (error.detail || error.message)) || "报表暂时无法加载") });
    }
  },

  handleRetry() {
    this.loadReport();
  },

  handleOpenTask(event) {
    const taskId = String(event.currentTarget.dataset.taskId || "");
    if (!taskId) return;
    wx.navigateTo({ url: `/subpackages/my-tools-mutual-help/task-detail/index?id=${encodeURIComponent(taskId)}` });
  }
});
