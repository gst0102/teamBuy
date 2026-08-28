const api = require("../../../services/api");
const { getCurrentUser } = require("../../../utils/dashboard");
const { editorPathForCardType } = require("../../../utils/resource-navigation");
const { buildContactCandidates, normalizePhoneList, removePhoneFromFields, unresolvedContactCandidates } = require("../../../utils/contact-review");

const SYSTEM_PLACEHOLDERS = new Set([
  "未命名服务方案", "未命名服务", "手动创建，可继续补充内容。",
  "补充服务内容和预约方式后即可发给客户", "让客户快速理解价值"
]);

function text(value) { return String(value == null ? "" : value).trim(); }
function contentValue(value) { const result = text(value); return SYSTEM_PLACEHOLDERS.has(result) ? "" : result; }
function images(media = []) { return media.filter((item) => item && item.type === "image"); }
function files(media = []) { return media.filter((item) => item && item.type !== "image"); }

function serviceContactTextValues(structuredData = {}) {
  return [
    structuredData.serviceName,
    structuredData.headline,
    structuredData.detailText,
    structuredData.serviceScope,
    structuredData.pricingOrTerms
  ];
}

function privateContactPhones(config = {}) {
  const privateData = config.privateData && typeof config.privateData === "object" ? config.privateData : {};
  return normalizePhoneList(privateData.contactPhones || []);
}

function withContactStatus(candidate, status) {
  return {
    ...candidate,
    status,
    statusLabel: status === "public" ? "公开电话" : status === "private" ? "仅自己可见" : "待处理"
  };
}

function buildContentBlocks(body, media = []) {
  const blocks = [];
  const textBody = text(body);
  if (textBody) blocks.push({ id: "service_detail_text", type: "text", text: textBody, sortOrder: 0 });
  media
    .filter((item) => item && item.url && ["image", "pdf", "link"].includes(item.type))
    .forEach((item, index) => blocks.push({
      ...item,
      id: item.id || `service_${item.type}_${index}`,
      mediaId: item.mediaId || item.id || "",
      sortOrder: blocks.length
    }));
  return blocks;
}

function migrateServiceData(source = {}, note = {}) {
  const hasNewDetail = Object.prototype.hasOwnProperty.call(source, "detailText");
  const legacyDetail = [
    source.detailText, source.serviceContent, source.targetAudience,
    source.serviceProcess, source.caseHighlights, source.appointmentNote
  ].map(contentValue).filter(Boolean);
  return {
    serviceName: contentValue(source.serviceName || note.title),
    headline: contentValue(source.headline || source.serviceSummary || note.summary),
    detailText: Array.from(new Set(legacyDetail.length ? legacyDetail : (hasNewDetail ? [] : [contentValue(note.body)]))).filter(Boolean).join("\n\n"),
    serviceScope: contentValue(source.serviceScope || source.serviceArea),
    pricingOrTerms: contentValue(source.pricingOrTerms || source.cooperationTerms || source.pricingNote),
    primaryAction: "consult"
  };
}

Page({
  data: {
    noteId: "", user: null, loading: true, saving: false, uploading: false, saveStatus: "",
    form: { title: "", summary: "", body: "", coverUrl: "", media: [], categoryIds: [], visibilityConfig: {} },
    structuredData: {}, contactCandidates: [], reviewContacts: false, imageMedia: [], fileMedia: [], detailCount: 0,
    previewTitle: "填写服务/合作名称", previewHeadline: "填写一句话介绍",
    previewIdentity: "发布者身份读取自“我的”", openOther: true,
    linkDraft: { title: "", url: "" }, showLinkForm: false
  },
  onLoad(options = {}) { this.setData({ noteId: options.id || "", reviewContacts: options.review === "contacts" }); },
  onShow() {
    const user = getCurrentUser();
    if (!user) { wx.reLaunch({ url: "/pages/login/index" }); return; }
    this.setData({ user });
    if (this.data.noteId) this.loadNote(); else this.createDraft();
  },
  async createDraft() {
    if (this.creatingDraft) return;
    this.creatingDraft = true;
    try {
      const res = await api.createManualNoteDraft({ ownerUserId: this.data.user.id, cardType: "service_offer", inputMode: "blank", rawText: "", title: "" });
      this.setData({ noteId: res.data.id }); this.applyNote(res.data || {});
    } catch (error) { wx.showToast({ title: error.detail || "创建失败", icon: "none" }); }
    finally { this.creatingDraft = false; }
  },
  async loadNote() {
    try {
      const res = await api.fetchNote(this.data.noteId, this.data.user.id);
      const note = res.data || {};
      const cardType = ((note.visibilityConfig || {}).cardType || "text_note");
      if (cardType !== "service_offer") { wx.redirectTo({ url: editorPathForCardType(cardType, this.data.noteId) }); return; }
      this.applyNote(note);
    } catch (error) { wx.showToast({ title: error.detail || "加载失败", icon: "none" }); }
  },
  applyNote(note) {
    const config = note.visibilityConfig || {};
    const structuredData = migrateServiceData(config.structuredData || {}, note);
    const form = { ...this.data.form, ...note, title: contentValue(note.title), summary: contentValue(note.summary), body: contentValue(note.body), media: note.media || [], visibilityConfig: config };
    const contactCandidates = buildContactCandidates(serviceContactTextValues(structuredData), {
      publicPhone: note.phone,
      privatePhones: privateContactPhones(config),
      previous: this.data.contactCandidates
    });
    this.setData({ form, structuredData, contactCandidates, saveStatus: "已保存", loading: false }, () => {
      this.refreshView();
      if (this.data.reviewContacts && contactCandidates.length) this.focusContactReview();
    });
  },
  refreshView() {
    const profile = ((this.data.user || {}).salesProfile || {});
    const name = profile.displayName || (this.data.user || {}).nickname || "发布者";
    const role = profile.jobTitle || profile.company || "";
    this.setData({
      imageMedia: images(this.data.form.media), fileMedia: files(this.data.form.media),
      detailCount: text(this.data.structuredData.detailText).length,
      previewTitle: text(this.data.structuredData.serviceName) || "填写服务/合作名称",
      previewHeadline: text(this.data.structuredData.headline) || "填写一句话介绍",
      previewIdentity: [name, role].filter(Boolean).join(" · ")
    });
  },
  markDirty() { if (this.data.saveStatus !== "未保存") this.setData({ saveStatus: "未保存" }); },
  handleInput(event) { this.setData({ [`structuredData.${event.currentTarget.dataset.key}`]: event.detail.value }, () => { this.markDirty(); this.refreshView(); this.refreshContactCandidates(); }); },
  refreshContactCandidates() {
    const config = this.data.form.visibilityConfig || {};
    const contactCandidates = buildContactCandidates(serviceContactTextValues(this.data.structuredData || {}), {
      publicPhone: this.data.form.phone,
      privatePhones: privateContactPhones(config),
      previous: this.data.contactCandidates
    });
    this.setData({ contactCandidates });
    return contactCandidates;
  },
  focusContactReview() {
    setTimeout(() => {
      if (!wx.createSelectorQuery) return;
      wx.createSelectorQuery().select("#contact-review").boundingClientRect().selectViewport().scrollOffset().exec((result) => {
        const rect = result && result[0];
        const viewport = result && result[1];
        if (!rect) return;
        wx.pageScrollTo({ scrollTop: Math.max(0, Number(rect.top || 0) + Number((viewport && viewport.scrollTop) || 0) - 100), duration: 260 });
      });
    }, 120);
  },
  handleContactDecision(event) {
    const phone = String(event.currentTarget.dataset.phone || "");
    const decision = String(event.currentTarget.dataset.decision || "");
    if (!phone || !["public", "private", "remove"].includes(decision)) return;
    const currentConfig = this.data.form.visibilityConfig || {};
    const privateData = { ...(currentConfig.privateData || {}) };
    let structuredData = this.data.structuredData || {};
    let publicPhone = this.data.form.phone || "";
    let privatePhones = privateContactPhones(currentConfig);
    let candidates = (this.data.contactCandidates || []).map((item) => item);
    if (decision === "public") {
      publicPhone = phone;
      privatePhones = privatePhones.filter((item) => item !== phone);
      candidates = candidates.map((item) => withContactStatus(item, item.phone === phone ? "public" : item.status === "public" ? "pending" : item.status));
    } else {
      structuredData = removePhoneFromFields(structuredData, phone);
      publicPhone = publicPhone === phone ? "" : publicPhone;
      privatePhones = privatePhones.filter((item) => item !== phone);
      if (decision === "private") privatePhones.push(phone);
      candidates = candidates
        .filter((item) => item.phone !== phone)
        .map((item) => withContactStatus(item, item.status));
    }
    if (privatePhones.length) privateData.contactPhones = Array.from(new Set(privatePhones));
    else delete privateData.contactPhones;
    const nextConfig = { ...currentConfig, privateData };
    const nextForm = { ...this.data.form, phone: publicPhone, visibilityConfig: nextConfig };
    this.setData({ structuredData, form: nextForm, contactCandidates: candidates }, () => {
      this.markDirty();
      this.refreshView();
      this.refreshContactCandidates();
      wx.showToast({
        title: decision === "public" ? "已设为公开电话" : decision === "private" ? "已移入私密资料" : "已从正文移除",
        icon: "success"
      });
    });
  },
  handleToggleOther() { this.setData({ openOther: !this.data.openOther }); },
  handleLinkInput(event) { this.setData({ [`linkDraft.${event.currentTarget.dataset.key}`]: event.detail.value }); },
  handleChooseAttachment() {
    wx.showActionSheet({ itemList: ["添加图片", "添加 PDF", "添加外部链接"], success: ({ tapIndex }) => {
      if (tapIndex === 0) this.chooseImages(); else if (tapIndex === 1) this.choosePdf(); else this.setData({ showLinkForm: true });
    } });
  },
  chooseImages() {
    const count = Math.min(9 - this.data.imageMedia.length, 12 - this.data.form.media.length);
    if (count <= 0) { wx.showToast({ title: "图片或附件数量已达上限", icon: "none" }); return; }
    const success = ({ tempFiles = [] }) => this.uploadFiles(tempFiles.map((item) => item.tempFilePath || item.path).filter(Boolean), "image");
    if (typeof wx.chooseImage === "function") { wx.chooseImage({ count, sourceType: ["album", "camera"], success }); return; }
    wx.chooseMedia({ count, mediaType: ["image"], sourceType: ["album", "camera"], success });
  },
  choosePdf() {
    const count = Math.min(5 - this.data.fileMedia.filter((item) => item.type === "pdf").length, 12 - this.data.form.media.length);
    if (count <= 0) { wx.showToast({ title: "PDF 或附件数量已达上限", icon: "none" }); return; }
    wx.chooseMessageFile({ count, type: "file", extension: ["pdf"], success: ({ tempFiles = [] }) => this.uploadFiles(tempFiles.map((item) => item.path).filter(Boolean), "pdf") });
  },
  async uploadFiles(paths, type) {
    if (!paths.length || this.data.uploading) return;
    this.setData({ uploading: true });
    try {
      const uploaded = await Promise.all(paths.map((filePath) => api.uploadAsset({ filePath, mediaType: type, ownerUserId: this.data.user.id })));
      const additions = uploaded.map((item, index) => ({ ...item, id: item.id || `${type}_${Date.now()}_${index}`, type }));
      const media = [...this.data.form.media, ...additions].map((item, index) => ({ ...item, sortOrder: index }));
      const firstImage = images(media)[0];
      this.setData({ "form.media": media, "form.coverUrl": (firstImage && firstImage.url) || "" }, () => { this.markDirty(); this.refreshView(); });
    } catch (error) { wx.showToast({ title: error.detail || "上传失败", icon: "none" }); }
    finally { this.setData({ uploading: false }); }
  },
  addLink() {
    const url = text(this.data.linkDraft.url);
    if (!/^https:\/\//i.test(url)) { wx.showToast({ title: "链接必须以 https:// 开头", icon: "none" }); return; }
    if (this.data.form.media.length >= 12 || this.data.fileMedia.filter((item) => item.type === "link").length >= 5) { wx.showToast({ title: "链接或附件数量已达上限", icon: "none" }); return; }
    const media = [...this.data.form.media, { id: `link_${Date.now()}`, type: "link", title: text(this.data.linkDraft.title) || url, url, status: "ready" }].map((item, index) => ({ ...item, sortOrder: index }));
    this.setData({ "form.media": media, linkDraft: { title: "", url: "" }, showLinkForm: false }, () => { this.markDirty(); this.refreshView(); });
  },
  handlePreviewAttachment(event) {
    const item = this.data.form.media[Number(event.currentTarget.dataset.index)]; if (!item) return;
    if (item.type === "image") { const urls = this.data.imageMedia.map((row) => row.displayUrl || row.url); wx.previewImage({ current: item.displayUrl || item.url, urls }); return; }
    if (item.type === "link") { wx.setClipboardData({ data: item.url, success: () => wx.showToast({ title: "链接已复制", icon: "success" }) }); return; }
    wx.downloadFile({ url: item.url, success: ({ tempFilePath }) => wx.openDocument({ filePath: tempFilePath, fileType: "pdf", showMenu: true }), fail: () => wx.showToast({ title: "PDF 打开失败", icon: "none" }) });
  },
  handlePreviewCover() {
    const firstImage = this.data.imageMedia[0];
    if (!firstImage) return;
    wx.previewImage({
      current: firstImage.displayUrl || firstImage.url,
      urls: this.data.imageMedia.map((item) => item.displayUrl || item.url).filter(Boolean)
    });
  },
  handleRemoveAttachment(event) {
    const index = Number(event.currentTarget.dataset.index);
    const media = this.data.form.media.filter((_, itemIndex) => itemIndex !== index).map((item, itemIndex) => ({ ...item, sortOrder: itemIndex }));
    const firstImage = images(media)[0];
    this.setData({ "form.media": media, "form.coverUrl": (firstImage && firstImage.url) || "" }, () => { this.markDirty(); this.refreshView(); });
  },
  async handleSave(showToast = true) {
    if (this.data.saving) return false;
    const serviceName = text(this.data.structuredData.serviceName);
    if (!serviceName) { wx.showToast({ title: "请填写服务/合作名称", icon: "none" }); return false; }
    this.setData({ saving: true });
    try {
      const structuredData = { ...this.data.structuredData, serviceName, primaryAction: "consult" };
      const body = text(structuredData.detailText) || text(structuredData.headline) || serviceName;
      const candidates = this.data.contactCandidates || [];
      const publicCandidate = candidates.find((item) => item.status === "public");
      const privatePhones = Array.from(new Set([
        ...privateContactPhones(this.data.form.visibilityConfig || {}),
        ...candidates.filter((item) => item.status === "private").map((item) => item.phone)
      ]));
      const privateData = { ...((this.data.form.visibilityConfig || {}).privateData || {}) };
      if (privatePhones.length) privateData.contactPhones = privatePhones;
      else delete privateData.contactPhones;
      const config = {
        ...(this.data.form.visibilityConfig || {}), schemaVersion: 2, cardType: "service_offer", cardState: "editing",
        structuredData, privateData, displayConfig: {},
        conversionConfig: {
          ...(((this.data.form.visibilityConfig || {}).conversionConfig) || {}),
          showContactPhone: true, enableLightScrm: true, collectLeads: true,
          enablePrivateConsultation: true, enableAppointment: false
        }
      };
      await api.updateNote(this.data.noteId, {
        ownerUserId: this.data.user.id, title: serviceName, summary: text(structuredData.headline),
        body, contentBlocks: buildContentBlocks(body, this.data.form.media),
        coverUrl: (this.data.imageMedia[0] && this.data.imageMedia[0].url) || null,
        media: this.data.form.media, categoryIds: this.data.form.categoryIds || [], phone: (publicCandidate && publicCandidate.phone) || this.data.form.phone || null, locationText: null, visibilityConfig: config
      });
      this.setData({ form: { ...this.data.form, phone: (publicCandidate && publicCandidate.phone) || this.data.form.phone || "", visibilityConfig: config }, structuredData, saveStatus: "已保存" });
      if (showToast) {
        const pendingCount = unresolvedContactCandidates(candidates).length;
        wx.showToast({ title: pendingCount ? `已保存，还有${pendingCount}个号码待处理` : "已保存", icon: pendingCount ? "none" : "success" });
      }
      return true;
    } catch (error) { wx.showToast({ title: error.detail || error.message || "保存失败", icon: "none" }); return false; }
    finally { this.setData({ saving: false }); }
  },
  async handlePreview() { const saved = await this.handleSave(false); if (saved) wx.navigateTo({ url: `/pages/note-preview/index?id=${this.data.noteId}&preview=1` }); },
  async handlePublish() {
    const pending = unresolvedContactCandidates(this.data.contactCandidates || []);
    if (pending.length) {
      this.focusContactReview();
      wx.showToast({ title: `请先处理${pending.length}个手机号`, icon: "none" });
      return;
    }
    const saved = await this.handleSave(false);
    if (!saved) return;
    this.setData({ saving: true });
    try {
      await api.publishNote(this.data.noteId, this.data.user.id);
      this.setData({ saveStatus: "可发客户" });
      wx.showToast({ title: "已准备好，可从资料卡发客户", icon: "success" });
      setTimeout(() => wx.switchTab({ url: "/pages/library/index" }), 450);
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "发客户失败，请先完善资料", icon: "none" });
    } finally { this.setData({ saving: false }); }
  },
  handleDelete() {
    wx.showModal({ title: "删除资料", content: "删除后无法恢复，确定继续吗？", confirmText: "删除", confirmColor: "#d9485f", success: async ({ confirm }) => {
      if (!confirm) return;
      try { await api.deleteNote(this.data.noteId, this.data.user.id); wx.showToast({ title: "已删除", icon: "success" }); setTimeout(() => wx.navigateBack(), 400); }
      catch (error) { wx.showToast({ title: error.detail || "删除失败", icon: "none" }); }
    } });
  }
});
