const shared = require("./shared");
const {
  SHARE_CARD_STYLE_VERSION,
  buildShareCardMessage,
  buildShareCardTitle,
  createShareSnapshotFingerprint,
  isShareImageUrl,
  prepareShareCardImage,
  setShareMenuEnabled
} = require("../../plugins/share-snapshot/index");

const TASK_SHARE_PATH = "/subpackages/my-tools-mutual-help/task-detail/index";
const MUTUAL_TASK_SHARE_CARD_STYLE_VERSION = "mutual_task_share_v2";

function taskShareRevision(task = {}) {
  return String(task.updatedAt || task.createdAt || "0");
}

function isTaskShareable(task = {}) {
  return Boolean(
    task
      && task.id
      && task.taskClosed !== true
      && task.status !== "paused"
      && task.status !== "closed"
      && task.status !== "completed"
      && task.remaining !== 0
  );
}

function taskSharePath(task = {}) {
  const taskId = String(task.id || "").trim();
  return taskId ? `${TASK_SHARE_PATH}?id=${encodeURIComponent(taskId)}&source=share` : "";
}

function firstTaskImage(task = {}) {
  const acceptanceBlocks = task.taskKind === "wool" ? [] : (Array.isArray(task.acceptanceCriteriaBlocks) ? task.acceptanceCriteriaBlocks : []);
  return [
    ...(Array.isArray(task.contentBlocks) ? task.contentBlocks : []),
    ...acceptanceBlocks
  ]
    .filter((block) => block && block.type === "image" && String(block.url || "").trim())
    .map((block) => String(block.url).trim())
    .find(Boolean) || "";
}

function taskShareSummary(task = {}) {
  const description = String(task.description || "").trim();
  if (description && !/^#小程序:\/\//.test(description) && !/^https?:\/\//i.test(description)) {
    return description;
  }
  if (task.taskKind === "miniapp") return "打开目标小程序，完成体验后提交反馈";
  if (task.taskKind === "wool") return "查看福利说明并按步骤使用";
  return "按任务说明完成后提交材料";
}

function buildTaskShareSource(task = {}) {
  const imageUrl = firstTaskImage(task);
  const links = shared.normalizeTaskLinks(task.taskLinks, task.shortLink);
  const woolPolicy = task.taskKind === "wool"
    ? shared.normalizeWoolPolicy(task.woolPolicy, task)
    : null;
  const remaining = task.remaining === null || task.remaining === undefined
    ? "长期开放"
    : `剩余 ${Math.max(0, Number(task.remaining) || 0)} 份`;
  const facts = task.taskKind === "wool"
    ? [
        woolPolicy.unlockFeePoints > 0 ? "解锁 " + woolPolicy.unlockFeePoints + " 分" : "免费查看",
        woolPolicy.allowTip ? "可自愿打赏" : "无额外积分",
        remaining
      ]
    : [
        `+${Number(task.executorReward || 0)} 分`,
        remaining,
        String(task.deadlineText || "长期开放").trim()
      ];
  return {
    layoutId: imageUrl ? "image_info" : "text_info",
    templateKind: "mutual_task",
    title: String(task.title || "互帮互助任务").trim() || "互帮互助任务",
    summary: taskShareSummary(task),
    badge: task.taskKind === "miniapp" ? "小程序任务" : (task.taskKind === "wool" ? "羊毛" : "普通任务"),
    facts,
    primaryImageUrl: imageUrl,
    shareTargetLabel: links.length ? shared.summarizeTaskLinks(links) : "任务入口",
    marketingLine: "互助赚积分，让别人帮你完成",
    footer: "点开任务，完成后赚积分"
  };
}

function taskShareFingerprint(task, source) {
  return createShareSnapshotFingerprint(
    "mutual_task",
    task && task.id,
    taskShareRevision(task),
    MUTUAL_TASK_SHARE_CARD_STYLE_VERSION,
    source
  );
}

function getReadyTaskSnapshot(task, source) {
  const snapshot = task && task.shareSnapshot;
  if (!snapshot || snapshot.status !== "ready" || !isShareImageUrl(snapshot.url)) return null;
  if (String(snapshot.styleId || "") !== MUTUAL_TASK_SHARE_CARD_STYLE_VERSION) return null;
  if (String(snapshot.sourceRevision || "") !== taskShareRevision(task)) return null;
  if (String(snapshot.fingerprint || "") !== taskShareFingerprint(task, source)) return null;
  return snapshot;
}

function buildTaskShareSnapshot(task, source, imageUrl) {
  return {
    status: "ready",
    url: imageUrl,
    styleId: MUTUAL_TASK_SHARE_CARD_STYLE_VERSION,
    sourceRevision: taskShareRevision(task),
    fingerprint: taskShareFingerprint(task, source),
    generatedAt: new Date().toISOString()
  };
}

function persistTaskShareSnapshot(task, snapshot) {
  const tasks = shared.getTasks().map((item) => item.id === task.id
    ? { ...item, shareSnapshot: snapshot }
    : item);
  shared.saveTasks(tasks);
}

function setTaskShareState(page, values) {
  if (!page || !page.setData) return;
  page.setData({
    shareCardReady: false,
    shareCardImage: "",
    shareStatusText: "分享准备中",
    ...values
  });
}

async function prepareTaskShareImage(page, task, ownerUserId = "") {
  if (!isTaskShareable(task)) {
    setTaskShareState(page, { shareStatusText: "任务已结束" });
    setShareMenuEnabled(false);
    return "";
  }
  const source = buildTaskShareSource(task);
  const existing = getReadyTaskSnapshot(task, source);
  if (existing) {
    setTaskShareState(page, {
      shareCardReady: true,
      shareCardImage: existing.url,
      shareStatusText: "分享任务"
    });
    setShareMenuEnabled(true);
    return existing.url;
  }

  const imageUrl = await prepareTaskShareImageForList(page, task, ownerUserId);
  if (!isShareImageUrl(imageUrl)) {
    setTaskShareState(page, { shareStatusText: ownerUserId ? "分享暂时失败，请重试" : "登录后即可分享" });
    setShareMenuEnabled(false);
    return "";
  }

  const latestTask = shared.getTask(task.id) || task;
  const snapshot = latestTask.shareSnapshot || buildTaskShareSnapshot(task, source, imageUrl);
  setTaskShareState(page, {
    shareCardReady: true,
    shareCardImage: imageUrl,
    shareStatusText: "分享任务",
    task: { ...(page.data && page.data.task ? page.data.task : task), shareSnapshot: snapshot }
  });
  return imageUrl;
}

async function prepareTaskShareImageForList(page, task, ownerUserId = "") {
  if (!isTaskShareable(task)) return "";
  const source = buildTaskShareSource(task);
  const existing = getReadyTaskSnapshot(task, source);
  if (existing) return existing.url;
  const imageUrl = await prepareShareCardImage(page, {
    ...source,
    path: taskSharePath(task)
  }, { ownerUserId });
  if (!isShareImageUrl(imageUrl)) return "";
  persistTaskShareSnapshot(task, buildTaskShareSnapshot(task, source, imageUrl));
  return imageUrl;
}

function buildTaskShareMessage(page, task) {
  const path = taskSharePath(task);
  if (!isTaskShareable(task) || !path) {
    setShareMenuEnabled(false);
    return null;
  }
  const source = buildTaskShareSource(task);
  const snapshot = getReadyTaskSnapshot(task, source);
  if (snapshot) {
    return {
      title: buildShareCardTitle(`${String(task.title || "互帮互助任务").trim()}｜邀请你完成任务`),
      path,
      imageUrl: snapshot.url
    };
  }
  const pageTask = page && page.data && page.data.task;
  if (!pageTask || pageTask.id !== task.id) {
    setShareMenuEnabled(false);
    return null;
  }
  return buildShareCardMessage(page, {
    ...buildTaskShareSource(task),
    title: `${String(task.title || "互帮互助任务").trim()}｜邀请你完成任务`,
    path
  });
}

module.exports = {
  MUTUAL_TASK_SHARE_CARD_STYLE_VERSION,
  TASK_SHARE_PATH,
  buildTaskShareMessage,
  buildTaskShareSource,
  firstTaskImage,
  getReadyTaskSnapshot,
  isTaskShareable,
  prepareTaskShareImage,
  prepareTaskShareImageForList,
  taskShareFingerprint,
  taskSharePath,
  taskShareRevision
};
