const { buildTitleCoverData } = require("./title-cover");

const DEFAULT_NICKNAMES = [
  "硬核生意人",
  "实战派生意人",
  "精明生意人",
  "靠谱生意人",
  "有胆生意人",
  "敏锐生意人",
  "老辣生意人",
  "进取生意人",
  "灵活生意人",
  "果断生意人"
];

function getRandomDefaultNickname() {
  return DEFAULT_NICKNAMES[Math.floor(Math.random() * DEFAULT_NICKNAMES.length)];
}

function getCurrentUser() {
  return getApp().globalData.currentUser || wx.getStorageSync("currentUser");
}

function safeAvatarUrl(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (!/^https:\/\//i.test(text)) return "";
  if (/example\.com/i.test(text)) return "";
  if (/avatar-default/i.test(text)) return "";
  if (/^(wxfile|file|blob):/i.test(text)) return "";
  if (/^\/tmp\//i.test(text)) return "";
  return text;
}

function avatarText(value, fallback = "客") {
  const text = String(value || fallback).trim();
  return text.slice(0, 1);
}

function normalizeStats(stats = {}) {
  return {
    pv: Number(stats.pv || 0),
    uv: Number(stats.uv || 0),
    anonymousPv: Number(stats.anonymousPv || 0),
    anonymousUv: Number(stats.anonymousUv || 0),
    relayCount: Number(stats.relayCount || 0),
    shareCount: Number(stats.shareCount || 0),
    latestShareAt: stats.latestShareAt || "",
    topShareId: stats.topShareId || "",
    loggedInViewers: stats.loggedInViewers || [],
    relayEntries: stats.relayEntries || []
  };
}

function normalizeCustomerSummary(summary = {}) {
  return {
    total: Number(summary.total || 0),
    leadContact: Number(summary.leadContact || 0),
    appointment: Number(summary.appointment || 0),
    orderIntent: Number(summary.orderIntent || 0),
    relayIntent: Number(summary.relayIntent || 0),
    consult: Number(summary.consult || 0),
    leads: Number(summary.leads || 0),
    pending: Number(summary.pending || 0),
    hasUnread: Boolean(summary.hasUnread),
    latestActionAt: summary.latestActionAt || ""
  };
}

function withStats(card = {}) {
  const customerSummary = normalizeCustomerSummary(card.customerSummary || {});
  const stats = normalizeStats(card.stats || {});
  const customerActivity =
    customerSummary.total ||
    customerSummary.leads ||
    customerSummary.pending ||
    stats.relayCount ||
    0;
  return {
    ...card,
    stats,
    customerSummary,
    customerActivity,
    hasCustomerSignal: stats.pv > 0 || stats.uv > 0 || customerActivity > 0,
    hasHotCustomerSignal: Boolean(customerSummary.hasUnread || customerSummary.pending > 0)
  };
}

function formatTime(value) {
  if (!value) return "刚刚";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diff = Date.now() - date.getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diff < minute) return "刚刚";
  if (diff < hour) return `${Math.max(1, Math.floor(diff / minute))}分钟前`;
  if (diff < day) return `${Math.floor(diff / hour)}小时前`;
  return `${date.getMonth() + 1}-${date.getDate()}`;
}

function statusText(value) {
  if (value === "followed") return "已跟进";
  if (value === "pending") return "待跟进";
  if (value === "deleted") return "已删除";
  if (value === "published") return "已发布";
  if (value === "draft") return "草稿";
  return value || "未知";
}

function inferCategory(card = {}) {
  const text = `${card.title || ""} ${card.projectName || ""} ${card.detailText || ""}`.toLowerCase();
  if (text.includes("房") || text.includes("小区") || text.includes("花园")) return "房源";
  if (text.includes("团") || text.includes("水果") || text.includes("接龙")) return "团购";
  if (text.includes("视频")) return "视频";
  if (text.includes("合同") || text.includes("pdf") || text.includes("文档")) return "文档";
  return "资料";
}

function resolveCustomTags(card = {}, categoriesById = {}) {
  const config = card.visibilityConfig || {};
  const categoryTags = (card.categoryIds || []).map((id) => categoriesById[id]).filter(Boolean);
  const configTags = [
    ...(Array.isArray(config.userTags) ? config.userTags : []),
    ...(Array.isArray(config.systemTags) ? config.systemTags : []),
    ...(Array.isArray(config.tags) ? config.tags : [])
  ];
  return [...new Set([...categoryTags, ...configTags].map((item) => String(item || "").trim()).filter(Boolean))];
}

function normalizePropertyValue(value, label) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.startsWith(label) ? text : `${label} ${text}`;
}

function normalizeProductValue(value, label) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.startsWith(label) ? text : `${label} ${text}`;
}

function productPriceText(data = {}) {
  const skuConfig = data.skuConfig && typeof data.skuConfig === "object" ? data.skuConfig : {};
  const prices = (Array.isArray(skuConfig.skus) ? skuConfig.skus : [])
    .filter((sku) => sku && !sku.soldOut && sku.price)
    .map((sku) => String(sku.price || "").trim())
    .filter(Boolean);
  const unique = Array.from(new Set(prices));
  if (unique.length === 1) return unique[0];
  if (unique.length > 1) return `${unique[0]} - ${unique[unique.length - 1]}`;
  return data.price || "";
}

function inferPropertyPrice(text) {
  const value = String(text || "");
  const labeled = value.match(/(?:租金|价格|房租)[：:\s]*([0-9]{3,6}\s*(?:元|块)?(?:\/月|每月|月)?)/);
  if (labeled) return labeled[1].replace(/\s+/g, "");
  const unit = value.match(/(^|[^0-9A-Za-z-])([1-9]\d{2,5})\s*(?:元|块|\/月|每月|月租|月)($|[^0-9A-Za-z-])/);
  if (unit) return unit[2];
  const plain = value.match(/(^|[^0-9A-Za-z-])([1-9]\d{3,5})($|[^0-9A-Za-z-])/);
  return plain ? plain[2] : "";
}

function inferPropertyLayout(text) {
  const value = String(text || "");
  const labeled = value.match(/户型[：:\s]*([^，,。；;\s·|]+)/);
  if (labeled) return labeled[1];
  const layout = value.match(/(公寓一房|公寓|一房一厅|一室一厅|一室一卫|一房|一室|两房一厅|两室一厅|两室两厅|二房一厅|二室一厅|三房两厅|三室两厅|三房一厅|三室一厅|四房两厅|四室两厅)/);
  return layout ? layout[1] : "";
}

function buildPropertyTextSource(card = {}, structuredData = {}) {
  return [
    structuredData.price,
    structuredData.layout,
    structuredData.area,
    structuredData.floor,
    structuredData.businessArea,
    structuredData.address,
    structuredData.paymentMethod,
    structuredData.moveInTime,
    structuredData.remark,
    card.detailText,
    card.summary,
    card.body,
    card.title,
    card.projectName
  ].filter(Boolean).join(" ");
}

function enrichCard(card = {}, categoriesById = {}) {
  const normalized = withStats(card);
  const customTagNames = resolveCustomTags(normalized, categoriesById);
  const categoryName = inferCategory(normalized);
  const config = normalized.visibilityConfig || {};
  const structuredData = config.structuredData || {};
  const propertyTextSource = buildPropertyTextSource(normalized, structuredData);
  const propertyPrice = structuredData.price || normalized.price || inferPropertyPrice(propertyTextSource);
  const propertyLayout = structuredData.layout || normalized.layout || inferPropertyLayout(propertyTextSource);
  const cardType = normalized.cardType || config.cardType || "";
  const isProperty = cardType === "property_listing" || categoryName === "房源";
  const isGroupbuy = cardType === "groupbuy_product" || categoryName === "团购";
  const customerSummary = normalized.customerSummary || {};
  const customerLabel = customerSummary.pending
    ? `待跟进 ${customerSummary.pending}`
    : customerSummary.appointment
      ? `预约 ${customerSummary.appointment}`
      : customerSummary.leadContact
        ? `留言 ${customerSummary.leadContact}`
        : customerSummary.orderIntent || customerSummary.relayIntent || normalized.stats.relayCount
          ? `接龙 ${customerSummary.orderIntent || customerSummary.relayIntent || normalized.stats.relayCount}`
          : normalized.stats.uv
            ? `访客 ${normalized.stats.uv}`
            : "暂无客户";
  const propertyInfoLine = [
    structuredData.businessArea || structuredData.address,
    structuredData.moveInTime,
    normalized.importBatchId ? "客服导入" : ""
  ].filter(Boolean).join(" · ");
  const propertyHighlightChips = [
    propertyPrice ? normalizePropertyValue(propertyPrice, "租金") : "租金待补",
    propertyLayout ? normalizePropertyValue(propertyLayout, "户型") : "户型待补",
    structuredData.area ? normalizePropertyValue(structuredData.area, "面积") : "",
    structuredData.paymentMethod || ""
  ].filter(Boolean);
  const propertyCustomerChips = [
    customerSummary.appointment ? `预约 ${customerSummary.appointment}` : "",
    customerSummary.leadContact ? `留言 ${customerSummary.leadContact}` : "",
    customerSummary.consult ? `咨询 ${customerSummary.consult}` : "",
    customerSummary.pending ? `待跟进 ${customerSummary.pending}` : "",
    !customerSummary.appointment && !customerSummary.leadContact && !customerSummary.consult && !customerSummary.pending && normalized.stats.uv ? `访客 ${normalized.stats.uv}` : ""
  ].filter(Boolean).slice(0, 3);
  const propertyPrimaryAction = normalized.hasCustomerSignal || propertyCustomerChips.length ? "看客户" : "分享";
  const propertyFollowStatus = customerSummary.pending || normalized.hasHotCustomerSignal
    ? { text: "待处理", tone: "hot", hint: "优先看客户" }
    : customerSummary.leads || customerSummary.leadContact || customerSummary.appointment || customerSummary.consult
      ? { text: "已跟进", tone: "done", hint: "继续观察" }
      : normalized.stats.uv || normalized.stats.pv
        ? { text: "有浏览", tone: "view", hint: "可再发客户" }
        : { text: "待分享", tone: "idle", hint: "先发给客户" };
  const hasRelayOrders = !!(customerSummary.relayIntent || normalized.stats.relayCount);
  const productOrderCount = customerSummary.orderIntent || customerSummary.relayIntent || normalized.stats.relayCount || 0;
  const productPendingCount = customerSummary.pending || (normalized.hasHotCustomerSignal ? productOrderCount : 0);
  const productPrice = productPriceText(structuredData);
  const productHighlightChips = [
    productPrice ? normalizeProductValue(productPrice, "价格") : "价格待补",
    structuredData.spec ? normalizeProductValue(structuredData.spec, "规格") : "",
    structuredData.pickupMethod || "",
    structuredData.deadline ? normalizeProductValue(structuredData.deadline, "截止") : ""
  ].filter(Boolean);
  const productInfoLine = [
    structuredData.pickupLocation,
    structuredData.remark,
    normalized.importBatchId ? "客服导入" : ""
  ].filter(Boolean).join(" · ");
  const productCustomerChips = [
    productPendingCount ? `待处理 ${productPendingCount}` : "",
    customerSummary.relayIntent ? `接龙 ${customerSummary.relayIntent}` : "",
    customerSummary.orderIntent && !customerSummary.relayIntent ? `下单 ${customerSummary.orderIntent}` : "",
    customerSummary.consult ? `咨询 ${customerSummary.consult}` : "",
    !productOrderCount && normalized.stats.uv ? `访客 ${normalized.stats.uv}` : ""
  ].filter(Boolean).slice(0, 3);
  const productFollowStatus = productPendingCount
    ? { text: "待处理", tone: "hot", hint: "先处理名单" }
    : productOrderCount
      ? { text: customerSummary.relayIntent ? "有接龙" : "有下单", tone: "done", hint: "继续发群" }
      : normalized.stats.uv || normalized.stats.pv
        ? { text: "有访客", tone: "view", hint: "可再催单" }
        : { text: "待发布", tone: "idle", hint: "先发到群" };
  const viewCount = normalized.stats.pv || 0;
  const visitorCount = normalized.stats.uv || 0;
  const shareCount = normalized.stats.shareCount || 0;
  const followupCount = customerSummary.pending || customerSummary.leadContact || customerSummary.appointment || customerSummary.consult || customerSummary.orderIntent || customerSummary.relayIntent || normalized.stats.relayCount || 0;
  const deliveryStatus = followupCount || normalized.hasHotCustomerSignal
    ? {
      text: followupCount ? `建议跟进 ${followupCount}` : "建议跟进",
      tone: "hot",
      hint: "客户有动作，去雷达看原因"
    }
    : visitorCount
      ? {
        text: visitorCount > 1 || viewCount > 2 ? "客户重复查看" : "客户已打开",
        tone: visitorCount > 1 || viewCount > 2 ? "warm" : "view",
        hint: visitorCount > 1 || viewCount > 2 ? "适合补一句对比或优惠" : "可以观察是否继续浏览"
      }
      : viewCount
        ? {
          text: "已有打开",
          tone: "view",
          hint: "有浏览记录，继续观察"
        }
        : shareCount
          ? {
            text: "已发出，等待打开",
            tone: "sent",
            hint: "客户打开后会进入雷达"
          }
        : {
          text: "待发送",
          tone: "idle",
          hint: "点发客户后，客户反馈会进雷达"
        };
  const checkIssues = [];
  const bodyText = [
    normalized.title,
    normalized.detailText,
    normalized.summary,
    normalized.body,
    structuredData.price,
    structuredData.layout,
    structuredData.address,
    structuredData.contactPhone,
    structuredData.contactWechat
  ].filter(Boolean).join(" ");
  if (!/电话|微信|联系|咨询|预约|1\d{10}/.test(bodyText)) {
    checkIssues.push("缺联系方式");
  }
  if ((isProperty || isGroupbuy || cardType === "service_offer") && !/价格|租金|报价|费用|优惠|元|¥|￥|\d/.test(bodyText)) {
    checkIssues.push("价格不清");
  }
  if (!normalized.coverUrl && !normalized.imageUrl && !(normalized.mediaUrls || []).length) {
    checkIssues.push("缺图片");
  }
  if (String(normalized.title || "").length < 6) {
    checkIssues.push("标题偏短");
  }
  const salesCheck = checkIssues.length
    ? {
      text: `发前体检：${checkIssues[0]}`,
      tone: "warn",
      hint: checkIssues.length > 1 ? `还有 ${checkIssues.length - 1} 项可补强` : "补一下再发更稳"
    }
    : {
      text: "发前体检通过",
      tone: "pass",
      hint: "可以直接发客户"
    };
  const materialStage = followupCount || normalized.hasHotCustomerSignal
    ? { text: "建议跟进", tone: "hot", hint: "客户有动作，先去雷达看原因" }
    : visitorCount || viewCount
      ? { text: "已打开", tone: "view", hint: "已有客户反馈，可继续观察" }
      : shareCount
        ? { text: "已发出", tone: "sent", hint: "等客户打开后进入雷达" }
        : checkIssues.length
          ? { text: "待补强", tone: "warn", hint: `先补${checkIssues[0]}` }
          : { text: "可发送", tone: "ready", hint: "可以直接发客户" };
  return {
    ...normalized,
    categoryName,
    isProperty,
    isGroupbuy,
    tagNames: customTagNames,
    sourceLabel: normalized.importBatchId ? "客服接收" : "手动添加",
    createdText: normalized.createdAt ? `创建于 ${formatTime(normalized.createdAt)}` : "",
    customerLabel,
    customerHint: normalized.hasCustomerSignal ? "来客户了" : "发出去后这里看反馈",
    propertyInfoLine: propertyInfoLine || normalized.detailText || normalized.summary || "",
    propertyHighlightChips,
    propertyCustomerChips,
    propertyPrimaryAction,
    propertyFollowStatus,
    titleCover: buildTitleCoverData(normalized.title || normalized.projectName || normalized.summary || "", categoryName || "资料"),
    productInfoLine: productInfoLine || normalized.detailText || normalized.summary || "",
    productHighlightChips,
    productCustomerChips,
    productHasOrders: !!productOrderCount,
    productPrimaryAction: productOrderCount
      ? (hasRelayOrders ? "处理接龙" : "处理订单")
      : "分享",
    productFollowStatus,
    deliveryStatus,
    salesCheck,
    materialStage
  };
}

function buildDashboard(cards = []) {
  const normalized = cards.map(enrichCard);
  const totalPv = normalized.reduce((sum, card) => sum + card.stats.pv, 0);
  const totalUv = normalized.reduce((sum, card) => sum + card.stats.uv, 0);
  const totalRelay = normalized.reduce((sum, card) => sum + card.stats.relayCount, 0);
  const totalCustomerActivity = normalized.reduce((sum, card) => sum + (card.customerActivity || 0), 0);
  const viewers = [];
  normalized.forEach((card) => {
    card.stats.loggedInViewers.forEach((viewer) => {
      if (!viewer || !viewer.nickname) return;
      viewers.push({
        ...viewer,
        avatarUrl: safeAvatarUrl(viewer.avatarUrl),
        avatarText: avatarText(viewer.nickname),
        cardId: card.id,
        cardTitle: card.title,
        timeText: formatTime(viewer.viewedAt),
        actionText: `${viewer.nickname}查看了${card.title || "资源页"}`
      });
    });
  });
  viewers.sort((a, b) => new Date(b.viewedAt || 0) - new Date(a.viewedAt || 0));
  const hotResources = [...normalized]
    .sort((a, b) => {
      const signalDiff = Number(b.hasHotCustomerSignal) - Number(a.hasHotCustomerSignal);
      if (signalDiff) return signalDiff;
      const activityDiff = (b.customerActivity || 0) - (a.customerActivity || 0);
      if (activityDiff) return activityDiff;
      return b.stats.pv - a.stats.pv;
    })
    .slice(0, 4);
  const customerAlerts = hotResources
    .filter((card) => card.hasCustomerSignal)
    .slice(0, 3)
    .map((card) => ({
      id: card.id,
      title: card.title || card.projectName || "资料",
      label: card.customerLabel,
      desc: `打开 ${card.stats.pv} · 访客 ${card.stats.uv}`,
      hot: card.hasHotCustomerSignal
    }));
  return {
    cards: normalized,
    totalResources: normalized.length,
    totalPv,
    totalUv,
    totalRelay,
    totalCustomerActivity,
    customerAlerts,
    viewers: viewers.slice(0, 6),
    hotResources
  };
}

function buildVisitGroups(cards = []) {
  return cards
    .map(enrichCard)
    .map((card) => {
      const viewers = card.stats.loggedInViewers.slice(0, 3).map((viewer, index) => ({
        ...viewer,
        avatarUrl: safeAvatarUrl(viewer.avatarUrl),
        avatarText: avatarText(viewer.nickname),
        timeText: formatTime(viewer.viewedAt),
        actionLabel:
          index === 0 ? "刚刚访问了详情页" : index === 1 ? "重复查看了资源页" : "对该资源感兴趣"
      }));
      const highIntent = card.stats.pv >= 3 || card.stats.relayCount > 0 || card.stats.loggedInViewers.length >= 2;
      return {
        ...card,
        viewers,
        highIntent,
        collectHint: card.stats.relayCount,
        visitSummary: `访问 ${card.stats.pv} · 访客 ${card.stats.uv}`
      };
    })
    .sort((a, b) => b.stats.pv - a.stats.pv);
}

module.exports = {
  buildDashboard,
  buildVisitGroups,
  formatTime,
  statusText,
  getCurrentUser,
  getRandomDefaultNickname,
  safeAvatarUrl,
  avatarText,
  enrichCard,
  inferCategory,
  withStats,
  normalizeCustomerSummary
};
