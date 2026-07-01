const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { getModeConfig, readWorkspaceMode, saveWorkspaceMode } = require("../../utils/workspace-mode");

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

function workspaceModeForCardType(cardType) {
  const prompt = BUSINESS_PROMPTS[cardType] || {};
  return prompt.workspaceMode || "notes";
}

function autoTitle(text) {
  const firstLine = String(text || "").split(/\n/).map((item) => item.trim()).find(Boolean) || "随手记录";
  return firstLine.slice(0, 30);
}

Page({
  data: {
    user: null,
    inputText: "",
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
    propertyBatchCreating: false
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user, inputFocused: false });
    setTimeout(() => {
      this.setData({ inputFocused: true });
    }, 120);
  },
  onUnload() {
    if (this.savedBarTimer) clearTimeout(this.savedBarTimer);
  },
  handleInput(event) {
    this.setData({ inputText: event.detail.value, savedBarVisible: false });
  },
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
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if (saving) return;
    if (!rawText) {
      wx.showToast({ title: "先写点内容", icon: "none" });
      return;
    }
    this.setData({ saving: true });
    wx.showLoading({ title: "保存中" });
    try {
      const textPrompt = businessPromptForText(rawText);
      if (textPrompt && textPrompt.cardType === "property_listing") {
        const parsed = await api.parsePropertyBatch({
          ownerUserId: user.id,
          rawText
        });
        const batchData = parsed.data || {};
        if ((batchData.detectedCount || 0) > 1) {
          wx.hideLoading();
          this.showPropertyBatch(batchData, rawText);
          return;
        }
      }
      const res = await api.createQuickNoteCapture({
        ownerUserId: user.id,
        rawText,
        title: autoTitle(rawText)
      });
      wx.hideLoading();
      const note = res.data || {};
      this.setData({ inputText: "", inputFocused: true });
      const businessPrompt = businessPromptForNote(note, rawText);
      if (businessPrompt) {
        this.showBusinessPrompt(note, businessPrompt);
        return;
      }
      this.showSavedBar(note, "已保存");
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
        inputFocused: true,
        propertyBatchRawText: "",
        propertyBatchCandidates: [],
        propertyBatchCount: 0,
        propertyBatchSelectedCount: 0,
        propertyBatchPrivacyText: ""
      });
      this.showSavedBar(note, "已按普通资料保存");
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || error.errMsg || "保存失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  showBusinessPrompt(note, prompt) {
    const userId = this.data.user && this.data.user.id;
    const currentMode = readWorkspaceMode(userId) || "notes";
    const targetMode = prompt.workspaceMode || workspaceModeForCardType(prompt.cardType);
    const targetModeConfig = getModeConfig(targetMode);
    const currentModeConfig = getModeConfig(currentMode);
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
      businessPromptMode: prompt.mode,
      businessPromptWorkspaceMode: targetModeConfig.key,
      businessPromptWorkspaceName: targetModeConfig.name,
      businessPromptCurrentWorkspaceName: currentModeConfig.name
    });
  },
  handleWorkspaceSwitch() {
    const userId = this.data.user && this.data.user.id;
    const mode = this.data.businessPromptWorkspaceMode || workspaceModeForCardType(this.data.businessPromptCardType);
    const modeConfig = saveWorkspaceMode(mode, userId);
    const noteId = this.data.businessPromptNoteId;
    this.setData({ businessPromptVisible: false });
    wx.showToast({ title: `已切到${modeConfig.shortName || modeConfig.name}`, icon: "none" });
    this.showSavedBar({ id: noteId }, "资料已保存，工作台已切换");
  },
  handleWorkspaceStay() {
    const noteId = this.data.businessPromptNoteId;
    const name = this.data.businessPromptCurrentWorkspaceName || "当前工作台";
    this.setData({ businessPromptVisible: false });
    wx.showToast({ title: `继续使用${name}`, icon: "none" });
    this.showSavedBar({ id: noteId }, "已保存到当前工作台");
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
      wx.navigateTo({ url: `/pages/note-edit/index?id=${noteId}` });
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
    wx.navigateTo({ url: `/pages/note-edit/index?id=${this.data.savedNoteId}` });
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
          wx.navigateTo({ url: "/pages/business-card-studio/index" });
          return;
        }
        if (tapIndex === 3) {
          wx.navigateTo({ url: "/pages/service-offer-studio/index" });
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
        wx.navigateTo({ url: `/pages/note-edit/index?id=${note.id}` });
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
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if (ocrUploading) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      success: ({ tempFiles = [] }) => {
        const file = tempFiles[0];
        if (!file || !file.tempFilePath) return;
        this.uploadImageNote(file.tempFilePath);
      }
    });
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
        this.showSavedBar(note, "图片已保存");
      }
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || error.errMsg || "保存失败", icon: "none" });
    } finally {
      this.setData({ ocrUploading: false });
    }
  }
});
