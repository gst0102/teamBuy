from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import settings


OPERATOR_HEADERS = {"X-Automation-Operator-Token": "automation-operator-test-token"}
DEVICE_HEADERS = {"X-Automation-Device-Token": "automation-device-test-token"}


def heartbeat(client, device_id: str = "android-01", account_id: str | None = "wechat-1"):
    return client.post(
        "/api/automation/devices/heartbeat",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": device_id,
            "name": "测试安卓手机",
            "hidDeviceId": "esp32-01",
            "activeWechatAccountId": account_id,
            "capabilities": ["ascript", "ble-hid"],
        },
    )


def test_automation_control_requires_role_specific_token(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")

    response = client.post(
        "/api/automation/devices/heartbeat",
        json={"deviceId": "android-01"},
    )

    assert response.status_code == 403

    wrong_role = client.post(
        "/api/automation/devices/heartbeat",
        headers=OPERATOR_HEADERS,
        json={"deviceId": "android-01"},
    )
    assert wrong_role.status_code == 403


def test_admin_token_can_read_automation_control_plane(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-admin-test-token")
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")

    response = client.get(
        "/api/automation/devices",
        headers={"X-Admin-Token": "ops-admin-test-token"},
    )

    assert response.status_code == 200


def test_operator_can_read_wechat_nickname_metadata_but_device_token_cannot(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")

    response = client.post(
        "/api/automation/devices/heartbeat",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-account-identity",
            "name": "测试双开安卓手机",
            "hidDeviceId": "esp32-01",
            "status": "degraded",
            "activeWechatAccountId": "wechat-nickname-leo",
            "capabilities": ["ascript", "double-wechat", "ble-hid"],
            "metadata": {
                "identitySource": "wechat_profile_nickname",
                "wechatAccounts": [
                    {"slot": "wechat-instance-1", "nickname": "高士腾"},
                    {"slot": "wechat-instance-2", "nickname": "leo"},
                ],
            },
        },
    )
    listed = client.get(
        "/api/automation/devices",
        headers=OPERATOR_HEADERS,
        params={"deviceId": "android-account-identity"},
    )
    denied = client.get(
        "/api/automation/devices",
        headers=DEVICE_HEADERS,
        params={"deviceId": "android-account-identity"},
    )

    assert response.status_code == 200
    assert listed.status_code == 200
    assert listed.json()["data"][0]["metadata"]["identitySource"] == "wechat_profile_nickname"
    assert listed.json()["data"][0]["status"] == "degraded"
    assert listed.json()["data"][0]["metadata"]["wechatAccounts"][1]["nickname"] == "leo"
    assert denied.status_code == 403


def test_one_device_claims_tasks_serially_and_records_result(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert heartbeat(client).status_code == 200

    created = client.post(
        "/api/automation/tasks",
        headers=OPERATOR_HEADERS,
        json={
            "functionId": "xhs.find_group",
            "deviceId": "android-01",
            "payload": {"keyword": "资料整理"},
            "idempotencyKey": "xhs-find-001",
        },
    )
    duplicate = client.post(
        "/api/automation/tasks",
        headers=OPERATOR_HEADERS,
        json={
            "functionId": "xhs.find_group",
            "deviceId": "android-01",
            "payload": {"keyword": "资料整理"},
            "idempotencyKey": "xhs-find-001",
        },
    )
    assert created.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["id"] == created.json()["data"]["id"]

    claimed = client.post(
        "/api/automation/tasks/claim",
        headers=DEVICE_HEADERS,
        json={"deviceId": "android-01", "activeWechatAccountId": "wechat-1"},
    )
    second_claim = client.post(
        "/api/automation/tasks/claim",
        headers=DEVICE_HEADERS,
        json={"deviceId": "android-01", "activeWechatAccountId": "wechat-1"},
    )
    assert claimed.status_code == 200
    assert claimed.json()["data"]["status"] == "running"
    assert second_claim.status_code == 200
    assert second_claim.json()["data"] is None

    task = claimed.json()["data"]
    completed = client.post(
        f"/api/automation/tasks/{task['id']}/complete",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-01",
            "leaseToken": task["leaseToken"],
            "activeWechatAccountId": "wechat-1",
            "result": {"candidateCount": 1},
        },
    )
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "success"


def test_account_neutral_xhs_task_does_not_clear_active_wechat_identity(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert heartbeat(client, device_id="android-xhs-01", account_id="wechat-1").status_code == 200

    created = client.post(
        "/api/automation/tasks",
        headers=OPERATOR_HEADERS,
        json={
            "functionId": "xhs.find_group",
            "deviceId": "android-xhs-01",
            "payload": {"keyword": "微信群"},
        },
    )
    assert created.status_code == 200

    claimed = client.post(
        "/api/automation/tasks/claim",
        headers=DEVICE_HEADERS,
        json={"deviceId": "android-xhs-01", "activeWechatAccountId": None},
    )
    assert claimed.status_code == 200
    task = claimed.json()["data"]
    assert task["functionId"] == "xhs.find_group"

    completed = client.post(
        f"/api/automation/tasks/{task['id']}/complete",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-xhs-01",
            "leaseToken": task["leaseToken"],
            "activeWechatAccountId": None,
            "result": {"candidateCount": 2},
        },
    )
    listed = client.get(
        "/api/automation/devices",
        headers=OPERATOR_HEADERS,
        params={"deviceId": "android-xhs-01"},
    )

    assert completed.status_code == 200
    assert listed.status_code == 200
    assert listed.json()["data"][0]["activeWechatAccountId"] == "wechat-1"


def test_task_account_context_is_isolated(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert heartbeat(client, device_id="android-02", account_id="wechat-1").status_code == 200
    created = client.post(
        "/api/automation/tasks",
        headers=OPERATOR_HEADERS,
        json={
            "functionId": "wechat.join_group",
            "deviceId": "android-02",
            "targetWechatAccountId": "wechat-2",
            "payload": {"groupQRCode": "qr-ref-001"},
        },
    )
    assert created.status_code == 200

    wrong_account = client.post(
        "/api/automation/tasks/claim",
        headers=DEVICE_HEADERS,
        json={"deviceId": "android-02", "activeWechatAccountId": "wechat-1"},
    )
    assert wrong_account.status_code == 200
    assert wrong_account.json()["data"] is None

    assert heartbeat(client, device_id="android-02", account_id="wechat-2").status_code == 200
    right_account = client.post(
        "/api/automation/tasks/claim",
        headers=DEVICE_HEADERS,
        json={"deviceId": "android-02", "activeWechatAccountId": "wechat-2"},
    )
    assert right_account.status_code == 200
    assert right_account.json()["data"]["targetWechatAccountId"] == "wechat-2"
    task = right_account.json()["data"]

    wrong_completion = client.post(
        f"/api/automation/tasks/{task['id']}/complete",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-02",
            "leaseToken": task["leaseToken"],
            "activeWechatAccountId": "wechat-1",
        },
    )
    assert wrong_completion.status_code == 409


def test_group_candidate_keeps_minimal_fields_and_is_idempotent(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert heartbeat(client, device_id="android-03", account_id="wechat-1").status_code == 200

    payload = {
        "deviceId": "android-03",
        "wechatAccountId": "wechat-1",
        "groupQRCode": "qr-ref-123",
        "groupName": "资料交流群",
        "joinStatus": "success",
        "canSend": False,
        "idempotencyKey": "group-001",
    }
    first = client.post("/api/automation/group-candidates", headers=DEVICE_HEADERS, json=payload)
    second = client.post(
        "/api/automation/group-candidates",
        headers=DEVICE_HEADERS,
        json={**payload, "canSend": True},
    )
    listed = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-1"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert first.json()["data"]["canSend"] is None
    assert second.json()["data"]["canSend"] is None
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_native_wechat_group_candidate_does_not_require_qr_and_preserves_review_fields(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert heartbeat(client, device_id="android-native-groups", account_id="wechat-leo").status_code == 200

    first = client.post(
        "/api/automation/group-candidates",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-native-groups",
            "wechatAccountId": "wechat-leo",
            "source": "wechat_native",
            "groupName": "川沙房源共享群",
            "joinStatus": "success",
            "canSend": None,
            "remark": "暂不营销",
        },
    )
    second = client.post(
        "/api/automation/group-candidates",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-native-groups",
            "wechatAccountId": "wechat-leo",
            "source": "wechat_native",
            "groupName": "川沙房源共享群",
            "joinStatus": "success",
        },
    )
    listed = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-leo"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert listed.status_code == 200
    assert first.json()["data"]["groupQRCode"] is None
    assert first.json()["data"]["source"] == "wechat_native"
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert second.json()["data"]["remark"] == "暂不营销"
    assert listed.json()["data"][0]["groupName"] == "川沙房源共享群"


def test_xhs_group_candidate_still_requires_qr(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert heartbeat(client, device_id="android-xhs-validation", account_id="wechat-1").status_code == 200

    response = client.post(
        "/api/automation/group-candidates",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-xhs-validation",
            "wechatAccountId": "wechat-1",
            "source": "xiaohongshu",
            "groupName": "资料交流群",
            "joinStatus": "pending",
        },
    )

    assert response.status_code == 422


def test_operator_can_review_native_group_without_device_token(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert heartbeat(client, device_id="android-review", account_id="wechat-review").status_code == 200
    created = client.post(
        "/api/automation/group-candidates",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-review",
            "wechatAccountId": "wechat-review",
            "source": "wechat_native",
            "groupName": "资料整理助手测试群",
            "joinStatus": "success",
        },
    )
    candidate_id = created.json()["data"]["id"]

    reviewed = client.patch(
        f"/api/automation/group-candidates/{candidate_id}",
        headers=OPERATOR_HEADERS,
        json={"canSend": False, "remark": "人工审核：暂不营销"},
    )
    device_attempt = client.patch(
        f"/api/automation/group-candidates/{candidate_id}",
        headers=DEVICE_HEADERS,
        json={"canSend": True, "remark": "不应被设备改写"},
    )

    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["canSend"] is False
    assert reviewed.json()["data"]["remark"] == "人工审核：暂不营销"
    assert device_attempt.status_code == 403

    rescan = client.post(
        "/api/automation/group-candidates",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-review",
            "wechatAccountId": "wechat-review",
            "source": "wechat_native",
            "groupName": "资料整理助手测试群",
            "joinStatus": "success",
            "canSend": None,
        },
    )
    assert rescan.status_code == 200
    assert rescan.json()["data"]["canSend"] is False
    assert rescan.json()["data"]["remark"] == "人工审核：暂不营销"


def test_group_profile_and_send_eligibility_are_separate_from_admin_permission(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert heartbeat(client, device_id="android-profile", account_id="wechat-profile").status_code == 200
    created = client.post(
        "/api/automation/group-candidates",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-profile",
            "wechatAccountId": "wechat-profile",
            "source": "wechat_native",
            "groupName": "上海宠物交流群",
            "joinStatus": "success",
        },
    )
    candidate_id = created.json()["data"]["id"]

    pending = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-profile"},
    )
    assert pending.status_code == 200
    assert pending.json()["data"][0]["sendEligibility"]["code"] == "pending_review"

    now = datetime.now(tz=timezone.utc)
    profiled = client.patch(
        f"/api/automation/group-candidates/{candidate_id}",
        headers=OPERATOR_HEADERS,
        json={
            "topic": "宠物",
            "region": "上海",
            "allowedContentTypes": ["寻猫", "领养"],
            "membershipStatus": "active",
            "lastActivityAt": now.isoformat(),
            "lastVerifiedAt": now.isoformat(),
        },
    )
    assert profiled.status_code == 200
    assert profiled.json()["data"]["canSend"] is None
    assert profiled.json()["data"]["allowedContentTypes"] == ["寻猫", "领养"]
    assert profiled.json()["data"]["sendEligibility"]["code"] == "pending_review"

    allowed = client.patch(
        f"/api/automation/group-candidates/{candidate_id}",
        headers=OPERATOR_HEADERS,
        json={"canSend": True},
    )
    assert allowed.status_code == 200
    assert allowed.json()["data"]["sendEligibility"]["code"] == "card_route_required"

    inactive = client.patch(
        f"/api/automation/group-candidates/{candidate_id}",
        headers=OPERATOR_HEADERS,
        json={"lastActivityAt": (now - timedelta(days=4)).isoformat()},
    )
    assert inactive.status_code == 200
    assert inactive.json()["data"]["sendEligibility"]["code"] == "inactive_3d"


def test_marketing_card_catalog_and_single_group_task_are_route_checked(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert heartbeat(client, device_id="android-marketing", account_id="wechat-marketing").status_code == 200

    owner = client.post("/api/auth/mock-login", json={"nickname": "营销资料用户"}).json()["data"]
    draft = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner["id"],
            "cardType": "text_note",
            "inputMode": "paste_text",
            "rawText": "长沙宠物寻猫与领养资料",
        },
    ).json()["data"]
    updated = client.put(
        f"/api/notes/{draft['id']}",
        json={
            "ownerUserId": owner["id"],
            "expectedRevision": draft["revision"],
            "title": "上海宠物寻猫资料",
            "summary": "宠物群测试卡",
            "body": "寻猫与领养信息",
            "contentBlocks": [{"type": "text", "text": "寻猫与领养信息", "sortOrder": 0}],
            "visibilityConfig": draft.get("visibilityConfig") or {},
        },
    )
    assert updated.status_code == 200
    published = client.post(
        f"/api/notes/{draft['id']}/publish",
        json={"ownerUserId": owner["id"], "expectedRevision": updated.json()["data"]["revision"]},
    )
    assert published.status_code == 200
    published_note = published.json()["data"]
    routed = client.patch(
        f"/api/automation/marketing-cards/{draft['id']}/route",
        headers=OPERATOR_HEADERS,
        json={"topic": "宠物", "region": "上海", "contentType": "寻猫/领养"},
    )
    assert routed.status_code == 200
    assert routed.json()["data"]["topic"] == "宠物"
    assert routed.json()["data"]["region"] == "上海"
    assert routed.json()["data"]["contentType"] == "寻猫/领养"
    owner_note = client.get(f"/api/notes/{draft['id']}", params={"ownerUserId": owner["id"]})
    assert owner_note.status_code == 200
    assert "marketingRoute" not in (owner_note.json()["data"].get("visibilityConfig") or {})
    owner_notes = client.get("/api/notes", params={"ownerUserId": owner["id"]})
    assert owner_notes.status_code == 200
    assert all("marketingRoute" not in (item.get("visibilityConfig") or {}) for item in owner_notes.json()["data"])
    snapshot = client.patch(
        f"/api/notes/{draft['id']}/share-snapshot",
        json={
            "ownerUserId": owner["id"],
            "sourceRevision": str(published_note["revision"]),
            "fingerprint": "marketing-card-test",
            "url": "/media/marketing-card-test.webp",
        },
    )
    assert snapshot.status_code == 200

    candidate = client.post(
        "/api/automation/group-candidates",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-marketing",
            "wechatAccountId": "wechat-marketing",
            "source": "wechat_native",
            "groupName": "上海宠物测试群",
            "joinStatus": "success",
        },
    ).json()["data"]
    now = datetime.now(tz=timezone.utc).isoformat()
    profiled = client.patch(
        f"/api/automation/group-candidates/{candidate['id']}",
        headers=OPERATOR_HEADERS,
        json={
            "topic": "宠物",
            "region": "上海",
            "allowedContentTypes": ["寻猫/领养"],
            "membershipStatus": "active",
            "lastActivityAt": now,
            "lastVerifiedAt": now,
            "canSend": True,
        },
    )
    assert profiled.status_code == 200

    cards = client.get("/api/automation/marketing-cards", headers=OPERATOR_HEADERS)
    assert cards.status_code == 200
    card = next(item for item in cards.json()["data"] if item["id"] == draft["id"])
    assert card["topic"] == "宠物"
    assert card["region"] == "上海"
    assert card["contentType"] == "寻猫/领养"
    assert "body" not in card
    assert "privateData" not in card
    public_note = client.get(f"/api/notes/public/{draft['id']}")
    assert public_note.status_code == 200
    assert "marketingRoute" not in (public_note.json()["data"].get("visibilityConfig") or {})

    task = client.post(
        "/api/automation/marketing-card-tasks",
        headers=OPERATOR_HEADERS,
        json={
            "candidateId": candidate["id"],
            "noteId": draft["id"],
            "deviceId": "android-marketing",
        },
    )
    assert task.status_code == 200
    task_data = task.json()["data"]
    assert task_data["functionId"] == "wechat.send_miniapp_card"
    assert task_data["status"] == "pending"
    assert task_data["payload"]["groupName"] == "上海宠物测试群"
    assert "targetWechatAccountName" in task_data["payload"]
    assert task_data["payload"]["route"]["contentType"] == "寻猫/领养"

    mismatch = client.patch(
        f"/api/automation/group-candidates/{candidate['id']}",
        headers=OPERATOR_HEADERS,
        json={"region": "长沙"},
    )
    assert mismatch.status_code == 200
    blocked = client.post(
        "/api/automation/marketing-card-tasks",
        headers=OPERATOR_HEADERS,
        json={
            "candidateId": candidate["id"],
            "noteId": draft["id"],
            "deviceId": "android-marketing",
        },
    )
    assert blocked.status_code == 409
    assert "地域" in blocked.json()["detail"]
