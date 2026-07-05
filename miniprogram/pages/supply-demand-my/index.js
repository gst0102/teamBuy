const { fetchMySupplyDemandCards, fetchSupplyDemandApplications, reviewSupplyDemandApplication, submitSupplyDemandCard, updateSupplyDemandCard } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildUniversalShareMessage, prepareUniversalShareImage } = require("../../utils/universal-share");

function statusText(value) {
  if (value === "published") return "展示中";
  if (value === "pending_review") return "待审核";
  if (value === "rejected") return "已拒绝";
  if (value === "archived") return "已下架";
  return "草稿";
}

Page({
  data: {
    cards: [],
    applications: [],
    myApplications: [],
    loading: false,
    universalShareImage: ""
  },
  onShow() {
    this.loadCards();
    this.prepareShareImage();
  },
  prepareShareImage() {
    const first = (this.data.cards || [])[0] || {};
    return prepareUniversalShareImage(this, {
      title: "我的发布",
      summary: first.summary || first.title || "查看我发布的供需卡和收到的合作申请。",
      badge: "供需",
      path: "/pages/supply-demand-my/index",
      shareTargetLabel: "供需"
    });
  },
  async loadCards() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ loading: true });
    try {
      const [res, appRes, myAppRes] = await Promise.all([
        fetchMySupplyDemandCards(user.id),
        fetchSupplyDemandApplications(user.id, "owner"),
        fetchSupplyDemandApplications(user.id, "applicant")
      ]);
      const cards = Array.isArray(res.data) ? res.data.map((item) => ({ ...item, statusText: statusText(item.status) })) : [];
      const applications = Array.isArray(appRes.data) ? appRes.data.map((item) => ({
        ...(item.application || {}),
        cardTitle: item.card && item.card.title,
        applicantNickname: item.applicant && item.applicant.nickname
      })) : [];
      const myApplications = Array.isArray(myAppRes.data) ? myAppRes.data.map((item) => ({
        ...(item.application || {}),
        cardTitle: item.card && item.card.title,
        cardSummary: item.card && item.card.summary
      })) : [];
      this.setData({ cards, applications, myApplications });
      this.prepareShareImage();
    } catch (error) {
      wx.showToast({ title: "读取失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handlePublish() {
    wx.navigateTo({ url: "/pages/supply-demand-publish/index" });
  },
  handleEdit(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/supply-demand-publish/index?id=${id}` });
  },
  handleOpenSupplyDetail(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/supply-demand-detail/index?id=${id}` });
  },
  async handleSubmit(event) {
    const user = getCurrentUser();
    const id = event.currentTarget.dataset.id;
    if (!user || !id) return;
    try {
      await submitSupplyDemandCard(id, user.id);
      wx.showToast({ title: "已提交审核", icon: "success" });
      this.loadCards();
    } catch (error) {
      wx.showToast({ title: "提交失败", icon: "none" });
    }
  },
  async handleArchive(event) {
    const user = getCurrentUser();
    const id = event.currentTarget.dataset.id;
    if (!user || !id) return;
    try {
      const card = this.data.cards.find((item) => item.id === id);
      await updateSupplyDemandCard(id, { ...card, userId: user.id, status: "archived" });
      wx.showToast({ title: "已下架", icon: "success" });
      this.loadCards();
    } catch (error) {
      wx.showToast({ title: "下架失败", icon: "none" });
    }
  },
  async handleReviewApplication(event) {
    const user = getCurrentUser();
    const id = event.currentTarget.dataset.id;
    const status = event.currentTarget.dataset.status;
    if (!user || !id || !status) return;
    try {
      await reviewSupplyDemandApplication(id, { userId: user.id, status });
      wx.showToast({ title: status === "accepted" ? "已通过" : "已拒绝", icon: "success" });
      this.loadCards();
    } catch (error) {
      wx.showToast({ title: "处理失败", icon: "none" });
    }
  },
  onShareAppMessage() {
    return buildUniversalShareMessage(this, {
      title: "我的发布",
      summary: "查看我发布的供需卡和收到的合作申请。",
      badge: "供需",
      path: "/pages/supply-demand-my/index",
      shareTargetLabel: "供需"
    });
  }
});
