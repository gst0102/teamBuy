const api = require("../../services/api");
const { getCurrentUser, safeAvatarUrl } = require("../../utils/dashboard");
const {
  getShowcaseTemplate,
  getDefaultTemplateId,
  normalizeSceneType,
  normalizeTemplateId,
  templateClass
} = require("../../utils/showcase-templates");
const { buildTitleCoverData } = require("../../utils/title-cover");
const subscription = require("../../services/subscription");
const { getAnonymousVisitorId } = require("../../utils/visitor-identity");


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
    const displayTags = ((item.tags && item.tags.length) ? item.tags : [item.badge || sectionName(item, "cardType")]).slice(0, 4);
    let section = sections.find((row) => row.title === title);
    if (!section) {
      section = { title, items: [] };
      sections.push(section);
    }
    section.items.push({
      ...item,
      titleCover: buildTitleCoverData(item.title || item.badge || "资料", item.badge || sectionName(item, "cardType")),
      tagText: (item.tags || []).slice(0, 3).join(" · "),
      badge: item.badge || sectionName(item, "cardType"),
      primaryText: item.primaryText || item.summary || "",
      secondaryText: item.secondaryText || "",
      priceText: item.priceText || "",
      isGroupbuy: item.cardType === "groupbuy_product",
      productMeta: item.productMeta || [],
      productActionText: item.productActionText || "",
      displayTags,
      tagClass: `tag-count-${displayTags.length || 1}`
    });
  });
  return sections;
}

function createViewSessionId(prefix) {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function buildCustomerShareTitle(title) {
  const cleanTitle = String(title || "这份合集").replace(/\s+/g, " ").trim();
  return `${cleanTitle}｜点开查看完整资料`;
}

function inferFocusSections(page = {}, items = [], maxScrollPercent = 0) {
  const sections = [];
  const text = `${page.name || ""} ${page.description || ""} ${(items || []).map((item) => `${item.title || ""} ${item.summary || ""} ${item.priceText || ""}`).join(" ")}`;
  if (/价格|优惠|租金|首付|月供|费用|报价|套餐/.test(text)) sections.push("价格/优惠");
  if (/户型|图片|相册|视频|房源/.test(text)) sections.push("图片/户型");
  if (/案例|成果|客户|反馈/.test(text)) sections.push("案例/成果");
  if (/FAQ|常见问题|保障|售后|风险/.test(text)) sections.push("FAQ/保障");
  if (/电话|微信|联系|咨询|预约/.test(text)) sections.push("联系方式");
  if (/地址|位置|地图|地铁|学校|商圈/.test(text)) sections.push("地址/位置");
  if (/规格|SKU|库存|自提|配送/.test(text)) sections.push("商品规格");
  if (/课程|班|课时|老师|培训/.test(text)) sections.push("课程内容");
  if (maxScrollPercent >= 65 && !sections.includes("联系方式")) sections.push("联系方式");
  return sections.slice(0, 5);
}

function summarizePreviewItems(items, notes) {
  return (items || []).map((item) => {
    const note = (notes || []).find((row) => row.id === item.noteId);
    const config = (note && note.visibilityConfig) || {};
    const data = config.structuredData || {};
    const cardType = config.cardType || "text_note";
    return {
      noteId: item.noteId,
      title: item.displayTitle || (note && note.title) || "资料",
      summary: (note && note.summary) || "",
      coverUrl: note && note.coverUrl,
      sectionTitle: item.sectionTitle || "",
      sortOrder: item.sortOrder || 0,
      cardType,
      systemCategory: config.systemCategory || "",
      tags: Array.isArray(config.tags) ? config.tags : [],
      badge: cardType === "property_listing" ? "房源" : cardType === "groupbuy_product" ? "好物" : "资料",
      primaryText: cardType === "property_listing"
        ? [data.area, data.businessArea, data.layout].filter(Boolean).join(" | ") || ((note && note.summary) || "")
        : cardType === "groupbuy_product"
          ? [data.spec, data.pickupMethod, data.pickupLocation].filter(Boolean).join(" | ") || ((note && note.summary) || "")
          : ((note && note.summary) || ""),
      secondaryText: cardType === "property_listing"
        ? [data.address, data.utilities, data.remark].filter(Boolean).join(" | ")
        : cardType === "groupbuy_product"
          ? [data.deadline, data.remark].filter(Boolean).join(" | ")
          : ((note && note.body) || ""),
      priceText: data.price || "",
      propertyMeta: cardType === "property_listing"
        ? {
            area: data.businessArea || data.address || data.community || "",
            layout: propertyLayoutBucket(data.layout || data.unitName || item.displayTitle || (note && note.title) || ""),
            price: propertyPriceBucket(data.price || "")
          }
        : {},
      productMeta: cardType === "groupbuy_product"
        ? [data.spec, data.pickupMethod, data.pickupLocation, data.deadline ? `截止 ${data.deadline}` : ""].filter(Boolean).slice(0, 4)
        : [],
      productActionText: cardType === "groupbuy_product" ? "查看详情/接龙" : ""
    };
  }).filter((item) => item.noteId);
}

function propertyLayoutBucket(text) {
  const value = String(text || "");
  if (/三房|三室|3房|3室/.test(value)) return "三房";
  if (/两房|二房|两室|二室|2房|2室/.test(value)) return "两房";
  if (/主卧/.test(value)) return "主卧";
  if (/次卧/.test(value)) return "次卧";
  if (/一室一厅/.test(value)) return "一室一厅";
  if (/一房|一室|1房|1室|单间/.test(value)) return "一房/单间";
  if (/loft|复式/i.test(value)) return "Loft/复式";
  return "";
}

function propertyPriceBucket(text) {
  const matches = String(text || "").match(/\d{3,5}/g) || [];
  if (!matches.length) return "";
  const price = Math.min(...matches.map((value) => Number(value)).filter((value) => Number.isFinite(value)));
  if (price < 1000) return "1000以下";
  if (price < 1500) return "1000-1500";
  if (price < 2000) return "1500-2000";
  if (price < 3000) return "2000-3000";
  return "3000以上";
}

function flattenSections(sections) {
  return (sections || []).reduce((rows, section) => rows.concat(section.items || []), []);
}

function filterItemsForDisplay(items = [], display = {}) {
  const category = String(display.activeCategory || "").trim();
  if (category === "房源" || category === "房产") {
    return (items || []).filter((item) => item.cardType === "property_listing");
  }
  if (category === "商品" || category === "团购") {
    return (items || []).filter((item) => item.cardType === "groupbuy_product");
  }
  if (category === "服务") {
    return (items || []).filter((item) => item.cardType === "business_card" || item.cardType === "service_offer");
  }
  return items || [];
}

function normalizePropertyFilters(display = {}) {
  const groups = Array.isArray(display.propertyFilters) ? display.propertyFilters : [];
  return groups.map((group) => ({
    key: String(group.key || ""),
    label: String(group.label || ""),
    options: [{ label: "全部", value: "", count: 0 }].concat((group.options || []).map((option) => ({
      label: option.label || option.value || "",
      value: option.value || option.label || "",
      count: option.count || 0
    })).filter((option) => option.value))
  })).filter((group) => group.key && group.label && group.options.length > 1);
}

function applyPropertyFilter(items = [], active = {}) {
  if (!active || !active.key || !active.value) return items || [];
  return (items || []).filter((item) => String((item.propertyMeta || {})[active.key] || "") === String(active.value));
}

function decoratePropertyFilters(groups = [], active = {}) {
  return (groups || []).map((group) => ({
    ...group,
    options: (group.options || []).map((option) => ({
      ...option,
      active: active && active.key
        ? active.key === group.key && active.value === option.value
        : !option.value
    }))
  }));
}

function formatShowcaseDate(value) {
  if (!value) return "刚刚更新";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚更新";
  const month = date.getMonth() + 1;
  const day = date.getDate();
  return `${month}月${day}日`;
}

function contactSummary(page) {
  const contact = (page && page.contactConfig) || {};
  const hasPhone = contact.showPhone && contact.phone;
  const hasWechat = contact.showWechat && contact.wechat;
  if (hasWechat) return "微信咨询";
  if (hasPhone) return "电话咨询";
  return "可分享";
}

function buildShowcaseCommunicationActions(page) {
  const contact = (page && page.contactConfig) || {};
  const actions = [];
  if (contact.showPhone && contact.phone) {
    actions.push({
      key: "contact",
      icon: "电",
      title: "打电话",
      primaryTitle: "电话联系",
      desc: "直接联系发布者"
    });
  }
  if (contact.showWechat && contact.wechat) {
    actions.push({
      key: "private",
      icon: "微",
      title: "微信沟通",
      primaryTitle: "微信联系",
      desc: "复制微信号联系"
    });
  }
  return actions;
}

function getShowcaseAnonymousId() {
  return getAnonymousVisitorId();
}

function createShareId(showcaseId) {
  return `share_${showcaseId || "showcase"}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function canSharePage(preview, page) {
  return !preview || (page && page.status === "published");
}

function resolveAudienceMode(preview, user, shareFromUserId) {
  if (preview) return "owner_preview";
  if (user && shareFromUserId && user.id === shareFromUserId) return "owner";
  return "customer";
}

function visibleStats(items, page) {
  const count = (items || []).length;
  return {
    resources: `${count}`,
    updated: formatShowcaseDate((page && (page.updatedAt || page.publishedAt)) || ""),
    contact: contactSummary(page)
  };
}

function inferShowcaseContext(page, items) {
  const display = (page && page.displayConfig) || {};
  const category = String(display.activeCategory || "").trim();
  const productLike = category === "商品" || category === "团购" || (items || []).filter((item) => item.cardType === "groupbuy_product").length > (items || []).filter((item) => item.cardType === "property_listing").length;
  const propertyLike = category === "房产" || (items || []).some((item) => item.cardType === "property_listing");
  if (productLike) {
    return {
      resourceMetric: "精选好物",
      updateMetric: "最近更新",
      contactMetric: "咨询方式",
      featuredTitle: "本周主推",
      agencyPill: "认证好物",
      shareText: "发给客户，一键分享好物",
      storyTabs: ["好物推荐", "生活好物", "真实分享", "贴心服务"],
      storyShareText: "发给客户，一起分享生活好物",
      catalogSearch: "好物资料目录",
      catalogTabs: ["全部", "好物", "团购", "热卖", "新品"],
      brandPill: "用专业帮您挑到合适好物",
      brandCases: "精选好物",
      brandShareText: "发给客户 · 让好物帮到更多人",
      trustItems: ["来自笔记", "点击详情", "可咨询", "持续更新"]
    };
  }
  if (propertyLike) {
    return {
      isProperty: true,
      resourceMetric: "精选房源",
      updateMetric: "最近更新",
      contactMetric: "微信联系",
      featuredTitle: "精选房源",
      agencyPill: "租房对盘",
      shareText: "发给客户",
      storyTabs: ["租房推荐", "可带看", "近地铁", "近期更新"],
      storyShareText: "发给客户",
      catalogSearch: "租房清单对比",
      catalogTabs: ["全部", "两房", "一房", "可带看", "近地铁"],
      brandPill: "租房中介精选房源",
      brandCases: "精选房源",
      brandShareText: "发给客户",
      trustItems: ["租金户型", "点击详情", "微信咨询", "持续更新"],
      sameCtaText: "我是中介，也想生成这种合集"
    };
  }
  return {
    resourceMetric: "精选资料",
    updateMetric: "最近更新",
    contactMetric: "咨询方式",
    featuredTitle: "本周主推",
    agencyPill: "认证资料",
    shareText: "发给客户，一键分享资料",
    storyTabs: ["资料推荐", "生活好物", "真实分享", "贴心服务"],
    storyShareText: "发给客户，一起分享资料",
    catalogSearch: "资料目录",
    catalogTabs: ["全部", "资料", "图片", "链接", "笔记"],
    brandPill: "用专业帮您整理有价值资料",
    brandCases: "精选资料",
    brandShareText: "发给客户 · 让资料帮到更多人",
      trustItems: ["来自笔记", "点击详情", "可咨询", "持续更新"]
    };
}

const {
  buildShowcaseShareSource,
  createShareSnapshotFingerprint,
  getShareSourceRevision,
  isShareImageUrl,
  setShareMenuEnabled,
  SHARE_CARD_STYLE_VERSION
} = require("../../plugins/share-snapshot/index");

Page({
  data: {
    id: "",
    preview: false,
    audienceMode: "customer",
    isOwnerViewing: false,
    user: null,
    page: null,
    displayLayout: "list",
    template: getShowcaseTemplate("featured_window"),
    templateClass: templateClass("featured_window"),
    profileInitial: "展",
    profileName: "展示页",
    sections: [],
    flatItems: [],
    allFlatItems: [],
    propertyFilters: [],
    activePropertyFilter: { key: "", value: "", label: "" },
    heroItem: null,
    stats: visibleStats([], null),
    context: inferShowcaseContext(null, []),
    loading: false,
    errorText: "",
    viewRecorded: false,
    viewSessionId: "",
    pageEnterAt: 0,
    maxScrollPercent: 0,
    shareId: "",
    shareFromUserId: "",
    shareScene: "",
    referrer: "",
    canShare: true,
    showcaseShareImage: "",
    shareImageReady: false,
    shareStatusText: "正在准备",
    showcaseCommunicationActions: [],
    showcasePrimaryCommunicationAction: null,
    showcaseCommunicationHint: "先浏览资料，选中具体内容后可留言或留下需求"
  },
  onLoad(options) {
    const id = options.id || options.showcaseId || "";
    const preview = options.preview === "1";
    this.setData({
      id,
      preview,
      shareId: options.sid || "",
      shareFromUserId: options.from || "",
      shareScene: options.src || options.scene || "",
      referrer: options.ref || "",
      audienceMode: resolveAudienceMode(preview, getCurrentUser(), options.from || ""),
      isOwnerViewing: resolveAudienceMode(preview, getCurrentUser(), options.from || "") !== "customer",
      viewSessionId: createViewSessionId("showcase_view"),
      pageEnterAt: Date.now(),
      maxScrollPercent: 0
    });
  },
  onShow() {
    const user = getCurrentUser();
    const audienceMode = resolveAudienceMode(this.data.preview, user, this.data.shareFromUserId);
    this.setData({
      user,
      audienceMode,
      isOwnerViewing: audienceMode !== "customer"
    });
    this.loadPage();
  },
  async loadPage() {
    const { id, preview, user } = this.data;
    if (!id) {
      this.setData({ errorText: "展示页链接缺少页面编号，请让发布者重新发送。", page: null });
      this.updateShareMenu(false);
      return;
    }
    this.setData({ loading: true, errorText: "" });
    try {
      const res = preview && user
        ? await api.fetchShowcase(id, user.id)
        : await api.fetchPublicShowcase(id);
      const page = res.data || {};
      page.shareSnapshotUrl = page.shareSnapshotUrl || (page.shareSnapshot && page.shareSnapshot.url) || "";
      page.shareSnapshotStyleId = page.shareSnapshotStyleId || (page.shareSnapshot && page.shareSnapshot.styleId) || "";
      page.shareSnapshotFingerprint = page.shareSnapshotFingerprint
        || (page.shareSnapshot && page.shareSnapshot.fingerprint)
        || "";
      page.contactConfig = {
        ...(page.contactConfig || {}),
        avatarUrl: safeAvatarUrl(page.contactConfig && page.contactConfig.avatarUrl)
      };
      if (preview && user) {
        const notesRes = await api.fetchNotes({ ownerUserId: user.id }, { metadataOnly: true });
        page.items = summarizePreviewItems(page.items || [], notesRes.data || []);
      }
      const display = page.displayConfig || {};
      const sceneType = normalizeSceneType(
        page.sceneType || display.sceneType || display.activeCategory || "notes"
      );
      const effectiveTemplateId = normalizeTemplateId(
        sceneType,
        page.templateId || getDefaultTemplateId(sceneType)
      );
      // 公开快照必须按场景白名单渲染。服务端已做同样约束，这里再做一次防御，
      // 避免旧快照或异常 templateId 把客户页落到错误的模板分支。
      page.sceneType = sceneType;
      page.templateId = effectiveTemplateId;
      const template = getShowcaseTemplate(effectiveTemplateId);
      const visibleItems = filterItemsForDisplay(page.items || [], display);
      const rawPropertyFilters = normalizePropertyFilters(display);
      const activePropertyFilter = { key: "", value: "", label: "" };
      const filteredItems = applyPropertyFilter(visibleItems, activePropertyFilter);
      const sections = buildSections(filteredItems, display.groupBy || "none");
      const flatItems = flattenSections(sections);
      const showcaseCommunicationActions = buildShowcaseCommunicationActions(page);
      this.setData({
        page,
        template,
        templateClass: templateClass(effectiveTemplateId),
        displayLayout: display.layoutMode === "grid" ? "grid" : "list",
        profileInitial: String(page.name || "展").slice(0, 1),
        profileName: (page.contactConfig && page.contactConfig.ownerName) || page.name || "展示页",
        sections,
        flatItems,
        allFlatItems: visibleItems,
        propertyFilters: decoratePropertyFilters(rawPropertyFilters, activePropertyFilter),
        activePropertyFilter,
        heroItem: flatItems.find((item) => item.coverUrl) || flatItems[0] || null,
        stats: visibleStats(flatItems, page),
        context: inferShowcaseContext(page, flatItems),
        canShare: canSharePage(preview, page),
        showcaseCommunicationActions,
        showcasePrimaryCommunicationAction: showcaseCommunicationActions.find((item) => item.key === "private")
          || showcaseCommunicationActions.find((item) => item.key === "contact")
          || null
      }, () => {
        this.prepareShowcaseShareImage();
      });
      if (!preview && !this.data.viewRecorded) {
        this.recordEvent("view", {
          sessionId: this.data.viewSessionId,
          durationSeconds: 1,
          maxScrollPercent: 0,
          focusSections: inferFocusSections(page, flatItems, 0)
        });
        this.setData({ viewRecorded: true });
      }
      this.bindReferralFromShare(page);
    } catch (error) {
      this.setData({ errorText: error.detail || "展示页不可访问，请让发布者确认已发布。" });
      wx.showToast({ title: error.detail || "展示页不可访问", icon: "none" });
      this.updateShareMenu(false);
    } finally {
      this.setData({ loading: false });
    }
  },
  bindReferralFromShare(page) {
    const user = this.data.user;
    const inviterUserId = this.data.shareFromUserId;
    if (this.data.preview || !user || !inviterUserId || user.id === inviterUserId || !page || page.ownerUserId === user.id) return;
    api.bindReferralFromShare(user.id, inviterUserId, this.data.shareScene || "share_link").catch(() => {});
  },
  handlePropertyFilterTap(event) {
    const key = event.currentTarget.dataset.key || "";
    const value = event.currentTarget.dataset.value || "";
    const label = event.currentTarget.dataset.label || "";
    const activePropertyFilter = value ? { key, value, label } : { key: "", value: "", label: "" };
    const page = this.data.page || {};
    const display = page.displayConfig || {};
    const filteredItems = applyPropertyFilter(this.data.allFlatItems || [], activePropertyFilter);
    const sections = buildSections(filteredItems, display.groupBy || "none");
    const flatItems = flattenSections(sections);
    this.setData({
      activePropertyFilter,
      propertyFilters: decoratePropertyFilters(this.data.propertyFilters || [], activePropertyFilter),
      sections,
      flatItems,
      heroItem: flatItems.find((item) => item.coverUrl) || flatItems[0] || null,
      stats: visibleStats(flatItems, page),
      context: inferShowcaseContext(page, flatItems)
    });
  },
  updateShareMenu(canShare) {
    setShareMenuEnabled(Boolean(canShare && isShareImageUrl(this.data.showcaseShareImage)));
  },
  recordEvent(eventType, extra = {}) {
    if (this.data.preview || !this.data.id) return;
    const user = this.data.user;
    const trace = {
      shareId: this.data.shareId || "",
      shareFromUserId: this.data.shareFromUserId || "",
      scene: this.data.shareScene || "public_showcase",
      referrer: this.data.referrer || "",
      ...extra
    };
    const payload = user ? {
      eventType,
      viewerUserId: user.id,
      nickname: user.nickname || "微信用户",
      avatarUrl: safeAvatarUrl(user.avatarUrl),
      ...trace
    } : {
      eventType,
      anonymousId: getShowcaseAnonymousId(),
      ...trace
    };
    api.recordShowcaseEvent(this.data.id, payload).catch(() => {});
  },
  onPageScroll(event) {
    const scrollTop = Number(event.scrollTop || 0);
    const percent = Math.min(100, Math.max(0, Math.round((scrollTop / 1800) * 100)));
    if (percent > this.data.maxScrollPercent) {
      this.setData({ maxScrollPercent: percent });
    }
  },
  flushViewBehavior() {
    if (this.data.preview || !this.data.id || !this.data.viewRecorded) return;
    const durationSeconds = Math.max(1, Math.round((Date.now() - (this.data.pageEnterAt || Date.now())) / 1000));
    this.recordEvent("view", {
      sessionId: this.data.viewSessionId,
      durationSeconds,
      maxScrollPercent: this.data.maxScrollPercent,
      focusSections: inferFocusSections(this.data.page || {}, this.data.flatItems || [], this.data.maxScrollPercent)
    });
  },
  onHide() {
    this.flushViewBehavior();
  },
  onUnload() {
    this.flushViewBehavior();
  },
  openNote(event) {
    const noteId = event.currentTarget.dataset.id;
    this.recordEvent("note_click", { noteId });
    wx.navigateTo({ url: `/pages/note-preview/index?id=${noteId}` });
  },
  handleCommunicationAction(event) {
    const key = event.detail && event.detail.key;
    if (key === "contact") {
      this.callPhone();
      return;
    }
    if (key === "private") this.copyWechat();
  },
  handleShareTap() {
    subscription.requestViewNotificationSubscription("showcase_view_share");
  },
  callPhone() {
    const phone = this.data.page && this.data.page.contactConfig && this.data.page.contactConfig.phone;
    if (!phone) return;
    this.recordEvent("phone_click");
    wx.makePhoneCall({ phoneNumber: phone });
  },
  copyWechat() {
    const wechat = this.data.page && this.data.page.contactConfig && this.data.page.contactConfig.wechat;
    if (!wechat) return;
    this.recordEvent("wechat_copy");
    wx.setClipboardData({ data: wechat });
  },
  handleGenerateSame() {
    if (this.data.isOwnerViewing || this.data.audienceMode !== "customer") {
      wx.showToast({ title: "这是自己的展示页，无需生成同款", icon: "none" });
      return;
    }
    const page = this.data.page || {};
    const contact = page.contactConfig || {};
    const query = [
      "sourceType=showcase",
      this.data.id ? `sourceId=${encodeURIComponent(this.data.id)}` : "",
      page.name ? `sourceTitle=${encodeURIComponent(page.name)}` : "",
      (contact.ownerName || this.data.profileName) ? `publisherName=${encodeURIComponent(contact.ownerName || this.data.profileName)}` : "",
      (contact.wechat || contact.phone || contact.contactText) ? `upstreamContact=${encodeURIComponent(contact.wechat || contact.phone || contact.contactText)}` : ""
    ].filter(Boolean).join("&");
    wx.navigateTo({ url: `/subpackages/workbench/property-same/index?${query}` });
  },
  async prepareShowcaseShareImage() {
    const page = this.data.page || {};
    if (!page) {
      this.setData({ showcaseShareImage: "", shareImageReady: false, shareStatusText: "正在准备" }, () => this.updateShareMenu(false));
      return;
    }
    const source = buildShowcaseShareSource(page);
    const expectedFingerprint = page.id
      ? createShareSnapshotFingerprint(
        "showcase",
        page.id,
        getShareSourceRevision("showcase", page),
        SHARE_CARD_STYLE_VERSION,
        source
      )
      : "";
    const isCurrentSnapshot = Boolean(
      page.shareSnapshotUrl
      && page.shareSnapshotStyleId === SHARE_CARD_STYLE_VERSION
      && page.shareSnapshotFingerprint === expectedFingerprint
      && isShareImageUrl(page.shareSnapshotUrl)
    );
    if (isCurrentSnapshot) {
      this.setData({ showcaseShareImage: page.shareSnapshotUrl, shareImageReady: true, shareStatusText: "发给客户" }, () => {
        this.updateShareMenu(canSharePage(this.data.preview, page) && isShareImageUrl(page.shareSnapshotUrl));
      });
      return;
    }
    this.setData({ showcaseShareImage: "", shareImageReady: false, shareStatusText: "正在准备" }, () => this.updateShareMenu(false));
  },
  onShareAppMessage() {
    const page = this.data.page || {};
    if (!this.data.canShare) {
      wx.showToast({ title: "发布后才能发给客户", icon: "none" });
      this.updateShareMenu(false);
      return null;
    }
    const user = this.data.user || getCurrentUser();
    if (!isShareImageUrl(this.data.showcaseShareImage)) {
      wx.showToast({ title: "分享内容正在准备，请稍后再发", icon: "none" });
      this.updateShareMenu(false);
      return null;
    }
    const shareId = createShareId(this.data.id);
    const scene = this.data.preview ? "showcase_preview_share" : "public_showcase_share";
    const shareFromUserId = user ? user.id : (this.data.shareFromUserId || "");
    if (this.data.id && page.status === "published") {
      api.recordShowcaseEvent(this.data.id, {
        eventType: "share",
        shareId,
        shareFromUserId,
        scene,
        referrer: this.data.shareId || ""
      }).catch(() => {});
    } else if (!this.data.preview) {
      this.recordEvent("share", { shareId, shareFromUserId, scene, referrer: this.data.shareId || "" });
    }
    return {
      title: buildCustomerShareTitle(page.shareTitle || page.name || "资料展示页"),
      path: `/pages/showcase-view/index?id=${encodeURIComponent(this.data.id)}&showcaseId=${encodeURIComponent(this.data.id)}&sid=${encodeURIComponent(shareId)}&from=${encodeURIComponent(shareFromUserId)}&src=${encodeURIComponent(scene)}&ref=${encodeURIComponent(this.data.shareId || "")}`,
      imageUrl: this.data.showcaseShareImage
    };
  }
});
