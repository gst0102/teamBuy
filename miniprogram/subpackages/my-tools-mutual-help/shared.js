const { getCurrentUser } = require("../../utils/dashboard");
const api = require("../../services/api");
const taskLinks = require("./task-links");
const wool = require("./wool");

const TAB_ITEMS = [
  { key: "home", label: "首页", path: "/subpackages/my-tools-mutual-help/index/index" },
  { key: "publish", label: "发布", path: "/subpackages/my-tools-mutual-help/publish/index" },
  { key: "task", label: "任务", path: "/subpackages/my-tools-mutual-help/task-manage/index" },
  { key: "mine", label: "我的", path: "/subpackages/my-tools-mutual-help/mine/index" }
];

const CATEGORY_OPTIONS = [
  "文本校对",
  "资料整理",
  "页面/功能体验",
  "问卷/反馈",
  "图片/视频标注",
  "商品信息核对",
  "人工调研",
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
    formSubtitle: "请别人打开你的小程序，体验后回来提交完成。",
    explanation: "适合收集小程序体验、页面测试和使用反馈；反馈文字和图片可以不填。",
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
    formSubtitle: "分享优惠、活动或资源，别人查看后自行使用。",
    explanation: "适合优惠券、活动入口、返利信息和免费资源；无需提交材料，也不需要发布者验收。",
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
    formSubtitle: "请别人完成一项人工工作，并提交文字或图片材料。",
    explanation: "适合文本校对、资料整理、问卷反馈和页面体验；必须写清做什么、交什么、什么结果算完成。",
    titlePlaceholder: "例如：帮忙校对一段商品文案",
    linkLabel: "参考/操作入口",
    linkHint: "粘贴后点击“添加入口”",
    linkPlaceholder: "例如：#小程序://名称/路径 或 https://网页地址",
    linkHelp: "案例链接：打开参考页面，点击右上角“…”→“复制链接”，粘贴后点击“添加入口”。",
    contentLabel: "任务说明",
    contentHint: "支持文字 / 图片 / 混合",
    contentPlaceholder: "例如：请通读文案，找出错别字并写出修改建议",
    settlementHint: "发布时不扣分；验收通过或 5 天未处理后，发布者扣分、执行者得分。",
    quotaLabel: "任务次数"
  }
};
const TASKS_KEY = "teambuy:mutual-help:demo-tasks:v1";
// The page implementation is still a local demo. Keep the first-entry seed
// explicit so an old unfinished-demo balance of 0 cannot leak into the agreed
// initial balance of 100 points. This must be replaced by a server ledger in
// the production implementation.
const POINTS_KEY_PREFIX = "teambuy:mutual-help:demo-points:v2";
const POINTS_SEED_KEY_PREFIX = "teambuy:mutual-help:demo-points-seed:v2";
const POINTS_SEED_VERSION = "100-v2";
const INITIAL_POINTS = 100;
const SUBMISSIONS_KEY_PREFIX = "teambuy:mutual-help:demo-submissions:v1";
const SUBMISSIONS_KEY = "teambuy:mutual-help:demo-submissions:v2";
const AUTO_APPROVE_DAYS = 5;
const AUTO_APPROVE_MS = AUTO_APPROVE_DAYS * 24 * 60 * 60 * 1000;
const THEME_KEY = "teambuy:mutual-help:theme:v1";
const TASK_LAYOUT_KEY = "teambuy:mutual-help:task-layout:v2";

const DEMO_TASKS = [
  {
    id: "demo-miniapp-recruitment",
    taskKind: "miniapp",
    title: "体验一个招聘小程序",
    category: "小程序任务",
    description: "打开页面，停留后提交体验反馈",
    contentBlocks: [{ type: "text", text: "打开目标小程序，体验首页和搜索流程，返回后可以写下你的使用感受。" }],
    acceptanceCriteriaBlocks: [{ type: "text", text: "成功打开目标页面，停留不少于 3 秒，返回后点击完成任务。反馈文字和图片可选。" }],
    shortLink: "#小程序://招聘工具/体验任务",
    publisherPoints: 368,
    rewardPoints: 5,
    executorReward: 4,
    remaining: 18,
    deadlineText: "长期开放",
    status: "published"
  },
  {
    id: "demo-proofread-copy",
    taskKind: "ordinary",
    title: "帮忙校对一段商品文案",
    category: "文本校对",
    description: "找出错别字，并说明修改原因",
    contentBlocks: [{ type: "text", text: "请通读商品文案，找出错别字、病句或表达不清的地方，并给出修改建议。" }],
    acceptanceCriteriaBlocks: [{ type: "text", text: "至少找出 1 处有效问题，标明原文位置、修改后的完整句子，并说明修改原因。" }],
    publisherPoints: 246,
    rewardPoints: 10,
    executorReward: 8,
    remaining: 6,
    deadlineText: "明天截止",
    status: "published"
  },
  {
    id: "demo-page-test",
    taskKind: "ordinary",
    title: "体验资料整理助手的新页面",
    category: "页面/功能体验",
    description: "按流程走一遍并反馈卡点",
    contentBlocks: [{ type: "text", text: "按页面提示完成一次新建资料、上传图片和保存操作。" }],
    acceptanceCriteriaBlocks: [{ type: "text", text: "提交操作结果，并至少描述一个顺畅点或一个需要改进的地方。" }],
    publisherPoints: 128,
    rewardPoints: 8,
    executorReward: 6,
    remaining: 12,
    deadlineText: "3 天后截止",
    status: "published"
  },
  {
    id: "demo-wool-coupon",
    taskKind: "wool",
    title: "本周可领取的招聘优惠券",
    category: "优惠券/折扣",
    description: "查看活动说明，符合条件即可领取优惠券",
    contentBlocks: [
      { type: "text", text: "打开活动入口，确认领取条件和有效期，再按页面提示领取或使用。" }
    ],
    taskLinks: [{ raw: "#小程序://招聘工具/优惠券活动" }],
    woolPolicy: {
      unlockFeePoints: 2,
      allowTip: true
    },
    publisherPoints: 420,
    rewardPoints: 0,
    executorReward: 0,
    remaining: 20,
    deadlineText: "本周截止",
    ownerUserId: "demo-wool-publisher",
    comments: [
      {
        id: "demo-wool-comment-1",
        recommendChoice: "worth_it",
        text: "入口可以正常打开，领取条件写得比较清楚。",
        authorLabel: "已完成用户",
        completed: true,
        createdAt: "2026-08-30T12:00:00.000Z"
      },
      {
        id: "demo-wool-comment-2",
        recommendChoice: "neutral",
        text: "部分地区可能没有资格，建议先看清活动范围。",
        authorLabel: "已解锁用户",
        createdAt: "2026-08-29T12:00:00.000Z"
      }
    ],
    status: "published"
  }
];

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
  return Number(readStorage(TASK_LAYOUT_KEY, 2)) === 1 ? 1 : 2;
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
  // An empty array is an intentional result after the user deletes all of
  // their local demo tasks; only a missing key should seed the demo list.
  if (!Array.isArray(stored)) return clone(DEMO_TASKS);
  return stored.map((task) => ({
    ...task,
    taskLinks: taskLinks.normalizeTaskLinks(task.taskLinks, task.shortLink),
    contentBlocks: Array.isArray(task.contentBlocks) ? task.contentBlocks : [],
    acceptanceCriteriaBlocks: task.taskKind === "wool"
      ? []
      : (Array.isArray(task.acceptanceCriteriaBlocks) ? task.acceptanceCriteriaBlocks : [])
  }));
}

function saveTasks(tasks) {
  writeStorage(TASKS_KEY, Array.isArray(tasks) ? tasks : []);
}

function getTask(taskId) {
  const tasks = getTasks();
  const requestedId = String(taskId || "").trim();
  // Keep the no-id entry useful for the demo's top-level “任务” tab, but
  // never show a different task when a shared deep link is unknown locally.
  return clone(requestedId ? tasks.find((task) => task.id === requestedId) || null : tasks[0] || null);
}

function getPoints(userId = getUserId()) {
  const pointsKey = scopedKey(POINTS_KEY_PREFIX, userId);
  const seedKey = scopedKey(POINTS_SEED_KEY_PREFIX, userId);
  if (readStorage(seedKey, "") !== POINTS_SEED_VERSION) {
    writeStorage(pointsKey, INITIAL_POINTS);
    writeStorage(seedKey, POINTS_SEED_VERSION);
    return INITIAL_POINTS;
  }
  const value = Number(readStorage(pointsKey, INITIAL_POINTS));
  return Number.isFinite(value) ? Math.max(0, value) : INITIAL_POINTS;
}

function savePoints(points, userId = getUserId()) {
  const value = Math.max(0, Number(points) || 0);
  writeStorage(scopedKey(POINTS_KEY_PREFIX, userId), value);
  writeStorage(scopedKey(POINTS_SEED_KEY_PREFIX, userId), POINTS_SEED_VERSION);
  return value;
}

function decorateTask(task, userId = getUserId()) {
  if (!task) return null;
  const taskKind = task.taskKind || "ordinary";
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
  const submitted = submissions.some((item) => ["submitted", "approved", "completed"].includes(item.status));
  const status = task.status || "published";
  const ownerPoints = task.ownerUserId ? getPoints(task.ownerUserId) : null;
  const publisherPoints = ownerPoints === null ? Number(task.publisherPoints || 0) : ownerPoints;
  const insufficientPoints = taskKind !== "wool" && Boolean(task.ownerUserId) && ownerPoints < reward;
  const taskClosed = status !== "published" || remaining === 0 || insufficientPoints;
  const statusLabel = taskClosed
    ? (status === "paused" ? "已暂停" : (status === "deleted" ? "已删除" : (insufficientPoints ? "积分不足" : "已结束")))
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
    rewardPoints: reward,
    executorReward,
    rewardText: `+${executorReward} 分`,
    publisherPointsText: `发布者积分 ${publisherPoints}`,
    remaining,
    remainingText: remaining === null ? "次数不限" : `剩余 ${remaining} 份`,
    deadlineText: task.deadlineText || "长期开放",
    pendingCount: taskKind === "wool" ? 0 : taskSubmissions.filter((item) => item.status === "submitted").length,
    completedCount: taskKind === "wool" ? 0 : taskSubmissions.filter((item) => ["approved", "completed"].includes(item.status) && item.rewardSettled !== false).length,
    woolPolicy,
    woolLocked: taskKind === "wool" ? !wool.getTaskAccess(task, userId).unlocked : false,
    woolAccessLabel: taskKind === "wool" ? woolPolicy.accessLabel : "",
    woolRewardLabel: taskKind === "wool" ? woolPolicy.rewardLabel : "",
    woolUnlockCount: taskKind === "wool" ? wool.getTaskUnlockCount(task.id) : 0,
    woolCardRewardText: taskKind === "wool"
      ? (woolPolicy.unlockFeePoints > 0 ? `查看 ${woolPolicy.unlockFeePoints} 分` : "免费查看")
      : "",
    woolAllowTip: taskKind === "wool" ? woolPolicy.allowTip : false,
    commentSummary: wool.getCommentSummary(wool.getTaskComments(task.id, task)),
    insufficientPoints,
    statusLabel,
    submitted,
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
  const publisherCost = Math.max(0, Number((task && task.rewardPoints) || 5));
  const executorReward = Math.max(0, Number((task && task.executorReward) || (task && task.taskKind === "miniapp" ? 4 : Math.floor(publisherCost * 0.8))));
  if (!ownerUserId || !executorUserId) return { ok: false, reason: "missing_participants", submission: current };
  if (getPoints(ownerUserId) < publisherCost) return { ok: false, reason: "insufficient_publisher_points", submission: current };

  if (publisherCost > 0) {
    savePoints(getPoints(ownerUserId) - publisherCost, ownerUserId);
    wool.appendPointLedger({
      type: "task_settlement_cost",
      taskId: task && task.id,
      fromUserId: ownerUserId,
      toUserId: "platform",
      amount: publisherCost,
      reason: "任务完成结算扣除"
    });
  }
  if (executorReward > 0) {
    savePoints(getPoints(executorUserId) + executorReward, executorUserId);
    wool.appendPointLedger({
      type: "task_reward",
      taskId: task && task.id,
      fromUserId: "platform",
      toUserId: executorUserId,
      amount: executorReward,
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

function recordActivity(eventType, task, userId = getUserId()) {
  const currentUserId = String(userId || "");
  if (!currentUserId || currentUserId === "guest" || !task || !task.id) return Promise.resolve(null);
  return api.recordMutualHelpActivity({
    userId: currentUserId,
    eventType,
    taskId: String(task.id),
    taskKind: task.taskKind || "ordinary",
    idempotencyKey: `${eventType}:${currentUserId}:${task.id}`
  });
}

function unlockWoolTask(taskId, userId) {
  const task = getTask(taskId) || {};
  const result = wool.unlockTask(task, userId, getPoints, savePoints);
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
  return wool.tipTaskPublisher(getTask(taskId) || {}, userId, amount, getPoints, savePoints);
}

module.exports = {
  TAB_ITEMS,
  CATEGORY_OPTIONS,
  WOOL_CATEGORY_OPTIONS,
  buildBlocks,
  decorateTask,
  getTaskColumns,
  getTaskKindCopy,
  getTheme,
  getPoints,
  getAllSubmissions,
  getSubmissions,
  getTaskSubmissions,
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
  getTasks,
  getUser,
  getUserId,
  navigateTab,
  normalizeBlock,
  normalizeBlocks,
  requireLogin,
  recordActivity,
  saveTaskColumns,
  saveTheme,
  savePoints,
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
