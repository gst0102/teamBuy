const { buildTitleCoverData } = require("./title-cover");
const api = require("../services/api");

const SHARE_CARD_WIDTH = 750;
const SHARE_CARD_HEIGHT = 420;
const SHARE_CARD_FOOTER = "由资料整理助手生成 · 点击生成同款";

function getCanvasExportSize() {
  let windowWidth = 375;
  try {
    const info = wx.getSystemInfoSync ? wx.getSystemInfoSync() : {};
    windowWidth = Number(info.windowWidth) || windowWidth;
  } catch (error) {
    windowWidth = 375;
  }
  const width = Math.max(300, Math.round(windowWidth));
  const height = Math.round(width * SHARE_CARD_HEIGHT / SHARE_CARD_WIDTH);
  return {
    width,
    height,
    scale: width / SHARE_CARD_WIDTH,
    destWidth: SHARE_CARD_WIDTH,
    destHeight: SHARE_CARD_HEIGHT
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
  return {
    name,
    role,
    company,
    serviceScope,
    contactLine: source.contactLine || preview.contactLine || [phone, wechat].filter(Boolean).join(" · ") || "电话 / 微信",
    avatarUrl: source.avatarUrl || preview.avatarUrl || data.avatarUrl || source.coverUrl || "",
    initial: String(source.initial || preview.initial || name || "名").slice(0, 1),
    templateName: source.templateName || source.displayTemplateName || data.displayTemplateName || "电子名片",
    templateId: source.templateId || source.displayTemplate || data.displayTemplate || "",
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
  return generateNativeShareImage(page, canvasId, {
    title: buildBusinessCardShareTitle(card),
    coverUrl: card.avatarUrl,
    badge: "名片",
    palette: { soft0: "#effaf5", soft1: "#e1f0eb", title: "#145c4a" }
  });
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
