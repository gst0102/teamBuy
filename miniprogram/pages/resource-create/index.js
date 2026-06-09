const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

function createUploadItem(data, fallbackName, fallbackType) {
  const mediaType = data.mediaType || fallbackType;
  return {
    name: fallbackName,
    type: mediaType,
    url: data.url,
    isCover: false
  };
}

Page({
  data: {
    submitting: false,
    previewSubmitting: false,
    uploading: false,
    type: "资料",
    typeOptions: ["房源", "团购", "视频", "文档", "资料"],
    categories: [],
    selectedCategoryIds: [],
    uploadedAssets: [],
    form: {
      title: "",
      projectName: "",
      detailText: "",
      coverUrl: "",
      locationText: "",
      phone: "",
      relayNotice: "",
      generatePage: true,
      requirePhone: false,
      requireAddress: false
    }
  },
  onShow() {
    if (!getCurrentUser()) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadCategories();
  },
  async loadCategories() {
    const currentUser = getCurrentUser();
    if (!currentUser) return;
    try {
      const res = await api.fetchCategories(currentUser.id);
      const categories = (res.data || []).map((item) => ({
        ...item,
        selected: this.data.selectedCategoryIds.includes(item.id)
      }));
      this.setData({ categories });
    } catch (error) {
      wx.showToast({ title: error.detail || "标签加载失败", icon: "none" });
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
  handleCategoryToggle(event) {
    const id = event.currentTarget.dataset.id;
    const selected = this.data.selectedCategoryIds.includes(id)
      ? this.data.selectedCategoryIds.filter((item) => item !== id)
      : [...this.data.selectedCategoryIds, id];
    this.setData({
      selectedCategoryIds: selected,
      categories: this.data.categories.map((item) => ({
        ...item,
        selected: selected.includes(item.id)
      }))
    });
  },
  handleGoTagManage() {
    wx.navigateTo({ url: "/pages/tag-manage/index" });
  },
  handleGoImports() {
    wx.switchTab({ url: "/pages/imports/index" });
  },
  handleChooseUpload() {
    wx.showActionSheet({
      itemList: ["上传图片", "上传视频", "上传文件"],
      success: ({ tapIndex }) => {
        if (tapIndex === 0) {
          this.chooseImageFiles();
          return;
        }
        if (tapIndex === 1) {
          this.chooseVideoFile();
          return;
        }
        this.chooseMessageFile();
      }
    });
  },
  chooseImageFiles() {
    wx.chooseMedia({
      count: 9,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      success: ({ tempFiles = [] }) => {
        tempFiles.forEach((file) => {
          this.uploadAsset({
            path: file.tempFilePath,
            name: file.tempFilePath.split("/").pop() || "image.jpg",
            type: "image"
          });
        });
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
        if (!file) return;
        this.uploadAsset({
          path: file.tempFilePath,
          name: file.tempFilePath.split("/").pop() || "video.mp4",
          type: "video"
        });
      }
    });
  },
  chooseMessageFile() {
    if (!wx.chooseMessageFile) {
      wx.showToast({ title: "当前基础库不支持文件选择", icon: "none" });
      return;
    }
    wx.chooseMessageFile({
      count: 1,
      type: "file",
      success: ({ tempFiles = [] }) => {
        const file = tempFiles[0];
        if (!file) return;
        const type = (file.name || "").toLowerCase().endsWith(".mp4") ? "video" : "file";
        this.uploadAsset({
          path: file.path,
          name: file.name || "file",
          type
        });
      }
    });
  },
  syncCoverState(uploadedAssets) {
    const coverUrl = this.data.form.coverUrl;
    return uploadedAssets.map((item, index) => ({
      ...item,
      isCover: item.type === "image" && !!coverUrl && item.url === coverUrl,
      roleText:
        item.type === "image"
          ? item.url === coverUrl
            ? "封面图"
            : `详情图 ${index + 1}`
          : item.type === "video"
            ? "详情视频"
            : "详情附件"
    }));
  },
  uploadAsset({ path, name, type }) {
    const currentUser = getCurrentUser();
    this.setData({ uploading: true });
    api
      .uploadAsset({
        filePath: path,
        mediaType: type,
        ownerUserId: currentUser ? currentUser.id : ""
      })
      .then((data) => {
        const nextItem = createUploadItem(data, name, type);
        const uploadedAssets = [...this.data.uploadedAssets, nextItem];
        const nextState = {};
        if (!this.data.form.coverUrl && nextItem.type === "image") {
          nextState["form.coverUrl"] = nextItem.url;
        }
        const syncedAssets = this.syncCoverState(uploadedAssets);
        nextState.uploadedAssets = syncedAssets;
        this.setData(nextState);
        wx.showToast({ title: nextItem.type === "image" ? "已上传，首图已设为封面" : "上传成功", icon: "none" });
      })
      .catch((error) => {
        wx.showToast({ title: error.detail || "上传失败", icon: "none" });
      })
      .finally(() => {
        this.setData({ uploading: false });
      });
  },
  handleSetCover(event) {
    const url = event.currentTarget.dataset.url;
    const syncedAssets = this.data.uploadedAssets.map((item, index) => ({
      ...item,
      isCover: item.type === "image" && item.url === url,
      roleText:
        item.type === "image"
          ? item.url === url
            ? "封面图"
            : `详情图 ${index + 1}`
          : item.type === "video"
            ? "详情视频"
            : "详情附件"
    }));
    this.setData({
      "form.coverUrl": url,
      uploadedAssets: syncedAssets
    });
  },
  handleRemoveUpload(event) {
    const url = event.currentTarget.dataset.url;
    const uploadedAssets = this.data.uploadedAssets.filter((item) => item.url !== url);
    const nextState = {};
    if (this.data.form.coverUrl === url) {
      const nextImage = uploadedAssets.find((item) => item.type === "image");
      nextState["form.coverUrl"] = nextImage ? nextImage.url : "";
    }
    nextState.uploadedAssets = this.syncCoverState(uploadedAssets);
    this.setData(nextState);
  },
  buildDetailText() {
    const form = this.data.form;
    const attachmentAssets = this.data.uploadedAssets.filter((item) => item.type === "file");
    const parts = [
      form.detailText.trim(),
      form.locationText ? `位置：${form.locationText.trim()}` : "",
      form.phone ? `电话：${form.phone.trim()}` : "",
      attachmentAssets.length ? `附件素材：\n${attachmentAssets.map((item) => item.url).join("\n")}` : ""
    ].filter(Boolean);
    return parts.join("\n\n");
  },
  buildMediaPayload() {
    return this.data.uploadedAssets
      .filter((item) => item.type === "image" || item.type === "video")
      .map((item, index) => ({
        type: item.type,
        url: item.url,
        sortOrder: item.isCover ? 1 : index + 2
      }))
      .sort((a, b) => a.sortOrder - b.sortOrder);
  },
  buildCardPayload() {
    const currentUser = getCurrentUser();
    const form = this.data.form;
    return {
      ownerUserId: currentUser.id,
      title: form.title.trim(),
      projectName: form.projectName.trim() || this.data.type,
      detailText: this.buildDetailText(),
      coverUrl: form.coverUrl.trim() || null,
      locationText: form.locationText.trim() || null,
      phone: form.phone.trim() || null,
      sourceUrl: null,
      categoryIds: this.data.categories.filter((item) => item.selected).map((item) => item.id),
      media: this.buildMediaPayload(),
      relayNotice: form.relayNotice.trim() || "请留下你的称呼和联系方式，方便后续跟进。",
      relayConfig: {
        enabled: form.generatePage,
        requirePhone: form.requirePhone,
        requireAddress: form.requireAddress
      }
    };
  },
  async submitCard(options = {}) {
    const { publishAfterCreate = false } = options;
    const currentUser = getCurrentUser();
    const form = this.data.form;
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if (!form.title.trim()) {
      wx.showToast({ title: "请填写资源标题", icon: "none" });
      return;
    }
    if (!form.coverUrl && this.data.uploadedAssets.some((item) => item.type === "image")) {
      this.setData({
        "form.coverUrl": this.data.uploadedAssets.find((item) => item.type === "image").url,
        uploadedAssets: this.syncCoverState(this.data.uploadedAssets)
      });
    }
    const loadingKey = publishAfterCreate ? "previewSubmitting" : "submitting";
    this.setData({ [loadingKey]: true });
    try {
      const created = await api.createCard(this.buildCardPayload());
      const cardId = created.data.id;
      if (publishAfterCreate) {
        await api.publishCard(cardId, currentUser.id);
        wx.navigateTo({ url: `/pages/card-view/index?id=${cardId}` });
        return;
      }
      wx.navigateTo({ url: `/pages/card-edit/index?id=${cardId}` });
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "保存失败", icon: "none" });
    } finally {
      this.setData({ [loadingKey]: false });
    }
  },
  async handleSubmit() {
    await this.submitCard({ publishAfterCreate: false });
  },
  async handlePreview() {
    await this.submitCard({ publishAfterCreate: true });
  }
});
