const SHOWCASE_TEMPLATES = [
  {
    id: "featured_window",
    name: "精选橱窗",
    subtitle: "适合日常发客户，主打精选、品质和快速联系。",
    badge: "精选",
    groupBy: "none",
    tone: "green",
    previewImage: "https://teambuy.lifelove.top/media/showcase-templates/featured-window.webp"
  },
  {
    id: "moments_story",
    name: "朋友圈长页",
    subtitle: "像一篇漂亮分享页，适合讲合集故事、发朋友圈或客户群。",
    badge: "长页",
    groupBy: "custom",
    tone: "warm",
    previewImage: "https://teambuy.lifelove.top/media/showcase-templates/moments-story.webp"
  },
  {
    id: "catalog_list",
    name: "清单目录",
    subtitle: "适合资料很多时筛选、对比、快速点详情。",
    badge: "目录",
    groupBy: "tag",
    tone: "blue",
    previewImage: "https://teambuy.lifelove.top/media/showcase-templates/catalog-list.webp"
  },
  {
    id: "brand_card",
    name: "品牌名片",
    subtitle: "强调人和信任，适合中介、顾问、团长建立专业感。",
    badge: "名片",
    groupBy: "cardType",
    tone: "teal",
    previewImage: "https://teambuy.lifelove.top/media/showcase-templates/brand-card.webp"
  }
];

function getShowcaseTemplate(templateId) {
  return SHOWCASE_TEMPLATES.find((item) => item.id === templateId) || SHOWCASE_TEMPLATES[0];
}

function templateClass(templateId) {
  return `tpl-${getShowcaseTemplate(templateId).id}`;
}

module.exports = {
  SHOWCASE_TEMPLATES,
  getShowcaseTemplate,
  templateClass
};
