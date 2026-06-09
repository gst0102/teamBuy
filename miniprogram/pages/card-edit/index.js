const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

function statusLabel(status) {
  return status === "published" ? "已发布" : "未发布";
}

function normalizeMedia(media = [], coverUrl = "") {
  return media
    .map((item, index) => ({
      ...item,
      sortOrder: item.sortOrder || index + 1
    }))
    .sort((a, b) => a.sortOrder - b.sortOrder)
    .map((item, index) => ({
      ...item,
      sortOrder: index + 1,
      isCover: item.type === "image" && item.url === coverUrl,
      roleText: item.type === "video" ? "详情视频" : item.url === coverUrl ? "封面图" : "详情图片"
    }));
}

Page({
  data: {
    cardId: "",
    card: null,
    categories: [],
    saving: false,
    publishing: false,
    uploading: false,
    statusLabel: ""
  },
  onLoad(query) {
    this.setData({ cardId: query.id });
  },
  async onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    await this.loadAll();
  },
  async loadAll() {
    await Promise.all([this.loadCard(), this.loadCategories()]);
  },
  async loadCard() {
    try {
      const res = await api.fetchCard(this.data.cardId);
      const card = {
        ...res.data,
        media: normalizeMedia(res.data.media || [], res.data.coverUrl),
        relayConfig: {
          enabled: !(res.data && res.data.relayConfig && res.data.relayConfig.enabled === false),
          requirePhone: !!(res.data && res.data.relayConfig && res.data.relayConfig.requirePhone),
          requireAddress: !!(res.data && res.data.relayConfig && res.data.relayConfig.requireAddress)
        }
      };
      this.setData({ card, statusLabel: statusLabel(card.status) });
      this.syncCategorySelection(card.categoryIds || []);
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "卡片加载失败", icon: "none" });
    }
  },
  async loadCategories() {
    const currentUser = getCurrentUser();
    if (!currentUser) return;
    try {
      const res = await api.fetchCategories(currentUser.id);
      this.setData({ categories: res.data || [] });
      this.syncCategorySelection(this.data.card ? this.data.card.categoryIds || [] : []);
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "标签加载失败", icon: "none" });
    }
  },
  syncCategorySelection(categoryIds) {
    const selected = categoryIds || [];
    this.setData({
      categories: this.data.categories.map((item) => ({
        ...item,
        selected: selected.includes(item.id)
      }))
    });
  },
  handleFieldChange(event) {
    const field = event.currentTarget.dataset.field;
    const nextState = {
      [`card.${field}`]: event.detail.value
    };
    if (field === "coverUrl") {
      nextState["card.media"] = normalizeMedia(this.data.card.media || [], event.detail.value);
    }
    this.setData(nextState);
  },
  handleToggleRelayPhone(event) {
    this.setData({
      "card.relayConfig.requirePhone": event.detail.value
    });
  },
  handleToggleRelayAddress(event) {
    this.setData({
      "card.relayConfig.requireAddress": event.detail.value
    });
  },
  handleCategoryToggle(event) {
    const id = event.currentTarget.dataset.id;
    const categories = this.data.categories.map((item) => ({
      ...item,
      selected: item.id === id ? !item.selected : item.selected
    }));
    this.setData({
      categories,
      "card.categoryIds": categories.filter((item) => item.selected).map((item) => item.id)
    });
  },
  handleGoTagManage() {
    wx.navigateTo({ url: "/pages/tag-manage/index" });
  },
  handleSetCover(event) {
    const url = event.currentTarget.dataset.url;
    if (!url) return;
    this.setData({
      "card.coverUrl": url,
      "card.media": normalizeMedia(this.data.card.media || [], url)
    });
  },
  handleRemoveMedia(event) {
    const index = Number(event.currentTarget.dataset.index);
    const media = [...(this.data.card.media || [])];
    const removed = media[index];
    if (!removed) return;
    const nextMedia = media.filter((_, itemIndex) => itemIndex !== index);
    const nextCoverUrl =
      removed.url === this.data.card.coverUrl
        ? ((nextMedia.find((item) => item.type === "image") || {}).url || "")
        : this.data.card.coverUrl;
    this.setData({
      "card.coverUrl": nextCoverUrl,
      "card.media": normalizeMedia(nextMedia, nextCoverUrl)
    });
  },
  handleMoveMedia(event) {
    const index = Number(event.currentTarget.dataset.index);
    const direction = event.currentTarget.dataset.direction;
    const nextIndex = direction === "up" ? index - 1 : index + 1;
    const media = [...(this.data.card.media || [])];
    if (index < 0 || nextIndex < 0 || index >= media.length || nextIndex >= media.length) return;
    const current = media[index];
    media[index] = media[nextIndex];
    media[nextIndex] = current;
    const reordered = media.map((item, itemIndex) => ({
      ...item,
      sortOrder: itemIndex + 1
    }));
    this.setData({
      "card.media": normalizeMedia(reordered, this.data.card.coverUrl)
    });
  },
  handleChooseUpload() {
    if (this.data.uploading) return;
    wx.showActionSheet({
      itemList: ["上传图片", "上传视频"],
      success: ({ tapIndex }) => {
        if (tapIndex === 0) {
          this.chooseImageFiles();
          return;
        }
        this.chooseVideoFile();
      }
    });
  },
  chooseImageFiles() {
    wx.chooseMedia({
      count: 9,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      success: ({ tempFiles = [] }) => {
        this.uploadAssets(tempFiles.map((file) => file.tempFilePath).filter(Boolean), "image");
      }
    });
  },
  chooseVideoFile() {
    wx.chooseMedia({
      count: 1,
      mediaType: ["video"],
      sourceType: ["album", "camera"],
      success: ({ tempFiles = [] }) => {
        const file = tempFiles[0];
        if (!file || !file.tempFilePath) return;
        this.uploadAssets([file.tempFilePath], "video");
      }
    });
  },
  uploadAssets(paths, type) {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if (!paths.length) return;
    this.setData({ uploading: true });
    Promise.all(
      paths.map((path) =>
        api.uploadAsset({
          filePath: path,
          mediaType: type,
          ownerUserId: currentUser.id
        })
      )
    )
      .then((uploaded) => {
        const baseLength = (this.data.card.media || []).length;
        const nextItems = uploaded.map((data, index) => ({
          type: data.mediaType || type,
          url: data.url,
          sortOrder: baseLength + index + 1
        }));
        const nextMedia = [...(this.data.card.media || []), ...nextItems];
        const firstImage = nextItems.find((item) => item.type === "image");
        const nextCoverUrl =
          this.data.card.coverUrl || (firstImage ? firstImage.url : "");
        this.setData({
          "card.coverUrl": nextCoverUrl,
          "card.media": normalizeMedia(nextMedia, nextCoverUrl)
        });
        wx.showToast({ title: "上传成功，记得保存", icon: "none" });
      })
      .catch((error) => {
        wx.showToast({ title: error.detail || error.errMsg || "上传失败", icon: "none" });
      })
      .finally(() => {
        this.setData({ uploading: false });
      });
  },
  handleMediaTap(event) {
    const url = event.currentTarget.dataset.url;
    const type = event.currentTarget.dataset.type;
    if (!url || type !== "image") return;
    this.setData({
      "card.coverUrl": url,
      "card.media": normalizeMedia(this.data.card.media || [], url)
    });
    wx.showToast({ title: "已设为封面", icon: "success" });
  },
  buildPayload(currentUser) {
    const card = this.data.card || {};
    const media = Array.isArray(card.media)
      ? card.media.map((item, index) => ({
          type: item.type,
          url: item.url,
          sortOrder: index + 1
        }))
      : [];
    return {
      ownerUserId: currentUser.id,
      title: (card.title || "").trim(),
      coverUrl: card.coverUrl || null,
      detailText: card.detailText || "",
      projectName: card.projectName || null,
      locationText: card.locationText || null,
      phone: card.phone || null,
      relayNotice: card.relayNotice || null,
      sourceUrl: card.sourceUrl || null,
      enabledFields: Array.isArray(card.enabledFields) ? card.enabledFields : [],
      categoryIds: this.data.categories.filter((item) => item.selected).map((item) => item.id),
      media,
      relayConfig: {
        enabled: !(card.relayConfig && card.relayConfig.enabled === false),
        requirePhone: !!(card.relayConfig && card.relayConfig.requirePhone),
        requireAddress: !!(card.relayConfig && card.relayConfig.requireAddress)
      }
    };
  },
  async handleSave() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return false;
    }
    if (!this.data.card || !this.data.card.title || !this.data.card.title.trim()) {
      wx.showToast({ title: "标题不能为空", icon: "none" });
      return false;
    }
    this.setData({ saving: true });
    try {
      const res = await api.updateCard(this.data.cardId, this.buildPayload(currentUser));
      const updatedCard = {
        ...this.data.card,
        ...(res.data || {})
      };
      updatedCard.media = normalizeMedia(updatedCard.media || [], updatedCard.coverUrl);
      this.setData({
        card: updatedCard,
        statusLabel: statusLabel(updatedCard.status)
      });
      wx.showToast({ title: "已保存", icon: "success" });
      return true;
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "保存失败", icon: "none" });
      return false;
    } finally {
      this.setData({ saving: false });
    }
  },
  async handlePublish() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    const saved = await this.handleSave();
    if (!saved) return;
    this.setData({ publishing: true });
    try {
      await api.publishCard(this.data.cardId, currentUser.id);
      wx.navigateTo({ url: `/pages/card-view/index?id=${this.data.cardId}` });
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "发布失败", icon: "none" });
    } finally {
      this.setData({ publishing: false });
    }
  }
});
