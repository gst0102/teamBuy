const { getCurrentUser } = require("../../utils/dashboard");
const api = require("../../services/api");
const taskLinks = require("./task-links");
const wool = require("./wool");
const sharedPoints = require("../../utils/shared-points");

const TAB_ITEMS = [
  { key: "home", label: "首页", path: "/subpackages/my-tools-mutual-help/index/index" },
  { key: "publish", label: "发布", path: "/subpackages/my-tools-mutual-help/publish/index" },
  { key: "task", label: "任务", path: "/subpackages/my-tools-mutual-help/task-manage/index" },
  { key: "mine", label: "我的", path: "/subpackages/my-tools-mutual-help/mine/index" }
];

const CATEGORY_OPTIONS = [
  "互助",
  "文本校对",
  "资料整理",
  "页面/功能体验",
  "图片/视频标注",
  "商品信息核对",
  "其他"
];
const WOOL_CATEGORY_OPTIONS = [
  "优惠券/折扣",
  "活动/抽奖",
  "返利/免单",
  "免费资源",
  "工具/网站",
  "试用/体验",
  "其他"
];
const TASK_KIND_COPY = {
  miniapp: {
    formTitle: "发布小程序体验任务",
    formSubtitle: "让别人打开小程序，体验后按标准提交反馈。",
    explanation: "适合收集体验、页面测试和使用反馈。",
    titlePlaceholder: "例如：体验鱼泡直聘招聘小程序",
    linkLabel: "目标小程序",
    linkHint: "粘贴后点击“添加入口”",
    linkPlaceholder: "例如：#小程序://名称/路径",
    linkHelp: "案例链接：在目标小程序里点击右上角“…”→“复制链接”，粘贴后点击“添加入口”。",
    contentLabel: "体验说明",
    contentHint: "告诉执行者重点体验什么",
    contentPlaceholder: "例如：重点体验首页、搜索和职位详情，看看哪里不清楚",
    settlementHint: "每次完成：发布者 -5 分，执行者 +4 分。",
    quotaLabel: "任务次数"
  },
  wool: {
    formTitle: "发布羊毛福利",
    formSubtitle: "分享优惠或资源，别人查看后自行使用。",
    explanation: "适合优惠、活动入口、返利信息和免费资源。",
    titlePlaceholder: "例如：本周可领取的招聘优惠券",
    linkLabel: "福利入口",
    linkHint: "粘贴后点击“添加入口”",
    linkPlaceholder: "例如：#小程序://活动名称/路径 或 https://网页地址",
    linkHelp: "案例链接：打开活动页面，点击右上角“…”→“复制链接”，粘贴后点击“添加入口”。",
    contentLabel: "羊毛说明",
    contentHint: "写清福利、步骤、期限和注意事项",
    contentPlaceholder: "例如：福利是什么、谁可以领取、如何操作、有效期到什么时候",
    settlementHint: "查看费用在解锁时结算；没有固定完成奖励，觉得有用可以自愿打赏。",
    quotaLabel: "可领取次数"
  },
  ordinary: {
    formTitle: "发布普通任务",
    formSubtitle: "让别人完成一项工作，并按标准提交材料。",
    explanation: "适合校对、整理、问卷反馈和页面体验。",
    titlePlaceholder: "例如：帮忙校对一段商品文案",
    linkLabel: "参考/操作入口",
    linkHint: "粘贴后点击“添加入口”",
    linkPlaceholder: "例如：#小程序://名称/路径 或 https://网页地址",
    linkHelp: "案例链接：打开参考页面，点击右上角“…”→“复制链接”，粘贴后点击“添加入口”。",
    contentLabel: "任务说明",
    contentHint: "支持文字 / 图片 / 混合",
    contentPlaceholder: "例如：请通读文案，找出错别字并写出修改建议",
    settlementHint: "发布时不扣分；验收通过或 1 天未处理后，发布者扣分、执行者得分。",
    quotaLabel: "任务次数"
  }
};
const TASKS_KEY = "teambuy:mutual-help:demo-tasks:v1";
const INITIAL_POINTS = sharedPoints.INITIAL_POINTS;
const POINT_TYPE_BASE = sharedPoints.POINT_TYPE_BASE;
const POINT_TYPE_REWARD = sharedPoints.POINT_TYPE_REWARD;
const POINT_TYPE_LABELS = sharedPoints.POINT_TYPE_LABELS;
const SUBMISSIONS_KEY_PREFIX = "teambuy:mutual-help:demo-submissions:v1";
const SUBMISSIONS_KEY = "teambuy:mutual-help:demo-submissions:v2";
const AUTO_APPROVE_DAYS = 1;
const AUTO_APPROVE_MS = AUTO_APPROVE_DAYS * 24 * 60 * 60 * 1000;
const THEME_KEY = "teambuy:mutual-help:theme:v1";
const TASK_LAYOUT_KEY = "teambuy:mutual-help:task-layout:v3";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function getTaskKindCopy(taskKind = "ordinary") {
  return clone(TASK_KIND_COPY[taskKind] || TASK_KIND_COPY.ordinary);
}

function getUser() {
  try {
    return getCurrentUser() || null;
  } catch (error) {
    return null;
  }
}

function getUserId(user = getUser()) {
  return String((user && (user.id || user.openid)) || "guest");
}

function scopedKey(prefix, userId) {
  return `${prefix}:${userId || "guest"}`;
}

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
    // The page remains usable when local demo persistence is unavailable.
  }
}

function getTheme() {
  return readStorage(THEME_KEY, "light") === "dark" ? "dark" : "light";
}

function saveTheme(theme) {
  const value = theme === "dark" ? "dark" : "light";
  writeStorage(THEME_KEY, value);
  return value;
}

function getTaskColumns() {
  return Number(readStorage(TASK_LAYOUT_KEY, 1)) === 1 ? 1 : 2;
}

function saveTaskColumns(columns) {
  const value = Number(columns) === 2 ? 2 : 1;
  writeStorage(TASK_LAYOUT_KEY, value);
  return value;
}

function normalizeBlock(block, index = 0) {
  if (!block || typeof block !== "object") return null;
  const type = block.type === "image" ? "image" : "text";
  if (type === "image" && !String(block.url || "").trim()) return null;
  if (type === "text" && !String(block.text || "").trim()) return null;
  return {
    id: block.id || `block_${type}_${index}_${Date.now()}`,
    type,
    text: type === "text" ? String(block.text || "").trim() : "",
    url: type === "image" ? String(block.url || "").trim() : ""
  };
}

function buildBlocks(text, images = []) {
  const blocks = [];
  const content = String(text || "").trim();
  if (content) blocks.push(normalizeBlock({ type: "text", text: content }, 0));
  (Array.isArray(images) ? images : []).forEach((item, index) => {
    const url = typeof item === "string" ? item : item && (item.url || item.path);
    const block = normalizeBlock({ type: "image", url, id: item && item.id }, blocks.length + index);
    if (block) blocks.push(block);
  });
  return blocks.filter(Boolean);
}

function normalizeBlocks(blocks = []) {
  return (Array.isArray(blocks) ? blocks : [])
    .map((block, index) => normalizeBlock(block, index))
    .filter(Boolean);
}

function getTasks() {
  const stored = readStorage(TASKS_KEY, null);
  // Demo tasks were previously bundled into the client. Remove any copies
  // left in existing devices so a successful server sync can never resurrect
  // them after an operator deletes the corresponding server records.
  if (!Array.isArray(stored)) return [];
  const tasks = stored
    .filter((task) => !String(task && task.id || "").startsWith("demo-"))
    .map((task) => ({
    ...task,
    taskLinks: taskLinks.normalizeTaskLinks(task.taskLinks, task.shortLink),
    contentBlocks: Array.isArray(task.contentBlocks) ? task.contentBlocks : [],
    acceptanceCriteriaBlocks: task.taskKind === "wool"
      ? []
      : (Array.isArray(task.acceptanceCriteriaBlocks) ? task.acceptanceCriteriaBlocks : [])
    }));
  if (tasks.length !== stored.length) saveTasks(tasks);
  return tasks;
}

function saveTasks(tasks) {
  writeStorage(TASKS_KEY, Array.isArray(tasks) ? tasks : []);
}

function removeTask(taskId) {
  const requestedId = String(taskId || "").trim();
  if (!requestedId) return false;
  const tasks = getTasks();
  const next = tasks.filter((task) => String(task.id || "") !== requestedId);
  if (next.length === tasks.length) return false;
  saveTasks(next);
  return true;
}

function getTask(taskId) {
  const tasks = getTasks();
  const requestedId = String(taskId || "").trim();
  // Keep the no-id entry useful for the demo's top-level “任务” tab, but
  // never show a different task when a shared deep link is unknown locally.
  return clone(requestedId ? tasks.find((task) => task.id === requestedId) || null : tasks[0] || null);
}

const getPointBalances = sharedPoints.getPointBalances;
const getPointsByType = sharedPoints.getPointsByType;
const getPoints = sharedPoints.getPoints;
const savePointBalances = sharedPoints.savePointBalances;
const savePoints = sharedPoints.savePoints;
const setTotalPoints = sharedPoints.setTotalPoints;
const saveServerPointData = sharedPoints.saveServerPointData;
const syncServerPointData = sharedPoints.syncServerPointData;

function taskPointType(task = {}) {
  if (task.taskKind !== "wool" && task.rewardPointType === POINT_TYPE_REWARD) return POINT_TYPE_REWARD;
  return POINT_TYPE_BASE;
}

function participationDay(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function isActiveSubmission(submission) {
  return Boolean(submission && ["submitted", "reviewing", "approved", "completed"].includes(submission.status));
}

function getSubmissionForTask(task, userId = getUserId()) {
  if (!task || task.taskKind === "wool") return null;
  const submissions = getSubmissions(userId).filter((item) => item.taskId === task.id);
  const repeatPolicy = task.repeatPolicy === "daily" ? "daily" : "once";
  const currentDay = task.viewerState && task.viewerState.participationDay
    ? String(task.viewerState.participationDay)
    : participationDay();
  const candidates = repeatPolicy === "daily"
    ? submissions.filter((item) => String(item.participationDay || "") === currentDay)
    : submissions;
  const active = candidates.filter(isActiveSubmission);
  const ordered = (active.length ? active : candidates).sort((left, right) => String(right.submittedAt || right.updatedAt || "").localeCompare(String(left.submittedAt || left.updatedAt || "")));
  return ordered[0] || null;
}

function decorateTask(task, userId = getUserId()) {
  if (!task) return null;
  const taskKind = task.taskKind || "ordinary";
  const rewardPointType = taskPointType(task);
  const woolPolicy = taskKind === "wool" ? wool.normalizeWoolPolicy(task.woolPolicy, task) : null;
  const reward = taskKind === "wool"
    ? 0
    : Number(task.rewardPoints || 5);
  const executorReward = taskKind === "wool"
    ? 0
    : Number(task.executorReward || (taskKind === "miniapp" ? 4 : Math.floor(reward * 0.8)));
  const remaining = task.remaining === null || task.remaining === undefined || task.remaining === ""
    ? null
    : Math.max(0, Number(task.remaining) || 0);
  const normalizedTaskLinks = taskLinks.normalizeTaskLinks(task.taskLinks, task.shortLink);
  const submissions = getSubmissions(userId).filter((item) => item.taskId === task.id);
  const taskSubmissions = getTaskSubmissions(task.id);
  const repeatPolicy = task.repeatPolicy === "daily" ? "daily" : "once";
  const viewerState = task.viewerState && typeof task.viewerState === "object" ? task.viewerState : null;
  const currentDay = viewerState && viewerState.participationDay
    ? String(viewerState.participationDay)
    : participationDay();
  const currentSubmissions = repeatPolicy === "daily"
    ? submissions.filter((item) => String(item.participationDay || "") === currentDay)
    : submissions;
  const localSubmitted = currentSubmissions.some(isActiveSubmission);
  const submitted = viewerState && Object.prototype.hasOwnProperty.call(viewerState, "submitted")
    ? Boolean(viewerState.submitted)
    : localSubmitted;
  const completedToday = repeatPolicy === "daily"
    ? (viewerState && Object.prototype.hasOwnProperty.call(viewerState, "completedToday")
      ? Boolean(viewerState.completedToday)
      : localSubmitted)
    : false;
  const serverActivitySummary = task.serverActivitySummary && typeof task.serverActivitySummary === "object"
    ? task.serverActivitySummary
    : {};
  const fallbackParticipatedCount = new Set(
    taskSubmissions.map((item) => String(item.executorUserId || "").trim()).filter(Boolean)
  ).size;
  const fallbackSubmittedCount = taskSubmissions.filter((item) => ["submitted", "reviewing", "approved", "completed"].includes(item.status)).length;
  const fallbackAcceptedCount = taskSubmissions.filter((item) => ["approved", "completed"].includes(item.status)).length;
  const fallbackSettledCount = taskSubmissions.filter((item) => item.rewardSettled === true).length;
  const summaryValue = (key, fallback) => {
    if (!Object.prototype.hasOwnProperty.call(serverActivitySummary, key)) return fallback;
    const value = Number(serverActivitySummary[key]);
    return Number.isFinite(value) && value >= 0 ? value : fallback;
  };
  const activitySummary = {
    participatedCount: summaryValue("participatedCount", fallbackParticipatedCount),
    submittedCount: summaryValue("submittedCount", fallbackSubmittedCount),
    acceptedCount: summaryValue("acceptedCount", fallbackAcceptedCount),
    settledCount: summaryValue("settledCount", fallbackSettledCount)
  };
  const status = task.status || "published";
  // An executor device does not have the publisher's account ledger. Never
  // use a local cache for the publisher's balance to decide availability.
  // The server response owns status/remaining. These two fields deliberately
  // take precedence over a stale cached taskClosed flag from an older build.
  const publisherPointValue = Number(task.publisherPoints);
  const publisherPoints = task.publisherPoints === null || task.publisherPoints === undefined || !Number.isFinite(publisherPointValue)
    ? null
    : publisherPointValue;
  const taskBudgetReserved = rewardPointType === POINT_TYPE_REWARD && Number(task.rewardBudgetReserved || 0) > 0;
  const taskClosed = status !== "published" || remaining === 0;
  const statusLabel = taskClosed
    ? (status === "paused" ? "已暂停" : (status === "deleted" ? "已删除" : (status === "pending_review" ? "审核中" : "已结束")))
    : "进行中";
  return {
    ...task,
    taskKind,
    acceptanceCriteriaBlocks: taskKind === "wool"
      ? []
      : (Array.isArray(task.acceptanceCriteriaBlocks) ? task.acceptanceCriteriaBlocks : []),
    taskLinks: normalizedTaskLinks,
    taskLinkSummary: normalizedTaskLinks.length ? taskLinks.summarizeTaskLinks(normalizedTaskLinks) : "",
    shortLink: task.shortLink || (normalizedTaskLinks.find((link) => link.type === "miniapp") || {}).shortLink || "",
    kindLabel: taskKind === "miniapp" ? "小程序任务" : (taskKind === "wool" ? "羊毛" : "普通任务"),
    categoryLabel: taskKind === "miniapp" ? "小程序任务" : (taskKind === "wool" ? "羊毛" : (task.category || "普通任务")),
    publisherPoints,
    rewardPointType,
    rewardPointTypeLabel: POINT_TYPE_LABELS[rewardPointType],
    rewardPoints: reward,
    executorReward,
    rewardText: `+${executorReward} ${POINT_TYPE_LABELS[rewardPointType]}`,
    repeatPolicy,
    participationFrequencyText: taskKind === "wool"
      ? ""
      : (repeatPolicy === "daily" ? "每位用户每天可参与一次" : "每位用户仅可参与一次"),
    participationStatusText: repeatPolicy === "daily" && completedToday ? "今日已完成，明日可参与" : "",
    publisherPointsText: taskBudgetReserved
      ? `发布者${POINT_TYPE_LABELS[rewardPointType]}预算已预留`
      : (publisherPoints === null ? "" : `发布者积分 ${publisherPoints}`),
    remaining,
    remainingText: remaining === null ? "次数不限" : `剩余 ${remaining} 份`,
    deadlineText: task.deadlineText || "长期开放",
    pendingCount: taskKind === "wool" ? 0 : taskSubmissions.filter((item) => item.status === "submitted").length,
    completedCount: taskKind === "wool" ? 0 : taskSubmissions.filter((item) => ["approved", "completed"].includes(item.status) && item.rewardSettled !== false).length,
    activitySummary,
    woolPolicy,
    woolLocked: taskKind === "wool"
      ? !(task.woolAccess && String(task.woolAccess.userId || "") === String(userId || "") && task.woolAccess.unlocked === true)
        && !wool.getTaskAccess(task, userId).unlocked
      : false,
    woolAccessLabel: taskKind === "wool" ? woolPolicy.accessLabel : "",
    woolRewardLabel: taskKind === "wool" ? woolPolicy.rewardLabel : "",
    woolUnlockCount: taskKind === "wool" ? (Number(task.woolAccessCount || 0) || wool.getTaskUnlockCount(task.id)) : 0,
    woolCardRewardText: taskKind === "wool"
      ? (woolPolicy.unlockFeePoints > 0 ? `查看 ${woolPolicy.unlockFeePoints} 分` : "免费查看")
      : "",
    woolAllowTip: taskKind === "wool" ? woolPolicy.allowTip : false,
    commentSummary: Array.isArray(task.serverComments)
      ? wool.getCommentSummary(task.serverComments)
      : (task.commentSummary && typeof task.commentSummary === "object"
        ? wool.normalizeCommentSummary(task.commentSummary)
        : wool.getCommentSummary(wool.getTaskComments(task.id, task))),
    statusLabel,
    submitted,
    completedToday,
    taskClosed
  };
}

function getAllSubmissions() {
  const current = readStorage(SUBMISSIONS_KEY, null);
  if (Array.isArray(current)) return current;

  // Read the old per-user demo records once for a non-destructive migration.
  // The production implementation will use a server-side submission table.
  if (typeof wx === "undefined" || typeof wx.getStorageInfoSync !== "function") return [];
  try {
    const info = wx.getStorageInfoSync() || {};
    return (Array.isArray(info.keys) ? info.keys : [])
      .filter((key) => String(key).indexOf(`${SUBMISSIONS_KEY_PREFIX}:`) === 0)
      .flatMap((key) => {
        const executorUserId = String(key).slice(`${SUBMISSIONS_KEY_PREFIX}:`.length);
        const value = readStorage(key, []);
        return (Array.isArray(value) ? value : []).map((item, index) => ({
          ...item,
          id: item.id || `legacy_submission_${executorUserId}_${item.taskId || index}`,
          executorUserId
        }));
      });
  } catch (error) {
    return [];
  }
}

function saveAllSubmissions(submissions) {
  writeStorage(SUBMISSIONS_KEY, Array.isArray(submissions) ? submissions : []);
}

function getSubmissions(userId = getUserId()) {
  const executorUserId = String(userId || "guest");
  return getAllSubmissions().filter((item) => String(item.executorUserId || "") === executorUserId);
}

function getTaskSubmissions(taskId) {
  const requestedId = String(taskId || "").trim();
  return requestedId ? getAllSubmissions().filter((item) => String(item.taskId || "") === requestedId) : [];
}

function saveSubmission(submission, userId = getUserId()) {
  const executorUserId = String(userId || "guest");
  const task = getTask(submission && submission.taskId);
  const now = new Date().toISOString();
  const submittedAt = submission && submission.submittedAt ? submission.submittedAt : now;
  const reviewDeadlineAt = submission && submission.reviewDeadlineAt
    ? submission.reviewDeadlineAt
    : (task && task.taskKind === "ordinary" ? new Date(new Date(submittedAt).getTime() + AUTO_APPROVE_MS).toISOString() : "");
  const record = {
    ...submission,
    id: submission && submission.id ? submission.id : `submission_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
    taskId: String((submission && submission.taskId) || ""),
    executorUserId,
    ownerUserId: String((submission && submission.ownerUserId) || (task && task.ownerUserId) || ""),
    participationDay: String((submission && submission.participationDay)
      || (task && task.repeatPolicy === "daily" ? participationDay(submittedAt) : "")),
    submittedAt,
    reviewDeadlineAt,
    updatedAt: now
  };
  const list = getAllSubmissions().filter((item) => !(item.taskId === record.taskId && String(item.executorUserId || "") === executorUserId));
  list.unshift(record);
  saveAllSubmissions(list);
  return record;
}

function updateSubmission(submissionId, changes = {}) {
  const id = String(submissionId || "");
  let updated = null;
  const list = getAllSubmissions().map((item) => {
    if (String(item.id || "") !== id) return item;
    updated = { ...item, ...changes, updatedAt: new Date().toISOString() };
    return updated;
  });
  if (updated) saveAllSubmissions(list);
  return updated;
}

function settleSubmission(submission, options = {}) {
  const submissionId = typeof submission === "string" ? submission : submission && submission.id;
  const current = getAllSubmissions().find((item) => String(item.id || "") === String(submissionId || ""));
  if (!current) return { ok: false, reason: "submission_not_found", submission: null };
  if (current.rewardSettled === true && ["approved", "completed"].includes(current.status)) {
    return { ok: true, alreadySettled: true, submission: current };
  }
  const task = getTask(current.taskId);
  if (task && task.taskKind === "wool") return { ok: false, reason: "wool_has_no_submission", submission: current };
  const ownerUserId = String(current.ownerUserId || (task && task.ownerUserId) || "");
  const executorUserId = String(current.executorUserId || "");
  const pointType = taskPointType(task || {});
  const publisherCost = Math.max(0, Number((task && task.rewardPoints) || 5));
  const executorReward = Math.max(0, Number((task && task.executorReward) || (task && task.taskKind === "miniapp" ? 4 : Math.floor(publisherCost * 0.8))));
  if (!ownerUserId || !executorUserId) return { ok: false, reason: "missing_participants", submission: current };
  if (getPointsByType(ownerUserId, pointType) < publisherCost && pointType === POINT_TYPE_REWARD) return { ok: false, reason: "insufficient_publisher_points", submission: current };
  if (pointType === POINT_TYPE_BASE && getPoints(ownerUserId) < publisherCost) return { ok: false, reason: "insufficient_publisher_points", submission: current };

  if (publisherCost > 0) {
    if (pointType === POINT_TYPE_REWARD) {
      savePoints(getPointsByType(ownerUserId, POINT_TYPE_REWARD) - publisherCost, ownerUserId, POINT_TYPE_REWARD);
    } else {
      setTotalPoints(getPoints(ownerUserId) - publisherCost, ownerUserId);
    }
    wool.appendPointLedger({
      type: "task_settlement_cost",
      taskId: task && task.id,
      fromUserId: ownerUserId,
      toUserId: "platform",
      amount: publisherCost,
      pointType,
      reason: "任务完成结算扣除"
    });
  }
  if (executorReward > 0) {
    if (pointType === POINT_TYPE_REWARD) {
      savePoints(getPointsByType(executorUserId, POINT_TYPE_REWARD) + executorReward, executorUserId, POINT_TYPE_REWARD);
    } else {
      setTotalPoints(getPoints(executorUserId) + executorReward, executorUserId);
    }
    wool.appendPointLedger({
      type: "task_reward",
      taskId: task && task.id,
      fromUserId: "platform",
      toUserId: executorUserId,
      amount: executorReward,
      pointType,
      reason: "任务完成奖励"
    });
  }
  const settled = updateSubmission(current.id, {
    status: options.autoApproved ? "approved" : (task && task.taskKind === "miniapp" ? "completed" : "approved"),
    autoApproved: Boolean(options.autoApproved),
    rewardSettled: true,
    approvedAt: new Date().toISOString(),
    completedAt: new Date().toISOString(),
    publisherCost,
    executorReward
  });
  if (task) {
    const tasks = getTasks().map((item) => {
      if (item.id !== task.id) return item;
      const remaining = item.remaining === null || item.remaining === undefined || item.remaining === ""
        ? item.remaining
        : Math.max(0, Number(item.remaining) - 1);
      return { ...item, remaining, completedCount: getTaskSubmissions(item.id).filter((row) => row.rewardSettled === true).length };
    });
    saveTasks(tasks);
  }
  return { ok: true, alreadySettled: false, submission: settled };
}

function approveSubmission(taskId, submissionId, reviewerUserId) {
  const task = getTask(taskId);
  const userId = String(reviewerUserId || "");
  const current = getTaskSubmissions(taskId).find((item) => String(item.id || "") === String(submissionId || ""));
  if (!task || !current || String(task.ownerUserId || "") !== userId) {
    return { ok: false, reason: "not_allowed", submission: current || null };
  }
  if (current.status !== "submitted") return { ok: false, reason: "already_processed", submission: current };
  return settleSubmission(current);
}

function syncAutoApprovedSubmissions(taskId = "") {
  const now = Date.now();
  const candidates = getAllSubmissions().filter((item) => {
    if (taskId && String(item.taskId || "") !== String(taskId)) return false;
    if (item.status !== "submitted" || !item.reviewDeadlineAt) return false;
    const task = getTask(item.taskId);
    if (!task || task.taskKind === "wool") return false;
    const deadline = new Date(item.reviewDeadlineAt).getTime();
    return Number.isFinite(deadline) && deadline <= now;
  });
  return candidates.map((item) => settleSubmission(item, { autoApproved: true }));
}

function navigateTab(tabKey, currentKey, query = "") {
  if (tabKey === currentKey) return;
  const item = TAB_ITEMS.find((entry) => entry.key === tabKey) || TAB_ITEMS[0];
  wx.redirectTo({ url: `${item.path}${query ? `?${query}` : ""}` });
}

function requireLogin(returnUrl) {
  const user = getUser();
  if (user) return user;
  wx.reLaunch({ url: `/pages/login/index?returnUrl=${encodeURIComponent(returnUrl || TAB_ITEMS[0].path)}` });
  return null;
}

function recordActivity(eventType, task, userId = getUserId(), options = {}) {
  const currentUserId = String(userId || "");
  if (!currentUserId || currentUserId === "guest" || !task || !task.id) return Promise.resolve(null);
  const linkId = String(options.linkId || "");
  const sessionId = String(options.sessionId || "");
  const idempotencyKey = String(options.idempotencyKey || "").trim()
    || (sessionId
      ? `${eventType}:${currentUserId}:${task.id}:${linkId}:${sessionId}`
      : `${eventType}:${currentUserId}:${task.id}`);
  return api.recordMutualHelpActivity({
    userId: currentUserId,
    eventType,
    taskId: String(task.id),
    taskKind: task.taskKind || "ordinary",
    linkId,
    sessionId,
    metadata: options.metadata && typeof options.metadata === "object" ? options.metadata : {},
    idempotencyKey
  });
}

function mergeServerTasks(serverTasks) {
  const normalized = (Array.isArray(serverTasks) ? serverTasks : []).filter(Boolean).map((task) => ({
    ...task,
    taskLinks: taskLinks.normalizeTaskLinks(task.taskLinks, task.shortLink),
    contentBlocks: Array.isArray(task.contentBlocks) ? task.contentBlocks : [],
    acceptanceCriteriaBlocks: task.taskKind === "wool"
      ? []
      : (Array.isArray(task.acceptanceCriteriaBlocks) ? task.acceptanceCriteriaBlocks : [])
  }));
  saveTasks(normalized);
  return normalized;
}

async function syncServerTasks(userId = getUserId()) {
  const cleanUserId = String(userId || "").trim();
  if (!cleanUserId || cleanUserId === "guest") return getTasks();
  // Migrate tasks created by the previous local-only build once. The client
  // id is accepted by the API, making retries idempotent across devices.
  const localTasks = getTasks().filter((task) => task.ownerUserId === cleanUserId && String(task.id || "").indexOf("local_") === 0);
  for (const task of localTasks) {
    try {
      await api.createMutualHelpTask({ ...task, ownerUserId: cleanUserId });
    } catch (error) {
      // Keep the local record visible until the server accepts the migration.
    }
  }
  async function fetchAllTasks(params) {
    const items = [];
    let cursor = "";
    for (let page = 0; page < 20; page += 1) {
      const response = await api.fetchMutualHelpTasks({ ...params, cursor, limit: 50 });
      const data = response && response.data ? response.data : {};
      if (Array.isArray(data.items)) items.push(...data.items);
      if (!data.hasMore || !data.nextCursor) break;
      cursor = data.nextCursor;
    }
    return items;
  }
  const [publicItems, ownItems] = await Promise.all([
    fetchAllTasks({ userId: cleanUserId }),
    fetchAllTasks({ userId: cleanUserId, ownerOnly: true })
  ]);
  return mergeServerTasks([...ownItems, ...publicItems]);
}

async function syncServerTask(taskId, userId = getUserId()) {
  const response = await api.fetchMutualHelpTaskDetail(taskId, userId);
  const data = response && response.data ? response.data : {};
  if (data.task) {
    const serverTask = {
      ...data.task,
      woolAccess: data.woolAccess || null,
      woolAccessCount: Number(data.woolAccessCount || 0),
      serverComments: Array.isArray(data.comments) ? data.comments : [],
      serverActivitySummary: data.activitySummary && typeof data.activitySummary === "object" ? data.activitySummary : {},
      serverWoolTip: data.woolTip || null,
      serverWoolRefund: data.woolRefund || null,
      serverPendingRefunds: Array.isArray(data.pendingRefunds) ? data.pendingRefunds : [],
      serverPendingCommentReports: Number(data.pendingCommentReports || 0)
    };
    const current = getTasks().filter((item) => item.id !== data.task.id);
    saveTasks([serverTask, ...current]);
  }
  const incoming = [];
  if (data.submission) incoming.push(data.submission);
  if (Array.isArray(data.submissions)) incoming.push(...data.submissions);
  if (incoming.length) {
    const ids = new Set(incoming.map((item) => String(item.id || "")));
    const merged = getAllSubmissions().filter((item) => !ids.has(String(item.id || "")) && item.taskId !== taskId);
    saveAllSubmissions([...incoming, ...merged]);
  }
  return data;
}

function unlockWoolTask(taskId, userId) {
  const task = getTask(taskId) || {};
  const pointType = taskPointType(task);
  const result = wool.unlockTask(
    task,
    userId,
    (currentUserId) => getPoints(currentUserId),
    (points, currentUserId) => setTotalPoints(points, currentUserId),
    POINT_TYPE_BASE
  );
  if (result.ok && !result.alreadyUnlocked && String(task.ownerUserId || "") !== String(userId || "")
      && task.remaining !== null && task.remaining !== undefined && task.remaining !== "") {
    const remaining = Math.max(0, Number(task.remaining) || 0);
    saveTasks(getTasks().map((item) => item.id === task.id ? { ...item, remaining: Math.max(0, remaining - 1) } : item));
  }
  return result;
}

function addTaskComment(taskId, userId, values = {}) {
  return wool.addTaskComment(taskId, userId, values);
}

function reportTaskComment(taskId, commentId, userId, reason) {
  return wool.reportTaskComment(taskId, commentId, userId, reason);
}

function requestWoolRefund(taskId, userId, reason) {
  return wool.requestWoolRefund(getTask(taskId) || {}, userId, reason);
}

function tipTaskPublisher(taskId, userId, amount) {
  const task = getTask(taskId) || {};
  const pointType = POINT_TYPE_BASE;
  return wool.tipTaskPublisher(
    task,
    userId,
    amount,
    (currentUserId) => getPoints(currentUserId),
    (points, currentUserId) => setTotalPoints(points, currentUserId),
    pointType
  );
}

module.exports = {
  TAB_ITEMS,
  CATEGORY_OPTIONS,
  WOOL_CATEGORY_OPTIONS,
  POINT_TYPE_BASE,
  POINT_TYPE_REWARD,
  POINT_TYPE_LABELS,
  buildBlocks,
  decorateTask,
  getTaskColumns,
  getTaskKindCopy,
  getTheme,
  getPoints,
  getAllSubmissions,
  getSubmissions,
  getTaskSubmissions,
  getSubmissionForTask,
  participationDay,
  getTaskAccess: wool.getTaskAccess,
  getTaskComments: wool.getTaskComments,
  getCommentSummary: wool.getCommentSummary,
  getTaskReports: wool.getTaskReports,
  getTaskRefunds: wool.getTaskRefunds,
  getTaskTips: wool.getTaskTips,
  getTaskUnlock: wool.getTaskUnlock,
  getTaskUnlockCount: wool.getTaskUnlockCount,
  getPointLedger: wool.getPointLedger,
  getTask,
  removeTask,
  getTasks,
  getUser,
  getUserId,
  getPointBalances,
  getPointsByType,
  navigateTab,
  normalizeBlock,
  normalizeBlocks,
  requireLogin,
  recordActivity,
  mergeServerTasks,
  syncServerTasks,
  syncServerTask,
  saveTaskColumns,
  saveTheme,
  savePointBalances,
  saveServerPointData,
  syncServerPointData,
  savePoints,
  setTotalPoints,
  taskPointType,
  saveSubmission,
  unlockWoolTask,
  addTaskComment,
  reportTaskComment,
  requestWoolRefund,
  tipTaskPublisher,
  resolveWoolRefund: wool.resolveWoolRefund,
  normalizeWoolPolicy: wool.normalizeWoolPolicy,
  saveTasks,
  settleSubmission,
  approveSubmission,
  syncAutoApprovedSubmissions,
  AUTO_APPROVE_DAYS,
  normalizeTaskLinks: taskLinks.normalizeTaskLinks,
  parseTaskLink: taskLinks.parseTaskLink,
  summarizeTaskLinks: taskLinks.summarizeTaskLinks
};
