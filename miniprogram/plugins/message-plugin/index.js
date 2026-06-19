const api = require("../../services/api");
const { getCurrentUser } = require("../../utils/dashboard");

function getRequiredUser() {
  const user = getCurrentUser();
  if (!user) {
    wx.reLaunch({ url: "/pages/login/index" });
    return null;
  }
  return user;
}

async function openMessageThread(options = {}) {
  const user = getRequiredUser();
  if (!user) return null;
  const noteId = String(options.noteId || "").trim();
  const orderActionId = String(options.orderActionId || "").trim();
  if (!noteId) {
    wx.showToast({ title: "缺少资料", icon: "none" });
    return null;
  }
  try {
    const payload = {
      userId: user.id,
      noteId
    };
    if (orderActionId) {
      payload.orderActionId = orderActionId;
    } else {
      payload.buyerUserId = options.buyerUserId || user.id;
    }
    if (options.content) payload.content = options.content;
    const res = await api.createMessageThread(payload);
    const thread = res.data || {};
    wx.navigateTo({ url: `/pages/message-thread/index?id=${thread.id}` });
    return thread;
  } catch (error) {
    wx.showToast({ title: error.detail || "打开消息失败", icon: "none" });
    return null;
  }
}

function openMessageCenter() {
  const user = getRequiredUser();
  if (!user) return;
  wx.navigateTo({ url: "/pages/messages/index" });
}

async function fetchUnreadTotal(userId) {
  const id = userId || (getCurrentUser() || {}).id;
  if (!id) return 0;
  try {
    const res = await api.fetchMessageThreads(id);
    return (res.data && res.data.unreadTotal) || 0;
  } catch (error) {
    return 0;
  }
}

module.exports = {
  openMessageThread,
  openMessageCenter,
  fetchUnreadTotal
};
