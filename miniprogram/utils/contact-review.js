const PHONE_PATTERN = /1[3-9]\d{9}/g;

function asText(value) {
  return String(value == null ? "" : value);
}

function extractPhoneCandidates(values = []) {
  const source = Array.isArray(values) ? values : [values];
  const seen = new Set();
  const result = [];
  source.forEach((value) => {
    const text = asText(value);
    PHONE_PATTERN.lastIndex = 0;
    let match;
    while ((match = PHONE_PATTERN.exec(text))) {
      const phone = match[0];
      const before = text[match.index - 1] || "";
      const after = text[match.index + phone.length] || "";
      if (/\d/.test(before) || /\d/.test(after) || seen.has(phone)) continue;
      seen.add(phone);
      result.push(phone);
    }
  });
  return result;
}

function maskPhone(phone) {
  const value = asText(phone).trim();
  return value.length === 11 ? `${value.slice(0, 3)}****${value.slice(-4)}` : "手机号";
}

function normalizePhoneList(value) {
  return extractPhoneCandidates(Array.isArray(value) ? value : [value]);
}

function removePhoneFromText(value, phone) {
  const target = asText(phone).trim();
  if (!target) return asText(value);
  return asText(value)
    .split(/\r?\n/)
    .map((line) => line.split(target).join(""))
    .map((line) => line.replace(/(?:手机号|联系电话|电话|联系方式)\s*[：:、,，-]?\s*$/u, "").trim())
    .filter(Boolean)
    .join("\n");
}

function removePhoneFromFields(fields = {}, phone) {
  const next = { ...fields };
  Object.keys(next).forEach((key) => {
    if (typeof next[key] === "string") next[key] = removePhoneFromText(next[key], phone);
  });
  return next;
}

function buildContactCandidates(values = [], options = {}) {
  const publicPhone = asText(options.publicPhone).trim();
  const privatePhones = new Set(normalizePhoneList(options.privatePhones || []));
  const previous = new Map((Array.isArray(options.previous) ? options.previous : []).map((item) => [item.phone, item.status]));
  return extractPhoneCandidates(values).map((phone) => {
    const status = previous.get(phone)
      || (phone === publicPhone ? "public" : privatePhones.has(phone) ? "private" : "pending");
    return {
      phone,
      masked: maskPhone(phone),
      status,
      statusLabel: status === "public" ? "公开电话" : status === "private" ? "仅自己可见" : "待处理"
    };
  });
}

function unresolvedContactCandidates(candidates = []) {
  return (Array.isArray(candidates) ? candidates : []).filter((item) => item && item.status === "pending");
}

module.exports = {
  buildContactCandidates,
  extractPhoneCandidates,
  maskPhone,
  normalizePhoneList,
  removePhoneFromFields,
  removePhoneFromText,
  unresolvedContactCandidates
};
