const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

function cardTypeLabel(cardType) {
  if (cardType === "property_listing") return "房源";
  if (cardType === "groupbuy_product") return "商品";
  if (cardType === "image_ocr") return "图片";
  if (cardType === "link") return "链接";
  return "资料";
}

function decorateNote(note, selectedItems) {
  const config = note.visibilityConfig || {};
  const selected = selectedItems.find((item) => item.noteId === note.id);
  return {
    ...note,
    selected: Boolean(selected),
    badge: cardTypeLabel(config.cardType),
    selectedText: selected ? "已选" : "选择"
  };
}

function decorateSelectedItem(item, note, index) {
  const config = (note && note.visibilityConfig) || {};
  return {
    ...item,
    index,
    title: item.displayTitle || (note && note.title) || "资料",
    summary: (note && note.summary) || "",
    coverUrl: note && note.coverUrl,
    badge: cardTypeLabel(config.cardType),
    visibleText: item.visible === false ? "已隐藏" : "展示中"
  };
}

Page({
  data: {
    id: "",
    user: null,
    loading: false,
    saving: false,
    status: "draft",
    name: "",
    description: "",
    bannerUrl: "",
    shareTitle: "",
    phone: "",
    wechat: "",
    contactText: "欢迎联系我了解详情",
    groupBy: "none",
    notes: [],
    selectedItems: [],
    selectedRows: []
  },
  onLoad(options) {
    this.setData({ id: options.id || "" });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    this.loadAll();
  },
  async loadAll() {
    const { id, user } = this.data;
    if (!user) return;
    this.setData({ loading: true });
    try {
      let selectedItems = [];
      if (id) {
        const detail = await api.fetchShowcase(id, user.id);
        const page = detail.data || {};
        const contact = page.contactConfig || {};
        const display = page.displayConfig || {};
        selectedItems = (page.items || []).map((item, index) => ({
          noteId: item.noteId,
          sortOrder: item.sortOrder == null ? index : item.sortOrder,
          sectionTitle: item.sectionTitle || "",
          displayTitle: item.displayTitle || "",
          visible: item.visible !== false,
          fieldConfig: item.fieldConfig || {}
        }));
        this.setData({
          status: page.status || "draft",
          name: page.name || "",
          description: page.description || "",
          bannerUrl: page.bannerUrl || "",
          shareTitle: page.shareTitle || "",
          phone: contact.phone || "",
          wechat: contact.wechat || "",
          contactText: contact.contactText || "欢迎联系我了解详情",
          groupBy: display.groupBy || "none",
          selectedItems
        });
      }
      const notesRes = await api.fetchNotes({ ownerUserId: user.id, sort: "updated" });
      const notes = notesRes.data || [];
      this.setData({
        notes: notes.map((note) => decorateNote(note, selectedItems))
      });
      this.rebuildSelectedRows();
    } catch (error) {
      wx.showToast({ title: error.detail || "展示页加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  updateField(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [key]: event.detail.value });
  },
  handleGroupChange(event) {
    this.setData({ groupBy: event.detail.value });
  },
  async handleBannerUpload() {
    const { user } = this.data;
    if (!user) return;
    try {
      const chooseRes = await wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sourceType: ["album", "camera"],
        sizeType: ["compressed"]
      });
      const file = (chooseRes.tempFiles || [])[0];
      if (!file || !file.tempFilePath) return;
      wx.showLoading({ title: "上传中" });
      const uploaded = await api.uploadAsset({
        filePath: file.tempFilePath,
        mediaType: "image",
        ownerUserId: user.id
      });
      this.setData({ bannerUrl: uploaded.url || uploaded.displayUrl || "" });
      wx.showToast({ title: "已上传", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "上传失败", icon: "none" });
    } finally {
      wx.hideLoading();
    }
  },
  toggleNote(event) {
    const noteId = event.currentTarget.dataset.id;
    const selectedItems = this.data.selectedItems.slice();
    const existingIndex = selectedItems.findIndex((item) => item.noteId === noteId);
    if (existingIndex >= 0) {
      selectedItems.splice(existingIndex, 1);
    } else {
      selectedItems.push({
        noteId,
        sortOrder: selectedItems.length,
        sectionTitle: "",
        displayTitle: "",
        visible: true,
        fieldConfig: {}
      });
    }
    this.setData({ selectedItems: this.reindexItems(selectedItems) });
    this.refreshSelectionState();
  },
  toggleSelectedVisible(event) {
    const noteId = event.currentTarget.dataset.id;
    const selectedItems = this.data.selectedItems.map((item) => (
      item.noteId === noteId ? { ...item, visible: item.visible === false } : item
    ));
    this.setData({ selectedItems });
    this.rebuildSelectedRows();
  },
  removeSelected(event) {
    const noteId = event.currentTarget.dataset.id;
    const selectedItems = this.data.selectedItems.filter((item) => item.noteId !== noteId);
    this.setData({ selectedItems: this.reindexItems(selectedItems) });
    this.refreshSelectionState();
  },
  updateSelectedField(event) {
    const noteId = event.currentTarget.dataset.id;
    const key = event.currentTarget.dataset.key;
    const selectedItems = this.data.selectedItems.map((item) => (
      item.noteId === noteId ? { ...item, [key]: event.detail.value } : item
    ));
    this.setData({ selectedItems });
    this.rebuildSelectedRows();
  },
  moveSelected(event) {
    const noteId = event.currentTarget.dataset.id;
    const direction = event.currentTarget.dataset.direction;
    const selectedItems = this.data.selectedItems.slice();
    const index = selectedItems.findIndex((item) => item.noteId === noteId);
    const target = direction === "up" ? index - 1 : index + 1;
    if (index < 0 || target < 0 || target >= selectedItems.length) return;
    const temp = selectedItems[index];
    selectedItems[index] = selectedItems[target];
    selectedItems[target] = temp;
    this.setData({ selectedItems: this.reindexItems(selectedItems) });
    this.rebuildSelectedRows();
  },
  reindexItems(items) {
    return items.map((item, index) => ({ ...item, sortOrder: index }));
  },
  refreshSelectionState() {
    const { notes, selectedItems } = this.data;
    this.setData({ notes: notes.map((note) => decorateNote(note, selectedItems)) });
    this.rebuildSelectedRows();
  },
  rebuildSelectedRows() {
    const { selectedItems, notes } = this.data;
    const rows = selectedItems.map((item, index) => {
      const note = notes.find((row) => row.id === item.noteId);
      return decorateSelectedItem(item, note, index);
    });
    this.setData({ selectedRows: rows });
  },
  buildPayload() {
    const { user, name, description, bannerUrl, shareTitle, phone, wechat, contactText, groupBy, selectedItems } = this.data;
    return {
      ownerUserId: user.id,
      name,
      description,
      bannerUrl,
      shareTitle,
      templateId: "classic_grid",
      contactConfig: {
        phone,
        wechat,
        contactText,
        showPhone: Boolean(phone),
        showWechat: Boolean(wechat)
      },
      displayConfig: {
        groupBy,
        showTags: true,
        showSearch: false,
        primaryColor: "#1677ff"
      },
      items: selectedItems
    };
  },
  async saveDraft() {
    const { id } = this.data;
    const payload = this.buildPayload();
    this.setData({ saving: true });
    try {
      const res = id ? await api.updateShowcase(id, payload) : await api.createShowcase(payload);
      const page = res.data || {};
      this.setData({ id: page.id, status: page.status || "draft" });
      wx.showToast({ title: "已保存", icon: "success" });
      return page;
    } catch (error) {
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
      throw error;
    } finally {
      this.setData({ saving: false });
    }
  },
  async handleSave() {
    await this.saveDraft();
  },
  async handlePublish() {
    try {
      const page = await this.saveDraft();
      const res = await api.publishShowcase(page.id, this.data.user.id);
      this.setData({ status: res.data.status || "published" });
      wx.showToast({ title: "已发布", icon: "success" });
    } catch (error) {
      if (!error.detail) return;
    }
  },
  async handleArchive() {
    const { id, user } = this.data;
    if (!id) return;
    try {
      const res = await api.archiveShowcase(id, user.id);
      this.setData({ status: res.data.status || "archived" });
      wx.showToast({ title: "已下架", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "下架失败", icon: "none" });
    }
  },
  async handlePreview() {
    try {
      const page = await this.saveDraft();
      wx.navigateTo({ url: `/pages/showcase-view/index?id=${page.id}&preview=1` });
    } catch (error) {
      if (!error.detail) return;
    }
  }
});
