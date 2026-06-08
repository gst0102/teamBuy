function getCurrentUser() {
  return getApp().globalData.currentUser || wx.getStorageSync("currentUser");
}

function normalizeStats(stats = {}) {
  return {
    pv: Number(stats.pv || 0),
    uv: Number(stats.uv || 0),
    anonymousPv: Number(stats.anonymousPv || 0),
    anonymousUv: Number(stats.anonymousUv || 0),
    relayCount: Number(stats.relayCount || 0),
    loggedInViewers: stats.loggedInViewers || [],
    relayEntries: stats.relayEntries || []
  };
}

function withStats(card = {}) {
  return {
    ...card,
    stats: normalizeStats(card.stats || {})
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

function inferCategory(card = {}) {
  const text = `${card.title || ""} ${card.projectName || ""} ${card.detailText || ""}`.toLowerCase();
  if (text.includes("房") || text.includes("小区") || text.includes("花园")) return "房源";
  if (text.includes("团") || text.includes("水果") || text.includes("接龙")) return "团购";
  if (text.includes("视频")) return "视频";
  if (text.includes("合同") || text.includes("pdf") || text.includes("文档")) return "文档";
  return "资料";
}

function buildDashboard(cards = []) {
  const normalized = cards.map(withStats);
  const totalPv = normalized.reduce((sum, card) => sum + card.stats.pv, 0);
  const totalUv = normalized.reduce((sum, card) => sum + card.stats.uv, 0);
  const totalRelay = normalized.reduce((sum, card) => sum + card.stats.relayCount, 0);
  const viewers = [];
  normalized.forEach((card) => {
    card.stats.loggedInViewers.forEach((viewer) => {
      if (!viewer || !viewer.nickname) return;
      viewers.push({
        ...viewer,
        cardId: card.id,
        cardTitle: card.title,
        timeText: formatTime(viewer.viewedAt),
        actionText: `${viewer.nickname}查看了${card.title || "资源页"}`
      });
    });
  });
  viewers.sort((a, b) => new Date(b.viewedAt || 0) - new Date(a.viewedAt || 0));
  const hotResources = [...normalized].sort((a, b) => b.stats.pv - a.stats.pv).slice(0, 4);
  return {
    cards: normalized,
    totalResources: normalized.length,
    totalPv,
    totalUv,
    totalRelay,
    viewers: viewers.slice(0, 6),
    hotResources
  };
}

function buildVisitGroups(cards = []) {
  return cards.map(withStats).map((card) => {
    const viewers = card.stats.loggedInViewers.slice(0, 3).map((viewer, index) => ({
      ...viewer,
      timeText: formatTime(viewer.viewedAt),
      actionLabel: index === 0 ? "刚刚访问了详情页" : index === 1 ? "重复查看了资源页" : "对该资源感兴趣"
    }));
    const highIntent = card.stats.pv >= 3 || card.stats.relayCount > 0 || card.stats.loggedInViewers.length >= 2;
    return {
      ...card,
      categoryName: inferCategory(card),
      viewers,
      highIntent,
      collectHint: card.stats.relayCount,
      visitSummary: `访问 ${card.stats.pv} · 访客 ${card.stats.uv}`
    };
  }).sort((a, b) => b.stats.pv - a.stats.pv);
}

module.exports = {
  buildDashboard,
  buildVisitGroups,
  formatTime,
  getCurrentUser,
  inferCategory,
  withStats
};
