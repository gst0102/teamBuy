const CACHE_KEY = "mediaCacheMap";

function readCacheMap() {
  const value = wx.getStorageSync(CACHE_KEY);
  return value && typeof value === "object" ? value : {};
}

function writeCacheMap(map) {
  wx.setStorageSync(CACHE_KEY, map);
}

function canCache(url) {
  return /^https?:\/\//i.test(url || "");
}

function cacheMedia(url) {
  if (!canCache(url)) {
    return Promise.resolve(url);
  }
  const cacheMap = readCacheMap();
  if (cacheMap[url]) {
    return Promise.resolve(cacheMap[url]);
  }
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
            const nextMap = readCacheMap();
            nextMap[url] = saveRes.savedFilePath;
            writeCacheMap(nextMap);
            resolve(saveRes.savedFilePath);
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
}

async function withCachedMedia(card) {
  if (!card || typeof card !== "object") return card;
  const media = Array.isArray(card.media) ? card.media : [];
  const [coverDisplayUrl, cachedMedia] = await Promise.all([
    cacheMedia(card.coverUrl),
    Promise.all(media.map(async (item) => ({ ...item, displayUrl: await cacheMedia(item.url) })))
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

module.exports = {
  cacheMedia,
  withCachedMedia,
  withCachedCards
};
