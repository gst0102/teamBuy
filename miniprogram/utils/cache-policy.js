// Keep client cache lifetimes and resource limits in one place. These values
// are performance hints only; the server remains the source of truth.
const MINUTE_MS = 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

module.exports = Object.freeze({
  // Lists are metadata snapshots: keep them fast on return, but revalidate
  // quickly so edits made on another page become visible promptly.
  noteListTtlMs: MINUTE_MS,
  // A stale metadata snapshot may still be painted while the page revalidates
  // in the background.  This is deliberately longer than the fresh TTL and
  // never applies to customer identity/contact data.
  noteListStaleTtlMs: 2 * 60 * MINUTE_MS,
  showcaseListTtlMs: MINUTE_MS,
  topicTtlMs: MINUTE_MS,
  categoryTtlMs: 10 * MINUTE_MS,
  resourceListTtlMs: MINUTE_MS,
  // A stale resource list can paint while the page revalidates, but it must
  // never be effectively permanent after an app restart.
  resourceListStaleTtlMs: 5 * MINUTE_MS,
  categoryStaleTtlMs: 30 * MINUTE_MS,
  profileSummaryTtlMs: MINUTE_MS,
  profileSummaryStaleTtlMs: 2 * 60 * MINUTE_MS,
  // Radar mutations invalidate this memory snapshot immediately; a short TTL
  // also prevents a cold return from showing an old customer state.
  customerIntelligenceTtlMs: 2 * MINUTE_MS,
  // Customer identity/contact data is intentionally short-lived and memory
  // only. This cache is for radar -> detail and hot return paths, not for
  // persistence across app restarts.
  customerDetailTtlMs: 2 * MINUTE_MS,
  membershipTtlMs: 5 * MINUTE_MS,
  notificationConfigTtlMs: 5 * MINUTE_MS,
  customerIntelligenceMaxEntries: 32,
  customerDetailMaxEntries: 24,
  radarPageTtlMs: 10 * MINUTE_MS,
  mediaTtlMs: 7 * DAY_MS,
  mediaMaxEntries: 80,
  mediaMaxBytes: 32 * 1024 * 1024,
  mediaMaxImagesPerCard: 3
});
