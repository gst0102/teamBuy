const { getCurrentUser, formatTime } = require("../../utils/dashboard");

const FEEDBACK_KEY = "teambuy:helpFeedback:list";

const feedbackTypes = [
  { key: "bug", label: "问题反馈", icon: "虫", reward: "100-1000", hint: "页面异常、数据错误、功能不可用" },
  { key: "idea", label: "功能建议", icon: "光", reward: "100-1000", hint: "帮我们把产品做得更好" },
  { key: "consult", label: "使用咨询", icon: "问", reward: "0-100", hint: "不会用、想了解某个功能" },
  { key: "points", label: "积分申诉", icon: "分", reward: "按核实", hint: "扣分、冻结、奖励相关问题" }
];

const rewardRules = [
  { label: "有效 Bug", value: "100-300" },
  { label: "严重 Bug", value: "300-1000" },
  { label: "采纳建议", value: "100-500" },
  { label: "上线建议", value: "500-1000" }
];

function storageKey(userId) {
  return `${FEEDBACK_KEY}:${userId || "guest"}`;
}

function readList(key) {
  try {
    const value = wx.getStorageSync(key);
    return Array.isArray(value) ? value : [];
  } catch (error) {
    return [];
  }
}

function defaultForm(user = {}) {
  return {
    type: "bug",
    title: "",
    content: "",
    contact: user.wechat || user.phone || "",
    page: "",
    images: []
  };
}

function decorateFeedback(item) {
  const type = feedbackTypes.find((option) => option.key === item.type) || feedbackTypes[0];
  return {
    ...item,
    typeLabel: type.label,
    timeText: formatTime(item.createdAt),
    statusText: item.statusText || "已提交",
    rewardText: item.rewardText || `预计 ${type.reward} 积分`
  };
}

Page({
  data: {
    user: null,
    form: defaultForm(),
    feedbackTypes,
    rewardRules,
    records: [],
    activePanel: "submit",
    submitting: false
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.userId = user.id;
    this.feedbackKey = storageKey(user.id);
    this.setData({
      user,
      form: defaultForm(user),
      records: readList(this.feedbackKey).map(decorateFeedback)
    });
  },
  handlePanelTap(event) {
    this.setData({ activePanel: event.currentTarget.dataset.panel || "submit" });
  },
  handleTypeTap(event) {
    this.setData({ "form.type": event.currentTarget.dataset.key || "bug" });
  },
  handleInput(event) {
    const key = event.currentTarget.dataset.key;
    if (!key) return;
    this.setData({ [`form.${key}`]: event.detail.value });
  },
  handleChooseImage() {
    const remain = 3 - (this.data.form.images || []).length;
    if (remain <= 0) {
      wx.showToast({ title: "最多上传 3 张截图", icon: "none" });
      return;
    }
    wx.chooseImage({
      count: remain,
      sourceType: ["album", "camera"],
      success: (res) => {
        const images = [...(this.data.form.images || []), ...(res.tempFilePaths || [])].slice(0, 3);
        this.setData({ "form.images": images });
      }
    });
  },
  handleRemoveImage(event) {
    const index = Number(event.currentTarget.dataset.index || 0);
    const images = [...(this.data.form.images || [])];
    images.splice(index, 1);
    this.setData({ "form.images": images });
  },
  handleSubmit() {
    const form = this.data.form || {};
    const title = String(form.title || "").trim();
    const content = String(form.content || "").trim();
    if (!title) {
      wx.showToast({ title: "先写一个标题", icon: "none" });
      return;
    }
    if (content.length < 8) {
      wx.showToast({ title: "描述再具体一点", icon: "none" });
      return;
    }
    const type = feedbackTypes.find((item) => item.key === form.type) || feedbackTypes[0];
    const record = decorateFeedback({
      id: `fb_${Date.now()}_${Math.floor(Math.random() * 100000)}`,
      type: form.type,
      title,
      content,
      contact: String(form.contact || "").trim(),
      page: String(form.page || "").trim(),
      images: form.images || [],
      createdAt: new Date().toISOString(),
      statusText: "已提交",
      rewardText: `预计 ${type.reward} 积分`
    });
    const records = [record, ...readList(this.feedbackKey)];
    wx.setStorageSync(this.feedbackKey, records);
    this.setData({
      form: defaultForm(this.data.user || {}),
      records: records.map(decorateFeedback),
      activePanel: "records"
    });
    wx.showToast({ title: "已收到反馈", icon: "success" });
  },
  handleOpenContact() {
    wx.showToast({ title: "急事可先在首页添加企业微信助手", icon: "none" });
  },
  noop() {}
});
