const api = require("../../services/api");
const { enrichCard, getCurrentUser } = require("../../utils/dashboard");

Page({
  data: {
    keyword: "",
    activeCategory: "全部",
    activeTag: "全部",
    categoryFilters: [],
    tagFilters: [],
    cards: [],
    categories: [],
    displayCards: [],
    stats: {
      total: 0,
      pv: 0,
      tags: 0,
      today: 0
    }
  },
  onShow() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadCards();
  },
  handleKeywordChange(event) {
    this.setData({ keyword: event.detail.value });
  },
  async loadCards() {
    const currentUser = getCurrentUser();
    try {
      const [res, categoryRes] = await Promise.all([
        api.fetchCards({ ownerUserId: currentUser ? currentUser.id : "" }),
        api.fetchCategories(currentUser ? currentUser.id : "")
      ]);
      const categories = categoryRes.data || [];
      const categoriesById = categories.reduce((result, item) => {
        result[item.id] = item.name;
        return result;
      }, {});
      const cards = (res.data || []).map((card) => enrichCard(card, categoriesById));
      const categoryFilters = this.buildCountFilters(cards, (card) => card.categoryName);
      const tagFilters = this.buildCountFilters(
        cards.flatMap((card) => card.tagNames.map((tag) => ({ tag }))),
        (item) => item.tag
      );
      const stats = {
        total: cards.length,
        pv: cards.reduce((sum, card) => sum + card.stats.pv, 0),
        tags: new Set(cards.map((card) => card.categoryName)).size,
        today: cards.reduce((sum, card) => sum + card.stats.pv, 0)
      };
      this.setData({ cards, categories, categoryFilters, tagFilters, stats });
      this.applyFilter();
    } catch (error) {
      wx.showToast({ title: "加载素材失败", icon: "none" });
    }
  },
  buildCountFilters(items, resolveName) {
    const counts = items.reduce((result, item) => {
      const name = resolveName(item) || "资料";
      result[name] = (result[name] || 0) + 1;
      return result;
    }, {});
    return [
      { name: "全部", count: items.length },
      ...Object.keys(counts)
        .sort()
        .map((name) => ({ name, count: counts[name] }))
    ];
  },
  applyFilter() {
    const keyword = this.data.keyword.trim().toLowerCase();
    const displayCards = this.data.cards.filter((card) => {
      const matchCategory = this.data.activeCategory === "全部" || card.categoryName === this.data.activeCategory;
      const matchTag = this.data.activeTag === "全部" || card.tagNames.includes(this.data.activeTag);
      const haystack = [
        card.title,
        card.projectName,
        card.detailText,
        card.sourceUrl,
        card.categoryName,
        ...(card.tagNames || [])
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const matchKeyword = !keyword || haystack.includes(keyword);
      return matchCategory && matchTag && matchKeyword;
    });
    this.setData({ displayCards });
  },
  handleSearch() {
    this.applyFilter();
  },
  handleFilter(event) {
    this.setData({ activeCategory: event.currentTarget.dataset.filter });
    this.applyFilter();
  },
  handleTagFilter(event) {
    this.setData({ activeTag: event.currentTarget.dataset.tag });
    this.applyFilter();
  },
  handleOpen(event) {
    const id = event.currentTarget.dataset.id || event.detail.id;
    wx.navigateTo({ url: `/pages/card-edit/index?id=${id}` });
  },
  handleManage(event) {
    const id = event.currentTarget.dataset.id || event.detail.id;
    wx.navigateTo({ url: `/pages/manager/index?id=${id}` });
  },
  handleView(event) {
    wx.navigateTo({ url: `/pages/card-view/index?id=${event.currentTarget.dataset.id}` });
  },
  handleGoImports() {
    wx.switchTab({ url: "/pages/imports/index" });
  },
  handleManualAdd() {
    wx.navigateTo({ url: "/pages/resource-create/index" });
  },
  handleTagPlaceholder() {
    wx.navigateTo({ url: "/pages/tag-manage/index" });
  },
  handleCopySummary(event) {
    const card = this.data.cards.find((item) => item.id === event.currentTarget.dataset.id);
    if (!card) return;
    wx.setClipboardData({
      data: `${card.title}\n${card.detailText || ""}\n${card.sourceUrl || ""}`.trim()
    });
  }
});
