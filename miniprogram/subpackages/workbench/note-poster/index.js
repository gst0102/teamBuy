const api = require("../../../services/api");
const { getCurrentUser } = require("../../../utils/dashboard");
const {
  buildNoteSharePlan,
  buildNoteShareTitle,
  getNoteShareSnapshotState,
  getShareImageUrlFromState,
  prepareNoteShareSnapshot,
  SHARE_CARD_CANVAS_ID
} = require("../../../plugins/share-snapshot/index");

function buildShareCopy(note, user) {
  const plan = buildNoteSharePlan(note, user);
  const source = plan.source || {};
  return [
    buildNoteShareTitle(note, user),
    source.summary || "",
    ...(source.facts || []).slice(0, 3)
  ].filter(Boolean).join("\n");
}

function downloadShareImage(url) {
  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.tempFilePath) {
          resolve(res.tempFilePath);
          return;
        }
        reject(new Error("分享图下载失败"));
      },
      fail: reject
    });
  });
}

Page({
  data: {
    noteId: "",
    user: null,
    note: null,
    shareImage: "",
    shareImageState: "missing",
    shareStatusText: "分享图准备中",
    savingPoster: false,
    copyText: ""
  },

  onLoad(options = {}) {
    this.setData({ noteId: options.id || "" });
  },

  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    this.loadNote();
  },

  async loadNote() {
    const user = this.data.user || getCurrentUser();
    const noteId = this.data.noteId;
    if (!user || !noteId) return;
    try {
      const response = await api.fetchNote(noteId, user.id);
      const note = response.data || {};
      this.setData({ note, copyText: buildShareCopy(note, user) });
      await this.prepareShareImage(note, user);
    } catch (error) {
      wx.showToast({ title: error.detail || "分享图加载失败", icon: "none" });
    }
  },

  async prepareShareImage(note = this.data.note, user = this.data.user || getCurrentUser()) {
    if (!note || !user || !note.id) return "";
    const current = getNoteShareSnapshotState(note, user.id, user);
    const existing = getShareImageUrlFromState(current);
    if (existing) {
      this.setData({ shareImage: existing, shareImageState: "ready", shareStatusText: "分享图已准备好" });
      return existing;
    }
    if (current.status === "preparing") return "";
    this.setData({ shareImage: "", shareImageState: "preparing", shareStatusText: "分享图生成中" });
    try {
      const result = await prepareNoteShareSnapshot({
        page: this,
        canvasId: SHARE_CARD_CANVAS_ID,
        note,
        ownerUserId: user.id,
        user
      });
      const imageUrl = result && result.snapshot && result.snapshot.url;
      if (!imageUrl) throw new Error("分享图地址为空");
      this.setData({ shareImage: imageUrl, shareImageState: "ready", shareStatusText: "分享图已准备好" });
      return imageUrl;
    } catch (error) {
      this.setData({ shareImage: "", shareImageState: "failed", shareStatusText: "重试分享图" });
      return "";
    }
  },

  async handleSavePoster() {
    if (this.data.savingPoster) return;
    const imageUrl = this.data.shareImage || await this.prepareShareImage();
    if (!imageUrl) {
      wx.showToast({ title: "分享图还没准备好，请稍后重试", icon: "none" });
      return;
    }
    this.setData({ savingPoster: true });
    try {
      const filePath = await downloadShareImage(imageUrl);
      await new Promise((resolve, reject) => {
        wx.saveImageToPhotosAlbum({ filePath, success: resolve, fail: reject });
      });
      wx.showToast({ title: "已保存分享图", icon: "success" });
    } catch (error) {
      const message = String((error && (error.errMsg || error.message)) || "");
      if (message.includes("auth") || message.includes("authorize") || message.includes("permission")) {
        wx.showModal({
          title: "需要相册权限",
          content: "请允许保存到相册后再试。",
          confirmText: "去设置",
          confirmColor: "#1677ff",
          success: ({ confirm }) => {
            if (confirm && wx.openSetting) wx.openSetting();
          }
        });
      } else {
        wx.showToast({ title: "保存分享图失败", icon: "none" });
      }
    } finally {
      this.setData({ savingPoster: false });
    }
  },

  handlePreviewPage() {
    wx.navigateTo({ url: `/pages/note-preview/index?id=${encodeURIComponent(this.data.noteId)}` });
  },

  handleRetry() {
    if (this.data.shareImageState === "preparing") return;
    this.prepareShareImage();
  },

  handleCopy() {
    if (!this.data.copyText) return;
    wx.setClipboardData({
      data: this.data.copyText,
      success: () => wx.showToast({ title: "文案已复制", icon: "success" }),
      fail: () => wx.showToast({ title: "复制失败", icon: "none" })
    });
  }
});
