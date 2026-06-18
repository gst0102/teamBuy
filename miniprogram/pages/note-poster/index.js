const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

const THEMES = [
  { key: "forest", name: "墨绿", color: "#17633a", light: "#e8f7ef" },
  { key: "teal", name: "青绿", color: "#0f766e", light: "#e6fffb" },
  { key: "blue", name: "湖蓝", color: "#2563eb", light: "#eaf2ff" },
  { key: "rose", name: "玫红", color: "#be3455", light: "#fff0f3" },
  { key: "amber", name: "暖黄", color: "#d97706", light: "#fff7e6" }
];

const CANVAS_ID = "posterCanvas";
const POSTER_WIDTH = 750;
const POSTER_HEIGHT = 1050;

function cleanPosterText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function buildPoster(note) {
  const config = note.visibilityConfig || {};
  const data = config.structuredData || {};
  const cardType = config.cardType || "text_note";
  const isProperty = cardType === "property_listing";
  const isGroupbuy = cardType === "groupbuy_product";
  const title = cleanPosterText(isProperty ? data.community || note.title : isGroupbuy ? data.productName || note.title : note.title);
  const price = data.price || "";
  const line = cleanPosterText(isProperty
    ? [data.layout, data.area, data.businessArea || data.address].filter(Boolean).join(" · ")
    : isGroupbuy
      ? [data.spec, data.pickupMethod, data.deadline].filter(Boolean).join(" · ")
      : note.summary || "");
  const coverUrl = note.coverUrl || ((note.media || []).find((item) => item.type === "image") || {}).url || "";
  const copy = [
    title,
    price ? `价格：${price}` : "",
    line,
    data.remark || note.summary || "",
    isProperty ? "感兴趣可以预约看房" : isGroupbuy ? "需要的可以直接接龙" : ""
  ].filter(Boolean).join("\n");
  return {
    title,
    price,
    line,
    coverUrl,
    badge: isProperty ? "房源分享图" : isGroupbuy ? "团购分享图" : "资料分享图",
    copy
  };
}

function requestDownloadImage(url) {
  return new Promise((resolve, reject) => {
    if (!url) {
      reject(new Error("no image"));
      return;
    }
    if (/^(wxfile|http:\/\/tmp|file):/i.test(url)) {
      resolve(url);
      return;
    }
    wx.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.tempFilePath) {
          resolve(res.tempFilePath);
          return;
        }
        reject(new Error("download failed"));
      },
      fail: reject
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

function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
  const chars = cleanPosterText(text).split("");
  const lines = [];
  let line = "";
  chars.forEach((char) => {
    const next = `${line}${char}`;
    const width = ctx.measureText ? ctx.measureText(next).width : next.length * 28;
    if (width > maxWidth && line) {
      lines.push(line);
      line = char;
      return;
    }
    line = next;
  });
  if (line) lines.push(line);
  const visibleLines = lines.slice(0, maxLines);
  visibleLines.forEach((item, index) => {
    const suffix = index === maxLines - 1 && lines.length > maxLines ? "..." : "";
    ctx.fillText(`${item}${suffix}`, x, y + index * lineHeight);
  });
  return y + visibleLines.length * lineHeight;
}

Page({
  data: {
    noteId: "",
    user: null,
    poster: null,
    themes: THEMES,
    activeTheme: THEMES[0],
    savingPoster: false
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
    this.setData({ user });
    this.loadNote();
  },
  async loadNote() {
    const { user, noteId } = this.data;
    if (!user || !noteId) return;
    try {
      const res = await api.fetchNote(noteId, user.id);
      this.setData({ poster: buildPoster(res.data || {}) });
    } catch (error) {
      wx.showToast({ title: error.detail || "海报加载失败", icon: "none" });
    }
  },
  handleTheme(event) {
    const key = event.currentTarget.dataset.key;
    const theme = THEMES.find((item) => item.key === key) || THEMES[0];
    this.setData({ activeTheme: theme });
  },
  handleCopy() {
    if (!this.data.poster) return;
    wx.setClipboardData({
      data: this.data.poster.copy,
      success: () => wx.showToast({ title: "文案已复制", icon: "success" }),
      fail: () => wx.showToast({ title: "复制失败", icon: "none" })
    });
  },
  handlePreviewPage() {
    wx.navigateTo({ url: `/pages/note-preview/index?id=${this.data.noteId}` });
  },
  async handleSavePoster() {
    if (!this.data.poster || this.data.savingPoster) return;
    this.setData({ savingPoster: true });
    try {
      const filePath = await this.renderPosterImage();
      await this.saveImageToAlbum(filePath);
      wx.showToast({ title: "已保存到相册", icon: "success" });
    } catch (error) {
      const message = (error && (error.errMsg || error.message)) || "";
      if (message.includes("auth") || message.includes("authorize") || message.includes("permission")) {
        wx.showModal({
          title: "需要相册权限",
          content: "请允许保存到相册后再试。",
          confirmText: "去设置",
          confirmColor: "#11924d",
          success: ({ confirm }) => {
            if (confirm && wx.openSetting) wx.openSetting();
          }
        });
      } else {
        wx.showToast({ title: "保存失败", icon: "none" });
      }
    } finally {
      this.setData({ savingPoster: false });
    }
  },
  async renderPosterImage() {
    const poster = this.data.poster || {};
    const theme = this.data.activeTheme || THEMES[0];
    let coverPath = "";
    try {
      coverPath = await requestDownloadImage(poster.coverUrl);
    } catch (error) {
      coverPath = "";
    }
    const ctx = wx.createCanvasContext(CANVAS_ID, this);
    ctx.setFillStyle("#f6f8fb");
    ctx.fillRect(0, 0, POSTER_WIDTH, POSTER_HEIGHT);
    fillRoundRect(ctx, 42, 42, 666, 966, 20, "#fffdf7");

    if (coverPath) {
      ctx.save();
      drawRoundRect(ctx, 72, 72, 606, 430, 14);
      ctx.clip();
      ctx.drawImage(coverPath, 72, 72, 606, 430);
      ctx.restore();
    } else {
      fillRoundRect(ctx, 72, 72, 606, 430, 14, "#eef2f7");
      ctx.setFillStyle(theme.color);
      ctx.setFontSize(48);
      ctx.setTextAlign("center");
      ctx.fillText(poster.badge || "分享图", POSTER_WIDTH / 2, 300);
      ctx.setTextAlign("left");
    }

    fillRoundRect(ctx, 72, 540, 146, 44, 8, theme.light || "#e8f7ef");
    ctx.setFillStyle(theme.color);
    ctx.setFontSize(24);
    ctx.fillText(poster.badge || "分享图", 92, 570);

    ctx.setFillStyle("#172033");
    ctx.setFontSize(46);
    let nextY = drawWrappedText(ctx, poster.title || "资料详情", 72, 630, 606, 56, 3);
    nextY = Math.min(nextY, 798);
    if (poster.price) {
      nextY += 20;
      ctx.setFillStyle(theme.color);
      ctx.setFontSize(42);
      ctx.fillText(poster.price, 72, nextY);
      nextY += 56;
    }
    if (poster.line) {
      ctx.setFillStyle("#4b5565");
      ctx.setFontSize(28);
      nextY = drawWrappedText(ctx, poster.line, 72, nextY + 4, 606, 40, 2);
    }

    ctx.setStrokeStyle("#e3e8f0");
    ctx.setLineWidth(1);
    ctx.beginPath();
    ctx.moveTo(72, 900);
    ctx.lineTo(678, 900);
    ctx.stroke();

    ctx.setFillStyle("#6f7d91");
    ctx.setFontSize(24);
    ctx.fillText("配合客户页链接查看详情", 72, 948);
    ctx.setFillStyle(theme.color);
    ctx.setFontSize(26);
    ctx.fillText("资料整理助手", 72, 982);

    return new Promise((resolve, reject) => {
      ctx.draw(false, () => {
        wx.canvasToTempFilePath({
          canvasId: CANVAS_ID,
          width: POSTER_WIDTH,
          height: POSTER_HEIGHT,
          destWidth: POSTER_WIDTH * 2,
          destHeight: POSTER_HEIGHT * 2,
          success: (res) => resolve(res.tempFilePath),
          fail: reject
        }, this);
      });
    });
  },
  saveImageToAlbum(filePath) {
    return new Promise((resolve, reject) => {
      wx.saveImageToPhotosAlbum({
        filePath,
        success: resolve,
        fail: reject
      });
    });
  }
});
