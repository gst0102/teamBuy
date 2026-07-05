const {
  createResponsePackage,
  fetchResponsePackage,
  previewResponsePackage,
  recordResponsePackageEvent
} = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");
const { buildUniversalShareMessage, prepareUniversalShareImage } = require("../../utils/universal-share");

const emptyPackage = {
  lead: { title: "回应包", summary: "系统会根据线索和你的资料生成回应内容。" },
  demandSummary: {},
  recommendedAssets: [],
  assetOptions: [],
  selectedAssetIds: [],
  items: [],
  openingText: "先选择一条商机线索，再生成回应包。",
  trackingUrl: "",
  followupSuggestion: "生成后再根据对方反馈跟进。",
  costPoints: 20,
  usedFreeQuota: false,
  existingPackageId: ""
};

function isDemoLeadId(value) {
  return /^opp_demo_/.test(String(value || ""));
}

function demoPackage(leadId, generated = false) {
  const leadMap = {
    opp_demo_1: {
      title: "长沙新店找本地推广渠道",
      summary: "餐饮新店准备开业，想找能触达社区和商圈客户的合作方。",
      city: "长沙",
      industry: "本地生活",
      demandType: "找渠道"
    },
    opp_demo_2: {
      title: "社区团购团长找稳定货源",
      summary: "希望找到日用品、食品类供给方，可接受样品试卖。",
      city: "长沙",
      industry: "团购",
      demandType: "找货源"
    },
    opp_demo_3: {
      title: "企业客户找活动执行供应商",
      summary: "下周有线下活动，需要摄影、物料和现场执行团队。",
      city: "长沙",
      industry: "企业服务",
      demandType: "找服务商"
    }
  };
  const lead = { id: leadId, ...(leadMap[leadId] || leadMap.opp_demo_1) };
  return normalizePackage({
    id: generated ? `demo_pkg_${leadId}` : "",
    lead,
    demandSummary: {
      city: lead.city,
      industry: lead.industry,
      demandType: lead.demandType,
      contactStatus: "示例数据"
    },
    recommendedAssets: [
      {
        assetId: "demo_asset_service",
        assetTitle: "服务介绍卡",
        assetSummary: "介绍你能提供的服务、案例和联系方式。",
        recommendReason: "适合作为首次介绍资料",
        selected: true
      }
    ],
    assetOptions: [
      {
        assetId: "demo_asset_service",
        assetTitle: "服务介绍卡",
        assetSummary: "介绍你能提供的服务、案例和联系方式。",
        recommendReason: "适合作为首次介绍资料",
        selected: true
      },
      {
        assetId: "demo_asset_case",
        assetTitle: "成功案例合集",
        assetSummary: "用案例降低首次沟通成本。",
        recommendReason: "适合补充信任感",
        selected: false
      }
    ],
    selectedAssetIds: ["demo_asset_service"],
    openingText: `你好，我看到你在找${lead.city}${lead.industry}相关合作资源。我这边可以先发一份服务介绍和案例，你看是否匹配。`,
    trackingUrl: generated ? "/pages/response-package/index?id=demo" : "",
    followupSuggestion: "先发送回应内容，稍后根据对方反馈再电话或微信跟进。",
    costPoints: 0,
    usedFreeQuota: true
  });
}

function normalizePackage(payload = {}) {
  const assets = Array.isArray(payload.items) && payload.items.length
    ? payload.items.map((item) => ({
        assetId: item.assetId,
        assetTitle: item.assetTitle,
        assetSummary: item.assetSummary,
        recommendReason: item.recommendReason
      }))
    : (payload.recommendedAssets || []);
  const assetOptions = Array.isArray(payload.assetOptions) && payload.assetOptions.length
    ? payload.assetOptions
    : assets.map((item) => ({ ...item, selected: true }));
  const selectedAssetIds = Array.isArray(payload.selectedAssetIds) && payload.selectedAssetIds.length
    ? payload.selectedAssetIds
    : assetOptions.filter((item) => item.selected).map((item) => item.assetId);
  return {
    ...emptyPackage,
    ...payload,
    recommendedAssets: assets,
    assetOptions: assetOptions.map((item) => ({
      ...item,
      selected: selectedAssetIds.includes(item.assetId)
    })),
    selectedAssetIds,
    trackingUrl: payload.trackingUrl || "",
    generated: Boolean(payload.id),
    priceText: payload.id
      ? (payload.usedFreeQuota ? "本次使用免费额度" : `已消耗 ${payload.costPoints || 0} 积分`)
      : (payload.existingPackageId ? "已生成过，可直接打开" : "预览不扣积分")
  };
}

Page({
  data: {
    leadId: "",
    packageId: "",
    responsePackage: emptyPackage,
    loading: false,
    creating: false,
    universalShareImage: ""
  },
  onLoad(options = {}) {
    this.leadId = options.leadId || "";
    this.packageId = options.id || "";
    this.loadPackage();
  },
  async loadPackage() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ loading: true, leadId: this.leadId, packageId: this.packageId });
    try {
      let res;
      if (this.packageId) {
        res = await fetchResponsePackage(this.packageId, user.id);
        await recordResponsePackageEvent(this.packageId, { eventType: "view", viewerId: user.id });
      } else if (isDemoLeadId(this.leadId)) {
        this.setData({
          responsePackage: demoPackage(this.leadId),
          packageId: ""
        });
        return;
      } else {
        res = await previewResponsePackage(this.leadId, {
          userId: user.id,
          selectedAssetIds: this.data.responsePackage.selectedAssetIds || []
        });
      }
      const responsePackage = normalizePackage(res.data || {});
      this.setData({
        responsePackage,
        packageId: responsePackage.id || responsePackage.existingPackageId || this.packageId
      });
      this.prepareShareImage();
    } catch (error) {
      this.setData({ responsePackage: isDemoLeadId(this.leadId) ? demoPackage(this.leadId) : normalizePackage(emptyPackage) });
      this.prepareShareImage();
      wx.showToast({ title: "回应包暂时不可用", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  async handleCreate() {
    const user = getCurrentUser();
    if (!user || !this.leadId) return;
    if (isDemoLeadId(this.leadId)) {
      this.setData({
        responsePackage: demoPackage(this.leadId, true),
        packageId: `demo_pkg_${this.leadId}`
      });
      wx.showToast({ title: "示例回应包已生成", icon: "success" });
      return;
    }
    if (!(this.data.responsePackage.selectedAssetIds || []).length) {
      wx.showToast({ title: "先选择至少一条资料", icon: "none" });
      return;
    }
    this.setData({ creating: true });
    try {
      const res = await createResponsePackage(this.leadId, {
        userId: user.id,
        selectedAssetIds: this.data.responsePackage.selectedAssetIds || []
      });
      const responsePackage = normalizePackage(res.data || {});
      this.setData({
        responsePackage,
        packageId: responsePackage.id || ""
      });
      this.prepareShareImage();
      wx.showToast({ title: "回应包已生成", icon: "success" });
    } catch (error) {
      const message = error && error.detail ? error.detail : "生成失败，稍后再试";
      wx.showToast({ title: message, icon: "none" });
    } finally {
      this.setData({ creating: false });
    }
  },
  handleCopyOpening() {
    const pack = this.data.responsePackage;
    const text = [pack.openingText, pack.trackingUrl ? `资料链接：${pack.trackingUrl}` : ""].filter(Boolean).join("\n");
    wx.setClipboardData({ data: text || "暂无回应内容" });
  },
  handleOpenRadar() {
    const id = this.data.responsePackage.id || this.data.packageId;
    if (!id) {
      wx.showToast({ title: "生成后可查看雷达", icon: "none" });
      return;
    }
    wx.navigateTo({ url: `/pages/response-package-radar/index?id=${id}` });
  },
  async handleAssetToggle(event) {
    const assetId = event.currentTarget.dataset.id;
    const pack = this.data.responsePackage || {};
    if (!assetId || pack.generated) return;
    const current = new Set(pack.selectedAssetIds || []);
    if (current.has(assetId)) {
      current.delete(assetId);
    } else {
      current.add(assetId);
    }
    const selectedAssetIds = Array.from(current).slice(0, 3);
    const assetOptions = (pack.assetOptions || []).map((item) => ({
      ...item,
      selected: selectedAssetIds.includes(item.assetId)
    }));
    const recommendedAssets = assetOptions.filter((item) => item.selected);
    this.setData({
      responsePackage: normalizePackage({
        ...pack,
        assetOptions,
        recommendedAssets,
        selectedAssetIds
      })
    });
  },
  async handleRefreshPreview() {
    if (this.data.responsePackage.generated || !this.leadId || isDemoLeadId(this.leadId)) return;
    await this.loadPackage();
    wx.showToast({ title: "已按所选资料刷新", icon: "none" });
  },
  handleOpenLead() {
    const leadId = this.data.responsePackage.lead && this.data.responsePackage.lead.id;
    if (leadId) {
      wx.navigateTo({ url: `/pages/opportunity-detail/index?id=${leadId}` });
    }
  },
  prepareShareImage() {
    const pack = this.data.responsePackage || emptyPackage;
    const lead = pack.lead || {};
    const id = pack.id || this.data.packageId || this.packageId || "";
    return prepareUniversalShareImage(this, {
      title: lead.title || "回应包",
      summary: lead.summary || pack.openingText || "打开查看回应包资料和话术。",
      badge: "回应包",
      path: id ? `/pages/response-package/index?id=${encodeURIComponent(id)}` : `/pages/response-package/index?leadId=${encodeURIComponent(this.leadId || "")}`,
      shareTargetLabel: "资料"
    });
  },
  onShareAppMessage() {
    const pack = this.data.responsePackage || emptyPackage;
    const lead = pack.lead || {};
    const id = pack.id || this.data.packageId || this.packageId || "";
    return buildUniversalShareMessage(this, {
      title: lead.title || "回应包",
      summary: lead.summary || "打开查看回应包资料和话术。",
      badge: "回应包",
      path: id ? `/pages/response-package/index?id=${encodeURIComponent(id)}` : `/pages/response-package/index?leadId=${encodeURIComponent(this.leadId || "")}`,
      shareTargetLabel: "资料"
    });
  }
});
