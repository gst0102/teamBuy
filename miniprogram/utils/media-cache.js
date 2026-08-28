const cachePolicy = require("./cache-policy");

// Keep the existing namespace so an app update does not orphan previously
// saved files. Entries without the newer size/lastUsedAt fields are upgraded
// lazily when they are read.
const CACHE_KEY_PREFIX = "mediaCacheMap:v2";
const CACHE_TTL_MS = cachePolicy.mediaTtlMs;
const MAX_CACHE_ENTRIES = cachePolicy.mediaMaxEntries;
const MAX_CACHE_BYTES = cachePolicy.mediaMaxBytes;
const MAX_IMAGES_PER_CARD = cachePolicy.mediaMaxImagesPerCard;
const inFlight = {};
const cacheMapsByKey = {};
let cacheGeneration = 0;

function cacheKey() {
  try {
    const app = getApp();
    const globalData = (app && app.globalData) || {};
    const storedUser = wx.getStorageSync("currentUser") || {};
    const userId = (globalData.currentUser && globalData.currentUser.id) || storedUser.id || "guest";
    return `${CACHE_KEY_PREFIX}:${globalData.environmentName || "default"}:${globalData.apiBaseUrl || ""}:${globalData.mediaRoutePrefix || ""}:${String(userId).replace(/[^a-zA-Z0-9_.:-]/g, "_")}`;
  } catch (error) {
    return `${CACHE_KEY_PREFIX}:default`;
  }
}

function readCacheMap(key = cacheKey()) {
  if (cacheMapsByKey[key]) return cacheMapsByKey[key];
  let value = null;
  try { value = wx.getStorageSync(key); } catch (error) {}
  cacheMapsByKey[key] = value && typeof value === "object" ? value : {};
  return cacheMapsByKey[key];
}

function writeCacheMap(map, key = cacheKey()) {
  cacheMapsByKey[key] = map;
  try {
    if (typeof wx.setStorage === "function") wx.setStorage({ key, data: map });
    else wx.setStorageSync(key, map);
  } catch (error) {}
}

function canCache(url, mediaType = "image") {
  if (!/^https:\/\//i.test(url || "")) return false;
  const type = String(mediaType || "").toLowerCase();
  return !type || type === "image";
}

function removeSavedFile(filePath) {
  if (!filePath || !wx.removeSavedFile) return;
  try { wx.removeSavedFile({ filePath }); } catch (error) {}
}

function getFileSize(filePath) {
  if (!filePath || !wx.getFileInfo) return Promise.resolve(0);
  return new Promise((resolve) => {
    wx.getFileInfo({
      filePath,
      success: (result) => resolve(Number(result && result.size || 0)),
      fail: () => resolve(0)
    });
  });
}

function entryPath(entry) {
  return typeof entry === "string" ? entry : entry && entry.filePath;
}

function entrySize(entry) {
  return typeof entry === "string" ? 0 : Number(entry && entry.size || 0);
}

function entryLastUsedAt(entry) {
  return Number(typeof entry === "string" ? 0 : entry && (entry.lastUsedAt || entry.savedAt) || 0);
}

function getValidCachedPath(url, cached, key) {
  const entry = cached && typeof cached === "object" ? cached[url] : null;
  if (!entry) return Promise.resolve("");
  const filePath = entryPath(entry);
  const savedAt = Number(typeof entry === "string" ? 0 : entry.savedAt || 0);
  if (!filePath || !savedAt || Date.now() - savedAt >= CACHE_TTL_MS) {
    removeSavedFile(filePath);
    delete cached[url];
    writeCacheMap(cached, key);
    return Promise.resolve("");
  }
  if (!wx.getFileInfo) return Promise.resolve(filePath);
  return new Promise((resolve) => {
    wx.getFileInfo({
      filePath,
      success: (fileInfo) => {
        const size = Number(fileInfo && fileInfo.size || entrySize(entry));
        if (size > MAX_CACHE_BYTES) {
          removeSavedFile(filePath);
          delete cached[url];
          writeCacheMap(cached, key);
          resolve("");
          return;
        }
        if (typeof entry !== "string") {
          cached[url] = { ...entry, size, lastUsedAt: Date.now() };
          evictCache(cached, url);
          writeCacheMap(cached, key);
        }
        resolve(filePath);
      },
      fail: () => {
        delete cached[url];
        writeCacheMap(cached, key);
        resolve("");
      }
    });
  });
}

function evictCache(map, protectedUrl = "") {
  let keys = Object.keys(map);
  let totalBytes = keys.reduce((sum, key) => sum + entrySize(map[key]), 0);
  while ((keys.length > MAX_CACHE_ENTRIES || totalBytes > MAX_CACHE_BYTES) && keys.length) {
    const candidates = keys
      .filter((key) => key !== protectedUrl)
      .sort((left, right) => entryLastUsedAt(map[left]) - entryLastUsedAt(map[right]));
    const oldUrl = candidates[0];
    if (!oldUrl) break;
    removeSavedFile(entryPath(map[oldUrl]));
    totalBytes -= entrySize(map[oldUrl]);
    delete map[oldUrl];
    keys = Object.keys(map);
  }
}

function cacheMedia(url, options = {}) {
  if (!canCache(url, options.mediaType || "image")) {
    return Promise.resolve(url);
  }
  const ownerCacheKey = cacheKey();
  const generationAtStart = cacheGeneration;
  const flightKey = `${ownerCacheKey}|${url}`;
  if (inFlight[flightKey]) return inFlight[flightKey];
  const cacheMap = readCacheMap(ownerCacheKey);
  const cached = getValidCachedPath(url, cacheMap, ownerCacheKey);
  const request = cached.then((cachedPath) => {
    if (cachedPath) return cachedPath;
    return new Promise((resolve) => {
      wx.downloadFile({
        url,
        success(downloadRes) {
          if (downloadRes.statusCode < 200 || downloadRes.statusCode >= 300 || !downloadRes.tempFilePath) {
            resolve(url);
            return;
          }
          if (!wx.saveFile) {
            resolve(downloadRes.tempFilePath);
            return;
          }
          wx.saveFile({
            tempFilePath: downloadRes.tempFilePath,
            success(saveRes) {
              const savedFilePath = saveRes.savedFilePath;
              getFileSize(savedFilePath).then((size) => {
                if (size > MAX_CACHE_BYTES) {
                  removeSavedFile(savedFilePath);
                  resolve(downloadRes.tempFilePath);
                  return;
                }
                if (generationAtStart !== cacheGeneration) {
                  removeSavedFile(savedFilePath);
                  resolve(downloadRes.tempFilePath);
                  return;
                }
                const nextMap = readCacheMap(ownerCacheKey);
                nextMap[url] = {
                  filePath: savedFilePath,
                  savedAt: Date.now(),
                  lastUsedAt: Date.now(),
                  size
                };
                evictCache(nextMap, url);
                writeCacheMap(nextMap, ownerCacheKey);
                resolve(savedFilePath);
              });
            },
            fail() {
              resolve(downloadRes.tempFilePath);
            }
          });
        },
        fail() {
          resolve(url);
        }
      });
    });
  }).finally(() => {
    delete inFlight[flightKey];
  });
  inFlight[flightKey] = request;
  return request;
}

async function withCachedMedia(card) {
  if (!card || typeof card !== "object") return card;
  const media = Array.isArray(card.media) ? card.media : [];
  const [coverDisplayUrl, cachedMedia] = await Promise.all([
    cacheMedia(card.coverUrl, { mediaType: "image" }),
    Promise.all(media.map(async (item, index) => {
      const mediaType = String(item && (item.type || item.mediaType) || "").toLowerCase();
      const isImage = mediaType === "image"
        || (!mediaType && /\.(?:jpe?g|png|webp|gif|bmp)(?:[?#]|$)/i.test(item && item.url || ""));
      const canUseLocalCache = isImage && index < MAX_IMAGES_PER_CARD;
      return {
        ...item,
        displayUrl: canUseLocalCache
          ? await cacheMedia(item.url, { mediaType: "image" })
          : item.url
      };
    }))
  ]);
  return {
    ...card,
    coverDisplayUrl: coverDisplayUrl || card.coverUrl,
    media: cachedMedia
  };
}

async function withCachedCards(cards) {
  return Promise.all((cards || []).map((card) => withCachedMedia(card)));
}

function clearAllCachedMedia() {
  cacheGeneration += 1;
  Object.keys(inFlight).forEach((key) => { delete inFlight[key]; });
  const keys = new Set(Object.keys(cacheMapsByKey));
  try {
    const info = wx.getStorageInfoSync();
    (info.keys || []).filter((key) => key.startsWith(`${CACHE_KEY_PREFIX}:`)).forEach((key) => keys.add(key));
  } catch (error) {}
  keys.forEach((key) => {
    const map = cacheMapsByKey[key] || readCacheMap(key);
    Object.keys(map || {}).forEach((url) => removeSavedFile(entryPath(map[url])));
    delete cacheMapsByKey[key];
    try {
      if (typeof wx.removeStorage === "function") wx.removeStorage({ key });
      else wx.removeStorageSync(key);
    } catch (error) {}
  });
}

module.exports = {
  cacheMedia,
  withCachedMedia,
  withCachedCards,
  clearAllCachedMedia
};
