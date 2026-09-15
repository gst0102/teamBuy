const UNLOCKS_KEY = "teambuy:mutual-help:wool-unlocks:v1";
const COMMENTS_KEY = "teambuy:mutual-help:task-comments:v1";
const REPORTS_KEY = "teambuy:mutual-help:task-comment-reports:v1";
const REFUNDS_KEY = "teambuy:mutual-help:wool-refunds:v1";
const LEDGER_KEY = "teambuy:mutual-help:point-ledger:v1";

const RECOMMEND_LABELS = {
  worth_it: "值得做",
  neutral: "一般",
  not_worth_it: "不建议"
};

function readStorage(key, fallback) {
  try {
    const value = wx.getStorageSync(key);
    return value === undefined || value === null ? fallback : value;
  } catch (error) {
    return fallback;
  }
}

function writeStorage(key, value) {
  try {
    wx.setStorageSync(key, value);
  } catch (error) {
    // The local demo remains usable when storage is unavailable.
  }
}

function readList(key) {
  const value = readStorage(key, []);
  return Array.isArray(value) ? value : [];
}

function writeList(key, value) {
  writeStorage(key, Array.isArray(value) ? value : []);
}

function toNonNegativeInteger(value, fallback = 0) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) return fallback;
  return Math.floor(number);
}

function formatCommentDate(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) return "刚刚";
  return String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0");
}

function normalizeWoolPolicy(policy = {}, task = {}) {
  const source = policy && typeof policy === "object" ? policy : {};
  const unlockFeePoints = toNonNegativeInteger(
    source.unlockFeePoints === undefined ? task.unlockFeePoints : source.unlockFeePoints,
    0
  );
  return {
    unlockFeePoints,
    allowTip: source.allowTip !== false,
    accessLabel: unlockFeePoints > 0 ? `查看完整内容需 ${unlockFeePoints} 分` : "免费查看完整内容",
    rewardLabel: "无固定完成奖励，可自愿打赏"
  };
}

function getTaskAccess(task = {}, userId = "") {
  const policy = normalizeWoolPolicy(task.woolPolicy, task);
  const currentUserId = String(userId || "");
  const ownerUserId = String(task.ownerUserId || "");
  if (task.taskKind !== "wool" || (ownerUserId && ownerUserId === currentUserId)) {
    return { unlocked: true, unlockRequired: false, unlock: null, policy };
  }
  const unlock = getTaskUnlock(task.id, currentUserId);
  if (policy.unlockFeePoints === 0) {
    return { unlocked: true, unlockRequired: false, unlock, policy };
  }
  return { unlocked: Boolean(unlock), unlockRequired: !unlock, unlock, policy };
}

function getTaskUnlock(taskId, userId) {
  const id = String(taskId || "");
  const currentUserId = String(userId || "");
  if (!id || !currentUserId) return null;
  return readList(UNLOCKS_KEY).find((item) => (
    String(item.taskId || "") === id
      && String(item.userId || "") === currentUserId
      && item.status === "completed"
  )) || null;
}

function getTaskUnlockCount(taskId) {
  const id = String(taskId || "");
  if (!id) return 0;
  return readList(UNLOCKS_KEY).filter((item) => String(item.taskId || "") === id && item.status === "completed").length;
}

function appendPointLedger(entry = {}) {
  const amount = toNonNegativeInteger(entry.amount, 0);
  if (!amount) return null;
  const record = {
    id: entry.id || `point_entry_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
    type: String(entry.type || "unknown"),
    taskId: String(entry.taskId || ""),
    fromUserId: String(entry.fromUserId || ""),
    toUserId: String(entry.toUserId || ""),
    pointType: entry.pointType === "reward" ? "reward" : "base",
    amount,
    reason: String(entry.reason || ""),
    createdAt: entry.createdAt || new Date().toISOString()
  };
  const list = readList(LEDGER_KEY);
  list.unshift(record);
  writeList(LEDGER_KEY, list);
  return record;
}

function getPointLedger(filters = {}) {
  const taskId = String(filters.taskId || "");
  const userId = String(filters.userId || "");
  return readList(LEDGER_KEY).filter((item) => (
    (!taskId || String(item.taskId || "") === taskId)
      && (!userId || String(item.fromUserId || "") === userId || String(item.toUserId || "") === userId)
  ));
}

function unlockTask(task = {}, userId, getPoints, savePoints, pointType = "base") {
  const currentUserId = String(userId || "");
  const policy = normalizeWoolPolicy(task.woolPolicy, task);
  if (task.taskKind !== "wool") return { ok: false, reason: "not_wool_task" };
  if (!currentUserId) return { ok: false, reason: "login_required" };
  if (String(task.ownerUserId || "") === currentUserId) {
    return { ok: true, unlocked: true, alreadyUnlocked: true, feePoints: 0 };
  }
  const existing = getTaskUnlock(task.id, currentUserId);
  if (existing) return { ok: true, unlocked: true, alreadyUnlocked: true, feePoints: 0, unlock: existing };
  if (task.status && task.status !== "published") return { ok: false, reason: "task_closed" };
  const remaining = task.remaining === null || task.remaining === undefined || task.remaining === ""
    ? null
    : Math.max(0, Number(task.remaining) || 0);
  if (remaining === 0) return { ok: false, reason: "task_closed" };
  const ownerUserId = String(task.ownerUserId || "");
  if (policy.unlockFeePoints > 0) {
    if (typeof getPoints !== "function" || typeof savePoints !== "function") return { ok: false, reason: "points_unavailable" };
    const currentPoints = Number(getPoints(currentUserId) || 0);
    if (currentPoints < policy.unlockFeePoints) return { ok: false, reason: "insufficient_points" };
    savePoints(currentPoints - policy.unlockFeePoints, currentUserId);
    if (ownerUserId) savePoints(Number(getPoints(ownerUserId) || 0) + policy.unlockFeePoints, ownerUserId);
  }
  const unlock = {
    id: `wool_unlock_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
    taskId: String(task.id || ""),
    userId: currentUserId,
    ownerUserId,
    pointType: pointType === "reward" ? "reward" : "base",
    feePoints: policy.unlockFeePoints,
    status: "completed",
    createdAt: new Date().toISOString()
  };
  const list = readList(UNLOCKS_KEY);
  list.unshift(unlock);
  writeList(UNLOCKS_KEY, list);
  if (policy.unlockFeePoints > 0) {
    appendPointLedger({
      type: "task_unlock",
      taskId: task.id,
      fromUserId: currentUserId,
      toUserId: ownerUserId,
      pointType,
      amount: policy.unlockFeePoints,
      reason: "解锁羊毛任务完整内容"
    });
  }
  return { ok: true, unlocked: true, alreadyUnlocked: false, feePoints: policy.unlockFeePoints, unlock };
}

function normalizeComment(comment = {}, index = 0) {
  if (!comment || typeof comment !== "object") return null;
  const text = String(comment.text || "").trim();
  const choice = RECOMMEND_LABELS[comment.recommendChoice] ? comment.recommendChoice : "";
  if (!text && !choice) return null;
  const authorId = String(comment.authorId || "");
  return {
    id: String(comment.id || `task_comment_${Date.now()}_${index}`),
    taskId: String(comment.taskId || ""),
    authorId,
    authorLabel: String(comment.authorLabel || (authorId ? "互助用户" : "匿名用户")),
    text,
    recommendChoice: choice,
    recommendLabel: choice ? RECOMMEND_LABELS[choice] : "",
    completed: Boolean(comment.completed),
    status: String(comment.status || "visible"),
    reportCount: toNonNegativeInteger(comment.reportCount, 0),
    createdAt: comment.createdAt || new Date().toISOString(),
    createdAtText: formatCommentDate(comment.createdAt)
  };
}


function getTaskComments(taskId, task = {}) {
  const id = String(taskId || "");
  const stored = readList(COMMENTS_KEY).filter((item) => String(item.taskId || "") === id);
  const seeded = Array.isArray(task.comments) ? task.comments : [];
  const source = [...seeded, ...stored];
  const seen = new Set();
  return source
    .map((item, index) => normalizeComment({ ...item, taskId: id }, index))
    .filter((item) => {
      if (!item || item.status === "hidden" || seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    })
    .sort((left, right) => String(right.createdAt).localeCompare(String(left.createdAt)));
}

function normalizeCommentSummary(summary = {}) {
  const source = summary && typeof summary === "object" ? summary : {};
  const count = toNonNegativeInteger(source.count, 0);
  const worthIt = toNonNegativeInteger(source.worthIt, 0);
  const notWorthIt = toNonNegativeInteger(source.notWorthIt, 0);
  const neutral = toNonNegativeInteger(source.neutral, 0);
  const recommendCount = worthIt + notWorthIt;
  const worthItRate = recommendCount ? Math.round((worthIt / recommendCount) * 100) : 0;
  return {
    count,
    worthIt,
    notWorthIt,
    neutral,
    recommendCount,
    worthItRate,
    worthItRateText: recommendCount ? `${worthItRate}%觉得值得` : "暂无比例",
    text: count
      ? `评论 ${count} 条 · ${recommendCount ? `${worthItRate}%觉得值得` : "暂无比例"}`
      : "暂时还没有评论"
  };
}

function getCommentSummary(comments = []) {
  const list = (Array.isArray(comments) ? comments : []).filter((item) => (
    item && item.status !== "hidden"
  ));
  return normalizeCommentSummary({
    count: list.length,
    worthIt: list.filter((item) => item.recommendChoice === "worth_it").length,
    notWorthIt: list.filter((item) => item.recommendChoice === "not_worth_it").length,
    neutral: list.filter((item) => item.recommendChoice === "neutral").length
  });
}

function addTaskComment(taskId, userId, values = {}) {
  const currentUserId = String(userId || "");
  const text = String(values.text || "").trim();
  const choice = RECOMMEND_LABELS[values.recommendChoice] ? values.recommendChoice : "";
  if (!currentUserId) return { ok: false, reason: "login_required" };
  if (!text && !choice) return { ok: false, reason: "content_required" };
  const comment = normalizeComment({
    id: `task_comment_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
    taskId: String(taskId || ""),
    authorId: currentUserId,
    authorLabel: String(values.authorLabel || "互助用户"),
    text,
    recommendChoice: choice,
    completed: Boolean(values.completed),
    status: "visible",
    createdAt: new Date().toISOString()
  });
  const list = readList(COMMENTS_KEY);
  list.unshift(comment);
  writeList(COMMENTS_KEY, list);
  return { ok: true, comment };
}

function reportTaskComment(taskId, commentId, userId, reason = "内容不实或违规") {
  const currentUserId = String(userId || "");
  const id = String(commentId || "");
  if (!currentUserId || !id) return { ok: false, reason: "login_required" };
  const list = readList(REPORTS_KEY);
  const existing = list.find((item) => String(item.commentId || "") === id && String(item.reporterId || "") === currentUserId);
  if (existing) return { ok: true, alreadyReported: true, report: existing };
  const report = {
    id: `task_comment_report_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
    taskId: String(taskId || ""),
    commentId: id,
    reporterId: currentUserId,
    reason: String(reason || "内容不实或违规"),
    status: "pending",
    createdAt: new Date().toISOString()
  };
  list.unshift(report);
  writeList(REPORTS_KEY, list);
  return { ok: true, alreadyReported: false, report };
}

function getTaskReports(taskId, status = "") {
  const id = String(taskId || "");
  return readList(REPORTS_KEY).filter((item) => (
    String(item.taskId || "") === id && (!status || item.status === status)
  ));
}

function getTaskTips(taskId, userId = "") {
  const id = String(taskId || "");
  const currentUserId = String(userId || "");
  return readList(LEDGER_KEY).filter((item) => (
    item.type === "task_tip"
      && String(item.taskId || "") === id
      && (!currentUserId || String(item.fromUserId || "") === currentUserId)
  ));
}

function tipTaskPublisher(task = {}, userId, amount, getPoints, savePoints, pointType = "base") {
  const currentUserId = String(userId || "");
  const ownerUserId = String(task.ownerUserId || "");
  const tipPoints = toNonNegativeInteger(amount, 0);
  const policy = normalizeWoolPolicy(task.woolPolicy, task);
  if (task.taskKind !== "wool" || !policy.allowTip) return { ok: false, reason: "tip_disabled" };
  if (!currentUserId || !ownerUserId || currentUserId === ownerUserId) return { ok: false, reason: "not_allowed" };
  if (tipPoints < 1) return { ok: false, reason: "invalid_amount" };
  if (typeof getPoints !== "function" || typeof savePoints !== "function") return { ok: false, reason: "points_unavailable" };
  const currentPoints = Number(getPoints(currentUserId) || 0);
  if (currentPoints < tipPoints) return { ok: false, reason: "insufficient_points" };
  savePoints(currentPoints - tipPoints, currentUserId);
  savePoints(Number(getPoints(ownerUserId) || 0) + tipPoints, ownerUserId);
  const ledger = appendPointLedger({
    type: "task_tip",
    taskId: task.id,
    fromUserId: currentUserId,
    toUserId: ownerUserId,
    pointType,
    amount: tipPoints,
    reason: "打赏羊毛任务发布者"
  });
  return { ok: true, amount: tipPoints, ledger };
}

function requestWoolRefund(task = {}, userId, reason = "任务内容或链接失效") {
  const currentUserId = String(userId || "");
  const unlock = getTaskUnlock(task.id, currentUserId);
  if (task.taskKind !== "wool" || !unlock) return { ok: false, reason: "unlock_required" };
  const existing = readList(REFUNDS_KEY).find((item) => (
    String(item.taskId || "") === String(task.id || "")
      && String(item.requesterId || "") === currentUserId
      && item.status === "pending"
  ));
  if (existing) return { ok: true, alreadyRequested: true, refund: existing };
  const refund = {
    id: `wool_refund_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
    taskId: String(task.id || ""),
    requesterId: currentUserId,
    ownerUserId: String(task.ownerUserId || ""),
    unlockId: unlock.id,
    feePoints: toNonNegativeInteger(unlock.feePoints, 0),
    reason: String(reason || "任务内容或链接失效"),
    status: "pending",
    createdAt: new Date().toISOString()
  };
  const list = readList(REFUNDS_KEY);
  list.unshift(refund);
  writeList(REFUNDS_KEY, list);
  return { ok: true, alreadyRequested: false, refund };
}

function getTaskRefunds(taskId, status = "") {
  const id = String(taskId || "");
  return readList(REFUNDS_KEY).filter((item) => (
    String(item.taskId || "") === id && (!status || item.status === status)
  ));
}

function resolveWoolRefund(refundId, status, reviewerId, getPoints, savePoints) {
  const id = String(refundId || "");
  const nextStatus = status === "approved" ? "approved" : (status === "rejected" ? "rejected" : "");
  if (!id || !nextStatus || !String(reviewerId || "")) return { ok: false, reason: "invalid_request" };
  const list = readList(REFUNDS_KEY);
  const current = list.find((item) => String(item.id || "") === id);
  if (!current) return { ok: false, reason: "not_found" };
  if (current.status !== "pending") return { ok: false, reason: "already_processed", refund: current };
  if (nextStatus === "approved") {
    const ownerPoints = typeof getPoints === "function" ? Number(getPoints(current.ownerUserId) || 0) : 0;
    if (ownerPoints < Number(current.feePoints || 0)) return { ok: false, reason: "insufficient_owner_points", refund: current };
    savePoints(ownerPoints - Number(current.feePoints || 0), current.ownerUserId);
    savePoints(Number(getPoints(current.requesterId) || 0) + Number(current.feePoints || 0), current.requesterId);
    appendPointLedger({
      type: "refund",
      taskId: current.taskId,
      fromUserId: current.ownerUserId,
      toUserId: current.requesterId,
      amount: current.feePoints,
      reason: "羊毛任务解锁退款"
    });
  }
  const updated = { ...current, status: nextStatus, reviewerId: String(reviewerId), resolvedAt: new Date().toISOString() };
  writeList(REFUNDS_KEY, list.map((item) => item.id === current.id ? updated : item));
  return { ok: true, refund: updated };
}

module.exports = {
  RECOMMEND_LABELS,
  addTaskComment,
  appendPointLedger,
  getCommentSummary,
  getPointLedger,
  getTaskAccess,
  getTaskComments,
  getTaskReports,
  getTaskRefunds,
  getTaskTips,
  getTaskUnlock,
  getTaskUnlockCount,
  normalizeWoolPolicy,
  normalizeCommentSummary,
  reportTaskComment,
  requestWoolRefund,
  resolveWoolRefund,
  tipTaskPublisher,
  unlockTask
};
