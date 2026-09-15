const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { getCurrentUser, safeAvatarUrl } = require("../../utils/dashboard");
const { getSalesPageTemplate, templateToneClass } = require("../../utils/sales-page-templates");
const { buildBusinessCardShareTitle, buildServiceOfferShareTitle, truncateShareTitle } = require("../../utils/business-card-share");
const { buildNoteShareTitle, buildShareMessage, getNoteShareSnapshotState, getShareImageUrlFromState, prepareNoteShareSnapshot, setShareMenuEnabled, NOTE_SHARE_CARD_STYLE_VERSION } = require("../../plugins/share-snapshot/index");
const { cleanImagePrimaryText, getPrimaryImageUrl, imagePrimaryTitle, isImagePrimaryNote } = require("../../utils/note-display");
const subscription = require("../../services/subscription");
const { getAnonymousVisitorId } = require("../../utils/visitor-identity");

const LAST_PROPERTY_CITY_KEY = "teambuy:lastPropertyCity";
let lastLeadPhoneInMemory = "";

function buildCustomerShareTitle(title) {
  const cleanTitle = String(title || "这份资料").replace(/\s+/g, " ").trim();
  return truncateShareTitle(cleanTitle.includes("｜") ? cleanTitle : `${cleanTitle}｜点开查看完整资料`);
}

function firstDistinctText(excluded, values) {
  const seen = new Set((excluded || []).map((item) => String(item || "").trim()).filter(Boolean));
  return (values || []).map((item) => String(item || "").trim()).find((item) => item && !seen.has(item)) || "";
}

function pad(num) {
  return `${num}`.padStart(2, "0");
}

function formatDateInput(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function formatDateLabel(value) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value || "";
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

function buildAppointmentDraft(offsetDays = 0) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return {
    date: formatDateInput(date),
    time: "10:00",
    remark: ""
  };
}

function inferCityFromText(value) {
  const text = String(value || "");
  const cityMatch = text.match(/([\u4e00-\u9fff]{2,12}市)/);
  if (cityMatch) return cityMatch[1];
  if (text.includes("长沙") || text.includes("湖南")) return "长沙市";
  return "";
}

function readLastPropertyCity() {
  try {
    return wx.getStorageSync(LAST_PROPERTY_CITY_KEY) || "";
  } catch (error) {
    return "";
  }
}

function rememberPropertyCity(value) {
  const city = inferCityFromText(value);
  if (!city) return;
  try {
    wx.setStorageSync(LAST_PROPERTY_CITY_KEY, city);
  } catch (error) {
    // Local memory only improves map matching; ignore failures.
  }
}

function readLastLeadPhone() {
  return lastLeadPhoneInMemory;
}

function getNotePreviewAnonymousId() {
  return getAnonymousVisitorId();
}

function buildViewerPayload(user, fallbackName) {
  if (user) {
    return {
      viewerUserId: user.id,
      nickname: user.nickname || fallbackName || "微信用户",
      avatarUrl: safeAvatarUrl(user.avatarUrl)
    };
  }
  return {
    anonymousId: getNotePreviewAnonymousId(),
    nickname: fallbackName || "匿名客户",
    avatarUrl: ""
  };
}

function createViewSessionId(prefix) {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function createShareId(noteId) {
  return `share_note_${noteId || "note"}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function inferFocusSections(view = {}, maxScrollPercent = 0) {
  const sections = [];
  const text = `${view.title || ""} ${view.summary || ""} ${view.body || ""} ${view.badge || ""}`;
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

function rememberLeadPhone(value) {
  const phone = String(value || "").match(/1[3-9]\d{9}/);
  if (!phone) return;
  lastLeadPhoneInMemory = phone[0];
}

function normalizePropertyStatus(value) {
  if (value === "rented" || value === "paused") return value;
  return "active";
}

function buildAvailability(data, isProperty) {
  if (!isProperty) return null;
  const status = normalizePropertyStatus(data.propertyStatus);
  if (status === "rented") {
    return {
      status,
      title: "该房源已租出",
      desc: "当前不再接收新的电话、留言和预约。"
    };
  }
  if (status === "paused") {
    return {
      status,
      title: "该房源暂停推广",
      desc: "发布者暂时关闭新的咨询和预约。"
    };
  }
  return null;
}

function normalizeSkuConfig(data) {
  const variants = Array.isArray((data || {}).variants) ? data.variants : [];
  if (variants.length) {
    return {
      attributeGroups: [],
      skus: variants.map((variant, index) => ({
        id: variant.id || `variant_${index}`,
        key: variant.id || `variant_${index}`,
        name: variant.name || "默认规格",
        price: Number.isFinite(Number(variant.priceFen)) ? `¥${(Number(variant.priceFen) / 100).toFixed(2).replace(/\.00$/, "").replace(/(\.\d)0$/, "$1")}` : "",
        description: "",
        soldOut: variant.stockStatus === "sold_out"
      }))
    };
  }
  const source = (data && data.skuConfig) || {};
  const skus = Array.isArray(source.skus) ? source.skus : [];
  const attributeGroups = Array.isArray(source.attributeGroups)
    ? source.attributeGroups.map((group, groupIndex) => ({
        id: group.id || `group_${groupIndex}`,
        name: group.name || `规格${groupIndex + 1}`,
        options: (Array.isArray(group.options) ? group.options : []).map((option, optionIndex) => ({
          id: option.id || `option_${groupIndex}_${optionIndex}`,
          label: option.label || option.name || ""
        })).filter((option) => option.label)
      })).filter((group) => group.options.length)
    : [];
  if (skus.length) {
    return {
      attributeGroups,
      skus: skus.map((sku, index) => ({
        id: sku.id || sku.key || `sku_${index}`,
        key: sku.key || sku.id || `sku_${index}`,
        optionIds: Array.isArray(sku.optionIds) && sku.optionIds.length
          ? sku.optionIds
          : String(sku.key || sku.id || `sku_${index}`).split("|").filter(Boolean),
        optionLabels: Array.isArray(sku.optionLabels) ? sku.optionLabels : [],
        name: sku.name || "默认规格",
        price: sku.price || data.price || "",
        description: sku.description || "",
        soldOut: Boolean(sku.soldOut)
      }))
    };
  }
  return {
    attributeGroups: [],
    skus: [{
      id: "default",
      key: "default",
      name: data.spec || data.productName || "默认规格",
      price: data.price || "",
      description: data.pickupMethod || "",
      soldOut: false
    }]
  };
}

function skuOptionIds(sku) {
  if (Array.isArray(sku.optionIds) && sku.optionIds.length) return sku.optionIds;
  return String(sku.key || sku.id || "").split("|").filter(Boolean);
}

function buildSelectedSkuOptions(skuConfig, skuKey) {
  const groups = skuConfig.attributeGroups || [];
  const sku = (skuConfig.skus || []).find((item) => item.key === skuKey || item.id === skuKey);
  const ids = sku ? skuOptionIds(sku) : [];
  return groups.reduce((result, group, index) => {
    if (ids[index]) result[group.id] = ids[index];
    return result;
  }, {});
}

function findSkuBySelectedOptions(skuConfig, selectedOptions) {
  const groups = skuConfig.attributeGroups || [];
  if (!groups.length) return null;
  const selectedIds = groups.map((group) => selectedOptions[group.id]).filter(Boolean);
  if (selectedIds.length !== groups.length) return null;
  return (skuConfig.skus || []).find((sku) => {
    const ids = skuOptionIds(sku);
    return groups.every((group, index) => ids[index] === selectedOptions[group.id]);
  }) || null;
}

function buildSkuSelectionGroups(skuConfig, selectedOptions) {
  const groups = skuConfig.attributeGroups || [];
  const skus = skuConfig.skus || [];
  return groups.map((group, groupIndex) => ({
    ...group,
    options: (group.options || []).map((option) => {
      const available = skus.some((sku) => {
        if (sku.soldOut) return false;
        const ids = skuOptionIds(sku);
        return ids[groupIndex] === option.id;
      });
      return {
        ...option,
        active: selectedOptions[group.id] === option.id,
        disabled: !available
      };
    })
  }));
}

function buildProductPriceText(skuConfig, fallback) {
  const prices = (skuConfig.skus || [])
    .filter((sku) => !sku.soldOut && sku.price)
    .map((sku) => String(sku.price || "").trim())
    .filter(Boolean);
  const unique = Array.from(new Set(prices)).sort((left, right) => {
    const leftValue = Number(String(left).replace(/[^\d.]/g, ""));
    const rightValue = Number(String(right).replace(/[^\d.]/g, ""));
    return leftValue - rightValue;
  });
  if (!unique.length) return fallback || "";
  if (unique.length === 1) return unique[0];
  return `${unique[0]} 起`;
}

function splitFeatureText(value) {
  return String(value || "")
    .split(/[\n,，、/|]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 6);
}

function buildServiceTags(data, config, isBusinessCard, isServiceOffer) {
  const tags = Array.isArray(config.tags) ? config.tags : [];
  const fieldTags = isBusinessCard
    ? splitFeatureText(data.serviceScope)
    : splitFeatureText(data.targetAudience || data.serviceArea);
  const fallback = isBusinessCard ? ["顾问", "咨询"] : ["服务", "预约"];
  return Array.from(new Set([...tags, ...fieldTags, ...fallback].filter(Boolean))).slice(0, 6);
}

function buildSalesSections(data, note, isBusinessCard, isServiceOffer) {
  if (isBusinessCard) {
    return [
      { key: "intro", title: "服务介绍", body: data.bio || note.body || note.summary || "" },
      { key: "scope", title: "服务范围", body: data.serviceScope || "" },
      { key: "city", title: "服务区域", body: data.city || "" }
    ].filter((item) => item.body);
  }
  if (isServiceOffer) {
    const detailText = data.detailText || data.serviceContent || note.body || "";
    const headline = data.serviceSummary || data.headline || "";
    const serviceScope = data.serviceScope || data.serviceArea || "";
    const pricingOrTerms = data.pricingOrTerms || data.cooperationTerms || data.pricingNote || "";
    return [
      { key: "audience", title: "适合谁", body: data.targetAudience || "" },
      { key: "value", title: "能帮你什么", body: headline },
      { key: "content", title: "服务内容", body: detailText },
      { key: "scope", title: "服务范围", body: serviceScope },
      { key: "process", title: "服务流程", body: data.serviceProcess || "" },
      { key: "pricing", title: "合作方式与报价", body: pricingOrTerms },
      { key: "cases", title: "案例 / 成果", body: data.caseHighlights || note.summary || "" },
      { key: "appointment", title: "预约说明", body: data.appointmentNote || "" }
    ].filter((item) => item.body);
  }
  return [];
}

function buildSalesHighlights(data, isBusinessCard, isServiceOffer) {
  if (isBusinessCard) {
    return [
      { label: "身份", value: data.title || "顾问" },
      { label: "机构", value: data.company || "个人服务" },
      { label: "区域", value: data.city || "线上沟通" }
    ].filter((item) => item.value);
  }
  if (isServiceOffer) {
    const serviceScope = data.serviceScope || data.serviceArea || "";
    const pricingOrTerms = data.pricingOrTerms || data.cooperationTerms || data.pricingNote || "";
    return [
      { label: "服务对象", value: data.targetAudience || "按需求沟通" },
      { label: "服务范围", value: serviceScope || "按需求定制" },
      { label: "合作方式", value: pricingOrTerms || "沟通确认" }
    ].filter((item) => item.value);
  }
  return [];
}

function businessCardResourceTypeLabel(cardType) {
  return ({
    property_listing: "房源",
    groupbuy_product: "商品",
    service_offer: "服务",
    text_note: "资料",
    image_ocr: "图片",
    pdf_document: "PDF",
    link: "链接",
    article: "文章"
  })[cardType] || "资料";
}

function businessCardAttachmentTypeLabel(type) {
  return ({ image: "图片", pdf: "PDF", link: "链接" })[type] || "资料";
}

function buildBusinessCardDetail(data, note) {
  const config = note.visibilityConfig || {};
  const opportunity = config.businessOpportunity || {};
  const phone = data.phone || note.phone || "";
  const wechat = data.wechat || data.contactWechat || "";
  const email = data.email || data.mail || "";
  const qrCodeUrl = data.wechatQrUrl || data.qrCodeUrl || data.wechatQrCodeUrl || "";
  const keywords = (Array.isArray(data.serviceKeywords) ? data.serviceKeywords : splitFeatureText(data.serviceKeywords || data.serviceScope)).filter(Boolean).slice(0, 6);
  const industryTags = Array.from(new Set([
    opportunity.industry,
    opportunity.subIndustry,
    ...(Array.isArray(opportunity.industryTags) ? opportunity.industryTags : []),
    data.industry,
    data.subIndustry,
    ...(Array.isArray(data.industryTags) ? data.industryTags : [])
  ].map((item) => String(item || "").trim()).filter(Boolean))).slice(0, 8);
  const cooperationIntent = opportunity.cooperationIntent || data.cooperationIntent || {};
  const intentExpiry = cooperationIntent.expiresAt || "";
  let intentActive = Boolean(cooperationIntent.text || cooperationIntent.summary);
  if (intentExpiry) {
    const expiryTime = new Date(intentExpiry).getTime();
    intentActive = Number.isFinite(expiryTime) && expiryTime > Date.now();
  }
  const featuredResources = (note.featuredResources || []).slice(0, 3).map((item) => ({
    ...item,
    typeLabel: businessCardResourceTypeLabel(item.cardType),
    typeInitial: businessCardResourceTypeLabel(item.cardType).slice(0, 1),
    media: (Array.isArray(item.media) ? item.media : []).slice(0, 6).map((media) => ({
      ...media,
      typeLabel: businessCardAttachmentTypeLabel(media.type)
    }))
  }));
  const hasContact = Boolean(phone || wechat || email || data.website || data.companyWebsite || data.websiteUrl || data.url || qrCodeUrl);
  return {
    headline: data.headline || "",
    intro: data.bio || "",
    keywords,
    industryTags,
    cooperationIntent: {
      direction: cooperationIntent.direction || "",
      text: cooperationIntent.text || cooperationIntent.summary || "",
      expiresAt: intentExpiry,
      active: intentActive
    },
    cityText: data.city || "",
    phone,
    wechat,
    email,
    website: data.website || data.companyWebsite || data.websiteUrl || data.url || "",
    qrCodeUrl,
    hasContact,
    featuredResources
  };
}

function buildCommunicationActions(actions, context = {}) {
  const labels = {
    contact: { icon: "电", title: "打电话", primaryTitle: "立即电话", desc: "直接拨打发布者电话" },
    private: { icon: "微", title: "微信沟通", primaryTitle: "添加微信", desc: "复制微信号或查看二维码" },
    message: { icon: "聊", title: context.isGroupbuy ? "咨询购买" : "留言咨询", desc: "站内留言给发布者", primaryTitle: "立即咨询" },
    lead: { icon: "留", title: "留下需求", primaryTitle: "留下需求", desc: "留下联系方式和需求" },
    appointment: { icon: "约", title: context.isProperty ? "预约看房" : "预约沟通", primaryTitle: context.isProperty ? "预约看房" : "预约沟通", desc: "选择日期和时间" },
    email: { icon: "邮", title: "邮箱联系", primaryTitle: "邮箱联系", desc: "复制邮箱地址" }
  };
  const orderedKeys = ["contact", "private", "message", "lead", "appointment", "email"];
  return orderedKeys
    .map((key) => {
      const source = (actions || []).find((item) => item.key === key);
      return source && labels[key] ? { ...source, ...labels[key], key } : null;
    })
    .filter(Boolean);
}

function buildServiceOfferMetricCards(templateId, audienceBullets, serviceBullets, processSteps, contactCount) {
  if (templateId === "service_pricing") {
    return [
      { value: `${serviceBullets.length}项`, label: "服务范围" },
      { value: `${processSteps.length}步`, label: "交付流程" },
      { value: `${contactCount}种`, label: "联系渠道" }
    ];
  }
  if (templateId === "service_campaign") {
    return [
      { value: `${audienceBullets.length}类`, label: "适合人群" },
      { value: `${processSteps.length}步`, label: "报名流程" },
      { value: `${contactCount}种`, label: "报名方式" }
    ];
  }
  if (templateId === "service_case_story") {
    return [
      { value: `${serviceBullets.length}项`, label: "服务亮点" },
      { value: `${Math.max(1, audienceBullets.length)}类`, label: "适合客户" },
      { value: `${Math.max(1, processSteps.length)}步`, label: "服务路径" }
    ];
  }
  return [
    { value: `${audienceBullets.length}类`, label: "适合人群" },
    { value: `${serviceBullets.length}项`, label: "服务内容" },
    { value: `${contactCount}种`, label: "联系渠道" }
  ];
}

function buildServiceOfferDetail(data, note, template, galleryImages) {
  const phone = data.phone || data.contactPhone || data.contact || note.phone || "";
  const wechat = data.wechat || data.contactWechat || "";
  const qrCodeUrl = data.wechatQrUrl || data.qrCodeUrl || data.wechatQrCodeUrl || "";
  const email = data.email || data.mail || "";
  const website = data.website || data.companyWebsite || data.websiteUrl || "";
  const hasNewDetail = Object.prototype.hasOwnProperty.call(data, "detailText");
  const legacyDetail = [
    data.detailText,
    data.serviceContent,
    data.targetAudience,
    data.serviceProcess,
    data.caseHighlights,
    data.appointmentNote
  ].map((item) => String(item || "").trim()).filter(Boolean);
  const detailText = Array.from(new Set(legacyDetail)).join("\n\n") || (hasNewDetail ? "" : note.body || "");
  const serviceScope = data.serviceScope || data.serviceArea || "";
  const pricingOrTerms = data.pricingOrTerms || data.cooperationTerms || data.pricingNote || "";
  const coverUrl = data.coverUrl || note.coverUrl || galleryImages[0] || "";
  return {
    serviceName: data.serviceName || note.title || "服务/合作",
    headline: data.serviceSummary || data.headline || note.summary || "",
    detailText,
    serviceScope,
    pricingOrTerms,
    primaryAction: "consult",
    phone,
    wechat,
    qrCodeUrl,
    email,
    website,
    coverUrl,
    publisherName: data.displayName || data.name || "发布者",
    publisherRole: [data.jobTitle || data.title, data.company].filter(Boolean).join(" · "),
    publisherAvatarUrl: data.avatarUrl || "",
    publisherInitial: String(data.displayName || data.name || "发").slice(0, 1)
  };
}

function buildServiceOfferPrimaryActions(actions, detail = {}) {
  const map = {
    contact: { icon: "电", shortTitle: detail.primaryAction || "电话咨询" },
    private: { icon: "微", shortTitle: detail.secondaryAction || "微信咨询" },
    appointment: { icon: "约", shortTitle: "预约沟通" },
    lead: { icon: "留", shortTitle: "留下信息" }
  };
  const keys = ["contact", "private", "appointment", "lead"];
  return keys
    .map((key) => actions.find((item) => item.key === key))
    .filter(Boolean)
    .map((item) => ({
      ...item,
      icon: map[item.key] ? map[item.key].icon : "咨",
      shortTitle: map[item.key] ? map[item.key].shortTitle : item.title
    }));
}

function buildServiceOfferSecondaryActions(actions) {
  const map = {
    email: "邮箱联系",
    message: "发消息"
  };
  return actions
    .filter((item) => ["email", "message"].includes(item.key))
    .map((item) => ({
      ...item,
      shortTitle: map[item.key] || item.title
    }));
}

function buildBusinessCardHeroView(data, note, title, subtitle, templateName, avatarUrl, template) {
  const phone = data.phone || note.phone || "";
  const wechat = data.wechat || data.contactWechat || "";
  const email = data.email || data.mail || "";
  return {
    layoutId: "business_card",
    name: data.name || title || "",
    role: data.title || "",
    company: data.company || "",
    serviceScope: data.headline || subtitle || note.summary || "",
    contactLine: [phone, wechat, email].filter(Boolean).join(" · "),
    templateName: templateName || "电子名片",
    templateId: (template && template.id) || "",
    tone: (template && template.tone) || "",
    avatarUrl: data.avatarUrl || note.coverUrl || avatarUrl || "",
    initial: String(title || "名").slice(0, 1)
  };
}

function resolveSalesTemplate(config, isBusinessCard) {
  const fallbackId = isBusinessCard ? "consultant_classic" : "service_consultation";
  const expectedType = isBusinessCard ? "business_card" : "service_offer";
  const candidate = config.displayTemplate ? getSalesPageTemplate(config.displayTemplate) : null;
  if (candidate && candidate.cardType === expectedType) return candidate;
  return getSalesPageTemplate(fallbackId);
}

function buildView(note) {
  const config = note.visibilityConfig || {};
  const data = config.structuredData || {};
  const candidateShareSnapshot = config.shareSnapshot || {};
  const shareSnapshot = String(candidateShareSnapshot.styleId || "") === NOTE_SHARE_CARD_STYLE_VERSION
    && candidateShareSnapshot.renderer === "backend"
    ? candidateShareSnapshot
    : {};
  const ownerProfile = note.ownerProfile || {};
  const miniapp = buildMiniappInfo(data);
  const cardType = config.cardType || "text_note";
  const isProperty = cardType === "property_listing";
  const isGroupbuy = cardType === "groupbuy_product";
  const isBusinessCard = cardType === "business_card";
  const isServiceOffer = cardType === "service_offer";
  const isArticle = cardType === "article";
  const isServiceCard = isBusinessCard || isServiceOffer;
  const isImageNote = isImagePrimaryNote(note);
  const contentBlocks = buildContentBlocks(note);
  const isContentStream = !isProperty && !isGroupbuy && !isBusinessCard && !isServiceOffer && !isArticle
    && contentBlocks.some((item) => item.type === "text" && String(item.text || "").trim())
    && contentBlocks.some((item) => item.type === "image" && item.url);
  const imageCaption = isImageNote
    ? cleanImagePrimaryText(note.body || data.rawText || (data.ocr || {}).text || "")
    : "";
  const imageTitle = isImageNote ? imagePrimaryTitle(note, imageCaption) : "";
  const propertyMode = ["sale", "sell", "出售"].includes(data.listingMode || data.dealType) ? "sale" : "rent";
  const propertyPriceText = isProperty && data.price
    ? (/元|万|\/月|每月/.test(String(data.price)) ? String(data.price) : `${data.price}${propertyMode === "sale" ? "万元" : "元/月"}`)
    : "";
  const identityData = isBusinessCard ? {
    ...data,
    name: ownerProfile.displayName || data.name,
    title: ownerProfile.jobTitle || data.title,
    company: ownerProfile.company || data.company,
    city: ownerProfile.city || data.city,
    avatarUrl: ownerProfile.avatarUrl || data.avatarUrl,
    phone: ownerProfile.phone || data.phone,
    wechat: ownerProfile.wechat || data.wechat,
    wechatQrUrl: ownerProfile.wechatQrUrl || data.wechatQrUrl || data.qrCodeUrl,
    email: ownerProfile.email || data.email,
    website: ownerProfile.website || data.website
  } : data;
  const serviceIdentityData = isServiceOffer ? {
    ...data,
    displayName: ownerProfile.displayName || data.displayName,
    jobTitle: ownerProfile.jobTitle || data.jobTitle,
    company: ownerProfile.company || data.company,
    avatarUrl: ownerProfile.avatarUrl || data.avatarUrl,
    phone: ownerProfile.phone || data.phone,
    wechat: ownerProfile.wechat || data.wechat,
    wechatQrUrl: ownerProfile.wechatQrUrl || data.wechatQrUrl || data.qrCodeUrl,
    email: ownerProfile.email || data.email,
    website: ownerProfile.website || data.website,
    city: ownerProfile.city || data.city
  } : data;
  const template = isServiceOffer ? resolveSalesTemplate(config, false) : null;
  const isMiniapp = miniapp.visible && config.sourceType === "miniapp";
  const skuConfig = normalizeSkuConfig(data);
  const productPriceText = buildProductPriceText(skuConfig, data.price);
  const productSalesMode = data.salesMode === "relay" ? "relay" : "inquiry";
  const fulfillment = data.fulfillment || {};
  const pickupLocation = fulfillment.pickupLocation || {};
  const fulfillmentLabels = (fulfillment.methods || []).map((item) => ({
    shipping: "快递",
    local_delivery: "同城配送",
    store_pickup: "到店自提",
    community_pickup: "小区自提",
    offline_contact: "线下联系"
  })[item]).filter(Boolean);
  const title = isProperty
    ? data.community || note.title
    : isGroupbuy
      ? data.productName || note.title
      : isBusinessCard
        ? ownerProfile.displayName || data.name || note.title
        : isServiceOffer
          ? data.serviceName || note.title
          : isImageNote
            ? imageTitle
            : miniapp.title || note.title;
  let subtitle = isProperty
    ? [propertyPriceText, data.layout, data.area].filter(Boolean).join(" · ")
    : isGroupbuy
      ? [productPriceText, data.headline, productSalesMode === "relay" ? "团购接龙" : "商品"].filter(Boolean).join(" · ")
      : isBusinessCard
        ? [ownerProfile.jobTitle || data.title, ownerProfile.company || data.company, data.serviceScope].filter(Boolean).join(" · ")
        : isServiceOffer
          ? [data.serviceSummary || data.headline, data.cooperationTerms || data.pricingNote, data.serviceScope || data.serviceArea].filter(Boolean).join(" · ")
          : isImageNote
            ? (imageCaption !== imageTitle ? imageCaption : "")
            : isMiniapp ? [miniapp.sourceName, miniapp.houseCode ? `房源编码 ${miniapp.houseCode}` : ""].filter(Boolean).join(" · ") : note.summary || "";
  if (String(subtitle || "").trim() === String(title || "").trim()) subtitle = "";
  const mapLocation = isGroupbuy ? buildMapLocation({
    mapLocation: pickupLocation,
    address: pickupLocation.address || pickupLocation.name || ""
  }) : buildMapLocation(data);
  const coverUrl = isImageNote
    ? getPrimaryImageUrl(note) || data.avatarUrl || data.qrCodeUrl || ""
    : note.coverUrl || data.avatarUrl || data.qrCodeUrl || ((note.media || []).find((item) => item.type === "image") || {}).url || "";
  const galleryImages = buildGalleryImages(note, coverUrl);
  const galleryVideos = buildGalleryVideos(note);
  const address = isProperty ? data.address || data.businessArea || "" : isGroupbuy ? pickupLocation.address || pickupLocation.name || data.pickupLocation || "" : "";
  const contact = ownerProfile.phone || data.phone || data.contactPhone || data.contact || note.phone || "";
  const wechat = ownerProfile.wechat || data.wechat || data.contactWechat || "";
  const email = ownerProfile.email || data.email || data.mail || "";
  const website = ownerProfile.website || data.website || data.companyWebsite || data.websiteUrl || "";
  const rows = isProperty
    ? [
        ["户型", data.layout],
        ["面积", data.area],
        [propertyMode === "sale" ? "售价" : "租金", propertyPriceText],
        ["水电物业", data.utilities],
        ["位置", address],
        ["服务费", data.serviceFee]
      ]
    : isGroupbuy
      ? [
          ["价格", productPriceText],
          ["销售方式", productSalesMode === "relay" ? "团购接龙" : "商品"],
          ["配送 / 自提", fulfillmentLabels.join("、") || data.pickupMethod],
          ["自提位置", address],
          ["可领取时间", fulfillment.availableTime],
          ["截止时间", productSalesMode === "relay" ? (data.relayConfig || {}).deadlineAt || data.deadline : ""],
          ["库存提示", productSalesMode === "relay" ? (data.relayConfig || {}).stockNote || data.stockNote : ""]
        ]
      : isBusinessCard
        ? [
            ["职位", ownerProfile.jobTitle || data.title],
            ["公司 / 门店", ownerProfile.company || data.company],
            ["服务范围", data.serviceScope],
            ["城市 / 区域", ownerProfile.city || data.city],
            ["电话", contact],
            ["微信", wechat]
          ]
        : isServiceOffer
          ? [
              ["服务范围", data.serviceScope || data.serviceArea],
              ["价格或合作条件", data.pricingOrTerms || data.cooperationTerms || data.pricingNote]
            ]
          : isImageNote
            ? [["说明", imageCaption]]
          : isMiniapp
            ? [["来源", miniapp.sourceName], ["房源编码", miniapp.houseCode], ["城市编码", miniapp.cityId]]
            : [["摘要", note.summary], ["正文", note.body]];
  const conversion = config.conversionConfig || {};
  const availability = buildAvailability(data, isProperty);
  const canConvert = !availability;
  const actions = [];
  if (miniapp.visible) actions.push({ key: "miniapp", title: miniapp.buttonText, desc: "打开原小程序详情" });
  if (canConvert && conversion.showContactPhone && contact) actions.push({ key: "contact", title: "电话咨询", desc: "拨打或复制电话" });
  const shouldCollectLeads = isBusinessCard || conversion.collectLeads;
  if (canConvert && shouldCollectLeads) actions.push({ key: "lead", title: "留下电话/微信", desc: "方便发布者回访" });
  if (canConvert && isProperty && conversion.enableAppointment) actions.push({ key: "appointment", title: "预约看房", desc: "选择日期和时间" });
  if (canConvert && conversion.enablePrivateConsultation && (wechat || ownerProfile.wechatQrUrl || data.wechatQrUrl || data.qrCodeUrl)) actions.push({ key: "private", title: "微信咨询", desc: "复制发布者微信/电话" });
  if (canConvert && isBusinessCard && email) actions.push({ key: "email", title: "邮箱联系", desc: "复制邮箱地址" });
  if (canConvert && conversion.enableLightScrm) actions.push({ key: "message", title: isGroupbuy ? "咨询购买" : "留言咨询", desc: "站内留言给发布者" });
  if ((isProperty || isGroupbuy) && address) actions.push({ key: "map", title: isGroupbuy ? "导航到自提点" : "地图定位", desc: mapLocation.hasPoint ? "打开腾讯地图" : "按地址搜索" });
  const communicationKeys = new Set(["contact", "private", "message", "lead", "appointment", "email"]);
  const communicationActions = buildCommunicationActions(actions, { isProperty, isGroupbuy });
  const sceneActions = actions.filter((item) => !communicationKeys.has(item.key));
  const primaryCommunicationAction = communicationActions.find((item) => item.key === "message")
    || communicationActions.find((item) => item.key === "lead")
    || communicationActions[0]
    || null;
  const serviceTags = buildServiceTags(data, config, isBusinessCard, isServiceOffer);
  const salesSections = buildSalesSections(data, note, isBusinessCard, isServiceOffer);
  const salesHighlights = buildSalesHighlights(data, isBusinessCard, isServiceOffer);
  const templateName = config.displayTemplateName || (template && template.name) || "";
  const businessCardHero = isBusinessCard ? buildBusinessCardHeroView(identityData, note, title, subtitle, templateName, coverUrl, template) : null;
  const businessCardDetail = isBusinessCard ? buildBusinessCardDetail(identityData, note) : null;
  const serviceOfferDetail = isServiceOffer ? buildServiceOfferDetail(serviceIdentityData, note, template, galleryImages) : null;
  const serviceOfferPrimaryActions = isServiceOffer ? buildServiceOfferPrimaryActions(actions, serviceOfferDetail || {}) : [];
  const serviceOfferSecondaryActions = isServiceOffer ? buildServiceOfferSecondaryActions(actions) : [];
  const shareTitle = isBusinessCard
    ? [title, data.title, data.company].filter(Boolean).join(" · ") || "电子名片"
    : isServiceOffer
      ? [title, data.headline].filter(Boolean).join(" · ") || "服务方案"
      : isProperty
        ? buildPropertyShareTitle(title, data)
      : isGroupbuy
        ? buildProductShareTitle(title, data, productPriceText)
      : title || "资料详情";
  return {
    title,
    shareTitle,
    ownerUserId: note.ownerUserId || "",
    revision: note.revision || 0,
    shareSnapshotUrl: shareSnapshot.status === "ready" ? shareSnapshot.url || "" : "",
    subtitle,
    isProperty,
    isGroupbuy,
    isBusinessCard,
    isServiceOffer,
    isArticle,
    isImageNote,
    isContentStream,
    contentBlocks,
    imageCaption,
    isTextNote: cardType === "text_note" && !isImageNote,
    isServiceCard,
    templateId: isBusinessCard ? ((config.displayConfig || {}).styleId || "business_blue") : template ? template.id : "",
    templateName,
    templateScene: config.displayTemplateScene || (template && template.scene) || "",
    templateToneClass: isBusinessCard ? `business-style-${((config.displayConfig || {}).styleId || "business_blue")}` : template ? templateToneClass(template) : "",
    serviceTags,
    salesSections,
    salesHighlights,
    businessCardDetail,
    businessCardContactLocked: Boolean(note.businessCardContactLocked),
    serviceOfferDetail,
    serviceOfferPrimaryActions,
    serviceOfferSecondaryActions,
    headline: data.serviceSummary || data.headline || note.summary || "",
    avatarUrl: ownerProfile.avatarUrl || data.avatarUrl || note.coverUrl || coverUrl || "",
    avatarInitial: String(title || "名").slice(0, 1),
    businessCardHero,
    company: ownerProfile.company || data.company || "",
    position: ownerProfile.jobTitle || data.title || "",
    city: ownerProfile.city || data.city || data.serviceArea || "",
    enableGroupRelay: productSalesMode === "relay",
    orderButtonText: productSalesMode === "relay" ? "参加接龙" : "咨询购买",
    badge: isProperty ? "房源" : isGroupbuy ? "商品" : isBusinessCard ? "名片" : isServiceOffer ? "服务" : isMiniapp ? "小程序房源" : "资料",
    articleDetail: isArticle ? {
      sourceUrl: config.sourceUrl || data.url || "",
      sourceName: config.sourceName || "网页链接",
      sourceLabel: config.sourceLabel || "文章链接",
      recommendation: data.salesRecommendation || data.recommendation || "",
      description: data.contentDescription || data.description || note.summary || "",
      coverUrl
    } : null,
    propertyHighlightChips: isProperty ? [propertyPriceText ? `${propertyMode === "sale" ? "售价" : "租金"} ${propertyPriceText}` : "", data.layout ? `户型 ${data.layout}` : ""].filter(Boolean) : [],
    coverUrl,
    galleryImages,
    galleryVideos,
    attachments: (note.media || []).filter((item) => {
      if (!["image", "pdf", "link"].includes(item.type)) return false;
      if (item.type !== "image") return true;
      return !isImageNote && !isGroupbuy && !isProperty && !isServiceOffer;
    }),
    rows: rows.filter((item) => {
      if (!item[1]) return false;
      if (isProperty || isGroupbuy || isBusinessCard || isServiceOffer || isMiniapp) return true;
      const value = String(item[1] || "").trim();
      return value !== String(title || "").trim() && value !== String(subtitle || "").trim();
    }).map(([label, value]) => ({ label, value })),
    remark: firstDistinctText([title, subtitle], [data.bio, data.caseHighlights, data.remark, note.summary, note.body]),
    availability,
    actions,
    communicationActions,
    primaryCommunicationAction,
    communicationHint: isProperty
      ? "先电话或留言，房源详情还可以预约看房"
      : isGroupbuy
        ? "咨询规格、价格或配送方式"
        : "电话、微信、留言都可以直接发起",
    sceneActions,
    hasMap: (isProperty || isGroupbuy) && Boolean(address),
    skuConfig,
    selectedSku: (skuConfig.skus || []).find((item) => !item.soldOut) || (skuConfig.skus || [])[0] || null,
    miniapp,
    contact,
    wechat,
    wechatQrUrl: ownerProfile.wechatQrUrl || data.wechatQrUrl || data.qrCodeUrl || data.wechatQrCodeUrl || "",
    publisherName: ownerProfile.displayName || data.ownerName || data.agentName || data.contactName || "",
    publisherRole: [ownerProfile.jobTitle, ownerProfile.company].filter(Boolean).join(" · "),
    email,
    website,
    address,
    mapLocation,
    mapCommunity: isProperty ? String(data.community || "") : ""
  };
}

function buildMiniappInfo(data) {
  const miniapp = (data && data.miniapp) || {};
  const appId = miniapp.appid || "";
  const path = miniapp.pagePath || "";
  const sourceName = miniapp.displayName || miniapp.description || "小程序";
  return {
    visible: Boolean(appId && path),
    appId,
    path,
    title: miniapp.title || "",
    sourceName,
    houseCode: miniapp.houseCode || "",
    cityId: miniapp.cityId || "",
    buttonText: sourceName.includes("贝壳") ? "查看贝壳原房源" : "打开原小程序"
  };
}

function buildGalleryImages(note, coverUrl) {
  const data = ((note.visibilityConfig || {}).structuredData || {});
  const structuredImages = data.images;
  const urls = [
    ...(Array.isArray(note.media) ? note.media.filter((item) => item.type === "image").map((item) => item.url) : []),
    ...(Array.isArray(structuredImages) ? structuredImages : []),
    data.qrCodeUrl
  ].filter(Boolean);
  return Array.from(new Set(urls.filter((url) => url !== coverUrl)));
}

function buildPropertyShareTitle(title, data = {}) {
  const chips = [data.price, data.layout].filter(Boolean);
  const headline = title || "房源资料";
  return chips.length ? `${headline}\n${chips.join(" · ")}` : headline;
}

function buildProductShareTitle(title, data = {}, priceText = "") {
  const price = String(priceText || data.price || "").trim();
  const productName = title || data.productName || "商品资料";
  return [price, productName].filter(Boolean).join(" ");
}

function buildGalleryVideos(note) {
  const urls = Array.isArray(note.media)
    ? note.media.filter((item) => item.type === "video").map((item) => item.url)
    : [];
  return Array.from(new Set(urls.filter(Boolean)));
}

function buildContentBlocks(note) {
  const explicit = Array.isArray(note.contentBlocks) ? note.contentBlocks : [];
  if (explicit.length) {
    return explicit
      .filter((item) => item && ["text", "image", "pdf", "link"].includes(item.type))
      .map((item, index) => ({
        ...item,
        sortOrder: Number.isFinite(Number(item.sortOrder)) ? Number(item.sortOrder) : index
      }))
      .sort((a, b) => a.sortOrder - b.sortOrder);
  }
  const blocks = [];
  const body = String(note.body || "").trim();
  if (body) blocks.push({ id: "legacy-text", type: "text", text: body, sortOrder: 0 });
  (Array.isArray(note.media) ? note.media : [])
    .filter((item) => item && item.url && ["image", "pdf", "link"].includes(item.type))
    .sort((a, b) => Number(a.sortOrder || 0) - Number(b.sortOrder || 0))
    .forEach((item, index) => blocks.push({ ...item, sortOrder: blocks.length + index }));
  return blocks;
}

function buildMapLocation(data) {
  const location = data.mapLocation || {};
  const latitude = Number(location.latitude);
  const longitude = Number(location.longitude);
  const address = location.address || data.address || data.businessArea || "";
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return {
      hasPoint: false,
      latitude: 0,
      longitude: 0,
      name: location.name || "",
      address,
      markers: []
    };
  }
  return {
    hasPoint: true,
    latitude,
    longitude,
    name: location.name || address || "房源位置",
    address,
    markers: [{
      id: 1,
      latitude,
      longitude,
      title: location.name || address || "房源位置",
      label: {
        content: "🏠",
        color: "#17633a",
        fontSize: 22,
        anchorX: -8,
        anchorY: -42,
        borderWidth: 1,
        borderColor: "#17633a",
        borderRadius: 6,
        bgColor: "#ffffff",
        padding: 4
      },
      callout: {
        content: "🏠 房源位置",
        color: "#172033",
        fontSize: 13,
        borderRadius: 6,
        bgColor: "#ffffff",
        padding: 8,
        display: "ALWAYS"
      }
    }]
  };
}

function simplifyMapAddress(value) {
  return String(value || "")
    .replace(/[，,]/g, " ")
    .replace(/(?:\d+|[一二三四五六七八九十百]+)栋(?:\d+|[一二三四五六七八九十百]+)?(?:号|室)?[^\s]*$/u, "")
    .replace(/(?:\d+|[一二三四五六七八九十百]+)(?:号|室)[^\s]*$/u, "")
    .replace(/\s+/g, " ")
    .trim();
}

function buildMapAddressCandidates(view = {}) {
  const address = String(view.address || "").trim();
  const location = view.mapLocation || {};
  const candidates = [
    address,
    simplifyMapAddress(address),
    String(location.address || "").trim(),
    simplifyMapAddress(location.address || "")
  ];
  const community = String(view.mapCommunity || "").trim();
  const simpleCommunity = community.replace(/\d+\s*(?:户型|房源|栋|号|室).*$/u, "").trim();
  if (simpleCommunity) candidates.push(simpleCommunity);
  return candidates.filter((item, index, items) => item && items.indexOf(item) === index);
}

function inferMapRegion(address) {
  const text = String(address || "");
  const remembered = readLastPropertyCity();
  if (remembered) return remembered;
  const city = inferCityFromText(text);
  if (city) return city;
  if (text.includes("长沙")) return "长沙市";
  if (text.includes("湖南")) return "湖南省";
  return "";
}

function enrichAddressWithCity(address) {
  const value = String(address || "").trim();
  if (!value) return "";
  const city = inferCityFromText(value) || readLastPropertyCity();
  if (city && !value.includes(city) && !value.includes(city.replace("市", ""))) {
    return `${city} ${value}`;
  }
  return value;
}

Page({
  data: {
    noteId: "",
    notePayload: null,
    user: null,
    view: null,
    viewRecorded: false,
    viewSessionId: "",
    pageEnterAt: 0,
    maxScrollPercent: 0,
    resolvingMap: false,
    showLeadForm: false,
    showAppointmentForm: false,
    leadDraft: {
      name: "",
      phone: "",
      wechat: "",
      remark: ""
    },
    appointmentDraft: buildAppointmentDraft(0),
    leadSubmittedText: "",
    appointmentText: "",
    relaySubmitted: false,
    productOrderSubmitted: false,
    productOrderStatusText: "",
    selectedContactCard: null,
    showRelayForm: false,
    showOrderSheet: false,
    selectedSkuKey: "",
    selectedSkuOptions: {},
    skuSelectionGroups: [],
    shareImageReady: false,
    shareImageState: "missing",
    shareStatusText: "分享图准备中",
    publicLoadError: false,
    publicLoadErrorKind: "",
    publicLoadErrorTitle: "",
    publicLoadErrorMessage: "",
    openedStandalone: false,
    previewMode: false,
    isOwnerViewing: false,
    pendingAction: "",
    relayDraft: {
      quantity: 1,
      receiverName: "",
      phone: "",
      address: "",
      wechat: "",
      remark: ""
    },
    actionStatus: {},
    submittingAction: ""
  },
  onLoad(options) {
    setShareMenuEnabled(false);
    const pages = getCurrentPages ? getCurrentPages() : [];
    this.setData({
      noteId: options.id || "",
      "leadDraft.phone": readLastLeadPhone(),
      openedStandalone: pages.length <= 1,
      viewSessionId: createViewSessionId("note_view"),
      pageEnterAt: Date.now(),
      maxScrollPercent: 0,
      previewMode: options.preview === "1" || options.preview === "true",
      shareId: options.sid || "",
      shareFromUserId: options.from || "",
      shareScene: options.src || options.scene || "",
      referrer: options.ref || "",
      pendingAction: options.action || ""
    });
  },
  onShow() {
    const user = getCurrentUser();
    this.setData({ user });
    this.loadNote();
  },
  async loadNote() {
    const { noteId } = this.data;
    if (!noteId) return;
    const requestSeq = (this._publicNoteRequestSeq || 0) + 1;
    this._publicNoteRequestSeq = requestSeq;
    const isCurrentRequest = () => requestSeq === this._publicNoteRequestSeq;
    try {
      const owner = this.data.user || getCurrentUser();
      const ownerPreview = Boolean(this.data.previewMode && owner && owner.id);
      // The editor's “完整预览” saves a private draft and then opens this
      // page with preview=1. A private draft cannot be read through the
      // public endpoint, which used to produce the misleading “资料已停止
      // 分享” screen even though the card itself was still being edited.
      const res = ownerPreview
        ? await api.fetchNote(noteId, owner.id, { force: true })
        : await api.fetchPublicNote(noteId);
      if (!isCurrentRequest()) return;
      const view = buildView(res.data || {});
      rememberPropertyCity(`${view.address} ${view.title}`);
      const isOwnerViewing = ownerPreview || Boolean(this.data.user && view.ownerUserId && this.data.user.id === view.ownerUserId);
      this.setData({
        view,
        notePayload: res.data || {},
        publicLoadError: false,
        publicLoadErrorKind: "",
        publicLoadErrorTitle: "",
        publicLoadErrorMessage: "",
        isOwnerViewing,
        selectedContactCard: null,
        showLeadForm: false,
        showAppointmentForm: false,
        // Do not trust the public payload's URL before the snapshot state is
        // checked against the current v10 fingerprint. Legacy v10 images can
        // still have a URL while using the old template.
        shareImageReady: false,
        shareImageState: "missing",
        shareStatusText: isOwnerViewing ? "准备分享图" : "分享图准备中"
      }, () => {
        if (!isCurrentRequest()) return;
        setShareMenuEnabled(false);
        const sku = view.selectedSku || {};
        const selectedSkuOptions = buildSelectedSkuOptions(view.skuConfig || {}, sku.key || "");
        this.setData({
          selectedSkuKey: sku.key || "",
          selectedSkuOptions,
          skuSelectionGroups: buildSkuSelectionGroups(view.skuConfig || {}, selectedSkuOptions),
          "relayDraft.phone": readLastLeadPhone()
        });
        this.resolveMapFromAddress();
        this.prepareShareSnapshot();
      });
      await this.loadCustomerActionConfig(requestSeq);
      if (!isCurrentRequest()) return;
      this.recordCurrentView();
      this.bindReferralFromShare(view);
      if (this.data.pendingAction === "message" && this.data.user && !isOwnerViewing) {
        this.setData({ pendingAction: "" });
        setTimeout(() => this.handleOpenMessage(), 0);
      }
    } catch (error) {
      if (!isCurrentRequest()) return;
      setShareMenuEnabled(false);
      const statusCode = Number(error && error.statusCode);
      const detail = String(error && (error.detail || error.message) || "");
      const unavailable = statusCode === 404 || /资料尚未发布|资料不存在|笔记不存在|停止分享/.test(detail);
      const errorTitle = unavailable ? "资料已停止分享" : "客户页加载失败";
      const errorMessage = unavailable
        ? "这份资料已被更新或停止分享，请让发布者重新发布后再发送。"
        : "请检查网络后重试。";
      this.setData({
        view: null,
        notePayload: null,
        publicLoadError: true,
        publicLoadErrorKind: unavailable ? "unavailable" : "retryable",
        publicLoadErrorTitle: errorTitle,
        publicLoadErrorMessage: errorMessage,
        shareImageReady: false,
        shareImageState: "missing",
        shareStatusText: unavailable ? "资料已停止分享" : "重新加载"
      });
      wx.showToast({ title: unavailable ? "资料已更新，请重新发送" : errorTitle, icon: "none" });
    }
  },
  handleRetryPublicNote() {
    this.setData({
      publicLoadError: false,
      publicLoadErrorKind: "",
      publicLoadErrorTitle: "",
      publicLoadErrorMessage: ""
    });
    this.loadNote();
  },
  bindReferralFromShare(view) {
    const user = this.data.user;
    const inviterUserId = this.data.shareFromUserId;
    if (!user || !inviterUserId || user.id === inviterUserId || !view || view.ownerUserId === user.id) return;
    api.bindReferralFromShare(user.id, inviterUserId, this.data.shareScene || "share_link").catch(() => {});
  },
  async recordCurrentView() {
    const { noteId, user, viewRecorded, view } = this.data;
    if (!noteId || viewRecorded || !view) return;
    if (user && view.ownerUserId && user.id === view.ownerUserId) return;
    this.setData({ viewRecorded: true });
    try {
      await api.recordNoteView(noteId, {
        ...buildViewerPayload(user, "微信客户"),
        shareId: this.data.shareId || "",
        shareFromUserId: this.data.shareFromUserId || "",
        scene: this.data.shareScene || "public_note",
        referrer: this.data.referrer || "",
        sessionId: this.data.viewSessionId,
        durationSeconds: 1,
        maxScrollPercent: 0,
        focusSections: inferFocusSections(view, 0)
      });
    } catch (error) {
      this.setData({ viewRecorded: false });
    }
  },
  onPageScroll(event) {
    const scrollTop = Number(event.scrollTop || 0);
    const percent = Math.min(100, Math.max(0, Math.round((scrollTop / 1600) * 100)));
    if (percent > this.data.maxScrollPercent) {
      this.setData({ maxScrollPercent: percent });
    }
  },
  flushViewBehavior() {
    const { noteId, user, viewRecorded, view, pageEnterAt } = this.data;
    if (!noteId || !viewRecorded || !view) return;
    if (user && view.ownerUserId && user.id === view.ownerUserId) return;
    const durationSeconds = Math.max(1, Math.round((Date.now() - (pageEnterAt || Date.now())) / 1000));
    api.recordNoteView(noteId, {
      ...buildViewerPayload(user, "微信客户"),
      shareId: this.data.shareId || "",
      shareFromUserId: this.data.shareFromUserId || "",
      scene: this.data.shareScene || "public_note",
      referrer: this.data.referrer || "",
      sessionId: this.data.viewSessionId,
      durationSeconds,
      maxScrollPercent: this.data.maxScrollPercent,
      focusSections: inferFocusSections(view, this.data.maxScrollPercent)
    }).catch(() => {});
  },
  onHide() {
    this.flushViewBehavior();
  },
  onUnload() {
    this.flushViewBehavior();
  },
  async loadCustomerActionConfig(requestSeq = this._publicNoteRequestSeq) {
    const { user, noteId } = this.data;
    if (!noteId) return;
    const isCurrentRequest = () => requestSeq === this._publicNoteRequestSeq;
    try {
      const res = await api.fetchCustomerActionConfig(noteId, user ? { viewerUserId: user.id } : { anonymousId: getNotePreviewAnonymousId() });
      if (!isCurrentRequest()) return;
      const actions = (res.data && res.data.actions) || [];
      const actionStatus = {};
      let submittedPayload = null;
      actions.forEach((item) => {
        if (item.submitted) {
          actionStatus[item.key] = item.statusText || "已提交";
          if (item.key === "order-intent" || item.key === "relay-intent") {
            submittedPayload = item.submittedPayload || null;
          }
        }
      });
      const updateData = {
        actionStatus,
        leadSubmittedText: actionStatus["lead-contact"] || "",
        appointmentText: (actionStatus.appointment || "").replace(/^已预约\s*/, ""),
        relaySubmitted: Boolean(actionStatus["relay-intent"]),
        productOrderSubmitted: Boolean(actionStatus["order-intent"] || actionStatus["relay-intent"]),
        productOrderStatusText: actionStatus["order-intent"] || actionStatus["relay-intent"] || ""
      };
      if (submittedPayload && submittedPayload.skuKey) {
        const view = this.data.view || {};
        const selectedSkuOptions = buildSelectedSkuOptions(view.skuConfig || {}, submittedPayload.skuKey);
        updateData.selectedSkuKey = submittedPayload.skuKey;
        updateData.selectedSkuOptions = selectedSkuOptions;
        updateData.skuSelectionGroups = buildSkuSelectionGroups(view.skuConfig || {}, selectedSkuOptions);
        updateData.relayDraft = {
          ...this.data.relayDraft,
          quantity: submittedPayload.quantity || this.data.relayDraft.quantity,
          receiverName: submittedPayload.receiverName || "",
          phone: submittedPayload.phone || this.data.relayDraft.phone,
          address: submittedPayload.address || "",
          wechat: submittedPayload.wechat || "",
          remark: submittedPayload.remark || ""
        };
      }
      this.setData(updateData);
    } catch (error) {
      if (!isCurrentRequest()) return;
      this.setData({ actionStatus: {} });
    }
  },
  async prepareShareSnapshot() {
    const note = this.data.notePayload || {};
    const user = this.data.user || getCurrentUser() || {};
    const ownerUserId = this.data.isOwnerViewing ? user.id : "";
    if (!note.id) return;
    if (this.data.previewMode && note.shareState !== "published") {
      this.setData({
        shareImageReady: false,
        shareImageState: "unavailable",
        shareStatusText: "发布后可分享"
      });
      setShareMenuEnabled(false);
      return;
    }
    const current = getNoteShareSnapshotState(note, ownerUserId, user);
    const statusText = {
      missing: "准备分享图",
      stale: "重新生成分享图",
      preparing: "分享图生成中",
      failed: "重试分享图",
      ready: "好友"
    }[current.status] || "准备分享图";
    if (current.status === "ready") {
      const url = getShareImageUrlFromState(current);
      const shareReady = Boolean(url);
      this.setData({
        shareImageReady: shareReady,
        shareImageState: "ready",
        shareStatusText: "好友",
        view: { ...(this.data.view || {}), shareSnapshotUrl: url }
      });
      setShareMenuEnabled(shareReady);
      return current;
    }
    if (!ownerUserId) {
      this.setData({ shareImageReady: false, shareImageState: current.status, shareStatusText: statusText });
      setShareMenuEnabled(false);
      return current;
    }
    if (current.status === "preparing") return current;
    this.setData({ shareImageReady: false, shareImageState: "preparing", shareStatusText: "分享图生成中" });
    setShareMenuEnabled(false);
    try {
      const result = await prepareNoteShareSnapshot({
        note,
        ownerUserId,
        user
      });
      const url = result.snapshot && result.snapshot.url || "";
      const shareReady = Boolean(url);
      if (!shareReady) throw new Error("分享图地址为空");
      const nextNote = {
        ...note,
        revision: result.sourceRevision,
        visibilityConfig: result.entity && result.entity.visibilityConfig
          ? result.entity.visibilityConfig
          : note.visibilityConfig
      };
      this.setData({
        notePayload: nextNote,
        view: { ...(this.data.view || {}), shareSnapshotUrl: url },
        shareImageReady: shareReady,
        shareImageState: "ready",
        shareStatusText: "好友",
      });
      setShareMenuEnabled(shareReady);
      return result;
    } catch (error) {
      this.setData({ shareImageReady: false, shareImageState: "failed", shareStatusText: "重试分享图" });
      setShareMenuEnabled(false);
      return null;
    }
  },
  async resolveMapFromAddress() {
    const view = this.data.view || {};
    const location = view.mapLocation || {};
    if (this.data.resolvingMap || location.hasPoint || !view.address || !view.hasMap) return;
    const candidates = buildMapAddressCandidates(view).map(enrichAddressWithCity).filter(Boolean);
    const region = inferMapRegion(view.address);
    this.setData({ resolvingMap: true });
    try {
      let data = null;
      const regions = region ? [region, ""] : [""];
      for (let regionIndex = 0; regionIndex < regions.length && !data; regionIndex += 1) {
        for (let index = 0; index < candidates.length; index += 1) {
          const res = await api.geocodeAddress({
            address: candidates[index],
            region: regions[regionIndex]
          });
          const candidate = (res && res.data) || {};
          if (candidate.found && Number.isFinite(Number(candidate.latitude)) && Number.isFinite(Number(candidate.longitude))) {
            data = candidate;
            break;
          }
        }
      }
      if (!data) return;
      const mapAddress = candidates[0] || view.address;
      this.setData({
        "view.mapLocation": buildMapLocation({
          address: view.address,
          mapLocation: {
            name: data.name || view.title || "房源位置",
            address: data.address || mapAddress,
            latitude: data.latitude,
            longitude: data.longitude
          }
        }),
        "view.actions": (view.actions || []).map((item) => (
          item.key === "map" ? { ...item, desc: "打开腾讯地图" } : item
        ))
      });
      rememberPropertyCity(data.address || mapAddress);
    } finally {
      this.setData({ resolvingMap: false });
    }
  },
  handleAction(event) {
    const key = event.currentTarget.dataset.key;
    if (key === "contact" || key === "private") {
      this.handleContact(key);
      return;
    }
    if (key === "email") {
      this.handleCopyEmail();
      return;
    }
    if (key === "website") {
      this.handleCopyWebsite();
      return;
    }
    if (key === "save-card") {
      this.handleSaveBusinessCard();
      return;
    }
    if (key === "miniapp") {
      this.handleOpenMiniapp();
      return;
    }
    if (key === "lead") {
      const showLeadForm = !this.data.showLeadForm;
      this.setData({ showLeadForm }, () => {
        if (!showLeadForm || !wx.createSelectorQuery) return;
        const query = wx.createSelectorQuery();
        query.select("#leadForm").boundingClientRect();
        query.selectViewport().scrollOffset();
        query.exec(([rect, viewport]) => {
          if (!rect || !viewport) return;
          wx.pageScrollTo({
            scrollTop: Math.max(0, viewport.scrollTop + rect.top - 32),
            duration: 240
          });
        });
      });
      return;
    }
    if (key === "appointment") {
      this.handleAppointment();
      return;
    }
    if (key === "map") {
      this.handleOpenMap();
      return;
    }
    if (key === "message") {
      this.handleOpenMessage();
      return;
    }
    if (key === "relay") {
      this.setData({ showRelayForm: !this.data.showRelayForm });
    }
  },
  handleCommunicationAction(event) {
    const key = event.detail && event.detail.key;
    if (!key) return;
    this.handleAction({ currentTarget: { dataset: { key } } });
  },
  handleOpenFeaturedResource(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    this.recordInteraction("featured_note_open", "", { featuredNoteId: id });
    wx.navigateTo({ url: `/pages/note-preview/index?id=${id}` });
  },
  handleEditBusinessCard() {
    const noteId = this.data.noteId || "";
    if (!noteId) return;
    wx.navigateTo({ url: `/subpackages/workbench/business-card-studio/index?id=${encodeURIComponent(noteId)}` });
  },
  handleFeaturedAttachment(event) {
    const dataset = (event && event.currentTarget && event.currentTarget.dataset) || {};
    const url = String(dataset.url || "").trim();
    const type = String(dataset.type || "image").trim();
    const id = String(dataset.id || "").trim();
    if (!url) return;
    if (type === "image") {
      this.recordInteraction("image_open", id, { featured: true });
      wx.previewImage({ current: url, urls: [url] });
      return;
    }
    this.recordInteraction(type === "pdf" ? "pdf_open" : "link_open", id, { featured: true });
    if (type === "pdf") {
      wx.downloadFile({
        url,
        success: ({ tempFilePath }) => wx.openDocument({
          filePath: tempFilePath,
          fileType: "pdf",
          showMenu: true,
          fail: () => wx.showToast({ title: "PDF 打开失败", icon: "none" })
        }),
        fail: () => wx.showToast({ title: "PDF 打开失败", icon: "none" })
      });
      return;
    }
    wx.setClipboardData({ data: url, success: () => wx.showToast({ title: "链接已复制，请在浏览器打开", icon: "none" }) });
  },
  noop() {},
  handleBackHome() {
    wx.switchTab({ url: "/pages/home/index" });
  },
  handleSelectSku(event) {
    const key = event.currentTarget.dataset.key;
    const soldOut = event.currentTarget.dataset.soldOut;
    if (soldOut === true || soldOut === "true") {
      wx.showToast({ title: "该规格已售罄", icon: "none" });
      return;
    }
    const view = this.data.view || {};
    const selectedSkuOptions = buildSelectedSkuOptions(view.skuConfig || {}, key);
    this.setData({
      selectedSkuKey: key,
      selectedSkuOptions,
      skuSelectionGroups: buildSkuSelectionGroups(view.skuConfig || {}, selectedSkuOptions)
    });
  },
  handleSelectSkuOption(event) {
    const groupId = event.currentTarget.dataset.groupId;
    const groupIndex = Number(event.currentTarget.dataset.groupIndex);
    const optionId = event.currentTarget.dataset.optionId;
    const disabled = event.currentTarget.dataset.disabled;
    if (disabled === true || disabled === "true") {
      wx.showToast({ title: "该选项已售罄", icon: "none" });
      return;
    }
    const view = this.data.view || {};
    const skuConfig = view.skuConfig || {};
    const selectedSkuOptions = {
      ...(this.data.selectedSkuOptions || {}),
      [groupId]: optionId
    };
    let selectedSku = findSkuBySelectedOptions(skuConfig, selectedSkuOptions);
    if (!selectedSku || selectedSku.soldOut) {
      selectedSku = (skuConfig.skus || []).find((sku) => {
        const ids = skuOptionIds(sku);
        return !sku.soldOut && ids[groupIndex] === optionId;
      });
      if (selectedSku) {
        Object.assign(selectedSkuOptions, buildSelectedSkuOptions(skuConfig, selectedSku.key));
      }
    }
    this.setData({
      selectedSkuKey: selectedSku && !selectedSku.soldOut ? selectedSku.key : "",
      selectedSkuOptions,
      skuSelectionGroups: buildSkuSelectionGroups(skuConfig, selectedSkuOptions)
    });
  },
  handleOpenOrderSheet() {
    const view = this.data.view || {};
    const { selectedSkuKey } = this.data;
    if (!selectedSkuKey) {
      wx.showToast({ title: "请选择规格", icon: "none" });
      return;
    }
    const selectedSku = ((view.skuConfig && view.skuConfig.skus) || []).find((item) => item.key === selectedSkuKey);
    if (selectedSku && selectedSku.soldOut) {
      wx.showToast({ title: "该规格已售罄", icon: "none" });
      return;
    }
    this.setData({ showOrderSheet: true });
  },
  handleCloseOrderSheet() {
    if (this.data.submittingAction) return;
    this.setData({ showOrderSheet: false });
  },
  handleRelayInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`relayDraft.${key}`]: event.detail.value });
  },
  async handleSubmitProductOrder() {
    const view = this.data.view || {};
    const { selectedSkuKey, relayDraft } = this.data;
    if (!selectedSkuKey) {
      wx.showToast({ title: "请选择规格", icon: "none" });
      return;
    }
    const selectedSku = ((view.skuConfig && view.skuConfig.skus) || []).find((item) => item.key === selectedSkuKey);
    if (selectedSku && selectedSku.soldOut) {
      wx.showToast({ title: "该规格已售罄", icon: "none" });
      return;
    }
    const quantity = Number(relayDraft.quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      wx.showToast({ title: "请填写数量", icon: "none" });
      return;
    }
    if (!String(relayDraft.phone || "").trim()) {
      wx.showToast({ title: "请填写电话", icon: "none" });
      return;
    }
    if (!String(relayDraft.address || "").trim()) {
      wx.showToast({ title: "请填写地址", icon: "none" });
      return;
    }
    await this.handleSubmitProductIntent(view.enableGroupRelay ? "relay-intent" : "order-intent");
  },
  async handleSubmitProductIntent(actionKey) {
    const { user, noteId, selectedSkuKey, relayDraft } = this.data;
    if (!noteId || this.data.submittingAction) return;
    if (!selectedSkuKey) {
      wx.showToast({ title: "请选择规格", icon: "none" });
      return;
    }
    this.setData({ submittingAction: actionKey });
    try {
      const res = await api.submitCustomerAction(noteId, actionKey, {
        ...buildViewerPayload(user, relayDraft.receiverName || relayDraft.phone || "匿名客户"),
        payload: {
          ...relayDraft,
          skuKey: selectedSkuKey
        }
      });
      rememberLeadPhone(relayDraft.phone);
      const statusText = (res.data && res.data.statusText) || (actionKey === "relay-intent" ? "已提交接龙" : "已下单");
      this.setData({
        showRelayForm: false,
        showOrderSheet: false,
        relaySubmitted: actionKey === "relay-intent",
        productOrderSubmitted: true,
        productOrderStatusText: statusText,
        [`actionStatus.${actionKey}`]: statusText
      });
      wx.showToast({ title: actionKey === "relay-intent" ? "已提交接龙" : "已下单", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "提交失败", icon: "none" });
    } finally {
      this.setData({ submittingAction: "" });
    }
  },
  async handleOpenMessage() {
    const { user, noteId } = this.data;
    if (!noteId) return;
    this.recordInteraction("contact_click");
    if (!user) {
      const query = [
        `id=${encodeURIComponent(noteId)}`,
        this.data.shareId ? `sid=${encodeURIComponent(this.data.shareId)}` : "",
        this.data.shareFromUserId ? `from=${encodeURIComponent(this.data.shareFromUserId)}` : "",
        this.data.shareScene ? `src=${encodeURIComponent(this.data.shareScene)}` : "",
        this.data.referrer ? `ref=${encodeURIComponent(this.data.referrer)}` : "",
        "action=message"
      ].filter(Boolean).join("&");
      const returnUrl = `/pages/note-preview/index?${query}`;
      wx.reLaunch({
        url: `/pages/login/index?returnUrl=${encodeURIComponent(returnUrl)}`
      });
      return;
    }
    await messagePlugin.openMessageThread({ noteId, buyerUserId: user.id });
  },
  openWechatLocation(location, view) {
    wx.openLocation({
      latitude: Number(location.latitude),
      longitude: Number(location.longitude),
      name: location.name || view.title,
      address: location.address || view.address || ""
    });
  },
  openNavigationApp(location, view) {
    if (!wx.createMapContext) {
      this.openWechatLocation(location, view);
      return;
    }
    const mapContext = wx.createMapContext("previewMap", this);
    if (!mapContext || typeof mapContext.openMapApp !== "function") {
      this.openWechatLocation(location, view);
      return;
    }
    mapContext.openMapApp({
      latitude: Number(location.latitude),
      longitude: Number(location.longitude),
      destination: location.name || view.title || "房源位置",
      fail: () => this.openWechatLocation(location, view)
    });
  },
  copyAddress() {
    const view = this.data.view || {};
    if (!view.address) {
      wx.showToast({ title: "暂无地址", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: view.address,
      success: () => wx.showToast({ title: "地址已复制", icon: "success" })
    });
  },
  handleContact(kind) {
    const view = this.data.view || {};
    const rawPhone = (view.businessCardDetail && view.businessCardDetail.phone) || view.contact || "";
    const phone = String(rawPhone || "").replace(/[^\d+]/g, "");
    const wechat = (view.businessCardDetail && view.businessCardDetail.wechat) || view.wechat || "";
    const qrCodeUrl = (view.businessCardDetail && view.businessCardDetail.qrCodeUrl)
      || (view.serviceOfferDetail && view.serviceOfferDetail.qrCodeUrl)
      || view.wechatQrUrl
      || "";
    this.recordInteraction(kind === "private" ? "contact_click" : "phone_click");
    if (kind === "private") {
      const value = wechat || phone;
      if (value) {
        this.setData({ selectedContactCard: { label: wechat ? "微信" : "电话", value, hint: wechat ? "微信号已复制，可添加咨询" : "电话已复制" } });
        wx.setClipboardData({ data: value, success: () => wx.showToast({ title: wechat ? "微信已复制" : "电话已复制", icon: "success" }) });
        return;
      }
      if (qrCodeUrl) {
        this.recordInteraction("wechat_qr_open");
        wx.previewImage({ current: qrCodeUrl, urls: [qrCodeUrl] });
        return;
      }
      wx.showToast({ title: "暂无微信", icon: "none" });
      return;
    }
    if (phone && phone.length >= 5) {
      this.setData({ selectedContactCard: { label: "电话", value: rawPhone || phone, hint: "正在拨打电话" } });
      wx.makePhoneCall({ phoneNumber: phone });
      return;
    }
    if (phone) {
      wx.setClipboardData({ data: phone, success: () => wx.showToast({ title: "电话已复制", icon: "success" }) });
      return;
    }
    wx.showToast({ title: "暂无联系方式", icon: "none" });
  },
  handleCopyEmail() {
    const view = this.data.view || {};
    const email = (view.businessCardDetail && view.businessCardDetail.email) || (view.serviceOfferDetail && view.serviceOfferDetail.email) || view.email || "";
    if (!email) {
      wx.showToast({ title: "暂无邮箱", icon: "none" });
      return;
    }
    this.setData({ selectedContactCard: { label: "邮箱", value: email, hint: "邮箱已复制，可发邮件联系" } });
    wx.setClipboardData({ data: email, success: () => wx.showToast({ title: "邮箱已复制", icon: "success" }) });
  },
  handleCopyWebsite() {
    const view = this.data.view || {};
    const website = (view.businessCardDetail && view.businessCardDetail.website) || (view.serviceOfferDetail && view.serviceOfferDetail.website) || view.website || "";
    if (!website) {
      wx.showToast({ title: "暂无网址", icon: "none" });
      return;
    }
    wx.setClipboardData({ data: website, success: () => wx.showToast({ title: "网址已复制", icon: "success" }) });
  },
  handleSaveBusinessCard() {
    const view = this.data.view || {};
    const detail = view.businessCardDetail || {};
    const hero = view.businessCardHero || {};
    const text = [
      hero.name,
      [hero.role, hero.company].filter(Boolean).join(" · "),
      hero.serviceScope,
      detail.phone ? `电话：${detail.phone}` : "",
      detail.wechat ? `微信：${detail.wechat}` : "",
      detail.email ? `邮箱：${detail.email}` : "",
      detail.website ? `网址：${detail.website}` : ""
    ].filter(Boolean).join("\n");
    if (!text) {
      wx.showToast({ title: "暂无名片信息", icon: "none" });
      return;
    }
    wx.setClipboardData({ data: text, success: () => wx.showToast({ title: "名片信息已复制", icon: "success" }) });
  },
  handleOpenMiniapp() {
    const miniapp = (this.data.view && this.data.view.miniapp) || {};
    if (!miniapp.appId || !miniapp.path) {
      wx.showToast({ title: "暂无小程序路径", icon: "none" });
      return;
    }
    wx.navigateToMiniProgram({
      appId: miniapp.appId,
      path: miniapp.path,
      envVersion: "release",
      fail: () => this.copyMiniappFallback()
    });
  },
  copyMiniappFallback() {
    const miniapp = (this.data.view && this.data.view.miniapp) || {};
    const text = [
      miniapp.title || (this.data.view && this.data.view.title),
      miniapp.sourceName,
      miniapp.houseCode ? `房源编码：${miniapp.houseCode}` : "",
      miniapp.cityId ? `城市编码：${miniapp.cityId}` : ""
    ].filter(Boolean).join("\n");
    if (!text) {
      wx.showToast({ title: "打开失败", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: "已复制房源信息", icon: "success" }),
      fail: () => wx.showToast({ title: "打开失败", icon: "none" })
    });
  },
  handleAppointment() {
    this.setData({
      showAppointmentForm: !this.data.showAppointmentForm,
      appointmentDraft: this.data.appointmentDraft.date ? this.data.appointmentDraft : buildAppointmentDraft(0)
    });
  },
  handleQuickAppointment(event) {
    const offset = Number(event.currentTarget.dataset.offset || 0);
    this.setData({ appointmentDraft: { ...this.data.appointmentDraft, ...buildAppointmentDraft(offset) } });
  },
  handleAppointmentDate(event) {
    this.setData({ "appointmentDraft.date": event.detail.value });
  },
  handleAppointmentTime(event) {
    this.setData({ "appointmentDraft.time": event.detail.value });
  },
  handleAppointmentRemark(event) {
    this.setData({ "appointmentDraft.remark": event.detail.value });
  },
  async handleSubmitAppointment() {
    const draft = this.data.appointmentDraft || {};
    const dateText = formatDateLabel(draft.date);
    const timeText = draft.time || "10:00";
    const remarkText = draft.remark ? `，${draft.remark}` : "";
    const { user, noteId } = this.data;
    if (!noteId || this.data.submittingAction) return;
    this.setData({ submittingAction: "appointment" });
    try {
      const res = await api.submitCustomerAction(noteId, "appointment", {
        ...buildViewerPayload(user, this.data.leadDraft.name || this.data.leadDraft.phone || "匿名客户"),
        payload: draft
      });
      this.setData({
        appointmentText: `${dateText} ${timeText}${remarkText}`,
        showAppointmentForm: false,
        "actionStatus.appointment": (res.data && res.data.statusText) || "已预约"
      });
      wx.showToast({ title: "已记录预约意向", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "预约提交失败", icon: "none" });
    } finally {
      this.setData({ submittingAction: "" });
    }
  },
  async handleOpenMap() {
    const view = this.data.view || {};
    this.recordInteraction("map_open");
    let location = view.mapLocation || {};
    await this.resolveMapFromAddress();
    const nextView = this.data.view || view;
    location = nextView.mapLocation || location;
    if (location.latitude && location.longitude) {
      wx.showActionSheet({
        itemList: ["选择导航App", "微信内置地图", "复制地址"],
        success: ({ tapIndex }) => {
          if (tapIndex === 0) this.openNavigationApp(location, nextView);
          if (tapIndex === 1) this.openWechatLocation(location, nextView);
          if (tapIndex === 2) this.copyAddress();
        }
      });
      return;
    }
    if (nextView.address) {
      this.copyAddress();
      return;
    }
    wx.showToast({ title: "暂无定位信息", icon: "none" });
  },
  handleLeadInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`leadDraft.${key}`]: event.detail.value });
  },
  async handleSubmitLead() {
    if (!this.data.leadDraft.phone.trim() && !this.data.leadDraft.wechat.trim()) {
      wx.showToast({ title: "请填写电话或微信", icon: "none" });
      return;
    }
    const { user, noteId } = this.data;
    if (!noteId || this.data.submittingAction) return;
    this.setData({ submittingAction: "lead-contact" });
    try {
      const res = await api.submitCustomerAction(noteId, "lead-contact", {
        ...buildViewerPayload(user, this.data.leadDraft.name || this.data.leadDraft.phone || "匿名客户"),
        payload: this.data.leadDraft
      });
      rememberLeadPhone(this.data.leadDraft.phone);
      this.setData({
        showLeadForm: false,
        leadSubmittedText: (res.data && res.data.statusText) || "已提交联系方式",
        "actionStatus.lead-contact": (res.data && res.data.statusText) || "已提交联系方式"
      });
      wx.showToast({ title: "已提交联系方式", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "提交失败", icon: "none" });
    } finally {
      this.setData({ submittingAction: "" });
    }
  },
  handleTimelineHint() {
    wx.showModal({
      title: "朋友圈",
      content: "受微信限制，小程序内不能直接打开朋友圈发布页。请点击右上角菜单，选择“分享到朋友圈”；也可以先保存分享图再发布。",
      showCancel: false,
      confirmColor: "#11924d"
    });
  },
  handlePreviewImage(event) {
    const url = event.currentTarget.dataset.url;
    const view = this.data.view || {};
    const serviceOfferDetail = view.serviceOfferDetail || {};
    const isBusinessQr = Boolean(view.isBusinessCard && view.businessCardDetail && url === view.businessCardDetail.qrCodeUrl);
    const urls = [
      isBusinessQr ? url : "",
      serviceOfferDetail.coverUrl,
      ...(serviceOfferDetail.caseImages || []),
      view.coverUrl,
      ...(view.galleryImages || [])
    ].filter(Boolean);
    if (!url || !urls.length) return;
    if (isBusinessQr) this.recordInteraction("wechat_qr_open");
    const attachment = (view.attachments || []).find((item) => item.url === url);
    if (attachment) this.recordInteraction("image_open", attachment.id);
    wx.previewImage({ current: url, urls });
  },
  recordInteraction(eventType, attachmentId = "", metadata = {}) {
    const { noteId, user } = this.data;
    if (!noteId) return;
    api.recordNoteInteraction(noteId, {
      eventType,
      attachmentId: attachmentId || null,
      ...buildViewerPayload(user, "微信客户"),
      shareId: this.data.shareId || "",
      shareFromUserId: this.data.shareFromUserId || "",
      sessionId: this.data.viewSessionId,
      scene: this.data.shareScene || "public_note",
      metadata
    }).catch(() => {});
  },
  handleAttachment(event) {
    const item = (this.data.view.attachments || [])[Number(event.currentTarget.dataset.index)];
    if (!item) return;
    if (item.type === "image") {
      this.recordInteraction("image_open", item.id);
      wx.previewImage({ current: item.url, urls: this.data.view.attachments.filter((row) => row.type === "image").map((row) => row.url) });
      return;
    }
    this.recordInteraction(item.type === "pdf" ? "pdf_open" : "link_open", item.id);
    if (item.type === "pdf") {
      wx.downloadFile({ url: item.url, success: ({ tempFilePath }) => wx.openDocument({ filePath: tempFilePath, fileType: "pdf", showMenu: true }), fail: () => wx.showToast({ title: "PDF 打开失败", icon: "none" }) });
      return;
    }
    wx.setClipboardData({ data: item.url, success: () => wx.showToast({ title: "链接已复制，请在浏览器打开", icon: "none" }) });
  },
  handleOpenArticleSource() {
    const detail = ((this.data.view || {}).articleDetail || {});
    const url = detail.sourceUrl || "";
    if (!url) {
      wx.showToast({ title: "暂无原文链接", icon: "none" });
      return;
    }
    this.recordInteraction("source_open");
    if (/mp\.weixin\.qq\.com/i.test(url) && typeof wx.openOfficialAccountArticle === "function") {
      wx.openOfficialAccountArticle({ url, fail: () => wx.setClipboardData({ data: url, success: () => wx.showToast({ title: "原文链接已复制", icon: "success" }) }) });
      return;
    }
    wx.setClipboardData({ data: url, success: () => wx.showToast({ title: "原文链接已复制，请在浏览器打开", icon: "none" }) });
  },
  handleGenerateSame() {
    const user = this.data.user || getCurrentUser();
    if (!user) {
      wx.navigateTo({ url: `/pages/login/index?returnUrl=${encodeURIComponent(`/pages/note-preview/index?id=${this.data.noteId}`)}` });
      return;
    }
    if (this.data.generatingSame) return;
    this.setData({ generatingSame: true });
    wx.showLoading({ title: "生成同款" });
    api.generateSameStyle({
      ownerUserId: user.id,
      mode: "reuse_content",
      sourceNoteId: this.data.noteId,
      ownNoteIds: [],
      idempotencyKey: `public-${user.id}-${this.data.noteId}`
    }).then((response) => {
      const generation = ((response.data || {}).generation || {});
      if (!generation.generatedNoteId) throw new Error("生成结果缺少资料ID");
      const { navigateToNoteEditor } = require("../../utils/resource-navigation");
      navigateToNoteEditor(generation.generatedNoteId);
    }).catch((error) => wx.showToast({ title: error.detail || error.message || "生成失败", icon: "none" }))
      .finally(() => { wx.hideLoading(); this.setData({ generatingSame: false }); });
  },
  handleShareTap() {
    subscription.requestViewNotificationSubscription("note_preview_share");
  },
  onShareAppMessage() {
    const view = this.data.view || {};
    const user = this.data.user || getCurrentUser();
    const shareId = createShareId(this.data.noteId);
    const shareFromUserId = user ? user.id : (this.data.shareFromUserId || "");
    const scene = "note_preview_share";
    const rawTitle = view.isBusinessCard && view.businessCardHero
      ? buildBusinessCardShareTitle(view.businessCardHero)
      : view.isServiceOffer
        ? buildServiceOfferShareTitle(view.serviceOfferDetail || view)
        : buildNoteShareTitle(this.data.notePayload || {}, user || {}) || view.shareTitle || view.title || "资料详情";
    const shareState = getNoteShareSnapshotState(this.data.notePayload || {}, this.data.isOwnerViewing && user ? user.id : "", user || {});
    const sharePath = `/pages/note-preview/index?id=${this.data.noteId}&sid=${shareId}&from=${shareFromUserId}&src=${scene}&ref=${this.data.shareId || ""}`;
    const shareMessage = buildShareMessage({
      title: buildCustomerShareTitle(rawTitle),
      path: sharePath,
      snapshot: shareState.snapshot,
      sourceRevision: shareState.sourceRevision,
      fingerprint: shareState.fingerprint,
      styleId: shareState.styleId,
      imageUrl: getShareImageUrlFromState(shareState)
    });
    if (!shareMessage) {
      wx.showToast({ title: "资料分享图正在准备，请稍后再发", icon: "none" });
      setShareMenuEnabled(false);
      return null;
    }
    if (this.data.noteId && shareFromUserId) {
      api.recordNoteView(this.data.noteId, {
        eventType: "share",
        viewerUserId: shareFromUserId,
        shareId,
        shareFromUserId,
        scene,
        referrer: this.data.shareId || ""
      }).catch(() => {});
    }
    return shareMessage;
  },
  onShareTimeline() {
    const view = this.data.view || {};
    const user = this.data.user || getCurrentUser();
    const shareId = createShareId(this.data.noteId);
    const shareFromUserId = user ? user.id : (this.data.shareFromUserId || "");
    const scene = "note_timeline_share";
    if (this.data.noteId && shareFromUserId) {
      api.recordNoteView(this.data.noteId, {
        eventType: "share",
        viewerUserId: shareFromUserId,
        shareId,
        shareFromUserId,
        scene,
        referrer: this.data.shareId || ""
      }).catch(() => {});
    }
    const rawTitle = view.isBusinessCard && view.businessCardHero
      ? buildBusinessCardShareTitle(view.businessCardHero)
      : view.isServiceOffer
        ? buildServiceOfferShareTitle(view.serviceOfferDetail || view)
        : buildNoteShareTitle(this.data.notePayload || {}, user || {}) || view.shareTitle || view.title || "资料详情";
    const shareState = getNoteShareSnapshotState(this.data.notePayload || {}, this.data.isOwnerViewing && user ? user.id : "", user || {});
    const shareImage = getShareImageUrlFromState(shareState);
    if (!shareImage) {
      wx.showToast({ title: "资料分享图正在准备，请稍后再发", icon: "none" });
      setShareMenuEnabled(false);
      return null;
    }
    return {
      title: buildCustomerShareTitle(rawTitle),
      query: `id=${this.data.noteId}&sid=${shareId}&from=${shareFromUserId}&src=${scene}&ref=${this.data.shareId || ""}`,
      imageUrl: shareImage
    };
  }
});
