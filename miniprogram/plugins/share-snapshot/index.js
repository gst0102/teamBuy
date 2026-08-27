const api = require("../../services/api");
const {
  buildBusinessCardShareSource,
  generateUnifiedShareCardImage
} = require("../../utils/business-card-share");
const {
  cleanImagePrimaryText,
  getPrimaryImageUrl,
  imagePrimaryTitle,
  isImagePrimaryNote
} = require("../../utils/note-display");

const SNAPSHOT_STATUS_READY = "ready";
// v7 keeps original-media direct share for non-business cards with a real
// primary image, and gives every no-image typed card a fixed information-card
// layout. A missing imageUrl must never make WeChat screenshot the current
// library/detail page.
const SHARE_CARD_STYLE_VERSION = "share_card_v7";
const shareSnapshotInFlight = {};
const shareSnapshotMemory = {};
const shareSnapshotFailures = {};
const SHARE_MEMORY_TTL_MS = 10 * 60 * 1000;
const SHARE_MEMORY_MAX_ENTRIES = 64;
const SHARE_FAILURE_TTL_MS = 30 * 1000;
const SHARE_CARD_CANVAS_ID = "shareCardCanvas";
const DEFAULT_SHARE_PATH = "/pages/home/index";

function isShareImageUrl(value) {
  const url = String(value || "").trim();
  if (!url || /^(wxfile|file|blob|data|ftp):/i.test(url)) return false;
  if (/^https?:\/\//i.test(url)) return /^https:\/\//i.test(url);
  return url.startsWith("/");
}

function isRenderableImageSource(value) {
  const url = String(value || "").trim();
  return Boolean(url) && !/^(http:\/\/|blob:|data:|ftp:)/i.test(url);
}

function setShareMenuEnabled(enabled) {
  if (typeof wx === "undefined") return;
  const method = enabled ? wx.showShareMenu : wx.hideShareMenu;
  if (typeof method !== "function") return;
  method.call(wx, { withShareTicket: false });
}

function cleanShareText(value, fallback = "") {
  return String(value || fallback || "").replace(/\s+/g, " ").trim();
}

function buildShareCardTitle(title, fallback = "资料整理助手") {
  const cleanTitle = cleanShareText(title, fallback);
  return cleanTitle.includes("｜") ? cleanTitle : `${cleanTitle}｜点开查看完整资料`;
}

function normalizeShareCardSource(source = {}) {
  return {
    title: cleanShareText(source.title, "资料整理助手"),
    summary: cleanShareText(source.summary || source.subtitle, "打开小程序查看完整资料"),
    badge: cleanShareText(source.badge || source.categoryName, "资料"),
    coverUrl: cleanShareText(source.coverUrl || source.coverDisplayUrl || source.imageUrl, ""),
    path: cleanShareText(source.path, DEFAULT_SHARE_PATH),
    shareTargetLabel: cleanShareText(source.shareTargetLabel || source.badge, "资料")
  };
}

async function prepareShareCardImage(page, source = {}) {
  if (!page || !page.setData) return "";
  const share = normalizeShareCardSource(source);
  const generation = Number(page.__shareCardGeneration || 0) + 1;
  page.__shareCardGeneration = generation;
  setShareMenuEnabled(false);
  page.setData({
    shareCardImage: "",
    shareCardSource: share,
    shareCardReady: false
  });
  try {
    const imageUrl = await renderShareCard({
      page,
      canvasId: SHARE_CARD_CANVAS_ID,
      variant: "resource",
      upload: true,
      source: {
        title: share.title,
        summary: share.summary,
        badge: share.badge,
        coverUrl: isShareImageUrl(share.coverUrl) ? share.coverUrl : "",
        hint: share.summary,
        growthHint: "点击生成同款",
        shareTargetLabel: share.shareTargetLabel
      }
    });
    if (page.__shareCardGeneration !== generation) return "";
    if (!isShareImageUrl(imageUrl)) throw new Error("share card image is unusable");
    page.setData({
      shareCardImage: imageUrl,
      shareCardSource: share,
      shareCardReady: true
    });
    setShareMenuEnabled(true);
    return imageUrl;
  } catch (error) {
    if (page.__shareCardGeneration === generation) {
      page.setData({
        shareCardImage: "",
        shareCardSource: share,
        shareCardReady: false
      });
      setShareMenuEnabled(false);
    }
    return "";
  }
}

function buildShareCardMessage(page, source = {}) {
  const data = (page && page.data) || {};
  const share = normalizeShareCardSource({
    ...(data.shareCardSource || {}),
    ...(source || {})
  });
  const directImage = isShareImageUrl(source.imageUrl) ? String(source.imageUrl).trim() : "";
  const imageUrl = directImage || (data.shareCardReady && isShareImageUrl(data.shareCardImage)
    ? String(data.shareCardImage).trim()
    : "");
  if (!imageUrl) {
    setShareMenuEnabled(false);
    return null;
  }
  return {
    title: buildShareCardTitle(share.title),
    path: share.path || DEFAULT_SHARE_PATH,
    imageUrl
  };
}

function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue);
  if (!value || typeof value !== "object") return value;
  return Object.keys(value).sort().reduce((result, key) => {
    result[key] = stableValue(value[key]);
    return result;
  }, {});
}

// The backend persists fingerprints in a bounded text field.  A raw
// canonical JSON payload can exceed that bound for business cards and
// showcases, which makes a successfully saved snapshot look unusable when
// the truncated value is compared with the full client-side payload.  Keep
// the canonical JSON as the hash input, but exchange a fixed-size digest.
function compactFingerprint(value) {
  const seeds = [0x811c9dc5, 0x9e3779b1, 0x85ebca6b, 0xc2b2ae35];
  const primes = [16777619, 2246822519, 3266489917, 668265263];
  const hashes = seeds.slice();
  const text = String(value || "");
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index);
    for (let slot = 0; slot < hashes.length; slot += 1) {
      hashes[slot] = Math.imul(hashes[slot] ^ (code + slot + (index & 0xff)), primes[slot]) >>> 0;
    }
  }
  return hashes.map((hash) => hash.toString(16).padStart(8, "0")).join("");
}

function createShareSnapshotFingerprint(entityType, entityId, sourceRevision, styleId, source = {}) {
  const canonical = JSON.stringify(stableValue({
    entityType,
    entityId,
    sourceRevision: String(sourceRevision || ""),
    styleId: styleId || "default",
    source
  }));
  return `v2:${compactFingerprint(canonical)}`;
}

function getNoteShareSnapshot(note = {}) {
  const config = note.visibilityConfig || {};
  return config.shareSnapshot && typeof config.shareSnapshot === "object"
    ? config.shareSnapshot
    : null;
}

function getShowcaseShareSnapshot(showcase = {}) {
  return showcase.shareSnapshot && typeof showcase.shareSnapshot === "object"
    ? showcase.shareSnapshot
    : null;
}

function getShareSnapshot(entityType, entity = {}) {
  return entityType === "showcase"
    ? getShowcaseShareSnapshot(entity)
    : getNoteShareSnapshot(entity);
}

function getShareSourceRevision(entityType, entity = {}) {
  if (entityType === "showcase") {
    return `${entity.snapshotVersion || 0}:${entity.updatedAt || ""}`;
  }
  return String(entity.revision || 0);
}

function noteEntityId(note = {}) {
  return note.sourceNoteId || note.noteId || note.id || "";
}

function noteCardKind(note = {}) {
  const config = note.visibilityConfig || {};
  const cardType = config.cardType || note.cardType || "text_note";
  if (cardType === "business_card" || note.isBusinessCard || note.isBusinessCardResource) return "business_card";
  if (cardType === "service_offer" || note.isServiceOffer || note.isServiceOfferResource) return "service_offer";
  if (cardType === "property_listing" || note.isProperty || note.isPropertyCard) return "property";
  if (cardType === "groupbuy_product" || note.isGroupbuy || note.isGroupbuyCard) return "product";
  if (cardType === "image_ocr" || isImagePrimaryNote(note)) return "image_ocr";
  if (cardType === "link" || cardType === "article" || note.contentMode === "link") return "link";
  return "text_note";
}

function shareCardBadge(kind) {
  return {
    image_ocr: "图片资料",
    link: "链接资料",
    property: "房源",
    product: "商品",
    service_offer: "服务方案",
    business_card: "电子名片",
    text_note: "文字资料"
  }[kind] || "资料";
}

function normalizeLinkShareData(note = {}, data = {}) {
  const preview = data.linkPreview || note.linkPreview || {};
  const sourceUrl = String(
    data.sourceUrl
      || data.url
      || note.sourceUrl
      || note.linkUrl
      || note.url
      || preview.url
      || ""
  ).trim();
  const sourceTitle = String(
    data.sourceTitle
      || preview.title
      || note.linkTitle
      || note.title
      || "网页链接"
  ).trim();
  const sourceName = String(data.sourceName || preview.sourceName || preview.siteName || "").trim();
  const sourceDomain = String(data.sourceDomain || preview.domain || "").trim();
  const sourceCoverUrl = String(
    data.sourceCoverUrl
      || data.coverUrl
      || preview.coverUrl
      || note.coverDisplayUrl
      || note.coverUrl
      || ""
  ).trim();
  const sourceDescription = String(
    data.sourceDescription
      || preview.description
      || note.summary
      || ""
  ).trim();
  const sellerRecommendation = String(data.sellerRecommendation || preview.recommendation || "").trim();
  return { sourceUrl, sourceTitle, sourceName, sourceDomain, sourceCoverUrl, sourceDescription, sellerRecommendation };
}

function noImageLayoutForKind(kind) {
  return {
    text_note: "text_info",
    image_ocr: "image_info",
    link: "link_info",
    property: "property_info",
    product: "product_info",
    service_offer: "service_info",
    business_card: "business_card"
  }[kind] || "text_info";
}

function normalizePropertyShareData(note = {}, data = {}) {
  return {
    community: String(data.community || note.title || "房源资料").trim(),
    price: String(data.price || "").trim(),
    listingMode: String(data.listingMode || data.dealType || "").trim(),
    layout: String(data.layout || "").trim(),
    area: String(data.area || "").trim(),
    address: String(data.address || data.businessArea || "").trim(),
    orientation: String(data.orientation || data.direction || "").trim(),
    floor: String(data.floor || data.floorInfo || "").trim(),
    // The property editor and backend use moveInTime as the canonical field.
    moveIn: String(data.moveIn || data.moveInTime || data.availableTime || data.checkIn || "").trim()
  };
}

function formatPropertySharePrice(value, listingMode = "") {
  const text = String(value || "").trim();
  if (!text) return "";
  if (/元|万|万元|每月|\/月|¥|￥/.test(text)) return text;
  return `${text}${["sale", "sell", "出售"].includes(String(listingMode || "").trim()) ? "万元" : "元/月"}`;
}

function formatProductSharePrice(value) {
  const text = String(value || "").trim();
  if (!text || /元|万|¥|￥/.test(text)) return text;
  return /^\d+(?:\.\d+)?$/.test(text) ? `${text}元` : text;
}

function buildNoteShareTitle(note = {}, user = {}) {
  const plan = buildNoteSharePlan(note, user);
  const source = plan.source || {};
  if (plan.kind === "business_card") {
    return source.title || "电子名片";
  }
  if (plan.kind === "property") {
    const property = source.propertyData || {};
    const details = [
      formatPropertySharePrice(property.price, property.listingMode),
      property.layout,
      property.area ? `${property.area}㎡` : ""
    ].filter(Boolean);
    return [property.community || source.title || "房源资料", details.join(" · ")].filter(Boolean).join("\n");
  }
  if (plan.kind === "product") {
    const price = formatProductSharePrice((source.facts || [])[0]);
    return [price, source.title || "商品资料"].filter(Boolean).join(" ");
  }
  return source.title || note.title || "资料详情";
}

function buildNoteContentBlocks(note = {}) {
  const explicit = Array.isArray(note.contentBlocks) ? note.contentBlocks : [];
  if (explicit.length) {
    return explicit
      .filter((item) => item && ["text", "image"].includes(item.type))
      .map((item, index) => ({
        id: item.id || `block_${index}`,
        type: item.type,
        text: item.type === "text" ? String(item.text || "").trim() : "",
        url: item.type === "image" ? String(item.url || item.displayUrl || "").trim() : "",
        sortOrder: Number.isFinite(Number(item.sortOrder)) ? Number(item.sortOrder) : index
      }))
      .filter((item) => item.type === "text" ? Boolean(item.text) : Boolean(item.url))
      .sort((left, right) => left.sortOrder - right.sortOrder);
  }
  const blocks = [];
  const body = String(note.body || "").trim();
  if (body) blocks.push({ id: "legacy_text", type: "text", text: body, sortOrder: 0 });
  (Array.isArray(note.media) ? note.media : [])
    .filter((item) => item && item.type === "image" && (item.url || item.displayUrl))
    .sort((left, right) => Number(left.sortOrder || 0) - Number(right.sortOrder || 0))
    .forEach((item, index) => blocks.push({
      id: item.id || `media_image_${index}`,
      type: "image",
      url: item.url || item.displayUrl,
      sortOrder: blocks.length
    }));
  return blocks;
}

function buildNoteSharePlan(note = {}, user = {}) {
  const config = note.visibilityConfig || {};
  const data = config.structuredData || note.structuredData || {};
  const kind = noteCardKind(note);
  const noteId = noteEntityId(note);
  const sourceRevision = getShareSourceRevision("note", note);
  let blocks = buildNoteContentBlocks(note);
  let source = {
    title: note.title || "资料详情",
    badge: shareCardBadge(kind),
    blocks,
    primaryImageUrl: blocks.find((item) => item.type === "image")?.url || "",
    facts: []
  };

  if (kind === "business_card") {
    const card = buildBusinessCardShareSource(note, user);
    const businessText = [card.role, card.company, card.serviceScope, card.phone, card.wechat, card.email]
      .map((item) => String(item || "").trim())
      .filter(Boolean)
      .filter((item, index, list) => list.indexOf(item) === index)
      .join(" · ");
    source = {
      ...source,
      ...card,
      layoutId: "business_card",
      businessCard: card,
      title: card.name || note.title || "电子名片",
      blocks: businessText ? [{ id: "business_summary", type: "text", text: businessText, sortOrder: 0 }] : [],
      primaryImageUrl: card.avatarUrl || ""
    };
  } else if (kind === "service_offer") {
    const preview = note.serviceOfferPreview || {};
    const title = note.title || preview.title || data.serviceName || "服务方案";
    const headline = preview.headline || data.headline || note.summary || "";
    const primaryImageUrl = preview.coverUrl || note.coverDisplayUrl || note.coverUrl || data.coverUrl || source.primaryImageUrl || "";
    const serviceData = {
      serviceName: title,
      headline,
      detailText: data.detailText || data.serviceScope || "",
      targetAudience: preview.targetAudience || data.targetAudience || "",
      pricingNote: preview.pricingNote || data.pricingNote || data.pricingOrTerms || "",
      scene: data.scene || preview.scene || ""
    };
    source = {
      ...source,
      ...preview,
      ...data,
      layoutId: isRenderableImageSource(primaryImageUrl) ? "original_media" : "service_info",
      templateKind: "service_offer",
      serviceData,
      title,
      badge: shareCardBadge(kind),
      summary: headline,
      blocks: headline ? [{ id: "service_headline", type: "text", text: headline, sortOrder: 0 }] : [],
      primaryImageUrl,
      facts: [serviceData.targetAudience, serviceData.pricingNote].filter(Boolean)
    };
  } else if (kind === "property") {
    const primaryImageUrl = note.coverDisplayUrl || note.coverUrl || data.coverUrl || source.primaryImageUrl || "";
    const propertyData = normalizePropertyShareData(note, data);
    source = {
      ...source,
      layoutId: isRenderableImageSource(primaryImageUrl) ? "original_media" : "property_info",
      templateKind: "property",
      propertyData,
      title: propertyData.community || "房源资料",
      summary: Array.isArray(data.highlights)
        ? data.highlights.filter(Boolean).join(" · ")
        : data.highlights || note.summary || "",
      primaryImageUrl,
      facts: [propertyData.price, propertyData.layout, propertyData.area, propertyData.address].filter(Boolean)
    };
  } else if (kind === "product") {
    const primaryImageUrl = note.coverDisplayUrl || note.coverUrl || data.coverUrl || source.primaryImageUrl;
    const productData = {
      productName: note.title || data.productName || "商品资料",
      headline: data.headline || note.summary || "",
      price: data.price || "",
      spec: data.spec || data.variantName || "",
      pickupMethod: data.pickupMethod || (data.fulfillment || {}).methods?.[0] || "",
      stockStatus: data.stockStatus || "",
      highlights: Array.isArray(data.highlights) ? data.highlights : []
    };
    source = {
      ...source,
      layoutId: isRenderableImageSource(primaryImageUrl) ? "original_media" : "product_info",
      templateKind: "product",
      productData,
      title: productData.productName,
      summary: productData.headline,
      primaryImageUrl,
      facts: [productData.price, productData.spec, productData.pickupMethod, productData.stockStatus].filter(Boolean)
    };
  } else if (kind === "link") {
    const linkData = normalizeLinkShareData(note, data);
    source = {
      ...source,
      layoutId: isRenderableImageSource(linkData.sourceCoverUrl) ? "original_media" : "link_info",
      templateKind: "link",
      linkData,
      title: linkData.sourceTitle || "网页链接",
      summary: linkData.sourceDescription,
      badge: shareCardBadge(kind),
      primaryImageUrl: linkData.sourceCoverUrl,
      facts: [linkData.sourceName, linkData.sourceDomain].filter(Boolean),
      blocks: linkData.sourceDescription
        ? [{ id: "link_description", type: "text", text: linkData.sourceDescription, sortOrder: 0 }]
        : []
    };
  } else {
    const imageCaption = kind === "image_ocr"
      ? cleanImagePrimaryText(note.body || data.rawText || (data.ocr || {}).text || note.summary || "")
      : "";
    const hasPrimaryImage = isRenderableImageSource(getPrimaryImageUrl(note));
    source = {
      ...source,
      layoutId: hasPrimaryImage ? "original_media" : noImageLayoutForKind(kind),
      templateKind: kind,
      title: kind === "image_ocr" ? imagePrimaryTitle(note, imageCaption) : note.title || "资料详情",
      badge: shareCardBadge(kind),
      summary: note.summary || imageCaption,
      blocks: kind === "image_ocr" && imageCaption && !blocks.some((item) => item.type === "text")
        ? [{ id: "image_caption", type: "text", text: imageCaption, sortOrder: 0 }, ...blocks]
        : blocks,
      primaryImageUrl: isRenderableImageSource(
        kind === "image_ocr" ? getPrimaryImageUrl(note) : source.primaryImageUrl || note.coverDisplayUrl || note.coverUrl || data.coverUrl || ""
      )
        ? (kind === "image_ocr" ? getPrimaryImageUrl(note) : source.primaryImageUrl || note.coverDisplayUrl || note.coverUrl || data.coverUrl || "")
        : ""
    };
    if (isRenderableImageSource(source.primaryImageUrl)) source.layoutId = "original_media";
  }

  const styleId = SHARE_CARD_STYLE_VERSION;
  const fingerprint = createShareSnapshotFingerprint("note", noteId, sourceRevision, styleId, {
    ...source,
    shareCardStyleVersion: SHARE_CARD_STYLE_VERSION
  });
  return {
    entity: { ...note, id: noteId, revision: note.revision || 0, visibilityConfig: config },
    kind,
    source,
    styleId,
    fingerprint,
    sourceRevision
  };
}

function isCurrentNoteShareSnapshot(note = {}, snapshot = {}, user = {}) {
  const plan = buildNoteSharePlan(note, user);
  return isShareSnapshotReady(snapshot, plan.sourceRevision, plan.fingerprint)
    && String(snapshot.styleId || "") === plan.styleId;
}

function isDirectSharePlan(plan = {}) {
  // Non-business scenes with a real registered primary image use the native
  // WeChat card path with that image.  Without an image, stay inside the
  // plugin and generate a typed information card so WeChat never screenshots the
  // current library/detail page.
  return plan.kind !== "business_card"
    && isShareImageUrl(plan.source && plan.source.primaryImageUrl);
}

function getShareImageUrlFromState(state = {}) {
  if (state.direct) {
    const directUrl = state.source && state.source.primaryImageUrl;
    return isShareImageUrl(directUrl) ? String(directUrl).trim() : "";
  }
  return state.status === "ready" && state.snapshot && isShareImageUrl(state.snapshot.url)
    ? String(state.snapshot.url).trim()
    : "";
}

function noteShareRequestKey(note, ownerUserId, user = {}) {
  const plan = buildNoteSharePlan(note, user);
  return shareSnapshotRequestKey("note", plan.entity.id, ownerUserId, plan.sourceRevision, plan.styleId, plan.fingerprint);
}

function getNoteShareSnapshotState(note = {}, ownerUserId = "", user = {}) {
  const plan = buildNoteSharePlan(note, user);
  if (isDirectSharePlan(plan)) return { status: "ready", direct: true, snapshot: null, ...plan };
  const snapshot = getNoteShareSnapshot(note);
  const requestKey = shareSnapshotRequestKey("note", plan.entity.id, ownerUserId, plan.sourceRevision, plan.styleId, plan.fingerprint);
  if (isShareSnapshotReady(snapshot, plan.sourceRevision, plan.fingerprint) && String(snapshot.styleId || "") === plan.styleId) {
    return { status: "ready", snapshot, ...plan };
  }
  if (shareSnapshotInFlight[requestKey]) return { status: "preparing", snapshot, ...plan };
  const failure = shareSnapshotFailures[requestKey];
  if (failure && Date.now() - failure.failedAt < SHARE_FAILURE_TTL_MS) {
    return { status: "failed", snapshot, error: failure.error, ...plan };
  }
  return { status: snapshot ? "stale" : "missing", snapshot, ...plan };
}

async function prepareNoteShareSnapshot({ page, canvasId, note, ownerUserId, user = {} }) {
  const plan = buildNoteSharePlan(note, user);
  if (isDirectSharePlan(plan)) return { ...plan, direct: true, snapshot: null, entity: plan.entity };
  const requestKey = shareSnapshotRequestKey("note", plan.entity.id, ownerUserId, plan.sourceRevision, plan.styleId, plan.fingerprint);
  try {
    const result = await ensureShareSnapshot({
      entityType: "note",
      entity: plan.entity,
      ownerUserId,
      styleId: plan.styleId,
      fingerprint: plan.fingerprint,
      generate: () => {
        const options = { upload: true, ownerUserId };
        return generateUnifiedShareCardImage(page, canvasId, plan.source, options);
      }
    });
    delete shareSnapshotFailures[requestKey];
    // Keep the entity returned by the save API.  It contains the persisted
    // snapshot and must not be replaced by the pre-generation plan entity;
    // otherwise the page can show the uploaded URL while its local state
    // still believes that no snapshot was saved.
    return { ...plan, ...result };
  } catch (error) {
    shareSnapshotFailures[requestKey] = { failedAt: Date.now(), error };
    throw error;
  }
}

async function renderShareCard({ page, canvasId, source = {}, variant = "resource", upload = false, ownerUserId = "" }) {
  const options = { upload, ownerUserId };
  // Only business cards retain a dedicated renderer. Every other scene with
  // media uses the same original-media path; CSS/WXML wrappers cannot be
  // carried into a native WeChat share card.
  let modelSource = source;
  if (!source.layoutId && variant === "business_card") {
    modelSource = { ...source, layoutId: "business_card", businessCard: source };
  } else if (!source.layoutId) {
    modelSource = { ...source, layoutId: source.primaryImageUrl || source.coverUrl ? "original_media" : "text_info" };
  }
  return generateUnifiedShareCardImage(page, canvasId, modelSource, options);
}

function buildShareMessage({ title, path, snapshot, sourceRevision, fingerprint, styleId, direct = false, imageUrl = "" }) {
  if (direct && !isShareImageUrl(imageUrl)) return null;
  if (!direct && !isShareSnapshotReady(snapshot, sourceRevision, fingerprint)) return null;
  if (!direct && styleId && String(snapshot.styleId || "") !== String(styleId)) return null;
  const directImageUrl = direct && isShareImageUrl(imageUrl) ? String(imageUrl).trim() : "";
  return {
    title: title || "资料详情",
    path: path || "/pages/home/index",
    imageUrl: direct ? directImageUrl : snapshot.url
  };
}

function isShareSnapshotReady(snapshot, sourceRevision, fingerprint) {
  return Boolean(
    snapshot
      && snapshot.status === SNAPSHOT_STATUS_READY
      && isShareImageUrl(snapshot.url)
      && String(snapshot.sourceRevision || "") === String(sourceRevision || "")
      && String(snapshot.fingerprint || "") === String(fingerprint || "")
  );
}

function shareSnapshotRequestKey(entityType, entityId, ownerUserId, sourceRevision, styleId, fingerprint) {
  return JSON.stringify([
    entityType || "note",
    entityId || "",
    ownerUserId || "",
    String(sourceRevision || ""),
    styleId || "default",
    String(fingerprint || "")
  ]);
}

function readRememberedSnapshot(requestKey) {
  const remembered = shareSnapshotMemory[requestKey];
  if (!remembered || Date.now() - remembered.savedAt > SHARE_MEMORY_TTL_MS) {
    delete shareSnapshotMemory[requestKey];
    return null;
  }
  remembered.lastUsedAt = Date.now();
  return remembered.result;
}

function rememberSnapshot(requestKey, result) {
  shareSnapshotMemory[requestKey] = {
    savedAt: Date.now(),
    lastUsedAt: Date.now(),
    result
  };
  const keys = Object.keys(shareSnapshotMemory);
  if (keys.length > SHARE_MEMORY_MAX_ENTRIES) {
    keys
      .sort((left, right) => Number(shareSnapshotMemory[left].lastUsedAt || 0) - Number(shareSnapshotMemory[right].lastUsedAt || 0))
      .slice(0, keys.length - SHARE_MEMORY_MAX_ENTRIES)
      .forEach((key) => delete shareSnapshotMemory[key]);
  }
}

async function ensureShareSnapshot({
  entityType,
  entity,
  ownerUserId,
  styleId = "default",
  fingerprint,
  generate
}) {
  const entityId = entity && entity.id;
  if (!entityId || !ownerUserId) throw new Error("share snapshot missing entity or owner");
  const sourceRevision = getShareSourceRevision(entityType, entity);
  const current = getShareSnapshot(entityType, entity);
  const requestKey = shareSnapshotRequestKey(entityType, entityId, ownerUserId, sourceRevision, styleId, fingerprint);
  if (isShareSnapshotReady(current, sourceRevision, fingerprint)) {
    const result = { snapshot: current, entity, reused: true };
    rememberSnapshot(requestKey, result);
    return result;
  }
  if (typeof generate !== "function") throw new Error("share snapshot generator is required");
  const remembered = readRememberedSnapshot(requestKey);
  if (remembered && isShareSnapshotReady(remembered.snapshot, sourceRevision, fingerprint)) {
    return { ...remembered, reused: true };
  }
  if (shareSnapshotInFlight[requestKey]) return shareSnapshotInFlight[requestKey];
  const request = (async () => {
    const url = await generate();
    if (!url) throw new Error("share snapshot image is empty");
    const payload = {
      ownerUserId,
      sourceRevision,
      fingerprint,
      url,
      styleId,
      generatedAt: new Date().toISOString()
    };
    const response = entityType === "showcase"
      ? await api.saveShowcaseShareSnapshot(entityId, payload)
      : await api.saveNoteShareSnapshot(entityId, payload);
    const savedEntity = response && response.data ? response.data : entity;
    const snapshot = getShareSnapshot(entityType, savedEntity);
    if (!isShareSnapshotReady(snapshot, sourceRevision, fingerprint)) {
      throw new Error("share snapshot save returned an unusable snapshot");
    }
    const result = { snapshot, entity: savedEntity, reused: false };
    rememberSnapshot(requestKey, result);
    return result;
  })();
  shareSnapshotInFlight[requestKey] = request.finally(() => {
    delete shareSnapshotInFlight[requestKey];
  });
  return shareSnapshotInFlight[requestKey];
}

module.exports = {
  SHARE_CARD_CANVAS_ID,
  SHARE_CARD_STYLE_VERSION,
  buildShareCardMessage,
  buildShareCardTitle,
  buildShareMessage,
  buildNoteSharePlan,
  buildNoteShareTitle,
  createShareSnapshotFingerprint,
  getNoteShareSnapshotState,
  getNoteShareSnapshot,
  getShowcaseShareSnapshot,
  getShareSnapshot,
  getShareSourceRevision,
  getShareImageUrlFromState,
  isDirectSharePlan,
  isShareImageUrl,
  isCurrentNoteShareSnapshot,
  isShareSnapshotReady,
  noteShareRequestKey,
  normalizeShareCardSource,
  prepareShareCardImage,
  prepareNoteShareSnapshot,
  renderShareCard,
  setShareMenuEnabled,
  ensureShareSnapshot
};
