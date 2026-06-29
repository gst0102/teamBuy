const { buildTitleCoverData } = require("./title-cover");
const api = require("../services/api");

const SHARE_CARD_WIDTH = 750;
const SHARE_CARD_HEIGHT = 600;

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

function drawWrappedLines(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
  const value = String(text || "");
  if (!value) return;
  let line = "";
  let lineCount = 0;
  for (const char of value) {
    const next = `${line}${char}`;
    if (line && ctx.measureText && ctx.measureText(next).width > maxWidth) {
      lineCount += 1;
      if (lineCount >= maxLines) {
        drawOneLine(ctx, `${line}${char}`, x, y + (lineCount - 1) * lineHeight, maxWidth);
        return;
      }
      ctx.fillText(line, x, y + (lineCount - 1) * lineHeight);
      line = char;
    } else {
      line = next;
    }
  }
  if (line && lineCount < maxLines) {
    ctx.fillText(line, x, y + lineCount * lineHeight);
  }
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

function resolvePalette(card) {
  if (card.templateId === "consultant_classic" || card.tone === "blue") {
    return { bg0: "#eaf2ff", bg1: "#ffffff", bg2: "#d9e8ff", primary: "#0c2349", text: "#0c2349", bodyText: "#172033", mutedText: "#334155", accent: "#e7b85f", panel: "rgba(255,255,255,0.95)", badgeText: "#ffffff", ctaText: "#ffffff" };
  }
  if (card.templateId === "store_sales_card" || card.tone === "green") {
    return { bg0: "#eaf8ef", bg1: "#fbfffd", bg2: "#d9f2e3", primary: "#477446", text: "#243426", bodyText: "#243426", mutedText: "#516052", accent: "#90d5ad", panel: "rgba(255,255,255,0.95)", badgeText: "#ffffff", ctaText: "#ffffff" };
  }
  if (card.templateId === "expert_personal_brand" || card.tone === "purple") {
    return { bg0: "#11151b", bg1: "#1a2029", bg2: "#0a0d12", primary: "#d2a14b", text: "#f8f1dd", bodyText: "#f5efe0", mutedText: "#d9c58e", accent: "#d2a14b", panel: "rgba(17,21,27,0.96)", badgeText: "#17120a", ctaText: "#17120a" };
  }
  if (card.templateId === "wechat_simple_card" || card.tone === "minimal") {
    return { bg0: "#ffffff", bg1: "#f8fafc", bg2: "#eef2f7", primary: "#4ea65e", text: "#172033", bodyText: "#172033", mutedText: "#667085", accent: "#cbd5e1", panel: "rgba(255,255,255,0.95)", badgeText: "#ffffff", ctaText: "#ffffff" };
  }
  return { bg0: "#effaf5", bg1: "#f7fbf8", bg2: "#e1f0eb", primary: "#145c4a", text: "#123047", bodyText: "#172033", mutedText: "#334155", accent: "#f2c46f", panel: "rgba(255,255,255,0.95)", badgeText: "#ffffff", ctaText: "#ffffff" };
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
  const coverPath = await downloadCanvasImage(property.coverUrl);
  const exportSize = getCanvasExportSize();
  const ctx = wx.createCanvasContext(canvasId, page);

  ctx.save();
  ctx.scale(exportSize.scale, exportSize.scale);

  const bg = ctx.createLinearGradient(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);
  bg.addColorStop(0, "#edf7ff");
  bg.addColorStop(0.58, "#ffffff");
  bg.addColorStop(1, "#eaf7ef");
  ctx.setFillStyle(bg);
  ctx.fillRect(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);

  ctx.setFillStyle("rgba(22, 119, 255, 0.08)");
  ctx.beginPath();
  ctx.arc(634, 84, 150, 0, 2 * Math.PI);
  ctx.fill();
  ctx.setFillStyle("rgba(22, 163, 74, 0.10)");
  ctx.beginPath();
  ctx.arc(80, 520, 126, 0, 2 * Math.PI);
  ctx.fill();

  fillRoundRect(ctx, 42, 50, 666, 408, 38, "rgba(255,255,255,0.96)");
  ctx.setStrokeStyle("rgba(22, 119, 255, 0.16)");
  ctx.setLineWidth(4);
  drawRoundRect(ctx, 42, 50, 666, 408, 38);
  ctx.stroke();

  if (coverPath) {
    ctx.save();
    drawRoundRect(ctx, 76, 92, 260, 292, 30);
    ctx.clip();
    ctx.drawImage(coverPath, 76, 92, 260, 292);
    ctx.restore();
  } else {
    const coverGrd = ctx.createLinearGradient(76, 92, 336, 384);
    coverGrd.addColorStop(0, "#dbeafe");
    coverGrd.addColorStop(1, "#bbf7d0");
    fillRoundRect(ctx, 76, 92, 260, 292, 30, coverGrd);
    ctx.setFillStyle("#17633a");
    ctx.setTextAlign("center");
    ctx.setFontSize(44);
    ctx.fillText("房源", 206, 250);
    ctx.setTextAlign("left");
  }

  fillRoundRect(ctx, 372, 92, 126, 44, 22, "#ecfdf3");
  ctx.setFillStyle("#17633a");
  ctx.setFontSize(23);
  ctx.fillText("房源推荐", 394, 122);

  ctx.setFillStyle("#101828");
  ctx.setFontSize(46);
  drawWrappedLines(ctx, property.title || "房源资料", 372, 190, 278, 54, 2);

  const primaryLine = [property.price, property.layout].filter(Boolean).join(" · ");
  if (primaryLine) {
    fillRoundRect(ctx, 372, 304, 274, 52, 26, "#fff7ed");
    ctx.setFillStyle("#c2410c");
    ctx.setFontSize(28);
    drawOneLine(ctx, primaryLine, 394, 338, 230);
  }

  ctx.setFillStyle("#526070");
  ctx.setFontSize(25);
  drawOneLine(ctx, [property.area, property.address].filter(Boolean).join(" · "), 372, 394, 278);

  fillRoundRect(ctx, 84, 492, 582, 64, 32, "#1677ff");
  ctx.setFillStyle("#ffffff");
  ctx.setFontSize(30);
  ctx.setTextAlign("center");
  ctx.fillText("打开房源 · 看图片 / 预约 / 留下联系方式", 375, 535);
  ctx.setFillStyle("#64748b");
  ctx.setFontSize(22);
  ctx.fillText("由资料整理助手生成", 375, 584);
  ctx.setTextAlign("left");
  ctx.restore();

  return exportShareCanvas(page, canvasId, ctx, exportSize);
}

async function generateBusinessCardShareImage(page, canvasId, source) {
  const card = normalizeBusinessCardShareSource(source);
  const palette = resolvePalette(card);
  const avatarPath = await downloadCanvasImage(card.avatarUrl);
  const exportSize = getCanvasExportSize();
  const ctx = wx.createCanvasContext(canvasId, page);

  ctx.save();
  ctx.scale(exportSize.scale, exportSize.scale);

  ctx.setFillStyle("#eef6f2");
  ctx.fillRect(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);

  const grd = ctx.createLinearGradient(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);
  grd.addColorStop(0, palette.bg0);
  grd.addColorStop(0.55, palette.bg1);
  grd.addColorStop(1, palette.bg2);
  ctx.setFillStyle(grd);
  ctx.fillRect(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);

  ctx.setFillStyle("rgba(28, 91, 72, 0.08)");
  ctx.beginPath();
  ctx.arc(626, 100, 164, 0, 2 * Math.PI);
  ctx.fill();
  ctx.setFillStyle("rgba(255, 255, 255, 0.52)");
  ctx.beginPath();
  ctx.arc(644, 118, 104, 0, 2 * Math.PI);
  ctx.fill();

  fillRoundRect(ctx, 42, 52, 666, 398, 38, palette.panel || "rgba(255,255,255,0.94)");
  ctx.setStrokeStyle("rgba(22, 92, 74, 0.26)");
  ctx.setLineWidth(4);
  drawRoundRect(ctx, 42, 52, 666, 398, 38);
  ctx.stroke();

  fillRoundRect(ctx, 536, 82, 120, 42, 21, "rgba(20, 92, 74, 0.1)");
  ctx.setFillStyle(palette.primary);
  ctx.setFontSize(22);
  ctx.setTextAlign("center");
  ctx.fillText("电子名片", 596, 110);
  ctx.setTextAlign("left");

  ctx.save();
  ctx.beginPath();
  ctx.arc(184, 238, 104, 0, 2 * Math.PI);
  ctx.clip();
  if (avatarPath) {
    ctx.drawImage(avatarPath, 80, 134, 208, 208);
  } else {
    const avatarGrd = ctx.createLinearGradient(80, 134, 288, 342);
    avatarGrd.addColorStop(0, "#2670d9");
    avatarGrd.addColorStop(1, "#36b37e");
    ctx.setFillStyle(avatarGrd);
    ctx.fillRect(80, 134, 208, 208);
    ctx.setFillStyle("#ffffff");
    ctx.setTextAlign("center");
    ctx.setFontSize(78);
    ctx.fillText(card.initial || "名", 184, 266);
    ctx.setTextAlign("left");
  }
  ctx.restore();

  ctx.setStrokeStyle(palette.accent);
  ctx.setLineWidth(7);
  ctx.beginPath();
  ctx.arc(184, 238, 109, 0, 2 * Math.PI);
  ctx.stroke();

  ctx.setFillStyle("#f5bf48");
  ctx.beginPath();
  ctx.moveTo(292, 112);
  ctx.lineTo(305, 142);
  ctx.lineTo(335, 155);
  ctx.lineTo(305, 168);
  ctx.lineTo(292, 198);
  ctx.lineTo(279, 168);
  ctx.lineTo(249, 155);
  ctx.lineTo(279, 142);
  ctx.closePath();
  ctx.fill();

  ctx.setFillStyle(palette.text);
  ctx.setFontSize(62);
  drawOneLine(ctx, card.name || "电子名片", 338, 168, 308);

  fillRoundRect(ctx, 338, 208, 224, 54, 27, palette.primary);
  ctx.setFillStyle("#fff7d9");
  ctx.setFontSize(26);
  ctx.fillText("●", 360, 243);
  ctx.setFillStyle(palette.badgeText || "#ffffff");
  drawOneLine(ctx, card.role || "个人顾问", 390, 243, 148);

  ctx.setFillStyle(palette.bodyText || "#172033");
  ctx.setFontSize(31);
  drawOneLine(ctx, card.company || "个人服务", 338, 314, 326);
  ctx.setFillStyle(palette.mutedText || "#334155");
  ctx.setFontSize(29);
  drawOneLine(ctx, card.serviceScope || "", 338, 360, 326);
  ctx.setFillStyle(palette.primary);
  ctx.setFontSize(27);
  drawOneLine(ctx, card.contactLine || "电话 / 微信", 338, 406, 326);

  fillRoundRect(ctx, 84, 488, 582, 64, 32, palette.primary);
  ctx.setFillStyle(palette.ctaText || "#ffffff");
  ctx.setFontSize(30);
  ctx.setTextAlign("center");
  ctx.fillText("打开名片 · 电话 / 微信 / 留下联系方式", 375, 540);
  ctx.setTextAlign("left");
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

function resolveServicePalette(card) {
  if (card.templateId === "service_pricing") {
    return { bg0: "#e9f7eb", bg1: "#ffffff", bg2: "#d4ead6", primary: "#17633a", text: "#173723", muted: "#52675a", accent: "#22c55e", panel: "rgba(255,255,255,0.95)", ctaText: "#ffffff" };
  }
  if (card.templateId === "service_case_story") {
    return { bg0: "#fff7e8", bg1: "#ffffff", bg2: "#f4d9a2", primary: "#8a4b11", text: "#3b260e", muted: "#76552b", accent: "#d99432", panel: "rgba(255,255,255,0.95)", ctaText: "#ffffff" };
  }
  if (card.templateId === "service_campaign") {
    return { bg0: "#6b1d1d", bg1: "#a13a20", bg2: "#d66b2b", primary: "#ffffff", text: "#ffffff", muted: "#fff1dc", accent: "#ffd166", panel: "rgba(255,255,255,0.14)", ctaText: "#6b1d1d" };
  }
  return { bg0: "#0f2a4c", bg1: "#1761a0", bg2: "#e8f2ff", primary: "#ffffff", text: "#ffffff", muted: "#d9ecff", accent: "#8dd3ff", panel: "rgba(255,255,255,0.14)", ctaText: "#0f2a4c" };
}

function buildServiceOfferShareTitle(source) {
  const card = normalizeServiceOfferShareSource(source);
  return [card.title, card.headline].filter(Boolean).join(" · ") || "服务方案";
}

async function generateServiceOfferShareImage(page, canvasId, source) {
  const card = normalizeServiceOfferShareSource(source);
  const palette = resolveServicePalette(card);
  const coverPath = await downloadCanvasImage(card.coverUrl);
  const exportSize = getCanvasExportSize();
  const ctx = wx.createCanvasContext(canvasId, page);

  ctx.save();
  ctx.scale(exportSize.scale, exportSize.scale);

  const grd = ctx.createLinearGradient(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);
  grd.addColorStop(0, palette.bg0);
  grd.addColorStop(0.55, palette.bg1);
  grd.addColorStop(1, palette.bg2);
  ctx.setFillStyle(grd);
  ctx.fillRect(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);

  ctx.setFillStyle(card.templateId === "service_campaign" || card.templateId === "service_consultation" ? "rgba(255,255,255,0.16)" : "rgba(22,163,74,0.10)");
  ctx.beginPath();
  ctx.arc(640, 92, 164, 0, 2 * Math.PI);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(76, 516, 120, 0, 2 * Math.PI);
  ctx.fill();

  fillRoundRect(ctx, 42, 50, 666, 408, 38, palette.panel);
  ctx.setStrokeStyle(card.templateId === "service_campaign" || card.templateId === "service_consultation" ? "rgba(255,255,255,0.30)" : "rgba(22,163,74,0.18)");
  ctx.setLineWidth(4);
  drawRoundRect(ctx, 42, 50, 666, 408, 38);
  ctx.stroke();

  if (coverPath) {
    ctx.save();
    drawRoundRect(ctx, 78, 94, 206, 246, 28);
    ctx.clip();
    ctx.drawImage(coverPath, 78, 94, 206, 246);
    ctx.restore();
  } else {
    const coverGrd = ctx.createLinearGradient(78, 94, 284, 340);
    coverGrd.addColorStop(0, palette.accent);
    coverGrd.addColorStop(1, palette.bg2);
    fillRoundRect(ctx, 78, 94, 206, 246, 28, coverGrd);
    ctx.setFillStyle(card.templateId === "service_campaign" || card.templateId === "service_consultation" ? "#ffffff" : palette.text);
    ctx.setTextAlign("center");
    ctx.setFontSize(42);
    ctx.fillText(card.scene || "服务", 181, 232);
    ctx.setTextAlign("left");
  }

  fillRoundRect(ctx, 328, 96, 170, 46, 23, card.templateId === "service_campaign" || card.templateId === "service_consultation" ? "rgba(255,255,255,0.18)" : "rgba(22,163,74,0.12)");
  ctx.setFillStyle(palette.text);
  ctx.setFontSize(24);
  drawOneLine(ctx, card.templateName || "服务方案", 350, 127, 130);

  ctx.setFillStyle(palette.text);
  ctx.setFontSize(56);
  drawOneLine(ctx, card.title, 328, 202, 318);
  ctx.setFillStyle(palette.muted);
  ctx.setFontSize(30);
  drawOneLine(ctx, card.headline, 328, 258, 318);

  ctx.setFillStyle(palette.text);
  ctx.setFontSize(26);
  drawOneLine(ctx, `适合：${card.audience}`, 328, 320, 318);
  drawOneLine(ctx, `报价：${card.pricing}`, 328, 366, 318);

  fillRoundRect(ctx, 84, 492, 582, 64, 32, palette.accent);
  ctx.setFillStyle(palette.ctaText || "#ffffff");
  ctx.setFontSize(30);
  ctx.setTextAlign("center");
  ctx.fillText("打开方案 · 咨询 / 留言 / 预约沟通", 375, 535);
  ctx.setTextAlign("left");
  ctx.restore();

  return exportShareCanvas(page, canvasId, ctx, exportSize);
}

async function generateTitleShareImage(page, canvasId, source = {}) {
  const cover = buildTitleCoverData(source.title || source.summary || "资料", source.badge || "资料");
  const coverPath = await downloadCanvasImage(source.coverUrl || "");
  const exportSize = getCanvasExportSize();
  const ctx = wx.createCanvasContext(canvasId, page);
  const shareTargetLabel = String(source.shareTargetLabel || source.badge || "").includes("合集") ? "合集" : "资料";
  const primaryCta = source.hint || `打开小程序查看完整${shareTargetLabel}`;
  const secondaryCta = source.growthHint || "我也想做同款";
  const palettes = [
    { bg0: "#edf7ff", bg1: "#ffffff", bg2: "#dbeafe", badgeBg: "#e0f2fe", badgeText: "#075985", title: "#0f172a", sub: "#475467", accent: "#1677ff" },
    { bg0: "#effcf3", bg1: "#ffffff", bg2: "#dcfce7", badgeBg: "#dcfce7", badgeText: "#166534", title: "#052e16", sub: "#3f5a47", accent: "#16a34a" },
    { bg0: "#fff8ef", bg1: "#ffffff", bg2: "#ffedd5", badgeBg: "#ffedd5", badgeText: "#9a3412", title: "#431407", sub: "#7c5b3e", accent: "#f97316" },
    { bg0: "#f7f5ff", bg1: "#ffffff", bg2: "#ede9fe", badgeBg: "#ede9fe", badgeText: "#5b21b6", title: "#1f1147", sub: "#5b5377", accent: "#7c3aed" }
  ];
  const palette = palettes[cover.tone] || palettes[0];

  ctx.save();
  ctx.scale(exportSize.scale, exportSize.scale);

  const bg = ctx.createLinearGradient(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);
  bg.addColorStop(0, palette.bg0);
  bg.addColorStop(0.55, palette.bg1);
  bg.addColorStop(1, palette.bg2);
  ctx.setFillStyle(bg);
  ctx.fillRect(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);

  ctx.setFillStyle("rgba(255,255,255,0.55)");
  ctx.beginPath();
  ctx.arc(642, 86, 132, 0, 2 * Math.PI);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(84, 530, 148, 0, 2 * Math.PI);
  ctx.fill();

  fillRoundRect(ctx, 48, 56, 654, 488, 40, "rgba(255,255,255,0.94)");
  ctx.setStrokeStyle("rgba(148, 163, 184, 0.16)");
  ctx.setLineWidth(3);
  drawRoundRect(ctx, 48, 56, 654, 488, 40);
  ctx.stroke();

  fillRoundRect(ctx, 84, 96, 120, 44, 22, palette.badgeBg);
  ctx.setFillStyle(palette.badgeText);
  ctx.setFontSize(24);
  ctx.fillText(cover.badge, 112, 126);

  if (coverPath) {
    ctx.save();
    drawRoundRect(ctx, 84, 160, 244, 244, 30);
    ctx.clip();
    ctx.drawImage(coverPath, 84, 160, 244, 244);
    ctx.restore();

    ctx.setFillStyle(palette.title);
    ctx.setFontSize(54);
    drawWrappedLines(ctx, source.title || cover.focusText || "资料", 360, 214, 270, 64, 2);

    ctx.setFillStyle(palette.sub);
    ctx.setFontSize(28);
    drawWrappedLines(ctx, source.summary || "打开查看完整资料", 360, 350, 270, 38, 2);
  } else {
    ctx.setFillStyle(palette.title);
    ctx.setFontSize(78);
    drawWrappedLines(ctx, cover.focusText || "资料", 84, 240, 470, 94, 2);

    ctx.setFillStyle(palette.sub);
    ctx.setFontSize(30);
    drawWrappedLines(ctx, source.title || source.summary || "打开查看完整资料", 84, 404, 500, 42, 2);
  }

  fillRoundRect(ctx, 84, 446, 502, 64, 32, palette.accent);
  ctx.setFillStyle("#ffffff");
  ctx.setFontSize(30);
  ctx.setTextAlign("center");
  drawOneLine(ctx, primaryCta, 335, 488, 430);

  ctx.setFillStyle(`${palette.title}99`);
  ctx.setFontSize(22);
  drawOneLine(ctx, secondaryCta, 335, 544, 260);

  ctx.setFillStyle(palette.accent);
  ctx.setFontSize(164);
  ctx.fillText((cover.focusText || "资料").slice(0, 1), 592, 340);

  ctx.setFillStyle("#667085");
  ctx.setFontSize(22);
  ctx.fillText("来自资料整理助手", 375, 574);
  ctx.setTextAlign("left");
  ctx.restore();

  return exportShareCanvas(page, canvasId, ctx, exportSize);
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
