function moneyYuan(fen) {
  return (Number(fen || 0) / 100).toFixed(2);
}

function pad2(value) {
  return String(value).padStart(2, "0");
}

function formatChineseDateTime(value) {
  if (!value) return "";
  const raw = String(value);
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return `${date.getFullYear()}年${pad2(date.getMonth() + 1)}月${pad2(date.getDate())}日 ${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function withdrawalStatusLabel(status) {
  return {
    pending: "审核中",
    approved: "已审核",
    waiting_user_confirm: "待确认收款",
    processing: "转账处理中",
    paid: "已到账",
    failed: "转账失败",
    cancelled: "已撤销",
    rejected: "已拒绝"
  }[status] || "处理中";
}

function rewardStatusLabel(status) {
  return {
    pending: "待生效",
    available: "可提现",
    reserved: "提现处理中",
    withdrawn: "已提现",
    revoked: "已撤销"
  }[status] || "处理中";
}

function relationStatusLabel(status) {
  return {
    paid: "已开通会员",
    pending: "奖励待生效",
    revoked: "奖励已撤销",
    bound: "已建立关系"
  }[status] || "已建立关系";
}

function positiveNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : 0;
}

function normalizeCenter(center, selectedAmountFen = 0) {
  const value = center || {};
  const rules = value.withdrawalRules || {};
  const totals = value.totals || {};
  const minimumFen = positiveNumber(rules.minimumWithdrawalFen) || positiveNumber(value.minimumWithdrawalFen);
  const dailyLimit = positiveNumber(rules.dailyWithdrawalLimit) || positiveNumber(value.dailyWithdrawalLimit);
  const feeNumber = Number(value.feeFen);
  const feeFen = Number.isFinite(feeNumber) && feeNumber >= 0 ? feeNumber : null;
  const withdrawalWindowText = rules.withdrawalWindowText || value.withdrawalWindowText || "";
  const feeText = rules.feeText || value.feeText || "";
  const availableNumber = Number(totals.available);
  const balanceReady = Number.isFinite(availableNumber) && availableNumber >= 0;
  const availableFen = balanceReady ? availableNumber : 0;
  const rulesReady = minimumFen > 0 && dailyLimit > 0 && feeFen !== null && Boolean(withdrawalWindowText);
  const withdrawalShortfallFen = rulesReady && balanceReady ? Math.max(0, minimumFen - availableFen) : 0;
  const canWithdraw = rulesReady && balanceReady && availableFen >= minimumFen;
  const rewardRatio = Number(value.rewardRatio);
  const rewardRatioPercent = Number.isFinite(rewardRatio) && rewardRatio >= 0 ? Math.round(rewardRatio * 100) : "—";
  const withdrawalOptionAmounts = Array.from(
    new Set([minimumFen, 1000, 5000, 20000].filter((amountFen) => amountFen > 0))
  ).sort((a, b) => a - b);
  const withdrawalOptions = withdrawalOptionAmounts.map((amountFen) => ({
    amountFen,
    amountYuan: moneyYuan(amountFen),
    selectable: canWithdraw && amountFen >= minimumFen && availableFen >= amountFen,
    selected: amountFen === selectedAmountFen && canWithdraw && amountFen >= minimumFen && availableFen >= amountFen
  }));
  const rewards = (value.rewards || []).map((item) => ({
    ...item,
    amountYuan: moneyYuan(item.amountFen),
    createdAtText: formatChineseDateTime(item.createdAt),
    updatedAtText: formatChineseDateTime(item.updatedAt),
    statusLabel: rewardStatusLabel(item.status)
  }));
  const directReferrals = (value.directReferrals || []).map((item) => ({
    ...item,
    createdAtText: formatChineseDateTime(item.createdAt),
    relationStatusLabel: relationStatusLabel(item.relationStatus),
    rewardAmountYuan: moneyYuan(item.rewardAmountFen),
    rewardStatusLabel: item.rewardStatus ? rewardStatusLabel(item.rewardStatus) : "暂未产生收益",
    rewardText: item.rewardAmountFen
      ? `奖励 ¥${moneyYuan(item.rewardAmountFen)} · ${item.rewardStatus ? rewardStatusLabel(item.rewardStatus) : "暂未产生收益"}`
      : "暂未产生收益"
  }));
  const nicknameByInviteeId = {};
  directReferrals.forEach((item) => {
    if (item.inviteeUserId) nicknameByInviteeId[item.inviteeUserId] = item.nickname;
  });
  const enrichedRewards = rewards.map((item) => ({
    ...item,
    inviteeNickname: item.inviteeNickname || nicknameByInviteeId[item.inviteeUserId] || "直接推广好友"
  }));
  const rewardTotalFen = enrichedRewards.reduce(
    (sum, item) => sum + (item.status === "revoked" ? 0 : Math.max(0, Number(item.amountFen || 0))),
    0
  );
  const unpaidInviteeCount = directReferrals.filter((item) => item.relationStatus === "bound").length;
  return {
    ...value,
    rulesReady,
    balanceReady,
    canWithdraw,
    minimumWithdrawalFen: minimumFen,
    minimumWithdrawalYuan: minimumFen ? moneyYuan(minimumFen) : "—",
    dailyWithdrawalLimit: dailyLimit || "—",
    feeYuan: feeFen === null ? "—" : moneyYuan(feeFen),
    feeText: feeText || (feeFen === null ? "" : `当前提现手续费为 ${moneyYuan(feeFen)} 元`),
    withdrawalWindowText: withdrawalWindowText || "—",
    withdrawalShortfallYuan: moneyYuan(withdrawalShortfallFen),
    rewardRatioPercent,
    rewardTotalFen,
    rewardTotalYuan: moneyYuan(rewardTotalFen),
    unpaidInviteeCount,
    rulesSummary: rulesReady
      ? `${rules.reviewTimeText || "提交后进入平台审核"}；${rules.arrivalTimeText || "到账以微信实际处理结果为准"}。`
      : "提现规则暂不可用，请重新加载后再试。",
    totals: {
      ...totals,
      availableYuan: balanceReady ? moneyYuan(availableFen) : "—",
      withdrawnYuan: moneyYuan(totals.withdrawn),
      reservedYuan: moneyYuan(totals.reserved)
    },
    withdrawalOptions,
    withdrawalRules: {
      ...rules,
      minimumWithdrawalFen: minimumFen,
      minimumWithdrawalYuan: minimumFen ? moneyYuan(minimumFen) : "—",
      dailyWithdrawalLimit: dailyLimit || "—",
      withdrawalWindowText,
      feeText
    },
    rewards: enrichedRewards,
    recentRewards: enrichedRewards.slice(0, 3),
    directReferrals,
    withdrawals: (value.withdrawals || []).map((item) => ({
      ...item,
      amountYuan: moneyYuan(item.amountFen),
      createdAtText: formatChineseDateTime(item.createdAt),
      paidAtText: formatChineseDateTime(item.paidAt),
      displayStatus: item.paidAt || item.transferState === "SUCCESS" ? "paid" : item.status,
      statusLabel: withdrawalStatusLabel(item.paidAt || item.transferState === "SUCCESS" ? "paid" : item.status),
      canConfirm: item.status === "waiting_user_confirm" && Boolean(item.packageInfo)
    }))
  };
}

module.exports = {
  formatChineseDateTime,
  moneyYuan,
  normalizeCenter,
  rewardStatusLabel,
  withdrawalStatusLabel
};
