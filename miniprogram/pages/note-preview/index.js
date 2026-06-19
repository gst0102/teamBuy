const api = require("../../services/api");
const messagePlugin = require("../../plugins/message-plugin/index");
const { getCurrentUser } = require("../../utils/dashboard");

const LAST_LEAD_PHONE_KEY = "teambuy:lastLeadPhone";
const LAST_PROPERTY_CITY_KEY = "teambuy:lastPropertyCity";

function pad(num) {
  return `${num}`.padStart(2, "0");
}

function formatDateInput(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function formatDateLabel(value) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value || "";
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

function buildAppointmentDraft(offsetDays = 0) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return {
    date: formatDateInput(date),
    time: "10:00",
    remark: ""
  };
}

function inferCityFromText(value) {
  const text = String(value || "");
  const cityMatch = text.match(/([\u4e00-\u9fff]{2,12}市)/);
  if (cityMatch) return cityMatch[1];
  if (text.includes("长沙") || text.includes("湖南")) return "长沙市";
  return "";
}

function readLastPropertyCity() {
  try {
    return wx.getStorageSync(LAST_PROPERTY_CITY_KEY) || "";
  } catch (error) {
    return "";
  }
}

function rememberPropertyCity(value) {
  const city = inferCityFromText(value);
  if (!city) return;
  try {
    wx.setStorageSync(LAST_PROPERTY_CITY_KEY, city);
  } catch (error) {
    // Local memory only improves map matching; ignore failures.
  }
}

function readLastLeadPhone() {
  try {
    return wx.getStorageSync(LAST_LEAD_PHONE_KEY) || "";
  } catch (error) {
    return "";
  }
}

function rememberLeadPhone(value) {
  const phone = String(value || "").match(/1[3-9]\d{9}/);
  if (!phone) return;
  try {
    wx.setStorageSync(LAST_LEAD_PHONE_KEY, phone[0]);
  } catch (error) {
    // Local memory is only a convenience; ignore failures.
  }
}

function normalizePropertyStatus(value) {
  if (value === "rented" || value === "paused") return value;
  return "active";
}

function buildAvailability(data, isProperty) {
  if (!isProperty) return null;
  const status = normalizePropertyStatus(data.propertyStatus);
  if (status === "rented") {
    return {
      status,
      title: "该房源已租出",
      desc: "当前不再接收新的电话、留资和预约。"
    };
  }
  if (status === "paused") {
    return {
      status,
      title: "该房源暂停推广",
      desc: "发布者暂时关闭新的咨询和预约。"
    };
  }
  return null;
}

function normalizeSkuConfig(data) {
  const source = (data && data.skuConfig) || {};
  const skus = Array.isArray(source.skus) ? source.skus : [];
  const attributeGroups = Array.isArray(source.attributeGroups)
    ? source.attributeGroups.map((group, groupIndex) => ({
        id: group.id || `group_${groupIndex}`,
        name: group.name || `规格${groupIndex + 1}`,
        options: (Array.isArray(group.options) ? group.options : []).map((option, optionIndex) => ({
          id: option.id || `option_${groupIndex}_${optionIndex}`,
          label: option.label || option.name || ""
        })).filter((option) => option.label)
      })).filter((group) => group.options.length)
    : [];
  if (skus.length) {
    return {
      attributeGroups,
      skus: skus.map((sku, index) => ({
        id: sku.id || sku.key || `sku_${index}`,
        key: sku.key || sku.id || `sku_${index}`,
        optionIds: Array.isArray(sku.optionIds) && sku.optionIds.length
          ? sku.optionIds
          : String(sku.key || sku.id || `sku_${index}`).split("|").filter(Boolean),
        optionLabels: Array.isArray(sku.optionLabels) ? sku.optionLabels : [],
        name: sku.name || "默认规格",
        price: sku.price || data.price || "",
        description: sku.description || "",
        soldOut: Boolean(sku.soldOut)
      }))
    };
  }
  return {
    attributeGroups: [],
    skus: [{
      id: "default",
      key: "default",
      name: data.spec || data.productName || "默认规格",
      price: data.price || "",
      description: data.pickupMethod || "",
      soldOut: false
    }]
  };
}

function skuOptionIds(sku) {
  if (Array.isArray(sku.optionIds) && sku.optionIds.length) return sku.optionIds;
  return String(sku.key || sku.id || "").split("|").filter(Boolean);
}

function buildSelectedSkuOptions(skuConfig, skuKey) {
  const groups = skuConfig.attributeGroups || [];
  const sku = (skuConfig.skus || []).find((item) => item.key === skuKey || item.id === skuKey);
  const ids = sku ? skuOptionIds(sku) : [];
  return groups.reduce((result, group, index) => {
    if (ids[index]) result[group.id] = ids[index];
    return result;
  }, {});
}

function findSkuBySelectedOptions(skuConfig, selectedOptions) {
  const groups = skuConfig.attributeGroups || [];
  if (!groups.length) return null;
  const selectedIds = groups.map((group) => selectedOptions[group.id]).filter(Boolean);
  if (selectedIds.length !== groups.length) return null;
  return (skuConfig.skus || []).find((sku) => {
    const ids = skuOptionIds(sku);
    return groups.every((group, index) => ids[index] === selectedOptions[group.id]);
  }) || null;
}

function buildSkuSelectionGroups(skuConfig, selectedOptions) {
  const groups = skuConfig.attributeGroups || [];
  const skus = skuConfig.skus || [];
  return groups.map((group, groupIndex) => ({
    ...group,
    options: (group.options || []).map((option) => {
      const available = skus.some((sku) => {
        if (sku.soldOut) return false;
        const ids = skuOptionIds(sku);
        return ids[groupIndex] === option.id;
      });
      return {
        ...option,
        active: selectedOptions[group.id] === option.id,
        disabled: !available
      };
    })
  }));
}

function buildProductPriceText(skuConfig, fallback) {
  const prices = (skuConfig.skus || [])
    .filter((sku) => !sku.soldOut && sku.price)
    .map((sku) => String(sku.price || "").trim())
    .filter(Boolean);
  const unique = Array.from(new Set(prices));
  if (!unique.length) return fallback || "";
  if (unique.length === 1) return unique[0];
  return `${unique[0]} - ${unique[unique.length - 1]}`;
}

function buildView(note) {
  const config = note.visibilityConfig || {};
  const data = config.structuredData || {};
  const miniapp = buildMiniappInfo(data);
  const cardType = config.cardType || "text_note";
  const isProperty = cardType === "property_listing";
  const isGroupbuy = cardType === "groupbuy_product";
  const isMiniapp = miniapp.visible && config.sourceType === "miniapp";
  const skuConfig = normalizeSkuConfig(data);
  const productPriceText = buildProductPriceText(skuConfig, data.price);
  const title = isProperty ? data.community || note.title : isGroupbuy ? data.productName || note.title : miniapp.title || note.title;
  const subtitle = isProperty
    ? [data.price, data.layout, data.area].filter(Boolean).join(" · ")
    : isGroupbuy
      ? [productPriceText, data.spec, data.pickupMethod].filter(Boolean).join(" · ")
      : isMiniapp ? [miniapp.sourceName, miniapp.houseCode ? `房源编码 ${miniapp.houseCode}` : ""].filter(Boolean).join(" · ") : note.summary || "";
  const mapLocation = buildMapLocation(data);
  const coverUrl = note.coverUrl || ((note.media || []).find((item) => item.type === "image") || {}).url || "";
  const galleryImages = buildGalleryImages(note, coverUrl);
  const galleryVideos = buildGalleryVideos(note);
  const address = isProperty ? data.address || data.businessArea || "" : data.pickupLocation || "";
  const contact = data.contact || note.phone || "";
  const rows = isProperty
    ? [
        ["户型", data.layout],
        ["面积", data.area],
        ["价格", data.price],
        ["水电物业", data.utilities],
        ["位置", address],
        ["服务费", data.serviceFee]
      ]
    : isGroupbuy
      ? [
          ["价格", productPriceText],
          ["规格", data.spec],
          ["取货方式", data.pickupMethod],
          ["取货地点", data.pickupLocation],
          ["截止时间", data.deadline],
          ["库存", data.stockNote]
        ]
      : isMiniapp
        ? [["来源", miniapp.sourceName], ["房源编码", miniapp.houseCode], ["城市编码", miniapp.cityId]]
        : [["摘要", note.summary], ["正文", note.body]];
  const conversion = config.conversionConfig || {};
  const availability = buildAvailability(data, isProperty);
  const canConvert = !availability;
  const actions = [];
  if (miniapp.visible) actions.push({ key: "miniapp", title: miniapp.buttonText, desc: "打开原小程序详情" });
  if (canConvert && conversion.showContactPhone) actions.push({ key: "contact", title: "电话咨询", desc: contact ? "拨打或复制电话" : "复制联系方式" });
  if (canConvert && conversion.collectLeads) actions.push({ key: "lead", title: "留下电话/微信", desc: "方便发布者回访" });
  if (canConvert && conversion.enableAppointment) actions.push({ key: "appointment", title: "预约看房", desc: "选择日期和时间" });
  if (canConvert && conversion.enablePrivateConsultation) actions.push({ key: "private", title: "微信咨询", desc: "复制发布者微信/电话" });
  if (canConvert && (isProperty || isGroupbuy)) actions.push({ key: "message", title: "发消息", desc: "站内留言给发布者" });
  if (isProperty && address) actions.push({ key: "map", title: "地图定位", desc: mapLocation.hasPoint ? "打开腾讯地图" : "按地址搜索" });
  return {
    title,
    ownerUserId: note.ownerUserId || "",
    subtitle,
    isGroupbuy,
    enableGroupRelay: Boolean(conversion.enableGroupRelay),
    orderButtonText: conversion.enableGroupRelay ? "下单并接龙" : "下单",
    badge: isProperty ? "房源" : isGroupbuy ? "商品" : isMiniapp ? "小程序房源" : "资料",
    coverUrl,
    galleryImages,
    galleryVideos,
    rows: rows.filter((item) => item[1]).map(([label, value]) => ({ label, value })),
    remark: data.remark || note.summary || note.body || "",
    availability,
    actions,
    hasMap: isProperty && Boolean(address),
    skuConfig,
    selectedSku: (skuConfig.skus || []).find((item) => !item.soldOut) || (skuConfig.skus || [])[0] || null,
    miniapp,
    contact,
    address,
    mapLocation
  };
}

function buildMiniappInfo(data) {
  const miniapp = (data && data.miniapp) || {};
  const appId = miniapp.appid || "";
  const path = miniapp.pagePath || "";
  const sourceName = miniapp.displayName || miniapp.description || "小程序";
  return {
    visible: Boolean(appId && path),
    appId,
    path,
    title: miniapp.title || "",
    sourceName,
    houseCode: miniapp.houseCode || "",
    cityId: miniapp.cityId || "",
    buttonText: sourceName.includes("贝壳") ? "查看贝壳原房源" : "打开原小程序"
  };
}

function buildGalleryImages(note, coverUrl) {
  const structuredImages = ((note.visibilityConfig || {}).structuredData || {}).images;
  const urls = [
    ...(Array.isArray(note.media) ? note.media.filter((item) => item.type === "image").map((item) => item.url) : []),
    ...(Array.isArray(structuredImages) ? structuredImages : [])
  ].filter(Boolean);
  return Array.from(new Set(urls.filter((url) => url !== coverUrl)));
}

function buildGalleryVideos(note) {
  const urls = Array.isArray(note.media)
    ? note.media.filter((item) => item.type === "video").map((item) => item.url)
    : [];
  return Array.from(new Set(urls.filter(Boolean)));
}

function buildMapLocation(data) {
  const location = data.mapLocation || {};
  const latitude = Number(location.latitude);
  const longitude = Number(location.longitude);
  const address = location.address || data.address || data.businessArea || "";
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return {
      hasPoint: false,
      latitude: 0,
      longitude: 0,
      name: location.name || "",
      address,
      markers: []
    };
  }
  return {
    hasPoint: true,
    latitude,
    longitude,
    name: location.name || address || "房源位置",
    address,
    markers: [{
      id: 1,
      latitude,
      longitude,
      title: location.name || address || "房源位置",
      label: {
        content: "🏠",
        color: "#17633a",
        fontSize: 22,
        anchorX: -8,
        anchorY: -42,
        borderWidth: 1,
        borderColor: "#17633a",
        borderRadius: 6,
        bgColor: "#ffffff",
        padding: 4
      },
      callout: {
        content: "🏠 房源位置",
        color: "#172033",
        fontSize: 13,
        borderRadius: 6,
        bgColor: "#ffffff",
        padding: 8,
        display: "ALWAYS"
      }
    }]
  };
}

function inferMapRegion(address) {
  const text = String(address || "");
  const remembered = readLastPropertyCity();
  if (remembered) return remembered;
  const city = inferCityFromText(text);
  if (city) return city;
  if (text.includes("长沙")) return "长沙市";
  if (text.includes("湖南")) return "湖南省";
  return "";
}

function enrichAddressWithCity(address) {
  const value = String(address || "").trim();
  if (!value) return "";
  const city = inferCityFromText(value) || readLastPropertyCity();
  if (city && !value.includes(city) && !value.includes(city.replace("市", ""))) {
    return `${city} ${value}`;
  }
  return value;
}

Page({
  data: {
    noteId: "",
    user: null,
    view: null,
    resolvingMap: false,
    showLeadForm: false,
    showAppointmentForm: false,
    leadDraft: {
      name: "",
      phone: "",
      wechat: "",
      remark: ""
    },
    appointmentDraft: buildAppointmentDraft(0),
    leadSubmittedText: "",
    appointmentText: "",
    relaySubmitted: false,
    productOrderSubmitted: false,
    productOrderStatusText: "",
    showRelayForm: false,
    showOrderSheet: false,
    selectedSkuKey: "",
    selectedSkuOptions: {},
    skuSelectionGroups: [],
    relayDraft: {
      quantity: 1,
      receiverName: "",
      phone: "",
      address: "",
      wechat: "",
      remark: ""
    },
    actionStatus: {},
    submittingAction: ""
  },
  onLoad(options) {
    this.setData({
      noteId: options.id || "",
      "leadDraft.phone": readLastLeadPhone()
    });
  },
  onShow() {
    const user = getCurrentUser();
    if (!user) {
      wx.reLaunch({ url: "/pages/login/index" });
      return;
    }
    this.setData({ user });
    this.loadNote();
  },
  async loadNote() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    try {
      const res = await api.fetchNote(noteId, user.id);
      const view = buildView(res.data || {});
      rememberPropertyCity(`${view.address} ${view.title}`);
      this.setData({ view }, () => {
        const sku = view.selectedSku || {};
        const selectedSkuOptions = buildSelectedSkuOptions(view.skuConfig || {}, sku.key || "");
        this.setData({
          selectedSkuKey: sku.key || "",
          selectedSkuOptions,
          skuSelectionGroups: buildSkuSelectionGroups(view.skuConfig || {}, selectedSkuOptions),
          "relayDraft.phone": readLastLeadPhone()
        });
        this.resolveMapFromAddress();
      });
      await this.loadCustomerActionConfig();
    } catch (error) {
      wx.showToast({ title: error.detail || "客户页加载失败", icon: "none" });
    }
  },
  async loadCustomerActionConfig() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    try {
      const res = await api.fetchCustomerActionConfig(noteId, { viewerUserId: user.id });
      const actions = (res.data && res.data.actions) || [];
      const actionStatus = {};
      let submittedPayload = null;
      actions.forEach((item) => {
        if (item.submitted) {
          actionStatus[item.key] = item.statusText || "已提交";
          if (item.key === "order-intent" || item.key === "relay-intent") {
            submittedPayload = item.submittedPayload || null;
          }
        }
      });
      const updateData = {
        actionStatus,
        leadSubmittedText: actionStatus["lead-contact"] || "",
        appointmentText: (actionStatus.appointment || "").replace(/^已预约\s*/, ""),
        relaySubmitted: Boolean(actionStatus["relay-intent"]),
        productOrderSubmitted: Boolean(actionStatus["order-intent"] || actionStatus["relay-intent"]),
        productOrderStatusText: actionStatus["order-intent"] || actionStatus["relay-intent"] || ""
      };
      if (submittedPayload && submittedPayload.skuKey) {
        const view = this.data.view || {};
        const selectedSkuOptions = buildSelectedSkuOptions(view.skuConfig || {}, submittedPayload.skuKey);
        updateData.selectedSkuKey = submittedPayload.skuKey;
        updateData.selectedSkuOptions = selectedSkuOptions;
        updateData.skuSelectionGroups = buildSkuSelectionGroups(view.skuConfig || {}, selectedSkuOptions);
        updateData.relayDraft = {
          ...this.data.relayDraft,
          quantity: submittedPayload.quantity || this.data.relayDraft.quantity,
          receiverName: submittedPayload.receiverName || "",
          phone: submittedPayload.phone || this.data.relayDraft.phone,
          address: submittedPayload.address || "",
          wechat: submittedPayload.wechat || "",
          remark: submittedPayload.remark || ""
        };
      }
      this.setData(updateData);
    } catch (error) {
      this.setData({ actionStatus: {} });
    }
  },
  async resolveMapFromAddress() {
    const view = this.data.view || {};
    const location = view.mapLocation || {};
    if (this.data.resolvingMap || location.hasPoint || !view.address || !view.hasMap) return;
    const mapAddress = enrichAddressWithCity(view.address);
    this.setData({ resolvingMap: true });
    try {
      const res = await api.geocodeAddress({
        address: mapAddress,
        region: inferMapRegion(mapAddress)
      });
      const data = (res && res.data) || {};
      if (!data.found || !data.latitude || !data.longitude) return;
      this.setData({
        "view.mapLocation": buildMapLocation({
          address: view.address,
          mapLocation: {
            name: data.name || view.title || "房源位置",
            address: data.address || mapAddress,
            latitude: data.latitude,
            longitude: data.longitude
          }
        }),
        "view.actions": (view.actions || []).map((item) => (
          item.key === "map" ? { ...item, desc: "打开腾讯地图" } : item
        ))
      });
      rememberPropertyCity(data.address || mapAddress);
    } finally {
      this.setData({ resolvingMap: false });
    }
  },
  handleAction(event) {
    const key = event.currentTarget.dataset.key;
    if (key === "contact" || key === "private") {
      this.handleContact();
      return;
    }
    if (key === "miniapp") {
      this.handleOpenMiniapp();
      return;
    }
    if (key === "lead") {
      this.setData({ showLeadForm: !this.data.showLeadForm });
      return;
    }
    if (key === "appointment") {
      this.handleAppointment();
      return;
    }
    if (key === "map") {
      this.handleOpenMap();
      return;
    }
    if (key === "message") {
      this.handleOpenMessage();
      return;
    }
    if (key === "relay") {
      this.setData({ showRelayForm: !this.data.showRelayForm });
    }
  },
  noop() {},
  handleSelectSku(event) {
    const key = event.currentTarget.dataset.key;
    const soldOut = event.currentTarget.dataset.soldOut;
    if (soldOut === true || soldOut === "true") {
      wx.showToast({ title: "该规格已售罄", icon: "none" });
      return;
    }
    const view = this.data.view || {};
    const selectedSkuOptions = buildSelectedSkuOptions(view.skuConfig || {}, key);
    this.setData({
      selectedSkuKey: key,
      selectedSkuOptions,
      skuSelectionGroups: buildSkuSelectionGroups(view.skuConfig || {}, selectedSkuOptions)
    });
  },
  handleSelectSkuOption(event) {
    const groupId = event.currentTarget.dataset.groupId;
    const groupIndex = Number(event.currentTarget.dataset.groupIndex);
    const optionId = event.currentTarget.dataset.optionId;
    const disabled = event.currentTarget.dataset.disabled;
    if (disabled === true || disabled === "true") {
      wx.showToast({ title: "该选项已售罄", icon: "none" });
      return;
    }
    const view = this.data.view || {};
    const skuConfig = view.skuConfig || {};
    const selectedSkuOptions = {
      ...(this.data.selectedSkuOptions || {}),
      [groupId]: optionId
    };
    let selectedSku = findSkuBySelectedOptions(skuConfig, selectedSkuOptions);
    if (!selectedSku || selectedSku.soldOut) {
      selectedSku = (skuConfig.skus || []).find((sku) => {
        const ids = skuOptionIds(sku);
        return !sku.soldOut && ids[groupIndex] === optionId;
      });
      if (selectedSku) {
        Object.assign(selectedSkuOptions, buildSelectedSkuOptions(skuConfig, selectedSku.key));
      }
    }
    this.setData({
      selectedSkuKey: selectedSku && !selectedSku.soldOut ? selectedSku.key : "",
      selectedSkuOptions,
      skuSelectionGroups: buildSkuSelectionGroups(skuConfig, selectedSkuOptions)
    });
  },
  handleOpenOrderSheet() {
    const view = this.data.view || {};
    const { selectedSkuKey } = this.data;
    if (!selectedSkuKey) {
      wx.showToast({ title: "请选择规格", icon: "none" });
      return;
    }
    const selectedSku = ((view.skuConfig && view.skuConfig.skus) || []).find((item) => item.key === selectedSkuKey);
    if (selectedSku && selectedSku.soldOut) {
      wx.showToast({ title: "该规格已售罄", icon: "none" });
      return;
    }
    this.setData({ showOrderSheet: true });
  },
  handleCloseOrderSheet() {
    if (this.data.submittingAction) return;
    this.setData({ showOrderSheet: false });
  },
  handleRelayInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`relayDraft.${key}`]: event.detail.value });
  },
  async handleSubmitProductOrder() {
    const view = this.data.view || {};
    const { selectedSkuKey, relayDraft } = this.data;
    if (!selectedSkuKey) {
      wx.showToast({ title: "请选择规格", icon: "none" });
      return;
    }
    const selectedSku = ((view.skuConfig && view.skuConfig.skus) || []).find((item) => item.key === selectedSkuKey);
    if (selectedSku && selectedSku.soldOut) {
      wx.showToast({ title: "该规格已售罄", icon: "none" });
      return;
    }
    const quantity = Number(relayDraft.quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      wx.showToast({ title: "请填写数量", icon: "none" });
      return;
    }
    if (!String(relayDraft.phone || "").trim()) {
      wx.showToast({ title: "请填写电话", icon: "none" });
      return;
    }
    if (!String(relayDraft.address || "").trim()) {
      wx.showToast({ title: "请填写地址", icon: "none" });
      return;
    }
    await this.handleSubmitProductIntent(view.enableGroupRelay ? "relay-intent" : "order-intent");
  },
  async handleSubmitProductIntent(actionKey) {
    const { user, noteId, selectedSkuKey, relayDraft } = this.data;
    if (!user || !noteId || this.data.submittingAction) return;
    if (!selectedSkuKey) {
      wx.showToast({ title: "请选择规格", icon: "none" });
      return;
    }
    this.setData({ submittingAction: actionKey });
    try {
      const res = await api.submitCustomerAction(noteId, actionKey, {
        viewerUserId: user.id,
        nickname: user.nickname || "微信用户",
        avatarUrl: user.avatarUrl || "",
        payload: {
          ...relayDraft,
          skuKey: selectedSkuKey
        }
      });
      rememberLeadPhone(relayDraft.phone);
      const statusText = (res.data && res.data.statusText) || (actionKey === "relay-intent" ? "已提交接龙" : "已下单");
      this.setData({
        showRelayForm: false,
        showOrderSheet: false,
        relaySubmitted: actionKey === "relay-intent",
        productOrderSubmitted: true,
        productOrderStatusText: statusText,
        [`actionStatus.${actionKey}`]: statusText
      });
      wx.showToast({ title: actionKey === "relay-intent" ? "已提交接龙" : "已下单", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "提交失败", icon: "none" });
    } finally {
      this.setData({ submittingAction: "" });
    }
  },
  async handleOpenMessage() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    await messagePlugin.openMessageThread({ noteId, buyerUserId: user.id });
  },
  openWechatLocation(location, view) {
    wx.openLocation({
      latitude: Number(location.latitude),
      longitude: Number(location.longitude),
      name: location.name || view.title,
      address: location.address || view.address || ""
    });
  },
  openNavigationApp(location, view) {
    if (!wx.createMapContext) {
      this.openWechatLocation(location, view);
      return;
    }
    const mapContext = wx.createMapContext("previewMap", this);
    if (!mapContext || typeof mapContext.openMapApp !== "function") {
      this.openWechatLocation(location, view);
      return;
    }
    mapContext.openMapApp({
      latitude: Number(location.latitude),
      longitude: Number(location.longitude),
      destination: location.name || view.title || "房源位置",
      fail: () => this.openWechatLocation(location, view)
    });
  },
  copyAddress() {
    const view = this.data.view || {};
    if (!view.address) {
      wx.showToast({ title: "暂无地址", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: view.address,
      success: () => wx.showToast({ title: "地址已复制", icon: "success" })
    });
  },
  handleContact() {
    const contact = this.data.view && this.data.view.contact;
    if (/^1[3-9]\d{9}$/.test(contact || "")) {
      wx.makePhoneCall({ phoneNumber: contact });
      return;
    }
    if (contact) {
      wx.setClipboardData({ data: contact, success: () => wx.showToast({ title: "联系方式已复制", icon: "success" }) });
      return;
    }
    wx.showToast({ title: "暂无联系方式", icon: "none" });
  },
  handleOpenMiniapp() {
    const miniapp = (this.data.view && this.data.view.miniapp) || {};
    if (!miniapp.appId || !miniapp.path) {
      wx.showToast({ title: "暂无小程序路径", icon: "none" });
      return;
    }
    wx.navigateToMiniProgram({
      appId: miniapp.appId,
      path: miniapp.path,
      envVersion: "release",
      fail: () => this.copyMiniappFallback()
    });
  },
  copyMiniappFallback() {
    const miniapp = (this.data.view && this.data.view.miniapp) || {};
    const text = [
      miniapp.title || (this.data.view && this.data.view.title),
      miniapp.sourceName,
      miniapp.houseCode ? `房源编码：${miniapp.houseCode}` : "",
      miniapp.cityId ? `城市编码：${miniapp.cityId}` : ""
    ].filter(Boolean).join("\n");
    if (!text) {
      wx.showToast({ title: "打开失败", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: "已复制房源信息", icon: "success" }),
      fail: () => wx.showToast({ title: "打开失败", icon: "none" })
    });
  },
  handleAppointment() {
    this.setData({
      showAppointmentForm: !this.data.showAppointmentForm,
      appointmentDraft: this.data.appointmentDraft.date ? this.data.appointmentDraft : buildAppointmentDraft(0)
    });
  },
  handleQuickAppointment(event) {
    const offset = Number(event.currentTarget.dataset.offset || 0);
    this.setData({ appointmentDraft: { ...this.data.appointmentDraft, ...buildAppointmentDraft(offset) } });
  },
  handleAppointmentDate(event) {
    this.setData({ "appointmentDraft.date": event.detail.value });
  },
  handleAppointmentTime(event) {
    this.setData({ "appointmentDraft.time": event.detail.value });
  },
  handleAppointmentRemark(event) {
    this.setData({ "appointmentDraft.remark": event.detail.value });
  },
  async handleSubmitAppointment() {
    const draft = this.data.appointmentDraft || {};
    const dateText = formatDateLabel(draft.date);
    const timeText = draft.time || "10:00";
    const remarkText = draft.remark ? `，${draft.remark}` : "";
    const { user, noteId } = this.data;
    if (!user || !noteId || this.data.submittingAction) return;
    this.setData({ submittingAction: "appointment" });
    try {
      const res = await api.submitCustomerAction(noteId, "appointment", {
        viewerUserId: user.id,
        nickname: user.nickname || "",
        avatarUrl: user.avatarUrl || "",
        payload: draft
      });
      this.setData({
        appointmentText: `${dateText} ${timeText}${remarkText}`,
        showAppointmentForm: false,
        "actionStatus.appointment": (res.data && res.data.statusText) || "已预约"
      });
      wx.showToast({ title: "已记录预约意向", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "预约提交失败", icon: "none" });
    } finally {
      this.setData({ submittingAction: "" });
    }
  },
  async handleOpenMap() {
    const view = this.data.view || {};
    let location = view.mapLocation || {};
    await this.resolveMapFromAddress();
    const nextView = this.data.view || view;
    location = nextView.mapLocation || location;
    if (location.latitude && location.longitude) {
      wx.showActionSheet({
        itemList: ["选择导航App", "微信内置地图", "复制地址"],
        success: ({ tapIndex }) => {
          if (tapIndex === 0) this.openNavigationApp(location, nextView);
          if (tapIndex === 1) this.openWechatLocation(location, nextView);
          if (tapIndex === 2) this.copyAddress();
        }
      });
      return;
    }
    if (nextView.address) {
      this.copyAddress();
      return;
    }
    wx.showToast({ title: "暂无定位信息", icon: "none" });
  },
  handleLeadInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [`leadDraft.${key}`]: event.detail.value });
  },
  async handleSubmitLead() {
    if (!this.data.leadDraft.phone.trim() && !this.data.leadDraft.wechat.trim()) {
      wx.showToast({ title: "请填写电话或微信", icon: "none" });
      return;
    }
    const { user, noteId } = this.data;
    if (!user || !noteId || this.data.submittingAction) return;
    this.setData({ submittingAction: "lead-contact" });
    try {
      const res = await api.submitCustomerAction(noteId, "lead-contact", {
        viewerUserId: user.id,
        nickname: user.nickname || this.data.leadDraft.name || "",
        avatarUrl: user.avatarUrl || "",
        payload: this.data.leadDraft
      });
      rememberLeadPhone(this.data.leadDraft.phone);
      this.setData({
        showLeadForm: false,
        leadSubmittedText: (res.data && res.data.statusText) || "已提交联系方式",
        "actionStatus.lead-contact": (res.data && res.data.statusText) || "已提交联系方式"
      });
      wx.showToast({ title: "已提交联系方式", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.detail || "提交失败", icon: "none" });
    } finally {
      this.setData({ submittingAction: "" });
    }
  },
  handleTimelineHint() {
    wx.showModal({
      title: "发朋友圈",
      content: "请点击右上角菜单，选择分享到朋友圈。",
      showCancel: false,
      confirmColor: "#11924d"
    });
  },
  handlePreviewImage(event) {
    const url = event.currentTarget.dataset.url;
    const view = this.data.view || {};
    const urls = [view.coverUrl, ...(view.galleryImages || [])].filter(Boolean);
    if (!url || !urls.length) return;
    wx.previewImage({ current: url, urls });
  },
  onShareAppMessage() {
    const view = this.data.view || {};
    return {
      title: view.title || "资料详情",
      path: `/pages/note-preview/index?id=${this.data.noteId}`,
      imageUrl: view.coverUrl || ""
    };
  },
  onShareTimeline() {
    const view = this.data.view || {};
    return {
      title: view.title || "资料详情",
      query: `id=${this.data.noteId}`,
      imageUrl: view.coverUrl || ""
    };
  }
});
