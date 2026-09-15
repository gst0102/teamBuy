from __future__ import annotations

import hashlib
import json
import threading
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.models.domain import (
    ContentModerationAssessment,
    ContentModerationAuditLog,
    ContentSafetyRule,
)
from app.services.repository import AppRepository
from app.services.text_safety import strip_unicode_surrogates
from app.services.time_utils import parse_iso
from app.services.helpers import new_id


ACTION_PRIORITY = {"allow": 0, "warn": 1, "review": 2, "block": 3}
RULE_ACTIONS = set(ACTION_PRIORITY) - {"allow"}
RULE_MATCH_TYPES = {"contains", "exact"}
RULE_SEVERITIES = {"high", "medium", "low"}
_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}


def normalize_for_match(value: Any) -> str:
    """Return a detection-only form without mutating the stored user text."""
    text = strip_unicode_surrogates(str(value or ""))
    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text if char not in _ZERO_WIDTH)
    return text.casefold().strip()


def compact_for_match(value: Any) -> str:
    text = normalize_for_match(value)
    return "".join(
        char for char in text
        if not char.isspace() and unicodedata.category(char)[0] not in {"P", "S", "C"}
    )


def _iter_text_fields(value: Any, path: str):
    if isinstance(value, str):
        yield path, value
        return
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from _iter_text_fields(child, child_path)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_text_fields(child, f"{path}[{index}]")


def _scope_matches(scopes: list[str], content_type: str, field_path: str) -> bool:
    if not scopes:
        return True
    for scope in scopes:
        clean = str(scope or "").strip()
        if not clean:
            continue
        qualified_path = f"{content_type}.{field_path}" if field_path else content_type
        if clean in {content_type, field_path, qualified_path}:
            return True
        if (
            field_path.startswith(f"{clean}.")
            or field_path.startswith(f"{clean}[")
            or qualified_path.startswith(f"{clean}.")
            or qualified_path.startswith(f"{clean}[")
        ):
            return True
    return False


def _is_rule_active(rule: ContentSafetyRule, now: datetime) -> bool:
    if not rule.enabled:
        return False
    if not rule.expiresAt:
        return True
    try:
        expiry = parse_iso(rule.expiresAt)
    except (TypeError, ValueError):
        # A malformed imported rule must fail closed for that rule, not take
        # down every content write in the application.
        return False
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return bool(expiry > now)


@dataclass(frozen=True)
class ContentSafetyResult:
    contentType: str
    contentRevision: str
    contentFingerprint: str
    ruleVersion: str
    decision: str
    status: str
    matches: tuple[dict, ...] = ()
    assessmentId: str | None = None

    def public_payload(self) -> dict:
        return {
            "code": {
                "block": "CONTENT_BLOCKED",
                "review": "CONTENT_REVIEWING",
                "warn": "CONTENT_WARNING",
                "allow": "CONTENT_ALLOWED",
            }.get(self.decision, "CONTENT_REVIEWING"),
            "decision": self.decision,
            "status": self.status,
            "ruleVersion": self.ruleVersion,
            "contentRevision": self.contentRevision,
            "assessmentId": self.assessmentId,
            "matchCount": len(self.matches),
            "fields": sorted({str(item.get("fieldPath") or "") for item in self.matches if item.get("fieldPath")}),
            "categories": sorted({str(item.get("category") or "") for item in self.matches if item.get("category")}),
        }


class ContentSafetyService:
    """Server-owned deterministic text policy and moderation record service."""

    def __init__(self, repo: AppRepository, cache_ttl_seconds: float = 10.0):
        self.repo = repo
        self.cache_ttl_seconds = max(float(cache_ttl_seconds), 0.0)
        self._cache_lock = threading.RLock()
        self._cached_at = 0.0
        self._cached_rules: list[ContentSafetyRule] = []
        self._cached_rule_version = self._calculate_rule_version([])

    def invalidate_cache(self) -> None:
        with self._cache_lock:
            self._cached_at = 0.0

    @staticmethod
    def _normalize_expiry(value: Any) -> str | None:
        clean = str(value or "").strip()
        if not clean:
            return None
        try:
            parsed = parse_iso(clean)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="规则有效期必须是有效日期时间") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()

    def _load_rules(self) -> tuple[list[ContentSafetyRule], str]:
        now_monotonic = __import__("time").monotonic()
        with self._cache_lock:
            if now_monotonic - self._cached_at <= self.cache_ttl_seconds:
                return list(self._cached_rules), self._cached_rule_version
            rules = self.repo.list_content_safety_rules(enabled_only=False)
            version = self._calculate_rule_version(rules)
            self._cached_rules = list(rules)
            self._cached_rule_version = version
            self._cached_at = now_monotonic
            return list(rules), version

    @staticmethod
    def _calculate_rule_version(rules: list[ContentSafetyRule]) -> str:
        payload = [
            {
                "id": rule.id,
                "termHash": rule.termHash,
                "matchType": rule.matchType,
                "category": rule.category,
                "severity": rule.severity,
                "action": rule.action,
                "scopes": sorted(rule.scopes),
                "enabled": rule.enabled,
                "version": rule.version,
                "expiresAt": rule.expiresAt,
            }
            for rule in sorted(rules, key=lambda item: item.id)
        ]
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _fingerprint(fields: dict) -> str:
        payload = json.dumps(strip_unicode_surrogates(fields), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def scan(
        self,
        content_type: str,
        fields: dict,
        content_revision: str = "",
    ) -> ContentSafetyResult:
        clean_type = str(content_type or "unknown").strip() or "unknown"
        clean_revision = str(content_revision or "")[:160]
        fingerprint = self._fingerprint(fields if isinstance(fields, dict) else {})
        rules, rule_version = self._load_rules()
        now = datetime.now(timezone.utc)
        active_rules = [rule for rule in rules if _is_rule_active(rule, now)]
        matches: list[dict] = []
        for field_path, raw_text in _iter_text_fields(fields if isinstance(fields, dict) else {}, ""):
            compact_text = compact_for_match(raw_text)
            if not compact_text:
                continue
            for rule in active_rules:
                if not _scope_matches(rule.scopes, clean_type, field_path):
                    continue
                compact_term = compact_for_match(rule.normalizedTerm or rule.term)
                if not compact_term:
                    continue
                matched = compact_text == compact_term if rule.matchType == "exact" else compact_term in compact_text
                if not matched:
                    continue
                matches.append({
                    "ruleId": rule.id,
                    "fieldPath": field_path,
                    "category": rule.category,
                    "severity": rule.severity,
                    "action": rule.action,
                    "count": 1,
                })
        decision = "allow"
        if matches:
            decision = max((str(item["action"]) for item in matches), key=lambda item: ACTION_PRIORITY.get(item, 0))
        status = {"allow": "allowed", "warn": "allowed", "review": "reviewing", "block": "blocked"}[decision]
        return ContentSafetyResult(
            contentType=clean_type,
            contentRevision=clean_revision,
            contentFingerprint=fingerprint,
            ruleVersion=rule_version,
            decision=decision,
            status=status,
            matches=tuple(matches),
        )

    def assess(
        self,
        content_type: str,
        target_id: str,
        fields: dict,
        *,
        owner_user_id: str | None = None,
        content_revision: str = "",
        persist: bool = True,
    ) -> ContentSafetyResult:
        result = self.scan(content_type, fields, content_revision)
        existing = self.repo.get_latest_content_moderation_assessment(
            result.contentType,
            str(target_id or ""),
            result.contentRevision,
        ) if target_id else None
        if not existing and target_id:
            # A moderation approval is attached to the exact content
            # fingerprint and rule version.  This lets an operator approve a
            # draft and the owner retry the same publish action even when the
            # lifecycle timestamp changed, while a changed body still needs a
            # fresh assessment.
            candidates = self.repo.list_content_moderation_assessments(
                target_type=result.contentType,
                limit=200,
                offset=0,
            )
            existing = next(
                (
                    item
                    for item in candidates
                    if item.targetId == str(target_id)
                    and item.contentFingerprint == result.contentFingerprint
                    and item.ruleVersion == result.ruleVersion
                ),
                None,
            )
        if (
            existing
            and existing.contentFingerprint == result.contentFingerprint
            and existing.ruleVersion == result.ruleVersion
            and existing.status == "overridden"
        ):
            return ContentSafetyResult(
                contentType=result.contentType,
                contentRevision=result.contentRevision,
                contentFingerprint=result.contentFingerprint,
                ruleVersion=result.ruleVersion,
                decision="allow",
                status="overridden",
                matches=result.matches,
                assessmentId=existing.id,
            )
        if (
            existing
            and existing.contentFingerprint == result.contentFingerprint
            and existing.ruleVersion == result.ruleVersion
            and existing.status == result.status
            and existing.decision == result.decision
        ):
            return ContentSafetyResult(
                contentType=result.contentType,
                contentRevision=result.contentRevision,
                contentFingerprint=result.contentFingerprint,
                ruleVersion=result.ruleVersion,
                decision=result.decision,
                status=result.status,
                matches=result.matches,
                assessmentId=existing.id,
            )
        if not persist or not target_id:
            return result
        now = datetime.now(timezone.utc).isoformat()
        assessment = ContentModerationAssessment(
            id=new_id("content_assessment"),
            targetType=result.contentType,
            targetId=str(target_id),
            ownerUserId=str(owner_user_id or "").strip() or None,
            contentRevision=result.contentRevision,
            contentFingerprint=result.contentFingerprint,
            ruleVersion=result.ruleVersion,
            status=result.status,
            decision=result.decision,
            matchedRuleIds=list(dict.fromkeys(str(item["ruleId"]) for item in result.matches)),
            matchSummary=list(result.matches),
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_content_moderation_assessment(assessment)
        self.repo.save_content_moderation_audit_log(ContentModerationAuditLog(
            id=new_id("content_audit"),
            eventType="automatic_assessment",
            targetType=result.contentType,
            targetId=str(target_id),
            assessmentId=assessment.id,
            operatorName="system",
            details={"decision": result.decision, "ruleVersion": result.ruleVersion},
            createdAt=now,
        ))
        return ContentSafetyResult(
            contentType=result.contentType,
            contentRevision=result.contentRevision,
            contentFingerprint=result.contentFingerprint,
            ruleVersion=result.ruleVersion,
            decision=result.decision,
            status=result.status,
            matches=result.matches,
            assessmentId=assessment.id,
        )

    def assert_can_publish(self, result: ContentSafetyResult) -> ContentSafetyResult:
        if result.decision == "block":
            raise HTTPException(status_code=422, detail={
                **result.public_payload(),
                "message": "内容包含暂不能发布的内容，请修改后重试",
            })
        if result.decision == "review" and result.status != "overridden":
            raise HTTPException(status_code=409, detail={
                **result.public_payload(),
                "message": "内容已提交审核，审核通过后才能公开",
            })
        return result

    def create_rule(self, payload: dict, operator_name: str = "ops") -> ContentSafetyRule:
        term = strip_unicode_surrogates(str(payload.get("term") or "")).strip()
        normalized = normalize_for_match(term)
        compact_term = compact_for_match(normalized)
        if not compact_term:
            raise HTTPException(status_code=400, detail="违禁词不能为空")
        match_type = str(payload.get("matchType") or "contains").strip()
        action = str(payload.get("action") or "review").strip()
        severity = str(payload.get("severity") or "medium").strip()
        if match_type not in RULE_MATCH_TYPES:
            raise HTTPException(status_code=400, detail="匹配方式无效")
        if action not in RULE_ACTIONS:
            raise HTTPException(status_code=400, detail="处理动作无效")
        if severity not in RULE_SEVERITIES:
            raise HTTPException(status_code=400, detail="风险级别无效")
        scopes = [str(item).strip()[:120] for item in (payload.get("scopes") or []) if str(item).strip()][:30]
        term_hash = hashlib.sha256(compact_term.encode("utf-8")).hexdigest()
        for existing in self.repo.list_content_safety_rules(enabled_only=True):
            if existing.termHash == term_hash and existing.matchType == match_type and sorted(existing.scopes) == sorted(scopes):
                raise HTTPException(status_code=409, detail="相同作用域下已存在相同规则")
        now = datetime.now(timezone.utc).isoformat()
        rule = ContentSafetyRule(
            id=new_id("content_rule"),
            term=term[:200],
            normalizedTerm=normalized[:200],
            termHash=term_hash,
            matchType=match_type,
            category=str(payload.get("category") or "platform_custom").strip()[:80] or "platform_custom",
            severity=severity,
            action=action,
            scopes=scopes,
            enabled=bool(payload.get("enabled", True)),
            version=1,
            source=str(payload.get("source") or "manual") if str(payload.get("source") or "manual") in {"manual", "import", "provider"} else "manual",
            expiresAt=self._normalize_expiry(payload.get("expiresAt")),
            operatorName=str(operator_name or "ops").strip()[:120] or "ops",
            reason=str(payload.get("reason") or "").strip()[:240],
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_content_safety_rule(rule)
        self.repo.save_content_moderation_audit_log(ContentModerationAuditLog(
            id=new_id("content_audit"),
            eventType="rule_created",
            ruleId=rule.id,
            operatorName=rule.operatorName,
            details={"category": rule.category, "action": rule.action, "severity": rule.severity},
            createdAt=now,
        ))
        self.invalidate_cache()
        return rule

    def update_rule(self, rule_id: str, payload: dict, operator_name: str = "ops") -> ContentSafetyRule:
        current = self.repo.get_content_safety_rule(rule_id)
        if not current:
            raise HTTPException(status_code=404, detail="规则不存在")
        values = current.model_dump()
        for key in ("term", "matchType", "category", "severity", "action", "scopes", "enabled", "expiresAt", "reason"):
            if key in payload and payload[key] is not None:
                values[key] = payload[key]
        term = strip_unicode_surrogates(str(values.get("term") or "")).strip()
        normalized = normalize_for_match(term)
        compact_term = compact_for_match(normalized)
        if not compact_term:
            raise HTTPException(status_code=400, detail="违禁词不能为空")
        if values.get("matchType") not in RULE_MATCH_TYPES or values.get("action") not in RULE_ACTIONS or values.get("severity") not in RULE_SEVERITIES:
            raise HTTPException(status_code=400, detail="规则参数无效")
        now = datetime.now(timezone.utc).isoformat()
        values["expiresAt"] = self._normalize_expiry(values.get("expiresAt"))
        values.update({
            "term": term[:200],
            "normalizedTerm": normalized[:200],
            "termHash": hashlib.sha256(compact_term.encode("utf-8")).hexdigest(),
            "scopes": [str(item).strip()[:120] for item in (values.get("scopes") or []) if str(item).strip()][:30],
            "version": int(current.version or 0) + 1,
            "operatorName": str(operator_name or "ops").strip()[:120] or "ops",
            "updatedAt": now,
        })
        updated = ContentSafetyRule.model_validate(values)
        self.repo.save_content_safety_rule(updated)
        self.repo.save_content_moderation_audit_log(ContentModerationAuditLog(
            id=new_id("content_audit"),
            eventType="rule_updated",
            ruleId=updated.id,
            operatorName=updated.operatorName,
            details={"version": updated.version, "enabled": updated.enabled},
            createdAt=now,
        ))
        self.invalidate_cache()
        return updated

    def review_assessment(self, assessment_id: str, action: str, operator_name: str, note: str = "") -> ContentModerationAssessment:
        assessment = self.repo.get_content_moderation_assessment(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="审核记录不存在")
        clean_action = str(action or "").strip()
        if clean_action not in {"approve", "reject"}:
            raise HTTPException(status_code=400, detail="审核动作无效")
        now = datetime.now(timezone.utc).isoformat()
        updated = assessment.model_copy(update={
            "status": "overridden" if clean_action == "approve" else "blocked",
            "decision": "allow" if clean_action == "approve" else "block",
            "reviewedBy": str(operator_name or "ops").strip()[:120] or "ops",
            "reviewedAt": now,
            "reviewNote": str(note or "").strip()[:240] or None,
            "updatedAt": now,
        })
        self.repo.save_content_moderation_assessment(updated)
        self.repo.save_content_moderation_audit_log(ContentModerationAuditLog(
            id=new_id("content_audit"),
            eventType=f"manual_{clean_action}",
            targetType=updated.targetType,
            targetId=updated.targetId,
            assessmentId=updated.id,
            operatorName=updated.reviewedBy or "ops",
            details={"reviewNote": updated.reviewNote or ""},
            createdAt=now,
        ))
        return updated
