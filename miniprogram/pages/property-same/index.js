const { getCurrentUser } = require("../../utils/dashboard");
const { saveWorkspaceMode } = require("../../utils/workspace-mode");
const api = require("../../services/api");

const CONTACT_STORAGE_KEY = "teambuy:propertyAgentContact";

function decodeValue(value) {
  try {
    return decodeURIComponent(value || "");
  } catch (error) {
    return value || "";
  }
}

function readContactDraft() {
  try {
    return wx.getStorageSync(CONTACT_STORAGE_KEY) || {};
  } catch (error) {
    return {};
  }
}

function writeContactDraft(payload) {
  try {
    wx.setStorageSync(CONTACT_STORAGE_KEY, payload);
  } catch (error) {}
}

function sourceCopy(sourceType) {
  if (sourceType === "showcase") {
    return {
      badge: "房源合集",
      title: "生成同款房源合集",
      desc: "复制公开房源内容和图片，换成你的微信，再发给客户或对盘群。"
    };
  }
  if (sourceType === "note") {
    return {
      badge: "房源卡",
      title: "生成同款房源卡",
      desc: "把这套房源变成你的版本，客户看到你的微信，上游联系人你自己留着。"
    };
  }
  return {
    badge: "房源版",
    title: "生成你的房源卡",
    desc: "把群里的房源发给助手，整理成你的房源卡或房源合集。"
  };
}

function encodeQuery(options = {}, extra = {}) {
  return Object.keys({ ...options, ...extra })
    .map((key) => {
      const value = key in extra ? extra[key] : options[key];
      if (value === undefined || value === null || value === "") return "";
      return `${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
    })
    .filter(Boolean)
    .join("&");
}

Page({
  data: {
    user: null,
    sourceType: "guide",
    sourceId: "",
    sourceTitle: "",
    publisherName: "",
    upstreamContact: "",
    wechat: "",
    phone: "",
    copy: sourceCopy("guide"),
    copied: false,
    generating: false,
    fallbackReason: "",
    autoGenerate: false
  },
  onLoad(options = {}) {
    const user = getCurrentUser();
    if (!user) {
      const query = encodeQuery(options, { autoGenerate: "1" });
      const returnUrl = `/pages/property-same/index${query ? `?${query}` : ""}`;
      wx.reLaunch({ url: `/pages/login/index?returnUrl=${encodeURIComponent(returnUrl)}` });
      return;
    }
    saveWorkspaceMode("property", user.id);
    const stored = readContactDraft();
    const sourceType = options.sourceType || "guide";
    const publisherName = decodeValue(options.publisherName || "");
    const sourceTitle = decodeValue(options.sourceTitle || "");
    const upstreamContact = decodeValue(options.upstreamContact || "") || publisherName || "原发布中介";
    this.setData({
      user,
      sourceType,
      sourceId: options.sourceId || "",
      sourceTitle,
      publisherName,
      upstreamContact,
      wechat: stored.wechat || user.wechat || "",
      phone: stored.phone || user.phone || "",
      copy: sourceCopy(sourceType),
      autoGenerate: options.autoGenerate === "1"
    });
    if (options.autoGenerate === "1") {
      setTimeout(() => this.handleGenerateSame(), 300);
    }
  },
  handleWechatInput(event) {
    this.setData({ wechat: event.detail.value, copied: false });
  },
  handlePhoneInput(event) {
    this.setData({ phone: event.detail.value, copied: false });
  },
  handleUpstreamInput(event) {
    this.setData({ upstreamContact: event.detail.value, copied: false });
  },
  canDirectClone() {
    return Boolean(this.data.sourceId && (this.data.sourceType === "note" || this.data.sourceType === "showcase"));
  },
  buildAssistantText() {
    const { copy, sourceType, sourceId, sourceTitle, wechat, phone, upstreamContact, publisherName } = this.data;
    const sourceText = sourceType === "showcase"
      ? "房源合集"
      : sourceType === "note"
        ? "房源卡"
        : "房源资料";
    return [
      "请帮我生成同款租房资料。",
      `生成类型：${copy.badge || sourceText}`,
      sourceId ? `来源编号：${sourceId}` : "",
      sourceTitle ? `来源标题：${sourceTitle}` : "",
      publisherName ? `原发布者：${publisherName}` : "",
      `我的微信：${wechat}`,
      phone ? `我的电话：${phone}` : "",
      `我的上游联系人：${upstreamContact || "待补"}`,
      "规则：客户页展示我的微信；上游联系人只给我自己看；不要复制原发布者私密房东联系方式。"
    ].filter(Boolean).join("\n");
  },
  copyAssistantText() {
    return new Promise((resolve, reject) => {
      wx.setClipboardData({
        data: this.buildAssistantText(),
        success: resolve,
        fail: reject
      });
    });
  },
  async handleGenerateSame() {
    const wechat = String(this.data.wechat || "").trim();
    const phone = String(this.data.phone || "").trim();
    const upstreamContact = String(this.data.upstreamContact || "").trim();
    if (!wechat && !phone) {
      wx.showToast({ title: "先填写微信或电话", icon: "none" });
      return;
    }
    writeContactDraft({ wechat, phone });
    if (!this.canDirectClone()) {
      this.setData({ fallbackReason: "来源信息不完整，已转为助手整理" });
      await this.handleOpenAssistant();
      return;
    }
    if (this.data.generating) return;
    this.setData({ generating: true, fallbackReason: "" });
    wx.showLoading({ title: "正在生成" });
    try {
      const response = await api.clonePropertySame({
        ownerUserId: this.data.user.id,
        sourceType: this.data.sourceType,
        sourceId: this.data.sourceId,
        phone,
        wechat,
        upstreamContact,
        ownerName: this.data.user.nickname || "",
        avatarUrl: this.data.user.avatarUrl || "",
        publishShowcase: true
      });
      wx.hideLoading();
      this.openClonedResult(response && response.data);
    } catch (error) {
      wx.hideLoading();
      const reason = error && (error.detail || error.message || error.errMsg) || "生成失败";
      this.setData({ fallbackReason: `${reason}，已转为助手整理` });
      await this.handleOpenAssistant();
    } finally {
      this.setData({ generating: false });
    }
  },
  openClonedResult(data = {}) {
    if (data.type === "showcase" && data.showcase && data.showcase.id) {
      wx.showToast({ title: "已生成合集", icon: "success" });
      setTimeout(() => {
        wx.redirectTo({ url: `/pages/showcase-view/index?id=${encodeURIComponent(data.showcase.id)}` });
      }, 500);
      return;
    }
    if (data.type === "note" && data.note && data.note.id) {
      wx.showToast({ title: "已生成房源卡", icon: "success" });
      setTimeout(() => {
        wx.redirectTo({ url: `/pages/note-preview/index?id=${encodeURIComponent(data.note.id)}` });
      }, 500);
      return;
    }
    wx.showToast({ title: "已生成，请到资料库查看", icon: "success" });
    setTimeout(() => {
      wx.redirectTo({ url: "/pages/library/index?workspaceMode=property" });
    }, 500);
  },
  async handleOpenAssistant() {
    const wechat = String(this.data.wechat || "").trim();
    if (!wechat) {
      wx.showToast({ title: "先填写你的微信号", icon: "none" });
      return;
    }
    const contact = {
      wechat,
      phone: String(this.data.phone || "").trim()
    };
    writeContactDraft(contact);
    try {
      await this.copyAssistantText();
      this.setData({ copied: true });
      wx.showToast({ title: "已复制，发给企业微信助手", icon: "none" });
    } catch (error) {
      wx.showToast({ title: "复制失败，请手动发送", icon: "none" });
    }
  },
  handleGoCreate() {
    wx.navigateTo({ url: "/pages/resource-create/index?workspaceMode=property&scene=property_listing" });
  }
});
