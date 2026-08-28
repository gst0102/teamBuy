function getCustomerPaymentState(membership = {}) {
  if (!membership || typeof membership !== "object") return "unknown";
  if (typeof membership.paymentRequired !== "boolean") return "unknown";
  if (membership.paymentRequired === false) return "allowed";
  if (typeof membership.active !== "boolean") return "unknown";
  return membership.active === true ? "allowed" : "payment_required";
}

function getCustomerAccessState(membership = {}) {
  if (!membership || typeof membership !== "object") return "unknown";
  if (membership.featureEnabled === false) return "disabled";
  return getCustomerPaymentState(membership);
}

module.exports = {
  getCustomerPaymentState,
  getCustomerAccessState
};
