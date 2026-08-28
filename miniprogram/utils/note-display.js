const NOISY_LABELS = new Set(["未整理", "待整理", "待跟进", "已整理", "房源候选", "团购候选"]);
const PROPERTY_CONTEXT_LABELS = ["房产", "房源", "租房", "小区", "公寓", "人民广场", "五一广场"];
const { getSalesPageTemplate } = require("./sales-page-templates");

const CARD_TYPE_LABELS = {
  property_listing: "房源",
  groupbuy_product: "团购",
  business_card: "名片",
  service_offer: "服务",
  image_ocr: "图片",
  article: "文章",
  link: "链接",
  text_note: "笔记"
};

const SOURCE_LABELS = {
  wecom: "企业微信",
  wecom_kf: "企业微信",
  wecom_archive: "企业微信",
  manual_text: "手动文字",
  manual: "手动添加",
  image_capture: "图片保存",
  image_ocr: "图片资料",
  miniapp: "小程序卡片",
  link: "链接收藏",
  note: "手动笔记",
  ocr: "图片资料"
};

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (num) => `${num}`.padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function isUsefulLabel(label) {
  const value = String(label || "").trim();
  if (!value || NOISY_LABELS.has(value)) return false;
  if (/^\d{3,5}-\d{3,5}$/.test(value)) return true;
  return value.length <= 10;
}

function isPropertyContextLabel(label) {
  const value = String(label || "").trim();
  return Boolean(value && PROPERTY_CONTEXT_LABELS.some((keyword) => value.includes(keyword)));
}

function filterContextualLabels(labels, userLabels, cardType) {
  const userSet = new Set(userLabels || []);
  const useful = (labels || []).filter(isUsefulLabel);
  if (cardType === "property_listing") return useful;
  return useful.filter((label) => userSet.has(label) || !isPropertyContextLabel(label));
}

function filterContextualTopics(topics, cardType) {
  const names = (topics || []).map((topic) => topic && topic.name).filter(isUsefulLabel);
  if (cardType === "property_listing") return names;
  return names.filter((name) => !isPropertyContextLabel(name));
}

function cardTypeLabel(cardType) {
  return CARD_TYPE_LABELS[cardType] || "资料";
}

function resolveCardType(config) {
  return config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note");
}

const LEGACY_IMAGE_TRANSFER_NOTICE = "收到image素材，媒体稍后转存。";
// Keep legacy image-note snapshot validation aligned with the single share
// plugin version. Older pre-v8 images are intentionally stale after the typed
// fixed-layout templates were introduced. v10 also routes every card through
// the JPG fixed-template pipeline, using an image-first presentation when a
// real cover exists and an info-first presentation when it does not.

function cleanImagePrimaryText(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => item !== LEGACY_IMAGE_TRANSFER_NOTICE)
    .join("\n")
    .trim();
}

function isImagePrimaryNote(note = {}) {
  const config = note.visibilityConfig || {};
  const cardType = resolveCardType(config);
  const sourceType = config.sourceType || "";
  const structuredData = config.structuredData || {};
  const hasImage = Array.isArray(note.media)
    && note.media.some((item) => item && item.type === "image" && item.url);
  if (!hasImage) return false;
  if (cardType === "image_ocr" || ["ocr", "image_ocr", "image_capture"].includes(sourceType)) return true;
  // Backward compatibility for records created before image-primary classification.
  if (cardType !== "text_note" || config.contentMode === "bookmark") return false;
  if (Array.isArray(structuredData.images) && structuredData.images.some(Boolean)) return true;
  // Private WeCom image + caption messages were historically stored as a
  // manual text note with an image attachment. Keep those images in the body
  // presentation while leaving links and mini-app cards on their own layouts.
  return !["link", "article", "miniapp", "weapp"].includes(sourceType);
}

function getPrimaryImageUrl(note = {}) {
  const mediaImage = Array.isArray(note.media)
    ? note.media.find((item) => item && item.type === "image" && (item.url || item.displayUrl))
    : null;
  return (mediaImage && (mediaImage.url || mediaImage.displayUrl))
    || note.coverUrl
    || note.coverDisplayUrl
    || ((note.visibilityConfig || {}).structuredData || {}).coverUrl
    || "";
}

function imagePrimaryTitle(note = {}, caption = "") {
  const title = String(note.title || "").trim();
  if (title && title !== LEGACY_IMAGE_TRANSFER_NOTICE) return title;
  return String(caption || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .find(Boolean) || "图片资料";
}

function decorateNoteForList(note) {
  const config = note.visibilityConfig || {};
  const suggestions = Array.isArray(config.typeSuggestions) ? config.typeSuggestions : [];
  const cardType = resolveCardType(config);
  const userTags = Array.isArray(config.userTags) ? config.userTags.filter(isUsefulLabel) : [];
  const tags = filterContextualLabels(Array.isArray(config.tags) ? config.tags : [], userTags, cardType);
  const structuredData = config.structuredData || {};
  const isImageNote = isImagePrimaryNote(note);
  const imageCaption = isImageNote
    ? cleanImagePrimaryText(note.body || structuredData.rawText || (structuredData.ocr || {}).text || note.summary || "")
    : "";
  const migrationInfo = buildMigrationInfo(note, config, cardType, structuredData, suggestions);
  const confirmAction = buildConfirmAction(suggestions);
  return {
    ...note,
    ...(isImageNote ? {
      title: imagePrimaryTitle(note, imageCaption),
      summary: imageCaption || cleanImagePrimaryText(note.summary)
    } : {}),
    cardType,
    isImageNote,
    structuredData,
    isBookmark: cardType === "link" && config.contentMode === "bookmark",
    isProperty: cardType === "property_listing",
    isGroupbuy: cardType === "groupbuy_product",
    isBusinessCard: cardType === "business_card",
    isServiceOffer: cardType === "service_offer",
    isServiceCard: cardType === "business_card" || cardType === "service_offer",
    sourceUrl: config.sourceUrl || "",
    sourceName: config.sourceName || "链接来源",
    sourceLabel: config.sourceLabel || "网页链接",
    sourceType: config.sourceType || "note",
    systemCategory: config.systemCategory || config.category || "待整理",
    bookmarkCategory: config.systemCategory || config.category || "文章收藏",
    bookmarkTags: tags,
    topicNames: filterContextualTopics(Array.isArray(config.topics) ? config.topics : [], cardType),
    primaryValue: buildPrimaryValue(cardType, structuredData, note),
    secondaryValue: buildSecondaryValue(cardType, structuredData, note),
    gridTitle: buildGridTitle(cardType, structuredData, note),
    gridSummary: buildGridSummary(cardType, structuredData, note),
    gridPrice: buildGridPrice(cardType, structuredData),
    businessCardPreview: buildBusinessCardPreview(cardType, structuredData, note, config),
    serviceOfferPreview: buildServiceOfferPreview(cardType, structuredData, note, config),
    cardBadge: buildCardBadge(cardType, config),
    propertyStatus: buildPropertyStatus(structuredData.propertyStatus),
    cardAction: buildCardAction(cardType),
    suggestionText: buildSuggestionText(suggestions),
    migrationInfo,
    migrationSourceText: migrationInfo.sourceText,
    migrationStatusText: migrationInfo.statusText,
    migrationActionText: migrationInfo.actionText,
    migrationTone: migrationInfo.tone,
    migrationNeedsAction: migrationInfo.needsAction,
    migrationConfirmType: confirmAction.cardType,
    migrationConfirmText: confirmAction.text,
    collectedAtText: formatDateTime(note.createdAt),
    uploadDateText: formatDate(note.createdAt),
    scrmSummary: null,
    scrmHasUnread: false
  };
}

function buildBusinessCardPreview(cardType, data, note, config = {}) {
  if (cardType !== "business_card") return null;
  const name = data.name || note.title || "电子名片";
  const phone = data.phone || note.phone || "";
  const wechat = data.wechat || data.contactWechat || "";
  return {
    name,
    role: data.title || "",
    company: data.company || "",
    serviceScope: data.serviceScope || data.headline || note.summary || "",
    contactLine: [phone, wechat].filter(Boolean).join(" · "),
    avatarUrl: data.avatarUrl || note.coverUrl || "",
    templateId: config.displayTemplate || "",
    tone: config.displayTemplateTone || "",
    initial: String(name || "名").slice(0, 1)
  };
}

function buildServiceOfferPreview(cardType, data, note, config = {}) {
  if (cardType !== "service_offer") return null;
  const serviceName = data.serviceName || note.title || "服务/合作";
  const headline = data.headline || note.summary || "";
  return {
    serviceName,
    headline,
    detailText: data.detailText || data.serviceContent || note.body || "",
    pricingOrTerms: data.pricingOrTerms || data.cooperationTerms || data.pricingNote || "",
    serviceScope: data.serviceScope || data.serviceArea || "",
    coverUrl: data.coverUrl || note.coverUrl || ((note.media || []).find((item) => item.type === "image") || {}).url || "",
    badge: "服务 / 合作",
    actionText: "咨询详情"
  };
}

function buildConfirmAction(suggestions) {
  const allowed = (suggestions || []).find((item) => item && ["property_listing", "groupbuy_product"].includes(item.cardType));
  if (!allowed) return { cardType: "", text: "" };
  if (allowed.cardType === "property_listing") return { cardType: allowed.cardType, text: "整理成房源" };
  if (allowed.cardType === "groupbuy_product") return { cardType: allowed.cardType, text: "整理成商品" };
  return { cardType: "", text: "" };
}

function buildMigrationInfo(note, config, cardType, structuredData, suggestions) {
  const sourceType = config.sourceType || note.sourceType || "note";
  const sourceText = SOURCE_LABELS[sourceType] || config.sourceLabel || cardTypeLabel(cardType);
  const ocrStatus = structuredData && structuredData.ocr && structuredData.ocr.status;
  if (cardType === "image_ocr" || sourceType === "image_ocr" || sourceType === "image_capture" || sourceType === "ocr") {
    if (ocrStatus === "recognized" || ocrStatus === "success") {
      return { sourceText, statusText: "已识别文字", actionText: "继续整理", tone: "green", needsAction: false };
    }
    if (ocrStatus === "failed") {
      return { sourceText, statusText: "识别失败", actionText: "重新识别", tone: "red", needsAction: true };
    }
    return { sourceText, statusText: "图片已保存", actionText: "按需识别", tone: "blue", needsAction: true };
  }
  if (cardType === "property_listing") {
    return { sourceText, statusText: "已整理成房源", actionText: "完善房源", tone: "green", needsAction: false };
  }
  if (cardType === "groupbuy_product") {
    return { sourceText, statusText: "已整理成商品", actionText: "完善商品", tone: "green", needsAction: false };
  }
  if (cardType === "business_card") {
    return { sourceText, statusText: "已生成名片", actionText: "完善名片", tone: "green", needsAction: false };
  }
  if (cardType === "service_offer") {
    return { sourceText, statusText: "已整理成服务", actionText: "完善服务", tone: "green", needsAction: false };
  }
  if (suggestions.length) {
    return { sourceText, statusText: "需要确认类型", actionText: "确认整理", tone: "orange", needsAction: true };
  }
  if (cardType === "text_note") {
    return { sourceText, statusText: "普通笔记", actionText: "编辑", tone: "gray", needsAction: false };
  }
  if (config.systemCategory === "待整理" || config.cardState === "draft") {
    return { sourceText, statusText: "待整理", actionText: "继续整理", tone: "orange", needsAction: true };
  }
  if (cardType === "link") {
    return { sourceText, statusText: "已收藏链接", actionText: "整理为笔记", tone: "blue", needsAction: false };
  }
  return { sourceText, statusText: "已入库", actionText: "编辑", tone: "gray", needsAction: false };
}

function decorateNoteForShowcasePicker(note, selectedItems) {
  const base = decorateNoteForList(note);
  const config = note.visibilityConfig || {};
  const structuredData = base.structuredData || {};
  const selected = (selectedItems || []).find((item) => item.noteId === note.id);
  const title = note.title || structuredData.community || structuredData.productName || "资料";
  return {
    ...base,
    title,
    categoryLabels: buildNoteCategoryLabels(note, config),
    selected: Boolean(selected),
    badge: base.cardBadge || cardTypeLabel(base.cardType),
    selectedText: selected ? "已加入" : "加入展示页",
    tagText: (base.bookmarkTags || []).slice(0, 3).join(" · "),
    primaryText: buildShowcasePrimaryText(base.cardType, structuredData, note),
    gridTitle: base.gridTitle,
    gridSummary: base.gridSummary,
    gridPrice: base.gridPrice,
    contactName: structuredData.contactName || structuredData.ownerName || structuredData.agentName || structuredData.contactPerson || "",
    contactAvatarUrl: structuredData.contactAvatarUrl || structuredData.ownerAvatarUrl || structuredData.avatarUrl || "",
    contactPhone: note.phone || structuredData.contactPhone || structuredData.mobile || structuredData.tel || structuredData.contact || structuredData.phone || "",
    contactWechat: structuredData.wechat || structuredData.contactWechat || structuredData.customerWechat || structuredData.weixin || structuredData.wx || ""
  };
}

function decorateSelectedShowcaseItem(item, note, index) {
  const config = (note && note.visibilityConfig) || {};
  const structuredData = (note && note.structuredData) || config.structuredData || {};
  const cardType = (note && note.cardType) || resolveCardType(config);
  return {
    ...item,
    index,
    title: item.displayTitle || (note && (note.title || structuredData.community || structuredData.productName)) || "资料",
    summary: (note && (note.summary || note.primaryValue)) || "",
    coverUrl: note && note.coverUrl,
    badge: (note && (note.badge || note.cardBadge)) || cardTypeLabel(cardType),
    cardType,
    structuredData,
    visibleText: item.visible === false ? "已隐藏" : (note && (note.primaryText || note.gridPrice || note.summary)) || "展示中"
  };
}

function buildPropertyStatus(value) {
  if (value === "rented") return { text: "已租", className: "rented" };
  if (value === "paused") return { text: "暂停推广", className: "paused" };
  return { text: "推广中", className: "active" };
}

function buildPrimaryValue(cardType, data, note) {
  if (cardType === "property_listing") {
    const sale = ["sale", "sell", "出售"].includes(data.listingMode || data.dealType);
    const price = data.price ? (/元|万|\/月|每月/.test(String(data.price)) ? String(data.price) : `${data.price}${sale ? "万元" : "元/月"}`) : "";
    return [price, data.layout].filter(Boolean).join(" · ") || note.summary || "房源信息";
  }
  if (cardType === "groupbuy_product") {
    return [data.price, data.spec].filter(Boolean).join(" · ") || note.summary || "团购商品";
  }
  if (cardType === "business_card") {
    return [data.title, data.company, data.city].filter(Boolean).join(" · ") || note.summary || "个人顾问名片";
  }
  if (cardType === "service_offer") {
    return [data.headline, data.pricingOrTerms || data.cooperationTerms || data.pricingNote].filter(Boolean).join(" · ") || note.summary || "服务/合作";
  }
  if (data.miniapp) {
    return [data.miniapp.displayName || data.miniapp.description, data.miniapp.houseCode ? `房源编码 ${data.miniapp.houseCode}` : ""].filter(Boolean).join(" · ") || note.summary || "";
  }
  return note.summary || note.body || "";
}

function buildSecondaryValue(cardType, data, note) {
  if (cardType === "property_listing") {
    return [data.businessArea, data.address, data.utilities].filter(Boolean).join(" · ") || data.remark || "";
  }
  if (cardType === "groupbuy_product") {
    return [data.pickupMethod, data.pickupLocation, data.deadline].filter(Boolean).join(" · ") || data.remark || "";
  }
  if (cardType === "business_card") {
    return data.serviceScope || data.bio || note.body || "";
  }
  if (cardType === "service_offer") {
    return [data.serviceScope || data.serviceArea, data.pricingOrTerms || data.cooperationTerms || data.pricingNote].filter(Boolean).join(" · ") || data.detailText || data.serviceContent || "";
  }
  if (data.miniapp) {
    return data.miniapp.title || note.body || "";
  }
  return note.body || "";
}

function buildCardBadge(cardType, config) {
  if (config.sourceType === "miniapp") return "小程序";
  return cardTypeLabel(cardType);
}

function buildSuggestionText(suggestions) {
  const labels = {
    property_listing: "房源",
    groupbuy_product: "团购"
  };
  const names = suggestions.map((item) => labels[item.cardType]).filter(Boolean);
  if (!names.length) return "";
  return `可能是：${names.join(" / ")}`;
}

function buildCardAction(cardType) {
  if (cardType === "property_listing") return "转发给好友";
  if (cardType === "groupbuy_product") return "转发给好友";
  if (cardType === "business_card") return "发名片";
  if (cardType === "service_offer") return "发客户";
  return "整理 / 编辑";
}

function buildShowcasePrimaryText(cardType, data, note) {
  if (cardType === "property_listing") {
    return [data.price, data.layout, data.businessArea].filter(Boolean).join(" · ") || note.summary || "";
  }
  if (cardType === "groupbuy_product") {
    return [data.price, data.spec, data.pickupMethod].filter(Boolean).join(" · ") || note.summary || "";
  }
  if (cardType === "business_card") {
    return [data.title, data.company, data.serviceScope].filter(Boolean).join(" · ") || note.summary || "";
  }
  if (cardType === "service_offer") {
    return [data.headline, data.pricingOrTerms || data.cooperationTerms || data.pricingNote, data.serviceScope || data.serviceArea].filter(Boolean).join(" · ") || note.summary || "";
  }
  return note.summary || note.body || "";
}

function buildGridTitle(cardType, data, note) {
  if (cardType === "property_listing") return data.community || note.title || "房源";
  if (cardType === "groupbuy_product") return data.productName || note.title || "商品";
  if (cardType === "business_card") return data.name || note.title || "电子名片";
  if (cardType === "service_offer") return data.serviceName || note.title || "服务/合作";
  return note.title || data.title || "资料";
}

function buildGridSummary(cardType, data, note) {
  if (cardType === "property_listing") {
    return [data.layout, data.area, data.businessArea || data.address].filter(Boolean).join(" | ") || note.summary || "";
  }
  if (cardType === "groupbuy_product") {
    return [data.spec, data.pickupMethod, data.pickupLocation].filter(Boolean).join(" | ") || note.summary || "";
  }
  if (cardType === "business_card") {
    return [data.title, data.company, data.serviceScope].filter(Boolean).join(" | ") || note.summary || "";
  }
  if (cardType === "service_offer") {
    return [data.serviceScope || data.serviceArea, data.pricingOrTerms || data.cooperationTerms || data.pricingNote].filter(Boolean).join(" | ") || note.summary || "";
  }
  return note.summary || note.body || "";
}

function buildGridPrice(cardType, data) {
  if (cardType === "property_listing") {
    if (!data.price) return "";
    if (/元|万|\/月|每月/.test(String(data.price))) return String(data.price);
    return `${data.price}${["sale", "sell", "出售"].includes(data.listingMode || data.dealType) ? "万元" : "元/月"}`;
  }
  if (cardType === "groupbuy_product") return data.price || "";
  if (cardType === "service_offer") return data.pricingOrTerms || data.cooperationTerms || data.pricingNote || "";
  return "";
}

function buildNoteCategoryLabels(note, config) {
  const labels = [];
  const tags = Array.isArray(config.tags) ? config.tags : [];
  const cardType = resolveCardType(config);
  if (cardType === "property_listing") labels.push("房产");
  if (cardType === "groupbuy_product") labels.push("商品", "团购");
  if (cardType === "business_card") labels.push("名片", "顾问");
  if (cardType === "service_offer") labels.push("服务", "销售");
  if (cardType === "link") labels.push("链接");
  if (cardType === "image_ocr") labels.push("图片");
  if (config.systemCategory) labels.push(config.systemCategory);
  tags.forEach((tag) => labels.push(tag));
  const data = config.structuredData || {};
  const text = `${note.title || ""} ${note.summary || ""} ${note.body || ""} ${data.community || ""} ${data.businessArea || ""}`;
  if (/房|小区|户型|租|售|公寓|住宅/.test(text)) labels.push("房产");
  return Array.from(new Set(labels.map((item) => String(item || "").trim()).filter(isUsefulLabel)));
}

module.exports = {
  cardTypeLabel,
  cleanImagePrimaryText,
  decorateNoteForList,
  decorateNoteForShowcasePicker,
  decorateSelectedShowcaseItem,
  getPrimaryImageUrl,
  imagePrimaryTitle,
  isImagePrimaryNote,
  isUsefulLabel
};
