const api = require("../../services/api");
const { getCurrentUser, getRandomDefaultNickname, safeAvatarUrl } = require("../../utils/dashboard");
const { getShowcaseTemplate, templateClass } = require("../../utils/showcase-templates");
const { buildTitleCoverData } = require("../../utils/title-cover");
const { generateTitleShareImage } = require("../../utils/business-card-share");

const SHOWCASE_SHARE_CANVAS_ID = "showcaseShareCanvas";

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
      productMeta: cardType === "groupbuy_product"
        ? [data.spec, data.pickupMethod, data.pickupLocation, data.deadline ? `截止 ${data.deadline}` : ""].filter(Boolean).slice(0, 4)
        : [],
      productActionText: cardType === "groupbuy_product" ? "查看详情/接龙" : ""
    };
  }).filter((item) => item.noteId);
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

function getShowcaseAnonymousId() {
  const key = "showcaseAnonymousId";
  const stored = wx.getStorageSync(key);
  if (stored) return stored;
  const next = `showcase_anon_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
  wx.setStorageSync(key, next);
  return next;
}

function createShareId(showcaseId) {
  return `share_${showcaseId || "showcase"}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function canSharePage(preview, page) {
  return !preview || (page && page.status === "published");
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

Page({
  data: {
    id: "",
    preview: false,
    user: null,
    page: null,
    displayLayout: "list",
    template: getShowcaseTemplate("featured_window"),
    templateClass: templateClass("featured_window"),
    profileInitial: "展",
    profileName: "展示页",
    sections: [],
    flatItems: [],
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
    canShare: true
  },
  onLoad(options) {
    const id = options.id || options.showcaseId || "";
    this.setData({
      id,
      preview: options.preview === "1",
      shareId: options.sid || "",
      shareFromUserId: options.from || "",
      shareScene: options.src || options.scene || "",
      referrer: options.ref || "",
      viewSessionId: createViewSessionId("showcase_view"),
      pageEnterAt: Date.now(),
      maxScrollPercent: 0
    });
  },
  onShow() {
    this.setData({ user: getCurrentUser() });
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
      page.contactConfig = {
        ...(page.contactConfig || {}),
        avatarUrl: safeAvatarUrl(page.contactConfig && page.contactConfig.avatarUrl)
      };
      if (preview && user) {
        const notesRes = await api.fetchNotes({ ownerUserId: user.id });
        page.items = summarizePreviewItems(page.items || [], notesRes.data || []);
      }
      const display = page.displayConfig || {};
      const template = getShowcaseTemplate(page.templateId);
      const visibleItems = filterItemsForDisplay(page.items || [], display);
      const sections = buildSections(visibleItems, display.groupBy || "none");
      const flatItems = flattenSections(sections);
      this.setData({
        page,
        template,
        templateClass: templateClass(page.templateId),
        displayLayout: display.layoutMode === "grid" ? "grid" : "list",
        profileInitial: String(page.name || "展").slice(0, 1),
        profileName: (page.contactConfig && page.contactConfig.ownerName) || page.name || "展示页",
        sections,
        flatItems,
        heroItem: flatItems.find((item) => item.coverUrl) || flatItems[0] || null,
        stats: visibleStats(flatItems, page),
        context: inferShowcaseContext(page, flatItems),
        canShare: canSharePage(preview, page)
      }, () => this.prepareShowcaseShareImage());
      this.updateShareMenu(canSharePage(preview, page));
      if (!preview && !this.data.viewRecorded) {
        this.recordEvent("view", {
          sessionId: this.data.viewSessionId,
          durationSeconds: 1,
          maxScrollPercent: 0,
          focusSections: inferFocusSections(page, flatItems, 0)
        });
        this.setData({ viewRecorded: true });
      }
    } catch (error) {
      this.setData({ errorText: error.detail || "展示页不可访问，请让发布者确认已发布。" });
      wx.showToast({ title: error.detail || "展示页不可访问", icon: "none" });
      this.updateShareMenu(false);
    } finally {
      this.setData({ loading: false });
    }
  },
  updateShareMenu(canShare) {
    if (canShare) {
      wx.showShareMenu({ withShareTicket: false });
    } else {
      wx.hideShareMenu();
    }
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
      nickname: user.nickname || getRandomDefaultNickname(),
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
    const page = this.data.page || {};
    const contact = page.contactConfig || {};
    const query = [
      "sourceType=showcase",
      this.data.id ? `sourceId=${encodeURIComponent(this.data.id)}` : "",
      page.name ? `sourceTitle=${encodeURIComponent(page.name)}` : "",
      (contact.ownerName || this.data.profileName) ? `publisherName=${encodeURIComponent(contact.ownerName || this.data.profileName)}` : "",
      (contact.wechat || contact.phone || contact.contactText) ? `upstreamContact=${encodeURIComponent(contact.wechat || contact.phone || contact.contactText)}` : ""
    ].filter(Boolean).join("&");
    wx.navigateTo({ url: `/pages/property-same/index?${query}` });
  },
  async prepareShowcaseShareImage() {
    const page = this.data.page || {};
    const heroItem = this.data.heroItem || {};
    if (!page) {
      this.setData({ showcaseShareImage: "" });
      return;
    }
    try {
      const imagePath = await generateTitleShareImage(this, SHOWCASE_SHARE_CANVAS_ID, {
        title: page.shareTitle || page.name || "资料展示页",
        summary: page.description || "",
        badge: "合集",
        coverUrl: heroItem.coverUrl || page.bannerUrl || "",
        hint: "打开小程序查看完整合集",
        growthHint: "我也想做同款",
        shareTargetLabel: "合集"
      });
      if (imagePath) this.setData({ showcaseShareImage: imagePath });
    } catch (error) {
      this.setData({ showcaseShareImage: "" });
    }
  },
  onShareAppMessage() {
    const page = this.data.page || {};
    if (!this.data.canShare) {
      wx.showToast({ title: "发布后才能发给客户", icon: "none" });
      return {
        title: page.name || "资料展示页",
        path: `/pages/showcases/index`
      };
    }
    const user = this.data.user || getCurrentUser();
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
      path: `/pages/showcases/index?shareTarget=showcase&showcaseId=${this.data.id}&sid=${shareId}&from=${shareFromUserId}&src=${scene}&ref=${this.data.shareId || ""}`,
      imageUrl: this.data.showcaseShareImage || ""
    };
  }
});
