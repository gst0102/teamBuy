const { fetchOpportunitySubscriptions, saveOpportunitySubscription } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildUniversalShareMessage, prepareUniversalShareImage } = require("../../utils/universal-share");

const directionOptions = ["我在找机会", "我能提供资源", "两边都看"];
const contactOptions = ["有电话", "有微信", "可私信", "待核验也看"];

const tagGroups = [
  { key: "lookingFor", title: "我在找", placeholder: "例如：客户 / 合作方 / 渠道", options: ["客户", "合作方", "渠道", "供应商", "人才"] },
  { key: "providing", title: "我能提供", placeholder: "例如：本地服务 / 地推 / 房源", options: ["装修设计", "地推", "房源", "供应链", "本地服务"] },
  { key: "city", title: "城市", placeholder: "例如：长沙 / 岳麓 / 全国", options: ["长沙", "上海", "深圳", "杭州", "全国"] }
];

const initialSelected = {
  direction: "两边都看",
  lookingFor: "客户",
  providing: "本地服务",
  city: "长沙",
  contact: "有电话"
};

function getApiErrorTitle(error, fallback) {
  const message = String((error && (error.detail || error.message || error.errMsg)) || "");
  if (/not found|404/i.test(message)) {
    return "测试后端未同步接口";
  }
  return message || fallback;
}

function buildTagGroups(selected) {
  return tagGroups.map((group) => ({
    ...group,
    value: selected[group.key] || "",
    options: group.options.map((label) => ({
      label,
      selected: selected[group.key] === label
    }))
  }));
}

function buildOptions(options, selectedValue) {
  return options.map((label) => ({ label, selected: label === selectedValue }));
}

Page({
  data: {
    directionOptions: buildOptions(directionOptions, initialSelected.direction),
    contactOptions: buildOptions(contactOptions, initialSelected.contact),
    tagGroups: buildTagGroups(initialSelected),
    selected: initialSelected,
    keywords: "开业推广 / 商家合作",
    reminderCadence: "每天早上",
    universalShareImage: ""
  },
  onShow() {
    this.loadSubscription();
    this.prepareShareImage();
  },
  prepareShareImage() {
    const selected = this.data.selected || initialSelected;
    return prepareUniversalShareImage(this, {
      title: "订阅雷达",
      summary: `${selected.city || "全国"} · ${selected.providing || "资源"} · ${selected.lookingFor || "机会"}`,
      badge: "雷达",
      path: "/pages/opportunity-subscription/index",
      shareTargetLabel: "商机"
    });
  },
  async loadSubscription() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    try {
      const res = await fetchOpportunitySubscriptions(user.id);
      const item = Array.isArray(res.data) && res.data.length ? res.data[0] : null;
      if (!item) return;
      const selected = {
        direction: item.direction || initialSelected.direction,
        lookingFor: item.lookingFor || initialSelected.lookingFor,
        providing: item.providing || initialSelected.providing,
        city: item.city || initialSelected.city,
        contact: item.contactRequirement || initialSelected.contact
      };
      this.setData({
        selected,
        keywords: item.keywords || this.data.keywords,
        reminderCadence: item.reminderCadence || this.data.reminderCadence,
        directionOptions: buildOptions(directionOptions, selected.direction),
        contactOptions: buildOptions(contactOptions, selected.contact),
        tagGroups: buildTagGroups(selected)
      });
      this.prepareShareImage();
    } catch (error) {
      wx.showToast({ title: getApiErrorTitle(error, "订阅读取失败"), icon: "none" });
    }
  },
  handleSimpleOptionTap(event) {
    const { key, value } = event.currentTarget.dataset;
    const selected = { ...this.data.selected, [key]: value };
    this.setData({
      selected,
      directionOptions: buildOptions(directionOptions, selected.direction),
      contactOptions: buildOptions(contactOptions, selected.contact)
    });
  },
  handleTagInput(event) {
    const key = event.currentTarget.dataset.key;
    const selected = { ...this.data.selected, [key]: event.detail.value };
    this.setData({
      selected,
      tagGroups: buildTagGroups(selected)
    });
  },
  handleTagTap(event) {
    const { key, value } = event.currentTarget.dataset;
    const selected = { ...this.data.selected, [key]: value };
    this.setData({
      selected,
      tagGroups: buildTagGroups(selected)
    });
  },
  handleKeywordsInput(event) {
    this.setData({ keywords: event.detail.value });
  },
  handleReminderTap(event) {
    this.setData({ reminderCadence: event.currentTarget.dataset.value });
  },
  async handleSave() {
    const user = getCurrentUser();
    if (!user) return;
    try {
      await saveOpportunitySubscription({
        userId: user.id,
        direction: this.data.selected.direction,
        lookingFor: this.data.selected.lookingFor,
        providing: this.data.selected.providing,
        city: this.data.selected.city,
        contactRequirement: this.data.selected.contact,
        keywords: this.data.keywords,
        reminderCadence: this.data.reminderCadence,
        status: "active"
      });
      wx.showToast({ title: "雷达订阅已保存", icon: "success" });
    } catch (error) {
      wx.showToast({ title: getApiErrorTitle(error, "保存失败，稍后再试"), icon: "none" });
    }
  },
  onShareAppMessage() {
    const selected = this.data.selected || initialSelected;
    return buildUniversalShareMessage(this, {
      title: "订阅雷达",
      summary: `${selected.city || "全国"} · ${selected.providing || "资源"} · ${selected.lookingFor || "机会"}`,
      badge: "雷达",
      path: "/pages/opportunity-subscription/index",
      shareTargetLabel: "商机"
    });
  }
});
