const { applySupplyDemandCard, fetchSupplyDemandCard } = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildUniversalShareMessage, prepareUniversalShareImage } = require("../../utils/universal-share");

const emptyCard = {
  id: "",
  badge: "供需卡",
  title: "供需详情",
  summary: "",
  city: "不限城市",
  industry: "综合",
  demandType: "合作",
  contactRequirement: "申请联系",
  tags: [],
  ownerNickname: "",
  applicationCount: 0,
  myApplicationStatus: "",
  isMine: false
};

function applicationStatusText(value) {
  if (value === "accepted") return "已通过";
  if (value === "rejected") return "已拒绝";
  if (value === "closed") return "已关闭";
  if (value === "pending") return "已申请";
  return "";
}

Page({
  data: {
    card: emptyCard,
    applicationText: "",
    loading: false,
    applying: false,
    universalShareImage: ""
  },
  onLoad(options = {}) {
    this.cardId = options.id || "";
    this.loadCard();
  },
  async loadCard() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    if (!this.cardId) return;
    this.setData({ loading: true });
    try {
      const res = await fetchSupplyDemandCard(this.cardId, user.id);
      const card = {
        ...emptyCard,
        ...(res.data || {})
      };
      card.applicationStatusText = applicationStatusText(card.myApplicationStatus);
      this.setData({ card });
      this.prepareShareImage();
    } catch (error) {
      wx.showToast({ title: "供需卡暂时不可用", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  setApplicationText(event) {
    this.setData({ applicationText: event.detail.value });
  },
  async handleApply() {
    const user = getCurrentUser();
    const card = this.data.card;
    if (!user || !card.id || card.isMine) return;
    if (card.myApplicationStatus === "pending" || card.myApplicationStatus === "accepted") {
      wx.showToast({ title: "已提交过申请", icon: "none" });
      return;
    }
    this.setData({ applying: true });
    try {
      await applySupplyDemandCard(card.id, {
        userId: user.id,
        message: this.data.applicationText || "我想进一步沟通这个合作机会。"
      });
      wx.showToast({ title: "申请已发送", icon: "success" });
      this.loadCard();
    } catch (error) {
      wx.showToast({ title: (error && error.detail) || "申请失败", icon: "none" });
    } finally {
      this.setData({ applying: false });
    }
  },
  handleOpenLinkedNote() {
    const note = this.data.card.linkedNote || {};
    if (!note.id) {
      wx.showToast({ title: "暂无关联资料", icon: "none" });
      return;
    }
    wx.navigateTo({ url: `/pages/note-preview/index?id=${note.id}` });
  },
  prepareShareImage() {
    const card = this.data.card || emptyCard;
    const note = card.linkedNote || {};
    return prepareUniversalShareImage(this, {
      title: card.title || "供需详情",
      summary: card.summary || "打开查看供需合作详情。",
      badge: card.cardType === "demand" ? "需求" : "供给",
      coverUrl: card.coverUrl || note.coverUrl || note.coverDisplayUrl || "",
      path: `/pages/supply-demand-detail/index?id=${encodeURIComponent(card.id || this.cardId || "")}`,
      shareTargetLabel: "供需"
    });
  },
  onShareAppMessage() {
    const card = this.data.card || emptyCard;
    return buildUniversalShareMessage(this, {
      title: card.title || "供需详情",
      summary: card.summary || "打开查看供需合作详情。",
      badge: card.cardType === "demand" ? "需求" : "供给",
      path: `/pages/supply-demand-detail/index?id=${encodeURIComponent(card.id || this.cardId || "")}`,
      shareTargetLabel: "供需"
    });
  }
});
