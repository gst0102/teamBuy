const api = require("../../services/api");
const resourceStore = require("../../stores/resource-store");
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
      const [cardsData, categories] = await Promise.all([
        resourceStore.listCards({ ownerUserId: currentUser ? currentUser.id : "" }, { force: true }),
        resourceStore.listCategories(currentUser ? currentUser.id : "", { force: true })
      ]);
      const categoriesById = categories.reduce((result, item) => {
        result[item.id] = item.name;
        return result;
      }, {});
      const cards = (cardsData || []).map((card) => enrichCard(card, categoriesById));
      const categoryFilters = this.buildCountFilters(cards, (card) => card.categoryName);
      const tagItems = cards.flatMap((card) => (card.tagNames || []).map((tag) => ({ tag })));
      const tagFilters = this.buildCountFilters(tagItems, (item) => item.tag);
      const stats = {
        total: cards.length,
        pv: cards.reduce((sum, card) => sum + card.stats.pv, 0),
        tags: new Set(tagItems.map((item) => item.tag)).size,
        today: cards.reduce((sum, card) => sum + card.stats.pv, 0)
      };
      this.setData({ cards, categories, categoryFilters, tagFilters, stats });
      this.applyFilter();
    } catch (error) {
      wx.showToast({ title: error.detail || "加载资源失败", icon: "none" });
    }
  },
  buildCountFilters(items, resolveName) {
    const counts = items.reduce((result, item) => {
      const name = resolveName(item);
      if (!name) return result;
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
      const matchTag = this.data.activeTag === "全部" || (card.tagNames || []).includes(this.data.activeTag);
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
  handleOpenPendingImports() {
    wx.navigateTo({ url: "/pages/imports/index" });
  },
  handleOpenNotes() {
    wx.navigateTo({ url: "/pages/notes/index" });
  },
  handleManualAdd() {
    wx.switchTab({ url: "/pages/resource-create/index" });
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
  },
  handleDelete(event) {
    const cardId = event.currentTarget.dataset.id;
    const currentUser = getCurrentUser();
    if (!cardId || !currentUser) return;
    wx.showModal({
      title: "删除资源",
      content: "删除后该资源、访问记录和接龙线索都会移除，确认删除吗？",
      confirmColor: "#ff5d5d",
      success: async ({ confirm }) => {
        if (!confirm) return;
        try {
          await api.deleteCard(cardId, currentUser.id);
          resourceStore.invalidateOwner(currentUser.id);
          wx.showToast({ title: "已删除", icon: "success" });
          this.loadCards();
        } catch (error) {
          wx.showToast({ title: error.detail || "删除失败", icon: "none" });
        }
      }
    });
  }
});
