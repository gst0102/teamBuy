const shared = require("../shared");
const api = require("../../../services/api");

function messageTime(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) return "刚刚";
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function previewMessage(message, currentUserId) {
  return {
    ...message,
    isMine: String(message.senderUserId || "") === String(currentUserId || ""),
    timeText: messageTime(message.createdAt),
    renderId: `message-${message.id}`
  };
}

Page({
  data: {
    taskId: "",
    conversationId: "",
    taskTitle: "任务沟通",
    taskLinks: [],
    miniProgramLinks: [],
    currentUserId: "",
    currentUser: null,
    peer: null,
    messages: [],
    inputText: "",
    attachmentOpen: false,
    loading: true,
    sending: false,
    scrollIntoView: ""
  },

  onLoad(options = {}) {
    this.taskId = String(options.taskId || "");
    this.executorUserId = String(options.executorUserId || "");
    this.pollTimer = null;
    this.isFetching = false;
    this.initialize();
  },

  onShow() {
    this.startPolling();
  },

  onHide() {
    this.stopPolling();
  },

  onUnload() {
    this.stopPolling();
  },

  async initialize() {
    const user = shared.requireLogin(`/subpackages/my-tools-mutual-help/chat/index?taskId=${encodeURIComponent(this.taskId)}${this.executorUserId ? `&executorUserId=${encodeURIComponent(this.executorUserId)}` : ""}`);
    if (!user) return;
    const currentUserId = shared.getUserId(user);
    this.setData({ currentUserId, currentUser: user });
    try {
      const response = await api.openMutualHelpConversation(this.taskId, currentUserId, this.executorUserId);
      const data = response.data || {};
      const links = shared.normalizeTaskLinks((data.task || {}).taskLinks || []);
      this.setData({
        conversationId: data.conversation && data.conversation.id || "",
        taskTitle: (data.task && data.task.title) || "任务沟通",
        taskLinks: links,
        miniProgramLinks: links.filter((item) => item.type === "miniapp"),
        peer: data.peer || null,
        loading: false
      });
      await this.loadMessages();
      this.startPolling();
    } catch (error) {
      this.setData({ loading: false });
      wx.showModal({
        title: "暂时无法进入沟通",
        content: String((error && (error.detail || error.message)) || "开始参与任务后即可联系发布者。"),
        showCancel: false,
        confirmText: "知道了",
        success: () => wx.navigateBack()
      });
    }
  },

  startPolling() {
    this.stopPolling();
    if (!this.data.conversationId) return;
    this.pollTimer = setInterval(() => this.loadMessages({ silent: true }), 4500);
  },

  stopPolling() {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = null;
  },

  async loadMessages(options = {}) {
    if (!this.data.conversationId || this.isFetching) return;
    this.isFetching = true;
    try {
      const response = await api.fetchMutualHelpChatMessages(this.data.conversationId, this.data.currentUserId, { limit: 80 });
      const data = response.data || {};
      const messages = (Array.isArray(data.items) ? data.items : []).map((item) => previewMessage(item, this.data.currentUserId));
      const previousIds = this.data.messages.map((item) => item.id).join(",");
      const nextIds = messages.map((item) => item.id).join(",");
      const changed = previousIds !== nextIds;
      this.setData({
        messages,
        peer: data.peer || this.data.peer,
        taskTitle: data.task && data.task.title || this.data.taskTitle,
        loading: false,
        scrollIntoView: changed && messages.length ? messages[messages.length - 1].renderId : this.data.scrollIntoView
      });
    } catch (error) {
      if (!options.silent) wx.showToast({ title: String((error && (error.detail || error.message)) || "消息加载失败"), icon: "none" });
    } finally {
      this.isFetching = false;
    }
  },

  handleInput(event) {
    this.setData({ inputText: event.detail.value || "" });
  },

  async sendMessage(payload) {
    if (this.data.sending || !this.data.conversationId) return;
    this.setData({ sending: true, attachmentOpen: false });
    try {
      const response = await api.sendMutualHelpChatMessage(this.data.conversationId, {
        userId: this.data.currentUserId,
        idempotencyKey: `${this.data.currentUserId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        ...payload
      });
      const message = response.data && response.data.message;
      if (message) {
        const item = previewMessage(message, this.data.currentUserId);
        this.setData({ messages: [...this.data.messages, item], scrollIntoView: item.renderId, inputText: "" });
      }
      this.loadMessages({ silent: true });
    } catch (error) {
      wx.showToast({ title: String((error && (error.detail || error.message)) || "发送失败，请重试"), icon: "none" });
    } finally {
      this.setData({ sending: false });
    }
  },

  handleSendText() {
    const text = String(this.data.inputText || "").trim();
    if (!text) return;
    this.sendMessage({ messageType: "text", text });
  },

  handleToggleAttachments() {
    this.setData({ attachmentOpen: !this.data.attachmentOpen });
  },

  handleChooseImage() {
    const choose = new Promise((resolve, reject) => {
      const options = { count: 1, sourceType: ["album", "camera"], success: resolve, fail: reject };
      if (typeof wx.chooseMedia === "function") wx.chooseMedia({ ...options, mediaType: ["image"] });
      else wx.chooseImage(options);
    });
    choose.then(async (result = {}) => {
      const file = (result.tempFiles || [])[0];
      const filePath = file && file.tempFilePath || (result.tempFilePaths || [])[0] || "";
      if (!filePath) return;
      this.setData({ attachmentOpen: false });
      try {
        const asset = await api.uploadAsset({ filePath, mediaType: "image", ownerUserId: this.data.currentUserId });
        await this.sendMessage({ messageType: "image", imageUrl: asset.url });
      } catch (error) {
        wx.showToast({ title: String((error && (error.detail || error.message)) || "图片上传失败"), icon: "none" });
      }
    }).catch(() => {});
  },

  handleChooseMiniProgram() {
    const links = this.data.miniProgramLinks || [];
    if (!links.length) {
      wx.showToast({ title: "该任务没有配置可发送的小程序入口", icon: "none" });
      return;
    }
    const choose = (index) => {
      const link = links[index];
      if (link) this.sendMessage({
        messageType: "mini_program",
        miniProgram: { title: link.displayTitle || link.title, shortLink: link.shortLink || link.raw }
      });
    };
    this.setData({ attachmentOpen: false });
    if (links.length === 1) {
      choose(0);
      return;
    }
    wx.showActionSheet({
      itemList: links.map((item) => item.displayTitle || item.title || "目标小程序"),
      success: (result = {}) => choose(Number(result.tapIndex))
    });
  },

  handlePreviewImage(event) {
    const current = String(event.currentTarget.dataset.url || "");
    if (!current) return;
    wx.previewImage({ current, urls: [current] });
  },

  handleOpenMiniProgram(event) {
    const shortLink = String(event.currentTarget.dataset.shortLink || "");
    if (!shortLink) return;
    wx.navigateToMiniProgram({
      shortLink,
      fail: () => wx.setClipboardData({ data: shortLink, success: () => wx.showToast({ title: "未能直接打开，已复制小程序链接", icon: "none" }) })
    });
  }
});
