const api = require("../../../services/api");
const { getCurrentUser } = require("../../../utils/dashboard");
const { saveWorkspaceMode } = require("../../../utils/workspace-mode");
const { navigateToNoteEditor } = require("../../../utils/resource-navigation");

const BUSINESS_PROMPTS = {
  property_listing: {
    icon: "房",
    title: "已帮你整理成房源草稿",
    content: "去补图片、电话和展示按钮，马上就能发给客户。",
    confirmText: "去完善房源",
    candidateTitle: "这条像房源资料",
    candidateContent: "可以整理成房源草稿，再补图片、电话和展示按钮。",
    workspaceMode: "property"
  },
  groupbuy_product: {
    icon: "购",
    title: "已帮你整理成商品草稿",
    content: "去补规格、取货方式和接龙按钮，马上就能发给客户下单。",
    confirmText: "去完善商品",
    candidateTitle: "这条像商品团购",
    candidateContent: "可以整理成商品草稿，再补规格、取货方式和接龙按钮。",
    workspaceMode: "groupbuy"
  },
  business_card: {
    icon: "名",
    title: "已帮你整理成名片资料",
    content: "可以放到服务工作台，继续制作名片和跟进咨询客户。",
    confirmText: "去完善名片",
    candidateTitle: "这条像服务名片资料",
    candidateContent: "可以放到服务工作台，继续制作名片和跟进咨询客户。",
    workspaceMode: "service"
  },
  service_offer: {
    icon: "服",
    title: "已帮你整理成服务方案",
    content: "可以放到服务工作台，继续制作服务页和跟进咨询客户。",
    confirmText: "去完善方案",
    candidateTitle: "这条像服务方案资料",
    candidateContent: "可以放到服务工作台，继续制作服务页和跟进咨询客户。",
    workspaceMode: "service"
  }
};

function noteCardType(note) {
  const config = (note && note.visibilityConfig) || {};
  return config.cardType || "text_note";
}

function isHighConfidenceBusinessNote(note) {
  const config = (note && note.visibilityConfig) || {};
  const confidence = config.recognitionConfidence || {};
  const cardType = noteCardType(note);
  return Boolean(BUSINESS_PROMPTS[cardType]) && confidence.level === "high";
}

function firstBusinessSuggestion(note) {
  const config = (note && note.visibilityConfig) || {};
  const suggestions = Array.isArray(config.typeSuggestions) ? config.typeSuggestions : [];
  return suggestions.find((item) => item && BUSINESS_PROMPTS[item.cardType]);
}

function scoreTextSignals(text, patterns) {
  return patterns.reduce((score, pattern) => score + (pattern.test(text) ? 1 : 0), 0);
}

function businessPromptForText(text) {
  const value = String(text || "");
  if (!value.trim()) return null;
  const propertyScore = scoreTextSignals(value, [
    /房源|房产|小区|楼盘|郡府|和府|花园|家园|公馆|苑|带看|看房/,
    /户型|[一二三四五六七八九十两0-9]+室|[一二三四五六七八九十两0-9]+厅|[一二三四五六七八九十两0-9]+居室|南北通透|独梯独户/,
    /面积|平米|平方|㎡|m²|[0-9]+(?:\.[0-9]+)?\s*平/i,
    /总价|售价|租金|月租|首付|均价|[0-9]+(?:\.[0-9]+)?\s*万/,
    /楼层|小高层|朝向|毛坯|精装|装修|阳台|阴台|地铁|学区|小学|中学|入学/,
    /1[3-9]\d{9}/
  ]);
  const groupbuyScore = scoreTextSignals(value, [
    /团购|接龙|下单|拼团|预订|预定/,
    /商品|好物|现货|到货|库存|限量/,
    /规格|口味|套餐|单价|价格|售价/,
    /自提|配送|发货|取货|包邮/,
    /¥|￥|[0-9]+(\.[0-9]+)?元|[0-9]+斤|[0-9]+箱|[0-9]+份/
  ]);
  const cardType = propertyScore >= 2 && propertyScore >= groupbuyScore
    ? "property_listing"
    : groupbuyScore >= 2
      ? "groupbuy_product"
      : "";
  if (!cardType) return null;
  const prompt = BUSINESS_PROMPTS[cardType];
  return {
    ...prompt,
    cardType,
    mode: "suggested",
    title: prompt.candidateTitle,
    content: prompt.candidateContent,
    confirmText: cardType === "property_listing" ? "整理成房源" : "整理成商品"
  };
}

function businessPromptForNote(note, rawText) {
  const cardType = noteCardType(note);
  if (isHighConfidenceBusinessNote(note)) {
    const prompt = BUSINESS_PROMPTS[cardType];
    return {
      ...prompt,
      cardType,
      mode: "confirmed",
      title: prompt.title,
      content: prompt.content,
      confirmText: prompt.confirmText
    };
  }
  const suggestion = firstBusinessSuggestion(note);
  if (!suggestion) return businessPromptForText(rawText);
  const prompt = BUSINESS_PROMPTS[suggestion.cardType];
  return {
    ...prompt,
    cardType: suggestion.cardType,
    mode: "suggested",
    title: prompt.candidateTitle,
    content: prompt.candidateContent,
    confirmText: suggestion.cardType === "property_listing" ? "整理成房源" : "整理成商品"
  };
}

function autoTitle(text) {
  const firstLine = String(text || "").split(/\n/).map((item) => item.trim()).find(Boolean) || "随手记录";
  return firstLine.slice(0, 30);
}

function buildContentBlocks(rawText, media = []) {
  const blocks = [];
  const text = String(rawText || "").trim();
  if (text) {
    blocks.push({
      id: `block_text_${Date.now()}`,
      type: "text",
      text,
      sortOrder: 0
    });
  }
  (media || []).forEach((item, index) => {
    if (!item || !item.url || !["image", "pdf", "link"].includes(item.type)) return;
    blocks.push({
      ...item,
      id: item.id || `block_${item.type}_${Date.now()}_${index}`,
      mediaId: item.mediaId || item.id || "",
      sortOrder: blocks.length
    });
  });
  return blocks;
}

function redirectToLogin() {
  wx.redirectTo({
    url: `/pages/login/index?returnUrl=${encodeURIComponent("/subpackages/workbench/resource-create/index")}`
  });
}

Page({
  data: {
    user: null,
    sourceMode: "text",
    inputPlaceholder: "粘贴房源、商品、服务介绍、公众号内容或日常资料…",
    inputText: "",
    inputLength: 0,
    pendingMedia: [],
    showLinkForm: false,
    linkDraft: { title: "", url: "" },
    inputFocused: false,
    saving: false,
    ocrUploading: false,
    savedBarVisible: false,
    savedNoteId: "",
    savedText: "已保存",
    businessPromptVisible: false,
    businessPromptTitle: "",
    businessPromptContent: "",
    businessPromptConfirmText: "",
    businessPromptNoteId: "",
    businessPromptIcon: "",
    businessPromptCardType: "",
    businessPromptMode: "confirmed",
    businessPromptWorkspaceMode: "",
    businessPromptWorkspaceName: "",
    businessPromptCurrentWorkspaceName: "",
    propertyBatchVisible: false,
    propertyBatchRawText: "",
    propertyBatchCandidates: [],
    propertyBatchCount: 0,
    propertyBatchSelectedCount: 0,
    propertyBatchPrivacyText: "",
    propertyBatchCreating: false,
    captureIdempotencyKey: ""
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      redirectToLogin();
      return;
    }
    this.setData({ user, inputFocused: false });
  },
  onUnload() {
    if (this.savedBarTimer) clearTimeout(this.savedBarTimer);
  },
  handleInput(event) {
    const inputText = event.detail.value || "";
    this.setData({ inputText, inputLength: inputText.length, savedBarVisible: false });
  },
  handleSourceSelect(event) {
    const mode = event.currentTarget.dataset.mode || "text";
    if (mode === "image") {
      this.handleImageUpload();
      return;
    }
    if (mode === "pdf") {
      this.handlePdfUpload();
      return;
    }
    if (mode === "link") {
      this.setData({ showLinkForm: true, linkDraft: { title: "", url: "" } });
      return;
    }
    this.setData({
      sourceMode: mode,
      inputFocused: true,
      inputPlaceholder: mode === "link"
        ? "粘贴以 https:// 开头的文章或网页链接"
        : "粘贴房源、商品、服务介绍、公众号内容或日常资料…"
    });
  },
  handleSceneCreate(event) {
    const cardType = event.currentTarget.dataset.type;
    if (!cardType) return;
    if (cardType === "business_card") {
      wx.navigateTo({ url: "/subpackages/workbench/business-card-studio/index" });
      return;
    }
    this.createBlankDraft(cardType);
  },
  handleRemovePendingImage(event) {
    const index = Number(event.currentTarget.dataset.index);
    this.setData({ pendingMedia: this.data.pendingMedia.filter((_, itemIndex) => itemIndex !== index) });
  },
  handleLinkInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`linkDraft.${key}`]: event.detail.value || "" });
  },
  handleCloseLinkForm() {
    this.setData({ showLinkForm: false });
  },
  handleAddLink() {
    const url = String(this.data.linkDraft.url || "").trim();
    const title = String(this.data.linkDraft.title || "").trim();
    if (!/^https:\/\//i.test(url)) {
      wx.showToast({ title: "请粘贴 https:// 开头的链接", icon: "none" });
      return;
    }
    if (this.data.pendingMedia.some((item) => item.type === "link" && item.url === url)) {
      wx.showToast({ title: "这个链接已经添加", icon: "none" });
      return;
    }
    const pendingMedia = [...this.data.pendingMedia, {
      id: `link_${Date.now()}`,
      type: "link",
      url,
      title: title || url,
      source: "manual",
      status: "ready",
      sortOrder: this.data.pendingMedia.length
    }];
    this.setData({ pendingMedia, sourceMode: "text", showLinkForm: false, linkDraft: { title: "", url: "" } });
  },
  noop() {},
  appendText(value) {
    const current = this.data.inputText || "";
    const prefix = current && !current.endsWith("\n") ? "\n" : "";
    this.setData({
      inputText: `${current}${prefix}${value}`,
      inputFocused: true
    });
  },
  handleInsertTag() {
    const current = this.data.inputText || "";
    const prefix = current && !current.endsWith("\n") ? "\n" : "";
    this.setData({
      inputText: `${current}${prefix}#`,
      inputFocused: true
    });
  },
  handleInsertList() {
    this.appendText("- ");
  },
  async handleSubmit() {
    const { user, inputText, saving } = this.data;
    const rawText = inputText.trim();
    if (!user) {
      redirectToLogin();
      return;
    }
    if (saving) return;
    if (!rawText && !this.data.pendingMedia.length) {
      wx.showToast({ title: "先添加内容", icon: "none" });
      return;
    }
    this.setData({ saving: true });
    wx.showLoading({ title: "保存中" });
    try {
      const idempotencyKey = this.data.captureIdempotencyKey || `capture_${user.id}_${Date.now()}`;
      this.setData({ captureIdempotencyKey: idempotencyKey });
      const onlyLink = !rawText && this.data.pendingMedia.length && this.data.pendingMedia.every((item) => item.type === "link");
      const primaryLink = onlyLink ? this.data.pendingMedia[0] : null;
      const pendingMedia = this.data.pendingMedia.map((item, index) => ({ ...item, sortOrder: index }));
      const contentBlocks = buildContentBlocks(rawText, pendingMedia);
      const res = rawText
        ? await api.createQuickNoteCapture({ ownerUserId: user.id, rawText, title: autoTitle(rawText), idempotencyKey })
        : onlyLink
          ? await api.createLinkNoteCapture({
              ownerUserId: user.id,
              url: primaryLink.url,
              title: primaryLink.title === primaryLink.url ? "" : primaryLink.title,
              idempotencyKey
            })
          : await api.createManualNoteDraft({ ownerUserId: user.id, cardType: "text_note", inputMode: "blank", rawText: "", title: "图片资料", idempotencyKey });
      let note = res.data || {};
      if (note.id) {
        const saved = await api.updateNote(note.id, {
          ownerUserId: user.id,
          title: note.title || autoTitle(rawText || "图片资料"),
          summary: rawText ? (note.summary || rawText.slice(0, 120)) : (note.summary || (onlyLink ? "" : "图片资料")),
          body: rawText || (onlyLink ? note.body || "" : ""),
          contentBlocks,
          coverUrl: (pendingMedia.find((item) => item.type === "image") || {}).url || note.coverUrl || "",
          media: pendingMedia.length ? pendingMedia : (note.media || []),
          categoryIds: note.categoryIds || [],
          phone: note.phone || "",
          locationText: note.locationText || "",
          visibilityConfig: note.visibilityConfig || {}
        });
        note = saved.data || note;
      }
      if (!note.id) throw new Error("资料创建失败，请重试");
      const published = await api.publishNote(note.id, user.id, note.revision);
      note = published.data || note;
      this.setData({
        inputText: "",
        inputLength: 0,
        pendingMedia: [],
        inputFocused: true,
        sourceMode: "text",
        inputPlaceholder: "粘贴房源、商品、服务介绍、公众号内容或日常资料…",
        captureIdempotencyKey: ""
      });
      wx.hideLoading();
      wx.showToast({ title: "已发布，正在打开客户页", icon: "success" });
      wx.redirectTo({ url: `/pages/note-preview/index?id=${encodeURIComponent(note.id)}` });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || error.errMsg || "保存失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  showPropertyBatch(batchData, rawText) {
    const candidates = (batchData.candidates || []).map((item, index) => ({
      ...item,
      selected: item.selected !== false,
      displayIndex: index + 1,
      publicTagsText: (item.publicTags || []).join(" / "),
      privateTagsText: (item.privateTags || []).join(" / ")
    }));
    const privacy = batchData.privacySummary || {};
    const privateBits = [];
    if ((privacy.upstreamPhones || []).length) privateBits.push(`上游电话${privacy.upstreamPhones.length}个`);
    if (privacy.commission) privateBits.push(privacy.commission);
    if (privacy.upstreamWechat) privateBits.push("上游微信");
    this.setData({
      propertyBatchVisible: true,
      propertyBatchRawText: rawText,
      propertyBatchCandidates: candidates,
      propertyBatchCount: candidates.length,
      propertyBatchSelectedCount: candidates.filter((item) => item.selected).length,
      propertyBatchPrivacyText: privateBits.length ? privateBits.join("、") : "上游信息",
      businessPromptVisible: false,
      savedBarVisible: false
    });
  },
  togglePropertyCandidate(event) {
    const index = Number(event.currentTarget.dataset.index);
    const candidates = (this.data.propertyBatchCandidates || []).map((item, itemIndex) => (
      itemIndex === index ? { ...item, selected: !item.selected } : item
    ));
    this.setData({
      propertyBatchCandidates: candidates,
      propertyBatchSelectedCount: candidates.filter((item) => item.selected).length
    });
  },
  handlePropertyBatchCancel() {
    this.setData({
      propertyBatchVisible: false,
      propertyBatchRawText: "",
      propertyBatchCandidates: [],
      propertyBatchCount: 0,
      propertyBatchSelectedCount: 0,
      propertyBatchPrivacyText: ""
    });
  },
  async handlePropertyBatchCreate() {
    const { user, propertyBatchRawText, propertyBatchCandidates, propertyBatchCreating } = this.data;
    if (!user || propertyBatchCreating) return;
    const candidates = (propertyBatchCandidates || []).filter((item) => item.selected);
    if (!candidates.length) {
      wx.showToast({ title: "至少选择一套房源", icon: "none" });
      return;
    }
    this.setData({ propertyBatchCreating: true });
    wx.showLoading({ title: "生成中" });
    try {
      const res = await api.createPropertyBatch({
        ownerUserId: user.id,
        rawText: propertyBatchRawText,
        candidates
      });
      wx.hideLoading();
      const data = res.data || {};
      const notes = data.notes || [];
      saveWorkspaceMode("property", user.id);
      this.setData({
        inputText: "",
        inputLength: 0,
        inputFocused: true,
        propertyBatchVisible: false,
        propertyBatchRawText: "",
        propertyBatchCandidates: [],
        propertyBatchCount: 0,
        propertyBatchSelectedCount: 0,
        propertyBatchPrivacyText: ""
      });
      const createdCount = data.createdCount || notes.length;
      const resultText = data.showcaseId ? `已生成${createdCount}张房源卡和合集` : `已生成${createdCount}张房源卡`;
      wx.showToast({ title: resultText, icon: "success" });
      this.showSavedBar(notes[0] || {}, resultText);
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || error.errMsg || "生成失败", icon: "none" });
    } finally {
      this.setData({ propertyBatchCreating: false, saving: false });
    }
  },
  async handlePropertyBatchSaveRaw() {
    const { user, propertyBatchRawText, saving } = this.data;
    if (!user || saving || !propertyBatchRawText) return;
    this.setData({ saving: true, propertyBatchVisible: false });
    wx.showLoading({ title: "保存中" });
    try {
      const res = await api.createQuickNoteCapture({
        ownerUserId: user.id,
        rawText: propertyBatchRawText,
        title: autoTitle(propertyBatchRawText)
      });
      wx.hideLoading();
      const note = res.data || {};
      this.setData({
        inputText: "",
        inputLength: 0,
        inputFocused: true,
        propertyBatchRawText: "",
        propertyBatchCandidates: [],
        propertyBatchCount: 0,
        propertyBatchSelectedCount: 0,
        propertyBatchPrivacyText: ""
      });
      wx.navigateTo({ url: `/subpackages/workbench/link-confirm/index?id=${note.id}` });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || error.errMsg || "保存失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  showBusinessPrompt(note, prompt) {
    this.setData({
      savedNoteId: note.id || "",
      savedBarVisible: false,
      businessPromptVisible: true,
      businessPromptTitle: prompt.title,
      businessPromptContent: prompt.content,
      businessPromptConfirmText: prompt.confirmText,
      businessPromptNoteId: note.id || "",
      businessPromptIcon: prompt.icon,
      businessPromptCardType: prompt.cardType,
      businessPromptMode: prompt.mode
    });
  },
  async handleBusinessConfirm() {
    const noteId = this.data.businessPromptNoteId;
    const cardType = this.data.businessPromptCardType;
    if (!noteId) return;
    if (this.data.businessPromptMode === "suggested" && cardType && this.data.user) {
      wx.showLoading({ title: "整理中" });
      try {
        await api.confirmNoteType(noteId, {
          ownerUserId: this.data.user.id,
          cardType
        });
        wx.hideLoading();
      } catch (error) {
        wx.hideLoading();
        wx.showToast({ title: error.detail || error.errMsg || "整理失败", icon: "none" });
        return;
      }
    }
    this.setData({ businessPromptVisible: false });
    if (noteId) {
      navigateToNoteEditor(noteId);
    }
  },
  handleBusinessCancel() {
    const noteId = this.data.businessPromptNoteId;
    this.setData({ businessPromptVisible: false });
    this.showSavedBar({ id: noteId }, "已保存到笔记库");
  },
  showSavedBar(note, text) {
    if (this.savedBarTimer) clearTimeout(this.savedBarTimer);
    this.setData({
      savedNoteId: note && note.id ? note.id : "",
      savedText: text || "已保存",
      savedBarVisible: true
    });
    this.savedBarTimer = setTimeout(() => {
      this.setData({ savedBarVisible: false });
    }, 5000);
  },
  handleViewSaved() {
    if (!this.data.savedNoteId) return;
    navigateToNoteEditor(this.data.savedNoteId);
  },
  handleMore() {
    wx.showActionSheet({
      itemList: ["空白房源", "空白商品", "电子名片", "服务方案", "图片资料"],
      success: ({ tapIndex }) => {
        if (tapIndex === 0) {
          this.createBlankDraft("property_listing");
          return;
        }
        if (tapIndex === 1) {
          this.createBlankDraft("groupbuy_product");
          return;
        }
        if (tapIndex === 2) {
          wx.navigateTo({ url: "/subpackages/workbench/business-card-studio/index" });
          return;
        }
        if (tapIndex === 3) {
          wx.navigateTo({ url: "/subpackages/workbench/service-offer-studio/index" });
          return;
        }
        this.handleImageUpload();
      }
    });
  },
  async createBlankDraft(cardType) {
    const { user, saving } = this.data;
    if (!user || saving) return;
    this.setData({ saving: true });
    wx.showLoading({ title: "创建中" });
    try {
      const res = await api.createManualNoteDraft({
        ownerUserId: user.id,
        cardType,
        inputMode: "blank",
        rawText: "",
        title: ""
      });
      wx.hideLoading();
      const note = res.data || {};
      if (note.id) {
        navigateToNoteEditor(note);
      }
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || error.errMsg || "创建失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  handleImageUpload() {
    const { user, ocrUploading } = this.data;
    if (!user) {
      redirectToLogin();
      return;
    }
    if (ocrUploading) return;
    if (this.data.pendingMedia.filter((item) => item.type === "image").length >= 9) {
      wx.showToast({ title: "最多添加 9 张图片", icon: "none" });
      return;
    }
    const onSelected = ({ tempFiles = [] }) => {
      const paths = tempFiles.map((file) => file.tempFilePath || file.path).filter(Boolean);
      if (!paths.length) return;
      this.setData({ ocrUploading: true });
      wx.showLoading({ title: "添加中" });
      Promise.all(paths.map((filePath) => api.uploadAsset({ filePath, mediaType: "image", ownerUserId: user.id })))
        .then((items) => {
          const base = this.data.pendingMedia.length;
          const pendingMedia = [...this.data.pendingMedia, ...items.map((item, index) => ({
            ...item,
            id: item.id || `pending_${Date.now()}_${index}`,
            type: item.type || item.mediaType || "image",
            status: item.status || "ready",
            sortOrder: base + index
          }))].slice(0, 12);
          this.setData({ pendingMedia });
          wx.showToast({ title: `已添加 ${items.length} 张`, icon: "success" });
        })
        .catch((error) => wx.showToast({ title: error.detail || error.errMsg || "图片添加失败", icon: "none" }))
        .finally(() => { wx.hideLoading(); this.setData({ ocrUploading: false }); });
    };
    const onChooseFail = (error = {}) => {
      const message = error.errMsg || error.detail || "系统相册没有打开";
      if (String(message).includes("cancel")) return;
      if (/privacy agreement|api scope is not declared/i.test(message)) {
        wx.showModal({
          title: "需要补充隐私声明",
          content: "请在微信小程序后台的用户隐私保护指引中声明“选中的照片或视频信息”，更新后才能选择相册图片。",
          showCancel: false
        });
        return;
      }
      wx.showModal({
        title: "相册没有打开",
        content: message,
        showCancel: false
      });
    };
    const count = 9 - this.data.pendingMedia.filter((item) => item.type === "image").length;
    if (typeof wx.chooseImage === "function") {
      wx.chooseImage({ count, sourceType: ["album", "camera"], success: onSelected, fail: onChooseFail });
      return;
    }
    if (typeof wx.chooseMedia !== "function") {
      onChooseFail({ errMsg: "当前微信版本不支持选择图片" });
      return;
    }
    wx.chooseMedia({
      count,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      success: onSelected,
      fail: onChooseFail
    });
  },
  handlePdfUpload() {
    const { user, ocrUploading } = this.data;
    if (!user) {
      redirectToLogin();
      return;
    }
    if (ocrUploading) return;
    wx.chooseMessageFile({
      count: 1,
      type: "file",
      extension: ["pdf"],
      success: ({ tempFiles = [] }) => {
        const file = tempFiles[0];
        if (!file || !file.path) return;
        this.uploadPdfNote(file);
      }
    });
  },
  async uploadPdfNote(file) {
    const { user } = this.data;
    if (!user || !file || !file.path) return;
    this.setData({ ocrUploading: true });
    wx.showLoading({ title: "创建中" });
    try {
      const asset = await api.uploadAsset({ filePath: file.path, mediaType: "pdf", ownerUserId: user.id });
      const draftRes = await api.createManualNoteDraft({
        ownerUserId: user.id,
        cardType: "text_note",
        inputMode: "blank",
        rawText: "",
        title: String(file.name || "PDF 资料").replace(/\.pdf$/i, "")
      });
      const note = draftRes.data || {};
      const media = [...(note.media || []), {
        id: asset.id,
        type: asset.type || asset.mediaType || "pdf",
        url: asset.url,
        name: asset.name || file.name,
        mimeType: asset.mimeType || asset.contentType || "application/pdf",
        sizeBytes: asset.sizeBytes || file.size,
        source: asset.source || "upload",
        status: asset.status || "ready",
        sortOrder: (note.media || []).length
      }];
      const saved = await api.updateNote(note.id, {
        ownerUserId: user.id,
        title: note.title || String(file.name || "PDF 资料").replace(/\.pdf$/i, ""),
        summary: note.summary || "PDF 资料",
        body: note.body || "PDF 资料",
        coverUrl: note.coverUrl || "",
        media,
        categoryIds: note.categoryIds || [],
        phone: note.phone || "",
        locationText: note.locationText || "",
        contentBlocks: [{
          id: asset.id || `block_pdf_${Date.now()}`,
          type: "pdf",
          mediaId: asset.id || "",
          url: asset.url,
          name: asset.name || file.name,
          title: asset.name || file.name,
          mimeType: asset.mimeType || asset.contentType || "application/pdf",
          sortOrder: 0
        }],
        visibilityConfig: note.visibilityConfig || {}
      });
      const published = await api.publishNote((saved.data || note).id, user.id, (saved.data || note).revision);
      wx.hideLoading();
      wx.showToast({ title: "PDF 已发布", icon: "success" });
      wx.redirectTo({ url: `/pages/note-preview/index?id=${encodeURIComponent((published.data || saved.data || note).id)}` });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || error.errMsg || "PDF 添加失败", icon: "none" });
    } finally {
      this.setData({ ocrUploading: false });
    }
  },
  async uploadImageNote(filePath) {
    const { user } = this.data;
    if (!user || !filePath) return;
    this.setData({ ocrUploading: true });
    wx.showLoading({ title: "保存中" });
    try {
      const result = await api.uploadImageNote({ filePath, ownerUserId: user.id });
      wx.hideLoading();
      const note = result.note || {};
      wx.showToast({ title: "图片已保存", icon: "success" });
      if (note.id) {
        wx.navigateTo({ url: `/subpackages/workbench/link-confirm/index?id=${note.id}` });
      }
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || error.errMsg || "保存失败", icon: "none" });
    } finally {
      this.setData({ ocrUploading: false });
    }
  }
});
