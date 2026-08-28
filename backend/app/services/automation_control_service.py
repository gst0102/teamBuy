from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re

from app.models.domain import AutomationDevice, AutomationGroupCandidate, AutomationTask, UserNote
from app.services.helpers import new_id
from app.services.repository import AppRepository
from app.services.time_utils import now_iso, parse_iso


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
        lease_seconds: int,
    ) -> AutomationTask | None:
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
        device = self.repo.get_automation_device(device_id)
        if device:
            self._save_device_status(device, active_wechat_account_id, "ready", now)
        return updated

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
        if source == "wechat_native" and not normalized_name:
            raise AutomationControlError(422, "native WeChat group candidate requires a group name")
        if source == "xiaohongshu" and not str(group_qr_code or "").strip():
            raise AutomationControlError(422, "Xiaohongshu group candidate requires a group QR code")
        key = str(idempotency_key or "").strip()
        if not key:
            identity = group_qr_code if source == "xiaohongshu" else normalized_name
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            key = f"group:{source}:{wechat_account_id}:{digest}"
        existing = self.repo.get_automation_group_candidate(candidate_id) if candidate_id else None
        existing = existing or self.repo.find_automation_group_candidate_by_idempotency_key(key)
        if existing and (existing.deviceId != device_id or existing.wechatAccountId != wechat_account_id):
            raise AutomationControlError(409, "group candidate belongs to another device or account")
        now = now_iso()
        candidate = AutomationGroupCandidate(
            id=existing.id if existing else (candidate_id or new_id("group_candidate")),
            deviceId=device_id,
            wechatAccountId=wechat_account_id,
            source=source,
            groupQRCode=group_qr_code or (existing.groupQRCode if existing else None),
            groupName=normalized_name or (existing.groupName if existing else None),
            wechatAccountName=(
                " ".join(str(wechat_account_name or "").split())
                or (existing.wechatAccountName if existing else None)
            ),
            savedAt=saved_at or (existing.savedAt if existing else now),
            joinStatus=join_status,
            canSend=can_send if can_send is not None else (existing.canSend if existing else None),
            remark=remark if remark is not None else (existing.remark if existing else None),
            topic=existing.topic if existing else None,
            region=existing.region if existing else None,
            allowedContentTypes=list(existing.allowedContentTypes) if existing else [],
            membershipStatus=existing.membershipStatus if existing else "unknown",
            lastActivityAt=existing.lastActivityAt if existing else None,
            lastVerifiedAt=existing.lastVerifiedAt if existing else None,
            lastSeenAt=last_seen_at or now,
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
