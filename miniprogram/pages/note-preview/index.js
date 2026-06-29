const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { getCurrentUser, getRandomDefaultNickname, safeAvatarUrl } = require("../../utils/dashboard");
const { getSalesPageTemplate, templateToneClass } = require("../../utils/sales-page-templates");
const { buildBusinessCardShareTitle, buildServiceOfferShareTitle, generatePropertyShareImage, generateBusinessCardShareImage, generateServiceOfferShareImage, generateTitleShareImage } = require("../../utils/business-card-share");

const LAST_LEAD_PHONE_KEY = "teambuy:lastLeadPhone";
const LAST_PROPERTY_CITY_KEY = "teambuy:lastPropertyCity";
const SHARE_CARD_CANVAS_ID = "businessCardShareCanvas";

function buildCustomerShareTitle(title) {
  const cleanTitle = String(title || "这份资料").replace(/\s+/g, " ").trim();
  return `${cleanTitle}｜点开查看完整资料`;
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
  try {
    return wx.getStorageSync(LAST_LEAD_PHONE_KEY) || "";
  } catch (error) {
    return "";
  }
}

function getNotePreviewAnonymousId() {
  const key = "notePreviewAnonymousId";
  try {
    const stored = wx.getStorageSync(key);
    if (stored) return stored;
    const next = `note_anon_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
    wx.setStorageSync(key, next);
    return next;
  } catch (error) {
    return `note_anon_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
  }
}

function buildViewerPayload(user, fallbackName) {
  if (user) {
    return {
      viewerUserId: user.id,
      nickname: user.nickname || fallbackName || getRandomDefaultNickname(),
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
  try {
    wx.setStorageSync(LAST_LEAD_PHONE_KEY, phone[0]);
  } catch (error) {
    // Local memory is only a convenience; ignore failures.
  }
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
  const unique = Array.from(new Set(prices));
  if (!unique.length) return fallback || "";
  if (unique.length === 1) return unique[0];
  return `${unique[0]} - ${unique[unique.length - 1]}`;
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
    return [
      { key: "audience", title: "适合人群", body: data.targetAudience || "" },
      { key: "content", title: "服务内容", body: data.serviceContent || note.body || "" },
      { key: "process", title: "服务流程", body: data.serviceProcess || "" },
      { key: "pricing", title: "报价说明", body: data.pricingNote || "" },
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
    return [
      { label: "对象", value: data.targetAudience || "需要服务的客户" },
      { label: "报价", value: data.pricingNote || "按需求沟通" },
      { label: "地区", value: data.serviceArea || "线上 / 本地" }
    ].filter((item) => item.value);
  }
  return [];
}

function buildBusinessCardScopeItems(data) {
  const labels = splitFeatureText(data.serviceScope || data.headline);
  const fallback = ["专业咨询", "客户顾问", "长期跟进"];
  const descs = [
    "提供清晰建议",
    "一对一沟通",
    "持续响应需求"
  ];
  return (labels.length ? labels : fallback).slice(0, 3).map((label, index) => ({
    label,
    desc: descs[index] || "按需求服务"
  }));
}

function buildBusinessCardDetail(data, note, hero, galleryImages) {
  const phone = data.phone || note.phone || "";
  const wechat = data.wechat || data.contactWechat || "";
  const email = data.email || data.mail || "";
  const explicitQr = data.qrCodeUrl || data.qrcodeUrl || data.qrUrl || data.wechatQrCodeUrl || data.wechatQrUrl || data.qrCode || "";
  const mediaImages = Array.isArray(note.media) ? note.media.filter((item) => item && item.type === "image").map((item) => item.url) : [];
  const candidateImages = [explicitQr, ...(galleryImages || []), ...mediaImages].filter(Boolean);
  const qrCodeUrl = candidateImages.find((url) => url && url !== hero.avatarUrl && url !== data.avatarUrl) || explicitQr || "";
  return {
    intro: data.bio || data.headline || note.body || note.summary || "我会根据你的具体需求，提供清晰建议、及时沟通和持续跟进。",
    scopeText: data.serviceScope || hero.serviceScope || "咨询服务 / 客户顾问 / 长期跟进",
    cityText: data.city || data.serviceArea || "本地服务",
    phone,
    wechat,
    email,
    website: data.website || data.companyWebsite || data.websiteUrl || data.url || "",
    qrCodeUrl,
    scopeItems: buildBusinessCardScopeItems(data)
  };
}

function buildBusinessCardActions(detail) {
  const actions = [];
  if (detail.phone) actions.push({ key: "contact", icon: "电", title: "电话咨询", value: detail.phone, hint: "点击拨打电话" });
  if (detail.wechat) actions.push({ key: "private", icon: "微", title: "微信咨询", value: detail.wechat, hint: "点击复制微信" });
  if (detail.email) actions.push({ key: "email", icon: "邮", title: "邮箱", value: detail.email, hint: "点击复制邮箱" });
  actions.push({ key: "lead", icon: "留", title: "留下电话/微信", value: "", hint: "方便发布者回访" });
  return actions;
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
  const email = data.email || data.mail || "";
  const website = data.website || data.companyWebsite || data.websiteUrl || "";
  const templatePreview = (template && template.preview) || {};
  const templateCoverUrl = templatePreview.coverUrl || "";
  const templateCaseImageUrls = Array.isArray(templatePreview.caseImageUrls) ? templatePreview.caseImageUrls.filter(Boolean) : [];
  const audienceBullets = splitFeatureText(data.targetAudience || templatePreview.bullets || "").slice(0, 3);
  const serviceBullets = splitFeatureText(data.serviceContent || templatePreview.serviceItems || "").slice(0, 4);
  const processSteps = splitFeatureText(data.serviceProcess || "").slice(0, 4);
  const caseBullets = splitFeatureText(data.caseHighlights || (templatePreview.caseLabels || []).join(" / ")).slice(0, 3);
  const pricingTags = splitFeatureText(data.pricingNote || (templatePreview.quoteTags || []).join(" / ")).slice(0, 3);
  const supportChips = Array.from(new Set([
    ...(templatePreview.chips || []),
    data.serviceArea || note.locationText || "",
    data.appointmentNote || ""
  ].filter(Boolean))).slice(0, 4);
  const contactCount = Math.max(1, [phone, wechat, email].filter(Boolean).length);
  const coverUrl = data.coverUrl || note.coverUrl || galleryImages[0] || templateCoverUrl || "";
  const caseImages = Array.from(new Set([
    ...galleryImages,
    ...templateCaseImageUrls,
    (template && template.id) === "service_case_story" && coverUrl ? coverUrl : ""
  ].filter(Boolean))).slice(0, 3);
  return {
    templateId: (template && template.id) || "",
    templateName: (template && template.name) || "服务方案",
    scene: (template && template.scene) || "",
    serviceName: data.serviceName || note.title || "服务方案",
    headline: data.headline || note.summary || "",
    targetAudience: data.targetAudience || "适合需要专业服务、想先了解方案的客户",
    serviceContent: data.serviceContent || note.body || "",
    pricingNote: data.pricingNote || "按需求沟通报价",
    serviceProcess: data.serviceProcess || "提交需求 - 预约沟通 - 输出建议 - 后续跟进",
    caseHighlights: data.caseHighlights || note.summary || "",
    serviceArea: data.serviceArea || note.locationText || "",
    appointmentNote: data.appointmentNote || "",
    primaryAction: data.primaryAction || templatePreview.primaryAction || "电话咨询",
    secondaryAction: data.secondaryAction || templatePreview.secondaryAction || "微信咨询",
    phone,
    wechat,
    email,
    website,
    coverUrl,
    heroPortraitUrl: templatePreview.avatarUrl || "",
    supportChips,
    audienceBullets: audienceBullets.length ? audienceBullets : ["适合先了解服务价值，再决定是否深入沟通"],
    serviceBullets: serviceBullets.length ? serviceBullets : ["需求梳理", "方案建议", "执行跟进"],
    processSteps: processSteps.length ? processSteps : ["提交需求", "预约沟通", "输出建议", "后续跟进"],
    caseBullets: caseBullets.length ? caseBullets : ["案例成果", "客户反馈", "交付亮点"],
    caseImages,
    pricingTags: pricingTags.length ? pricingTags : ["按项目报价", "按阶段报价", "定制方案"],
    contentChips: splitFeatureText(data.serviceContent || "").slice(0, 4),
    metricCards: buildServiceOfferMetricCards(
      (template && template.id) || "",
      audienceBullets.length ? audienceBullets : ["咨询客户"],
      serviceBullets.length ? serviceBullets : ["服务内容"],
      processSteps.length ? processSteps : ["服务流程"],
      contactCount
    )
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
    name: title || "电子名片",
    role: data.title || "个人顾问",
    company: data.company || "个人服务",
    serviceScope: data.serviceScope || data.headline || subtitle || note.summary || "",
    contactLine: [phone, wechat, email].filter(Boolean).join(" · ") || "电话 / 微信 / 邮箱",
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
  const miniapp = buildMiniappInfo(data);
  const cardType = config.cardType || "text_note";
  const isProperty = cardType === "property_listing";
  const isGroupbuy = cardType === "groupbuy_product";
  const isBusinessCard = cardType === "business_card";
  const isServiceOffer = cardType === "service_offer";
  const isServiceCard = isBusinessCard || isServiceOffer;
  const template = isServiceCard ? resolveSalesTemplate(config, isBusinessCard) : null;
  const isMiniapp = miniapp.visible && config.sourceType === "miniapp";
  const skuConfig = normalizeSkuConfig(data);
  const productPriceText = buildProductPriceText(skuConfig, data.price);
  const title = isProperty
    ? data.community || note.title
    : isGroupbuy
      ? data.productName || note.title
      : isBusinessCard
        ? data.name || note.title
        : isServiceOffer
          ? data.serviceName || note.title
          : miniapp.title || note.title;
  const subtitle = isProperty
    ? [data.price, data.layout, data.area].filter(Boolean).join(" · ")
    : isGroupbuy
      ? [productPriceText, data.spec, data.pickupMethod].filter(Boolean).join(" · ")
      : isBusinessCard
        ? [data.title, data.company, data.serviceScope].filter(Boolean).join(" · ")
        : isServiceOffer
          ? [data.headline, data.pricingNote, data.serviceArea].filter(Boolean).join(" · ")
          : isMiniapp ? [miniapp.sourceName, miniapp.houseCode ? `房源编码 ${miniapp.houseCode}` : ""].filter(Boolean).join(" · ") : note.summary || "";
  const mapLocation = buildMapLocation(data);
  const coverUrl = note.coverUrl || data.avatarUrl || data.qrCodeUrl || ((note.media || []).find((item) => item.type === "image") || {}).url || "";
  const galleryImages = buildGalleryImages(note, coverUrl);
  const galleryVideos = buildGalleryVideos(note);
  const address = isProperty ? data.address || data.businessArea || "" : data.pickupLocation || "";
  const contact = data.phone || data.contactPhone || data.contact || note.phone || "";
  const wechat = data.wechat || data.contactWechat || "";
  const email = data.email || data.mail || "";
  const website = data.website || data.companyWebsite || data.websiteUrl || "";
  const rows = isProperty
    ? [
        ["户型", data.layout],
        ["面积", data.area],
        ["价格", data.price],
        ["水电物业", data.utilities],
        ["位置", address],
        ["服务费", data.serviceFee]
      ]
    : isGroupbuy
      ? [
          ["价格", productPriceText],
          ["规格", data.spec],
          ["取货方式", data.pickupMethod],
          ["取货地点", data.pickupLocation],
          ["截止时间", data.deadline],
          ["库存", data.stockNote]
        ]
      : isBusinessCard
        ? [
            ["职位", data.title],
            ["公司 / 门店", data.company],
            ["服务范围", data.serviceScope],
            ["城市 / 区域", data.city],
            ["电话", data.phone],
            ["微信", wechat]
          ]
        : isServiceOffer
          ? [
              ["适合人群", data.targetAudience],
              ["服务内容", data.serviceContent],
              ["报价说明", data.pricingNote],
              ["服务流程", data.serviceProcess],
              ["服务地区", data.serviceArea],
              ["预约说明", data.appointmentNote],
              ["电话", contact],
              ["微信", wechat],
              ["邮箱", email],
              ["网址", website]
            ]
          : isMiniapp
            ? [["来源", miniapp.sourceName], ["房源编码", miniapp.houseCode], ["城市编码", miniapp.cityId]]
            : [["摘要", note.summary], ["正文", note.body]];
  const conversion = config.conversionConfig || {};
  const availability = buildAvailability(data, isProperty);
  const canConvert = !availability;
  const actions = [];
  if (miniapp.visible) actions.push({ key: "miniapp", title: miniapp.buttonText, desc: "打开原小程序详情" });
  if (canConvert && conversion.showContactPhone) actions.push({ key: "contact", title: "电话咨询", desc: contact ? "拨打或复制电话" : "复制联系方式" });
  if (canConvert && conversion.collectLeads) actions.push({ key: "lead", title: "留下电话/微信", desc: "方便发布者回访" });
  if (canConvert && conversion.enableAppointment) actions.push({ key: "appointment", title: isProperty ? "预约看房" : "预约沟通", desc: "选择日期和时间" });
  if (canConvert && conversion.enablePrivateConsultation) actions.push({ key: "private", title: "微信咨询", desc: "复制发布者微信/电话" });
  if (canConvert && isServiceOffer && email) actions.push({ key: "email", title: "邮箱联系", desc: "复制邮箱地址" });
  if (canConvert && (isProperty || isGroupbuy || isServiceCard)) actions.push({ key: "message", title: "发消息", desc: "站内留言给发布者" });
  if (isProperty && address) actions.push({ key: "map", title: "地图定位", desc: mapLocation.hasPoint ? "打开腾讯地图" : "按地址搜索" });
  const serviceTags = buildServiceTags(data, config, isBusinessCard, isServiceOffer);
  const salesSections = buildSalesSections(data, note, isBusinessCard, isServiceOffer);
  const salesHighlights = buildSalesHighlights(data, isBusinessCard, isServiceOffer);
  const templateName = config.displayTemplateName || (template && template.name) || "";
  const businessCardHero = isBusinessCard ? buildBusinessCardHeroView(data, note, title, subtitle, templateName, coverUrl, template) : null;
  const businessCardDetail = isBusinessCard ? buildBusinessCardDetail(data, note, businessCardHero, galleryImages) : null;
  const serviceOfferDetail = isServiceOffer ? buildServiceOfferDetail(data, note, template, galleryImages) : null;
  const serviceOfferPrimaryActions = isServiceOffer ? buildServiceOfferPrimaryActions(actions, serviceOfferDetail || {}) : [];
  const serviceOfferSecondaryActions = isServiceOffer ? buildServiceOfferSecondaryActions(actions) : [];
  const shareTitle = isBusinessCard
    ? [title, data.title, data.company].filter(Boolean).join(" · ") || "电子名片"
    : isServiceOffer
      ? [title, data.headline].filter(Boolean).join(" · ") || "服务方案"
      : isProperty
        ? buildPropertyShareTitle(title, data)
      : title || "资料详情";
  return {
    title,
    shareTitle,
    ownerUserId: note.ownerUserId || "",
    subtitle,
    isProperty,
    isGroupbuy,
    isBusinessCard,
    isServiceOffer,
    isServiceCard,
    templateId: template ? template.id : "",
    templateName,
    templateScene: config.displayTemplateScene || (template && template.scene) || "",
    templateToneClass: template ? templateToneClass(template) : "",
    serviceTags,
    salesSections,
    salesHighlights,
    businessCardDetail,
    serviceOfferDetail,
    serviceOfferPrimaryActions,
    serviceOfferSecondaryActions,
    businessCardActions: businessCardDetail ? buildBusinessCardActions(businessCardDetail) : [],
    headline: data.headline || note.summary || "",
    avatarUrl: data.avatarUrl || note.coverUrl || coverUrl || "",
    avatarInitial: String(title || "名").slice(0, 1),
    businessCardHero,
    company: data.company || "",
    position: data.title || "",
    city: data.city || data.serviceArea || "",
    enableGroupRelay: Boolean(conversion.enableGroupRelay),
    orderButtonText: conversion.enableGroupRelay ? "下单并接龙" : "下单",
    badge: isProperty ? "房源" : isGroupbuy ? "商品" : isBusinessCard ? "名片" : isServiceOffer ? "服务" : isMiniapp ? "小程序房源" : "资料",
    propertyHighlightChips: isProperty ? [data.price ? `租金 ${data.price}` : "", data.layout ? `户型 ${data.layout}` : ""].filter(Boolean) : [],
    coverUrl,
    galleryImages,
    galleryVideos,
    rows: rows.filter((item) => item[1]).map(([label, value]) => ({ label, value })),
    remark: data.bio || data.caseHighlights || data.remark || note.summary || note.body || "",
    availability,
    actions,
    hasMap: isProperty && Boolean(address),
    skuConfig,
    selectedSku: (skuConfig.skus || []).find((item) => !item.soldOut) || (skuConfig.skus || [])[0] || null,
    miniapp,
    contact,
    wechat,
    publisherName: data.ownerName || data.agentName || data.contactName || "",
    email,
    website,
    address,
    mapLocation
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

function buildGalleryVideos(note) {
  const urls = Array.isArray(note.media)
    ? note.media.filter((item) => item.type === "video").map((item) => item.url)
    : [];
  return Array.from(new Set(urls.filter(Boolean)));
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
    businessCardShareImage: "",
    serviceOfferShareImage: "",
    propertyShareImage: "",
    openedStandalone: false,
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
    const pages = getCurrentPages ? getCurrentPages() : [];
    this.setData({
      noteId: options.id || "",
      "leadDraft.phone": readLastLeadPhone(),
      openedStandalone: pages.length <= 1,
      viewSessionId: createViewSessionId("note_view"),
      pageEnterAt: Date.now(),
      maxScrollPercent: 0,
      shareId: options.sid || "",
      shareFromUserId: options.from || "",
      shareScene: options.src || options.scene || "",
      referrer: options.ref || ""
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
    try {
      const res = await api.fetchPublicNote(noteId);
      const view = buildView(res.data || {});
      rememberPropertyCity(`${view.address} ${view.title}`);
      this.setData({ view, selectedContactCard: null, showLeadForm: false, showAppointmentForm: false }, () => {
        const sku = view.selectedSku || {};
        const selectedSkuOptions = buildSelectedSkuOptions(view.skuConfig || {}, sku.key || "");
        this.setData({
          selectedSkuKey: sku.key || "",
          selectedSkuOptions,
          skuSelectionGroups: buildSkuSelectionGroups(view.skuConfig || {}, selectedSkuOptions),
          "relayDraft.phone": readLastLeadPhone()
        });
        this.resolveMapFromAddress();
        this.prepareSalesShareImage();
      });
      await this.loadCustomerActionConfig();
      this.recordCurrentView();
    } catch (error) {
      wx.showToast({ title: error.detail || "客户页加载失败", icon: "none" });
    }
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
  async loadCustomerActionConfig() {
    const { user, noteId } = this.data;
    if (!noteId) return;
    try {
      const res = await api.fetchCustomerActionConfig(noteId, user ? { viewerUserId: user.id } : { anonymousId: getNotePreviewAnonymousId() });
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
      this.setData({ actionStatus: {} });
    }
  },
  async prepareBusinessCardShareImage() {
    const view = this.data.view || {};
    if (!view.isBusinessCard || !view.businessCardHero) {
      this.setData({ businessCardShareImage: "" });
      return;
    }
    try {
      const imagePath = await this.renderBusinessCardShareImage(view.businessCardHero);
      if (imagePath) this.setData({ businessCardShareImage: imagePath });
    } catch (error) {
      this.setData({ businessCardShareImage: "" });
    }
  },
  async renderBusinessCardShareImage(card) {
    return generateBusinessCardShareImage(this, SHARE_CARD_CANVAS_ID, card);
  },
  async preparePropertyShareImage() {
    const view = this.data.view || {};
    if (!view.badge || view.badge !== "房源") {
      this.setData({ propertyShareImage: "" });
      return;
    }
    try {
      const imagePath = await generatePropertyShareImage(this, SHARE_CARD_CANVAS_ID, {
        title: view.title,
        price: (view.propertyHighlightChips || []).find((item) => String(item).includes("租金")) || "",
        layout: (view.propertyHighlightChips || []).find((item) => String(item).includes("户型")) || "",
        area: (view.rows || []).find((item) => item.label === "面积") && (view.rows || []).find((item) => item.label === "面积").value,
        address: view.address,
        coverUrl: view.coverUrl
      });
      if (imagePath) this.setData({ propertyShareImage: imagePath });
    } catch (error) {
      this.setData({ propertyShareImage: "" });
    }
  },
  async prepareServiceOfferShareImage() {
    const view = this.data.view || {};
    if (!view.isServiceOffer || !view.serviceOfferDetail) {
      this.setData({ serviceOfferShareImage: "" });
      return;
    }
    try {
      const imagePath = await generateServiceOfferShareImage(this, SHARE_CARD_CANVAS_ID, {
        ...view.serviceOfferDetail,
        templateId: view.templateId,
        templateName: view.templateName,
        title: view.title,
        summary: view.subtitle
      });
      if (imagePath) this.setData({ serviceOfferShareImage: imagePath });
    } catch (error) {
      this.setData({ serviceOfferShareImage: "" });
    }
  },
  async prepareGenericShareImage() {
    const view = this.data.view || {};
    if (!view || view.isBusinessCard || view.isServiceOffer || view.cardType === "property_listing") {
      this.setData({ genericShareImage: "" });
      return;
    }
    try {
      const imagePath = await generateTitleShareImage(this, SHARE_CARD_CANVAS_ID, {
        title: view.shareTitle || view.title || "资料详情",
        summary: view.summary || view.subtitle || "",
        badge: view.categoryName || (view.cardType === "groupbuy_product" ? "商品" : "资料"),
        coverUrl: view.coverUrl || "",
        hint: "打开小程序查看完整资料",
        growthHint: "我也想做同款"
      });
      if (imagePath) this.setData({ genericShareImage: imagePath });
    } catch (error) {
      this.setData({ genericShareImage: "" });
    }
  },
  prepareSalesShareImage() {
    this.preparePropertyShareImage();
    this.prepareBusinessCardShareImage();
    this.prepareServiceOfferShareImage();
    this.prepareGenericShareImage();
  },
  async resolveMapFromAddress() {
    const view = this.data.view || {};
    const location = view.mapLocation || {};
    if (this.data.resolvingMap || location.hasPoint || !view.address || !view.hasMap) return;
    const mapAddress = enrichAddressWithCity(view.address);
    this.setData({ resolvingMap: true });
    try {
      const res = await api.geocodeAddress({
        address: mapAddress,
        region: inferMapRegion(mapAddress)
      });
      const data = (res && res.data) || {};
      if (!data.found || !data.latitude || !data.longitude) return;
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
      this.setData({ showLeadForm: !this.data.showLeadForm });
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
    if (!user) {
      wx.showToast({ title: "登录后可发消息", icon: "none" });
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
    if (kind === "private") {
      const value = wechat || phone;
      if (value) {
        this.setData({ selectedContactCard: { label: wechat ? "微信" : "电话", value, hint: wechat ? "微信号已复制，可添加咨询" : "电话已复制" } });
        wx.setClipboardData({ data: value, success: () => wx.showToast({ title: wechat ? "微信已复制" : "电话已复制", icon: "success" }) });
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
      title: "发朋友圈",
      content: "请点击右上角菜单，选择分享到朋友圈。",
      showCancel: false,
      confirmColor: "#11924d"
    });
  },
  handlePreviewImage(event) {
    const url = event.currentTarget.dataset.url;
    const view = this.data.view || {};
    const serviceOfferDetail = view.serviceOfferDetail || {};
    const urls = [
      serviceOfferDetail.coverUrl,
      ...(serviceOfferDetail.caseImages || []),
      view.coverUrl,
      ...(view.galleryImages || [])
    ].filter(Boolean);
    if (!url || !urls.length) return;
    wx.previewImage({ current: url, urls });
  },
  handleGenerateSame() {
    const view = this.data.view || {};
    const publisherName = view.publisherName || view.wechat || view.contact || "原发布中介";
    const query = [
      "sourceType=note",
      this.data.noteId ? `sourceId=${encodeURIComponent(this.data.noteId)}` : "",
      view.title ? `sourceTitle=${encodeURIComponent(view.title)}` : "",
      publisherName ? `publisherName=${encodeURIComponent(publisherName)}` : "",
      (view.wechat || view.contact || publisherName) ? `upstreamContact=${encodeURIComponent(view.wechat || view.contact || publisherName)}` : ""
    ].filter(Boolean).join("&");
    wx.navigateTo({ url: `/pages/property-same/index?${query}` });
  },
  onShareAppMessage() {
    const view = this.data.view || {};
    const user = this.data.user || getCurrentUser();
    const shareId = createShareId(this.data.noteId);
    const shareFromUserId = user ? user.id : (this.data.shareFromUserId || "");
    const scene = "note_preview_share";
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
    const rawTitle = view.isBusinessCard && view.businessCardHero ? buildBusinessCardShareTitle(view.businessCardHero) : view.isServiceOffer ? buildServiceOfferShareTitle(view.serviceOfferDetail || view) : (view.shareTitle || view.title || "资料详情");
    return {
      title: buildCustomerShareTitle(rawTitle),
      path: `/pages/note-preview/index?id=${this.data.noteId}&sid=${shareId}&from=${shareFromUserId}&src=${scene}&ref=${this.data.shareId || ""}`,
      imageUrl: this.data.businessCardShareImage || this.data.serviceOfferShareImage || this.data.propertyShareImage || this.data.genericShareImage || ""
    };
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
    const rawTitle = view.isBusinessCard && view.businessCardHero ? buildBusinessCardShareTitle(view.businessCardHero) : view.isServiceOffer ? buildServiceOfferShareTitle(view.serviceOfferDetail || view) : (view.shareTitle || view.title || "资料详情");
    return {
      title: buildCustomerShareTitle(rawTitle),
      query: `id=${this.data.noteId}&sid=${shareId}&from=${shareFromUserId}&src=${scene}&ref=${this.data.shareId || ""}`,
      imageUrl: this.data.businessCardShareImage || this.data.serviceOfferShareImage || this.data.propertyShareImage || this.data.genericShareImage || ""
    };
  }
});
