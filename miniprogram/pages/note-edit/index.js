const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildBusinessCardShareTitle, generatePropertyShareImage, generateBusinessCardShareImage } = require("../../utils/business-card-share");
const { getSalesPageTemplates, templateToneClass } = require("../../utils/sales-page-templates");

const BUSINESS_CARD_SHARE_CANVAS_ID = "businessCardEditShareCanvas";

const TEMPLATE_META = {
  general: {
    label: "通用资料",
    fields: ["标题", "摘要", "正文"]
  },
  realtor: {
    label: "中介信息",
    fields: ["电话", "位置", "预算/价格", "客户需求"]
  },
  groupbuy: {
    label: "团购信息",
    fields: ["价格", "截止时间", "取货方式", "联系方式"]
  }
};

const SOURCE_TYPES = [
  { label: "笔记", value: "note" },
  { label: "链接", value: "link" },
  { label: "图片资料", value: "ocr" },
  { label: "图片与视频", value: "media" },
  { label: "语音", value: "voice" },
  { label: "位置", value: "location" },
  { label: "聊天记录", value: "chat" },
  { label: "文件", value: "file" },
  { label: "小程序", value: "miniapp" }
];

const SYSTEM_CATEGORIES = ["文章", "图片", "链接", "文件", "生活", "工作", "待整理"];

const CARD_TYPES = {
  link: "链接卡",
  article: "阅读卡",
  text_note: "文本卡",
  property_listing: "房源字段卡",
  groupbuy_product: "团购商品卡",
  business_card: "电子名片",
  service_offer: "服务方案卡",
  image_ocr: "图片 OCR 卡"
};

const EMPTY_SCRM_SUMMARY = {
  total: 0,
  leadContact: 0,
  appointment: 0,
  leads: 0,
  pending: 0,
  hasUnread: false,
  latestText: "暂无客户动作"
};

function formatShortTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  const hour = `${date.getHours()}`.padStart(2, "0");
  const minute = `${date.getMinutes()}`.padStart(2, "0");
  return `${month}-${day} ${hour}:${minute}`;
}

function scrmReadKey(userId, noteId) {
  return `note_scrm_read_${userId || "guest"}_${noteId || ""}`;
}

function hasUnreadCustomerAction(summary, userId, noteId) {
  if (!summary || !summary.latestActionAt) return false;
  const latest = new Date(summary.latestActionAt).getTime();
  const readAt = Number(wx.getStorageSync(scrmReadKey(userId, noteId)) || 0);
  return latest > readAt;
}

const FEATURE_PRESETS = [
  { key: "enableLightScrm", label: "轻 CRM" },
  { key: "collectLeads", label: "留言表单" },
  { key: "enableAppointment", label: "预约" },
  { key: "enableGroupRelay", label: "接龙" }
];

const WORKFLOW_STEPS = [
  { key: "collected", label: "收藏" },
  { key: "editing", label: "编辑" },
  { key: "organized", label: "整理" },
  { key: "generated", label: "生成" }
];

const PROPERTY_FIELDS = [
  { key: "community", label: "小区 / 标题", placeholder: "例如：碧桂园城市之光1栋1210" },
  { key: "layout", label: "户型", placeholder: "例如：公寓一房", quickOptions: ["公寓一房", "一室一厅", "两室一厅", "三室两厅"] },
  { key: "price", label: "价格 / 租金", placeholder: "例如：1600元/月" },
  { key: "area", label: "面积", placeholder: "例如：38㎡", quickOptions: ["30㎡内", "30-50㎡", "50㎡以上"] },
  { key: "floor", label: "楼层 / 电梯", placeholder: "例如：电梯高层", quickOptions: ["电梯房", "楼梯房", "低楼层", "高楼层"] },
  { key: "utilities", label: "水电物业", placeholder: "例如：自缴", quickOptions: ["民水民电", "商水商电", "水电自缴", "物业已含"] },
  { key: "paymentMethod", label: "押付方式", placeholder: "例如：押一付一", quickOptions: ["押一付一", "押一付三", "押二付一"] },
  { key: "moveInTime", label: "入住时间", placeholder: "例如：随时入住", quickOptions: ["随时入住", "本周可住", "月底可住"] },
  { key: "businessArea", label: "商圈 / 区域", placeholder: "例如：万家丽、高桥北", quickOptions: ["万家丽", "高桥北", "汽车东站", "袁隆平地铁口", "高桥"] },
  { key: "address", label: "地址 / 位置", placeholder: "可选" },
  { key: "serviceFee", label: "服务费", placeholder: "例如：服务费200", quickOptions: ["无服务费", "服务费200", "合同期内收一次服务费"] },
  { key: "contact", label: "联系方式", placeholder: "可选" }
];

const GROUPBUY_FIELDS = [
  { key: "productName", label: "商品名", placeholder: "例如：丹东草莓" },
  { key: "spec", label: "规格", placeholder: "例如：3斤装" },
  { key: "deadline", label: "截止时间", placeholder: "例如：今晚22点" },
  { key: "pickupMethod", label: "自提 / 配送", placeholder: "例如：包邮到家 / 小区自提", quickOptions: ["包邮到家", "小区自提", "门店自提", "统一配送"] },
  { key: "pickupLocation", label: "取货地点", placeholder: "可选" },
  { key: "stockNote", label: "库存 / 数量", placeholder: "可选", quickOptions: ["限量", "售完即止", "库存充足"] },
  { key: "contact", label: "联系方式", placeholder: "可选" }
];

const PRODUCT_INFO_FIELDS = [
  { key: "productName", label: "商品标题", placeholder: "例如：白凤乌鸡蛋 / 丹东草莓" }
];

const PRODUCT_FULFILLMENT_FIELDS = [
  { key: "pickupMethod", label: "自提 / 配送", placeholder: "例如：包邮到家 / 小区自提", quickOptions: ["包邮到家", "小区自提", "门店自提", "统一配送"] },
  { key: "pickupLocation", label: "取货地点", placeholder: "可选" },
  { key: "deadline", label: "截止时间", placeholder: "可选，例如：今晚22点" },
  { key: "stockNote", label: "库存备注", placeholder: "可选", quickOptions: ["限量", "售完即止", "库存充足"] },
  { key: "contact", label: "联系方式", placeholder: "可选" }
];

const BUSINESS_CARD_FIELDS = [
  { key: "name", label: "姓名", placeholder: "例如：王小满" },
  { key: "title", label: "职位 / 身份", placeholder: "例如：置业顾问 / 课程顾问" },
  { key: "company", label: "公司 / 门店", placeholder: "例如：某某门店" },
  { key: "serviceScope", label: "服务范围", placeholder: "例如：长沙租房、二手房咨询" },
  { key: "headline", label: "一句话介绍", placeholder: "例如：专注帮你快速找到合适房源" },
  { key: "phone", label: "电话", placeholder: "可选" },
  { key: "wechat", label: "微信", placeholder: "可选" },
  { key: "email", label: "邮箱", placeholder: "可选，例如：hello@example.com" },
  { key: "city", label: "城市 / 区域", placeholder: "例如：长沙" },
  { key: "website", label: "公司网址", placeholder: "可选，例如：https://example.com" }
];

const SERVICE_OFFER_FIELDS = [
  { key: "serviceName", label: "服务名称", placeholder: "例如：全屋收纳咨询" },
  { key: "headline", label: "一句话卖点", placeholder: "例如：一次沟通，整理出可执行方案" },
  { key: "targetAudience", label: "适合人群", placeholder: "例如：准备装修 / 想提升收纳效率的家庭" },
  { key: "pricingNote", label: "价格 / 报价说明", placeholder: "例如：到店咨询免费，方案按面积报价" },
  { key: "serviceArea", label: "服务地区", placeholder: "例如：长沙全城" },
  { key: "phone", label: "电话", placeholder: "可选" },
  { key: "wechat", label: "微信", placeholder: "可选" },
  { key: "email", label: "邮箱", placeholder: "可选，例如：hello@example.com" },
  { key: "website", label: "公司网址 / 介绍链接", placeholder: "可选，例如：https://example.com" },
  { key: "appointmentNote", label: "预约说明", placeholder: "例如：提前一天预约沟通时间" }
];

const CONVERSION_OPTIONS = [
  { key: "showContactPhone", label: "展示联系电话", desc: "生成页展示电话或联系按钮", property: true, groupbuy: true, service: true },
  { key: "enableLightScrm", label: "客户反馈记录", desc: "记录浏览、咨询、留言和待跟进", property: true, groupbuy: false, service: true },
  { key: "collectLeads", label: "留电话/微信", desc: "允许客户提交联系方式和备注", property: true, groupbuy: false, service: true },
  { key: "enableAppointment", label: "预约看房", desc: "客户页展示预约看房入口", property: true, groupbuy: false, service: true },
  { key: "enablePrivateConsultation", label: "微信咨询", desc: "客户页展示微信咨询入口", property: true, groupbuy: false, service: true },
  { key: "enableSharePoster", label: "保存分享图", desc: "保留可保存到相册的图片素材入口", property: true, groupbuy: true, service: true },
  { key: "enableGroupRelay", label: "团购接龙", desc: "团购页展示接龙/报名入口", property: false, groupbuy: true },
  { key: "enablePaymentPlaceholder", label: "下单按钮", desc: "展示下单入口，暂不接真实支付", property: false, groupbuy: false }
];

const PROPERTY_STATUS_OPTIONS = [
  { value: "active", label: "推广中" },
  { value: "rented", label: "已租" },
  { value: "paused", label: "暂停推广" }
];

const NOISY_LABELS = new Set(["未整理", "待整理", "待跟进", "已整理", "房源候选", "团购候选"]);
const PROPERTY_CONTEXT_LABELS = ["房产", "房源", "租房", "小区", "公寓", "万家丽", "高桥北", "汽车东站", "袁隆平地铁口", "高桥"];
const LAST_CONTACT_PHONE_KEY = "teambuy:lastContactPhone";
const LAST_PROPERTY_CITY_KEY = "teambuy:lastPropertyCity";
const FLOAT_SAVE_SIZE = 42;
const FLOAT_SAVE_MARGIN = 12;

function extractPhone(value) {
  const match = String(value || "").match(/1[3-9]\d{9}/);
  return match ? match[0] : "";
}

function readLastContactPhone() {
  try {
    return wx.getStorageSync(LAST_CONTACT_PHONE_KEY) || "";
  } catch (error) {
    return "";
  }
}

function rememberContactPhone(value) {
  const phone = extractPhone(value);
  if (!phone) return;
  try {
    wx.setStorageSync(LAST_CONTACT_PHONE_KEY, phone);
  } catch (error) {
    // Ignore local storage failures; saving the note itself is still the source of truth.
  }
}

function inferCityFromText(value) {
  const text = String(value || "");
  const cityMatch = text.match(/([\u4e00-\u9fff]{2,12}市)/);
  if (cityMatch) return cityMatch[1];
  if (text.includes("长沙") || text.includes("湖南")) return "长沙市";
  return "";
}

function isUsefulMapRegion(value) {
  const region = String(value || "").trim();
  return Boolean(region && /省$|市$|自治区$|特别行政区$/.test(region));
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

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (num) => `${num}`.padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatUploadDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function buildBookmark(note) {
  const config = note.visibilityConfig || {};
  const cardType = config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note");
  const userTags = filterUsefulLabels(Array.isArray(config.userTags) ? config.userTags : []);
  const tags = filterContextualLabels(Array.isArray(config.tags) ? config.tags : [], userTags, cardType);
  return {
    sourceUrl: config.sourceUrl || "",
    sourceName: config.sourceName || "链接来源",
    sourceLabel: config.sourceLabel || "网页链接",
    sourceType: config.sourceType || "link",
    systemCategory: config.systemCategory || config.category || "文章",
    category: config.systemCategory || config.category || "文章",
    tags,
    userTags,
    topics: filterContextualTopics(Array.isArray(config.topics) ? config.topics : [], cardType),
    cardType,
    cardState: config.cardState || "collected",
    collectedAtText: formatDateTime(note.createdAt)
  };
}

function buildMiniappInfo(structuredData) {
  const miniapp = (structuredData && structuredData.miniapp) || {};
  const title = miniapp.title || "";
  const sourceName = miniapp.displayName || miniapp.description || "小程序";
  const appId = miniapp.appid || "";
  const path = miniapp.pagePath || "";
  const houseCode = miniapp.houseCode || "";
  return {
    visible: Boolean(appId && path),
    title,
    sourceName,
    appId,
    path,
    houseCode,
    cityId: miniapp.cityId || "",
    buttonText: sourceName.includes("贝壳") ? "查看贝壳原房源" : "打开原小程序"
  };
}

function buildOcrInfo(config, structuredData) {
  const ocr = (structuredData && structuredData.ocr) || {};
  const visible = config.sourceType === "ocr" || config.cardType === "image_ocr" || Boolean(ocr.status || ocr.text);
  const status = ocr.status || (ocr.text ? "done" : "pending");
  const statusLabels = {
    pending: "图片已保存",
    done: "已识别文字",
    not_configured: "识别服务未开启",
    empty: "未识别到文字"
  };
  const reason = (ocr.details && ocr.details.reason) || "";
  return {
    visible,
    status,
    title: statusLabels[status] || "图片资料",
    provider: ocr.provider || "",
    configured: Boolean(ocr.configured),
    textPreview: ocr.text || structuredData.rawText || "",
    reason,
    buttonText: status === "done" ? "重新识别" : "识别文字",
    hint: status === "done"
      ? "识别结果已进入资料字段，可继续人工校对。"
      : status === "not_configured"
        ? "图片已保存，可以先手动补文字和字段；配置 PaddleOCR 或 Tesseract 后可再识别。"
        : status === "empty"
          ? "图片已保存，但本次没有提取到文字，可手动补充或重新上传更清晰图片。"
          : "先保存原图，需要文字时再识别。"
  };
}

function hydrateFields(fields, data) {
  return fields.map((field) => ({
    ...field,
    value: data && data[field.key] ? data[field.key] : "",
    quickOptions: buildFieldQuickOptions(field, data)
  }));
}

function buildFieldQuickOptions(field, data) {
  const options = [...(field.quickOptions || [])];
  if (field.key === "businessArea") {
    options.push(...splitUsefulLabels(data.businessArea || ""));
  }
  return Array.from(new Set(options.filter(Boolean))).slice(0, 8);
}

function buildMediaItems(form) {
  const items = [];
  const media = form.media || [];
  const coverInMedia = Boolean(form.coverUrl && media.some((item) => item && item.type === "image" && item.url === form.coverUrl));
  if (form.coverUrl && !coverInMedia) {
    items.push({
      key: "cover",
      type: "image",
      url: form.coverUrl,
      source: "cover",
      index: -1,
      label: "封面"
    });
  }
  media.forEach((item, index) => {
    if (!item || !item.url) return;
    items.push({
      ...item,
      key: `${item.type || "media"}-${index}-${item.url}`,
      source: "media",
      index,
      canMoveUp: index > 0,
      canMoveDown: index < media.length - 1,
      label: item.type === "image" && item.url === form.coverUrl ? "封面" : item.type === "video" ? "视频" : "图片"
    });
  });
  return items;
}

function resolveBusinessCardQrUrl(data, form) {
  const explicit = data.qrCodeUrl || data.qrcodeUrl || data.qrUrl || data.wechatQrCodeUrl || data.wechatQrUrl || data.qrCode || "";
  if (explicit) return explicit;
  const avatar = data.avatarUrl || form.coverUrl || "";
  const images = [
    ...(Array.isArray(form.media) ? form.media.filter((item) => item && item.type === "image").map((item) => item.url) : []),
    ...(Array.isArray(data.images) ? data.images : [])
  ].filter(Boolean);
  return images.find((url) => url && url !== avatar && url !== data.avatarUrl) || "";
}

function buildBusinessCardImageState(form, data) {
  if (!data) data = {};
  const avatarUrl = data.avatarUrl || form.coverUrl || "";
  const qrCodeUrl = resolveBusinessCardQrUrl(data, form);
  return {
    avatarUrl,
    qrCodeUrl,
    hasAvatar: Boolean(avatarUrl),
    hasQrCode: Boolean(qrCodeUrl)
  };
}

function buildBusinessCardTemplateOptions(currentId) {
  return getSalesPageTemplates("business_card").map((template) => ({
    id: template.id,
    name: template.name,
    scene: template.scene,
    badge: template.badge,
    toneClass: templateToneClass(template),
    active: template.id === currentId
  }));
}

function normalizePropertyStatus(value) {
  return PROPERTY_STATUS_OPTIONS.some((item) => item.value === value) ? value : "active";
}

function buildPropertyStatusOptions(value) {
  const current = normalizePropertyStatus(value);
  return PROPERTY_STATUS_OPTIONS.map((item) => ({
    ...item,
    active: item.value === current,
    className: item.value === current ? "active" : ""
  }));
}

function defaultConversionConfig(cardType) {
  if (cardType === "property_listing") {
    return {
      showContactPhone: true,
      enableLightScrm: true,
      collectLeads: true,
      enableAppointment: true,
      enablePrivateConsultation: true,
      enableSharePoster: true,
      enableGroupRelay: false,
      enablePaymentPlaceholder: false
    };
  }
  if (cardType === "groupbuy_product") {
    return {
      showContactPhone: true,
      enableLightScrm: false,
      collectLeads: false,
      enableAppointment: false,
      enablePrivateConsultation: false,
      enableSharePoster: true,
      enableGroupRelay: true,
      enablePaymentPlaceholder: false
    };
  }
  if (cardType === "business_card" || cardType === "service_offer") {
    return {
      showContactPhone: true,
      enableLightScrm: true,
      collectLeads: true,
      enableAppointment: true,
      enablePrivateConsultation: true,
      enableSharePoster: true,
      enableGroupRelay: false,
      enablePaymentPlaceholder: false
    };
  }
  return {};
}

function defaultMiniappConversionConfig(structuredData) {
  const miniapp = buildMiniappInfo(structuredData);
  if (!miniapp.visible) return {};
  return {
    showContactPhone: false,
    enableLightScrm: true,
    collectLeads: true,
    enableAppointment: true,
    enablePrivateConsultation: true,
    enableSharePoster: true,
    enableGroupRelay: false,
    enablePaymentPlaceholder: false
  };
}

function makeLocalId(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
}

function normalizeSkuConfig(structuredData) {
  const source = (structuredData && structuredData.skuConfig) || {};
  const attributeGroups = Array.isArray(source.attributeGroups)
    ? source.attributeGroups.map((group, groupIndex) => ({
        id: group.id || makeLocalId("group"),
        name: group.name || "",
        options: (Array.isArray(group.options) ? group.options : []).map((option) => ({
          id: option.id || makeLocalId("option"),
          label: option.label || option.name || ""
        }))
      }))
    : [];
  const existingSkus = Array.isArray(source.skus) ? source.skus : [];
  const comboGroups = attributeGroups
    .map((group) => ({
      ...group,
      options: (group.options || []).filter((option) => option.label)
    }))
    .filter((group) => group.options.length);
  if (!comboGroups.length) {
    return {
      attributeGroups,
      skus: attributeGroups.length ? [] : existingSkus.length ? existingSkus : [{
        id: "default",
        key: "default",
        name: structuredData.spec || structuredData.productName || "默认规格",
        price: structuredData.price || "",
        description: structuredData.pickupMethod || "",
        soldOut: false
      }]
    };
  }
  const combos = comboGroups.reduce((rows, group) => {
    const options = group.options || [];
    if (!rows.length) return options.map((option) => ({ optionIds: [option.id], labels: [option.label] }));
    return rows.flatMap((row) => options.map((option) => ({
      optionIds: [...row.optionIds, option.id],
      labels: [...row.labels, option.label]
    })));
  }, []);
  const existingByKey = existingSkus.reduce((map, sku) => {
    map[sku.key || sku.id] = sku;
    return map;
  }, {});
  return {
    attributeGroups,
    skus: combos.map((combo, index) => {
      const key = combo.optionIds.join("|");
      const existing = existingByKey[key] || {};
      const name = combo.labels.join(" / ");
      return {
        id: existing.id || `sku_${index}_${key}`,
        key,
        optionIds: combo.optionIds,
        optionLabels: combo.labels,
        name,
        price: existing.price || structuredData.price || "",
        description: existing.description || "",
        soldOut: Boolean(existing.soldOut)
      };
    })
  };
}

function buildPriceRange(skuConfig, fallback) {
  const prices = (skuConfig.skus || [])
    .filter((sku) => !sku.soldOut && sku.price)
    .map((sku) => String(sku.price).trim())
    .filter(Boolean);
  const unique = Array.from(new Set(prices));
  if (!unique.length) return fallback || "";
  if (unique.length === 1) return unique[0];
  return `${unique[0]} - ${unique[unique.length - 1]}`;
}

function buildProductPriceText(structuredData) {
  return buildPriceRange(normalizeSkuConfig(structuredData), structuredData.price);
}

function hydrateConversionOptions(cardType, config) {
  const merged = { ...defaultConversionConfig(cardType), ...(config || {}) };
  return CONVERSION_OPTIONS
    .filter((option) => (cardType === "property_listing" ? option.property : cardType === "groupbuy_product" ? option.groupbuy : ["business_card", "service_offer"].includes(cardType) ? option.service : false))
    .filter((option) => !(cardType === "business_card" && option.key === "enableAppointment"))
    .map((option) => ({
      ...option,
      checked: Boolean(merged[option.key])
    }));
}

function hydrateFeaturePresets(config) {
  const merged = config || {};
  return FEATURE_PRESETS.map((item) => ({
    ...item,
    active: Boolean(merged[item.key])
  }));
}

function buildSuggestionButtons(suggestions) {
  const labels = {
    property_listing: "房源",
    groupbuy_product: "商品",
    business_card: "名片",
    service_offer: "服务",
    text_note: "普通笔记"
  };
  return (Array.isArray(suggestions) ? suggestions : [])
    .filter((item) => item && item.cardType && item.cardType !== "text_note")
    .map((item) => ({
      cardType: item.cardType,
      label: labels[item.cardType] || item.label || "确认类型",
      reason: item.reason || "",
      signalsText: Array.isArray(item.signals) && item.signals.length ? item.signals.slice(0, 4).join("、") : "",
      confidenceText: item.confidence ? `${Math.round(Number(item.confidence) * 100)}%` : ""
    }));
}

function hiddenSectionMap(config) {
  const sections = Array.isArray(config.hiddenSections) ? config.hiddenSections : [];
  return sections.reduce((map, key) => ({ ...map, [key]: true }), {});
}

function normalizeCardState(state) {
  return ["collected", "editing", "organized", "generated"].includes(state) ? state : "collected";
}

function buildWorkflowSteps(activeState) {
  const activeIndex = WORKFLOW_STEPS.findIndex((item) => item.key === activeState);
  return WORKFLOW_STEPS.map((item, index) => ({
    ...item,
    number: index + 1,
    active: item.key === activeState,
    done: index < activeIndex,
    className: item.key === activeState ? "active" : index < activeIndex ? "done" : ""
  }));
}

function getStateTitle(cardType, state) {
  const isProperty = cardType === "property_listing";
  const noun = isProperty ? "房源" : cardType === "groupbuy_product" ? "团购" : cardType === "business_card" ? "名片" : cardType === "service_offer" ? "服务方案" : "资料";
  const titles = {
    collected: `${noun}已收藏`,
    editing: `编辑${noun}资料`,
    organized: `${noun}整理结果`,
    generated: `${noun}页已生成`
  };
  return titles[state] || "资料详情";
}

function getStateHint(cardType, state) {
  const isProperty = cardType === "property_listing";
  const isService = cardType === "business_card" || cardType === "service_offer";
  const hints = {
    collected: isProperty ? "系统已识别为房源候选，先确认内容，再进入字段编辑。" : isService ? "先补齐展示给客户看的身份、服务和联系方式。" : "系统已识别资料类型，先确认内容，再进入字段编辑。",
    editing: isProperty ? "先把房源字段修准，转化功能单独配置，不混进房源本体字段。" : isService ? "服务内容和客户动作分开保存，方便统一查看客户反馈。" : "先把商品字段修准，转化功能单独配置。",
    organized: "系统已按字段整理，重点检查待确认项和生成建议。",
    generated: "当前是生成态管理预览，可查看启用动作并继续回到编辑。"
  };
  return hints[state] || "";
}

function buildRawPreviewLines(note, structuredData) {
  const lines = String(note.body || "")
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 8);
  if (lines.length) return lines;
  return [
    note.title,
    note.summary,
    structuredData.price,
    structuredData.layout || structuredData.spec,
    structuredData.businessArea || structuredData.pickupMethod,
    structuredData.serviceFee || structuredData.pickupLocation
  ].filter(Boolean);
}

function buildKeyChips(cardType, structuredData, config) {
  const chips = [];
  if (cardType === "property_listing") {
    chips.push("房源候选");
    if (structuredData.price) chips.push(structuredData.price);
    if (structuredData.layout) chips.push(structuredData.layout);
    if (structuredData.businessArea) chips.push(structuredData.businessArea);
  } else if (cardType === "groupbuy_product") {
    chips.push("团购候选");
    const priceText = buildProductPriceText(structuredData);
    if (priceText) chips.push(priceText);
    if (structuredData.spec) chips.push(structuredData.spec);
    if (structuredData.pickupMethod) chips.push(structuredData.pickupMethod);
  } else if (cardType === "business_card") {
    chips.push("电子名片");
    if (structuredData.name) chips.push(structuredData.name);
    if (structuredData.title) chips.push(structuredData.title);
    if (structuredData.serviceScope) chips.push(structuredData.serviceScope);
  } else if (cardType === "service_offer") {
    chips.push("服务方案");
    if (structuredData.serviceName) chips.push(structuredData.serviceName);
    if (structuredData.pricingNote) chips.push(structuredData.pricingNote);
    if (structuredData.serviceArea) chips.push(structuredData.serviceArea);
  }
  chips.push(config.sourceName || "企业微信导入");
  return chips.filter(Boolean).slice(0, 5);
}

function buildReviewRows(fields, structuredData) {
  return fields.map((field) => {
    const value = structuredData[field.key] || "";
    return {
      key: field.key,
      label: field.label,
      value: value || "待确认",
      warning: !value
    };
  });
}

function buildMissingWarnings(cardType, structuredData) {
  const checks = cardType === "property_listing"
    ? [
        ["contact", "联系方式待确认"],
        ["address", "详细地址不完整"],
        ["price", "租金待确认"]
      ]
    : cardType === "groupbuy_product" ? [
        ["contact", "联系方式待确认"],
        ["pickupLocation", "取货地点待确认"]
      ] : cardType === "business_card" ? [
        ["name", "姓名待确认"],
        ["phone", "电话待确认"],
        ["serviceScope", "服务范围待确认"]
      ] : cardType === "service_offer" ? [
        ["serviceName", "服务名称待确认"],
        ["serviceContent", "服务内容待确认"],
        ["contact", "联系方式待确认"]
      ] : [];
  return checks.filter(([key]) => !structuredData[key]).map(([, label]) => label);
}

function buildPropertyCustomerPreview(form = {}, structuredData = {}, conversionConfig = {}) {
  const title = form.title || structuredData.community || "房源标题待补";
  const firstImage = (form.media || []).find((item) => item && item.type === "image" && item.url);
  const coverUrl = form.coverUrl || (firstImage && firstImage.url) || "";
  const location = structuredData.businessArea || structuredData.address || "位置待补";
  const highlights = [
    structuredData.price || "租金待补",
    structuredData.layout || "户型待补",
    structuredData.area,
    structuredData.floor,
    structuredData.paymentMethod,
    structuredData.moveInTime
  ].filter(Boolean).slice(0, 6);
  const actions = [
    conversionConfig.showContactPhone ? "电话" : "",
    conversionConfig.enablePrivateConsultation ? "微信咨询" : "",
    conversionConfig.enableAppointment ? "预约看房" : "",
    conversionConfig.collectLeads ? "留电话/微信" : ""
  ].filter(Boolean);
  return {
    title,
    coverUrl,
    location,
    highlights,
    remark: structuredData.remark || "亮点待补",
    actions: actions.length ? actions : ["未开启联系入口"]
  };
}

function buildPropertyPublishChecks(form = {}, structuredData = {}, conversionConfig = {}) {
  const hasImage = Boolean(form.coverUrl || (form.media || []).some((item) => item && item.type === "image" && item.url));
  const checks = [
    { key: "cover", label: "封面图片", ok: hasImage, fix: "建议设置一张客户第一眼能看清的房源图" },
    { key: "price", label: "租金", ok: Boolean(structuredData.price), fix: "补租金后客户更容易判断是否合适" },
    { key: "layout", label: "户型", ok: Boolean(structuredData.layout), fix: "补户型，方便客户快速筛选" },
    { key: "location", label: "位置", ok: Boolean(structuredData.businessArea || structuredData.address), fix: "补商圈或地址，减少反复询问" },
    { key: "contact", label: "联系方式", ok: Boolean(structuredData.contact || form.phone || conversionConfig.collectLeads || conversionConfig.enablePrivateConsultation), fix: "至少开启一种联系方式或留言入口" }
  ];
  const status = normalizePropertyStatus(structuredData.propertyStatus);
  if (status === "rented") {
    checks.push({ key: "status", label: "房源状态", ok: false, fix: "当前是已租，发给客户前建议确认是否还可推荐" });
  } else if (status === "paused") {
    checks.push({ key: "status", label: "房源状态", ok: false, fix: "当前暂停推广，发布前建议改为可租或确认用途" });
  }
  return checks.map((item) => ({
    ...item,
    tone: item.ok ? "ok" : "warn",
    statusText: item.ok ? "已完成" : "待完善"
  }));
}

function buildProductCustomerPreview(form = {}, structuredData = {}, conversionConfig = {}) {
  const title = structuredData.productName || form.title || "商品标题待补";
  const firstImage = (form.media || []).find((item) => item && item.type === "image" && item.url);
  const coverUrl = form.coverUrl || (firstImage && firstImage.url) || "";
  const priceText = buildProductPriceText(structuredData);
  const highlights = [
    priceText || "价格待补",
    structuredData.spec,
    structuredData.pickupMethod,
    structuredData.deadline ? `截止 ${structuredData.deadline}` : ""
  ].filter(Boolean).slice(0, 5);
  const actions = [
    conversionConfig.enableGroupRelay ? "下单并接龙" : "下单",
    conversionConfig.showContactPhone ? "电话联系" : "",
    conversionConfig.enableSharePoster ? "保存分享图" : ""
  ].filter(Boolean);
  return {
    title,
    coverUrl,
    location: structuredData.pickupLocation || "取货地点待补",
    highlights,
    remark: structuredData.remark || "商品卖点待补",
    actions: actions.length ? actions : ["未开启下单入口"]
  };
}

function buildProductPublishChecks(form = {}, structuredData = {}, conversionConfig = {}) {
  const hasImage = Boolean(form.coverUrl || (form.media || []).some((item) => item && item.type === "image" && item.url));
  const skuConfig = normalizeSkuConfig(structuredData);
  const hasPrice = Boolean(buildProductPriceText(structuredData));
  const hasAvailableSku = (skuConfig.skus || []).some((sku) => !sku.soldOut);
  const checks = [
    { key: "cover", label: "商品图片", ok: hasImage, fix: "建议设置一张清晰商品图，发群更容易成交" },
    { key: "name", label: "商品名称", ok: Boolean(structuredData.productName || form.title), fix: "补商品名，客户才能快速判断是什么" },
    { key: "price", label: "价格 / 规格", ok: hasPrice, fix: "补价格或 SKU 价格，避免客户反复询问" },
    { key: "pickup", label: "取货方式", ok: Boolean(structuredData.pickupMethod || structuredData.pickupLocation), fix: "补自提、配送或取货地点" },
    { key: "contact", label: "联系方式", ok: Boolean(structuredData.contact || form.phone || conversionConfig.showContactPhone || conversionConfig.enableGroupRelay), fix: "至少保留接龙或联系方式，方便客户提交" }
  ];
  if ((skuConfig.skus || []).length && !hasAvailableSku) {
    checks.push({ key: "sku", label: "SKU 库存", ok: false, fix: "当前所有规格都售罄，发群前建议确认库存" });
  }
  return checks.map((item) => ({
    ...item,
    tone: item.ok ? "ok" : "warn",
    statusText: item.ok ? "已完成" : "待完善"
  }));
}

function buildEnabledLabels(options) {
  return (options || []).filter((item) => item.checked).map((item) => item.label);
}

function buildEnabledCustomerFeatures(options) {
  return (options || [])
    .filter((item) => item.checked && ["showContactPhone", "enableLightScrm", "collectLeads", "enableAppointment", "enablePrivateConsultation"].includes(item.key))
    .map((item) => item.label);
}

function buildGenerationOptions(cardType, structuredData) {
  const result = structuredData.organizeResult || {};
  if (Array.isArray(result.generationOptions) && result.generationOptions.length) {
    return result.generationOptions;
  }
  if (cardType === "property_listing") return ["房源推广页", "微信群文案", "客户话术", "对比表"];
  if (cardType === "groupbuy_product") return ["团购分享图", "发群文案", "接龙格式", "商品卖点"];
  if (cardType === "business_card") return ["个人名片页", "微信介绍文案", "客户沟通话术"];
  if (cardType === "service_offer") return ["服务介绍页", "咨询邀约文案", "客户沟通话术"];
  return [];
}

function buildGeneratedActions(structuredData, enabledLabels) {
  const generated = structuredData.generatedResult || {};
  return Array.isArray(generated.enabledActions) && generated.enabledActions.length
    ? generated.enabledActions
    : enabledLabels;
}

function buildDisplayTitle(cardType, form, structuredData) {
  if (cardType === "property_listing") return form.title || structuredData.community || "房源资料";
  if (cardType === "groupbuy_product") return structuredData.productName || form.title || "团购商品";
  if (cardType === "business_card") return structuredData.name || form.title || "电子名片";
  if (cardType === "service_offer") return structuredData.serviceName || form.title || "服务方案";
  return form.title || "资料";
}

function buildDisplaySubtitle(cardType, form, structuredData) {
  if (cardType === "property_listing") {
    return [structuredData.price, structuredData.layout, structuredData.area, structuredData.businessArea].filter(Boolean).join(" · ") || form.summary || "房源信息";
  }
  if (cardType === "groupbuy_product") {
    const skuConfig = normalizeSkuConfig(structuredData);
    return [buildPriceRange(skuConfig, structuredData.price), structuredData.spec, structuredData.pickupMethod].filter(Boolean).join(" · ") || form.summary || "商品信息";
  }
  if (cardType === "business_card") {
    return [structuredData.title, structuredData.company, structuredData.serviceScope].filter(Boolean).join(" · ") || form.summary || "个人顾问信息";
  }
  if (cardType === "service_offer") {
    return [structuredData.headline, structuredData.pricingNote, structuredData.serviceArea].filter(Boolean).join(" · ") || form.summary || "服务介绍";
  }
  return form.summary || "";
}

function buildBusinessCardHero(form, structuredData, templateName) {
  const name = structuredData.name || form.title || "电子名片";
  const role = structuredData.title || "个人顾问";
  const company = structuredData.company || "我的公司 / 门店";
  const serviceScope = structuredData.serviceScope || structuredData.headline || form.summary || "补充服务范围后即可发给客户";
  const phone = structuredData.phone || form.phone || "";
  const wechat = structuredData.wechat || structuredData.contactWechat || "";
  const email = structuredData.email || "";
  const contactLine = [phone, wechat, email].filter(Boolean).join(" · ") || "补充电话 / 微信 / 邮箱";
  return {
    name,
    role,
    company,
    serviceScope,
    contactLine,
    templateName: templateName || "电子名片",
    templateId: ((form.visibilityConfig || {}).displayTemplate) || "",
    tone: ((form.visibilityConfig || {}).displayTemplateTone) || "",
    avatarUrl: structuredData.avatarUrl || form.coverUrl || "",
    initial: String(name || "名").slice(0, 1)
  };
}

function buildShareText(cardType, form, structuredData) {
  if (cardType === "property_listing") {
    return [
      structuredData.community || form.title,
      structuredData.layout ? `户型：${structuredData.layout}` : "",
      structuredData.area ? `面积：${structuredData.area}` : "",
      structuredData.price ? `价格：${structuredData.price}` : "",
      structuredData.address || structuredData.businessArea ? `位置：${structuredData.address || structuredData.businessArea}` : "",
      structuredData.remark || form.summary
    ].filter(Boolean).join("\n");
  }
  if (cardType === "groupbuy_product") {
    const priceText = buildProductPriceText(structuredData);
    return [
      structuredData.productName || form.title,
      priceText ? `价格：${priceText}` : "",
      structuredData.spec ? `规格：${structuredData.spec}` : "",
      structuredData.pickupMethod ? `取货：${structuredData.pickupMethod}` : "",
      structuredData.deadline ? `截止：${structuredData.deadline}` : "",
      structuredData.remark || form.summary
    ].filter(Boolean).join("\n");
  }
  if (cardType === "business_card") {
    return [
      structuredData.name || form.title,
      [structuredData.title, structuredData.company].filter(Boolean).join(" · "),
      structuredData.serviceScope ? `服务：${structuredData.serviceScope}` : "",
      structuredData.headline || form.summary,
      structuredData.phone ? `电话：${structuredData.phone}` : "",
      structuredData.wechat ? `微信：${structuredData.wechat}` : "",
      structuredData.email ? `邮箱：${structuredData.email}` : ""
    ].filter(Boolean).join("\n");
  }
  if (cardType === "service_offer") {
    return [
      structuredData.serviceName || form.title,
      structuredData.headline || form.summary,
      structuredData.targetAudience ? `适合：${structuredData.targetAudience}` : "",
      structuredData.pricingNote ? `报价：${structuredData.pricingNote}` : "",
      structuredData.serviceArea ? `地区：${structuredData.serviceArea}` : "",
      structuredData.contact ? `联系：${structuredData.contact}` : ""
    ].filter(Boolean).join("\n");
  }
  return [form.title, form.summary, form.body].filter(Boolean).join("\n");
}

function buildPropertyShareTitle(form, structuredData) {
  const headline = form.title || structuredData.community || "房源资料";
  const chips = [structuredData.price, structuredData.layout].filter(Boolean);
  return chips.length ? `${headline}\n${chips.join(" · ")}` : headline;
}

function buildCustomerTalkText(cardType, form, structuredData) {
  if (cardType === "property_listing") {
    return [
      structuredData.community || form.title,
      [structuredData.price, structuredData.layout, structuredData.area].filter(Boolean).join(" · "),
      structuredData.businessArea || structuredData.address ? `位置：${structuredData.businessArea || structuredData.address}` : "",
      structuredData.utilities ? `水电物业：${structuredData.utilities}` : "",
      structuredData.serviceFee ? `服务费：${structuredData.serviceFee}` : "",
      structuredData.remark || form.summary,
      structuredData.contact ? `联系：${structuredData.contact}` : ""
    ].filter(Boolean).join("\n");
  }
  if (cardType === "groupbuy_product") {
    const priceText = buildProductPriceText(structuredData);
    return [
      structuredData.productName || form.title,
      [priceText, structuredData.spec].filter(Boolean).join(" · "),
      structuredData.pickupMethod ? `取货：${structuredData.pickupMethod}` : "",
      structuredData.deadline ? `截止：${structuredData.deadline}` : "",
      structuredData.remark || form.summary,
      structuredData.contact ? `联系：${structuredData.contact}` : ""
    ].filter(Boolean).join("\n");
  }
  if (cardType === "business_card") {
    return buildShareText(cardType, form, structuredData);
  }
  if (cardType === "service_offer") {
    return [
      structuredData.serviceName || form.title,
      structuredData.headline || form.summary,
      structuredData.serviceContent,
      structuredData.serviceProcess ? `流程：${structuredData.serviceProcess}` : "",
      structuredData.appointmentNote ? `预约：${structuredData.appointmentNote}` : "",
      structuredData.contact ? `联系：${structuredData.contact}` : ""
    ].filter(Boolean).join("\n");
  }
  return buildShareText(cardType, form, structuredData);
}

function buildStructuredDataForType(cardType, form, current) {
  const images = buildImageUrls(form);
  const miniapp = current.miniapp ? { miniapp: current.miniapp } : {};
  if (cardType === "property_listing") {
    return {
      ...miniapp,
      community: current.community || form.title,
      layout: current.layout || "",
      area: current.area || "",
      price: current.price || "",
      utilities: current.utilities || "",
      businessArea: current.businessArea || "",
      address: current.address || form.locationText || "",
      serviceFee: current.serviceFee || "",
      contact: current.contact || form.phone || "",
      propertyStatus: normalizePropertyStatus(current.propertyStatus),
      remark: current.remark || form.summary || form.body,
      images,
      rawText: current.rawText || form.body
    };
  }
  if (cardType === "groupbuy_product") {
    return {
      ...miniapp,
      productName: current.productName || form.title,
      price: current.price || "",
      spec: current.spec || "",
      deadline: current.deadline || "",
      pickupMethod: current.pickupMethod || "",
      pickupLocation: current.pickupLocation || form.locationText || "",
      stockNote: current.stockNote || "",
      contact: current.contact || form.phone || "",
      remark: current.remark || form.summary || form.body,
      skuConfig: normalizeSkuConfig(current),
      images,
      rawText: current.rawText || form.body
    };
  }
  if (cardType === "business_card") {
    return {
      ...miniapp,
      name: current.name || form.title,
      title: current.title || "",
      company: current.company || "",
      serviceScope: current.serviceScope || "",
      headline: current.headline || form.summary || "",
      bio: current.bio || form.body,
      phone: current.phone || form.phone || "",
      wechat: current.wechat || "",
      email: current.email || "",
      city: current.city || form.locationText || "",
      website: current.website || "",
      avatarUrl: current.avatarUrl || form.coverUrl || "",
      qrCodeUrl: current.qrCodeUrl || "",
      images,
      rawText: current.rawText || form.body
    };
  }
  if (cardType === "service_offer") {
    return {
      ...miniapp,
      serviceName: current.serviceName || form.title,
      headline: current.headline || form.summary || "",
      targetAudience: current.targetAudience || "",
      serviceContent: current.serviceContent || form.body,
      pricingNote: current.pricingNote || "",
      serviceProcess: current.serviceProcess || "",
      caseHighlights: current.caseHighlights || "",
      serviceArea: current.serviceArea || form.locationText || "",
      contact: current.contact || form.phone || "",
      appointmentNote: current.appointmentNote || "",
      images,
      rawText: current.rawText || form.body
    };
  }
  return { ...miniapp, rawText: form.body, images };
}

function buildImageUrls(form) {
  return Array.from(new Set([form.coverUrl, ...(form.media || []).filter((item) => item.type === "image").map((item) => item.url)].filter(Boolean)));
}

function splitUsefulLabels(value) {
  return String(value || "")
    .split(/[、,，/｜|\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function isUsefulLabel(label) {
  const value = String(label || "").trim();
  if (!value || NOISY_LABELS.has(value)) return false;
  if (/^\d{3,5}-\d{3,5}$/.test(value)) return true;
  return value.length <= 10;
}

function filterUsefulLabels(values) {
  return Array.from(new Set((values || []).map((item) => String(item || "").trim()).filter(isUsefulLabel)));
}

function isPropertyContextLabel(label) {
  const value = String(label || "").trim();
  return Boolean(value && PROPERTY_CONTEXT_LABELS.some((keyword) => value.includes(keyword)));
}

function filterContextualLabels(labels, userLabels, cardType) {
  const userSet = new Set(userLabels || []);
  const useful = filterUsefulLabels(labels || []);
  if (cardType === "property_listing") return useful;
  return useful.filter((label) => userSet.has(label) || !isPropertyContextLabel(label));
}

function filterContextualTopics(topics, cardType) {
  const items = (topics || []).filter((topic) => topic && topic.id && topic.name);
  if (cardType === "property_listing") return items;
  return items.filter((topic) => !isPropertyContextLabel(topic.name));
}

function buildMapPreview(structuredData) {
  const location = structuredData.mapLocation || {};
  const latitude = Number(location.latitude);
  const longitude = Number(location.longitude);
  const address = location.address || structuredData.address || structuredData.businessArea || "";
  if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
    return {
      hasPoint: true,
      latitude,
      longitude,
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
  return {
    hasPoint: false,
    latitude: 0,
    longitude: 0,
    address,
    markers: []
  };
}

function buildMapAddress(structuredData) {
  return buildMapAddressCandidates(structuredData)[0] || "";
}

function buildMapAddressCandidates(structuredData) {
  const source = structuredData || {};
  const fields = {
    address: String(source.address || "").trim(),
    community: String(source.community || "").trim(),
    businessArea: String(source.businessArea || "").trim()
  };
  const candidates = [
    fields.address,
    [fields.address, fields.community].filter(Boolean).join(" "),
    [fields.community, fields.businessArea].filter(Boolean).join(" "),
    fields.community,
    [fields.address, fields.community, fields.businessArea].filter(Boolean).join(" ")
  ]
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .filter((item, index, arr) => arr.indexOf(item) === index);
  const remembered = readLastPropertyCity();
  const city = inferCityFromText(candidates.join(" ")) || (isUsefulMapRegion(remembered) ? remembered : "");
  if (!city) return candidates;
  const withCity = candidates.map((item) => (
    item.includes(city) || item.includes(city.replace("市", "")) ? item : `${city} ${item}`
  ));
  return [...candidates, ...withCity].filter((item, index, arr) => arr.indexOf(item) === index);
}

function inferMapRegion(structuredData) {
  const text = buildMapAddress(structuredData);
  const city = inferCityFromText(text);
  if (city) return city;
  const remembered = readLastPropertyCity();
  if (isUsefulMapRegion(remembered)) return remembered;
  if (text.includes("长沙")) return "长沙市";
  if (text.includes("湖南")) return "湖南省";
  return "";
}

function shouldDropMapLocation(current, key, value) {
  if (key !== "address") return false;
  if (!current.mapLocation || !current.mapLocation.latitude || !current.mapLocation.longitude) return false;
  const nextAddress = String(value || "").trim();
  const oldAddress = String(current.mapLocation.address || current.address || "").trim();
  return Boolean(nextAddress && oldAddress && nextAddress !== oldAddress);
}

function buildSuggestedTagOptions(cardType, structuredData, form, config) {
  const existing = new Set([...(config.tags || []), ...(config.userTags || [])]);
  const base = cardType === "property_listing"
    ? ["房产", "房源", ...splitUsefulLabels(structuredData.businessArea), structuredData.layout]
    : cardType === "groupbuy_product"
      ? ["团购", "商品", structuredData.productName, structuredData.pickupMethod]
      : cardType === "business_card"
        ? ["名片", "顾问", structuredData.title, structuredData.company, ...splitUsefulLabels(structuredData.serviceScope)]
        : cardType === "service_offer"
          ? ["服务", "方案", "咨询", structuredData.serviceName]
          : [];
  return filterUsefulLabels(base).filter((item) => !existing.has(item)).slice(0, 6);
}

function buildCommonTagOptions(categories = [], config = {}) {
  const existing = new Set([...(config.tags || []), ...(config.userTags || [])].map((item) => String(item || "").trim()));
  return (categories || [])
    .map((item) => String(item.name || "").trim())
    .filter((name) => name && !existing.has(name))
    .slice(0, 12);
}

function parsePropertyRent(value) {
  const text = String(value || "");
  const labeled = text.match(/(?:租金|价格|房租)?[：:\s]*([1-9]\d{2,5})\s*(?:元|块|\/月|每月|月租|月)?/);
  return labeled ? Number(labeled[1]) : 0;
}

function buildPropertySystemTags(structuredData = {}) {
  const text = [
    structuredData.price,
    structuredData.layout,
    structuredData.area,
    structuredData.floor,
    structuredData.address,
    structuredData.businessArea,
    structuredData.paymentMethod,
    structuredData.moveInTime,
    structuredData.remark,
    structuredData.utilities
  ].filter(Boolean).join(" ");
  const rent = parsePropertyRent(structuredData.price || "");
  const tags = ["房源"];
  if (rent) {
    if (rent <= 1300) tags.push("1300以下");
    else if (rent <= 1800) tags.push("1300-1800");
    else if (rent <= 2500) tags.push("1800-2500");
    else tags.push("2500以上");
  }
  if (/公寓/.test(text)) tags.push("公寓");
  if (/([1-2]\d|30)㎡?内|小户型/.test(text)) tags.push("小户型");
  if (/30\s*[-至]\s*50|3\d㎡|4\d㎡/.test(text)) tags.push("30-50㎡");
  if (/50㎡?以上|[5-9]\d㎡/.test(text)) tags.push("50㎡以上");
  if (/(一房|一室|公寓一房)/.test(text)) tags.push("一房");
  if (/(两房|两室|二房|二室)/.test(text)) tags.push("两房");
  if (/(三房|三室)/.test(text)) tags.push("三房");
  if (/(地铁口|地铁站|近地铁|步行.*地铁)/.test(text)) tags.push("地铁口");
  else if (/地铁/.test(text)) tags.push("地铁");
  if (/电梯/.test(text)) tags.push("电梯房");
  if (/楼梯/.test(text)) tags.push("楼梯房");
  if (/押一付一/.test(text)) tags.push("押一付一");
  if (/押一付三/.test(text)) tags.push("押一付三");
  if (/随时入住|拎包入住|空置/.test(text)) tags.push("随时入住");
  if (/本周可住|本周入住/.test(text)) tags.push("本周可住");
  const status = normalizePropertyStatus(structuredData.propertyStatus);
  if (status === "active") tags.push("可租");
  if (status === "rented") tags.push("已租");
  if (status === "paused") tags.push("暂停推广");
  if (!rent || !structuredData.layout) tags.push("待确认");
  return filterUsefulLabels(tags);
}

function buildGroupbuySystemTags(structuredData = {}) {
  const skuConfig = normalizeSkuConfig(structuredData);
  const text = [
    structuredData.productName,
    structuredData.price,
    structuredData.spec,
    structuredData.pickupMethod,
    structuredData.pickupLocation,
    structuredData.deadline,
    structuredData.remark
  ].filter(Boolean).join(" ");
  const tags = ["团购", "商品"];
  if (/自提|小区取|到店取/.test(text)) tags.push("自提");
  if (/配送|送货|送上门/.test(text)) tags.push("配送");
  if (/快递|邮寄/.test(text)) tags.push("快递");
  if (/今日截止|今天截止|今晚截止|当天截止/.test(text)) tags.push("今日截止");
  else if (/本周截止|周末截止|这周截止|截止/.test(text)) tags.push("本周截止");
  if ((skuConfig.skus || []).length > 1) tags.push("有SKU");
  if ((skuConfig.skus || []).length && (skuConfig.skus || []).every((sku) => sku.soldOut)) tags.push("已售罄");
  const priceText = buildProductPriceText(structuredData);
  if (!priceText) tags.push("待补价格");
  if (!structuredData.pickupMethod && !structuredData.pickupLocation) tags.push("待补取货");
  return filterUsefulLabels(tags);
}

function applySystemTagsToConfig(config = {}, structuredData = {}) {
  if (!["property_listing", "groupbuy_product"].includes(config.cardType || "")) return config;
  const systemTags = config.cardType === "groupbuy_product"
    ? buildGroupbuySystemTags(structuredData)
    : buildPropertySystemTags(structuredData);
  const previousSystemTags = new Set(Array.isArray(config.systemTags) ? config.systemTags : []);
  const userTags = filterUsefulLabels(config.userTags || []);
  const preservedTags = filterUsefulLabels(config.tags || []).filter((tag) => !previousSystemTags.has(tag));
  return {
    ...config,
    userTags,
    systemTags,
    tags: filterUsefulLabels([...systemTags, ...preservedTags, ...userTags])
  };
}

function buildSuggestedTopicOptions(cardType, structuredData, form, topics, config) {
  const assigned = new Set((config.topics || []).map((item) => item.name).filter(Boolean));
  const base = cardType === "property_listing"
    ? [structuredData.businessArea ? `${splitUsefulLabels(structuredData.businessArea)[0] || structuredData.businessArea}房源` : ""]
    : cardType === "groupbuy_product"
      ? [isUsefulLabel(structuredData.productName) ? `${structuredData.productName}团购` : "", "团购资料"]
      : cardType === "business_card"
        ? [structuredData.name ? `${structuredData.name}名片` : "", "顾问名片"]
        : cardType === "service_offer"
          ? [isUsefulLabel(structuredData.serviceName) ? `${structuredData.serviceName}服务` : "", "服务方案"]
          : [];
  const existingNames = new Set((topics || []).map((item) => item.name).filter(Boolean));
  return base
    .map((item) => String(item || "").trim())
    .filter((item, index, arr) => isUsefulLabel(item) && arr.indexOf(item) === index && !assigned.has(item))
    .map((name) => ({ name, existing: existingNames.has(name) }))
    .slice(0, 4);
}

Page({
  data: {
    user: null,
    noteId: "",
    template: TEMPLATE_META.general,
    form: {
      title: "",
      summary: "",
      body: "",
      coverUrl: "",
      phone: "",
      locationText: "",
      categoryIds: [],
      media: [],
      visibilityConfig: {}
    },
    isBookmark: false,
    isPlainNote: false,
    plainNoteOpsOpen: false,
    abilityPluginOpen: false,
    abilityPlugins: [
      { key: "message", name: "留言", status: "按需添加", desc: "让查看者留下补充说明或反馈。" },
      { key: "consult", name: "咨询", status: "按需添加", desc: "适合需要进一步沟通的资料。" },
      { key: "relay", name: "接龙", status: "按需添加", desc: "适合报名、收集名单或轻量统计。" }
    ],
    showOperationalControls: true,
    bookmark: {},
    sourceTypes: SOURCE_TYPES,
    systemCategories: SYSTEM_CATEGORIES,
    cardTypeLabel: CARD_TYPES.text_note,
    isProperty: false,
    isGroupbuy: false,
    isBusinessCard: false,
    isServiceOffer: false,
    isServiceCard: false,
    cardState: "collected",
    workflowSteps: buildWorkflowSteps("collected"),
    stateTitle: "资料已收藏",
    stateHint: "",
    rawPreviewLines: [],
    keyChips: [],
    reviewRows: [],
    missingWarnings: [],
    organizeSummary: "",
    generationOptions: [],
    enabledActionLabels: [],
    generatedActions: [],
    miniappInfo: buildMiniappInfo({}),
    ocrInfo: buildOcrInfo({}, {}),
    structuredData: {},
    skuConfig: normalizeSkuConfig({}),
    conversionConfig: {},
    conversionOptions: [],
    customerFeatureLabels: [],
    featureSettingsOpen: false,
    featurePresets: hydrateFeaturePresets({}),
    suggestionButtons: [],
    recognitionExplanation: {},
    hiddenSections: {},
    uploadDateText: "",
    noteCreatedAt: "",
    displayTitle: "",
    displaySubtitle: "",
    displayTemplateName: "",
    businessCardTemplates: buildBusinessCardTemplateOptions(""),
    businessCardHero: null,
    businessCardShareImage: "",
    propertyShareImage: "",
    activePropertyDetailTab: "operate",
    businessCardImages: buildBusinessCardImageState({ media: [] }, {}),
    mediaCountText: "",
    mediaItems: [],
    propertyStatusOptions: buildPropertyStatusOptions("active"),
    propertyCustomerPreview: buildPropertyCustomerPreview(),
    propertyPublishChecks: [],
    productCustomerPreview: buildProductCustomerPreview(),
    productPublishChecks: [],
    showGroupbuyEdit: false,
    showTagTopicPanel: true,
    mapPreview: buildMapPreview({}),
    geocodingAddress: false,
    propertyFields: hydrateFields(PROPERTY_FIELDS, {}),
    groupbuyFields: hydrateFields(GROUPBUY_FIELDS, {}),
    productInfoFields: hydrateFields(PRODUCT_INFO_FIELDS, {}),
    productFulfillmentFields: hydrateFields(PRODUCT_FULFILLMENT_FIELDS, {}),
    businessCardFields: hydrateFields(BUSINESS_CARD_FIELDS, {}),
    serviceOfferFields: hydrateFields(SERVICE_OFFER_FIELDS, {}),
    topics: [],
    globalCategories: [],
    commonTagOptions: [],
    tagDraft: "",
    topicDraft: "",
    tagTopicOpen: false,
    suggestedTagOptions: [],
    suggestedTopicOptions: [],
    scrmSummary: EMPTY_SCRM_SUMMARY,
    saveFloatX: 0,
    saveFloatY: 260,
    saveFloatLastX: 0,
    saveFloatLastY: 260,
    saveFloatMovable: false,
    uploadingMedia: false,
    ocrRecognizing: false,
    saving: false
  },
  onLoad(options) {
    this.setData({
      noteId: options.id || "",
      template: TEMPLATE_META[options.template] || TEMPLATE_META.general
    });
    this.initFloatingSave();
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    this.loadGlobalCategories();
    this.loadTopics();
    this.loadNote();
  },
  async loadGlobalCategories() {
    const { user } = this.data;
    if (!user) return;
    try {
      const res = await api.fetchCategories(user.id);
      const globalCategories = res.data || [];
      this.setData({
        globalCategories,
        commonTagOptions: buildCommonTagOptions(globalCategories, this.data.form.visibilityConfig || {})
      });
    } catch (error) {
      this.setData({ globalCategories: [], commonTagOptions: [] });
    }
  },
  async loadTopics() {
    const { user } = this.data;
    if (!user) return;
    try {
      const res = await api.fetchTopics(user.id);
      const topics = res.data || [];
      this.setData({
        topics,
        suggestedTopicOptions: buildSuggestedTopicOptions(
          (this.data.form.visibilityConfig || {}).cardType || "text_note",
          this.data.structuredData || {},
          this.data.form,
          topics,
          this.data.form.visibilityConfig || {}
        )
      });
    } catch (error) {
      this.setData({ topics: [] });
    }
  },
  async loadNote() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    try {
      const res = await api.fetchNote(noteId, user.id);
      const note = res.data || {};
      this.applyLoadedNote(note);
      this.loadNoteCustomerActions();
    } catch (error) {
      wx.showToast({ title: error.detail || "笔记加载失败", icon: "none" });
    }
  },
  async loadNoteCustomerActions() {
    const { user, noteId, isProperty, isGroupbuy, isServiceCard } = this.data;
    if (!user || !noteId || (!isProperty && !isGroupbuy && !isServiceCard)) {
      this.setData({ scrmSummary: EMPTY_SCRM_SUMMARY });
      return;
    }
    try {
      const res = await api.fetchNoteCustomerActions(noteId, user.id);
      const summary = (res.data && res.data.summary) || {};
      const latestText = summary.latestActionAt ? `最近 ${formatShortTime(summary.latestActionAt)}` : "暂无客户动作";
      this.setData({
        scrmSummary: {
          ...EMPTY_SCRM_SUMMARY,
          ...summary,
          latestText,
          hasUnread: hasUnreadCustomerAction(summary, user.id, noteId)
        }
      });
    } catch (error) {
      this.setData({ scrmSummary: EMPTY_SCRM_SUMMARY });
    }
  },
  applyLoadedNote(note) {
    const config = note.visibilityConfig || {};
    const cardType = config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note");
    const isBookmark = cardType === "link" && config.contentMode === "bookmark";
    const structuredData = { ...(config.structuredData || {}) };
    if ((cardType === "property_listing" || cardType === "groupbuy_product") && !structuredData.contact) {
      structuredData.contact = readLastContactPhone();
    }
    if (cardType === "property_listing") {
      structuredData.propertyStatus = normalizePropertyStatus(structuredData.propertyStatus);
      rememberPropertyCity([structuredData.address, structuredData.community, structuredData.businessArea, note.title, note.body].filter(Boolean).join(" "));
    }
    if (cardType === "groupbuy_product") {
      structuredData.skuConfig = normalizeSkuConfig(structuredData);
    }
    const isServiceCard = cardType === "business_card" || cardType === "service_offer";
    const cardState = normalizeCardState(config.cardState);
    const miniappInfo = buildMiniappInfo(structuredData);
    const conversionConfig = {
      ...defaultConversionConfig(cardType),
      ...defaultMiniappConversionConfig(structuredData),
      ...(config.conversionConfig || {})
    };
    const contextualTopics = filterContextualTopics(Array.isArray(config.topics) ? config.topics : [], cardType);
    const effectiveConfig = applySystemTagsToConfig({
      ...config,
      tags: filterContextualLabels(Array.isArray(config.tags) ? config.tags : [], Array.isArray(config.userTags) ? config.userTags : [], cardType),
      topics: contextualTopics,
      topicIds: cardType === "property_listing" ? config.topicIds : contextualTopics.map((topic) => topic.id),
      structuredData,
      conversionConfig
    }, structuredData);
    const conversionOptions = hydrateConversionOptions(cardType, conversionConfig);
    const typedFields = cardType === "property_listing"
      ? PROPERTY_FIELDS
      : cardType === "groupbuy_product"
        ? GROUPBUY_FIELDS
        : cardType === "business_card"
          ? BUSINESS_CARD_FIELDS
          : cardType === "service_offer"
            ? SERVICE_OFFER_FIELDS
            : [];
    const enabledActionLabels = buildEnabledLabels(conversionOptions);
    const form = {
      title: note.title || "",
      summary: note.summary || "",
      body: note.body || "",
      coverUrl: note.coverUrl || "",
      phone: note.phone || "",
      locationText: note.locationText || "",
      categoryIds: note.categoryIds || [],
      media: note.media || [],
      visibilityConfig: effectiveConfig
    };
    const mediaItems = buildMediaItems(form);
    const ocrInfo = buildOcrInfo(effectiveConfig, structuredData);
    const suggestionButtons = buildSuggestionButtons(effectiveConfig.typeSuggestions);
    const isPlainNote = cardType === "text_note" && !isBookmark && !miniappInfo.visible && !ocrInfo.visible && !suggestionButtons.length;
    const showOperationalControls = !isPlainNote || this.data.plainNoteOpsOpen;
    this.setData({
      form,
      isBookmark,
      isProperty: cardType === "property_listing",
      isGroupbuy: cardType === "groupbuy_product",
      isBusinessCard: cardType === "business_card",
      isServiceOffer: cardType === "service_offer",
      isServiceCard,
      isPlainNote,
      showOperationalControls,
      abilityPluginOpen: false,
      cardState,
      workflowSteps: buildWorkflowSteps(cardState),
      stateTitle: getStateTitle(cardType, cardState),
      stateHint: getStateHint(cardType, cardState),
      rawPreviewLines: buildRawPreviewLines(note, structuredData),
      keyChips: buildKeyChips(cardType, structuredData, effectiveConfig),
      reviewRows: buildReviewRows(typedFields, structuredData),
      missingWarnings: buildMissingWarnings(cardType, structuredData),
      organizeSummary: (structuredData.organizeResult && structuredData.organizeResult.summary) || note.summary || "",
      generationOptions: buildGenerationOptions(cardType, structuredData),
      enabledActionLabels,
      generatedActions: buildGeneratedActions(structuredData, enabledActionLabels),
      cardTypeLabel: CARD_TYPES[cardType] || "资料卡",
      structuredData,
      skuConfig: structuredData.skuConfig || normalizeSkuConfig(structuredData),
      miniappInfo,
      ocrInfo,
      conversionConfig,
      conversionOptions,
      customerFeatureLabels: buildEnabledCustomerFeatures(conversionOptions),
      featurePresets: hydrateFeaturePresets(conversionConfig),
      suggestionButtons,
      recognitionExplanation: effectiveConfig.recognitionExplanation || {},
      hiddenSections: hiddenSectionMap(effectiveConfig),
      uploadDateText: formatUploadDate(note.createdAt),
      noteCreatedAt: note.createdAt || "",
      displayTitle: buildDisplayTitle(cardType, form, structuredData),
      displaySubtitle: buildDisplaySubtitle(cardType, form, structuredData),
      displayTemplateName: effectiveConfig.displayTemplateName || "",
      propertyCustomerPreview: cardType === "property_listing" ? buildPropertyCustomerPreview(form, structuredData, conversionConfig) : buildPropertyCustomerPreview(),
      propertyPublishChecks: cardType === "property_listing" ? buildPropertyPublishChecks(form, structuredData, conversionConfig) : [],
      productCustomerPreview: cardType === "groupbuy_product" ? buildProductCustomerPreview(form, structuredData, conversionConfig) : buildProductCustomerPreview(),
      productPublishChecks: cardType === "groupbuy_product" ? buildProductPublishChecks(form, structuredData, conversionConfig) : [],
      showGroupbuyEdit: cardType === "groupbuy_product" && this.data.activePropertyDetailTab === "edit",
      showTagTopicPanel: showOperationalControls && (cardType === "property_listing" || cardType === "groupbuy_product" ? this.data.activePropertyDetailTab === "edit" : true),
      businessCardTemplates: buildBusinessCardTemplateOptions(effectiveConfig.displayTemplate || ""),
      businessCardHero: cardType === "business_card" ? buildBusinessCardHero(form, structuredData, effectiveConfig.displayTemplateName || "") : null,
      businessCardImages: buildBusinessCardImageState(form, structuredData),
      mediaCountText: mediaItems.length ? `共 ${mediaItems.length} 个素材，可隐藏但不会删除。` : "暂无素材，可稍后补充。",
      mediaItems,
      propertyStatusOptions: buildPropertyStatusOptions(structuredData.propertyStatus),
      mapPreview: buildMapPreview(structuredData),
      propertyFields: hydrateFields(PROPERTY_FIELDS, structuredData),
      groupbuyFields: hydrateFields(GROUPBUY_FIELDS, structuredData),
      productInfoFields: hydrateFields(PRODUCT_INFO_FIELDS, structuredData),
      productFulfillmentFields: hydrateFields(PRODUCT_FULFILLMENT_FIELDS, structuredData),
      businessCardFields: hydrateFields(BUSINESS_CARD_FIELDS, structuredData),
      serviceOfferFields: hydrateFields(SERVICE_OFFER_FIELDS, structuredData),
      suggestedTagOptions: buildSuggestedTagOptions(cardType, structuredData, form, effectiveConfig),
      commonTagOptions: buildCommonTagOptions(this.data.globalCategories, effectiveConfig),
      suggestedTopicOptions: buildSuggestedTopicOptions(cardType, structuredData, form, this.data.topics, effectiveConfig),
      bookmark: buildBookmark({ ...note, visibilityConfig: effectiveConfig })
    }, () => {
      this.autoResolveMapLocation({ silent: true });
      this.prepareBusinessCardShareImage();
      this.preparePropertyShareImage();
    });
  },
  async prepareBusinessCardShareImage() {
    const hero = this.data.businessCardHero || null;
    if (!this.data.isBusinessCard || !hero) {
      this.setData({ businessCardShareImage: "" });
      return;
    }
    try {
      const imagePath = await generateBusinessCardShareImage(this, BUSINESS_CARD_SHARE_CANVAS_ID, hero);
      this.setData({ businessCardShareImage: imagePath || "" });
    } catch (error) {
      this.setData({ businessCardShareImage: "" });
    }
  },
  async preparePropertyShareImage() {
    if (!this.data.isProperty) {
      this.setData({ propertyShareImage: "" });
      return;
    }
    try {
      const form = this.data.form || {};
      const data = this.data.structuredData || {};
      const imagePath = await generatePropertyShareImage(this, BUSINESS_CARD_SHARE_CANVAS_ID, {
        title: form.title || data.community || "房源资料",
        price: data.price || "",
        layout: data.layout || "",
        area: data.area || "",
        address: data.address || data.businessArea || "",
        coverUrl: form.coverUrl || ""
      });
      this.setData({ propertyShareImage: imagePath || "" });
    } catch (error) {
      this.setData({ propertyShareImage: "" });
    }
  },
  async handleRecognizeOcr() {
    const { user, noteId, ocrRecognizing } = this.data;
    if (!user || !noteId || ocrRecognizing) return;
    this.setData({ ocrRecognizing: true });
    wx.showLoading({ title: "识别中" });
    try {
      const res = await api.recognizeNoteImage(noteId, user.id);
      const payload = res.data || {};
      const note = payload.note || {};
      const ocr = payload.ocr || {};
      this.applyLoadedNote(note);
      this.loadNoteCustomerActions();
      wx.hideLoading();
      if (ocr.text) {
        wx.showToast({ title: "已识别", icon: "success" });
      } else if (ocr.configured) {
        wx.showToast({ title: "未识别到文字", icon: "none" });
      } else {
        wx.showToast({ title: "图片已保存，可手动补", icon: "none" });
      }
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.detail || error.errMsg || "识别失败", icon: "none" });
    } finally {
      this.setData({ ocrRecognizing: false });
    }
  },
  async handleStartEdit() {
    const config = { ...(this.data.form.visibilityConfig || {}), cardState: "editing" };
    this.setData({ "form.visibilityConfig": config });
    this.applyLoadedNote({
      ...this.data.form,
      id: this.data.noteId,
      visibilityConfig: config,
      title: this.data.form.title,
      summary: this.data.form.summary,
      body: this.data.form.body,
      createdAt: this.data.bookmark.collectedAtText
    });
    try {
      await this.handleSaveOnly();
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "保存状态失败", icon: "none" });
    }
  },
  handleBackToEdit() {
    const config = { ...(this.data.form.visibilityConfig || {}), cardState: "editing" };
    this.setData({ "form.visibilityConfig": config });
    this.applyLoadedNote({
      ...this.data.form,
      id: this.data.noteId,
      visibilityConfig: config,
      title: this.data.form.title,
      summary: this.data.form.summary,
      body: this.data.form.body
    });
  },
  handleInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.detail.value;
    const form = { ...this.data.form, [key]: value };
    const config = form.visibilityConfig || {};
    const cardType = config.cardType || "text_note";
    const structuredData = this.data.structuredData || {};
    this.setData({
      form,
      [`form.${key}`]: value,
      productCustomerPreview: cardType === "groupbuy_product" ? buildProductCustomerPreview(form, structuredData, this.data.conversionConfig || {}) : this.data.productCustomerPreview,
      productPublishChecks: cardType === "groupbuy_product" ? buildProductPublishChecks(form, structuredData, this.data.conversionConfig || {}) : this.data.productPublishChecks
    });
  },
  handleOpenPlainNoteOps() {
    this.setData({
      abilityPluginOpen: true
    });
  },
  handleEnablePlainNoteOrganize() {
    this.setData({
      plainNoteOpsOpen: true,
      abilityPluginOpen: false,
      showOperationalControls: true,
      showTagTopicPanel: true
    });
  },
  handleClosePlainNoteOps() {
    this.setData({
      plainNoteOpsOpen: false,
      abilityPluginOpen: false,
      showOperationalControls: false,
      showTagTopicPanel: false
    });
  },
  async handleAddToShowcase() {
    const { noteId } = this.data;
    if (!noteId) return;
    try {
      await this.handleSaveOnly();
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "保存失败", icon: "none" });
      return;
    }
    wx.navigateTo({ url: `/pages/showcase-edit/index?mode=notes&noteId=${encodeURIComponent(noteId)}` });
  },
  handleBookmarkField(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.currentTarget.dataset.value || event.detail.value;
    const config = { ...(this.data.form.visibilityConfig || {}), [key]: value };
    this.setData({
      "form.visibilityConfig": config,
      [`bookmark.${key}`]: value
    });
  },
  handleStructuredInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.detail.value;
    const currentStructuredData = this.data.structuredData || {};
    const structuredData = { ...currentStructuredData, [key]: value };
    if (shouldDropMapLocation(currentStructuredData, key, value)) {
      delete structuredData.mapLocation;
    }
    const config = { ...(this.data.form.visibilityConfig || {}), structuredData, cardState: "editing" };
    const cardType = config.cardType || "text_note";
    this.setData({
      structuredData,
      propertyFields: hydrateFields(PROPERTY_FIELDS, structuredData),
      groupbuyFields: hydrateFields(GROUPBUY_FIELDS, structuredData),
      productInfoFields: hydrateFields(PRODUCT_INFO_FIELDS, structuredData),
      productFulfillmentFields: hydrateFields(PRODUCT_FULFILLMENT_FIELDS, structuredData),
      businessCardFields: hydrateFields(BUSINESS_CARD_FIELDS, structuredData),
      serviceOfferFields: hydrateFields(SERVICE_OFFER_FIELDS, structuredData),
      businessCardImages: buildBusinessCardImageState(this.data.form, structuredData),
      displayTitle: buildDisplayTitle(cardType, this.data.form, structuredData),
      displaySubtitle: buildDisplaySubtitle(cardType, this.data.form, structuredData),
      propertyCustomerPreview: cardType === "property_listing" ? buildPropertyCustomerPreview(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.propertyCustomerPreview,
      propertyPublishChecks: cardType === "property_listing" ? buildPropertyPublishChecks(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.propertyPublishChecks,
      productCustomerPreview: cardType === "groupbuy_product" ? buildProductCustomerPreview(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.productCustomerPreview,
      productPublishChecks: cardType === "groupbuy_product" ? buildProductPublishChecks(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.productPublishChecks,
      businessCardHero: cardType === "business_card" ? buildBusinessCardHero(this.data.form, structuredData, (config || {}).displayTemplateName || "") : this.data.businessCardHero,
      suggestedTagOptions: buildSuggestedTagOptions(cardType, structuredData, this.data.form, config),
      suggestedTopicOptions: buildSuggestedTopicOptions(cardType, structuredData, this.data.form, this.data.topics, config),
      mapPreview: buildMapPreview(structuredData),
      "form.visibilityConfig": config
    });
  },
  async handleSwitchBusinessCardTemplate(event) {
    const templateId = event.currentTarget.dataset.id;
    const template = getSalesPageTemplates("business_card").find((item) => item.id === templateId);
    if (!template || !this.data.isBusinessCard) return;
    const currentConfig = { ...(this.data.form.visibilityConfig || {}) };
    if (currentConfig.displayTemplate === template.id) return;
    const structuredData = this.data.structuredData || {};
    const config = {
      ...currentConfig,
      displayTemplate: template.id,
      displayTemplateName: template.name,
      displayTemplateScene: template.scene,
      displayTemplateTone: template.tone,
      structuredData,
      cardState: "editing"
    };
    const form = { ...this.data.form, visibilityConfig: config };
    this.setData({
      form,
      displayTemplateName: template.name,
      businessCardTemplates: buildBusinessCardTemplateOptions(template.id),
      businessCardHero: buildBusinessCardHero(form, structuredData, template.name),
      "form.visibilityConfig": config,
      saving: true
    });
    try {
      await this.handleSaveOnly();
      this.prepareBusinessCardShareImage();
      wx.showToast({ title: "名片风格已切换", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "风格保存失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  handleQuickFieldOption(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.currentTarget.dataset.value;
    if (!key || value === undefined) return;
    const structuredData = { ...(this.data.structuredData || {}), [key]: value };
    const config = { ...(this.data.form.visibilityConfig || {}), structuredData, cardState: "editing" };
    const cardType = config.cardType || "text_note";
    this.setData({
      structuredData,
      propertyFields: hydrateFields(PROPERTY_FIELDS, structuredData),
      groupbuyFields: hydrateFields(GROUPBUY_FIELDS, structuredData),
      productInfoFields: hydrateFields(PRODUCT_INFO_FIELDS, structuredData),
      productFulfillmentFields: hydrateFields(PRODUCT_FULFILLMENT_FIELDS, structuredData),
      businessCardFields: hydrateFields(BUSINESS_CARD_FIELDS, structuredData),
      serviceOfferFields: hydrateFields(SERVICE_OFFER_FIELDS, structuredData),
      businessCardImages: buildBusinessCardImageState(this.data.form, structuredData),
      displayTitle: buildDisplayTitle(cardType, this.data.form, structuredData),
      displaySubtitle: buildDisplaySubtitle(cardType, this.data.form, structuredData),
      propertyCustomerPreview: cardType === "property_listing" ? buildPropertyCustomerPreview(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.propertyCustomerPreview,
      propertyPublishChecks: cardType === "property_listing" ? buildPropertyPublishChecks(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.propertyPublishChecks,
      productCustomerPreview: cardType === "groupbuy_product" ? buildProductCustomerPreview(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.productCustomerPreview,
      productPublishChecks: cardType === "groupbuy_product" ? buildProductPublishChecks(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.productPublishChecks,
      businessCardHero: cardType === "business_card" ? buildBusinessCardHero(this.data.form, structuredData, (config || {}).displayTemplateName || "") : this.data.businessCardHero,
      suggestedTagOptions: buildSuggestedTagOptions(cardType, structuredData, this.data.form, config),
      suggestedTopicOptions: buildSuggestedTopicOptions(cardType, structuredData, this.data.form, this.data.topics, config),
      mapPreview: buildMapPreview(structuredData),
      "form.visibilityConfig": config
    });
  },
  applySkuConfig(skuConfig) {
    const structuredData = {
      ...(this.data.structuredData || {}),
      skuConfig: normalizeSkuConfig({ ...(this.data.structuredData || {}), skuConfig })
    };
    const config = { ...(this.data.form.visibilityConfig || {}), structuredData, cardState: "editing" };
    this.setData({
      structuredData,
      skuConfig: structuredData.skuConfig,
      displaySubtitle: buildDisplaySubtitle(config.cardType || "groupbuy_product", this.data.form, structuredData),
      productCustomerPreview: config.cardType === "groupbuy_product" ? buildProductCustomerPreview(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.productCustomerPreview,
      productPublishChecks: config.cardType === "groupbuy_product" ? buildProductPublishChecks(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.productPublishChecks,
      "form.visibilityConfig": config
    });
  },
  handleAddSkuGroup() {
    const skuConfig = normalizeSkuConfig(this.data.structuredData || {});
    skuConfig.attributeGroups.push({
      id: makeLocalId("group"),
      name: "",
      options: [
        { id: makeLocalId("option"), label: "" },
        { id: makeLocalId("option"), label: "" }
      ]
    });
    this.applySkuConfig(skuConfig);
  },
  handleSkuGroupName(event) {
    const index = Number(event.currentTarget.dataset.index);
    const skuConfig = normalizeSkuConfig(this.data.structuredData || {});
    if (!skuConfig.attributeGroups[index]) return;
    skuConfig.attributeGroups[index].name = event.detail.value;
    this.applySkuConfig(skuConfig);
  },
  handleDeleteSkuGroup(event) {
    const index = Number(event.currentTarget.dataset.index);
    const skuConfig = normalizeSkuConfig(this.data.structuredData || {});
    skuConfig.attributeGroups.splice(index, 1);
    this.applySkuConfig(skuConfig);
  },
  handleAddSkuOption(event) {
    const groupIndex = Number(event.currentTarget.dataset.groupIndex);
    const skuConfig = normalizeSkuConfig(this.data.structuredData || {});
    const group = skuConfig.attributeGroups[groupIndex];
    if (!group) return;
    group.options.push({ id: makeLocalId("option"), label: "" });
    this.applySkuConfig(skuConfig);
  },
  handleSkuOptionLabel(event) {
    const groupIndex = Number(event.currentTarget.dataset.groupIndex);
    const optionIndex = Number(event.currentTarget.dataset.optionIndex);
    const skuConfig = normalizeSkuConfig(this.data.structuredData || {});
    const option = skuConfig.attributeGroups[groupIndex] && skuConfig.attributeGroups[groupIndex].options[optionIndex];
    if (!option) return;
    option.label = event.detail.value;
    this.applySkuConfig(skuConfig);
  },
  handleDeleteSkuOption(event) {
    const groupIndex = Number(event.currentTarget.dataset.groupIndex);
    const optionIndex = Number(event.currentTarget.dataset.optionIndex);
    const skuConfig = normalizeSkuConfig(this.data.structuredData || {});
    const group = skuConfig.attributeGroups[groupIndex];
    if (!group) return;
    group.options.splice(optionIndex, 1);
    if (!group.options.length) {
      skuConfig.attributeGroups.splice(groupIndex, 1);
    }
    this.applySkuConfig(skuConfig);
  },
  handleSkuFieldInput(event) {
    const index = Number(event.currentTarget.dataset.index);
    const key = event.currentTarget.dataset.key;
    const skuConfig = normalizeSkuConfig(this.data.structuredData || {});
    if (!skuConfig.skus[index] || !key) return;
    skuConfig.skus[index][key] = event.detail.value;
    this.applySkuConfig(skuConfig);
  },
  handleSkuSoldOut(event) {
    const index = Number(event.currentTarget.dataset.index);
    const skuConfig = normalizeSkuConfig(this.data.structuredData || {});
    if (!skuConfig.skus[index]) return;
    skuConfig.skus[index].soldOut = Boolean(event.detail.value);
    this.applySkuConfig(skuConfig);
  },
  handleChooseLocation() {
    const defaultAddress = buildMapAddress(this.data.structuredData || {});
    wx.chooseLocation({
      success: (res) => {
        const fallbackAddress = defaultAddress || this.data.structuredData.address || this.data.structuredData.community || this.data.structuredData.businessArea || "";
        const structuredData = {
          ...(this.data.structuredData || {}),
          address: res.address || res.name || fallbackAddress,
          mapLocation: {
            name: res.name || this.data.structuredData.community || "房源位置",
            address: res.address || fallbackAddress,
            latitude: res.latitude,
            longitude: res.longitude
          }
        };
        rememberPropertyCity(`${structuredData.address} ${structuredData.community || ""} ${structuredData.businessArea || ""}`);
        const config = { ...(this.data.form.visibilityConfig || {}), structuredData, cardState: "editing" };
        const cardType = config.cardType || "text_note";
        this.setData({
          saving: true,
          structuredData,
          propertyFields: hydrateFields(PROPERTY_FIELDS, structuredData),
          displaySubtitle: buildDisplaySubtitle(cardType, this.data.form, structuredData),
          propertyCustomerPreview: cardType === "property_listing" ? buildPropertyCustomerPreview(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.propertyCustomerPreview,
          propertyPublishChecks: cardType === "property_listing" ? buildPropertyPublishChecks(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.propertyPublishChecks,
          suggestedTagOptions: buildSuggestedTagOptions(cardType, structuredData, this.data.form, config),
          suggestedTopicOptions: buildSuggestedTopicOptions(cardType, structuredData, this.data.form, this.data.topics, config),
          mapPreview: buildMapPreview(structuredData),
          "form.visibilityConfig": config
        }, async () => {
          try {
            await this.handleSaveOnly();
            wx.showToast({ title: "定位已保存", icon: "success" });
          } catch (error) {
            wx.showToast({ title: error.detail || error.message || "定位保存失败", icon: "none" });
          } finally {
            this.setData({ saving: false });
          }
        });
      },
      fail: (error) => {
        const message = (error && error.errMsg) || "";
        if (message.includes("cancel")) {
          wx.showToast({ title: "未选择位置", icon: "none" });
          return;
        }
        wx.showModal({
          title: "地图选点未打开",
          content: "请确认小程序已开启位置权限。选点时搜小区名称即可，不需要精确到门牌号。",
          showCancel: false,
          confirmColor: "#11924d"
        });
      }
    });
  },
  async handleResolveDefaultMap() {
    if (this.data.geocodingAddress) return;
    const address = buildMapAddress(this.data.structuredData || {});
    if (!address) {
      wx.showToast({ title: "请先填写地址", icon: "none" });
      return;
    }
    const resolved = await this.autoResolveMapLocation({ silent: false });
    if (!resolved && !(this.data.mapPreview || {}).hasPoint) {
      wx.showToast({ title: "未匹配到位置，可手动选择", icon: "none" });
    }
  },
  async autoResolveMapLocation({ silent = false } = {}) {
    const structuredData = this.data.structuredData || {};
    const currentPreview = buildMapPreview(structuredData);
    const address = buildMapAddress(structuredData);
    if (!this.data.isProperty || !address || this.data.geocodingAddress) return false;
    if (currentPreview.hasPoint) return true;
    const addressCandidates = buildMapAddressCandidates(structuredData);

    this.setData({ geocodingAddress: true });
    try {
      let location = null;
      const region = inferMapRegion(structuredData);
      const regions = region ? [region, ""] : [""];
      for (let regionIndex = 0; regionIndex < regions.length; regionIndex += 1) {
        for (let index = 0; index < addressCandidates.length; index += 1) {
          const candidate = addressCandidates[index];
          const res = await api.geocodeAddress({
            address: candidate,
            region: regions[regionIndex]
          });
          const data = (res && res.data) || {};
          if (data.found && data.latitude && data.longitude) {
            location = data;
            break;
          }
        }
        if (location) break;
      }
      if (!location) {
        if (!silent) wx.showToast({ title: "默认地址暂未匹配到地图", icon: "none" });
        return false;
      }
      const nextStructuredData = {
        ...this.data.structuredData,
        address: this.data.structuredData.address || location.address || address,
        mapLocation: {
          name: location.name || this.data.structuredData.community || "房源位置",
          address: location.address || address,
          latitude: location.latitude,
          longitude: location.longitude
        }
      };
      rememberPropertyCity(`${nextStructuredData.address} ${nextStructuredData.community || ""} ${nextStructuredData.businessArea || ""}`);
      const config = {
        ...(this.data.form.visibilityConfig || {}),
        structuredData: nextStructuredData,
        cardState: "editing"
      };
      const cardType = config.cardType || "text_note";
      this.setData({
        structuredData: nextStructuredData,
        propertyFields: hydrateFields(PROPERTY_FIELDS, nextStructuredData),
        displaySubtitle: buildDisplaySubtitle(cardType, this.data.form, nextStructuredData),
        propertyCustomerPreview: cardType === "property_listing" ? buildPropertyCustomerPreview(this.data.form, nextStructuredData, this.data.conversionConfig || {}) : this.data.propertyCustomerPreview,
        propertyPublishChecks: cardType === "property_listing" ? buildPropertyPublishChecks(this.data.form, nextStructuredData, this.data.conversionConfig || {}) : this.data.propertyPublishChecks,
        suggestedTagOptions: buildSuggestedTagOptions(cardType, nextStructuredData, this.data.form, config),
        suggestedTopicOptions: buildSuggestedTopicOptions(cardType, nextStructuredData, this.data.form, this.data.topics, config),
        mapPreview: buildMapPreview(nextStructuredData),
        "form.visibilityConfig": config
      }, async () => {
        try {
          await this.handleSaveOnly();
        } catch (error) {
          if (!silent) wx.showToast({ title: error.detail || error.message || "地图位置保存失败", icon: "none" });
        }
      });
      return true;
    } catch (error) {
      if (!silent) wx.showToast({ title: error.detail || error.message || "默认地址暂未匹配到地图", icon: "none" });
      return false;
    } finally {
      this.setData({ geocodingAddress: false });
    }
  },
  handleConversionToggle(event) {
    const key = event.currentTarget.dataset.key;
    const conversionConfig = { ...(this.data.conversionConfig || {}), [key]: Boolean(event.detail.value) };
    const config = {
      ...(this.data.form.visibilityConfig || {}),
      conversionConfig,
      cardState: "editing"
    };
    this.setData({
      conversionConfig,
      conversionOptions: hydrateConversionOptions(config.cardType, conversionConfig),
      customerFeatureLabels: buildEnabledCustomerFeatures(hydrateConversionOptions(config.cardType, conversionConfig)),
      propertyCustomerPreview: config.cardType === "property_listing" ? buildPropertyCustomerPreview(this.data.form, this.data.structuredData || {}, conversionConfig) : this.data.propertyCustomerPreview,
      propertyPublishChecks: config.cardType === "property_listing" ? buildPropertyPublishChecks(this.data.form, this.data.structuredData || {}, conversionConfig) : this.data.propertyPublishChecks,
      productCustomerPreview: config.cardType === "groupbuy_product" ? buildProductCustomerPreview(this.data.form, this.data.structuredData || {}, conversionConfig) : this.data.productCustomerPreview,
      productPublishChecks: config.cardType === "groupbuy_product" ? buildProductPublishChecks(this.data.form, this.data.structuredData || {}, conversionConfig) : this.data.productPublishChecks,
      featurePresets: hydrateFeaturePresets(conversionConfig),
      "form.visibilityConfig": config
    });
  },
  handleToggleFeatureSettings() {
    this.setData({ featureSettingsOpen: !this.data.featureSettingsOpen });
  },
  handleToggleTagTopic() {
    this.setData({ tagTopicOpen: !this.data.tagTopicOpen });
  },
  handlePropertyDetailTab(event) {
    const activePropertyDetailTab = event.currentTarget.dataset.tab || "operate";
    const isScopedWorkbench = this.data.isProperty || this.data.isGroupbuy;
    this.setData({
      activePropertyDetailTab,
      showGroupbuyEdit: this.data.isGroupbuy && activePropertyDetailTab === "edit",
      showTagTopicPanel: this.data.showOperationalControls && (isScopedWorkbench ? activePropertyDetailTab === "edit" : true)
    });
  },
  handleToggleSection(event) {
    const section = event.currentTarget.dataset.section;
    if (!section) return;
    const config = { ...(this.data.form.visibilityConfig || {}) };
    const sections = new Set(Array.isArray(config.hiddenSections) ? config.hiddenSections : []);
    if (sections.has(section)) {
      sections.delete(section);
    } else {
      sections.add(section);
    }
    config.hiddenSections = Array.from(sections);
    this.setData({
      "form.visibilityConfig": config,
      hiddenSections: hiddenSectionMap(config)
    });
  },
  handleAddFeatureGroup(event) {
    const key = event.currentTarget.dataset.key;
    if (!key) return;
    const conversionConfig = { ...(this.data.conversionConfig || {}) };
    conversionConfig[key] = !conversionConfig[key];
    const config = {
      ...(this.data.form.visibilityConfig || {}),
      conversionConfig
    };
    this.setData({
      conversionConfig,
      featurePresets: hydrateFeaturePresets(conversionConfig),
      productCustomerPreview: config.cardType === "groupbuy_product" ? buildProductCustomerPreview(this.data.form, this.data.structuredData || {}, conversionConfig) : this.data.productCustomerPreview,
      productPublishChecks: config.cardType === "groupbuy_product" ? buildProductPublishChecks(this.data.form, this.data.structuredData || {}, conversionConfig) : this.data.productPublishChecks,
      "form.visibilityConfig": config
    });
  },
  async handleConvertType(event) {
    const cardType = event.currentTarget.dataset.type || "text_note";
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    this.setData({ saving: true });
    try {
      const res = await api.confirmNoteType(noteId, {
        ownerUserId: user.id,
        cardType
      });
      this.applyLoadedNote(res.data || {});
      wx.showToast({ title: "已切换", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "切换失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  handleCopyShareText() {
    const text = buildShareText(this.data.form.visibilityConfig.cardType, this.data.form, this.data.structuredData || {});
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: "文案已复制", icon: "success" }),
      fail: () => wx.showToast({ title: "复制失败", icon: "none" })
    });
  },
  handleCopyCustomerTalk() {
    const text = buildCustomerTalkText(this.data.form.visibilityConfig.cardType, this.data.form, this.data.structuredData || {});
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: "客户话术已复制", icon: "success" }),
      fail: () => wx.showToast({ title: "复制失败", icon: "none" })
    });
  },
  handleOpenMiniapp() {
    const miniapp = this.data.miniappInfo || {};
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
    const miniapp = this.data.miniappInfo || {};
    const text = [
      miniapp.title,
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
  handlePosterEntry() {
    wx.navigateTo({ url: `/pages/note-poster/index?id=${this.data.noteId}` });
  },
  handlePreviewPage() {
    wx.navigateTo({ url: `/pages/note-preview/index?id=${this.data.noteId}` });
  },
  handleOpenCustomerActions() {
    if (!this.data.noteId) return;
    const { user, noteId, scrmSummary } = this.data;
    wx.setStorageSync(scrmReadKey(user && user.id, noteId), Date.now());
    this.setData({
      scrmSummary: {
        ...scrmSummary,
        hasUnread: false
      }
    });
    wx.navigateTo({ url: `/pages/note-actions/index?id=${this.data.noteId}` });
  },
  handleOpenBusinessCardStudio() {
    if (!this.data.noteId) return;
    wx.navigateTo({ url: `/pages/business-card-studio/index?id=${this.data.noteId}` });
  },
  handleOpenServiceOfferStudio() {
    if (!this.data.noteId) return;
    wx.navigateTo({ url: `/pages/service-offer-studio/index?id=${this.data.noteId}` });
  },
  handleOpenMessages() {
    messagePlugin.openMessageCenter();
  },
  async handleSetCover(event) {
    const url = event.currentTarget.dataset.url;
    if (!url) return;
    const form = { ...this.data.form, coverUrl: url };
    await this.persistMediaState(form, "封面已设置");
  },
  async handleSetBusinessCardImage(event) {
    const url = event.currentTarget.dataset.url;
    const field = event.currentTarget.dataset.field;
    if (!url || !["avatarUrl", "qrCodeUrl"].includes(field)) return;
    const structuredData = { ...(this.data.structuredData || {}), [field]: url };
    const form = {
      ...this.data.form,
      coverUrl: field === "avatarUrl" ? url : this.data.form.coverUrl,
      visibilityConfig: {
        ...(this.data.form.visibilityConfig || {}),
        structuredData,
        cardState: "editing"
      }
    };
    this.applyMediaState(form);
    try {
      await this.handleSaveOnly();
      wx.showToast({ title: field === "avatarUrl" ? "头像已设置" : "二维码已设置", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "保存失败", icon: "none" });
    }
  },
  async handleDeleteMedia(event) {
    const source = event.currentTarget.dataset.source;
    const index = Number(event.currentTarget.dataset.index);
    const form = { ...this.data.form, media: [...(this.data.form.media || [])] };
    if (source === "cover") {
      form.coverUrl = "";
    } else if (Number.isInteger(index) && index >= 0) {
      const removed = form.media[index];
      form.media.splice(index, 1);
      if (removed && removed.url === form.coverUrl) {
        form.coverUrl = (form.media.find((item) => item.type === "image") || {}).url || "";
      }
    }
    await this.persistMediaState(form, "已删除素材");
  },
  async handleMoveMedia(event) {
    const index = Number(event.currentTarget.dataset.index);
    const direction = event.currentTarget.dataset.direction;
    const media = [...(this.data.form.media || [])];
    const target = direction === "up" ? index - 1 : index + 1;
    if (!Number.isInteger(index) || index < 0 || target < 0 || target >= media.length) return;
    const form = { ...this.data.form, media };
    [form.media[index], form.media[target]] = [form.media[target], form.media[index]];
    form.media = form.media.map((item, itemIndex) => ({
      ...item,
      sortOrder: itemIndex + 1
    }));
    await this.persistMediaState(form, "顺序已保存");
  },
  async handleSetPropertyStatus(event) {
    const status = normalizePropertyStatus(event.currentTarget.dataset.status);
    const structuredData = { ...(this.data.structuredData || {}), propertyStatus: status };
    const config = { ...(this.data.form.visibilityConfig || {}), structuredData, cardState: "editing" };
    const cardType = config.cardType || "text_note";
    this.setData({
      structuredData,
      propertyStatusOptions: buildPropertyStatusOptions(status),
      propertyFields: hydrateFields(PROPERTY_FIELDS, structuredData),
      displaySubtitle: buildDisplaySubtitle(cardType, this.data.form, structuredData),
      propertyCustomerPreview: cardType === "property_listing" ? buildPropertyCustomerPreview(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.propertyCustomerPreview,
      propertyPublishChecks: cardType === "property_listing" ? buildPropertyPublishChecks(this.data.form, structuredData, this.data.conversionConfig || {}) : this.data.propertyPublishChecks,
      "form.visibilityConfig": config,
      saving: true
    });
    try {
      await this.handleSaveOnly();
      wx.showToast({ title: "状态已保存", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "状态保存失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  handlePreviewMedia(event) {
    const url = event.currentTarget.dataset.url;
    if (!url) return;
    const urls = buildImageUrls(this.data.form);
    wx.previewImage({ current: url, urls });
  },
  handleChooseMediaUpload() {
    if (this.data.uploadingMedia) return;
    wx.showActionSheet({
      itemList: ["添加图片", "添加视频"],
      success: ({ tapIndex }) => {
        if (tapIndex === 0) {
          this.chooseNoteImages();
          return;
        }
        this.chooseNoteVideo();
      }
    });
  },
  chooseNoteImages() {
    wx.chooseMedia({
      count: 9,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      success: ({ tempFiles = [] }) => {
        const paths = tempFiles.map((file) => file.tempFilePath).filter(Boolean);
        this.uploadNoteMedia(paths, "image");
      }
    });
  },
  chooseNoteVideo() {
    wx.chooseMedia({
      count: 1,
      mediaType: ["video"],
      sourceType: ["album", "camera"],
      success: ({ tempFiles = [] }) => {
        const file = tempFiles[0];
        if (!file || !file.tempFilePath) return;
        this.uploadNoteMedia([file.tempFilePath], "video");
      }
    });
  },
  async uploadNoteMedia(paths, type) {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if (!paths.length || this.data.uploadingMedia) return;
    this.setData({ uploadingMedia: true });
    try {
      const uploaded = await Promise.all(
        paths.map((path) =>
          api.uploadAsset({
            filePath: path,
            mediaType: type,
            ownerUserId: currentUser.id
          })
        )
      );
      const baseLength = (this.data.form.media || []).length;
      const nextItems = uploaded
        .filter((item) => item && item.url)
        .map((item, index) => ({
          type: item.mediaType || type,
          url: item.url,
          displayUrl: item.displayUrl || item.url,
          sortOrder: baseLength + index + 1
        }));
      if (!nextItems.length) {
        wx.showToast({ title: "没有可用素材", icon: "none" });
        return;
      }
      const firstImage = nextItems.find((item) => item.type === "image");
      const form = {
        ...this.data.form,
        coverUrl: this.data.form.coverUrl || (firstImage ? firstImage.url : ""),
        media: [...(this.data.form.media || []), ...nextItems]
      };
      this.applyMediaState(form);
      await this.handleSaveOnly();
      wx.showToast({ title: "已添加并保存", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || error.errMsg || "上传失败", icon: "none" });
    } finally {
      this.setData({ uploadingMedia: false });
    }
  },
  applyMediaState(form) {
    const incomingData = ((form.visibilityConfig || {}).structuredData) || this.data.structuredData || {};
    const structuredData = { ...incomingData, images: buildImageUrls(form) };
    const config = { ...(form.visibilityConfig || {}), structuredData, cardState: "editing" };
    form.visibilityConfig = config;
    const mediaItems = buildMediaItems(form);
    this.setData({
      form,
      structuredData,
      mediaItems,
      businessCardImages: buildBusinessCardImageState(form, structuredData),
      propertyCustomerPreview: config.cardType === "property_listing" ? buildPropertyCustomerPreview(form, structuredData, this.data.conversionConfig || {}) : this.data.propertyCustomerPreview,
      propertyPublishChecks: config.cardType === "property_listing" ? buildPropertyPublishChecks(form, structuredData, this.data.conversionConfig || {}) : this.data.propertyPublishChecks,
      productCustomerPreview: config.cardType === "groupbuy_product" ? buildProductCustomerPreview(form, structuredData, this.data.conversionConfig || {}) : this.data.productCustomerPreview,
      productPublishChecks: config.cardType === "groupbuy_product" ? buildProductPublishChecks(form, structuredData, this.data.conversionConfig || {}) : this.data.productPublishChecks,
      mediaCountText: mediaItems.length ? `共 ${mediaItems.length} 个素材，可隐藏但不会删除。` : "暂无素材，可稍后补充。",
      "form.visibilityConfig": config
    });
  },
  async persistMediaState(form, successTitle) {
    if (this.data.saving) return;
    this.applyMediaState(form);
    this.setData({ saving: true });
    try {
      await this.handleSaveOnly();
      wx.showToast({ title: successTitle, icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "保存失败", icon: "none" });
      this.loadNote();
    } finally {
      this.setData({ saving: false });
    }
  },
  handleTagDraft(event) {
    this.setData({ tagDraft: event.detail.value });
  },
  handleAddTag() {
    const tag = this.data.tagDraft.trim();
    if (!tag) return;
    const config = { ...(this.data.form.visibilityConfig || {}) };
    const userTags = Array.from(new Set([...(config.userTags || []), tag]));
    const tags = Array.from(new Set([...(config.tags || []), tag]));
    config.userTags = userTags;
    config.tags = tags;
    config.tagStatus = "user_updated";
    this.setData({
      "form.visibilityConfig": config,
      "bookmark.userTags": userTags,
      "bookmark.tags": tags,
      commonTagOptions: buildCommonTagOptions(this.data.globalCategories, config),
      suggestedTagOptions: buildSuggestedTagOptions(config.cardType || "text_note", this.data.structuredData || {}, this.data.form, config),
      tagDraft: ""
    });
  },
  handleSuggestedTag(event) {
    const tag = String(event.currentTarget.dataset.tag || "").trim();
    if (!tag) return;
    const config = { ...(this.data.form.visibilityConfig || {}) };
    const userTags = Array.from(new Set([...(config.userTags || []), tag]));
    const tags = Array.from(new Set([...(config.tags || []), tag]));
    config.userTags = userTags;
    config.tags = tags;
    config.tagStatus = "user_updated";
    this.setData({
      "form.visibilityConfig": config,
      "bookmark.userTags": userTags,
      "bookmark.tags": tags,
      commonTagOptions: buildCommonTagOptions(this.data.globalCategories, config),
      suggestedTagOptions: buildSuggestedTagOptions(config.cardType || "text_note", this.data.structuredData || {}, this.data.form, config)
    });
  },
  handleRemoveTag(event) {
    const tag = event.currentTarget.dataset.tag;
    const config = { ...(this.data.form.visibilityConfig || {}) };
    config.userTags = (config.userTags || []).filter((item) => item !== tag);
    config.tags = (config.tags || []).filter((item) => item !== tag);
    config.tagStatus = "user_updated";
    this.setData({
      "form.visibilityConfig": config,
      "bookmark.userTags": config.userTags,
      "bookmark.tags": config.tags,
      commonTagOptions: buildCommonTagOptions(this.data.globalCategories, config),
      suggestedTagOptions: buildSuggestedTagOptions(config.cardType || "text_note", this.data.structuredData || {}, this.data.form, config)
    });
  },
  handleTopicDraft(event) {
    this.setData({ topicDraft: event.detail.value });
  },
  async handleCreateTopic() {
    const name = this.data.topicDraft.trim();
    const { user } = this.data;
    if (!name || !user) return;
    try {
      const res = await api.createTopic({ ownerUserId: user.id, name });
      this.setData({ topicDraft: "" });
      await this.loadTopics();
      await this.handleAddTopicById(res.data.id);
    } catch (error) {
      wx.showToast({ title: error.detail || "专题创建失败", icon: "none" });
    }
  },
  async handleAddTopic(event) {
    await this.handleAddTopicById(event.currentTarget.dataset.id);
  },
  async handleAddTopicById(topicId) {
    const { user, noteId } = this.data;
    if (!topicId || !user || !noteId) return;
    try {
      const res = await api.addNoteToTopic(noteId, topicId, user.id);
      this.applyLoadedNote(res.data || {});
    } catch (error) {
      wx.showToast({ title: error.detail || "加入专题失败", icon: "none" });
    }
  },
  async handleSuggestedTopic(event) {
    const name = String(event.currentTarget.dataset.name || "").trim();
    const { user } = this.data;
    if (!name || !user) return;
    try {
      const existing = (this.data.topics || []).find((item) => item.name === name);
      const topicId = existing ? existing.id : (await api.createTopic({ ownerUserId: user.id, name })).data.id;
      await this.loadTopics();
      await this.handleAddTopicById(topicId);
    } catch (error) {
      wx.showToast({ title: error.detail || "加入专题失败", icon: "none" });
    }
  },
  async handleRemoveTopic(event) {
    const { user, noteId } = this.data;
    const topicId = event.currentTarget.dataset.id;
    if (!topicId || !user || !noteId) return;
    try {
      const res = await api.removeNoteFromTopic(noteId, topicId, user.id);
      this.applyLoadedNote(res.data || {});
    } catch (error) {
      wx.showToast({ title: error.detail || "移出专题失败", icon: "none" });
    }
  },
  async handleSave() {
    this.setData({ saving: true });
    try {
      await this.handleSaveOnly();
      wx.showToast({ title: "已保存", icon: "success" });
      setTimeout(() => wx.navigateBack(), 350);
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "保存失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  async handleOrganize() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    this.setData({ saving: true });
    try {
      await this.handleSaveOnly();
      const res = await api.organizeNote(noteId, user.id);
      const note = res.data || {};
      this.applyLoadedNote(note);
      wx.showToast({ title: "已整理", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "整理失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  async handleGenerate() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    this.setData({ saving: true });
    try {
      await this.handleSaveOnly();
      const res = await api.generateNote(noteId, user.id);
      this.applyLoadedNote(res.data || {});
      wx.showToast({ title: "已生成配置", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || error.message || "生成失败", icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },
  async handleSaveOnly() {
    const { user, noteId, form } = this.data;
    const structuredData = this.data.structuredData || {};
    const cardType = (form.visibilityConfig && form.visibilityConfig.cardType) || "text_note";
    const visibilityConfig = applySystemTagsToConfig({
      ...(form.visibilityConfig || {}),
      structuredData
    }, structuredData);
    const nextForm = {
      ...form,
      visibilityConfig
    };
    const primaryTitle = cardType === "property_listing"
      ? structuredData.community || form.title
      : cardType === "groupbuy_product"
        ? structuredData.productName || form.title
        : cardType === "business_card"
          ? structuredData.name || form.title
          : cardType === "service_offer"
            ? structuredData.serviceName || form.title
            : form.title;
    const title = String(primaryTitle || "").trim();
    if (!title) {
      throw new Error("标题不能为空");
    }
    rememberContactPhone((this.data.structuredData || {}).contact || (this.data.structuredData || {}).phone || form.phone);
    this.setData({
      form: nextForm,
      bookmark: buildBookmark({ ...nextForm, visibilityConfig }),
      commonTagOptions: buildCommonTagOptions(this.data.globalCategories, visibilityConfig)
    });
    await api.updateNote(noteId, {
      ownerUserId: user.id,
      ...nextForm,
      title,
      body: nextForm.body.trim() || title
    });
  },
  initFloatingSave() {
    try {
      const info = wx.getSystemInfoSync();
      const x = Math.max(FLOAT_SAVE_MARGIN, info.windowWidth - FLOAT_SAVE_SIZE - FLOAT_SAVE_MARGIN);
      const y = Math.max(120, Math.round(info.windowHeight / 2 - FLOAT_SAVE_SIZE / 2));
      this.setData({
        saveFloatX: x,
        saveFloatY: y,
        saveFloatLastX: x,
        saveFloatLastY: y
      });
    } catch (error) {
      this.setData({
        saveFloatX: 330,
        saveFloatY: 300,
        saveFloatLastX: 330,
        saveFloatLastY: 300
      });
    }
  },
  handleFloatSaveLongPress() {
    this.setData({ saveFloatMovable: true });
    if (wx.vibrateShort) wx.vibrateShort({ type: "light" });
  },
  handleFloatSaveChange(event) {
    const detail = event.detail || {};
    if (typeof detail.x !== "number" || typeof detail.y !== "number") return;
    this.setData({
      saveFloatLastX: detail.x,
      saveFloatLastY: detail.y
    });
  },
  handleFloatSaveTouchEnd() {
    try {
      const info = wx.getSystemInfoSync();
      const leftX = FLOAT_SAVE_MARGIN;
      const rightX = Math.max(FLOAT_SAVE_MARGIN, info.windowWidth - FLOAT_SAVE_SIZE - FLOAT_SAVE_MARGIN);
      const centerY = Math.max(120, Math.round(info.windowHeight / 2 - FLOAT_SAVE_SIZE / 2));
      const shouldDockLeft = this.data.saveFloatLastX + FLOAT_SAVE_SIZE / 2 < info.windowWidth / 2;
      const nextX = shouldDockLeft ? leftX : rightX;
      this.setData({
        saveFloatMovable: false,
        saveFloatX: nextX,
        saveFloatY: centerY,
        saveFloatLastX: nextX,
        saveFloatLastY: centerY
      });
    } catch (error) {
      this.setData({ saveFloatMovable: false });
    }
  },
  handleOpenSource() {
    const { sourceUrl } = this.data.bookmark || {};
    if (!sourceUrl) {
      wx.showToast({ title: "没有原文链接", icon: "none" });
      return;
    }
    if (/mp\.weixin\.qq\.com/i.test(sourceUrl) && typeof wx.openOfficialAccountArticle === "function") {
      wx.openOfficialAccountArticle({
        url: sourceUrl,
        fail: () => this.copySourceUrl(sourceUrl)
      });
      return;
    }
    this.copySourceUrl(sourceUrl);
  },
  copySourceUrl(url) {
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: "链接已复制", icon: "success" }),
      fail: () => wx.showToast({ title: "复制失败", icon: "none" })
    });
  },
  handleDelete() {
    const { user, noteId } = this.data;
    wx.showModal({
      title: "删除笔记",
      content: "删除笔记不会删除原始归档消息，确认删除吗？",
      confirmColor: "#e5484d",
      success: async ({ confirm }) => {
        if (!confirm) return;
        try {
          await api.deleteNote(noteId, user.id);
          wx.showToast({ title: "已删除", icon: "success" });
          setTimeout(() => wx.navigateBack(), 350);
        } catch (error) {
          wx.showToast({ title: error.detail || "删除失败", icon: "none" });
        }
      }
    });
  },
  onShareAppMessage() {
    const hero = this.data.businessCardHero || null;
    const isProperty = this.data.isProperty;
    const title = hero
      ? buildBusinessCardShareTitle(hero)
      : isProperty
        ? buildPropertyShareTitle(this.data.form, this.data.structuredData || {})
        : this.data.displayTitle || this.data.form.title || "资料详情";
    return {
      title,
      path: `/pages/note-preview/index?id=${this.data.noteId}`,
      imageUrl: this.data.businessCardShareImage || this.data.propertyShareImage || (hero && hero.avatarUrl) || this.data.form.coverUrl || ""
    };
  }
});
