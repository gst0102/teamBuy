const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { getCurrentUser, formatTime } = require("../../utils/dashboard");

function actionTitle(action) {
  if (action.actionKey === "lead-contact") return "客户留资";
  if (action.actionKey === "appointment") return "预约看房";
  if (action.actionKey === "order-intent") return "商品下单";
  if (action.actionKey === "relay-intent") return "商品接龙";
  if (action.actionLabel) return action.actionLabel;
  return "客户动作";
}

function actionDetails(action) {
  const payload = action.payload || {};
  const details = [];
  if (payload.name) details.push(`姓名：${payload.name}`);
  if (payload.phone) details.push(`电话：${payload.phone}`);
  if (payload.wechat) details.push(`微信：${payload.wechat}`);
  if (payload.date || payload.time) details.push(`预约：${[payload.date, payload.time].filter(Boolean).join(" ")}`);
  if (payload.skuName) details.push(`规格：${payload.skuName}`);
  if (payload.quantity) details.push(`数量：${payload.quantity}`);
  if (payload.remark) details.push(`备注：${payload.remark}`);
  return details;
}

function leadStatusText(status) {
  const map = {
    pending: "待联系",
    contacted: "已联系",
    invalid: "无效",
    paused: "暂不跟进",
    completed: "已完成"
  };
  return map[status] || "待联系";
}

function isClosedLead(status) {
  return ["invalid", "paused", "completed"].includes(status);
}

function productSkuKey(action) {
  const payload = action.payload || {};
  return payload.skuKey || payload.skuName || "default";
}

function productSkuLabel(action) {
  const payload = action.payload || {};
  return payload.skuName || "默认规格";
}

function buildSkuFilters(actions) {
  const rows = (actions || []).reduce((map, action) => {
    const key = productSkuKey(action);
    if (!map[key]) {
      map[key] = {
        key,
        label: productSkuLabel(action),
        count: 0
      };
    }
    map[key].count += 1;
    return map;
  }, {});
  return Object.values(rows);
}

function filterProductActions(actions, filterKey) {
  if (!filterKey) return actions || [];
  return (actions || []).filter((action) => productSkuKey(action) === filterKey);
}

Page({
  data: {
    noteId: "",
    loading: true,
    summary: {
      total: 0,
      leadContact: 0,
      appointment: 0,
      orderIntent: 0,
      relayIntent: 0,
      leads: 0,
      pending: 0
    },
    actions: [],
    leads: [],
    pendingLeads: [],
    appointmentActions: [],
    relayActions: [],
    filteredRelayActions: [],
    skuFilters: [],
    selectedSkuFilter: "",
    productListTitle: "商品下单名单",
    productEmptyText: "暂无下单",
    productCopyToast: "下单信息已复制",
    finishedLeads: [],
    otherActions: [],
    isProductRelay: false
  },
  onLoad(options) {
    this.setData({ noteId: options.id || "" });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.loadActions(user.id);
  },
  async loadActions(ownerUserId) {
    const { noteId } = this.data;
    if (!noteId) return;
    this.setData({ loading: true });
    try {
      const res = await api.fetchNoteCustomerActions(noteId, ownerUserId);
      const data = res.data || {};
      const actions = (data.actions || []).map((item) => ({
        ...item,
        title: actionTitle(item),
        createdText: formatTime(item.createdAt),
        details: item.displayRows && item.displayRows.length
          ? item.displayRows.map((row) => `${row.label}：${row.value}`)
          : actionDetails(item)
      }));
      const leads = (data.leads || []).map((item) => ({
        ...item,
        statusText: leadStatusText(item.status),
        isClosed: isClosedLead(item.status),
        updatedText: formatTime(item.updatedAt),
        nextFollowUpText: item.nextFollowUpAt ? String(item.nextFollowUpAt).slice(0, 16).replace("T", " ") : "未设置"
      }));
      const productActions = actions.filter((item) => item.actionKey === "relay-intent" || item.actionKey === "order-intent");
      const relayCount = productActions.filter((item) => item.actionKey === "relay-intent").length;
      const hasRelayMode = relayCount > 0 || (data.summary || {}).relayIntent > 0;
      const skuFilters = buildSkuFilters(productActions);
      const selectedSkuFilter = skuFilters.some((item) => item.key === this.data.selectedSkuFilter)
        ? this.data.selectedSkuFilter
        : "";
      this.setData({
        summary: {
          ...this.data.summary,
          ...(data.summary || {})
        },
        actions,
        leads,
        pendingLeads: leads.filter((item) => item.status === "pending"),
        appointmentActions: actions.filter((item) => item.actionKey === "appointment"),
        relayActions: productActions,
        filteredRelayActions: filterProductActions(productActions, selectedSkuFilter),
        skuFilters,
        selectedSkuFilter,
        productListTitle: hasRelayMode ? "商品接龙名单" : "商品下单名单",
        productEmptyText: hasRelayMode ? "暂无接龙" : "暂无下单",
        productCopyToast: hasRelayMode ? "接龙信息已复制" : "下单信息已复制",
        finishedLeads: leads.filter((item) => item.status !== "pending"),
        otherActions: actions.filter((item) => item.actionKey !== "appointment" && item.actionKey !== "relay-intent" && item.actionKey !== "order-intent"),
        isProductRelay: data.cardType === "groupbuy_product" || (data.summary || {}).mode === "product_relay"
      });
    } catch (error) {
      wx.showToast({ title: error.detail || "客户动作加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
  handleOpenLead(event) {
    const id = event.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/lead-detail/index?id=${id}` });
  },
  handleCallPhone(event) {
    const phone = event.currentTarget.dataset.phone;
    const id = event.currentTarget.dataset.id;
    if (!phone) {
      wx.showToast({ title: "暂无手机号", icon: "none" });
      return;
    }
    wx.makePhoneCall({
      phoneNumber: phone,
      success: () => this.confirmMarkContacted(id),
      fail: () => wx.showToast({ title: "拨号失败", icon: "none" })
    });
  },
  handleCopyContact(event) {
    const value = event.currentTarget.dataset.value;
    if (!value) {
      wx.showToast({ title: "暂无内容", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: value,
      success: () => wx.showToast({ title: "已复制", icon: "success" })
    });
  },
  handleCopyRelay(event) {
    const index = Number(event.currentTarget.dataset.index);
    const action = (this.data.filteredRelayActions || [])[index];
    if (!action) return;
    const text = [
      action.customerName || action.payload.name || "客户",
      ...(action.details || [])
    ].filter(Boolean).join("\n");
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: this.data.productCopyToast, icon: "success" })
    });
  },
  async handleOpenMessage(event) {
    const index = Number(event.currentTarget.dataset.index);
    const action = (this.data.filteredRelayActions || [])[index];
    if (!action || !this.data.noteId) return;
    await messagePlugin.openMessageThread({ noteId: this.data.noteId, orderActionId: action.id });
  },
  handleCopyRelaySummary() {
    const lines = (this.data.filteredRelayActions || []).map((item, index) => [
      `${index + 1}. ${item.customerName || item.payload.name || "客户"}`,
      ...(item.details || [])
    ].join("；"));
    if (!lines.length) {
      wx.showToast({ title: this.data.productEmptyText, icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: lines.join("\n"),
      success: () => wx.showToast({ title: "汇总已复制", icon: "success" })
    });
  },
  handleSkuFilter(event) {
    const key = event.currentTarget.dataset.key || "";
    this.setData({
      selectedSkuFilter: key,
      filteredRelayActions: filterProductActions(this.data.relayActions, key)
    });
  },
  confirmMarkContacted(id) {
    if (!id) return;
    wx.showModal({
      title: "是否标记已联系？",
      content: "如果这通电话已经沟通过，可以顺手记录到线索里。",
      confirmText: "标记",
      confirmColor: "#11924d",
      success: async (res) => {
        if (!res.confirm) return;
        await this.markLeadContacted(id);
      }
    });
  },
  async markLeadContacted(id) {
    const user = getCurrentUser();
    if (!user || !id) return;
    try {
      await api.updateLeadReminder(id, {
        ownerUserId: user.id,
        status: "contacted",
        logContent: "已电话联系客户"
      });
      wx.showToast({ title: "已标记联系", icon: "success" });
      this.loadActions(user.id);
    } catch (error) {
      wx.showToast({ title: error.detail || "更新失败", icon: "none" });
    }
  }
});
