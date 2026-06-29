const WORKSPACE_STORAGE_KEY = "teambuy:workspaceMode";
const PROPERTY_GROWTH_MODE_ENABLED = false;
const DEFAULT_WORKSPACE_MODE = "property";

const WORKSPACE_MODES = [
  {
    key: "notes",
    name: "日常资料场景",
    shortName: "日常资料",
    title: "日常资料场景",
    badge: "日常资料",
    icon: "资料",
    heroImage: "/static/workspace/workspace-notes.webp",
    desc: "保存笔记、图片、链接，整理成日常合集。",
    fit: "备忘、文章、聊天资料、图片和日常记录。",
    tone: "blue",
    feedbackName: "分享效果",
    feedbackDesc: "查看日常合集、分享页和单条资料的打开情况。",
    workbenchTitle: "分享效果中心",
    workbenchSubtitle: "日常资料只看分享效果和日常合集反馈，不展示业务后台词。",
    stats: ["资料", "打开", "访客", "动态"],
    pending: ["新导入资料", "待整理图片", "最近笔记", "未完成日常合集"],
    quickActions: [
      { key: "write_note", label: "写笔记", desc: "随手记录", icon: "笔记", action: "capture" },
      { key: "save_image", label: "存图片", desc: "图片放进笔记", icon: "图片", action: "captureImage" },
      { key: "save_link", label: "存链接", desc: "链接放进笔记", icon: "链接", action: "captureLink" },
      { key: "collection", label: "日常合集", desc: "打包资料分享", icon: "资料", action: "showcases" }
    ],
    workbenchActions: [
      { key: "showcases", label: "日常合集效果", desc: "查看合集和分享页", icon: "包", action: "showcases" },
      { key: "notes", label: "最近资料", desc: "查看单条资料", icon: "资", action: "library" },
      { key: "share", label: "分享记录", desc: "复用展示页反馈", icon: "享", action: "dashboard" }
    ]
  },
  {
    key: "property",
    name: "房源场景",
    shortName: "房源",
    title: "房源场景",
    badge: "资料整理助手 · 房源版",
    icon: "房源",
    heroImage: "/static/workspace/workspace-property.webp",
    desc: "群里房源发给助手，自动变成你的房源卡和合集。",
    fit: "租房中介、二房东、对盘群房源流通。",
    tone: "green",
    feedbackName: "客户看板",
    feedbackDesc: "查看房源浏览、留言、咨询和预约看房。",
    workbenchTitle: "房源反馈中心",
    workbenchSubtitle: "集中查看看房客户、房源效果和待跟进事项。",
    overviewTitle: "今日概览",
    overviewSubtitle: "今天新房源、同行浏览和待跟进一眼看清",
    stats: ["房源", "打开", "访客", "待跟进"],
    pending: ["添加房源助手", "转发群房源", "整理房源合集", "看同行/客户反馈"],
    quickActions: [
      { key: "wecom_assistant", label: "添加房源助手", desc: "转发群消息生成房源", icon: "微信", iconImage: "/static/icons/wechat.svg", action: "openAssistant" },
      { key: "same", label: "生成同款", desc: "换成我的微信", icon: "同款", action: "generateSame" },
      { key: "collection", label: "房源合集", desc: "对盘群清单", icon: "合集", action: "showcases" },
      { key: "feedback", label: "客户反馈", desc: "看谁要跟进", icon: "反馈", action: "dashboard" }
    ],
    workbenchActions: [
      { key: "dashboard", label: "客户看板", desc: "待跟进和访客", icon: "看", action: "dashboard" },
      { key: "leads", label: "待跟进客户", desc: "留言和预约", icon: "联", action: "leads" },
      { key: "showcases", label: "推荐包效果", desc: "多套房源一起发", icon: "包", action: "showcases" }
    ]
  },
  {
    key: "groupbuy",
    name: "团购/商品场景",
    shortName: "团购",
    title: "团购/商品场景",
    badge: "团购/商品",
    icon: "团购",
    heroImage: "/static/workspace/workspace-groupbuy.webp",
    desc: "整理商品，发到群里，管理接龙和买家反馈。",
    fit: "团长、商品接龙、小区团购。",
    tone: "orange",
    feedbackName: "接龙看板",
    feedbackDesc: "查看商品浏览、接龙、买家和待处理订单。",
    workbenchTitle: "团购反馈中心",
    workbenchSubtitle: "集中查看接龙名单、买家记录和商品效果。",
    overviewTitle: "今日待处理",
    overviewSubtitle: "先看待处理接龙、今日新增和订单记录",
    stats: ["商品", "待处理", "今日接龙", "订单"],
    pending: ["待发布商品", "待处理接龙", "今日接龙", "待联系买家"],
    quickActions: [
      { key: "new_product", label: "新建商品", desc: "粘贴团购文案", icon: "商品", action: "captureGroupbuy" },
      { key: "material_note", label: "记素材", desc: "记录团购素材", icon: "素材", action: "captureGroupbuyMaterial" },
      { key: "collection", label: "商品合集", desc: "多个商品一起发", icon: "合集", action: "showcases" },
      { key: "relay", label: "处理接龙", desc: "查看待处理名单", icon: "接龙", action: "orders" }
    ],
    workbenchActions: [
      { key: "orders", label: "接龙 / 买家", desc: "查看下单和接龙", icon: "单", action: "orders" },
      { key: "dashboard", label: "商品效果", desc: "浏览和咨询反馈", icon: "效", action: "dashboard" },
      { key: "library", label: "商品资料", desc: "编辑和复用", icon: "品", action: "library" }
    ]
  },
  {
    key: "service",
    name: "服务/商机场景",
    shortName: "服务商机",
    title: "服务/商机场景",
    badge: "服务/商机",
    icon: "商机",
    heroImage: "/static/workspace/workspace-service.webp",
    desc: "制作名片、服务方案和商机合作页，记录咨询客户。",
    fit: "咨询、清关、保险、招商、批发合作和服务顾问。",
    tone: "teal",
    feedbackName: "咨询看板",
    feedbackDesc: "查看名片、服务方案、留言和预约沟通。",
    workbenchTitle: "服务反馈中心",
    workbenchSubtitle: "集中查看咨询客户、预约记录和服务页效果。",
    stats: ["名片", "打开", "访客", "咨询"],
    pending: ["待完善服务/商机页", "新咨询客户", "最近被查看方案", "待跟进合作"],
    quickActions: [
      { key: "business_card", label: "做名片", desc: "先给客户认识你", icon: "名片", action: "businessCard" },
      { key: "service_offer", label: "做方案", desc: "发服务介绍页", icon: "方案", action: "serviceOffer" },
      { key: "opportunity", label: "商机合作", desc: "保险/清关/招募", icon: "商机", action: "serviceOpportunity" },
      { key: "collection", label: "案例合集", desc: "组合案例资料", icon: "案例", action: "showcases" }
    ],
    workbenchActions: [
      { key: "dashboard", label: "咨询看板", desc: "客户互动总览", icon: "看", action: "dashboard" },
      { key: "leads", label: "预约记录", desc: "留言和预约", icon: "约", action: "leads" },
      { key: "offers", label: "服务方案", desc: "编辑和复用", icon: "案", action: "serviceOffer" }
    ]
  }
];

function getModeConfig(mode) {
  return WORKSPACE_MODES.find((item) => item.key === mode) || WORKSPACE_MODES.find((item) => item.key === DEFAULT_WORKSPACE_MODE) || WORKSPACE_MODES[0];
}

function storageKey(userId) {
  return userId ? `${WORKSPACE_STORAGE_KEY}:${userId}` : WORKSPACE_STORAGE_KEY;
}

function readWorkspaceMode(userId) {
  try {
    const value = wx.getStorageSync(storageKey(userId)) || wx.getStorageSync(WORKSPACE_STORAGE_KEY) || "";
    return WORKSPACE_MODES.some((item) => item.key === value) ? value : DEFAULT_WORKSPACE_MODE;
  } catch (error) {
    return DEFAULT_WORKSPACE_MODE;
  }
}

function saveWorkspaceMode(mode, userId) {
  const config = getModeConfig(mode);
  try {
    wx.setStorageSync(storageKey(userId), config.key);
    wx.setStorageSync(WORKSPACE_STORAGE_KEY, config.key);
  } catch (error) {
    // Local preference only; ignore storage failures.
  }
  return config;
}

function buildModeOptions(activeMode) {
  const modes = PROPERTY_GROWTH_MODE_ENABLED
    ? WORKSPACE_MODES.filter((item) => item.key === "property")
    : WORKSPACE_MODES;
  return modes.map((item) => ({
    ...item,
    active: item.key === activeMode,
    activeClass: item.key === activeMode ? "active" : ""
  }));
}

module.exports = {
  PROPERTY_GROWTH_MODE_ENABLED,
  WORKSPACE_MODES,
  buildModeOptions,
  getModeConfig,
  readWorkspaceMode,
  saveWorkspaceMode
};
