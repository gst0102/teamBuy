const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    submitting: false,
    uploading: false,
    type: "资料",
    sourceMode: "original",
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
      sourceUrl: "",
      relayNotice: "",
      isPublic: true,
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
    try {
      const res = await api.fetchCategories(currentUser.id);
      const categories = (res.data || []).map((item) => ({
        ...item,
        selected: this.data.selectedCategoryIds.includes(item.id)
      }));
      this.setData({ categories });
    } catch (error) {
      wx.showToast({ title: "标签加载失败", icon: "none" });
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
  handleSourceModeChange(event) {
    this.setData({ sourceMode: event.currentTarget.dataset.mode });
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
  handlePreviewPlaceholder() {
    wx.showToast({ title: "保存后可进入资源页查看", icon: "none" });
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
      wx.showToast({ title: "当前基础库暂不支持文件选择", icon: "none" });
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
        const uploadedAssets = [
          ...this.data.uploadedAssets,
          {
            name,
            type: data.mediaType || type,
            url: data.url
          }
        ];
        const nextState = { uploadedAssets };
        if (!this.data.form.coverUrl && (data.mediaType || type) === "image") {
          nextState["form.coverUrl"] = data.url;
        }
        this.setData(nextState);
        wx.showToast({ title: "上传成功", icon: "success" });
      })
      .catch((error) => {
        wx.showToast({ title: error.detail || "上传失败", icon: "none" });
      })
      .finally(() => {
        this.setData({ uploading: false });
      });
  },
  handleRemoveUpload(event) {
    const url = event.currentTarget.dataset.url;
    const uploadedAssets = this.data.uploadedAssets.filter((item) => item.url !== url);
    const nextState = { uploadedAssets };
    if (this.data.form.coverUrl === url) {
      const nextImage = uploadedAssets.find((item) => item.type === "image");
      nextState["form.coverUrl"] = nextImage ? nextImage.url : "";
    }
    this.setData(nextState);
  },
  buildDetailText() {
    const form = this.data.form;
    const parts = [
      form.detailText,
      form.locationText ? `位置：${form.locationText}` : "",
      form.phone ? `电话：${form.phone}` : "",
      form.sourceUrl ? `链接：${form.sourceUrl}` : "",
      this.data.uploadedAssets.length ? `素材：${this.data.uploadedAssets.map((item) => item.url).join("\n")}` : ""
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
        categoryIds: this.data.categories.filter((item) => item.selected).map((item) => item.id),
        relayNotice: form.relayNotice.trim() || "请留下你的称呼和联系方式，方便后续跟进。",
        relayConfig: {
          enabled: form.generatePage,
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
