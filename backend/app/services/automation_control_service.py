from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re

from app.core.config import settings
from app.models.domain import (
    AutomationBatchContent,
    AutomationCardAsset,
    AutomationDevice,
    AutomationGroupCandidate,
    AutomationGroupContentPlan,
    AutomationTask,
    LiveQrCode,
    UserNote,
)
from app.services.helpers import new_id
from app.services.repository import AppRepository
from app.services.time_utils import SHANGHAI, now_iso, parse_iso


class AutomationControlError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class AutomationControlService:
    """PC control-plane state for one serialized Android/HID executor.

    The service intentionally stores execution facts, not screenshots or raw
    UI dumps.  AScript remains responsible for sensing and acting on the
    phone; this layer only leases work and records bounded results.
    """

    def __init__(self, repo: AppRepository):
        self.repo = repo

    def heartbeat(
        self,
        *,
        device_id: str,
        name: str,
        hid_device_id: str | None,
        status: str,
        active_wechat_account_id: str | None,
        capabilities: list[str],
        metadata: dict,
    ) -> AutomationDevice:
        now = now_iso()
        existing = self.repo.get_automation_device(device_id)
        merged_metadata = dict(existing.metadata if existing else {})
        merged_metadata.update(metadata or {})
        nickname = str((metadata or {}).get("nickname") or "").strip()
        if active_wechat_account_id and nickname:
            account_records = list(merged_metadata.get("wechatAccounts") or [])
            account_records = [
                item for item in account_records
                if isinstance(item, dict)
                and str(item.get("accountId") or "") != active_wechat_account_id
            ]
            account_records.append({"accountId": active_wechat_account_id, "nickname": nickname})
            merged_metadata["wechatAccounts"] = account_records[-8:]
        device = AutomationDevice(
            id=device_id,
            name=name,
            hidDeviceId=hid_device_id,
            status=status,
            activeWechatAccountId=active_wechat_account_id,
            capabilities=capabilities,
            metadata=merged_metadata,
            lastHeartbeatAt=now,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_automation_device(device)
        return device

    def list_devices(self, device_id: str | None, limit: int) -> list[AutomationDevice]:
        if device_id:
            device = self.repo.get_automation_device(device_id)
            return [device] if device else []
        return self.repo.list_automation_devices(limit)

    def get_native_group_scan_config(self, device_id: str) -> dict:
        """Return a bounded scan scope; legacy devices retain the g10 default."""
        device = self.repo.get_automation_device(str(device_id or "").strip())
        if not device:
            raise AutomationControlError(404, "automation device is not registered")
        stored = (device.metadata or {}).get("nativeGroupScanConfig") or {}
        return {
            "deviceId": device.id,
            "searchPrefixes": list(stored.get("searchPrefixes") or ["g10"]),
            "scanOnly": bool(stored.get("scanOnly", False)),
        }

    def update_native_group_scan_config(
        self,
        *,
        device_id: str,
        search_prefixes: list[str],
        scan_only: bool,
    ) -> dict:
        """Save PC-selected g/c code prefixes without touching device state."""
        device = self.repo.get_automation_device(str(device_id or "").strip())
        if not device:
            raise AutomationControlError(404, "automation device is not registered")
        normalized = []
        for value in search_prefixes or []:
            prefix = "".join(str(value or "").split()).lower()
            if not re.fullmatch(r"[gc]\d{1,8}", prefix):
                raise AutomationControlError(
                    422,
                    "扫描前缀仅允许 g/c 开头的群编号，例如 g10、c1001",
                )
            if prefix not in normalized:
                normalized.append(prefix)
        if not normalized:
            raise AutomationControlError(422, "至少配置一个群编号扫描前缀")
        if len(normalized) > 12:
            raise AutomationControlError(422, "一次最多配置 12 个群编号扫描前缀")
        now = now_iso()
        config = {
            "searchPrefixes": normalized,
            "scanOnly": bool(scan_only),
            "updatedAt": now,
        }
        metadata = dict(device.metadata or {})
        metadata["nativeGroupScanConfig"] = config
        self.repo.save_automation_device(
            device.model_copy(update={"metadata": metadata, "updatedAt": now})
        )
        return {"deviceId": device.id, **config}

    def create_task(
        self,
        *,
        function_id: str,
        device_id: str,
        target_wechat_account_id: str | None,
        payload: dict,
        idempotency_key: str | None,
    ) -> AutomationTask:
        if not self.repo.get_automation_device(device_id):
            raise AutomationControlError(404, "automation device is not registered")
        key = str(idempotency_key or "").strip() or None
        if key:
            existing = self.repo.find_automation_task_by_idempotency_key(key)
            if existing:
                if (
                    existing.functionId != function_id
                    or existing.deviceId != device_id
                    or existing.targetWechatAccountId != target_wechat_account_id
                ):
                    raise AutomationControlError(409, "idempotency key belongs to another automation task")
                return existing
        now = now_iso()
        task = AutomationTask(
            id=new_id("automation_task"),
            functionId=function_id,
            deviceId=device_id,
            targetWechatAccountId=target_wechat_account_id,
            payload=payload,
            idempotencyKey=key,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_automation_task(task)
        return task

    def claim_task(
        self,
        *,
        device_id: str,
        active_wechat_account_id: str | None,
        run_id: str | None = None,
        lease_seconds: int,
        function_ids: set[str] | None = None,
    ) -> AutomationTask | None:
        if not settings.live_qr_member_count_automation_enabled and function_ids is not None:
            function_ids = set(function_ids)
            function_ids.discard("wechat.scan_live_qr_member_count")
            if not function_ids:
                return None
        device = self.repo.get_automation_device(device_id)
        if not device:
            raise AutomationControlError(404, "automation device is not registered")
        now = now_iso()
        if device.lastHeartbeatAt:
            try:
                if parse_iso(now) - parse_iso(device.lastHeartbeatAt) > timedelta(minutes=5):
                    raise AutomationControlError(409, "automation device heartbeat is stale")
            except AutomationControlError:
                raise
            except Exception:
                raise AutomationControlError(409, "automation device heartbeat is invalid")
        lease_expires_at = (parse_iso(now) + timedelta(seconds=lease_seconds)).isoformat()
        task = self.repo.claim_next_automation_task(
            device_id=device_id,
            active_wechat_account_id=active_wechat_account_id,
            now=now,
            lease_expires_at=lease_expires_at,
            lease_token=new_id("lease"),
            run_id=run_id,
            function_ids=function_ids,
        )
        self._save_device_status(device, active_wechat_account_id, "busy" if task else "ready", now)
        return task

    def complete_task(
        self,
        *,
        task_id: str,
        device_id: str,
        lease_token: str,
        active_wechat_account_id: str | None,
        result: dict,
    ) -> AutomationTask:
        existing = self.repo.get_automation_task(task_id)
        if existing and existing.status == "success":
            if existing.deviceId != device_id or existing.leaseToken != lease_token:
                raise AutomationControlError(409, "automation task completion token is invalid")
            return existing
        if existing and existing.status == "failed":
            raise AutomationControlError(409, "failed automation task cannot be completed")
        task = self._owned_running_task(task_id, device_id, lease_token, active_wechat_account_id)
        now = now_iso()
        updated = task.model_copy(
            update={
                "status": "success",
                "result": result,
                "errorMessage": None,
                "leaseExpiresAt": None,
                "finishedAt": now,
                "updatedAt": now,
            }
        )
        self.repo.save_automation_task(updated)
        self._record_group_not_found(updated, result, "执行时未找到目标群")
        device = self.repo.get_automation_device(device_id)
        if device:
            self._save_device_status(device, active_wechat_account_id, "ready", now)
        return updated

    def fail_task(
        self,
        *,
        task_id: str,
        device_id: str,
        lease_token: str,
        active_wechat_account_id: str | None,
        error_message: str,
        result: dict,
    ) -> AutomationTask:
        existing = self.repo.get_automation_task(task_id)
        if existing and existing.status == "failed":
            if existing.deviceId != device_id or existing.leaseToken != lease_token:
                raise AutomationControlError(409, "automation task failure token is invalid")
            return existing
        if existing and existing.status == "success":
            raise AutomationControlError(409, "successful automation task cannot be failed")
        task = self._owned_running_task(task_id, device_id, lease_token, active_wechat_account_id)
        now = now_iso()
        updated = task.model_copy(
            update={
                "status": "failed",
                "result": result,
                "errorMessage": error_message,
                "leaseExpiresAt": None,
                "finishedAt": now,
                "updatedAt": now,
            }
        )
        self.repo.save_automation_task(updated)
        self._record_group_not_found(updated, result, error_message)
        device = self.repo.get_automation_device(device_id)
        if device:
            self._save_device_status(device, active_wechat_account_id, "ready", now)
        return updated

    def _record_group_not_found(
        self,
        task: AutomationTask,
        result: dict,
        error_message: str,
    ) -> None:
        """Persist an explicit live UI lookup miss for later runs."""
        if task.functionId != "wechat.send_group_batch" or not isinstance(result, dict):
            return
        payload = task.payload if isinstance(task.payload, dict) else {}
        target_results = result.get("targetResults")
        if isinstance(target_results, list):
            if not any(
                isinstance(item, dict) and item.get("groupNotFound") is True
                for item in target_results
            ):
                return
            for target_result in target_results:
                if not isinstance(target_result, dict) or target_result.get("groupNotFound") is not True:
                    continue
                self._record_missing_candidate(
                    task,
                    payload,
                    target_result,
                    error_message,
                )
            return
        if result.get("groupNotFound") is not True:
            return
        self._record_missing_candidate(task, payload, result, error_message)

    def _record_missing_candidate(
        self,
        task: AutomationTask,
        payload: dict,
        result: dict,
        error_message: str,
    ) -> None:
        candidate_ids = result.get("candidateIds") or payload.get("candidateIds") or []
        if not isinstance(candidate_ids, list):
            candidate_ids = []
        candidate_ids = [
            str(value or "").strip()
            for value in candidate_ids
            if str(value or "").strip()
        ]
        representative_id = str(
            result.get("candidateId") or payload.get("candidateId") or ""
        ).strip()
        if representative_id:
            candidate_ids.append(representative_id)
        candidate_ids = list(dict.fromkeys(candidate_ids))
        if not candidate_ids:
            return
        expected_group_name = " ".join(str(
            result.get("groupName") or payload.get("groupName") or ""
        ).split())
        now = now_iso()
        for candidate_id in candidate_ids:
            candidate = self.repo.get_automation_group_candidate(candidate_id)
            if not candidate or candidate.deviceId != task.deviceId:
                continue
            if task.targetWechatAccountId and candidate.wechatAccountId != task.targetWechatAccountId:
                continue
            actual_group_name = " ".join(str(candidate.groupName or "").split())
            if expected_group_name and actual_group_name != expected_group_name:
                continue
            missing_reason = "执行时未找到群：{}".format(
                expected_group_name or actual_group_name or "未命名群"
            )
            self.repo.save_automation_group_candidate(candidate.model_copy(update={
                # Same-name rows are deliberately one PC routing bundle; when
                # that bundle is absent from live WeChat results, disable every
                # stored alias together and retain each row's audit history.
                "canSend": False,
                "membershipStatus": "removed",
                "lastVerifiedAt": now,
                "lastSeenAt": now,
                "lastError": "{}（{}）".format(missing_reason, error_message)[:2000],
                "updatedAt": now,
            }))

    def upsert_group_candidate(
        self,
        *,
        candidate_id: str | None,
        device_id: str,
        wechat_account_id: str,
        source: str,
        group_qr_code: str | None,
        group_name: str | None,
        wechat_account_name: str | None,
        saved_at: str | None,
        join_status: str,
        can_send: bool | None,
        remark: str | None,
        last_seen_at: str | None,
        idempotency_key: str | None,
        last_error: str | None,
        group_member_count: int | None = None,
        group_codes: list[str] | None = None,
        group_identity: str | None = None,
        group_occurrence_count: int | None = None,
    ) -> AutomationGroupCandidate:
        if not self.repo.get_automation_device(device_id):
            raise AutomationControlError(404, "automation device is not registered")
        device = self.repo.get_automation_device(device_id)
        if device and device.activeWechatAccountId and device.activeWechatAccountId != wechat_account_id:
            raise AutomationControlError(409, "group candidate account does not match the latest device heartbeat")
        source = str(source or "xiaohongshu").strip()
        if source not in {"xiaohongshu", "wechat_native"}:
            raise AutomationControlError(422, "unsupported group candidate source")
        normalized_name = " ".join(str(group_name or "").split())
        normalized_group_identity = str(group_identity or "").strip().lower() or None
        if normalized_group_identity and not re.fullmatch(r"[0-9a-f]{64}", normalized_group_identity):
            raise AutomationControlError(422, "groupIdentity 必须是成员名称的 SHA-256 摘要")
        if source == "wechat_native" and not normalized_name:
            raise AutomationControlError(422, "native WeChat group candidate requires a group name")
        if source == "xiaohongshu" and not str(group_qr_code or "").strip():
            raise AutomationControlError(422, "Xiaohongshu group candidate requires a group QR code")
        key = str(idempotency_key or "").strip()
        if not key:
            if source == "xiaohongshu":
                identity = str(group_qr_code or "")
            else:
                # Native WeChat candidates are routed by account + code + name;
                # same-name physical rows are represented by groupOccurrenceCount.
                code_identity = ",".join(
                    sorted({" ".join(str(value or "").split()).strip() for value in group_codes or [] if str(value or "").strip()})
                )
                identity = "{}:{}:{}".format(
                    normalized_group_identity or "",
                    code_identity,
                    normalized_name,
                )
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            key = f"group:{source}:{wechat_account_id}:{digest}"
        existing = self.repo.get_automation_group_candidate(candidate_id) if candidate_id else None
        existing = existing or self.repo.find_automation_group_candidate_by_idempotency_key(key)
        if existing and (existing.deviceId != device_id or existing.wechatAccountId != wechat_account_id):
            raise AutomationControlError(409, "group candidate belongs to another device or account")
        now = now_iso()
        merged_group_codes = []
        for value in list(existing.groupCodes if existing else []) + list(group_codes or []):
            code = " ".join(str(value or "").split()).strip()
            if code and code not in merged_group_codes:
                merged_group_codes.append(code)
        candidate = AutomationGroupCandidate(
            id=existing.id if existing else (candidate_id or new_id("group_candidate")),
            deviceId=device_id,
            wechatAccountId=wechat_account_id,
            source=source,
            groupQRCode=group_qr_code or (existing.groupQRCode if existing else None),
            groupName=normalized_name or (existing.groupName if existing else None),
            groupIdentity=normalized_group_identity or (existing.groupIdentity if existing else None),
            groupOccurrenceCount=(
                group_occurrence_count
                if group_occurrence_count is not None
                else (existing.groupOccurrenceCount if existing else None)
            ),
            wechatAccountName=(
                " ".join(str(wechat_account_name or "").split())
                or (existing.wechatAccountName if existing else None)
            ),
            savedAt=saved_at or (existing.savedAt if existing else now),
            joinStatus=join_status,
            canSend=can_send if can_send is not None else (existing.canSend if existing else None),
            remark=remark if remark is not None else (existing.remark if existing else None),
            groupCodes=merged_group_codes,
            topic=existing.topic if existing else None,
            region=existing.region if existing else None,
            allowedContentTypes=list(existing.allowedContentTypes) if existing else [],
            batchContents=list(existing.batchContents) if existing else [],
            dailySendLimit=existing.dailySendLimit if existing else 3,
            membershipStatus=existing.membershipStatus if existing else "unknown",
            lastActivityAt=existing.lastActivityAt if existing else None,
            lastVerifiedAt=existing.lastVerifiedAt if existing else None,
            lastSeenAt=last_seen_at or now,
            groupMemberCount=(
                group_member_count
                if group_member_count is not None
                else (existing.groupMemberCount if existing else None)
            ),
            groupMemberCountCheckedAt=(
                now
                if group_member_count is not None
                else (existing.groupMemberCountCheckedAt if existing else None)
            ),
            groupMemberCountSource=(
                "wechat_group_info"
                if group_member_count is not None
                else (existing.groupMemberCountSource if existing else None)
            ),
            idempotencyKey=key,
            lastError=last_error,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_automation_group_candidate(candidate)
        return candidate

    def account_name_for_candidate(self, candidate: AutomationGroupCandidate) -> str | None:
        if candidate.wechatAccountName:
            return candidate.wechatAccountName
        device = self.repo.get_automation_device(candidate.deviceId)
        metadata = device.metadata if device else {}
        for item in metadata.get("wechatAccounts") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("accountId") or "") == candidate.wechatAccountId:
                nickname = " ".join(str(item.get("nickname") or "").split())
                if nickname:
                    return nickname
        if device and device.activeWechatAccountId == candidate.wechatAccountId:
            nickname = " ".join(str(metadata.get("nickname") or "").split())
            return nickname or None
        return None

    def list_group_candidates(self, wechat_account_id: str | None, limit: int) -> list[AutomationGroupCandidate]:
        return self.repo.list_automation_group_candidates(wechat_account_id, limit)

    def list_card_assets(self, limit: int = 200) -> list[AutomationCardAsset]:
        return self.repo.list_automation_card_assets(limit)

    def upsert_card_asset(
        self,
        *,
        card_id: str,
        deep_link: str | None,
        card_title: str | None,
        status: str,
    ) -> AutomationCardAsset:
        normalized_id = " ".join(str(card_id or "").split())
        if not normalized_id:
            raise AutomationControlError(422, "card id is required")
        normalized_status = str(status or "active").strip()
        if normalized_status not in {"active", "inactive", "expired"}:
            raise AutomationControlError(422, "unsupported card asset status")
        existing = self.repo.get_automation_card_asset(normalized_id)
        now = now_iso()
        asset = AutomationCardAsset(
            id=existing.id if existing else new_id("automation_card"),
            cardId=normalized_id,
            deepLink=str(deep_link or "").strip() or None,
            cardTitle=" ".join(str(card_title or "").split()) or None,
            status=normalized_status,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_automation_card_asset(asset)
        return asset

    def list_group_content_plans(self, limit: int = 200) -> list[AutomationGroupContentPlan]:
        return self.repo.list_automation_group_content_plans(limit)

    def upsert_group_content_plan(
        self,
        *,
        group_code: str,
        remark: str | None,
        batch_contents: list,
        status: str,
    ) -> AutomationGroupContentPlan:
        normalized_code = " ".join(str(group_code or "").split()).strip()
        if not normalized_code:
            raise AutomationControlError(422, "group code is required")
        if len(normalized_code) > 40:
            raise AutomationControlError(422, "群编号不能超过 40 个字符")
        normalized_status = str(status or "active").strip()
        if normalized_status not in {"active", "inactive"}:
            raise AutomationControlError(422, "unsupported group content plan status")
        existing = self.repo.get_automation_group_content_plan(normalized_code)
        now = now_iso()
        plan = AutomationGroupContentPlan(
            id=existing.id if existing else new_id("automation_group_plan"),
            groupCode=normalized_code,
            remark=" ".join(str(remark or "").split()).strip() or None,
            status=normalized_status,
            batchContents=self._normalize_batch_contents(batch_contents),
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_automation_group_content_plan(plan)
        return plan

    def create_group_batch_tasks(
        self,
        *,
        group_code: str,
        batch_no: int,
        device_id: str,
        wechat_account_id: str | None,
        max_targets: int,
    ) -> dict:
        """Expand one dynamic PC group-code batch into bounded device tasks.

        The group code is a database routing key, never a WeChat search term.
        Each task keeps the real candidate/group name and account so the phone
        executor can verify the live chat before any UI action.
        """
        normalized_code = " ".join(str(group_code or "").split()).strip()
        if not normalized_code:
            raise AutomationControlError(422, "group code is required")
        if not self.repo.get_automation_device(device_id):
            raise AutomationControlError(404, "automation device is not registered")
        plan = self.repo.get_automation_group_content_plan(normalized_code)
        if not plan:
            raise AutomationControlError(404, "group content plan not found")
        if plan.status != "active":
            raise AutomationControlError(409, "group content plan is inactive")
        batch = next((item for item in plan.batchContents if item.batchNo == batch_no), None)
        if not batch:
            raise AutomationControlError(404, "batch not found in group content plan")
        if not batch.enabled:
            raise AutomationControlError(409, "selected batch is disabled")
        if not batch.cardId and not batch.text:
            raise AutomationControlError(422, "selected batch has no card or text")

        # The batch stores the stable card id.  The phone still needs the
        # human-visible title to locate that existing card in the material
        # group, so copy the current catalog metadata into each leased task.
        card_asset = (
            self.repo.get_automation_card_asset(batch.cardId)
            if batch.cardId
            else None
        )

        candidates = [
            item
            for item in self.repo.list_automation_group_candidates(None, 10000)
            if item.deviceId == device_id
            and normalized_code in item.groupCodes
            and (not wechat_account_id or item.wechatAccountId == wechat_account_id)
        ]
        candidates.sort(key=lambda item: (str(item.groupName or ""), item.id))
        run_id = new_id("group_batch_run")
        tasks = []
        skipped = []
        # Routing by group code intentionally does not require a fresh
        # membership/activity/profile check.  The phone must search the saved
        # real group name and report a missing group at execution time; only
        # explicit operator blocks and previously confirmed removals are
        # skipped before a task is created.
        blocked_codes = {
            "not_allowed",
            "pending_review",
            "removed",
        }
        for candidate in candidates[:max_targets]:
            eligibility = self.group_send_eligibility(candidate)
            if eligibility["code"] in blocked_codes:
                skipped.append({
                    "candidateId": candidate.id,
                    "groupName": candidate.groupName,
                    "reason": eligibility["reason"],
                })
                continue
            payload = {
                "source": "group_content_plan",
                "groupCode": normalized_code,
                "batchNo": batch.batchNo,
                "candidateId": candidate.id,
                "candidateIds": [candidate.id],
                "groupName": candidate.groupName,
                "groupIdentity": candidate.groupIdentity,
                "groupOccurrenceCount": candidate.groupOccurrenceCount or 1,
                "targetWechatAccountId": candidate.wechatAccountId,
                "targetWechatAccountName": self.account_name_for_candidate(candidate),
                "cardId": batch.cardId,
                "cardTitle": card_asset.cardTitle if card_asset else None,
                "cardDeepLink": card_asset.deepLink if card_asset else None,
                "text": batch.text,
            }
            tasks.append(self.create_task(
                function_id="wechat.send_group_batch",
                device_id=device_id,
                target_wechat_account_id=candidate.wechatAccountId,
                payload=payload,
                idempotency_key=f"{run_id}:{candidate.id}:{batch.batchNo}",
            ))
        for candidate in candidates[max_targets:]:
            skipped.append({
                "candidateId": candidate.id,
                "groupName": candidate.groupName,
                "reason": "超过本次任务目标上限",
            })
        return {
            "runId": run_id,
            "groupCode": normalized_code,
            "batchNo": batch.batchNo,
            "candidateCount": len(candidates),
            "createdCount": len(tasks),
            "skippedCount": len(skipped),
            "tasks": tasks,
            "skipped": skipped,
        }

    def create_device_batch_tasks(
        self,
        *,
        device_id: str,
        batch_no: int,
        wechat_account_ids: list[str] | None,
        group_codes: list[str] | None,
        max_targets: int,
        run_id: str | None = None,
    ) -> dict:
        """Build the phone run as grouped, account-scoped forwarding tasks.

        A task contains one group-code batch and all eligible real groups for
        one WeChat account.  The phone executor splits ``targets`` into the
        native WeChat limit of nine recipients per forward operation.  This is
        deliberately separate from the older operator endpoint above, whose
        one-candidate tasks remain available for backwards compatibility.
        """
        normalized_device_id = " ".join(str(device_id or "").split()).strip()
        if not normalized_device_id:
            raise AutomationControlError(422, "device id is required")
        if not self.repo.get_automation_device(normalized_device_id):
            raise AutomationControlError(404, "automation device is not registered")
        requested_accounts = {
            " ".join(str(value or "").split()).strip()
            for value in (wechat_account_ids or [])
            if " ".join(str(value or "").split()).strip()
        }
        requested_codes = {
            " ".join(str(value or "").split()).strip()
            for value in (group_codes or [])
            if " ".join(str(value or "").split()).strip()
        }
        clean_run_id = " ".join(str(run_id or "").split()).strip() or new_id("group_batch_run")
        tasks = []
        skipped = []
        target_count = 0
        plans = self.repo.list_automation_group_content_plans(1000)
        candidates = [
            item
            for item in self.repo.list_automation_group_candidates(None, 10000)
            if item.deviceId == normalized_device_id
            and (not requested_accounts or item.wechatAccountId in requested_accounts)
        ]
        blocked_codes = {"not_allowed", "pending_review", "removed"}

        for plan in plans:
            if plan.status != "active":
                continue
            if requested_codes and plan.groupCode not in requested_codes:
                continue
            batch = next((item for item in plan.batchContents if item.batchNo == batch_no), None)
            if not batch or not batch.enabled:
                continue
            if not batch.cardId:
                skipped.append({
                    "groupCode": plan.groupCode,
                    "batchNo": batch_no,
                    "reason": "批次必须绑定小程序卡片",
                    "reasonCode": "batch_card_missing",
                })
                continue
            card_asset = self.repo.get_automation_card_asset(batch.cardId)
            if not card_asset or card_asset.status != "active" or not card_asset.cardTitle:
                skipped.append({
                    "groupCode": plan.groupCode,
                    "batchNo": batch_no,
                    "reason": "卡片目录中找不到启用且有标题的卡片",
                    "reasonCode": "card_asset_unavailable",
                })
                continue

            code_candidates = [
                item for item in candidates
                if plan.groupCode in item.groupCodes
            ]
            code_candidates.sort(key=lambda item: (str(item.wechatAccountId or ""), str(item.groupName or ""), item.id))
            eligible_by_account = {}
            accepted_count = 0
            candidates_by_route = {}
            for candidate in code_candidates:
                route_key = (
                    candidate.wechatAccountId,
                    self._normalize_group_name(candidate.groupName),
                )
                candidates_by_route.setdefault(route_key, []).append(candidate)

            # The approved low-granularity policy treats equal account/code/name
            # rows as one route bundle. A confirmed scan count is authoritative;
            # legacy rows without a count remain one physical recipient each.
            # If any legacy row in a bundle has no scan count, use at least the
            # number of stored rows so old duplicate candidates are not lost.
            for (account_id, group_name), route_candidates in sorted(candidates_by_route.items()):
                route_candidates.sort(key=lambda item: item.id)
                eligibilities = [
                    (candidate, self.group_send_eligibility(candidate))
                    for candidate in route_candidates
                ]
                blocked = [
                    (candidate, eligibility)
                    for candidate, eligibility in eligibilities
                    if eligibility["code"] in blocked_codes
                ]
                if blocked:
                    # There is no reliable UI identity for only one of two
                    # same-name rows, so an operator block/removal applies to
                    # the whole bundle rather than silently sending a subset.
                    primary_blocked = blocked[0][1]
                    for candidate in route_candidates:
                        skipped.append({
                            "groupCode": plan.groupCode,
                            "candidateId": candidate.id,
                            "groupName": candidate.groupName,
                            "wechatAccountId": candidate.wechatAccountId,
                            "reasonCode": primary_blocked["code"],
                            "reason": "同名群按一个目标包管理；{}".format(primary_blocked["reason"]),
                        })
                    continue

                known_counts = [
                    int(candidate.groupOccurrenceCount)
                    for candidate in route_candidates
                    if candidate.groupOccurrenceCount is not None
                ]
                occurrence_count = max(known_counts or [1])
                if len(known_counts) != len(route_candidates):
                    occurrence_count = max(occurrence_count, len(route_candidates))
                if accepted_count + occurrence_count > max_targets:
                    for candidate in route_candidates:
                        skipped.append({
                            "groupCode": plan.groupCode,
                            "candidateId": candidate.id,
                            "groupName": candidate.groupName,
                            "wechatAccountId": candidate.wechatAccountId,
                            "reasonCode": "target_limit",
                            "reason": "超过本次任务目标上限",
                        })
                    continue

                representative = route_candidates[0]
                candidate_ids = [candidate.id for candidate in route_candidates]
                eligible_by_account.setdefault(account_id, []).append({
                    "candidateId": representative.id,
                    "candidateIds": candidate_ids,
                    "groupCode": plan.groupCode,
                    "groupName": group_name,
                    "groupOccurrenceCount": occurrence_count,
                    "targetWechatAccountId": account_id,
                    "targetWechatAccountName": self.account_name_for_candidate(representative),
                })
                accepted_count += occurrence_count
            for account_id, target_rows in sorted(eligible_by_account.items()):
                target_count += sum(
                    int(target.get("groupOccurrenceCount") or 1)
                    for target in target_rows
                )
                payload = {
                    "source": "group_content_plan",
                    "runId": clean_run_id,
                    "groupCode": plan.groupCode,
                    "batchNo": batch.batchNo,
                    "targets": target_rows,
                    "cardId": batch.cardId,
                    "cardTitle": card_asset.cardTitle,
                    "cardDeepLink": card_asset.deepLink,
                    "text": batch.text,
                }
                tasks.append(self.create_task(
                    function_id="wechat.send_group_batch",
                    device_id=normalized_device_id,
                    target_wechat_account_id=account_id,
                    payload=payload,
                    idempotency_key="{}:{}:{}:{}".format(
                        clean_run_id, account_id, plan.groupCode, batch.batchNo
                    ),
                ))
        return {
            "runId": clean_run_id,
            "batchNo": batch_no,
            "createdCount": len(tasks),
            "targetCount": target_count,
            # 这里统计跳过记录数（含方案级失败），不是微信发送失败群数。
            "skippedCount": len(skipped),
            "skippedItems": skipped,
            "tasks": tasks,
        }

    @staticmethod
    def _normalize_group_name(value: str | None) -> str:
        return " ".join(str(value or "").split())

    def reconcile_native_group_scan(
        self,
        *,
        device_id: str,
        wechat_account_id: str,
        wechat_account_name: str | None,
        scan_id: str,
        scan_mode: str,
        coverage: str,
        contacts_scan_stop_reason: str,
        chat_list_scan_stop_reason: str,
        contacts_group_count: int,
        chat_list_group_count: int,
        group_names: list[str],
        delete_missing: bool,
        group_mappings: list[dict] | None = None,
    ) -> dict:
        """Reconcile one native-WeChat inventory for one account.

        The account id is part of the boundary: same-named groups in the
        second WeChat account are separate records. Xiaohongshu candidates are
        excluded from both the diff and the deletion set.
        """
        device = self.repo.get_automation_device(device_id)
        if not device:
            raise AutomationControlError(404, "automation device is not registered")
        if device.activeWechatAccountId and device.activeWechatAccountId != wechat_account_id:
            raise AutomationControlError(409, "group scan account does not match the latest device heartbeat")

        clean_scan_id = " ".join(str(scan_id or "").split())
        if not clean_scan_id:
            raise AutomationControlError(422, "group scan requires a scan id")
        clean_scan_mode = str(scan_mode or "full").strip()
        if clean_scan_mode not in {"full", "incremental", "targeted"}:
            raise AutomationControlError(422, "unsupported group scan mode")
        clean_coverage = str(coverage or "partial").strip()
        if clean_coverage not in {"partial", "complete"}:
            raise AutomationControlError(422, "unsupported group scan coverage")

        coverage_is_complete = (
            clean_scan_mode == "full"
            and
            clean_coverage == "complete"
            and str(contacts_scan_stop_reason or "") in {"reported_total", "stable"}
            and str(chat_list_scan_stop_reason or "") in {"bottom_stable", "empty_list"}
        )
        if clean_coverage == "complete" and not coverage_is_complete:
            raise AutomationControlError(409, "群扫描未达到完整覆盖，已拒绝清理；请重新运行扫描")

        incoming_by_key: dict[tuple[str, str], dict] = {}
        for mapping in group_mappings or []:
            if not isinstance(mapping, dict):
                continue
            name = self._normalize_group_name(mapping.get("groupName"))
            code = "".join(str(mapping.get("groupCode") or "").split()).lower()
            identity = str(mapping.get("groupIdentity") or "").strip().lower()
            try:
                occurrence_count = int(mapping.get("occurrenceCount") or 1)
            except (TypeError, ValueError):
                raise AutomationControlError(422, "occurrenceCount 必须是正整数")
            if not name:
                continue
            if code and not re.fullmatch(r"[gc]\d{1,8}", code):
                raise AutomationControlError(422, "原生微信群映射包含无效群编号：" + code)
            if identity and not re.fullmatch(r"[0-9a-f]{64}", identity):
                raise AutomationControlError(422, "groupIdentity 必须是成员名称的 SHA-256 摘要")
            if occurrence_count < 1 or occurrence_count > 10000:
                raise AutomationControlError(422, "occurrenceCount 必须在 1 到 10000 之间")
            # The phone has no stable identity for equal-name rows. Keep one
            # account/code/name route and carry observed multiplicity instead
            # of inventing separate candidate identities from row positions.
            key = (code, name)
            entry = incoming_by_key.get(key)
            if entry is None:
                entry = {
                    "groupName": name,
                    "groupIdentity": None,
                    "groupCodes": [],
                    "groupOccurrenceCount": occurrence_count,
                }
                incoming_by_key[key] = entry
            else:
                # Repeated raw mappings in one reconcile request each describe
                # one visible row; the AScript scanner already max-merges
                # overlapping prefix/page snapshots before sending this list.
                entry["groupOccurrenceCount"] += occurrence_count
            if code and code not in entry["groupCodes"]:
                entry["groupCodes"].append(code)

        mapped_names = {entry["groupName"] for entry in incoming_by_key.values()}
        for value in group_names or []:
            name = self._normalize_group_name(value)
            if name and name not in mapped_names:
                incoming_by_key.setdefault(
                    ("", name),
                    {
                        "groupName": name,
                        "groupIdentity": None,
                        "groupCodes": [],
                        "groupOccurrenceCount": 1,
                    },
                )
                mapped_names.add(name)
        incoming = list(incoming_by_key.values())
        if delete_missing and coverage_is_complete and not incoming:
            raise AutomationControlError(409, "完整群扫描结果为空，已拒绝清理")

        existing_candidates = [
            candidate
            for candidate in self.repo.list_automation_group_candidates(None, 10000)
            if candidate.source == "wechat_native"
            and candidate.wechatAccountId == wechat_account_id
        ]
        now = now_iso()
        created_count = 0
        updated_count = 0
        seen_candidate_ids = set()
        mapped_count = 0
        for entry in incoming:
            name = entry["groupName"]
            codes = entry["groupCodes"]
            matches = [
                candidate for candidate in existing_candidates
                if candidate.id not in seen_candidate_ids
                and self._normalize_group_name(candidate.groupName) == name
                and (
                    any(code in candidate.groupCodes for code in codes)
                    if codes
                    else not candidate.groupCodes
                )
            ]
            # Old fingerprint-based rows can coexist in the PC database. Keep
            # their IDs/history, but refresh them as aliases of the same coarse
            # route so the task builder can bundle them and avoid over-sending.
            targets_to_update = matches or [None]
            for existing in targets_to_update:
                candidate = self.upsert_group_candidate(
                    candidate_id=existing.id if existing else None,
                    device_id=device_id,
                    wechat_account_id=wechat_account_id,
                    source="wechat_native",
                    group_qr_code=None,
                    group_name=name,
                    group_identity=None,
                    wechat_account_name=wechat_account_name,
                    saved_at=now,
                    join_status="success",
                    # A native scan allows new groups by default, but keeps any
                    # prior operator decision, including an explicit block.
                    can_send=(
                        True
                        if existing is None or existing.canSend is None
                        else existing.canSend
                    ),
                    remark=None,
                    last_seen_at=now,
                    idempotency_key=None,
                    last_error=None,
                    group_codes=codes,
                    group_occurrence_count=entry["groupOccurrenceCount"],
                )
                seen_candidate_ids.add(candidate.id)
                if existing:
                    updated_count += 1
                else:
                    created_count += 1
            mapped_count += len(codes) * entry["groupOccurrenceCount"]

        missing = [
            candidate for candidate in existing_candidates
            if candidate.id not in seen_candidate_ids
        ] if coverage_is_complete else []
        deleted_ids = [candidate.id for candidate in missing] if delete_missing and coverage_is_complete else []
        unlinked_live_qr_count = 0
        cancelled_pending_task_count = 0
        if deleted_ids:
            deleted_id_set = set(deleted_ids)
            # A stale candidate must not leave a live QR pointing at a row that
            # is about to disappear. Keep the QR itself, but clear only this
            # automation binding so its existing target URL/history remains
            # intact.
            for qr in self.repo.list_live_qr_codes():
                if qr.automationGroupCandidateId not in deleted_id_set:
                    continue
                self.repo.save_live_qr_code(
                    qr.model_copy(
                        update={
                            "automationGroupCandidateId": None,
                            "updatedAt": now,
                        }
                    )
                )
                unlinked_live_qr_count += 1

            # Do not leave not-yet-started marketing tasks referring to a
            # group that is no longer in the account inventory. Completed
            # tasks remain history; a currently running task is intentionally
            # left alone because it may already be in the send flow.
            pending_tasks = self.repo.list_automation_tasks(
                device_id=device_id,
                statuses={"pending"},
                limit=10000,
            )
            for task in pending_tasks:
                candidate_id = str(task.payload.get("candidateId") or "").strip()
                if candidate_id not in deleted_id_set:
                    continue
                self.repo.save_automation_task(
                    task.model_copy(
                        update={
                            "status": "cancelled",
                            "errorMessage": "群已不在微信账号当前完整扫描结果中",
                            "updatedAt": now,
                        }
                    )
                )
                cancelled_pending_task_count += 1
            self.repo.delete_automation_group_candidates(deleted_ids)

        now = now_iso()
        summary = {
            "scanId": clean_scan_id,
            "scanMode": clean_scan_mode,
            "wechatAccountId": wechat_account_id,
            "wechatAccountName": self._normalize_group_name(wechat_account_name) or None,
            "coverage": "complete" if coverage_is_complete else "partial",
            "contactsScanStopReason": contacts_scan_stop_reason or None,
            "chatListScanStopReason": chat_list_scan_stop_reason or None,
            "contactsGroupCount": contacts_group_count,
            "chatListGroupCount": chat_list_group_count,
            "seenCount": len(incoming),
            "createdCount": created_count,
            "updatedCount": updated_count,
            "mappedCount": mapped_count,
            "missingCount": len(missing),
            "deletedCount": len(deleted_ids),
            "unlinkedLiveQrCount": unlinked_live_qr_count,
            "cancelledPendingTaskCount": cancelled_pending_task_count,
            "deleted": bool(deleted_ids),
            "finishedAt": now,
        }
        metadata = dict(device.metadata or {})
        scans = dict(metadata.get("nativeGroupScans") or {})
        scans[wechat_account_id] = summary
        metadata["nativeGroupScans"] = scans
        self.repo.save_automation_device(
            device.model_copy(update={"metadata": metadata, "updatedAt": now})
        )
        return {
            **summary,
            "missing": [
                {"id": candidate.id, "groupName": candidate.groupName}
                for candidate in missing
            ],
        }

    @staticmethod
    def _same_shanghai_day(value: str | None, now: str) -> bool:
        if not value:
            return False
        try:
            current = parse_iso(now).astimezone(SHANGHAI).date()
            checked = parse_iso(value).astimezone(SHANGHAI).date()
            return current == checked
        except (TypeError, ValueError, AttributeError):
            return False

    @staticmethod
    def _fresh_automation_device(device: AutomationDevice, now: str) -> bool:
        if device.status in {"offline", "paused", "degraded"} or not device.lastHeartbeatAt:
            return False
        try:
            return parse_iso(now) - parse_iso(device.lastHeartbeatAt) <= timedelta(minutes=10)
        except (TypeError, ValueError):
            return False

    def schedule_live_qr_member_count_tasks(self) -> dict:
        """Create at most one native-WeChat count task per live QR per day.

        The scheduler deliberately does not infer a group from a fuzzy name. A
        QR is linked only when its explicit candidate id exists, or when exactly
        one native candidate has the same normalized group name. This keeps a
        duplicate WeChat group name from silently reporting the wrong count.
        """
        if not settings.live_qr_member_count_automation_enabled:
            return {"scheduled": 0, "linked": 0, "skipped": "deferred_until_ascript"}
        now = now_iso()
        current = parse_iso(now).astimezone(SHANGHAI)
        if current.hour < 8:
            return {"scheduled": 0, "linked": 0, "skipped": "before_morning_window"}

        candidates = self.repo.list_automation_group_candidates(None, 500)
        native_by_name: dict[str, list[AutomationGroupCandidate]] = {}
        for candidate in candidates:
            if candidate.source != "wechat_native" or not candidate.groupName:
                continue
            key = " ".join(str(candidate.groupName).split())
            native_by_name.setdefault(key, []).append(candidate)

        scheduled = 0
        linked = 0
        for qr in self.repo.list_live_qr_codes():
            if qr.status != "active":
                continue
            candidate = (
                self.repo.get_automation_group_candidate(qr.automationGroupCandidateId)
                if qr.automationGroupCandidateId
                else None
            )
            if not candidate:
                matches = native_by_name.get(" ".join(str(qr.name).split()), [])
                if len(matches) != 1:
                    continue
                candidate = matches[0]
                qr = qr.model_copy(
                    update={
                        "automationGroupCandidateId": candidate.id,
                        "groupMemberCount": candidate.groupMemberCount,
                        "groupMemberCountCheckedAt": candidate.groupMemberCountCheckedAt,
                        "groupMemberCountSource": candidate.groupMemberCountSource,
                        "updatedAt": now,
                    }
                )
                self.repo.save_live_qr_code(qr)
                linked += 1
            if candidate.source != "wechat_native" or not candidate.groupName:
                continue
            device = self.repo.get_automation_device(candidate.deviceId)
            if not device or device.activeWechatAccountId not in {None, candidate.wechatAccountId}:
                continue
            if not self._fresh_automation_device(device, now):
                continue
            if self._same_shanghai_day(candidate.groupMemberCountCheckedAt, now):
                continue
            key = "live-qr-member-count:{}:{}".format(qr.id, current.date().isoformat())
            existing_task = self.repo.find_automation_task_by_idempotency_key(key)
            task = self.create_task(
                function_id="wechat.scan_live_qr_member_count",
                device_id=candidate.deviceId,
                target_wechat_account_id=candidate.wechatAccountId,
                payload={
                    "liveQrCodeId": qr.id,
                    "candidateId": candidate.id,
                    "wechatAccountId": candidate.wechatAccountId,
                    "groupName": candidate.groupName,
                },
                idempotency_key=key,
            )
            if existing_task is None and task.idempotencyKey == key:
                scheduled += 1
        return {"scheduled": scheduled, "linked": linked, "date": current.date().isoformat()}

    def record_live_qr_member_count(
        self,
        *,
        device_id: str,
        candidate_id: str,
        live_qr_code_id: str,
        wechat_account_id: str,
        group_name: str,
        group_member_count: int,
    ) -> dict:
        device = self.repo.get_automation_device(device_id)
        if not device:
            raise AutomationControlError(404, "automation device is not registered")
        if device.activeWechatAccountId and device.activeWechatAccountId != wechat_account_id:
            raise AutomationControlError(409, "member count account does not match the latest device heartbeat")
        candidate = self.repo.get_automation_group_candidate(candidate_id)
        if not candidate:
            raise AutomationControlError(404, "automation group candidate not found")
        if candidate.deviceId != device_id or candidate.wechatAccountId != wechat_account_id:
            raise AutomationControlError(409, "member count candidate belongs to another device or account")
        if " ".join(str(candidate.groupName or "").split()) != " ".join(str(group_name or "").split()):
            raise AutomationControlError(409, "member count group name does not match the candidate")
        qr = self.repo.get_live_qr_code(live_qr_code_id)
        if not qr:
            raise AutomationControlError(404, "live QR code not found")
        if qr.automationGroupCandidateId != candidate.id:
            raise AutomationControlError(409, "live QR code is not linked to this group candidate")
        now = now_iso()
        updated_candidate = candidate.model_copy(
            update={
                "groupMemberCount": int(group_member_count),
                "groupMemberCountCheckedAt": now,
                "groupMemberCountSource": "wechat_group_info",
                "lastSeenAt": now,
                "updatedAt": now,
                "lastError": None,
            }
        )
        self.repo.save_automation_group_candidate(updated_candidate)
        updated_qr = qr.model_copy(
            update={
                "groupMemberCount": int(group_member_count),
                "groupMemberCountCheckedAt": now,
                "groupMemberCountSource": "wechat_group_info",
                "updatedAt": now,
            }
        )
        self.repo.save_live_qr_code(updated_qr)
        return {
            "liveQrCodeId": updated_qr.id,
            "candidateId": updated_candidate.id,
            "groupMemberCount": updated_qr.groupMemberCount,
            "groupMemberCountCheckedAt": updated_qr.groupMemberCountCheckedAt,
        }

    def list_marketing_cards(self, limit: int) -> list[dict]:
        """Return only published card metadata that the PC operator may route.

        The automation control plane must not expose note bodies or private typed-card
        fields.  The Android executor receives the public share snapshot URL/path only
        after a task passes the stricter checks in ``create_marketing_card_task``.
        """
        cards = []
        for note in self.repo.list_all_user_notes(include_deleted=False):
            if note.status == "deleted" or note.shareState != "published":
                continue
            cards.append(self._marketing_card_payload(note))
        cards.sort(key=lambda item: (str(item.get("updatedAt") or ""), str(item.get("id") or "")), reverse=True)
        return cards[: max(1, min(int(limit), 200))]

    def update_marketing_card_route(
        self,
        *,
        note_id: str,
        topic: str,
        region: str,
        content_type: str,
    ) -> dict:
        """Save the PC-only routing metadata without changing card content revision."""
        note = self.repo.get_user_note(note_id)
        if not note or note.status == "deleted":
            raise AutomationControlError(404, "marketing card not found")
        if note.shareState != "published":
            raise AutomationControlError(409, "marketing card must be published before routing")
        clean_topic = " ".join(str(topic or "").split())
        clean_region = " ".join(str(region or "").split())
        clean_content_type = " ".join(str(content_type or "").split())
        if not clean_topic or not clean_content_type:
            raise AutomationControlError(400, "卡片主题和内容类型不能为空")
        config = dict(note.visibilityConfig or {})
        config["marketingRoute"] = {
            "enabled": True,
            "topic": clean_topic,
            "region": clean_region,
            "contentType": clean_content_type,
        }
        note.visibilityConfig = config
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return self._marketing_card_payload(note)

    def create_marketing_card_task(
        self,
        *,
        candidate_id: str,
        note_id: str,
        device_id: str,
        idempotency_key: str | None,
    ) -> AutomationTask:
        candidate = self.repo.get_automation_group_candidate(candidate_id)
        if not candidate:
            raise AutomationControlError(404, "automation group candidate not found")
        if candidate.deviceId != device_id:
            raise AutomationControlError(409, "selected group does not belong to this automation device")
        card = self.repo.get_user_note(note_id)
        if not card or card.status == "deleted":
            raise AutomationControlError(404, "marketing card not found")
        if card.shareState != "published":
            raise AutomationControlError(409, "marketing card must be published before it can be sent")

        eligibility = self.group_send_eligibility(candidate)
        blocked_codes = {
            "not_allowed",
            "pending_review",
            "removed",
            "membership_check_required",
            "activity_check_required",
            "activity_invalid",
            "inactive_3d",
            "profile_required",
        }
        if eligibility["code"] in blocked_codes:
            raise AutomationControlError(409, eligibility["reason"])

        card_payload = self._marketing_card_payload(card)
        route_mismatches = self._marketing_route_mismatches(candidate, card_payload)
        if route_mismatches:
            raise AutomationControlError(409, "群画像与卡片内容不匹配：" + "、".join(route_mismatches))
        snapshot = (card.visibilityConfig or {}).get("shareSnapshot")
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        if snapshot.get("status") != "ready" or not str(snapshot.get("url") or "").strip():
            raise AutomationControlError(409, "资料卡分享图尚未准备完成，不能创建发送任务")
        if str(snapshot.get("sourceRevision") or "") != str(card.revision):
            raise AutomationControlError(409, "资料卡已更新，请重新生成当前版本分享图")

        payload = {
            "candidateId": candidate.id,
            "noteId": card.id,
            "cardId": card.id,
            "cardRevision": card.revision,
            "title": card.title,
            "groupName": candidate.groupName,
            "targetWechatAccountName": self.account_name_for_candidate(candidate),
            "shareSnapshotUrl": snapshot.get("url"),
            "sharePath": f"/pages/note-preview/index?id={card.id}",
            "route": {
                "topic": card_payload["topic"],
                "region": card_payload["region"],
                "contentType": card_payload["contentType"],
            },
        }
        # The route identity is the idempotency boundary.  Do not let a caller
        # reuse one arbitrary key for a different group/card pair.
        key = f"marketing-card:{candidate.id}:{card.id}:{card.revision}"
        return self.create_task(
            function_id="wechat.send_miniapp_card",
            device_id=device_id,
            target_wechat_account_id=candidate.wechatAccountId,
            payload=payload,
            idempotency_key=key,
        )

    @staticmethod
    def _marketing_route_defaults(card_type: str) -> tuple[str, str]:
        return {
            "property_listing": ("房产", "房源"),
            "groupbuy_product": ("本地生活", "团购商品"),
            "service_offer": ("其他", "服务介绍"),
            "business_card": ("其他", "普通资料"),
            "image_ocr": ("其他", "普通资料"),
            "text_note": ("其他", "普通资料"),
        }.get(card_type, ("其他", "普通资料"))

    @staticmethod
    def _infer_region(note: UserNote, structured_data: dict) -> str:
        candidates = [
            structured_data.get("city"),
            structured_data.get("region"),
            structured_data.get("address"),
            structured_data.get("community"),
            structured_data.get("businessArea"),
            note.locationText,
        ]
        for value in candidates:
            text = " ".join(str(value or "").split())
            if not text:
                continue
            match = re.search(r"([\u4e00-\u9fff]{2,12})(?:市|省)", text)
            if match:
                return match.group(1)
            if re.fullmatch(r"[\u4e00-\u9fff]{2,8}", text):
                return text
        return ""

    def _marketing_card_payload(self, note: UserNote) -> dict:
        config = note.visibilityConfig or {}
        card_type = str(config.get("cardType") or "text_note")
        default_topic, default_content_type = self._marketing_route_defaults(card_type)
        route = config.get("marketingRoute") if isinstance(config.get("marketingRoute"), dict) else {}
        structured_data = config.get("structuredData") if isinstance(config.get("structuredData"), dict) else {}
        topic = " ".join(str(route.get("topic") or default_topic).split()) or default_topic
        region = " ".join(str(route.get("region") or self._infer_region(note, structured_data)).split())
        content_type = " ".join(str(route.get("contentType") or default_content_type).split()) or default_content_type
        snapshot = config.get("shareSnapshot") if isinstance(config.get("shareSnapshot"), dict) else {}
        return {
            "id": note.id,
            "ownerUserId": note.ownerUserId,
            "title": note.title,
            "cardType": card_type,
            "topic": topic,
            "region": region,
            "contentType": content_type,
            "revision": note.revision,
            "updatedAt": note.updatedAt,
            "shareSnapshotStatus": snapshot.get("status"),
            "shareSnapshotRevision": snapshot.get("sourceRevision"),
            "shareSnapshotUrl": snapshot.get("url"),
            "sharePath": f"/pages/note-preview/index?id={note.id}",
        }

    @staticmethod
    def _normal_route_value(value: str | None) -> str:
        return "".join(str(value or "").split()).replace("市", "").replace("省", "")

    @staticmethod
    def _normalize_group_codes(values) -> list[str]:
        result = []
        seen = set()
        for value in values or []:
            code = " ".join(str(value or "").split()).strip()
            if not code or code in seen:
                continue
            if len(code) > 40:
                raise AutomationControlError(422, "群编号不能超过 40 个字符")
            seen.add(code)
            result.append(code)
        return result[:20]

    def _marketing_route_mismatches(self, candidate: AutomationGroupCandidate, card: dict) -> list[str]:
        mismatches = []
        if self._normal_route_value(candidate.topic) != self._normal_route_value(card.get("topic")):
            mismatches.append(f"主题需为{candidate.topic or '未设置'}")
        if self._normal_route_value(candidate.region) != self._normal_route_value(card.get("region")):
            mismatches.append(f"地域需为{candidate.region or '未设置'}")
        allowed = [self._normal_route_value(item) for item in (candidate.allowedContentTypes or []) if self._normal_route_value(item)]
        if not allowed or self._normal_route_value(card.get("contentType")) not in allowed:
            mismatches.append(f"内容需为{('、'.join(candidate.allowedContentTypes) if candidate.allowedContentTypes else '群允许内容未设置')}")
        return mismatches

    def review_group_candidate(
        self,
        *,
        candidate_id: str,
        updates: dict,
    ) -> AutomationGroupCandidate:
        existing = self.repo.get_automation_group_candidate(candidate_id)
        if not existing:
            raise AutomationControlError(404, "automation group candidate not found")
        normalized = {}
        if "canSend" in updates:
            normalized["canSend"] = updates["canSend"]
        if "remark" in updates:
            normalized["remark"] = " ".join(str(updates["remark"] or "").split()) or None
        if "groupCodes" in updates:
            normalized["groupCodes"] = self._normalize_group_codes(updates["groupCodes"])
        if "wechatAccountName" in updates:
            normalized["wechatAccountName"] = " ".join(str(updates["wechatAccountName"] or "").split()) or None
        if "topic" in updates:
            normalized["topic"] = " ".join(str(updates["topic"] or "").split()) or None
        if "region" in updates:
            normalized["region"] = " ".join(str(updates["region"] or "").split()) or None
        if "allowedContentTypes" in updates:
            normalized["allowedContentTypes"] = list(dict.fromkeys(
                " ".join(str(item or "").split())
                for item in (updates["allowedContentTypes"] or [])
                if " ".join(str(item or "").split())
            ))[:8]
        if "batchContents" in updates:
            normalized["batchContents"] = self._normalize_batch_contents(updates["batchContents"])
        if "dailySendLimit" in updates:
            normalized["dailySendLimit"] = int(updates["dailySendLimit"])
        if "membershipStatus" in updates:
            normalized["membershipStatus"] = updates["membershipStatus"] or "unknown"
        if "lastActivityAt" in updates:
            normalized["lastActivityAt"] = updates["lastActivityAt"] or None
        if "lastVerifiedAt" in updates:
            normalized["lastVerifiedAt"] = updates["lastVerifiedAt"] or None
        if not normalized:
            raise AutomationControlError(422, "at least one group review field is required")
        updated = existing.model_copy(
            update={
                **normalized,
                "updatedAt": now_iso(),
            }
        )
        self.repo.save_automation_group_candidate(updated)
        return updated

    @staticmethod
    def _normalize_batch_contents(values) -> list[AutomationBatchContent]:
        normalized = []
        seen = set()
        now = now_iso()
        for value in values or []:
            raw = value.model_dump() if hasattr(value, "model_dump") else dict(value or {})
            batch_no = int(raw.get("batchNo") or 0)
            if batch_no in seen:
                raise AutomationControlError(422, f"batch {batch_no} is duplicated")
            if batch_no < 1 or batch_no > 100:
                raise AutomationControlError(422, "batch number must be between 1 and 100")
            seen.add(batch_no)
            card_id = " ".join(str(raw.get("cardId") or "").split()) or None
            text = str(raw.get("text") or "").strip() or None
            enabled = bool(raw.get("enabled", True))
            if enabled and not card_id and not text:
                raise AutomationControlError(422, f"batch {batch_no} must contain text or card")
            normalized.append(AutomationBatchContent(
                batchNo=batch_no,
                cardId=card_id,
                text=text,
                enabled=enabled,
                updatedAt=now,
            ))
        return sorted(normalized, key=lambda item: item.batchNo)

    def bulk_replace_batch_contents(
        self,
        *,
        group_code: str | None = None,
        old_card_id: str | None,
        new_card_id: str | None,
        old_text: str | None,
        new_text: str | None,
    ) -> dict:
        old_card_id = " ".join(str(old_card_id or "").split()) or None
        new_card_id = " ".join(str(new_card_id or "").split()) or None
        old_text = str(old_text or "").strip() or None
        new_text = str(new_text or "").strip() or None
        if old_card_id is None and old_text is None:
            raise AutomationControlError(422, "at least one old card or text value is required")
        normalized_group_code = " ".join(str(group_code or "").split()).strip() or None
        candidates = self.repo.list_automation_group_candidates(None, 10000)
        updated_groups = 0
        updated_batches = 0
        updated_plans = 0
        updated_plan_batches = 0
        now = now_iso()
        for candidate in candidates:
            changed = False
            next_batches = []
            for batch in candidate.batchContents:
                card_matches = old_card_id is None or batch.cardId == old_card_id
                text_matches = old_text is None or batch.text == old_text
                if card_matches and text_matches:
                    updates = {"updatedAt": now}
                    if new_card_id is not None:
                        updates["cardId"] = new_card_id
                    if new_text is not None:
                        updates["text"] = new_text
                    batch = batch.model_copy(update=updates)
                    changed = True
                    updated_batches += 1
                next_batches.append(batch)
            if changed:
                self.repo.save_automation_group_candidate(candidate.model_copy(update={
                    "batchContents": next_batches,
                    "updatedAt": now,
                }))
                updated_groups += 1
        for plan in self.repo.list_automation_group_content_plans(500):
            if normalized_group_code and plan.groupCode != normalized_group_code:
                continue
            changed = False
            next_batches = []
            for batch in plan.batchContents:
                card_matches = old_card_id is None or batch.cardId == old_card_id
                text_matches = old_text is None or batch.text == old_text
                if card_matches and text_matches:
                    updates = {"updatedAt": now}
                    if new_card_id is not None:
                        updates["cardId"] = new_card_id
                    if new_text is not None:
                        updates["text"] = new_text
                    batch = batch.model_copy(update=updates)
                    changed = True
                    updated_plan_batches += 1
                next_batches.append(batch)
            if changed:
                self.repo.save_automation_group_content_plan(plan.model_copy(update={
                    "batchContents": next_batches,
                    "updatedAt": now,
                }))
                updated_plans += 1
        return {
            "updatedGroups": updated_groups,
            "updatedBatches": updated_batches,
            "updatedPlans": updated_plans,
            "updatedPlanBatches": updated_plan_batches,
        }

    def group_send_eligibility(self, candidate: AutomationGroupCandidate) -> dict:
        if candidate.canSend is not True:
            if candidate.canSend is False:
                return {"code": "not_allowed", "label": "未允许进入", "reason": "管理员未允许该群进入营销策略"}
            return {"code": "pending_review", "label": "待管理员确认", "reason": "尚未明确允许该群进入营销策略"}
        if candidate.membershipStatus == "removed":
            return {"code": "removed", "label": "已移出群", "reason": "最近检查确认当前账号不在该群"}
        if candidate.membershipStatus != "active" or not candidate.lastVerifiedAt:
            return {"code": "membership_check_required", "label": "待检查群状态", "reason": "尚未确认当前账号仍在群内"}
        if not candidate.lastActivityAt:
            return {"code": "activity_check_required", "label": "待检查近3天活跃", "reason": "尚未读取群最近活跃时间"}
        try:
            activity_at = parse_iso(candidate.lastActivityAt)
            if activity_at.tzinfo is None:
                activity_at = activity_at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return {"code": "activity_invalid", "label": "活跃时间无效", "reason": "最近活跃时间无法解析，不能发送"}
        if activity_at < datetime.now(tz=timezone.utc) - timedelta(days=3):
            return {"code": "inactive_3d", "label": "近3天无活跃", "reason": "最近3天没有读取到群消息活动"}
        if not candidate.topic or not candidate.region:
            return {"code": "profile_required", "label": "待完善群画像", "reason": "需要先填写群主题和地域"}
        return {"code": "card_route_required", "label": "待配置卡片策略", "reason": "群状态符合基础条件，但还没有匹配的营销卡片策略"}

    def _owned_running_task(
        self,
        task_id: str,
        device_id: str,
        lease_token: str,
        active_wechat_account_id: str | None,
    ) -> AutomationTask:
        task = self.repo.get_automation_task(task_id)
        if not task:
            raise AutomationControlError(404, "automation task not found")
        if task.status in {"success", "failed"}:
            if task.deviceId != device_id:
                raise AutomationControlError(403, "automation task belongs to another device")
            return task
        if task.status != "running" or task.deviceId != device_id or task.leaseToken != lease_token:
            raise AutomationControlError(409, "automation task lease is invalid or expired")
        if task.leaseExpiresAt:
            try:
                if parse_iso(task.leaseExpiresAt) <= parse_iso(now_iso()):
                    raise AutomationControlError(409, "automation task lease is invalid or expired")
            except AutomationControlError:
                raise
            except Exception:
                raise AutomationControlError(409, "automation task lease is invalid or expired")
        if task.targetWechatAccountId and task.targetWechatAccountId != active_wechat_account_id:
            raise AutomationControlError(409, "active WeChat account does not match the task")
        return task

    def _save_device_status(
        self,
        device: AutomationDevice,
        active_wechat_account_id: str | None,
        status: str,
        now: str,
    ) -> None:
        preserved_account_id = (
            active_wechat_account_id
            if active_wechat_account_id is not None
            else device.activeWechatAccountId
        )
        self.repo.save_automation_device(
            device.model_copy(
                update={
                    "status": status,
                    "activeWechatAccountId": preserved_account_id,
                    "lastHeartbeatAt": now,
                    "updatedAt": now,
                }
            )
        )
