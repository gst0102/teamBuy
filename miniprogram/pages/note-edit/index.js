const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { getCurrentUser } = require("../../utils/dashboard");

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
  { key: "collectLeads", label: "留资表单" },
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
  { key: "utilities", label: "水电物业", placeholder: "例如：自缴", quickOptions: ["民水民电", "商水商电", "水电自缴", "物业已含"] },
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

const CONVERSION_OPTIONS = [
  { key: "showContactPhone", label: "展示联系电话", desc: "生成页展示电话或联系按钮", property: true, groupbuy: true },
  { key: "enableLightScrm", label: "轻 SCRM 跟进", desc: "记录浏览、收藏、咨询等转化行为", property: true, groupbuy: false },
  { key: "collectLeads", label: "收集线索", desc: "允许用户提交联系方式和备注", property: true, groupbuy: false },
  { key: "enableAppointment", label: "预约看房", desc: "房源页展示预约看房入口", property: true, groupbuy: false },
  { key: "enablePrivateConsultation", label: "私聊咨询", desc: "房源页展示私聊咨询入口", property: true, groupbuy: false },
  { key: "enableSharePoster", label: "保存分享图", desc: "保留可保存到相册的图片素材入口", property: true, groupbuy: true },
  { key: "enableGroupRelay", label: "团购接龙", desc: "团购页展示接龙/报名入口", property: false, groupbuy: true },
  { key: "enablePaymentPlaceholder", label: "下单按钮预留", desc: "只展示预留入口，不接真实支付", property: false, groupbuy: false }
];

const PROPERTY_STATUS_OPTIONS = [
  { value: "active", label: "推广中" },
  { value: "rented", label: "已租" },
  { value: "paused", label: "暂停推广" }
];

const NOISY_LABELS = new Set(["未整理", "待整理", "待跟进", "已整理", "房源候选", "团购候选"]);
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
  const tags = filterUsefulLabels(Array.isArray(config.tags) ? config.tags : []);
  const userTags = filterUsefulLabels(Array.isArray(config.userTags) ? config.userTags : []);
  return {
    sourceUrl: config.sourceUrl || "",
    sourceName: config.sourceName || "链接来源",
    sourceLabel: config.sourceLabel || "网页链接",
    sourceType: config.sourceType || "link",
    systemCategory: config.systemCategory || config.category || "文章",
    category: config.systemCategory || config.category || "文章",
    tags,
    userTags,
    topics: Array.isArray(config.topics) ? config.topics.filter((topic) => topic && topic.id && topic.name) : [],
    cardType: config.cardType || (config.contentMode === "bookmark" ? "link" : "text_note"),
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
    .filter((option) => (cardType === "property_listing" ? option.property : cardType === "groupbuy_product" ? option.groupbuy : false))
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
  const noun = isProperty ? "房源" : cardType === "groupbuy_product" ? "团购" : "资料";
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
  const hints = {
    collected: isProperty ? "系统已识别为房源候选，先确认内容，再进入字段编辑。" : "系统已识别资料类型，先确认内容，再进入字段编辑。",
    editing: isProperty ? "先把房源字段修准，转化功能单独配置，不混进房源本体字段。" : "先把商品字段修准，转化功能单独配置。",
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
    : [
        ["contact", "联系方式待确认"],
        ["pickupLocation", "取货地点待确认"]
      ];
  return checks.filter(([key]) => !structuredData[key]).map(([, label]) => label);
}

function buildEnabledLabels(options) {
  return (options || []).filter((item) => item.checked).map((item) => item.label);
}

function buildGenerationOptions(cardType, structuredData) {
  const result = structuredData.organizeResult || {};
  if (Array.isArray(result.generationOptions) && result.generationOptions.length) {
    return result.generationOptions;
  }
  if (cardType === "property_listing") return ["房源推广页", "微信群文案", "客户话术", "对比表"];
  if (cardType === "groupbuy_product") return ["团购分享图", "发群文案", "接龙格式", "商品卖点"];
  return [];
}

function buildGeneratedActions(structuredData, enabledLabels) {
  const generated = structuredData.generatedResult || {};
  return Array.isArray(generated.enabledActions) && generated.enabledActions.length
    ? generated.enabledActions
    : enabledLabels;
}

function buildDisplayTitle(cardType, form, structuredData) {
  if (cardType === "property_listing") return structuredData.community || form.title || "房源资料";
  if (cardType === "groupbuy_product") return structuredData.productName || form.title || "团购商品";
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
  return form.summary || "";
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
  return [form.title, form.summary, form.body].filter(Boolean).join("\n");
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
  return value.length <= 8;
}

function filterUsefulLabels(values) {
  return Array.from(new Set((values || []).map((item) => String(item || "").trim()).filter(isUsefulLabel)));
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
  const address = [
    structuredData.address,
    structuredData.community,
    structuredData.businessArea
  ]
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .filter((item, index, arr) => arr.indexOf(item) === index)
    .join(" ");
  const city = inferCityFromText(address) || readLastPropertyCity();
  if (city && address && !address.includes(city) && !address.includes(city.replace("市", ""))) {
    return `${city} ${address}`;
  }
  return address;
}

function inferMapRegion(structuredData) {
  const text = buildMapAddress(structuredData);
  const remembered = readLastPropertyCity();
  if (remembered) return remembered;
  const city = inferCityFromText(text);
  if (city) return city;
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
      : [];
  return filterUsefulLabels(base).filter((item) => !existing.has(item)).slice(0, 6);
}

function buildSuggestedTopicOptions(cardType, structuredData, form, topics, config) {
  const assigned = new Set((config.topics || []).map((item) => item.name).filter(Boolean));
  const base = cardType === "property_listing"
    ? [structuredData.businessArea ? `${splitUsefulLabels(structuredData.businessArea)[0] || structuredData.businessArea}房源` : ""]
    : cardType === "groupbuy_product"
      ? [isUsefulLabel(structuredData.productName) ? `${structuredData.productName}团购` : "", "团购资料"]
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
    bookmark: {},
    sourceTypes: SOURCE_TYPES,
    systemCategories: SYSTEM_CATEGORIES,
    cardTypeLabel: CARD_TYPES.text_note,
    isProperty: false,
    isGroupbuy: false,
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
    structuredData: {},
    skuConfig: normalizeSkuConfig({}),
    conversionConfig: {},
    conversionOptions: [],
    featurePresets: hydrateFeaturePresets({}),
    suggestionButtons: [],
    recognitionExplanation: {},
    hiddenSections: {},
    uploadDateText: "",
    noteCreatedAt: "",
    displayTitle: "",
    displaySubtitle: "",
    mediaCountText: "",
    mediaItems: [],
    propertyStatusOptions: buildPropertyStatusOptions("active"),
    mapPreview: buildMapPreview({}),
    geocodingAddress: false,
    propertyFields: hydrateFields(PROPERTY_FIELDS, {}),
    groupbuyFields: hydrateFields(GROUPBUY_FIELDS, {}),
    productInfoFields: hydrateFields(PRODUCT_INFO_FIELDS, {}),
    productFulfillmentFields: hydrateFields(PRODUCT_FULFILLMENT_FIELDS, {}),
    topics: [],
    tagDraft: "",
    topicDraft: "",
    suggestedTagOptions: [],
    suggestedTopicOptions: [],
    scrmSummary: EMPTY_SCRM_SUMMARY,
    saveFloatX: 0,
    saveFloatY: 260,
    saveFloatLastX: 0,
    saveFloatLastY: 260,
    saveFloatMovable: false,
    uploadingMedia: false,
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
    this.loadTopics();
    this.loadNote();
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
    const { user, noteId, isProperty, isGroupbuy } = this.data;
    if (!user || !noteId || (!isProperty && !isGroupbuy)) {
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
    const cardState = normalizeCardState(config.cardState);
    const miniappInfo = buildMiniappInfo(structuredData);
    const conversionConfig = {
      ...defaultConversionConfig(cardType),
      ...defaultMiniappConversionConfig(structuredData),
      ...(config.conversionConfig || {})
    };
    const effectiveConfig = { ...config, structuredData, conversionConfig };
    const conversionOptions = hydrateConversionOptions(cardType, conversionConfig);
    const typedFields = cardType === "property_listing" ? PROPERTY_FIELDS : cardType === "groupbuy_product" ? GROUPBUY_FIELDS : [];
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
    this.setData({
      form,
      isBookmark,
      isProperty: cardType === "property_listing",
      isGroupbuy: cardType === "groupbuy_product",
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
      conversionConfig,
      conversionOptions,
      featurePresets: hydrateFeaturePresets(conversionConfig),
      suggestionButtons: buildSuggestionButtons(effectiveConfig.typeSuggestions),
      recognitionExplanation: effectiveConfig.recognitionExplanation || {},
      hiddenSections: hiddenSectionMap(effectiveConfig),
      uploadDateText: formatUploadDate(note.createdAt),
      noteCreatedAt: note.createdAt || "",
      displayTitle: buildDisplayTitle(cardType, form, structuredData),
      displaySubtitle: buildDisplaySubtitle(cardType, form, structuredData),
      mediaCountText: mediaItems.length ? `共 ${mediaItems.length} 个素材，可隐藏但不会删除。` : "暂无素材，可后续补充。",
      mediaItems,
      propertyStatusOptions: buildPropertyStatusOptions(structuredData.propertyStatus),
      mapPreview: buildMapPreview(structuredData),
      propertyFields: hydrateFields(PROPERTY_FIELDS, structuredData),
      groupbuyFields: hydrateFields(GROUPBUY_FIELDS, structuredData),
      productInfoFields: hydrateFields(PRODUCT_INFO_FIELDS, structuredData),
      productFulfillmentFields: hydrateFields(PRODUCT_FULFILLMENT_FIELDS, structuredData),
      suggestedTagOptions: buildSuggestedTagOptions(cardType, structuredData, form, effectiveConfig),
      suggestedTopicOptions: buildSuggestedTopicOptions(cardType, structuredData, form, this.data.topics, effectiveConfig),
      bookmark: buildBookmark(note)
    }, () => {
      this.autoResolveMapLocation({ silent: true });
    });
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
    this.setData({ [`form.${key}`]: event.detail.value });
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
      displayTitle: buildDisplayTitle(cardType, this.data.form, structuredData),
      displaySubtitle: buildDisplaySubtitle(cardType, this.data.form, structuredData),
      suggestedTagOptions: buildSuggestedTagOptions(cardType, structuredData, this.data.form, config),
      suggestedTopicOptions: buildSuggestedTopicOptions(cardType, structuredData, this.data.form, this.data.topics, config),
      mapPreview: buildMapPreview(structuredData),
      "form.visibilityConfig": config
    });
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
      displayTitle: buildDisplayTitle(cardType, this.data.form, structuredData),
      displaySubtitle: buildDisplaySubtitle(cardType, this.data.form, structuredData),
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
  async autoResolveMapLocation({ silent = false } = {}) {
    const structuredData = this.data.structuredData || {};
    const currentPreview = buildMapPreview(structuredData);
    const address = buildMapAddress(structuredData);
    if (!this.data.isProperty || currentPreview.hasPoint || !address || this.data.geocodingAddress) return;

    this.setData({ geocodingAddress: true });
    try {
      const res = await api.geocodeAddress({
        address,
        region: inferMapRegion(structuredData)
      });
      const location = (res && res.data) || {};
      if (!location.found || !location.latitude || !location.longitude) {
        if (!silent && location.configured) {
          wx.showToast({ title: "默认地址暂未匹配到地图", icon: "none" });
        }
        return;
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
    } catch (error) {
      if (!silent) wx.showToast({ title: error.detail || error.message || "默认地址暂未匹配到地图", icon: "none" });
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
      featurePresets: hydrateFeaturePresets(conversionConfig),
      "form.visibilityConfig": config
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
  handleOpenMessages() {
    messagePlugin.openMessageCenter();
  },
  async handleSetCover(event) {
    const url = event.currentTarget.dataset.url;
    if (!url) return;
    const form = { ...this.data.form, coverUrl: url };
    await this.persistMediaState(form, "封面已设置");
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
    const structuredData = { ...(this.data.structuredData || {}), images: buildImageUrls(form) };
    const config = { ...(form.visibilityConfig || {}), structuredData, cardState: "editing" };
    form.visibilityConfig = config;
    const mediaItems = buildMediaItems(form);
    this.setData({
      form,
      structuredData,
      mediaItems,
      mediaCountText: mediaItems.length ? `共 ${mediaItems.length} 个素材，可隐藏但不会删除。` : "暂无素材，可后续补充。",
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
    const primaryTitle = cardType === "property_listing"
      ? structuredData.community || form.title
      : cardType === "groupbuy_product"
        ? structuredData.productName || form.title
        : form.title;
    const title = String(primaryTitle || "").trim();
    if (!title) {
      throw new Error("标题不能为空");
    }
    rememberContactPhone((this.data.structuredData || {}).contact || form.phone);
    await api.updateNote(noteId, {
      ownerUserId: user.id,
      ...form,
      title,
      body: form.body.trim() || title
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
    const title = this.data.displayTitle || this.data.form.title || "资料详情";
    return {
      title,
      path: `/pages/note-preview/index?id=${this.data.noteId}`,
      imageUrl: this.data.form.coverUrl || ""
    };
  }
});
