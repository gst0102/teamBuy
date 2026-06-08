const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    submitting: false,
    type: "资料",
    typeOptions: ["房源", "团购", "视频", "文档", "资料"],
    form: {
      title: "",
      projectName: "",
      detailText: "",
      coverUrl: "",
      locationText: "",
      phone: "",
      sourceUrl: "",
      relayNotice: "",
      requirePhone: false,
      requireAddress: false
    }
  },
  onShow() {
    if (!getCurrentUser()) {
      wx.reLaunch({ url: "/pages/login/index" });
    }
  },
  handleTypeChange(event) {
    this.setData({ type: event.currentTarget.dataset.type });
  },
  handleFieldChange(event) {
    const field = event.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: event.detail.value });
  },
  handleSwitchChange(event) {
    const field = event.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: event.detail.value });
  },
  buildDetailText() {
    const form = this.data.form;
    const parts = [
      form.detailText,
      form.locationText ? `位置：${form.locationText}` : "",
      form.phone ? `电话：${form.phone}` : "",
      form.sourceUrl ? `链接：${form.sourceUrl}` : ""
    ].filter(Boolean);
    return parts.join("\n");
  },
  async handleSubmit() {
    const currentUser = getCurrentUser();
    const form = this.data.form;
    if (!form.title.trim()) {
      wx.showToast({ title: "请填写资源标题", icon: "none" });
      return;
    }
    this.setData({ submitting: true });
    try {
      const res = await api.createCard({
        ownerUserId: currentUser.id,
        title: form.title.trim(),
        projectName: form.projectName.trim() || this.data.type,
        detailText: this.buildDetailText(),
        coverUrl: form.coverUrl.trim() || null,
        locationText: form.locationText.trim() || null,
        phone: form.phone.trim() || null,
        sourceUrl: form.sourceUrl.trim() || null,
        relayNotice: form.relayNotice.trim() || "请留下你的称呼和联系方式，方便后续跟进。",
        relayConfig: {
          enabled: true,
          requirePhone: form.requirePhone,
          requireAddress: form.requireAddress
        }
      });
      wx.showToast({ title: "已生成草稿", icon: "success" });
      wx.navigateTo({ url: `/pages/card-edit/index?id=${res.data.id}` });
    } catch (error) {
      wx.showToast({ title: error.detail || "创建失败", icon: "none" });
    } finally {
      this.setData({ submitting: false });
    }
  }
});
