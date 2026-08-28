const SHOWCASE_TEMPLATES = [
  {
    id: "featured_window",
    name: "精选橱窗",
    subtitle: "适合日常发客户，主打精选、品质和快速联系。",
    badge: "精选",
    groupBy: "none",
    tone: "green",
    previewImage: "/static/showcase/featured-window.jpg"
  },
  {
    id: "moments_story",
    name: "朋友圈长页",
    subtitle: "像一篇漂亮分享页，适合讲合集故事、发朋友圈或客户群。",
    badge: "长页",
    groupBy: "custom",
    tone: "warm",
    previewImage: "/static/showcase/moments-story.jpg"
  },
  {
    id: "catalog_list",
    name: "清单目录",
    subtitle: "适合资料很多时筛选、对比、快速点详情。",
    badge: "目录",
    groupBy: "tag",
    tone: "blue",
    previewImage: "/static/showcase/catalog-list.jpg"
  },
  {
    id: "brand_card",
    name: "品牌名片",
    subtitle: "强调人和信任，适合中介、顾问、团长建立专业感。",
    badge: "名片",
    groupBy: "cardType",
    tone: "teal",
    previewImage: "/static/showcase/brand-card.jpg"
  }
];

const TEMPLATE_SCENE_MAP = {
  property: ["featured_window", "catalog_list"],
  groupbuy: ["moments_story", "catalog_list", "featured_window"],
  service: ["moments_story", "catalog_list", "featured_window"],
  notes: ["catalog_list", "moments_story", "featured_window"],
  business_card: ["brand_card"],
  mixed: ["catalog_list", "moments_story", "featured_window"]
};
const TEMPLATE_SCENE_ALIASES = { property_batch_collection: "featured_window" };

function normalizeSceneType(value) {
  const key = String(value || "").trim().toLowerCase();
  if (["property", "房源", "房产", "property_listing", "property_batch_collection"].includes(key)) return "property";
  if (["groupbuy", "商品", "团购", "groupbuy_product"].includes(key)) return "groupbuy";
  if (["service", "服务", "案例", "service_offer"].includes(key)) return "service";
  if (["business_card", "电子名片", "名片"].includes(key)) return "business_card";
  if (key === "mixed") return "mixed";
  return "notes";
}

function getTemplatesForScene(sceneType) {
  const ids = TEMPLATE_SCENE_MAP[normalizeSceneType(sceneType)] || TEMPLATE_SCENE_MAP.notes;
  return ids.map((id) => SHOWCASE_TEMPLATES.find((item) => item.id === id)).filter(Boolean);
}

function getDefaultTemplateId(sceneType) {
  return (TEMPLATE_SCENE_MAP[normalizeSceneType(sceneType)] || TEMPLATE_SCENE_MAP.notes)[0];
}

function normalizeTemplateId(sceneType, templateId) {
  const candidate = TEMPLATE_SCENE_ALIASES[String(templateId || "").trim()] || String(templateId || "").trim();
  const allowed = TEMPLATE_SCENE_MAP[normalizeSceneType(sceneType)] || TEMPLATE_SCENE_MAP.notes;
  return allowed.includes(candidate) ? candidate : allowed[0];
}

function getShowcaseTemplate(templateId) {
  const normalized = TEMPLATE_SCENE_ALIASES[String(templateId || "").trim()] || templateId;
  return SHOWCASE_TEMPLATES.find((item) => item.id === normalized) || SHOWCASE_TEMPLATES[0];
}

function templateClass(templateId) {
  return `tpl-${getShowcaseTemplate(templateId).id}`;
}

module.exports = {
  SHOWCASE_TEMPLATES,
  TEMPLATE_SCENE_MAP,
  normalizeSceneType,
  getTemplatesForScene,
  getDefaultTemplateId,
  normalizeTemplateId,
  getShowcaseTemplate,
  templateClass
};
