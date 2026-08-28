const { getCurrentUser } = require("../../../utils/dashboard");
const { saveWorkspaceMode } = require("../../../utils/workspace-mode");
const api = require("../../../services/api");

const CONTACT_STORAGE_KEY = "teambuy:propertyAgentContact";

function contactStorageKey(userId) {
  const app = getApp();
  const globalData = (app && app.globalData) || {};
  const scope = [globalData.environmentName || "default", globalData.apiBaseUrl || ""].join("|")
    .replace(/[^a-zA-Z0-9_.:-]/g, "_");
  return `${CONTACT_STORAGE_KEY}:${scope}:${userId || "guest"}`;
}

function decodeValue(value) {
  try {
    return decodeURIComponent(value || "");
  } catch (error) {
    return value || "";
  }
}

function readContactDraft(userId) {
  try {
    // Remove the pre-scope key so an older account cannot repopulate this
    // form after an update.
    if (typeof wx.removeStorage === "function") wx.removeStorage({ key: CONTACT_STORAGE_KEY });
    else wx.removeStorageSync(CONTACT_STORAGE_KEY);
    return wx.getStorageSync(contactStorageKey(userId)) || {};
  } catch (error) {
    return {};
  }
}

function writeContactDraft(userId, payload) {
  try {
    if (typeof wx.setStorage === "function") wx.setStorage({ key: contactStorageKey(userId), data: payload });
    else wx.setStorageSync(contactStorageKey(userId), payload);
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
    autoGenerate: false,
    generationMode: "reuse_content",
    ownNotes: [],
    selectedNoteIds: []
  },
  onLoad(options = {}) {
    const user = getCurrentUser();
    if (!user) {
      const query = encodeQuery(options, { autoGenerate: "1" });
      const returnUrl = `/subpackages/workbench/property-same/index${query ? `?${query}` : ""}`;
      wx.reLaunch({ url: `/pages/login/index?returnUrl=${encodeURIComponent(returnUrl)}` });
      return;
    }
    saveWorkspaceMode("property", user.id);
    const stored = readContactDraft(user.id);
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
    this.loadOwnNotes();
    if (options.autoGenerate === "1") {
      setTimeout(() => this.handleGenerateSame(), 300);
    }
  },
  async loadOwnNotes() {
    try {
      const res = await api.fetchNotes({ ownerUserId: this.data.user.id }, { metadataOnly: true });
      this.setData({ ownNotes: (res.data || []).filter((item) => item.status !== "deleted").slice(0, 30).map((item) => ({ ...item, selected: false })) });
    } catch (error) {
      this.setData({ ownNotes: [] });
    }
  },
  handleModeChange(event) {
    this.setData({ generationMode: event.currentTarget.dataset.mode || "reuse_content", fallbackReason: "" });
  },
  handleToggleOwnNote(event) {
    const id = event.currentTarget.dataset.id;
    const selected = this.data.selectedNoteIds || [];
    const selectedNoteIds = selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id];
    this.setData({
      selectedNoteIds,
      ownNotes: (this.data.ownNotes || []).map((item) => ({ ...item, selected: selectedNoteIds.includes(item.id) }))
    });
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
    if (this.data.generationMode === "reuse_content" && !wechat && !phone) {
      wx.showToast({ title: "先填写微信或电话", icon: "none" });
      return;
    }
    if (wechat || phone) writeContactDraft(this.data.user.id, { wechat, phone });
    if (this.data.generationMode === "use_own_content") {
      if (!this.data.selectedNoteIds.length) {
        wx.showToast({ title: "至少选择一条自己的资料", icon: "none" });
        return;
      }
      if (this.data.generating) return;
      this.setData({ generating: true, fallbackReason: "" });
      wx.showLoading({ title: "正在生成" });
      try {
        const response = await api.generateSameStyle({
          ownerUserId: this.data.user.id,
          mode: "use_own_content",
          sourceShowcaseId: this.data.sourceType === "showcase" ? this.data.sourceId : null,
          ownNoteIds: this.data.selectedNoteIds,
          idempotencyKey: `own-${this.data.user.id}-${Date.now()}`
        });
        wx.hideLoading();
        const generation = response.data && response.data.generation || {};
        if (generation.generatedShowcaseId) {
          wx.redirectTo({ url: `/subpackages/workbench/showcase-edit/index?id=${encodeURIComponent(generation.generatedShowcaseId)}` });
        }
      } catch (error) {
        wx.hideLoading();
        wx.showToast({ title: (error && (error.detail || error.message)) || "生成失败", icon: "none" });
      } finally {
        this.setData({ generating: false });
      }
      return;
    }
    if (!this.canDirectClone()) {
      this.setData({ fallbackReason: "来源信息不完整，已转为助手整理" });
      await this.handleOpenAssistant();
      return;
    }
    if (this.data.generating) return;
    this.setData({ generating: true, fallbackReason: "" });
    wx.showLoading({ title: "正在生成" });
    try {
      const response = await api.generateSameStyle({
        ownerUserId: this.data.user.id,
        mode: "reuse_content",
        sourceNoteId: this.data.sourceType === "note" ? this.data.sourceId : null,
        sourceShowcaseId: this.data.sourceType === "showcase" ? this.data.sourceId : null,
        ownNoteIds: [],
        idempotencyKey: `reuse-${this.data.user.id}-${this.data.sourceType}-${this.data.sourceId}`
      });
      wx.hideLoading();
      const generation = response.data && response.data.generation || {};
      this.openClonedResult(generation.generatedShowcaseId
        ? { type: "showcase", showcase: { id: generation.generatedShowcaseId } }
        : { type: "note", note: { id: generation.generatedNoteId } });
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
    writeContactDraft(this.data.user.id, contact);
    try {
      await this.copyAssistantText();
      this.setData({ copied: true });
      wx.showToast({ title: "已复制，发给企业微信助手", icon: "none" });
    } catch (error) {
      wx.showToast({ title: "复制失败，请手动发送", icon: "none" });
    }
  },
  handleGoCreate() {
    wx.navigateTo({ url: "/subpackages/workbench/resource-create/index?workspaceMode=property&scene=property_listing" });
  }
});
