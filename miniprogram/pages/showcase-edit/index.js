const api = require("../../services/api");
const { getCurrentUser, safeAvatarUrl } = require("../../utils/dashboard");
const { SHOWCASE_TEMPLATES, getShowcaseTemplate } = require("../../utils/showcase-templates");
const {
  decorateNoteForShowcasePicker,
  decorateSelectedShowcaseItem
} = require("../../utils/note-display");

const DEFAULT_GROUP_BY = "tag";
const NOTE_PAGE_SIZE = 10;
const PROPERTY_PRICE_PRESETS = [
  { key: "all", label: "不限", min: "", max: "" },
  { key: "under1300", label: "1300以下", min: "", max: "1300" },
  { key: "1300to1800", label: "1300-1800", min: "1300", max: "1800" },
  { key: "1800to2500", label: "1800-2500", min: "1800", max: "2500" },
  { key: "above2500", label: "2500以上", min: "2500", max: "" }
];
const PROPERTY_LAYOUT_FILTERS = ["不限", "一房", "两房", "三房", "公寓"];
const PROPERTY_METRO_FILTERS = ["不限", "地铁", "近地铁"];
const PROPERTY_ELEVATOR_FILTERS = ["不限", "电梯", "楼梯"];
const PROPERTY_AREA_FILTERS = ["不限", "30㎡内", "30-50㎡", "50㎡以上"];
const PROPERTY_PAYMENT_FILTERS = ["不限", "押一付一", "押一付三"];
const PROPERTY_MOVE_IN_FILTERS = ["不限", "随时入住", "本周可住"];
const PROPERTY_STATUS_FILTERS = ["不限", "可租", "已租", "待确认"];
const GROUPBUY_PRICE_PRESETS = [
  { key: "all", label: "不限", min: "", max: "" },
  { key: "under30", label: "30以下", min: "", max: "30" },
  { key: "30to80", label: "30-80", min: "30", max: "80" },
  { key: "80to150", label: "80-150", min: "80", max: "150" },
  { key: "above150", label: "150以上", min: "150", max: "" }
];
const GROUPBUY_PICKUP_FILTERS = ["不限", "自提", "配送", "快递"];
const GROUPBUY_DEADLINE_FILTERS = ["不限", "今日截止", "本周截止"];
const SHOWCASE_CONDITION_FILTER_KEY = "teambuy:showcaseConditionFilter";
const SHOWCASE_CACHE_PREFIX = "teambuy_showcases_";
const DISPLAY_LAYOUT_OPTIONS = [
  { key: "list", label: "一列" },
  { key: "grid", label: "双列" }
];

const GENERATION_METHODS = [
  {
    key: "filter",
    title: "从当前筛选生成",
    desc: "按分类把符合条件的资料先放进合集，适合快速起一个房源推荐包。",
    enabled: true
  },
  {
    key: "manual",
    title: "手动选择",
    desc: "自己一套套勾选，适合已经知道要发哪几套。",
    enabled: true
  },
  {
    key: "condition",
    title: "按条件筛选",
    desc: "按租金、户型、地铁、电梯/楼梯等强标签筛房源。",
    enabled: true
  },
  {
    key: "activity",
    title: "按近期反馈推荐",
    desc: "根据近期可看、客户点击和同价位房源推荐候选。",
    enabled: false
  }
];

function buildGenerationMethods(category) {
  const isGroupbuy = isGroupbuyCategory(category);
  const isProperty = category === "房产" || category === "房源";
  const isService = category === "服务";
  if (!isGroupbuy && !isProperty) {
    return GENERATION_METHODS.map((item) => {
      if (item.key === "filter") {
        return {
          ...item,
          title: isService ? "从服务资料生成" : "从当前资料生成",
          desc: isService ? "按服务资料把名片、方案和案例先放进案例合集。" : "把当前资料范围内的内容先放进日常合集。"
        };
      }
      if (item.key === "manual") {
        return {
          ...item,
          desc: isService ? "自己勾选要放进案例合集的名片、方案或案例。" : "自己勾选要放进日常合集的笔记、图片或链接。"
        };
      }
      if (item.key === "condition") {
        return {
          ...item,
          title: "按专题/标签生成",
          desc: "按标签范围挑选资料，整理成合集。",
          enabled: false
        };
      }
      if (item.key === "activity") {
        return {
          ...item,
          desc: isService ? "根据近期咨询和打开反馈推荐案例。" : "根据近期打开和点击反馈推荐资料。"
        };
      }
      return item;
    });
  }
  if (!isGroupbuy) return GENERATION_METHODS;
  return GENERATION_METHODS.map((item) => {
    if (item.key === "filter") {
      return {
        ...item,
        desc: "按分类把符合条件的商品先放进合集，适合快速起一波团购。"
      };
    }
    if (item.key === "manual") {
      return {
        ...item,
        desc: "自己一个个勾选，适合已经知道今天要发哪些商品。"
      };
    }
    if (item.key === "condition") {
      return {
        ...item,
        desc: "按价格、取货方式、截止时间筛商品。"
      };
    }
    if (item.key === "activity") {
      return {
        ...item,
        desc: "根据近期接龙、下单和访客反馈推荐候选。"
      };
    }
    return item;
  });
}

function createShareId(showcaseId) {
  return `share_${showcaseId || "showcase"}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
}

function clearShowcaseCaches(userId) {
  if (!userId) return;
  ["notes", "property", "service", "groupbuy"].forEach((mode) => {
    try {
      wx.removeStorageSync(`${SHOWCASE_CACHE_PREFIX}${userId}_${mode}`);
    } catch (error) {}
  });
}

function isPropertyNote(note = {}) {
  const labels = note.categoryLabels || [];
  return note.cardType === "property_listing" || labels.includes("房源") || labels.includes("房产");
}

function isGroupbuyNote(note = {}) {
  const labels = note.categoryLabels || [];
  return note.cardType === "groupbuy_product" || labels.includes("商品") || labels.includes("团购");
}

function isServiceNote(note = {}) {
  const labels = note.categoryLabels || [];
  return note.cardType === "business_card" || note.cardType === "service_offer" || labels.includes("服务") || labels.includes("名片");
}

function isDailyNote(note = {}) {
  return !isPropertyNote(note) && !isGroupbuyNote(note) && !isServiceNote(note);
}

function noteMatchesCategory(note, category) {
  if (!category || category === "全部") return true;
  if (category === "资料" || category === "日常资料") return isDailyNote(note);
  if (category === "房源" || category === "房产") return isPropertyNote(note);
  if (category === "商品" || category === "团购" || category === "电商" || category === "好物") return isGroupbuyNote(note);
  if (category === "服务" || category === "案例") return isServiceNote(note);
  return (note.categoryLabels || []).some((item) => item === category);
}

function buildCategoryOptions(notes) {
  const priority = ["资料", "房源", "商品", "服务", "链接", "图片"];
  const counts = { 全部: notes.length, 资料: 0, 房源: 0, 商品: 0, 服务: 0 };
  notes.forEach((note) => {
    if (isDailyNote(note)) counts["资料"] += 1;
    if (isPropertyNote(note)) counts["房源"] += 1;
    if (isGroupbuyNote(note)) counts["商品"] += 1;
    if (isServiceNote(note)) counts["服务"] += 1;
    (note.categoryLabels || []).forEach((label) => {
      if (["资料", "日常资料", "房源", "房产", "商品", "团购", "服务", "名片"].includes(label)) return;
      counts[label] = (counts[label] || 0) + 1;
    });
  });
  const options = [{ label: "全部", value: "全部", count: counts["全部"] || 0 }];
  priority.forEach((label) => {
    if (counts[label]) options.push({ label, value: label, count: counts[label] });
  });
  Object.keys(counts).sort().forEach((label) => {
    if (label === "全部" || priority.includes(label)) return;
    options.push({ label, value: label, count: counts[label] });
  });
  return options;
}

function inferDefaultCategory(options) {
  return (options.find((item) => item.value === "房产" && item.count) || options.find((item) => item.count) || { value: "全部" }).value;
}

function selectedItemsFromNotes(notes, category) {
  return notes.filter((note) => noteMatchesCategory(note, category)).map((note, index) => ({
    noteId: note.id,
    sortOrder: index,
    sectionTitle: "",
    displayTitle: "",
    visible: true,
    fieldConfig: {}
  }));
}

function selectedItemsFromNoteList(notes) {
  return notes.map((note, index) => ({
    noteId: note.id,
    sortOrder: index,
    sectionTitle: "",
    displayTitle: "",
    visible: true,
    fieldConfig: {}
  }));
}

function noteText(note = {}) {
  const data = note.structuredData || {};
  return [
    note.title,
    note.summary,
    note.body,
    note.primaryText,
    note.secondaryValue,
    note.gridSummary,
    note.tagText,
    data.price,
    data.layout,
    data.area,
    data.floor,
    data.address,
    data.businessArea,
    data.paymentMethod,
    data.moveInTime,
    data.remark,
    data.utilities,
    ...(data.systemTags || []),
    ...(((note.visibilityConfig || {}).tags) || []),
    ...(note.bookmarkTags || []),
    ...(note.categoryLabels || [])
  ].filter(Boolean).join(" ");
}

function noteRent(note = {}) {
  const text = noteText(note);
  const labeled = text.match(/租金\s*([0-9]{3,6})/);
  if (labeled) return Number(labeled[1]);
  const unit = text.match(/(^|[^0-9A-Za-z-])([1-9]\d{2,5})\s*(?:元|块|\/月|每月|月租|月)($|[^0-9A-Za-z-])/);
  if (unit) return Number(unit[2]);
  return 0;
}

function noteArea(note = {}) {
  const text = noteText(note);
  const matched = text.match(/([1-9]\d{1,2})\s*(?:㎡|平|平方)/);
  return matched ? Number(matched[1]) : 0;
}

function noteProductPrice(note = {}) {
  const data = note.structuredData || {};
  const skuConfig = data.skuConfig || {};
  const skuPrices = (skuConfig.skus || [])
    .map((sku) => Number(String(sku.price || "").replace(/[^\d.]/g, "")))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (skuPrices.length) return Math.min(...skuPrices);
  const direct = Number(String(data.price || note.gridPrice || note.primaryText || "").replace(/[^\d.]/g, ""));
  if (Number.isFinite(direct) && direct > 0) return direct;
  const text = noteText(note);
  const labeled = text.match(/(?:¥|￥|价格|团购价|售价|单价)[：:\s]*([1-9]\d{0,4}(?:\.\d{1,2})?)/);
  if (labeled) return Number(labeled[1]);
  const unit = text.match(/([1-9]\d{0,4}(?:\.\d{1,2})?)\s*(?:元|块)(?:\/(?:份|斤|个|盒|件|箱))?/);
  return unit ? Number(unit[1]) : 0;
}

function hasAnyText(text, keywords = []) {
  return keywords.some((keyword) => text.includes(keyword));
}

function noteMatchesPropertyCondition(note = {}, filters = {}) {
  const labels = note.categoryLabels || [];
  const isProperty = note.cardType === "property_listing" || labels.includes("房源") || labels.includes("房产");
  if (!isProperty) return false;
  const text = noteText(note);
  const rent = noteRent(note);
  const area = noteArea(note);
  const min = Number(filters.priceMin || 0);
  const max = Number(filters.priceMax || 0);
  if (min && (!rent || rent < min)) return false;
  if (max && (!rent || rent > max)) return false;
  if (filters.layout && filters.layout !== "不限") {
    const layoutMap = {
      一房: ["一房", "一室", "公寓一房"],
      两房: ["两房", "两室", "二房", "二室"],
      三房: ["三房", "三室"],
      公寓: ["公寓"]
    };
    if (!hasAnyText(text, layoutMap[filters.layout] || [filters.layout])) return false;
  }
  if (filters.metro && filters.metro !== "不限") {
    const keywords = filters.metro === "近地铁" ? ["近地铁", "地铁口", "地铁站", "步行"] : ["地铁", "地铁口", "地铁站"];
    if (!hasAnyText(text, keywords)) return false;
  }
  if (filters.elevator && filters.elevator !== "不限" && !text.includes(filters.elevator)) return false;
  if (filters.area && filters.area !== "不限") {
    if (!area) return false;
    if (filters.area === "30㎡内" && area > 30) return false;
    if (filters.area === "30-50㎡" && (area < 30 || area > 50)) return false;
    if (filters.area === "50㎡以上" && area < 50) return false;
  }
  if (filters.payment && filters.payment !== "不限" && !text.includes(filters.payment)) return false;
  if (filters.moveIn && filters.moveIn !== "不限") {
    const moveMap = {
      随时入住: ["随时入住", "拎包入住", "空置"],
      本周可住: ["本周可住", "本周入住"]
    };
    if (!hasAnyText(text, moveMap[filters.moveIn] || [filters.moveIn])) return false;
  }
  if (filters.status && filters.status !== "不限") {
    const statusMap = {
      可租: ["可租", "在租", "可看", "空置"],
      已租: ["已租", "已出租"],
      待确认: ["待确认", "待核实", "待补"]
    };
    if (!hasAnyText(text, statusMap[filters.status] || [filters.status])) return false;
  }
  return true;
}

function noteMatchesGroupbuyCondition(note = {}, filters = {}) {
  const labels = note.categoryLabels || [];
  const isGroupbuy = note.cardType === "groupbuy_product" || labels.includes("商品") || labels.includes("团购");
  if (!isGroupbuy) return false;
  const text = noteText(note);
  const price = noteProductPrice(note);
  const min = Number(filters.priceMin || 0);
  const max = Number(filters.priceMax || 0);
  if (min && (!price || price < min)) return false;
  if (max && (!price || price > max)) return false;
  if (filters.pickup && filters.pickup !== "不限" && !text.includes(filters.pickup)) return false;
  if (filters.deadline && filters.deadline !== "不限") {
    if (filters.deadline === "今日截止" && !hasAnyText(text, ["今日截止", "今天截止", "今晚截止", "当天截止"])) return false;
    if (filters.deadline === "本周截止" && !hasAnyText(text, ["本周截止", "周末截止", "这周截止", "截止"])) return false;
  }
  return true;
}

function firstCover(notes, selectedItems) {
  const selectedIds = new Set((selectedItems || []).map((item) => item.noteId));
  const note = notes.find((item) => selectedIds.has(item.id) && item.coverUrl);
  return note ? note.coverUrl : "";
}

function firstPhone(notes, selectedItems, user) {
  if (user && user.phone) return user.phone;
  const selectedIds = new Set((selectedItems || []).map((item) => item.noteId));
  const note = notes.find((item) => selectedIds.has(item.id) && item.contactPhone);
  return note ? note.contactPhone : "";
}

function firstWechat(notes, selectedItems) {
  const selectedIds = new Set((selectedItems || []).map((item) => item.noteId));
  const note = notes.find((item) => selectedIds.has(item.id) && item.contactWechat);
  return note ? note.contactWechat : "";
}

function firstOwnerName(notes, selectedItems, user) {
  if (user && user.nickname) return user.nickname;
  const selectedIds = new Set((selectedItems || []).map((item) => item.noteId));
  const note = notes.find((item) => selectedIds.has(item.id) && item.contactName);
  return note ? note.contactName : "";
}

function firstAvatar(notes, selectedItems, user) {
  if (user && safeAvatarUrl(user.avatarUrl)) return safeAvatarUrl(user.avatarUrl);
  const selectedIds = new Set((selectedItems || []).map((item) => item.noteId));
  const note = notes.find((item) => selectedIds.has(item.id) && item.contactAvatarUrl);
  return note ? safeAvatarUrl(note.contactAvatarUrl) : "";
}

function defaultName(category, template) {
  if (category === "房产" || category === "房源") return "我的房源精选";
  if (category === "商品" || category === "团购" || category === "电商" || category === "好物") return "我的好物精选";
  if (category === "服务") return "我的案例合集";
  if (!category || category === "全部" || category === "资料") return "我的日常合集";
  if (category && category !== "全部") return `${category}精选`;
  return template.name;
}

function defaultDescription(category, template) {
  if (category === "房产" || category === "房源") return "精选近期可看房源，方便客户快速浏览、对比和联系。";
  if (category === "商品" || category === "团购" || category === "电商" || category === "好物") return "精选近期主推好物，方便客户快速了解、下单和咨询。";
  if (!category || category === "全部" || category === "资料") return "把相关资料放在一起，方便集中查看和分享。";
  if (category && category !== "全部") return `精选${category}资料，方便客户集中查看和联系。`;
  return template.subtitle;
}

function defaultContactText(category) {
  if (category === "房产" || category === "房源") return "想了解房源细节，欢迎直接联系我。";
  if (category === "商品" || category === "团购" || category === "电商" || category === "好物") return "想下单或咨询规格，欢迎直接联系我。";
  return "欢迎联系我了解详情。";
}

function isGroupbuyCategory(category) {
  return ["商品", "团购", "电商", "好物"].includes(category);
}

function buildShowcaseSceneTexts(category) {
  const isGroupbuy = isGroupbuyCategory(category);
  const isProperty = category === "房产" || category === "房源";
  const isService = category === "服务";
  const dailyTitle = "日常合集";
  const sceneName = isGroupbuy ? "商品合集" : isProperty ? "房源合集" : isService ? "案例合集" : dailyTitle;
  return {
    isGroupbuy,
    isProperty,
    isService,
    sceneName,
    shareAction: isGroupbuy ? "发到群里" : isProperty || isService ? "发给客户" : "分享日常合集",
    createTitle: `新建${sceneName}`,
    createPlaceholder: isGroupbuy ? "合集名称，例如：本周水果团购" : isProperty ? "合集名称，例如：树木岭一房精选" : isService ? "合集名称，例如：老客户案例精选" : "合集名称，例如：项目资料整理",
    descriptionPlaceholder: isGroupbuy ? "合集说明，例如：整理了今天可接龙的商品，客户打开后可以看详情和下单。" : isProperty ? "合集说明，例如：整理了几套 1300 左右、适合一个人住的房源。客户打开后可以直接看详情和预约。" : isService ? "合集说明，例如：整理服务案例、方案和名片，方便客户集中查看。" : "合集说明，例如：把相关笔记、图片和链接放在一起，方便集中查看。",
    generationTitle: isGroupbuy ? "先决定商品怎么放进合集" : isProperty ? "先决定房源怎么放进合集" : isService ? "先决定案例怎么放进合集" : "先决定资料怎么放进合集",
    conditionTitle: isGroupbuy ? "商品条件" : isProperty ? "房源条件" : "资料条件",
    confirmTitle: isGroupbuy ? "选择和确认商品" : isProperty ? "选择和确认房源" : isService ? "选择和确认案例" : "选择和确认资料",
    noteSectionMeta: isGroupbuy ? "确认哪些商品发到群里" : isProperty ? "确认哪些资料给客户看" : isService ? "确认案例合集里包含哪些内容" : "确认日常合集里包含哪些内容",
    contactHint: isGroupbuy ? "客户页底部展示，可作为咨询或补单入口" : "客户页底部展示",
    selectedTitle: isGroupbuy ? "已选商品顺序" : isService ? "已选案例顺序" : "已选资料顺序",
    previewTitle: isGroupbuy ? "发群前先看客户页效果" : isProperty || isService ? "发布前先看客户页效果" : "发布前先看日常合集效果",
    previewMeta: isGroupbuy ? "确认模板、标题、商品顺序、价格和联系方式后，再发布发群。" : isProperty ? "确认模板、标题、房源顺序和联系方式后，再发布发给客户。" : isService ? "确认模板、标题、案例顺序和联系方式后，再发布发给客户。" : "确认模板、标题、资料顺序和联系文案后，再发布分享。",
    publishButton: "发布",
    publishModalTitle: isGroupbuy ? "发群前检查" : "发布前检查"
  };
}

function buildShowcasePublishChecks({ name, selectedItems, selectedRows, bannerUrl, phone, wechat, contactText, activeCategory }) {
  const visibleRows = (selectedRows || []).filter((item) => item.visible !== false);
  const hasContact = Boolean(phone || wechat || contactText);
  const isGroupbuy = isGroupbuyCategory(activeCategory);
  const isProperty = activeCategory === "房产" || activeCategory === "房源";
  const checks = [
    { key: "name", label: "合集名称", ok: Boolean(String(name || "").trim()), fix: "补一个容易理解的合集名称" },
    { key: "items", label: isGroupbuy ? "已选商品" : isProperty ? "已选房源" : "已选资料", ok: (selectedItems || []).some((item) => item.visible !== false), fix: isGroupbuy ? "至少选择一个要发到群里的商品" : isProperty ? "至少选择一套要发给客户的房源" : "至少选择一条要放进合集的资料" },
    { key: "banner", label: "合集封面", ok: Boolean(bannerUrl || visibleRows.some((item) => item.coverUrl)), fix: isGroupbuy ? "建议设置封面，或确保第一个商品有图" : isProperty ? "建议设置封面，或确保第一套房源有图" : "建议设置封面，或确保第一条资料有图" },
    { key: "contact", label: "联系入口", ok: hasContact, fix: isGroupbuy ? "补电话、微信或联系文案，方便客户咨询和补单" : "补电话、微信或联系文案" }
  ];
  if (isGroupbuy) {
    const missingPriceCount = visibleRows.filter((item) => !noteProductPrice(item)).length;
    const missingPickupCount = visibleRows.filter((item) => {
      const data = item.structuredData || {};
      const text = `${item.visibleText || ""} ${item.title || ""}`;
      return !data.pickupMethod && !data.pickupLocation && !hasAnyText(text, ["自提", "配送", "快递", "取货"]);
    }).length;
    if (missingPriceCount) checks.push({ key: "price", label: "价格完整度", ok: false, fix: `${missingPriceCount} 个商品价格可能缺失，发群前建议确认` });
    if (missingPickupCount) checks.push({ key: "pickup", label: "取货信息", ok: false, fix: `${missingPickupCount} 个商品缺少取货方式或地点，发群前建议确认` });
  } else if (isProperty) {
    const missingPriceCount = visibleRows.filter((item) => !String(item.visibleText || "").includes("租金") && !/[1-9]\d{2,5}/.test(`${item.visibleText || ""} ${item.title || ""}`)).length;
    if (missingPriceCount) {
      checks.push({ key: "price", label: "租金完整度", ok: false, fix: `${missingPriceCount} 套房源租金可能缺失，发布前建议确认` });
    }
  }
  return checks.map((item) => ({
    ...item,
    tone: item.ok ? "ok" : "warn",
    statusText: item.ok ? "已完成" : "待完善"
  }));
}

function categoryForMode(mode) {
  if (mode === "property") return "房源";
  if (mode === "groupbuy") return "团购";
  if (mode === "service") return "服务";
  return "资料";
}

function readConditionFilter() {
  try {
    const value = wx.getStorageSync(SHOWCASE_CONDITION_FILTER_KEY);
    wx.removeStorageSync(SHOWCASE_CONDITION_FILTER_KEY);
    if (!value || Date.now() - Number(value.ts || 0) > 10 * 60 * 1000) return null;
    return value;
  } catch (error) {
    return null;
  }
}

function shouldRefreshGeneratedInfo(value, previousCategory, template) {
  if (!value) return true;
  return value === defaultName(previousCategory, template) || SHOWCASE_TEMPLATES.some((item) => value === defaultName(previousCategory, item) || value === item.name);
}

function shouldRefreshDescription(value, previousCategory, template) {
  if (!value) return true;
  return value === defaultDescription(previousCategory, template) || SHOWCASE_TEMPLATES.some((item) => value === item.subtitle || value === defaultDescription(previousCategory, item));
}

Page({
  data: {
    id: "",
    user: null,
    loading: false,
    saving: false,
    status: "draft",
    name: "",
    description: "",
    bannerUrl: "",
    shareTitle: "",
    phone: "",
    wechat: "",
    contactText: "欢迎联系我了解详情",
    templates: SHOWCASE_TEMPLATES,
    displayLayoutOptions: DISPLAY_LAYOUT_OPTIONS,
    displayLayout: "list",
    generationMethods: buildGenerationMethods("房产"),
    sceneTexts: buildShowcaseSceneTexts("房产"),
    activeGenerationMethod: "filter",
    propertyPricePresets: PROPERTY_PRICE_PRESETS,
    propertyPricePreset: "all",
    propertyPriceMin: "",
    propertyPriceMax: "",
    propertyLayoutFilters: PROPERTY_LAYOUT_FILTERS,
    propertyLayoutFilter: "不限",
    propertyMetroFilters: PROPERTY_METRO_FILTERS,
    propertyMetroFilter: "不限",
    propertyElevatorFilters: PROPERTY_ELEVATOR_FILTERS,
    propertyElevatorFilter: "不限",
    propertyAreaFilters: PROPERTY_AREA_FILTERS,
    propertyAreaFilter: "不限",
    propertyPaymentFilters: PROPERTY_PAYMENT_FILTERS,
    propertyPaymentFilter: "不限",
    propertyMoveInFilters: PROPERTY_MOVE_IN_FILTERS,
    propertyMoveInFilter: "不限",
    propertyStatusFilters: PROPERTY_STATUS_FILTERS,
    propertyStatusFilter: "不限",
    groupbuyPricePresets: GROUPBUY_PRICE_PRESETS,
    groupbuyPricePreset: "all",
    groupbuyPriceMin: "",
    groupbuyPriceMax: "",
    groupbuyPickupFilters: GROUPBUY_PICKUP_FILTERS,
    groupbuyPickupFilter: "不限",
    groupbuyDeadlineFilters: GROUPBUY_DEADLINE_FILTERS,
    groupbuyDeadlineFilter: "不限",
    activeTemplateId: SHOWCASE_TEMPLATES[0].id,
    activeTemplate: SHOWCASE_TEMPLATES[0],
    activeCategory: "房产",
    categoryOptions: [],
    noteViewMode: "list",
    noteVisibleCount: NOTE_PAGE_SIZE,
    showNotePicker: true,
    notes: [],
    filteredNotes: [],
    visibleFilteredNotes: [],
    filteredTotalCount: 0,
    hasMoreFilteredNotes: false,
    selectedItems: [],
    selectedRows: [],
    selectedCount: 0,
    unpublishedChanges: false,
    preselectNoteId: "",
    preselectTopicId: "",
    preselectTopicName: "",
    radarCompareMode: false,
    publishChecks: []
  },
  onLoad(options) {
    const modeCategory = categoryForMode(options.mode || "");
    const conditionFilter = readConditionFilter();
    this.setData({
      id: options.id || "",
      preselectNoteId: options.noteId || "",
      preselectTopicId: options.topicId || "",
      preselectTopicName: options.topicName ? decodeURIComponent(options.topicName) : "",
      radarCompareMode: options.method === "radar_compare",
      activeCategory: modeCategory,
      sceneTexts: buildShowcaseSceneTexts(modeCategory),
      generationMethods: buildGenerationMethods(modeCategory),
      activeGenerationMethod: options.method === "condition" || conditionFilter ? "condition" : options.method === "radar_compare" ? "manual" : this.data.activeGenerationMethod,
      propertyPricePreset: conditionFilter ? "custom" : this.data.propertyPricePreset,
      propertyPriceMin: conditionFilter ? conditionFilter.priceMin || "" : this.data.propertyPriceMin,
      propertyPriceMax: conditionFilter ? conditionFilter.priceMax || "" : this.data.propertyPriceMax,
      propertyLayoutFilter: conditionFilter ? conditionFilter.layout || "不限" : this.data.propertyLayoutFilter,
      propertyMetroFilter: conditionFilter ? conditionFilter.metro || "不限" : this.data.propertyMetroFilter,
      propertyElevatorFilter: conditionFilter ? conditionFilter.elevator || "不限" : this.data.propertyElevatorFilter,
      propertyAreaFilter: conditionFilter ? conditionFilter.area || "不限" : this.data.propertyAreaFilter,
      propertyPaymentFilter: conditionFilter ? conditionFilter.payment || "不限" : this.data.propertyPaymentFilter,
      propertyMoveInFilter: conditionFilter ? conditionFilter.moveIn || "不限" : this.data.propertyMoveInFilter,
      propertyStatusFilter: conditionFilter ? conditionFilter.status || "不限" : this.data.propertyStatusFilter,
      groupbuyPricePreset: conditionFilter && conditionFilter.mode === "groupbuy" ? "custom" : this.data.groupbuyPricePreset,
      groupbuyPriceMin: conditionFilter && conditionFilter.mode === "groupbuy" ? conditionFilter.priceMin || "" : this.data.groupbuyPriceMin,
      groupbuyPriceMax: conditionFilter && conditionFilter.mode === "groupbuy" ? conditionFilter.priceMax || "" : this.data.groupbuyPriceMax,
      groupbuyPickupFilter: conditionFilter && conditionFilter.mode === "groupbuy" ? conditionFilter.pickup || "不限" : this.data.groupbuyPickupFilter,
      groupbuyDeadlineFilter: conditionFilter && conditionFilter.mode === "groupbuy" ? conditionFilter.deadline || "不限" : this.data.groupbuyDeadlineFilter
    });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    this.loadAll();
  },
  async loadAll() {
    const { id, user } = this.data;
    if (!user) return;
    this.setData({ loading: true });
    try {
      let selectedItems = [];
      let activeTemplateId = SHOWCASE_TEMPLATES[0].id;
      let loadedFromServer = false;
      if (id) {
        loadedFromServer = true;
        const detail = await api.fetchShowcase(id, user.id);
        const page = detail.data || {};
        const contact = page.contactConfig || {};
        const display = page.displayConfig || {};
        activeTemplateId = page.templateId || SHOWCASE_TEMPLATES[0].id;
        selectedItems = (page.items || []).map((item, index) => ({
          noteId: item.noteId,
          sortOrder: item.sortOrder == null ? index : item.sortOrder,
          sectionTitle: item.sectionTitle || "",
          displayTitle: item.displayTitle || "",
          visible: item.visible !== false,
          fieldConfig: item.fieldConfig || {}
        }));
        this.setData({
          status: page.status || "draft",
          unpublishedChanges: false,
          name: page.name || "",
          description: page.description || "",
          bannerUrl: page.bannerUrl || "",
          shareTitle: page.shareTitle || "",
          phone: contact.phone || "",
          wechat: contact.wechat || "",
          contactText: contact.contactText || "欢迎联系我了解详情",
          displayLayout: display.layoutMode === "grid" ? "grid" : "list",
          activeTemplateId,
          activeTemplate: getShowcaseTemplate(activeTemplateId),
          activeGenerationMethod: display.generationMethod || "filter",
          activeCategory: display.activeCategory || this.data.activeCategory,
          sceneTexts: buildShowcaseSceneTexts(display.activeCategory || this.data.activeCategory),
          generationMethods: buildGenerationMethods(display.activeCategory || this.data.activeCategory),
          selectedItems
        });
      }
      const noteParams = {
        ownerUserId: user.id,
        sort: "updated"
      };
      if (!id && this.data.preselectTopicId) {
        noteParams.topicId = this.data.preselectTopicId;
      }
      const notesRes = await api.fetchNotes(noteParams);
      const notes = (notesRes.data || []).map((note) => decorateNoteForShowcasePicker(note, selectedItems));
      const categoryOptions = buildCategoryOptions(notes);
      const activeCategory = loadedFromServer
        ? this.resolveLoadedCategory(this.data.activeCategory, categoryOptions, notes, selectedItems)
        : this.resolveLoadedCategory(this.data.activeCategory, categoryOptions, notes, selectedItems) || inferDefaultCategory(categoryOptions);
      if (!loadedFromServer) {
        if (this.data.preselectNoteId) {
          selectedItems = [{
            noteId: this.data.preselectNoteId,
            sortOrder: 0,
            sectionTitle: "",
            displayTitle: "",
            visible: true,
            fieldConfig: {}
          }];
        } else if (this.data.preselectTopicId) {
          selectedItems = selectedItemsFromNoteList(notes);
        } else {
          selectedItems = this.data.activeGenerationMethod === "condition"
            ? selectedItemsFromNoteList(this.filterNotesByCurrentMode(notes, "condition"))
            : selectedItemsFromNotes(notes, activeCategory);
        }
        const template = getShowcaseTemplate(activeTemplateId);
        const selectedNote = notes.find((note) => note.id === this.data.preselectNoteId);
        const defaultTitle = selectedNote
          ? `${selectedNote.title || "资料"}日常合集`
          : this.data.preselectTopicName
            ? `${this.data.preselectTopicName}日常合集`
            : defaultName(activeCategory, template);
        this.setData({
          name: defaultTitle,
          description: defaultDescription(activeCategory, template),
          shareTitle: defaultTitle,
          bannerUrl: firstCover(notes, selectedItems),
          phone: firstPhone(notes, selectedItems, user),
          wechat: firstWechat(notes, selectedItems),
          contactText: defaultContactText(activeCategory),
          sceneTexts: buildShowcaseSceneTexts(activeCategory),
          generationMethods: buildGenerationMethods(activeCategory),
          selectedItems
        });
      }
      this.setData({
        notes: notes.map((note) => ({
          ...note,
          selected: selectedItems.some((item) => item.noteId === note.id),
          selectedText: selectedItems.some((item) => item.noteId === note.id) ? "已加入" : "加入合集"
        })),
        categoryOptions,
        activeCategory,
        sceneTexts: buildShowcaseSceneTexts(activeCategory),
        generationMethods: buildGenerationMethods(activeCategory)
      });
      this.refreshSelectionState();
    } catch (error) {
      wx.showToast({ title: error.detail || "展示页加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  updateField(event) {
    const key = event.currentTarget.dataset.key;
    this.setData(this.withUnpublishedChanges({ [key]: event.detail.value }), () => this.refreshPublishChecks());
  },
  withUnpublishedChanges(patch = {}) {
    if (this.data.status === "published") {
      return { ...patch, unpublishedChanges: true };
    }
    return patch;
  },
  handleTemplateSelect(event) {
    const templateId = event.currentTarget.dataset.id;
    const template = getShowcaseTemplate(templateId);
    const patch = {
      activeTemplateId: template.id,
      activeTemplate: template
    };
    if (!this.data.id) {
      patch.name = defaultName(this.data.activeCategory, template);
      patch.description = defaultDescription(this.data.activeCategory, template);
      patch.shareTitle = defaultName(this.data.activeCategory, template);
    }
    this.setData(this.withUnpublishedChanges(patch));
  },
  handleDisplayLayoutSelect(event) {
    const layout = event.currentTarget.dataset.layout === "grid" ? "grid" : "list";
    this.setData(this.withUnpublishedChanges({ displayLayout: layout }));
  },
  handleCategorySelect(event) {
    const category = event.currentTarget.dataset.value || "全部";
    const selectedItems = this.data.activeGenerationMethod === "filter"
      ? selectedItemsFromNotes(this.data.notes, category)
      : this.data.selectedItems;
    const template = getShowcaseTemplate(this.data.activeTemplateId);
    const previousCategory = this.data.activeCategory;
    const refreshName = shouldRefreshGeneratedInfo(this.data.name, previousCategory, template);
    const refreshShareTitle = shouldRefreshGeneratedInfo(this.data.shareTitle, previousCategory, template);
    const refreshDescription = shouldRefreshDescription(this.data.description, previousCategory, template);
    this.setData(this.withUnpublishedChanges({
      activeCategory: category,
      sceneTexts: buildShowcaseSceneTexts(category),
      generationMethods: buildGenerationMethods(category),
      noteVisibleCount: NOTE_PAGE_SIZE,
      selectedItems,
      name: refreshName ? defaultName(category, template) : this.data.name,
      description: refreshDescription ? defaultDescription(category, template) : this.data.description,
      shareTitle: refreshShareTitle ? defaultName(category, template) : this.data.shareTitle,
      bannerUrl: firstCover(this.data.notes, selectedItems) || this.data.bannerUrl,
      phone: this.data.phone || firstPhone(this.data.notes, selectedItems, this.data.user),
      wechat: this.data.wechat || firstWechat(this.data.notes, selectedItems),
      contactText: this.data.contactText || defaultContactText(category)
    }), () => {
      if (this.data.activeGenerationMethod === "condition") {
        this.applyConditionSelection();
        return;
      }
      this.refreshSelectionState();
    });
  },
  handleGenerationMethodSelect(event) {
    const key = event.currentTarget.dataset.key || "filter";
    const method = GENERATION_METHODS.find((item) => item.key === key);
    if (!method) return;
    if (!method.enabled) {
      wx.showToast({ title: "下一版开放", icon: "none" });
      return;
    }
    const selectedItems = key === "filter"
      ? selectedItemsFromNotes(this.data.notes, this.data.activeCategory)
      : key === "condition"
        ? selectedItemsFromNoteList(this.filterNotesByCurrentMode(this.data.notes, key))
        : [];
    const patch = {
      activeGenerationMethod: key,
      noteVisibleCount: NOTE_PAGE_SIZE,
      selectedItems,
      showNotePicker: true,
      bannerUrl: firstCover(this.data.notes, selectedItems) || this.data.bannerUrl,
      phone: this.data.phone || firstPhone(this.data.notes, selectedItems, this.data.user),
      wechat: this.data.wechat || firstWechat(this.data.notes, selectedItems)
    };
    this.setData(this.withUnpublishedChanges(patch));
    this.refreshSelectionState();
  },
  filterNotesByCurrentMode(notes, method) {
    const activeMethod = method || this.data.activeGenerationMethod;
    const isGroupbuy = isGroupbuyCategory(this.data.activeCategory);
    const filters = {
      priceMin: this.data.propertyPriceMin,
      priceMax: this.data.propertyPriceMax,
      layout: this.data.propertyLayoutFilter,
      metro: this.data.propertyMetroFilter,
      elevator: this.data.propertyElevatorFilter,
      area: this.data.propertyAreaFilter,
      payment: this.data.propertyPaymentFilter,
      moveIn: this.data.propertyMoveInFilter,
      status: this.data.propertyStatusFilter
    };
    const groupbuyFilters = {
      priceMin: this.data.groupbuyPriceMin,
      priceMax: this.data.groupbuyPriceMax,
      pickup: this.data.groupbuyPickupFilter,
      deadline: this.data.groupbuyDeadlineFilter
    };
    return notes
      .filter((note) => noteMatchesCategory(note, this.data.activeCategory))
      .filter((note) => {
        if (activeMethod !== "condition") return true;
        return isGroupbuy ? noteMatchesGroupbuyCondition(note, groupbuyFilters) : noteMatchesPropertyCondition(note, filters);
      });
  },
  applyConditionSelection() {
    const selectedItems = selectedItemsFromNoteList(this.filterNotesByCurrentMode(this.data.notes, "condition"));
    this.setData(this.withUnpublishedChanges({
      selectedItems,
      noteVisibleCount: NOTE_PAGE_SIZE,
      bannerUrl: firstCover(this.data.notes, selectedItems) || this.data.bannerUrl,
      phone: this.data.phone || firstPhone(this.data.notes, selectedItems, this.data.user),
      wechat: this.data.wechat || firstWechat(this.data.notes, selectedItems)
    }));
    this.refreshSelectionState();
  },
  handlePropertyPricePreset(event) {
    const key = event.currentTarget.dataset.key || "all";
    const preset = PROPERTY_PRICE_PRESETS.find((item) => item.key === key) || PROPERTY_PRICE_PRESETS[0];
    this.setData(this.withUnpublishedChanges({
      activeGenerationMethod: "condition",
      propertyPricePreset: preset.key,
      propertyPriceMin: preset.min,
      propertyPriceMax: preset.max
    }), () => this.applyConditionSelection());
  },
  handlePropertyPriceInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = String(event.detail.value || "").replace(/[^\d]/g, "");
    this.setData(this.withUnpublishedChanges({
      activeGenerationMethod: "condition",
      [key]: value,
      propertyPricePreset: "custom"
    }), () => this.applyConditionSelection());
  },
  handlePropertyQuickFilter(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.currentTarget.dataset.value || "不限";
    this.setData(this.withUnpublishedChanges({
      activeGenerationMethod: "condition",
      [key]: value
    }), () => this.applyConditionSelection());
  },
  handleResetPropertyFilters() {
    this.setData(this.withUnpublishedChanges({
      activeGenerationMethod: "condition",
      propertyPricePreset: "all",
      propertyPriceMin: "",
      propertyPriceMax: "",
      propertyLayoutFilter: "不限",
      propertyMetroFilter: "不限",
      propertyElevatorFilter: "不限",
      propertyAreaFilter: "不限",
      propertyPaymentFilter: "不限",
      propertyMoveInFilter: "不限",
      propertyStatusFilter: "不限"
    }), () => this.applyConditionSelection());
  },
  handleGroupbuyPricePreset(event) {
    const key = event.currentTarget.dataset.key || "all";
    const preset = GROUPBUY_PRICE_PRESETS.find((item) => item.key === key) || GROUPBUY_PRICE_PRESETS[0];
    this.setData(this.withUnpublishedChanges({
      activeGenerationMethod: "condition",
      groupbuyPricePreset: preset.key,
      groupbuyPriceMin: preset.min,
      groupbuyPriceMax: preset.max
    }), () => this.applyConditionSelection());
  },
  handleGroupbuyPriceInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = String(event.detail.value || "").replace(/[^\d.]/g, "");
    this.setData(this.withUnpublishedChanges({
      activeGenerationMethod: "condition",
      [key]: value,
      groupbuyPricePreset: "custom"
    }), () => this.applyConditionSelection());
  },
  handleGroupbuyQuickFilter(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.currentTarget.dataset.value || "不限";
    this.setData(this.withUnpublishedChanges({
      activeGenerationMethod: "condition",
      [key]: value
    }), () => this.applyConditionSelection());
  },
  handleResetGroupbuyFilters() {
    this.setData(this.withUnpublishedChanges({
      activeGenerationMethod: "condition",
      groupbuyPricePreset: "all",
      groupbuyPriceMin: "",
      groupbuyPriceMax: "",
      groupbuyPickupFilter: "不限",
      groupbuyDeadlineFilter: "不限"
    }), () => this.applyConditionSelection());
  },
  handleNoteViewModeChange(event) {
    this.setData({ noteViewMode: event.currentTarget.dataset.mode || "list" });
  },
  handleLoadMoreNotes() {
    this.setData({ noteVisibleCount: this.data.noteVisibleCount + NOTE_PAGE_SIZE });
    this.refreshSelectionState();
  },
  toggleNotePicker() {
    this.setData({ showNotePicker: !this.data.showNotePicker });
  },
  async handleBannerUpload() {
    const { user } = this.data;
    if (!user) return;
    try {
      const chooseRes = await wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sourceType: ["album", "camera"],
        sizeType: ["compressed"]
      });
      const file = (chooseRes.tempFiles || [])[0];
      if (!file || !file.tempFilePath) return;
      wx.showLoading({ title: "上传中" });
      const uploaded = await api.uploadAsset({
        filePath: file.tempFilePath,
        mediaType: "image",
        ownerUserId: user.id
      });
      this.setData(this.withUnpublishedChanges({ bannerUrl: uploaded.url || uploaded.displayUrl || "" }), () => this.refreshPublishChecks());
      wx.showToast({ title: "已上传", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "上传失败", icon: "none" });
    } finally {
      wx.hideLoading();
    }
  },
  toggleNote(event) {
    const noteId = (event.detail && event.detail.id) || event.currentTarget.dataset.id;
    const selectedItems = this.data.selectedItems.slice();
    const existingIndex = selectedItems.findIndex((item) => item.noteId === noteId);
    if (existingIndex >= 0) {
      selectedItems.splice(existingIndex, 1);
    } else {
      selectedItems.push({
        noteId,
        sortOrder: selectedItems.length,
        sectionTitle: "",
        displayTitle: "",
        visible: true,
        fieldConfig: {}
      });
    }
    this.setData(this.withUnpublishedChanges({ selectedItems: this.reindexItems(selectedItems) }));
    this.refreshSelectionState();
  },
  toggleSelectedVisible(event) {
    const noteId = event.currentTarget.dataset.id;
    const selectedItems = this.data.selectedItems.map((item) => (
      item.noteId === noteId ? { ...item, visible: item.visible === false } : item
    ));
    this.setData(this.withUnpublishedChanges({ selectedItems }));
    this.rebuildSelectedRows();
  },
  removeSelected(event) {
    const noteId = event.currentTarget.dataset.id;
    const selectedItems = this.data.selectedItems.filter((item) => item.noteId !== noteId);
    this.setData(this.withUnpublishedChanges({ selectedItems: this.reindexItems(selectedItems) }));
    this.refreshSelectionState();
  },
  updateSelectedField(event) {
    const noteId = event.currentTarget.dataset.id;
    const key = event.currentTarget.dataset.key;
    const selectedItems = this.data.selectedItems.map((item) => (
      item.noteId === noteId ? { ...item, [key]: event.detail.value } : item
    ));
    this.setData(this.withUnpublishedChanges({ selectedItems }));
    this.rebuildSelectedRows();
  },
  moveSelected(event) {
    const noteId = event.currentTarget.dataset.id;
    const direction = event.currentTarget.dataset.direction;
    const selectedItems = this.data.selectedItems.slice();
    const index = selectedItems.findIndex((item) => item.noteId === noteId);
    const target = direction === "up" ? index - 1 : index + 1;
    if (index < 0 || target < 0 || target >= selectedItems.length) return;
    const temp = selectedItems[index];
    selectedItems[index] = selectedItems[target];
    selectedItems[target] = temp;
    this.setData(this.withUnpublishedChanges({ selectedItems: this.reindexItems(selectedItems) }));
    this.rebuildSelectedRows();
  },
  reindexItems(items) {
    return items.map((item, index) => ({ ...item, sortOrder: index }));
  },
  refreshSelectionState() {
    const { notes, selectedItems } = this.data;
    const refreshedNotes = notes.map((note) => decorateNoteForShowcasePicker(note, selectedItems));
    const filteredNotes = this.filterNotesByCurrentMode(refreshedNotes);
    const visibleFilteredNotes = filteredNotes.slice(0, this.data.noteVisibleCount);
    this.setData({
      notes: refreshedNotes,
      filteredNotes,
      visibleFilteredNotes,
      filteredTotalCount: filteredNotes.length,
      hasMoreFilteredNotes: visibleFilteredNotes.length < filteredNotes.length,
      selectedCount: selectedItems.filter((item) => item.visible !== false).length
    });
    this.rebuildSelectedRows();
  },
  rebuildSelectedRows() {
    const { selectedItems, notes } = this.data;
    const rows = selectedItems.map((item, index) => {
      const note = notes.find((row) => row.id === item.noteId);
      return decorateSelectedShowcaseItem(item, note, index);
    });
    this.setData({ selectedRows: rows }, () => this.refreshPublishChecks());
  },
  refreshPublishChecks() {
    this.setData({
      publishChecks: buildShowcasePublishChecks({
        name: this.data.name,
        selectedItems: this.data.selectedItems,
        selectedRows: this.data.selectedRows,
        bannerUrl: this.data.bannerUrl,
        phone: this.data.phone,
        wechat: this.data.wechat,
        contactText: this.data.contactText,
        activeCategory: this.data.activeCategory
      })
    });
  },
  buildPayload() {
    const { user, name, description, bannerUrl, shareTitle, phone, wechat, contactText, selectedItems, activeTemplateId, activeCategory, activeGenerationMethod, displayLayout, notes } = this.data;
    const template = getShowcaseTemplate(activeTemplateId);
    const normalizedName = String(name || "").trim() || defaultName(activeCategory, template);
    const normalizedDescription = String(description || "").trim() || defaultDescription(activeCategory, template);
    const normalizedShareTitle = String(shareTitle || "").trim() || normalizedName;
    const normalizedContactText = String(contactText || "").trim() || defaultContactText(activeCategory);
    return {
      ownerUserId: user.id,
      name: normalizedName,
      description: normalizedDescription,
      bannerUrl,
      shareTitle: normalizedShareTitle,
      templateId: activeTemplateId,
      contactConfig: {
        phone,
        wechat,
        contactText: normalizedContactText,
        ownerName: firstOwnerName(notes, selectedItems, user),
        avatarUrl: firstAvatar(notes, selectedItems, user),
        showPhone: Boolean(phone),
        showWechat: Boolean(wechat)
      },
      displayConfig: {
        groupBy: DEFAULT_GROUP_BY,
        activeCategory,
        generationMethod: activeGenerationMethod,
        layoutMode: displayLayout === "grid" ? "grid" : "list",
        sourceTopicId: this.data.preselectTopicId || "",
        sourceTopicName: this.data.preselectTopicName || "",
        showTags: true,
        showSearch: false,
        primaryColor: "#1677ff"
      },
      items: selectedItems
    };
  },
  inferCategoryFromSelection(notes, selectedItems, options) {
    const selectedIds = new Set((selectedItems || []).map((item) => item.noteId));
    const selectedNotes = notes.filter((note) => selectedIds.has(note.id));
    const counts = {};
    selectedNotes.forEach((note) => {
      (note.categoryLabels || []).forEach((label) => {
        counts[label] = (counts[label] || 0) + 1;
      });
    });
    const best = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];
    return best || inferDefaultCategory(options);
  },
  resolveLoadedCategory(savedCategory, options, notes, selectedItems) {
    if (savedCategory && options.some((item) => item.value === savedCategory)) return savedCategory;
    return this.inferCategoryFromSelection(notes, selectedItems, options);
  },
  async saveDraft() {
    const { id } = this.data;
    const payload = this.buildPayload();
    this.setData({ saving: true });
    try {
      const res = id ? await api.updateShowcase(id, payload) : await api.createShowcase(payload);
      const page = res.data || {};
      this.setData({ id: page.id, status: page.status || "draft" });
      wx.showToast({ title: "已保存", icon: "success" });
      return page;
    } catch (error) {
      wx.showToast({ title: error.detail || "保存失败", icon: "none" });
      throw error;
    } finally {
      this.setData({ saving: false });
    }
  },
  async handleSave() {
    await this.saveDraft();
  },
  async handlePublish() {
    try {
      const warnings = (this.data.publishChecks || []).filter((item) => !item.ok);
      if (warnings.length) {
        const confirm = await new Promise((resolve) => {
          wx.showModal({
            title: this.data.sceneTexts.publishModalTitle,
            content: warnings.slice(0, 3).map((item) => item.fix).join("\n"),
            confirmText: this.data.sceneTexts.isGroupbuy ? "继续发群" : "继续发布",
            cancelText: "先完善",
            confirmColor: "#1677ff",
            success: (res) => resolve(Boolean(res.confirm)),
            fail: () => resolve(false)
          });
        });
        if (!confirm) return;
      }
      const page = await this.saveDraft();
      const res = await api.publishShowcase(page.id, this.data.user.id);
      this.setData({ status: res.data.status || "published", unpublishedChanges: false });
      clearShowcaseCaches(this.data.user && this.data.user.id);
      wx.showToast({ title: "已发布", icon: "success" });
    } catch (error) {
      if (!error.detail) return;
    }
  },
  async handleArchive() {
    const { id, user } = this.data;
    if (!id) return;
    try {
      const res = await api.archiveShowcase(id, user.id);
      this.setData({ status: res.data.status || "archived", unpublishedChanges: false });
      wx.showToast({ title: "已下架", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "下架失败", icon: "none" });
    }
  },
  handleDelete() {
    const { id, user } = this.data;
    if (!id || !user) return;
    wx.showModal({
      title: "删除展示页",
      content: "删除后客户将无法再打开这个展示页，确认删除吗？",
      confirmColor: "#e5484d",
      success: async ({ confirm }) => {
        if (!confirm) return;
        try {
          await api.deleteShowcase(id, user.id);
          wx.showToast({ title: "已删除", icon: "success" });
          setTimeout(() => wx.navigateBack(), 350);
        } catch (error) {
          wx.showToast({ title: error.detail || "删除失败", icon: "none" });
        }
      }
    });
  },
  async handlePreview() {
    try {
      const page = await this.saveDraft();
      wx.navigateTo({ url: `/pages/showcase-view/index?id=${page.id}&preview=1` });
    } catch (error) {
      if (!error.detail) return;
    }
  },
  onShareAppMessage() {
    const { id, user, status, unpublishedChanges } = this.data;
    if (!id || status !== "published" || unpublishedChanges) {
      wx.showToast({ title: unpublishedChanges ? "先发布新版再分享" : (this.data.sceneTexts.isGroupbuy ? "发布后才能发群" : "发布后才能发给客户"), icon: "none" });
      return {
        title: this.data.name || "资料展示页",
        path: "/pages/showcases/index"
      };
    }
    const shareId = createShareId(id);
    api.recordShowcaseEvent(id, {
      eventType: "share",
      shareId,
      shareFromUserId: user ? user.id : "",
      scene: "showcase_edit_share",
      referrer: "showcase-edit"
    }).catch(() => {});
    return {
      title: this.data.shareTitle || this.data.name || "资料展示页",
      path: `/pages/showcases/index?shareTarget=showcase&showcaseId=${id}&sid=${shareId}&from=${user ? user.id : ""}&src=showcase_edit_share`,
      imageUrl: ""
    };
  }
});
