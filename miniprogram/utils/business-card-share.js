const { buildTitleCoverData } = require("./title-cover");
const { getSalesPageTemplate } = require("./sales-page-templates");
const api = require("../services/api");

const SHARE_CARD_WIDTH = 750;
const SHARE_CARD_HEIGHT = 420;
const BUSINESS_CARD_SHARE_WIDTH = 600;
const BUSINESS_CARD_SHARE_HEIGHT = 480;
const SHARE_CARD_FOOTER = "由资料整理助手生成 · 点击生成同款";

function getCanvasExportSize(baseWidth = SHARE_CARD_WIDTH, baseHeight = SHARE_CARD_HEIGHT) {
  let windowWidth = 375;
  try {
    const info = wx.getSystemInfoSync ? wx.getSystemInfoSync() : {};
    windowWidth = Number(info.windowWidth) || windowWidth;
  } catch (error) {
    windowWidth = 375;
  }
  const width = Math.max(300, Math.round(windowWidth));
  const height = Math.round(width * baseHeight / baseWidth);
  return {
    width,
    height,
    scale: width / baseWidth,
    destWidth: baseWidth,
    destHeight: baseHeight
  };
}

function getShareOwnerUserId() {
  try {
    const app = getApp ? getApp() : null;
    const user = (app && app.globalData && app.globalData.currentUser) || wx.getStorageSync("currentUser") || {};
    return user.id || "";
  } catch (error) {
    return "";
  }
}

async function uploadShareImage(filePath) {
  if (!filePath || /^https:\/\//i.test(filePath)) return filePath || "";
  try {
    const uploaded = await api.uploadAsset({
      filePath,
      mediaType: "image",
      ownerUserId: getShareOwnerUserId()
    });
    return uploaded && uploaded.url ? uploaded.url : filePath;
  } catch (error) {
    return filePath;
  }
}

function exportShareCanvas(page, canvasId, ctx, exportSize) {
  return new Promise((resolve, reject) => {
    ctx.draw(false, () => {
      wx.canvasToTempFilePath({
        canvasId,
        width: exportSize.width,
        height: exportSize.height,
        destWidth: exportSize.destWidth,
        destHeight: exportSize.destHeight,
        success: async (res) => {
          try {
            resolve(await uploadShareImage(res.tempFilePath || ""));
          } catch (error) {
            resolve(res.tempFilePath || "");
          }
        },
        fail: reject
      }, page);
    });
  });
}

function drawRoundRect(ctx, x, y, width, height, radius) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.arc(x + width - radius, y + radius, radius, 1.5 * Math.PI, 0);
  ctx.lineTo(x + width, y + height - radius);
  ctx.arc(x + width - radius, y + height - radius, radius, 0, 0.5 * Math.PI);
  ctx.lineTo(x + radius, y + height);
  ctx.arc(x + radius, y + height - radius, radius, 0.5 * Math.PI, Math.PI);
  ctx.lineTo(x, y + radius);
  ctx.arc(x + radius, y + radius, radius, Math.PI, 1.5 * Math.PI);
  ctx.closePath();
}

function fillRoundRect(ctx, x, y, width, height, radius, color) {
  drawRoundRect(ctx, x, y, width, height, radius);
  ctx.setFillStyle(color);
  ctx.fill();
}

function drawOneLine(ctx, text, x, y, maxWidth) {
  const value = String(text || "");
  if (!value) return;
  if (!ctx.measureText || ctx.measureText(value).width <= maxWidth) {
    ctx.fillText(value, x, y);
    return;
  }
  let next = "";
  for (const char of value) {
    if (ctx.measureText(`${next}${char}...`).width > maxWidth) break;
    next += char;
  }
  ctx.fillText(`${next}...`, x, y);
}

function buildShareTitle(title, suffix = "") {
  const value = String(title || "").trim();
  if (!value) return suffix || "资料详情";
  if (suffix && !value.includes(suffix)) return `${value}${suffix}`;
  return value;
}

function drawNativeNoImageCover(ctx, source = {}, palette = {}) {
  const cover = buildTitleCoverData(source.title || source.summary || "资料", source.badge || "资料");
  const bg = ctx.createLinearGradient(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);
  bg.addColorStop(0, palette.soft0 || "#f7fbff");
  bg.addColorStop(1, palette.soft1 || "#e7f0ff");
  ctx.setFillStyle(bg);
  ctx.fillRect(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);

  fillRoundRect(ctx, 154, 122, 442, 126, 28, "rgba(255,255,255,0.92)");
  ctx.setFillStyle(palette.title || "#1f2937");
  ctx.setTextAlign("center");
  ctx.setFontSize(64);
  drawOneLine(ctx, cover.focusText || "资料", 375, 204, 340);
  ctx.setTextAlign("left");
}

function getLocalImageInfo(path) {
  return new Promise((resolve) => {
    if (!path) {
      resolve(null);
      return;
    }
    wx.getImageInfo({
      src: path,
      success: (res) => resolve(res),
      fail: () => resolve(null)
    });
  });
}

async function drawNativeImageCover(ctx, imagePath, palette = {}) {
  if (!imagePath) return false;
  const info = await getLocalImageInfo(imagePath);
  const sourceWidth = Number(info && info.width) || SHARE_CARD_WIDTH;
  const sourceHeight = Number(info && info.height) || SHARE_CARD_HEIGHT;
  const targetRatio = SHARE_CARD_WIDTH / SHARE_CARD_HEIGHT;
  const sourceRatio = sourceWidth / sourceHeight;
  let sx = 0;
  let sy = 0;
  let sw = sourceWidth;
  let sh = sourceHeight;
  if (sourceRatio > targetRatio) {
    sw = sourceHeight * targetRatio;
    sx = (sourceWidth - sw) / 2;
  } else if (sourceRatio < targetRatio) {
    sh = sourceWidth / targetRatio;
    sy = (sourceHeight - sh) / 2;
  }
  ctx.drawImage(imagePath, sx, sy, sw, sh, 0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);
  return true;
}

function drawCoverFooterHook(ctx) {
  ctx.setFillStyle("rgba(255,255,255,0.92)");
  ctx.fillRect(0, 360, SHARE_CARD_WIDTH, 60);
  ctx.setFillStyle("#667085");
  ctx.setFontSize(28);
  drawOneLine(ctx, SHARE_CARD_FOOTER, 34, 399, 690);
}

function businessCardPalette(templateId) {
  if (templateId === "store_sales_card") {
    return {
      bg0: "#f3fbf6",
      bg1: "#ffffff",
      card0: "#eef9f1",
      card1: "#ffffff",
      text: "#123528",
      subText: "#4b6659",
      accent: "#128f4b",
      chipBg: "#dff6e8",
      chipText: "#0d7a3e",
      qrBg: "#2f7d48",
      qrText: "#ffffff",
      border: "#bce8ce",
      avatarBg: "#dff6e8"
    };
  }
  if (templateId === "expert_personal_brand") {
    return {
      bg0: "#fbf8ef",
      bg1: "#ffffff",
      card0: "#101216",
      card1: "#2a2318",
      text: "#ffffff",
      subText: "#ead9ad",
      accent: "#d5ad59",
      chipBg: "rgba(213,173,89,0.18)",
      chipText: "#f1d890",
      qrBg: "#d5ad59",
      qrText: "#111827",
      border: "#ead9ad",
      avatarBg: "#2f3440"
    };
  }
  if (templateId === "wechat_simple_card") {
    return {
      bg0: "#f7f8fa",
      bg1: "#ffffff",
      card0: "#ffffff",
      card1: "#ffffff",
      text: "#172033",
      subText: "#687281",
      accent: "#1aad19",
      chipBg: "#edf8ee",
      chipText: "#168f2f",
      qrBg: "#172033",
      qrText: "#ffffff",
      border: "#e5eaf0",
      avatarBg: "#eef2f7"
    };
  }
  return {
    bg0: "#eef6ff",
    bg1: "#ffffff",
    card0: "#0f3365",
    card1: "#193f77",
    text: "#ffffff",
    subText: "#d8e7ff",
    accent: "#f1cc6b",
    chipBg: "rgba(241,204,107,0.2)",
    chipText: "#ffe29a",
    qrBg: "#f1cc6b",
    qrText: "#152542",
    border: "#d7e7ff",
    avatarBg: "#dbeafe"
  };
}

function drawCircleAvatar(ctx, imagePath, card, x, y, size, palette) {
  ctx.save();
  ctx.beginPath();
  ctx.arc(x + size / 2, y + size / 2, size / 2, 0, Math.PI * 2);
  ctx.clip();
  if (imagePath) {
    ctx.drawImage(imagePath, x, y, size, size);
  } else {
    ctx.setFillStyle("#f8fafc");
    ctx.fillRect(x, y, size, size);
    ctx.setFillStyle(palette.accent);
    ctx.setTextAlign("center");
    ctx.setFontSize(Math.round(size * 0.42));
    ctx.fillText(card.initial || "名", x + size / 2, y + size * 0.66);
    ctx.setTextAlign("left");
  }
  ctx.restore();
  ctx.setStrokeStyle("rgba(255,255,255,0.9)");
  ctx.setLineWidth(5);
  ctx.beginPath();
  ctx.arc(x + size / 2, y + size / 2, size / 2 - 2, 0, Math.PI * 2);
  ctx.stroke();
}

function drawBusinessCardPreview(ctx, card, avatarPath) {
  const width = BUSINESS_CARD_SHARE_WIDTH;
  const height = BUSINESS_CARD_SHARE_HEIGHT;
  const palette = businessCardPalette(card.templateId);
  const bg = ctx.createLinearGradient(0, 0, width, height);
  bg.addColorStop(0, palette.bg0);
  bg.addColorStop(1, palette.bg1);
  ctx.setFillStyle(bg);
  ctx.fillRect(0, 0, width, height);

  const outerX = 42;
  const outerY = 42;
  const outerW = 516;
  const outerH = 370;
  const innerX = 68;
  const innerY = 68;
  const innerW = 464;
  const innerH = 252;

  fillRoundRect(ctx, outerX, outerY, outerW, outerH, 26, "#ffffff");
  ctx.setStrokeStyle(palette.border);
  ctx.setLineWidth(2);
  drawRoundRect(ctx, outerX, outerY, outerW, outerH, 26);
  ctx.stroke();

  const cardBg = ctx.createLinearGradient(innerX, innerY, innerX + innerW, innerY + innerH);
  cardBg.addColorStop(0, palette.card0);
  cardBg.addColorStop(1, palette.card1);
  fillRoundRect(ctx, innerX, innerY, innerW, innerH, 22, palette.card0);
  drawRoundRect(ctx, innerX, innerY, innerW, innerH, 22);
  ctx.setFillStyle(cardBg);
  ctx.fill();

  ctx.setFillStyle("rgba(255,255,255,0.14)");
  ctx.beginPath();
  ctx.arc(innerX + innerW - 46, innerY + 42, 64, 0, Math.PI * 2);
  ctx.fill();

  drawCircleAvatar(ctx, avatarPath, card, innerX + 28, innerY + 46, 92, palette);

  ctx.setFillStyle(palette.text);
  ctx.setFontSize(46);
  drawOneLine(ctx, card.name || "电子名片", innerX + 146, innerY + 74, 244);

  ctx.setFillStyle(palette.subText);
  ctx.setFontSize(24);
  drawOneLine(ctx, card.role || "个人顾问", innerX + 148, innerY + 112, 220);

  fillRoundRect(ctx, innerX + 148, innerY + 128, 140, 34, 17, palette.chipBg);
  ctx.setFillStyle(palette.chipText);
  ctx.setFontSize(20);
  drawOneLine(ctx, card.templateName || "电子名片", innerX + 170, innerY + 152, 96);

  ctx.setFillStyle(palette.subText);
  ctx.setFontSize(23);
  drawOneLine(ctx, card.company || "个人服务", innerX + 30, innerY + 196, 300);
  drawOneLine(ctx, card.contactLine || "电话 / 微信", innerX + 30, innerY + 232, 332);

  fillRoundRect(ctx, innerX + innerW - 72, innerY + 154, 52, 64, 10, palette.qrBg);
  ctx.setFillStyle(palette.qrText);
  ctx.setTextAlign("center");
  ctx.setFontSize(22);
  ctx.fillText("码", innerX + innerW - 46, innerY + 196);
  ctx.setTextAlign("left");

  ctx.setFillStyle("#111827");
  ctx.setFontSize(34);
  drawOneLine(ctx, card.templateName || "电子名片", outerX + 28, innerY + innerH + 52, 190);
  ctx.setFillStyle("#667085");
  ctx.setFontSize(23);
  drawOneLine(ctx, card.serviceScope || card.role || "适合快速转发和客户沟通", outerX + 28, innerY + innerH + 88, 360);
  fillRoundRect(ctx, outerX + outerW - 96, innerY + innerH + 42, 66, 40, 20, "#eef6ff");
  ctx.setFillStyle("#1677ff");
  ctx.setFontSize(22);
  drawOneLine(ctx, "查看", outerX + outerW - 78, innerY + innerH + 69, 40);

  ctx.setFillStyle("#667085");
  ctx.setFontSize(24);
  drawOneLine(ctx, SHARE_CARD_FOOTER, 62, 450, 476);
}

async function generateNativeShareImage(page, canvasId, source = {}) {
  const exportSize = getCanvasExportSize();
  const ctx = wx.createCanvasContext(canvasId, page);
  const coverPath = await downloadCanvasImage(source.coverUrl || source.avatarUrl || "");
  const palette = source.palette || {};

  ctx.save();
  ctx.scale(exportSize.scale, exportSize.scale);

  ctx.setFillStyle("#ffffff");
  ctx.fillRect(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);

  if (!(await drawNativeImageCover(ctx, coverPath, palette))) {
    drawNativeNoImageCover(ctx, source, palette);
  }
  drawCoverFooterHook(ctx);

  ctx.restore();
  return exportShareCanvas(page, canvasId, ctx, exportSize);
}

function downloadCanvasImage(url) {
  return new Promise((resolve) => {
    if (!url) {
      resolve("");
      return;
    }
    if (/^(wxfile|file):/i.test(url)) {
      resolve(url);
      return;
    }
    if (url.startsWith("/")) {
      wx.getImageInfo({
        src: url,
        success: (res) => resolve(res.path || url),
        fail: () => resolve(url)
      });
      return;
    }
    if (!/^https:\/\//i.test(url)) {
      resolve("");
      return;
    }
    wx.downloadFile({
      url,
      success: (res) => resolve(res.tempFilePath || ""),
      fail: () => resolve("")
    });
  });
}

function normalizeBusinessCardShareSource(source = {}) {
  const data = source.structuredData || {};
  const preview = source.businessCardPreview || {};
  const name = source.name || preview.name || data.name || source.title || "电子名片";
  const role = source.role || preview.role || data.title || "个人顾问";
  const company = source.company || preview.company || data.company || "个人服务";
  const phone = source.phone || data.phone || source.contactPhone || "";
  const wechat = source.wechat || data.wechat || data.contactWechat || source.contactWechat || "";
  const serviceScope = source.serviceScope || preview.serviceScope || data.serviceScope || data.headline || source.summary || "微信资料整理 / 私域效率工具";
  const templateId = source.templateId || source.displayTemplate || data.displayTemplate || "";
  const template = getSalesPageTemplate(templateId);
  const templatePreview = (template && template.preview) || {};
  return {
    name,
    role,
    company,
    serviceScope,
    contactLine: source.contactLine || preview.contactLine || [phone, wechat].filter(Boolean).join(" · ") || "电话 / 微信",
    avatarUrl: source.avatarUrl || preview.avatarUrl || data.avatarUrl || source.coverUrl || templatePreview.avatarUrl || "",
    initial: String(source.initial || preview.initial || name || "名").slice(0, 1),
    templateName: source.templateName || source.displayTemplateName || data.displayTemplateName || "电子名片",
    templateId,
    tone: source.tone || data.tone || ""
  };
}

function buildBusinessCardShareTitle(card) {
  const normalized = normalizeBusinessCardShareSource(card);
  if (normalized.name && normalized.name !== "电子名片") return `${normalized.name}的电子名片`;
  return [normalized.role, normalized.company].filter(Boolean).join(" · ") || "电子名片";
}

function normalizePropertyShareSource(source = {}) {
  const data = source.structuredData || {};
  const title = source.title || data.title || data.community || "房源资料";
  const price = source.price || data.price || "";
  const layout = source.layout || data.layout || "";
  const area = source.area || data.area || "";
  const address = source.address || data.address || data.businessArea || "";
  const coverUrl = source.coverUrl || data.coverUrl || "";
  return {
    title,
    price: price && !String(price).startsWith("租金") ? `租金 ${price}` : price,
    layout: layout && !String(layout).startsWith("户型") ? `户型 ${layout}` : layout,
    area,
    address,
    coverUrl,
    locationLine: [address, data.subway, data.businessArea].filter(Boolean).join(" · "),
    contactLine: source.contactLine || data.contact || data.phone || data.contactPhone || ""
  };
}

async function generatePropertyShareImage(page, canvasId, source) {
  const property = normalizePropertyShareSource(source);
  return generateNativeShareImage(page, canvasId, {
    title: property.title || "房源资料",
    coverUrl: property.coverUrl,
    badge: "房源",
    palette: { soft0: "#edf7ff", soft1: "#dbeafe", title: "#1765c2" }
  });
}

async function generateBusinessCardShareImage(page, canvasId, source) {
  const card = normalizeBusinessCardShareSource(source);
  const exportSize = getCanvasExportSize(BUSINESS_CARD_SHARE_WIDTH, BUSINESS_CARD_SHARE_HEIGHT);
  const ctx = wx.createCanvasContext(canvasId, page);
  const downloadedAvatar = await downloadCanvasImage(card.avatarUrl || "");
  const avatarInfo = await getLocalImageInfo(downloadedAvatar);
  const drawableAvatar = avatarInfo ? (avatarInfo.path || downloadedAvatar) : "";
  ctx.save();
  ctx.scale(exportSize.scale, exportSize.scale);
  drawBusinessCardPreview(ctx, card, drawableAvatar);
  ctx.restore();
  return exportShareCanvas(page, canvasId, ctx, exportSize);
}

function normalizeServiceOfferShareSource(source = {}) {
  const data = source.structuredData || {};
  const detail = source.serviceOfferDetail || {};
  const title = source.serviceName || detail.serviceName || data.serviceName || source.title || "服务方案";
  const headline = source.headline || detail.headline || data.headline || source.summary || "先了解服务价值，再预约沟通";
  const audience = source.targetAudience || detail.targetAudience || data.targetAudience || "适合需要专业服务的客户";
  const pricing = source.pricingNote || detail.pricingNote || data.pricingNote || "按需求沟通报价";
  const templateId = source.templateId || source.displayTemplate || data.displayTemplate || "";
  return {
    title,
    headline,
    audience,
    pricing,
    scene: source.scene || detail.scene || source.templateScene || "",
    templateName: source.templateName || detail.templateName || source.displayTemplateName || "服务方案",
    coverUrl: source.coverUrl || detail.coverUrl || data.coverUrl || "",
    templateId
  };
}

function buildServiceOfferShareTitle(source) {
  const card = normalizeServiceOfferShareSource(source);
  return [card.title, card.headline].filter(Boolean).join(" · ") || "服务方案";
}

async function generateServiceOfferShareImage(page, canvasId, source) {
  const card = normalizeServiceOfferShareSource(source);
  return generateNativeShareImage(page, canvasId, {
    title: card.title || "服务方案",
    coverUrl: card.coverUrl,
    badge: "方案",
    palette: { soft0: "#eef7ff", soft1: "#e8f2ff", title: "#1761a0" }
  });
}

async function generateTitleShareImage(page, canvasId, source = {}) {
  const shareTargetLabel = String(source.shareTargetLabel || source.badge || "").includes("合集") ? "合集" : "资料";
  return generateNativeShareImage(page, canvasId, {
    title: buildShareTitle(source.title || "资料详情", shareTargetLabel === "合集" ? "合集" : ""),
    coverUrl: source.coverUrl || "",
    badge: source.badge || shareTargetLabel,
    palette: shareTargetLabel === "合集"
      ? { soft0: "#fff8ef", soft1: "#ffedd5", title: "#9a3412" }
      : { soft0: "#f7fbff", soft1: "#e7f0ff", title: "#1765c2" }
  });
}

module.exports = {
  SHARE_CARD_WIDTH,
  SHARE_CARD_HEIGHT,
  buildBusinessCardShareTitle,
  buildServiceOfferShareTitle,
  generatePropertyShareImage,
  generateBusinessCardShareImage,
  generateServiceOfferShareImage,
  generateTitleShareImage,
  normalizeBusinessCardShareSource
};
