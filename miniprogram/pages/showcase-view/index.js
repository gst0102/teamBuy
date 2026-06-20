const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

function sectionName(item, groupBy) {
  if (groupBy === "custom" && item.sectionTitle) return item.sectionTitle;
  if (groupBy === "cardType") {
    if (item.cardType === "property_listing") return "房源";
    if (item.cardType === "groupbuy_product") return "商品";
    if (item.cardType === "image_ocr") return "图片";
    if (item.cardType === "link") return "链接";
    return "资料";
  }
  if (groupBy === "tag" && item.tags && item.tags.length) return item.tags[0];
  return "精选资料";
}

function buildSections(items, groupBy) {
  const sections = [];
  (items || []).forEach((item) => {
    const title = sectionName(item, groupBy);
    let section = sections.find((row) => row.title === title);
    if (!section) {
      section = { title, items: [] };
      sections.push(section);
    }
    section.items.push({
      ...item,
      tagText: (item.tags || []).slice(0, 3).join(" · "),
      badge: sectionName(item, "cardType")
    });
  });
  return sections;
}

function summarizePreviewItems(items, notes) {
  return (items || []).map((item) => {
    const note = (notes || []).find((row) => row.id === item.noteId);
    const config = (note && note.visibilityConfig) || {};
    return {
      noteId: item.noteId,
      title: item.displayTitle || (note && note.title) || "资料",
      summary: (note && note.summary) || "",
      coverUrl: note && note.coverUrl,
      sectionTitle: item.sectionTitle || "",
      sortOrder: item.sortOrder || 0,
      cardType: config.cardType || "text_note",
      systemCategory: config.systemCategory || "",
      tags: Array.isArray(config.tags) ? config.tags : []
    };
  }).filter((item) => item.noteId);
}

Page({
  data: {
    id: "",
    preview: false,
    user: null,
    page: null,
    sections: [],
    loading: false
  },
  onLoad(options) {
    this.setData({
      id: options.id || "",
      preview: options.preview === "1"
    });
  },
  onShow() {
    this.setData({ user: getCurrentUser() });
    this.loadPage();
  },
  async loadPage() {
    const { id, preview, user } = this.data;
    if (!id) return;
    this.setData({ loading: true });
    try {
      const res = preview && user
        ? await api.fetchShowcase(id, user.id)
        : await api.fetchPublicShowcase(id);
      const page = res.data || {};
      if (preview && user) {
        const notesRes = await api.fetchNotes({ ownerUserId: user.id });
        page.items = summarizePreviewItems(page.items || [], notesRes.data || []);
      }
      const display = page.displayConfig || {};
      this.setData({
        page,
        sections: buildSections(page.items || [], display.groupBy || "none")
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "展示页不可访问", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  openNote(event) {
    const noteId = event.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/note-preview/index?id=${noteId}` });
  },
  callPhone() {
    const phone = this.data.page && this.data.page.contactConfig && this.data.page.contactConfig.phone;
    if (!phone) return;
    wx.makePhoneCall({ phoneNumber: phone });
  },
  copyWechat() {
    const wechat = this.data.page && this.data.page.contactConfig && this.data.page.contactConfig.wechat;
    if (!wechat) return;
    wx.setClipboardData({ data: wechat });
  },
  onShareAppMessage() {
    const page = this.data.page || {};
    return {
      title: page.shareTitle || page.name || "资料展示页",
      path: `/pages/showcase-view/index?id=${this.data.id}`,
      imageUrl: page.bannerUrl || ""
    };
  }
});
