const api = require("../services/api");

const SHARE_CARD_WIDTH = 750;
// WeChat's mini-program message thumbnail uses a 5:4 preview frame. Keep the
// generated information cards at the same ratio so the platform does not
// crop the right side of long titles and service details.
const SHARE_CARD_HEIGHT = 600;
const SHARE_CARD_FOOTER = "资料整理助手 · 点击查看完整资料";
const RESOURCE_DEFAULT_SHARE_WIDTH = 750;
const RESOURCE_DEFAULT_SHARE_HEIGHT = 600;
const BUSINESS_CARD_SHARE_WIDTH = 600;
const BUSINESS_CARD_SHARE_HEIGHT = 480;

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

async function uploadShareImage(filePath, ownerUserId = "") {
  if (!filePath || /^https:\/\//i.test(filePath)) return filePath || "";
  const uploaded = await api.uploadShareSnapshot({
    filePath,
    ownerUserId: ownerUserId || getShareOwnerUserId()
  });
  if (!uploaded || !uploaded.url || /^(wxfile|file):/i.test(uploaded.url)) {
    throw new Error("分享图上传未返回可用地址");
  }
  return uploaded.url;
}

function exportShareCanvas(page, canvasId, ctx, exportSize, options = {}) {
  return new Promise((resolve, reject) => {
    ctx.draw(false, () => {
      wx.canvasToTempFilePath({
        canvasId,
        width: exportSize.width,
        height: exportSize.height,
        destWidth: exportSize.destWidth,
        destHeight: exportSize.destHeight,
        fileType: "jpg",
        quality: 0.92,
        success: async (res) => {
          try {
            const tempFilePath = res.tempFilePath || "";
            resolve(options.upload === false ? tempFilePath : await uploadShareImage(tempFilePath, options.ownerUserId));
          } catch (error) {
            reject(error);
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
  if (!ctx.measureText || !Number.isFinite(maxWidth) || ctx.measureText(value).width <= maxWidth) {
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

function normalizeUnifiedShareCardModel(source = {}) {
  const inferredLayout = "text_info";
  const layoutId = String(source.layoutId || source.kind || inferredLayout).trim() || "text_info";
  const templateKind = String(source.templateKind || {
    text_info: "text_note",
    image_info: "image_ocr",
    link_info: "link",
    property_info: "property",
    product_info: "product",
    service_info: "service_offer",
    showcase_info: "showcase"
  }[layoutId] || "text_note").trim();
  const businessCard = layoutId === "business_card"
    ? normalizeBusinessCardShareSource(source.businessCard || source)
    : null;
  const rawBlocks = Array.isArray(source.blocks)
    ? source.blocks
    : Array.isArray(source.contentBlocks)
      ? source.contentBlocks
      : [];
  const blocks = rawBlocks
    .filter((item) => item && ["text", "image"].includes(item.type))
    .map((item, index) => ({
      ...item,
      type: item.type,
      text: item.type === "text" ? String(item.text || "").trim() : "",
      url: item.type === "image" ? String(item.url || item.displayUrl || "").trim() : "",
      sortOrder: Number.isFinite(Number(item.sortOrder)) ? Number(item.sortOrder) : index
    }))
    .filter((item) => item.type === "image" ? Boolean(item.url) : Boolean(item.text))
    .sort((left, right) => left.sortOrder - right.sortOrder);
  const fallbackText = String(source.summary || source.headline || source.body || "").trim();
  if (!blocks.some((item) => item.type === "text") && fallbackText) {
    blocks.unshift({ id: "fallback_text", type: "text", text: fallbackText, sortOrder: -1 });
  }
  // A real cover is part of the fixed card composition for every typed card.
  // The business-card avatar remains the dedicated avatar source, while other
  // cards use their explicit cover first and then their first image block.
  const firstImageBlock = blocks.find((item) => item.type === "image" && item.url);
  const rawPrimaryImageUrl = [
    source.primaryImageUrl,
    source.coverUrl,
    firstImageBlock && firstImageBlock.url,
    layoutId === "business_card" ? source.avatarUrl : ""
  ]
    .map((item) => String(item || "").trim())
    .find((item) => item && !/^(http:\/\/|blob:|data:|ftp:)/i.test(item)) || "";
  const primaryImageUrl = rawPrimaryImageUrl && !/^(http:\/\/|blob:|data:|ftp:)/i.test(rawPrimaryImageUrl)
    ? rawPrimaryImageUrl
    : "";
  if (primaryImageUrl && !blocks.some((item) => item.type === "image" && item.url === primaryImageUrl)) {
    blocks.push({ id: "primary_image", type: "image", url: primaryImageUrl, sortOrder: -0.5 });
    blocks.sort((left, right) => left.sortOrder - right.sortOrder);
  }
  const title = String(source.title || source.name || "资料详情").trim() || "资料详情";
  const textBlocks = blocks
    .filter((item) => item.type === "text")
    .map((item) => item.text)
    .filter((text) => text && text !== title);
  const facts = (Array.isArray(source.facts) ? source.facts : [
    source.price,
    source.layout,
    source.area,
    source.address,
    source.status,
    source.tags
  ])
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .filter((item, index, list) => list.indexOf(item) === index)
    .slice(0, 3);
  return {
    layoutId,
    templateKind,
    // v11 has one fixed 5:4 contract, but the presentation is derived from
    // the only input that changes the visual hierarchy: a usable real image.
    // Business cards remain identity-first because an avatar is not a
    // substitute for the person's contact information.
    presentation: layoutId === "business_card"
      ? "identity_first"
      : primaryImageUrl
        ? "image_first"
        : "info_first",
    businessCard,
    title,
    badge: String(source.badge || source.typeLabel || "资料").trim() || "资料",
    blocks,
    textBlocks,
    facts,
    propertyData: source.propertyData || {},
    productData: source.productData || {},
    serviceData: source.serviceData || {},
    linkData: source.linkData || {},
    collectionData: source.collectionData || {},
    marketingLine: String(source.marketingLine || "").trim(),
    primaryImageUrl,
    imageCount: blocks.filter((item) => item.type === "image").length,
    footer: String(source.footer || SHARE_CARD_FOOTER).trim() || SHARE_CARD_FOOTER
  };
}

function businessCardPalette(templateId) {
  return {
    bg0: "#f4f7fb", bg1: "#ffffff", card0: "#f0f5fb", card1: "#fbfcfe",
    text: "#101828", subText: "#667085", accent: "#1677ff", chipBg: "rgba(22,119,255,.09)",
    chipText: "#166fe3", border: "#dfe7f2", avatarBg: "#dce8f8"
  };
}

async function drawBusinessCardAvatar(ctx, imagePath, card, x, y, size, palette) {
  const centerX = x + size / 2;
  const centerY = y + size / 2;
  const inset = 9;
  const imageX = x + inset;
  const imageY = y + inset;
  const imageSize = size - inset * 2;

  ctx.setFillStyle("rgba(255,255,255,0.96)");
  ctx.beginPath();
  ctx.arc(centerX, centerY, size / 2 + 8, 0, Math.PI * 2);
  ctx.fill();
  ctx.setStrokeStyle(palette.accent || "#1677ff");
  ctx.setLineWidth(3);
  ctx.beginPath();
  ctx.arc(centerX, centerY, size / 2 + 5, 0, Math.PI * 2);
  ctx.stroke();

  ctx.save();
  ctx.beginPath();
  ctx.arc(centerX, centerY, imageSize / 2, 0, Math.PI * 2);
  ctx.clip();
  if (imagePath) {
    const info = await getLocalImageInfo(imagePath);
    const sourceWidth = Number(info && info.width) || imageSize;
    const sourceHeight = Number(info && info.height) || imageSize;
    const scale = Math.min(imageSize / sourceWidth, imageSize / sourceHeight);
    const drawWidth = Math.max(1, Math.round(sourceWidth * scale));
    const drawHeight = Math.max(1, Math.round(sourceHeight * scale));
    ctx.drawImage(
      (info && info.path) || imagePath,
      Math.round(imageX + (imageSize - drawWidth) / 2),
      Math.round(imageY + (imageSize - drawHeight) / 2),
      drawWidth,
      drawHeight
    );
  } else {
    ctx.setFillStyle(palette.avatarBg || "#f8fafc");
    ctx.fillRect(imageX, imageY, imageSize, imageSize);
    ctx.setFillStyle(palette.accent || "#1677ff");
    ctx.setTextAlign("center");
    ctx.setFontSize(Math.round(imageSize * 0.42));
    ctx.fillText(card.initial || "名", centerX, imageY + imageSize * 0.66);
    ctx.setTextAlign("left");
  }
  ctx.restore();
  ctx.setStrokeStyle("rgba(255,255,255,0.95)");
  ctx.setLineWidth(2);
  ctx.beginPath();
  ctx.arc(centerX, centerY, imageSize / 2, 0, Math.PI * 2);
  ctx.stroke();
}

async function drawBusinessCardLayout(ctx, card, avatarPath, footer) {
  const width = BUSINESS_CARD_SHARE_WIDTH;
  const height = BUSINESS_CARD_SHARE_HEIGHT;
  const palette = businessCardPalette(card.templateId);
  const background = ctx.createLinearGradient(0, 0, width, height);
  background.addColorStop(0, palette.bg0);
  background.addColorStop(1, palette.bg1);
  ctx.setFillStyle(background);
  ctx.fillRect(0, 0, width, height);

  const outerX = 36;
  const outerY = 32;
  const outerW = 528;
  const outerH = 358;
  const innerX = 56;
  const innerY = 52;
  const innerW = 488;
  const innerH = 270;
  fillRoundRect(ctx, outerX, outerY, outerW, outerH, 26, "#ffffff");
  ctx.setStrokeStyle(palette.border);
  ctx.setLineWidth(2);
  drawRoundRect(ctx, outerX, outerY, outerW, outerH, 26);
  ctx.stroke();

  const cardBackground = ctx.createLinearGradient(innerX, innerY, innerX + innerW, innerY + innerH);
  cardBackground.addColorStop(0, palette.card0);
  cardBackground.addColorStop(1, palette.card1);
  drawRoundRect(ctx, innerX, innerY, innerW, innerH, 22);
  ctx.setFillStyle(cardBackground);
  ctx.fill();
  ctx.setFillStyle("rgba(22,119,255,0.08)");
  ctx.beginPath();
  ctx.arc(innerX + innerW - 34, innerY + 36, 72, 0, Math.PI * 2);
  ctx.fill();

  await drawBusinessCardAvatar(ctx, avatarPath, card, innerX + 28, innerY + 54, 100, palette);
  ctx.setFillStyle(palette.text);
  ctx.setFontSize(42);
  drawOneLine(ctx, card.name || "你的姓名", innerX + 158, innerY + 88, 292);
  ctx.setFillStyle(palette.subText);
  ctx.setFontSize(24);
  drawOneLine(ctx, card.role || "职位 / 身份", innerX + 160, innerY + 126, 276);
  ctx.setStrokeStyle("#e5eaf1");
  ctx.setLineWidth(2);
  ctx.beginPath();
  ctx.moveTo(innerX + 160, innerY + 148);
  ctx.lineTo(innerX + innerW - 28, innerY + 148);
  ctx.stroke();
  ctx.setFillStyle(palette.subText);
  ctx.setFontSize(23);
  drawOneLine(ctx, card.company || "个人服务", innerX + 30, innerY + 196, innerW - 60);
  drawOneLine(ctx, card.serviceScope || "用一句话告诉客户你能提供什么", innerX + 30, innerY + 228, innerW - 60);
  drawOneLine(ctx, card.contactLine || "电话 / 微信", innerX + 30, innerY + 260, innerW - 60);

  ctx.setFillStyle("#1677ff");
  ctx.setFontSize(24);
  drawOneLine(ctx, footer || SHARE_CARD_FOOTER, 62, 448, 476);
}

function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight, maxLines = 2) {
  const value = String(text || "").trim();
  if (!value) return 0;
  const measure = (candidate) => (ctx.measureText ? ctx.measureText(candidate).width : candidate.length);
  const truncate = (candidate) => {
    const suffix = "...";
    if (measure(candidate) <= maxWidth) return candidate;
    let next = "";
    for (const char of candidate) {
      if (measure(`${next}${char}${suffix}`) > maxWidth) break;
      next += char;
    }
    return `${next}${suffix}`;
  };
  const lines = [];
  const paragraphs = value.split(/\r?\n/);
  paragraphs.forEach((paragraph) => {
    let line = "";
    for (const char of paragraph) {
      const candidate = `${line}${char}`;
      if (line && measure(candidate) > maxWidth) {
        lines.push(line);
        line = char;
      } else {
        line = candidate;
      }
    }
    if (line) lines.push(line);
  });
  if (!lines.length) return 0;
  if (lines.length > maxLines) {
    lines.length = maxLines;
    lines[maxLines - 1] = truncate(lines[maxLines - 1]);
  }
  lines.slice(0, maxLines).forEach((line, index) => ctx.fillText(truncate(line), x, y + index * lineHeight));
  return lines.length * lineHeight;
}

function typedInfoPalette(layoutId, templateKind = "") {
  if (templateKind === "mutual_task") {
    return {
      accent: "#d85d2b",
      accentText: "#b45c36",
      soft: "#fff0df",
      bg0: "#fff8ef",
      bg1: "#f8f1e8",
      icon: "互",
      border: "#f0d7c0",
      divider: "#eee0d2",
      title: "#3b2b26",
      subText: "#806d61"
    };
  }
  return {
    text_info: { accent: "#1677ff", accentText: "#1769c2", soft: "#e8f2ff", bg0: "#eef7ff", bg1: "#f8fbff", icon: "文" },
    image_info: { accent: "#7b61ff", accentText: "#5946bd", soft: "#f0edff", bg0: "#f3f1ff", bg1: "#fbfaff", icon: "图" },
    link_info: { accent: "#168b9b", accentText: "#147381", soft: "#e4f7f7", bg0: "#effafa", bg1: "#f8fcfb", icon: "链" },
    property_info: { accent: "#1b9b68", accentText: "#177b54", soft: "#e6f7ef", bg0: "#eefaf4", bg1: "#fbfefc", icon: "房" },
    product_info: { accent: "#e58c28", accentText: "#aa6417", soft: "#fff1df", bg0: "#fff7eb", bg1: "#fffdf9", icon: "品" },
    service_info: { accent: "#4775dc", accentText: "#3157a9", soft: "#eaf0ff", bg0: "#f0f5ff", bg1: "#fbfcff", icon: "服" },
    showcase_info: { accent: "#168b76", accentText: "#14705f", soft: "#e4f7f1", bg0: "#effaf7", bg1: "#fbfefc", icon: "合" }
  }[layoutId] || { accent: "#1677ff", accentText: "#1769c2", soft: "#e8f2ff", bg0: "#eef7ff", bg1: "#f8fbff", icon: "资" };
}

function drawInfoFactPills(ctx, facts, x, y, maxWidth, palette) {
  let cursor = x;
  (facts || []).filter(Boolean).slice(0, 3).forEach((fact) => {
    const text = String(fact).trim();
    if (!text || cursor >= x + maxWidth) return;
    ctx.setFontSize(21);
    const pillWidth = Math.min(206, Math.max(92, ctx.measureText(text).width + 32));
    if (cursor + pillWidth > x + maxWidth) return;
    fillRoundRect(ctx, cursor, y - 28, pillWidth, 42, 15, palette.soft);
    ctx.setFillStyle(palette.accentText);
    drawOneLine(ctx, text, cursor + 16, y, pillWidth - 32);
    cursor += pillWidth + 12;
  });
}

function shareDetailText(model) {
  let detail = (model.textBlocks || []).filter(Boolean).slice(0, 2).join(" ");
  if (model.layoutId === "property_info") {
    detail = model.propertyData.highlights || model.propertyData.address || detail;
  } else if (model.layoutId === "product_info") {
    detail = model.productData.headline || detail;
  } else if (model.layoutId === "service_info") {
    detail = model.serviceData.headline || detail;
  } else if (model.layoutId === "link_info") {
    detail = model.linkData.sourceDescription || model.linkData.sourceDomain || detail;
  } else if (model.layoutId === "showcase_info") {
    detail = model.collectionData.description || detail;
  }
  return detail;
}

function imageFirstCoverMode(model) {
  // Document/scanned-image cards and product collages must keep the full
  // original frame so text, a QR code, or product details are not cut off by
  // the share thumbnail crop. Property and service photos keep the full-bleed
  // treatment users expect from a cover image.
  return ["image_info", "product_info"].includes(model.layoutId) ? "contain" : "cover";
}

async function drawHeroImage(ctx, imagePath, model, x, y, width, height, radius) {
  const info = await getLocalImageInfo(imagePath);
  if (!info || !info.path) return false;
  const sourceWidth = Number(info.width) || 0;
  const sourceHeight = Number(info.height) || 0;
  if (!sourceWidth || !sourceHeight) return false;
  const mode = imageFirstCoverMode(model);
  const scale = mode === "contain"
    ? Math.min(width / sourceWidth, height / sourceHeight)
    : Math.max(width / sourceWidth, height / sourceHeight);
  const drawWidth = Math.max(1, Math.round(sourceWidth * scale));
  const drawHeight = Math.max(1, Math.round(sourceHeight * scale));
  const drawX = Math.round(x + (width - drawWidth) / 2);
  const drawY = Math.round(y + (height - drawHeight) / 2);
  ctx.save();
  drawRoundRect(ctx, x, y, width, height, radius);
  ctx.clip();
  ctx.setFillStyle("#edf2f7");
  ctx.fillRect(x, y, width, height);
  ctx.drawImage(info.path, drawX, drawY, drawWidth, drawHeight);
  ctx.restore();
  return true;
}

function drawImageFirstTitle(ctx, model, palette) {
  const title = model.title || "资料详情";
  ctx.setFillStyle("#ffffff");
  ctx.setFontSize(38);
  drawWrappedText(ctx, title, 52, 302, 630, 46, 2);
  ctx.setFillStyle("rgba(255,255,255,0.86)");
  ctx.setFontSize(21);
  drawOneLine(ctx, model.badge || "资料", 52, 378, 620);
  // Keep the accent in the composition even when the photo is very light.
  ctx.setFillStyle(palette.accent);
  ctx.fillRect(52, 390, 72, 5);
}

async function drawImageFirstLayout(ctx, model, primaryImagePath) {
  const width = RESOURCE_DEFAULT_SHARE_WIDTH;
  const height = RESOURCE_DEFAULT_SHARE_HEIGHT;
  const palette = typedInfoPalette(model.layoutId, model.templateKind);
  const background = ctx.createLinearGradient(0, 0, width, height);
  background.addColorStop(0, palette.bg0 || "#edf4fb");
  background.addColorStop(1, palette.bg1);
  ctx.setFillStyle(background);
  ctx.fillRect(0, 0, width, height);

  fillRoundRect(ctx, 24, 20, 702, 560, 32, "#ffffff");
  const drawn = await drawHeroImage(ctx, primaryImagePath, model, 24, 20, 702, 380, 32);
  if (!drawn) throw new Error("分享图主图读取失败，未生成不完整卡片");

  // A restrained bottom veil keeps the title readable without covering the
  // image with an opaque panel.
  ctx.save();
  drawRoundRect(ctx, 24, 20, 702, 380, 32);
  ctx.clip();
  const veil = ctx.createLinearGradient(0, 250, 0, 400);
  veil.addColorStop(0, "rgba(16,24,40,0)");
  veil.addColorStop(1, "rgba(16,24,40,0.78)");
  ctx.setFillStyle(veil);
  ctx.fillRect(24, 250, 702, 150);
  ctx.restore();

  ctx.setFillStyle("rgba(255,255,255,0.94)");
  ctx.setFontSize(22);
  const badgeWidth = Math.min(200, Math.max(100, ctx.measureText(model.badge || "资料").width + 36));
  fillRoundRect(ctx, 50, 48, badgeWidth, 44, 16, "rgba(255,255,255,0.92)");
  ctx.setFillStyle(palette.accentText);
  drawOneLine(ctx, model.badge || "资料", 68, 78, badgeWidth - 36);
  ctx.setFillStyle("rgba(255,255,255,0.82)");
  ctx.setFontSize(20);
  drawOneLine(ctx, "资料整理助手", 536, 77, 150);
  if (model.templateKind === "mutual_task" && model.marketingLine) {
    fillRoundRect(ctx, 50, 112, 650, 40, 16, "rgba(255,246,234,0.94)");
    ctx.setFillStyle(palette.accentText);
    ctx.setFontSize(21);
    drawOneLine(ctx, model.marketingLine, 68, 139, 614);
  }
  drawImageFirstTitle(ctx, model, palette);

  const detail = shareDetailText(model);
  if (detail) {
    ctx.setFillStyle(palette.title || "#273444");
    ctx.setFontSize(24);
    drawWrappedText(ctx, detail, 52, 444, 646, 32, 2);
  }
  drawInfoFactPills(ctx, (model.facts || []).filter(Boolean).slice(0, 3), 52, 510, 646, palette);
  ctx.setStrokeStyle(palette.divider || "#e5ebf1");
  ctx.setLineWidth(2);
  ctx.beginPath();
  ctx.moveTo(52, 536);
  ctx.lineTo(698, 536);
  ctx.stroke();
  ctx.setFillStyle(palette.accentText);
  ctx.setFontSize(21);
  drawOneLine(ctx, model.footer || SHARE_CARD_FOOTER, 52, 564, 646);
}

async function drawTypedInfoLayout(ctx, model) {
  const width = RESOURCE_DEFAULT_SHARE_WIDTH;
  const height = RESOURCE_DEFAULT_SHARE_HEIGHT;
  const layoutId = model.layoutId;
  const palette = typedInfoPalette(layoutId, model.templateKind);
  const background = ctx.createLinearGradient(0, 0, width, height);
  background.addColorStop(0, palette.bg0);
  background.addColorStop(1, palette.bg1);
  ctx.setFillStyle(background);
  ctx.fillRect(0, 0, width, height);

  fillRoundRect(ctx, 32, 28, 686, 544, 30, "#ffffff");
  ctx.setStrokeStyle(palette.border || "#dbe8e1");
  ctx.setLineWidth(2);
  drawRoundRect(ctx, 32, 28, 686, 544, 30);
  ctx.stroke();

  // Keep every variable-length field inside the fixed 5:4 card geometry.
  // This also protects older WeChat clients that rasterize the thumbnail with
  // a slightly different crop rectangle.
  ctx.save();
  ctx.beginPath();
  ctx.rect(48, 44, 654, 512);
  ctx.clip();

  fillRoundRect(ctx, 64, 60, 12, 54, 6, palette.accent);
  const badge = model.badge || "资料";
  ctx.setFillStyle(palette.soft);
  ctx.setFontSize(23);
  const badgeWidth = Math.min(190, Math.max(92, ctx.measureText(badge).width + 34));
  fillRoundRect(ctx, 92, 64, badgeWidth, 46, 16, palette.soft);
  ctx.setFillStyle(palette.accentText);
  drawOneLine(ctx, badge, 109, 95, badgeWidth - 34);

  ctx.setFillStyle("#667085");
  ctx.setFontSize(21);
  drawOneLine(ctx, "资料整理助手", 542, 94, 140);

  if (model.templateKind === "mutual_task" && model.marketingLine) {
    ctx.setFillStyle(palette.accentText);
    ctx.setFontSize(24);
    drawOneLine(ctx, model.marketingLine, 64, 132, 622);
  }

  fillRoundRect(ctx, 64, 142, 96, 96, 24, palette.soft);
  ctx.setFillStyle(palette.accentText);
  ctx.setTextAlign("center");
  ctx.setFontSize(42);
  ctx.fillText(palette.icon, 112, 202);
  ctx.setTextAlign("left");

  const contentX = 190;
  const contentWidth = 500;
  ctx.setFillStyle(palette.title || "#102a1d");
  ctx.setFontSize(38);
  drawWrappedText(ctx, model.title || "资料详情", contentX, 176, contentWidth, 48, 2);

  const summary = (model.textBlocks || []).filter(Boolean).slice(0, 2).join(" ");
  ctx.setFillStyle(palette.subText || "#667085");
  ctx.setFontSize(24);
  const detail = shareDetailText(model) || summary;
  if (detail) drawWrappedText(ctx, detail, contentX, 280, contentWidth, 36, 2);

  const facts = (model.facts || []).filter(Boolean).slice(0, 3);
  drawInfoFactPills(ctx, facts, 64, 388, 622, palette);

  ctx.restore();

  ctx.setStrokeStyle(palette.divider || "#e5eee9");
  ctx.setLineWidth(2);
  ctx.beginPath();
  ctx.moveTo(64, 470);
  ctx.lineTo(686, 470);
  ctx.stroke();
  ctx.setFillStyle(palette.accentText);
  ctx.setFontSize(22);
  drawOneLine(ctx, model.footer || SHARE_CARD_FOOTER, 64, 510, 622);
}

async function generateUnifiedShareCardImage(page, canvasId, source = {}, options = {}) {
  const model = normalizeUnifiedShareCardModel(source);
  const isBusinessCard = model.layoutId === "business_card" && model.businessCard;
  const ctx = wx.createCanvasContext(canvasId, page);
  const coverPath = model.primaryImageUrl ? await downloadCanvasImage(model.primaryImageUrl) : "";
  if (model.primaryImageUrl && !coverPath) {
    throw new Error("分享图图片下载失败，未生成不完整卡片");
  }
  const baseWidth = isBusinessCard ? BUSINESS_CARD_SHARE_WIDTH : RESOURCE_DEFAULT_SHARE_WIDTH;
  const baseHeight = isBusinessCard ? BUSINESS_CARD_SHARE_HEIGHT : RESOURCE_DEFAULT_SHARE_HEIGHT;
  const exportSize = getCanvasExportSize(baseWidth, baseHeight);
  ctx.save();
  ctx.scale(exportSize.scale, exportSize.scale);

  if (isBusinessCard) {
    await drawBusinessCardLayout(ctx, model.businessCard, coverPath, model.footer);
  } else if (model.presentation === "image_first") {
    await drawImageFirstLayout(ctx, model, coverPath);
  } else {
    await drawTypedInfoLayout(ctx, model);
  }
  ctx.restore();
  return exportShareCanvas(page, canvasId, ctx, exportSize, options);
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
  const role = source.role || preview.role || data.title || "";
  const company = source.company || preview.company || data.company || "";
  const phone = source.phone || data.phone || source.contactPhone || "";
  const wechat = source.wechat || data.wechat || data.contactWechat || source.contactWechat || "";
  const email = source.email || data.email || data.mail || "";
  const serviceScope = source.serviceScope || preview.serviceScope || data.serviceScope || data.headline || source.summary || "";
  const templateId = source.templateId || source.displayTemplate || data.displayTemplate || "";
  const explicitContactLine = String(source.contactLine || preview.contactLine || "").trim();
  const contactValues = [phone, wechat, email].map((value) => String(value || "").trim()).filter(Boolean);
  const uniqueContactValues = Array.from(new Set(contactValues));
  const contactLine = uniqueContactValues.length
    ? [
        phone ? (wechat && phone === wechat ? `电话 / 微信 ${phone}` : `电话 ${phone}`) : "",
        wechat && phone !== wechat ? `微信 ${wechat}` : "",
        email ? `邮箱 ${email}` : ""
      ].filter(Boolean).join(" · ")
    : explicitContactLine;
  return {
    layoutId: "business_card",
    name,
    role,
    company,
    serviceScope,
    contactLine,
    avatarUrl: source.avatarUrl || preview.avatarUrl || data.avatarUrl || source.coverUrl || "",
    initial: String(source.initial || preview.initial || name || "名").slice(0, 1),
    templateName: source.templateName || source.displayTemplateName || data.displayTemplateName || "电子名片",
    templateId,
    tone: source.tone || data.tone || "",
  };
}

function buildBusinessCardShareSource(card = {}, user = {}) {
  const config = card.visibilityConfig || {};
  const data = config.structuredData || {};
  const preview = card.businessCardPreview || {};
  const ownerProfile = card.ownerProfile || {};
  const salesProfile = user.salesProfile || {};
  const displayConfig = config.displayConfig || {};
  const serviceKeywords = Array.isArray(data.serviceKeywords)
    ? data.serviceKeywords.filter(Boolean).join(" · ")
    : "";
  const templateId = displayConfig.styleId
    || preview.templateId
    || config.displayTemplate
    || data.displayTemplate
    || "business_blue";
  const templateNames = {
    business_blue: "商务蓝",
    clean_white: "简洁白",
    warm_gold: "暖灰金",
    fresh_green: "清新绿"
  };
  const avatarUrl = salesProfile.avatarUrl
    || ownerProfile.avatarUrl
    || preview.avatarUrl
    || data.avatarUrl
    || user.avatarUrl
    || card.coverDisplayUrl
    || card.coverUrl
    || "";
  const phone = salesProfile.phone || ownerProfile.phone || preview.phone || data.phone || card.phone || user.phone || "";
  const wechat = salesProfile.wechat || ownerProfile.wechat || preview.wechat || data.wechat || data.contactWechat || user.wechat || "";
  const email = salesProfile.email || ownerProfile.email || preview.email || data.email || data.mail || "";
  return {
    layoutId: "business_card",
    name: salesProfile.displayName || ownerProfile.displayName || preview.name || data.name || user.nickname || card.title || "电子名片",
    role: salesProfile.jobTitle || ownerProfile.jobTitle || preview.role || data.title || "",
    company: salesProfile.company || ownerProfile.company || preview.company || data.company || "",
    phone,
    wechat,
    email,
    serviceScope: data.headline || preview.serviceScope || data.serviceScope || serviceKeywords || salesProfile.city || ownerProfile.city || data.city || "",
    avatarUrl,
    coverUrl: avatarUrl,
    templateId,
    templateName: displayConfig.styleName || config.displayTemplateName || preview.templateName || templateNames[templateId] || "电子名片",
    structuredData: data,
  };
}

function buildBusinessCardShareTitle(card) {
  const normalized = normalizeBusinessCardShareSource(card);
  if (normalized.name && normalized.name !== "电子名片") return `${normalized.name}的电子名片`;
  return [normalized.role, normalized.company].filter(Boolean).join(" · ") || "电子名片";
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

module.exports = {
  SHARE_CARD_WIDTH,
  SHARE_CARD_HEIGHT,
  RESOURCE_DEFAULT_SHARE_WIDTH,
  RESOURCE_DEFAULT_SHARE_HEIGHT,
  generateUnifiedShareCardImage,
  normalizeUnifiedShareCardModel,
  buildBusinessCardShareTitle,
  buildServiceOfferShareTitle,
  buildBusinessCardShareSource,
  normalizeBusinessCardShareSource,
};
