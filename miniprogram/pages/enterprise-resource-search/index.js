const { getCurrentUser } = require("../../utils/dashboard");
const api = require("../../services/api");

const POINTS_KEY = "teambuy:groupResourceLibrary:points";
const RECENT_KEY = "teambuy:enterpriseResourceSearch:recent";
const CACHE_KEY = "teambuy:enterpriseResourceSearch:queryCache";
const SAVED_KEY = "teambuy:enterpriseResourceSearch:saved";
const NEW_USER_POINTS = 100;
const CACHE_TTL = 24 * 60 * 60 * 1000;

const hotKeywords = ["装修公司", "房产中介", "团长供应链", "老板资源", "清关代理"];
const tagOptions = ["装修", "长沙", "线索", "本地商家", "服务合作"];
const queryTools = [
  { key: "basic", label: "基本信息", cost: 5, icon: "基" },
  { key: "shareholders", label: "股东结构", cost: 5, icon: "股" },
  { key: "risk", label: "司法风险", cost: 5, icon: "险" },
  { key: "operations", label: "经营情况", cost: 5, icon: "营" },
  { key: "history", label: "历史变更", cost: 5, icon: "史" },
  { key: "ip", label: "知识产权", cost: 5, icon: "知" }
];

const pointRules = [
  { label: "搜索企业候选", value: "免费" },
  { label: "企业查询", value: "-5/项" },
  { label: "24 小时缓存", value: "不重复扣" },
  { label: "保存资源卡", value: "免费" }
];

const enterprises = [
  {
    id: "ent_001",
    shortName: "某某装饰",
    name: "湖南某某装饰工程有限公司",
    status: "存续",
    legalPerson: "李某某",
    capital: "500万元人民币",
    foundedAt: "2016-05-18",
    industry: "建筑装饰业",
    city: "湖南省长沙市",
    address: "湖南省长沙市岳麓区某某路88号",
    creditCode: "91430100MA4LXXXXXX",
    risk: "暂无重大风险"
  },
  {
    id: "ent_002",
    shortName: "星辉装饰",
    name: "长沙星辉装饰设计有限公司",
    status: "存续",
    legalPerson: "张某",
    capital: "300万元人民币",
    foundedAt: "2014-03-12",
    industry: "建筑装饰业",
    city: "湖南省长沙市",
    address: "湖南省长沙市雨花区韶山路168号",
    creditCode: "91430111MA4TXXXXXX",
    risk: "存在少量经营变更记录"
  },
  {
    id: "ent_003",
    shortName: "艺筑装饰",
    name: "湖南艺筑装饰工程有限公司",
    status: "存续",
    legalPerson: "王某某",
    capital: "1000万元人民币",
    foundedAt: "2018-09-28",
    industry: "建筑装饰业",
    city: "湖南省长沙市",
    address: "湖南省长沙市开福区芙蓉北路99号",
    creditCode: "91430105MA4QXXXXXX",
    risk: "暂无重大风险"
  }
];

function storageKey(base, userId) {
  return `${base}:${userId || "guest"}`;
}

function readNumber(key, fallback) {
  try {
    const value = wx.getStorageSync(key);
    if (value === "" || value === undefined || value === null) {
      wx.setStorageSync(key, fallback);
      return fallback;
    }
    return Number(value || 0);
  } catch (error) {
    return fallback;
  }
}

function readList(key) {
  try {
    const value = wx.getStorageSync(key);
    return Array.isArray(value) ? value : [];
  } catch (error) {
    return [];
  }
}

function readObject(key) {
  try {
    const value = wx.getStorageSync(key);
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch (error) {
    return {};
  }
}

function buildToolResult(enterprise, tool) {
  if (tool.key === "basic") {
    return `${enterprise.name} 当前状态为${enterprise.status}，法人${enterprise.legalPerson}，注册资本${enterprise.capital}。`;
  }
  if (tool.key === "shareholders") return "股东结构已查询：当前建议结合实控人、持股比例和历史变更一起判断。";
  if (tool.key === "risk") return `司法风险已查询：${enterprise.risk}。`;
  if (tool.key === "operations") return "经营情况已查询：建议重点看经营状态、行业、地址稳定性和异常记录。";
  if (tool.key === "history") return "历史变更已查询：建议关注法人、地址、经营范围和股东变更。";
  return "知识产权已查询：可用于判断品牌、商标和业务沉淀情况。";
}

function decorateTools(results = {}) {
  return queryTools.map((tool) => ({
    ...tool,
    displayCost: tool.cost > 0 ? `${tool.cost}分` : "免费",
    result: results[tool.key] || null
  }));
}

function buildTagChoices(selected = []) {
  return tagOptions.map((tag) => ({
    label: tag,
    selected: selected.includes(tag)
  }));
}

Page({
  data: {
    keyword: "",
    points: NEW_USER_POINTS,
    recentSearches: [],
    results: [],
    selected: null,
    activeView: "search",
    queryTools,
    displayTools: decorateTools(),
    queryResults: {},
    hasQueryResults: false,
    searched: false,
    rulesVisible: false,
    savedTags: tagOptions.slice(0, 3),
    tagChoices: buildTagChoices(tagOptions.slice(0, 3)),
    savedCards: [],
    hotKeywords,
    tagOptions,
    pointRules
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.userId = currentUser.id;
    this.pointsKey = storageKey(POINTS_KEY, this.userId);
    this.recentKey = storageKey(RECENT_KEY, this.userId);
    this.cacheKey = storageKey(CACHE_KEY, this.userId);
    this.savedKey = storageKey(SAVED_KEY, this.userId);
    this.setData({
      points: readNumber(this.pointsKey, NEW_USER_POINTS),
      recentSearches: readList(this.recentKey),
      savedCards: readList(this.savedKey)
    });
  },
  handleKeywordInput(event) {
    this.setData({ keyword: event.detail.value });
  },
  handleHotKeyword(event) {
    this.setData({ keyword: event.currentTarget.dataset.keyword || "" }, () => this.handleSearch());
  },
  async handleSearch() {
    const keyword = String(this.data.keyword || "").trim();
    const normalized = keyword.toLowerCase();
    let results = !keyword
      ? enterprises
      : enterprises.filter((item) => [item.name, item.shortName, item.creditCode, item.industry, item.city].join(" ").toLowerCase().includes(normalized));
    if (keyword) {
      try {
        const response = await api.searchEnterpriseResources({ keyword, pageSize: 10 });
        const data = response && response.data;
        if (data && data.configured && Array.isArray(data.items)) {
          results = data.items;
        } else if (data && data.configured === false) {
          wx.showToast({ title: "企业查询服务未配置", icon: "none" });
        } else if (data && data.message && data.message !== "ok") {
          wx.showToast({ title: data.message, icon: "none" });
        }
      } catch (error) {
        wx.showToast({ title: "企业查询暂时不可用", icon: "none" });
      }
    }
    const recentSearches = keyword
      ? [keyword, ...this.data.recentSearches.filter((item) => item !== keyword)].slice(0, 5)
      : this.data.recentSearches;
    wx.setStorageSync(this.recentKey, recentSearches);
    this.setData({ results, recentSearches, activeView: "search", searched: true });
  },
  handleRecentTap(event) {
    this.setData({ keyword: event.currentTarget.dataset.keyword || "" }, () => this.handleSearch());
  },
  handleClearRecent() {
    wx.setStorageSync(this.recentKey, []);
    this.setData({ recentSearches: [] });
  },
  handleOpenEnterprise(event) {
    const id = event.currentTarget.dataset.id;
    const selected = (this.data.results || []).find((item) => String(item.id) === String(id))
      || enterprises.find((item) => String(item.id) === String(id));
    if (!selected) return;
    this.setData({
      selected,
      activeView: "detail",
      queryResults: this.buildCachedResults(selected.id)
    }, () => {
      this.refreshQueryDisplay();
    });
  },
  buildCachedResults(enterpriseId) {
    const cache = readObject(this.cacheKey);
    const now = Date.now();
    return queryTools.reduce((result, tool) => {
      const cached = cache[`${enterpriseId}:${tool.key}`];
      if (cached && now - Number(cached.ts || 0) < CACHE_TTL) {
        result[tool.key] = { ...cached, cached: true };
      }
      return result;
    }, {});
  },
  handleRunQuery(event) {
    const key = event.currentTarget.dataset.key;
    const tool = queryTools.find((item) => item.key === key);
    const enterprise = this.data.selected;
    if (!tool || !enterprise) return;
    const cache = readObject(this.cacheKey);
    const cacheId = `${enterprise.id}:${tool.key}`;
    const cached = cache[cacheId];
    const now = Date.now();
    if (cached && now - Number(cached.ts || 0) < CACHE_TTL) {
      this.setData({ [`queryResults.${tool.key}`]: { ...cached, cached: true } }, () => this.refreshQueryDisplay());
      wx.showToast({ title: "已用缓存，不扣分", icon: "none" });
      return;
    }
    const points = Number(this.data.points || 0);
    if (points < tool.cost) {
      wx.showToast({ title: "积分不足，先去资源库赚积分", icon: "none" });
      return;
    }
    const result = {
      key: tool.key,
      title: tool.label,
      cost: tool.cost,
      content: buildToolResult(enterprise, tool),
      ts: now,
      cached: false
    };
    cache[cacheId] = result;
    const nextPoints = points - tool.cost;
    wx.setStorageSync(this.cacheKey, cache);
    wx.setStorageSync(this.pointsKey, nextPoints);
    this.setData({
      points: nextPoints,
      [`queryResults.${tool.key}`]: result
    }, () => this.refreshQueryDisplay());
    wx.showToast({ title: tool.cost > 0 ? `已扣 ${tool.cost} 积分` : "免费查询完成", icon: "success" });
  },
  refreshQueryDisplay() {
    const results = this.data.queryResults || {};
    this.setData({
      displayTools: decorateTools(results),
      hasQueryResults: Object.keys(results).length > 0
    });
  },
  handleToggleTag(event) {
    const tag = event.currentTarget.dataset.tag;
    const tags = [...this.data.savedTags];
    const index = tags.indexOf(tag);
    if (index >= 0) tags.splice(index, 1);
    else tags.push(tag);
    const savedTags = tags.slice(0, 6);
    this.setData({
      savedTags,
      tagChoices: buildTagChoices(savedTags)
    });
  },
  handleOpenSave() {
    if (!this.data.selected) return;
    this.setData({ activeView: "save" });
  },
  handleOpenRules() {
    this.setData({ rulesVisible: true });
  },
  handleCloseRules() {
    this.setData({ rulesVisible: false });
  },
  handleSaveCard() {
    const enterprise = this.data.selected;
    if (!enterprise) return;
    const savedCards = readList(this.savedKey);
    const card = {
      id: `enterprise_${enterprise.id}_${Date.now()}`,
      ...enterprise,
      tags: this.data.savedTags,
      source: "天眼查公开信息",
      queriedAt: new Date().toISOString()
    };
    wx.setStorageSync(this.savedKey, [card, ...savedCards]);
    this.setData({ savedCards: [card, ...savedCards], activeView: "saved" });
  },
  handleBackToSearch() {
    this.setData({ activeView: "search", selected: null, queryResults: {}, displayTools: decorateTools(), hasQueryResults: false });
  },
  handleBackToDetail() {
    this.setData({ activeView: "detail" });
  },
  noop() {}
});
