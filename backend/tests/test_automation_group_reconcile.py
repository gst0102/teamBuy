from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings


OPERATOR_HEADERS = {"X-Automation-Operator-Token": "automation-operator-test-token"}
DEVICE_HEADERS = {"X-Automation-Device-Token": "automation-device-test-token"}


def _heartbeat(client, account_id: str):
    return client.post(
        "/api/automation/devices/heartbeat",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "name": "双微信测试手机",
            "activeWechatAccountId": account_id,
            "capabilities": ["ascript", "double-wechat"],
        },
    )


def _native_group(client, account_id: str, name: str):
    return client.post(
        "/api/automation/group-candidates",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "wechatAccountId": account_id,
            "wechatAccountName": account_id,
            "source": "wechat_native",
            "groupName": name,
            "joinStatus": "success",
        },
    )


def test_complete_native_group_scan_deletes_only_missing_rows_for_one_wechat_account(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")

    assert _heartbeat(client, "wechat-one").status_code == 200
    assert _native_group(client, "wechat-one", "保留群").status_code == 200
    assert _native_group(client, "wechat-one", "已退出群").status_code == 200
    xhs = client.post(
        "/api/automation/group-candidates",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "wechatAccountId": "wechat-one",
            "source": "xiaohongshu",
            "groupQRCode": "qr-keep",
            "groupName": "小红书资源",
            "joinStatus": "pending",
        },
    )
    assert xhs.status_code == 200

    assert _heartbeat(client, "wechat-two").status_code == 200
    assert _native_group(client, "wechat-two", "保留群").status_code == 200
    account_two_scan = client.post(
        "/api/automation/group-candidates/reconcile",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "wechatAccountId": "wechat-two",
            "wechatAccountName": "微信二",
            "scanId": "scan-two",
            "coverage": "complete",
            "contactsScanStopReason": "stable",
            "chatListScanStopReason": "bottom_stable",
            "groupNames": ["保留群"],
            "deleteMissing": True,
        },
    )
    assert account_two_scan.status_code == 200
    assert account_two_scan.json()["data"]["deletedCount"] == 0

    assert _heartbeat(client, "wechat-one").status_code == 200
    account_one_scan = client.post(
        "/api/automation/group-candidates/reconcile",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "wechatAccountId": "wechat-one",
            "wechatAccountName": "微信一",
            "scanId": "scan-one",
            "coverage": "complete",
            "contactsScanStopReason": "reported_total",
            "chatListScanStopReason": "bottom_stable",
            "groupNames": ["保留群"],
            "deleteMissing": True,
        },
    )
    assert account_one_scan.status_code == 200
    assert account_one_scan.json()["data"]["deletedCount"] == 1

    assert account_one_scan.json()["data"]["missingCount"] == 1

    one = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-one"},
    ).json()["data"]
    two = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-two"},
    ).json()["data"]
    assert {item["groupName"] for item in one if item["source"] == "wechat_native"} == {"保留群"}
    assert {item["groupName"] for item in one if item["source"] == "xiaohongshu"} == {"小红书资源"}
    assert {item["groupName"] for item in two if item["source"] == "wechat_native"} == {"保留群"}

    devices = client.get("/api/automation/devices", headers=OPERATOR_HEADERS).json()["data"]
    metadata = next(item for item in devices if item["id"] == "android-reconcile")["metadata"]
    assert metadata["nativeGroupScans"]["wechat-one"]["scanId"] == "scan-one"


def test_targeted_native_scan_updates_code_mapping_before_device_queue(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert _heartbeat(client, "wechat-leo").status_code == 200

    scanned = client.post(
        "/api/automation/group-candidates/reconcile",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "wechatAccountId": "wechat-leo",
            "wechatAccountName": "leo",
            "scanId": "targeted-c1001",
            "scanMode": "targeted",
            "coverage": "partial",
            "chatListScanStopReason": "targeted_bottom_stable",
            "groupNames": ["互助群", "测试群"],
            "groupMappings": [
                {"groupCode": "c1001", "groupName": "互助群"},
                {"groupCode": "c1001", "groupName": "测试群"},
            ],
        },
    )
    assert scanned.status_code == 200
    assert scanned.json()["data"]["mappedCount"] == 2

    candidates = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-leo"},
    ).json()["data"]
    assert {item["groupName"] for item in candidates} == {"互助群", "测试群"}
    assert {tuple(item["groupCodes"]) for item in candidates} == {("c1001",)}
    assert {item["canSend"] for item in candidates} == {True}

    now = datetime.now(tz=timezone.utc).isoformat()
    for candidate in candidates:
        reviewed = client.patch(
            f"/api/automation/group-candidates/{candidate['id']}",
            headers=OPERATOR_HEADERS,
            json={
                "canSend": True,
                "membershipStatus": "active",
                "lastVerifiedAt": now,
                "lastActivityAt": now,
                "topic": "测试",
                "region": "包头",
            },
        )
        assert reviewed.status_code == 200

    assert client.post(
        "/api/automation/card-assets",
        headers=OPERATOR_HEADERS,
        json={"cardId": "act-001", "cardTitle": "测试现有小程序卡片"},
    ).status_code == 200
    assert client.post(
        "/api/automation/group-content-plans",
        headers=OPERATOR_HEADERS,
        json={
            "groupCode": "c1001",
            "batchContents": [{"batchNo": 1, "cardId": "act-001", "text": "测试文字"}],
        },
    ).status_code == 200

    queued = client.post(
        "/api/automation/group-content-plans/device-run",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "batchNo": 1,
            "wechatAccountIds": ["wechat-leo"],
            "groupCodes": ["c1001"],
            "runId": "preflight-c1001",
        },
    )
    assert queued.status_code == 200
    assert queued.json()["data"]["createdCount"] == 1
    assert queued.json()["data"]["targetCount"] == 2


def test_pc_can_configure_scan_prefixes_and_scan_only_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert _heartbeat(client, "wechat-leo").status_code == 200

    saved = client.put(
        "/api/automation/devices/android-reconcile/group-scan-config",
        headers=OPERATOR_HEADERS,
        json={"searchPrefixes": ["g10", "c1001", "c1001"], "scanOnly": True},
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["searchPrefixes"] == ["g10", "c1001"]
    assert saved.json()["data"]["scanOnly"] is True

    fetched = client.get(
        "/api/automation/devices/android-reconcile/group-scan-config",
        headers=DEVICE_HEADERS,
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["searchPrefixes"] == ["g10", "c1001"]
    assert fetched.json()["data"]["scanOnly"] is True

    invalid = client.put(
        "/api/automation/devices/android-reconcile/group-scan-config",
        headers=OPERATOR_HEADERS,
        json={"searchPrefixes": ["all"], "scanOnly": True},
    )
    assert invalid.status_code == 422


def test_same_named_native_groups_are_bundled_with_observed_multiplicity(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert _heartbeat(client, "wechat-leo").status_code == 200

    scanned = client.post(
        "/api/automation/group-candidates/reconcile",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "wechatAccountId": "wechat-leo",
            "scanId": "same-name-c1001",
            "scanMode": "targeted",
            "coverage": "partial",
            "groupNames": ["重名测试群"],
            "groupMappings": [
                {"groupCode": "c1001", "groupName": "重名测试群", "occurrenceCount": 2},
            ],
        },
    )
    assert scanned.status_code == 200
    assert scanned.json()["data"]["createdCount"] == 1
    assert scanned.json()["data"]["mappedCount"] == 2

    candidates = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-leo"},
    ).json()["data"]
    same_name = [item for item in candidates if item["groupName"] == "重名测试群"]
    assert len(same_name) == 1
    assert same_name[0]["groupOccurrenceCount"] == 2
    assert same_name[0]["groupIdentity"] is None

    repeated_scan = client.post(
        "/api/automation/group-candidates/reconcile",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "wechatAccountId": "wechat-leo",
            "scanId": "same-name-c1001-repeat",
            "scanMode": "targeted",
            "coverage": "partial",
            "groupNames": ["重名测试群"],
            "groupMappings": [
                {"groupCode": "c1001", "groupName": "重名测试群", "occurrenceCount": 2},
            ],
        },
    )
    assert repeated_scan.status_code == 200
    assert repeated_scan.json()["data"]["createdCount"] == 0
    assert repeated_scan.json()["data"]["updatedCount"] == 1

    assert client.post(
        "/api/automation/card-assets",
        headers=OPERATOR_HEADERS,
        json={"cardId": "act-001", "cardTitle": "测试素材卡片"},
    ).status_code == 200
    assert client.post(
        "/api/automation/group-content-plans",
        headers=OPERATOR_HEADERS,
        json={
            "groupCode": "c1001",
            "batchContents": [{"batchNo": 1, "cardId": "act-001", "text": "测试文字"}],
        },
    ).status_code == 200
    queued = client.post(
        "/api/automation/group-content-plans/device-run",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "batchNo": 1,
            "wechatAccountIds": ["wechat-leo"],
            "groupCodes": ["c1001"],
            "runId": "same-name-forward-test",
        },
    )
    assert queued.status_code == 200
    assert queued.json()["data"]["targetCount"] == 2
    targets = queued.json()["data"]["tasks"][0]["payload"]["targets"]
    assert [item["groupName"] for item in targets] == ["重名测试群"]
    assert targets[0]["groupOccurrenceCount"] == 2
    assert targets[0]["candidateIds"] == [same_name[0]["id"]]


def test_same_code_and_name_without_identity_is_collapsed_into_count(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    assert _heartbeat(client, "wechat-leo").status_code == 200
    response = client.post(
        "/api/automation/group-candidates/reconcile",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "wechatAccountId": "wechat-leo",
            "scanId": "ambiguous-same-name",
            "scanMode": "targeted",
            "groupMappings": [
                {"groupCode": "c1001", "groupName": "重名测试群"},
                {"groupCode": "c1001", "groupName": "重名测试群"},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["createdCount"] == 1
    candidates = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-leo"},
    ).json()["data"]
    same_name = [item for item in candidates if item["groupName"] == "重名测试群"]
    assert len(same_name) == 1
    assert same_name[0]["groupOccurrenceCount"] == 2


def test_group_content_plan_is_shared_by_group_code_and_replaced_by_code(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    response = client.post(
        "/api/automation/group-content-plans",
        headers=OPERATOR_HEADERS,
        json={
            "groupCode": "g1001",
            "remark": "资料工具类群统一发送方案",
            "batchContents": [
                {"batchNo": 1, "cardId": "act-001", "text": "原始文字"},
                {"batchNo": 2, "cardId": "act-002"},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["groupCode"] == "g1001"
    assert response.json()["data"]["remark"] == "资料工具类群统一发送方案"
    assert [item["batchNo"] for item in response.json()["data"]["batchContents"]] == [1, 2]

    listed = client.get("/api/automation/group-content-plans", headers=OPERATOR_HEADERS)
    assert listed.status_code == 200
    assert [item["groupCode"] for item in listed.json()["data"]] == ["g1001"]

    replaced = client.post(
        "/api/automation/group-content-plans/bulk-replace",
        headers=OPERATOR_HEADERS,
        json={
            "groupCode": "g1001",
            "oldCardId": "act-001",
            "newCardId": "act-009",
            "oldText": "原始文字",
            "newText": "更新文字",
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["data"]["updatedPlans"] == 1
    assert replaced.json()["data"]["updatedPlanBatches"] == 1

    refreshed = client.get("/api/automation/group-content-plans", headers=OPERATOR_HEADERS)
    batch = refreshed.json()["data"][0]["batchContents"][0]
    assert batch["cardId"] == "act-009"
    assert batch["text"] == "更新文字"


def test_group_code_batch_expands_to_each_bound_group_without_hardcoding_code(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert _heartbeat(client, "wechat-one").status_code == 200

    candidates = [
        _native_group(client, "wechat-one", "c1001测试群甲").json()["data"],
        _native_group(client, "wechat-one", "c1001测试群乙").json()["data"],
    ]
    now = datetime.now(tz=timezone.utc).isoformat()
    for candidate in candidates:
        response = client.patch(
            f"/api/automation/group-candidates/{candidate['id']}",
            headers=OPERATOR_HEADERS,
            json={
                "canSend": True,
                "groupCodes": ["c1001"],
                "topic": "测试",
                "region": "包头",
                "membershipStatus": "active",
                "lastVerifiedAt": now,
                "lastActivityAt": now,
            },
        )
        assert response.status_code == 200

    asset = client.post(
        "/api/automation/card-assets",
        headers=OPERATOR_HEADERS,
        json={"cardId": "act-001", "cardTitle": "测试现有小程序卡片"},
    )
    assert asset.status_code == 200

    plan = client.post(
        "/api/automation/group-content-plans",
        headers=OPERATOR_HEADERS,
        json={
            "groupCode": "c1001",
            "batchContents": [{"batchNo": 1, "cardId": "act-001", "text": "测试文字"}],
        },
    )
    assert plan.status_code == 200

    queued = client.post(
        "/api/automation/group-content-plans/tasks",
        headers=OPERATOR_HEADERS,
        json={
            "groupCode": "c1001",
            "batchNo": 1,
            "deviceId": "android-reconcile",
        },
    )
    assert queued.status_code == 200
    data = queued.json()["data"]
    assert data["groupCode"] == "c1001"
    assert data["batchNo"] == 1
    assert data["createdCount"] == 2
    assert {task["payload"]["groupName"] for task in data["tasks"]} == {
        "c1001测试群甲",
        "c1001测试群乙",
    }
    assert {task["payload"]["cardTitle"] for task in data["tasks"]} == {"测试现有小程序卡片"}
    assert {task["functionId"] for task in data["tasks"]} == {"wechat.send_group_batch"}


def test_group_code_batch_allows_unverified_membership_until_phone_lookup(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert _heartbeat(client, "wechat-one").status_code == 200
    candidate = _native_group(client, "wechat-one", "待手机确认群").json()["data"]
    reviewed = client.patch(
        f"/api/automation/group-candidates/{candidate['id']}",
        headers=OPERATOR_HEADERS,
        json={
            "canSend": True,
            "groupCodes": ["c1001"],
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["membershipStatus"] == "unknown"

    plan = client.post(
        "/api/automation/group-content-plans",
        headers=OPERATOR_HEADERS,
        json={
            "groupCode": "c1001",
            "batchContents": [{"batchNo": 1, "cardId": "act-001", "text": "测试文字"}],
        },
    )
    assert plan.status_code == 200
    queued = client.post(
        "/api/automation/group-content-plans/tasks",
        headers=OPERATOR_HEADERS,
        json={"groupCode": "c1001", "batchNo": 1, "deviceId": "android-reconcile"},
    )
    assert queued.status_code == 200
    assert queued.json()["data"]["createdCount"] == 1
    assert queued.json()["data"]["skippedCount"] == 0


def test_device_batch_run_groups_targets_and_records_missing_target(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert _heartbeat(client, "wechat-one").status_code == 200
    # 排序靠前的禁用群不应占掉 maxTargets=2 的一个名额。
    blocked = _native_group(client, "wechat-one", "a禁用群").json()["data"]
    assert client.patch(
        f"/api/automation/group-candidates/{blocked['id']}",
        headers=OPERATOR_HEADERS,
        json={"canSend": False, "groupCodes": ["c1001"]},
    ).status_code == 200
    candidates = [
        _native_group(client, "wechat-one", "c1001测试群甲").json()["data"],
        _native_group(client, "wechat-one", "c1001测试群乙").json()["data"],
    ]
    for candidate in candidates:
        reviewed = client.patch(
            f"/api/automation/group-candidates/{candidate['id']}",
            headers=OPERATOR_HEADERS,
            json={"canSend": True, "groupCodes": ["c1001"]},
        )
        assert reviewed.status_code == 200
    assert client.post(
        "/api/automation/card-assets",
        headers=OPERATOR_HEADERS,
        json={"cardId": "act-001", "cardTitle": "测试现有小程序卡片"},
    ).status_code == 200
    assert client.post(
        "/api/automation/group-content-plans",
        headers=OPERATOR_HEADERS,
        json={
            "groupCode": "c1001",
            "batchContents": [{"batchNo": 1, "cardId": "act-001", "text": "测试文字"}],
        },
    ).status_code == 200

    stale = client.post(
        "/api/automation/tasks",
        headers=OPERATOR_HEADERS,
        json={
            "functionId": "wechat.send_group_batch",
            "deviceId": "android-reconcile",
            "targetWechatAccountId": "wechat-one",
            "payload": {"runId": "stale-run"},
        },
    )
    assert stale.status_code == 200

    queued = client.post(
        "/api/automation/group-content-plans/device-run",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "batchNo": 1,
            "wechatAccountIds": ["wechat-one"],
            "groupCodes": ["c1001"],
            "maxTargets": 2,
        },
    )
    assert queued.status_code == 200
    data = queued.json()["data"]
    assert data["createdCount"] == 1
    assert data["targetCount"] == 2
    assert data["skippedCount"] == 1
    assert data["skippedItems"] == [{
        "groupCode": "c1001",
        "candidateId": blocked["id"],
        "groupName": "a禁用群",
        "wechatAccountId": "wechat-one",
        "reasonCode": "not_allowed",
        "reason": "同名群按一个目标包管理；管理员未允许该群进入营销策略",
    }]
    task = data["tasks"][0]
    assert task["targetWechatAccountId"] == "wechat-one"
    assert task["payload"]["runId"] == data["runId"]
    assert {item["groupName"] for item in task["payload"]["targets"]} == {
        "c1001测试群甲",
        "c1001测试群乙",
    }

    claimed = client.post(
        "/api/automation/tasks/claim",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "activeWechatAccountId": "wechat-one",
            "runId": data["runId"],
        },
    )
    assert claimed.status_code == 200
    running = claimed.json()["data"]
    completed = client.post(
        f"/api/automation/tasks/{running['id']}/complete",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "leaseToken": running["leaseToken"],
            "activeWechatAccountId": "wechat-one",
            "result": {
                "status": "partial",
                "targetResults": [
                    {
                        "candidateId": candidates[0]["id"],
                        "groupName": "c1001测试群甲",
                        "status": "group_not_found",
                        "groupNotFound": True,
                    },
                    {
                        "candidateId": candidates[1]["id"],
                        "groupName": "c1001测试群乙",
                        "status": "sent_ui_confirmed",
                    },
                ],
            },
        },
    )
    assert completed.status_code == 200
    rows = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-one"},
    ).json()["data"]
    missing = next(item for item in rows if item["id"] == candidates[0]["id"])
    assert missing["membershipStatus"] == "removed"


def test_device_batch_run_keeps_stable_wechat_accounts_and_targets_separate(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    account_one = "wechat-id-qq673105954"
    account_two = "wechat-id-gaoshiteng_01"

    assert _heartbeat(client, account_one).status_code == 200
    first = _native_group(client, account_one, "测试群").json()["data"]
    assert client.patch(
        f"/api/automation/group-candidates/{first['id']}",
        headers=OPERATOR_HEADERS,
        json={"canSend": True, "groupCodes": ["c1001"]},
    ).status_code == 200

    assert _heartbeat(client, account_two).status_code == 200
    second = _native_group(client, account_two, "互助群").json()["data"]
    assert client.patch(
        f"/api/automation/group-candidates/{second['id']}",
        headers=OPERATOR_HEADERS,
        json={"canSend": True, "groupCodes": ["c1001"]},
    ).status_code == 200

    assert client.post(
        "/api/automation/card-assets",
        headers=OPERATOR_HEADERS,
        json={"cardId": "act-001", "cardTitle": "测试现有小程序卡片"},
    ).status_code == 200
    assert client.post(
        "/api/automation/group-content-plans",
        headers=OPERATOR_HEADERS,
        json={
            "groupCode": "c1001",
            "batchContents": [{"batchNo": 1, "cardId": "act-001", "text": "测试文字"}],
        },
    ).status_code == 200

    queued = client.post(
        "/api/automation/group-content-plans/device-run",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "batchNo": 1,
            "wechatAccountIds": [account_one, account_two],
            "groupCodes": ["c1001"],
            "maxTargets": 2,
            "runId": "stable-two-account-run",
        },
    )
    assert queued.status_code == 200
    data = queued.json()["data"]
    assert data["createdCount"] == 2
    assert data["targetCount"] == 2
    assert {task["targetWechatAccountId"] for task in data["tasks"]} == {account_one, account_two}
    assert {
        (task["targetWechatAccountId"], task["payload"]["targets"][0]["groupName"])
        for task in data["tasks"]
    } == {(account_one, "测试群"), (account_two, "互助群")}


def test_group_not_found_task_failure_marks_candidate_removed(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert _heartbeat(client, "wechat-one").status_code == 200
    candidate = _native_group(client, "wechat-one", "执行时找不到群").json()["data"]
    reviewed = client.patch(
        f"/api/automation/group-candidates/{candidate['id']}",
        headers=OPERATOR_HEADERS,
        json={"canSend": True, "groupCodes": ["c1001"]},
    )
    assert reviewed.status_code == 200
    plan = client.post(
        "/api/automation/group-content-plans",
        headers=OPERATOR_HEADERS,
        json={"groupCode": "c1001", "batchContents": [{"batchNo": 1, "text": "测试文字"}]},
    )
    assert plan.status_code == 200
    queued = client.post(
        "/api/automation/group-content-plans/tasks",
        headers=OPERATOR_HEADERS,
        json={"groupCode": "c1001", "batchNo": 1, "deviceId": "android-reconcile"},
    )
    assert queued.status_code == 200
    claimed = client.post(
        "/api/automation/tasks/claim",
        headers=DEVICE_HEADERS,
        json={"deviceId": "android-reconcile", "activeWechatAccountId": "wechat-one"},
    )
    assert claimed.status_code == 200
    task = claimed.json()["data"]
    failed = client.post(
        f"/api/automation/tasks/{task['id']}/fail",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "leaseToken": task["leaseToken"],
            "activeWechatAccountId": "wechat-one",
            "errorMessage": "当前微信群标题与任务目标不一致，已拒绝发送",
            "result": {
                "status": "group_not_found",
                "groupNotFound": True,
                "candidateId": candidate["id"],
                "groupName": "执行时找不到群",
            },
        },
    )
    assert failed.status_code == 200
    refreshed = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-one"},
    )
    item = next(row for row in refreshed.json()["data"] if row["id"] == candidate["id"])
    assert item["canSend"] is False
    assert item["membershipStatus"] == "removed"
    assert "找不到群" in item["lastError"]


def test_partial_native_group_scan_never_deletes_missing_rows(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert _heartbeat(client, "wechat-partial").status_code == 200
    assert _native_group(client, "wechat-partial", "暂时不可见群").status_code == 200

    response = client.post(
        "/api/automation/group-candidates/reconcile",
        headers=DEVICE_HEADERS,
        json={
            "deviceId": "android-reconcile",
            "wechatAccountId": "wechat-partial",
            "scanId": "scan-partial",
            "scanMode": "incremental",
            "coverage": "partial",
            "contactsScanStopReason": "scroll_guard",
            "chatListScanStopReason": "scroll_guard",
            "groupNames": [],
            "deleteMissing": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["deletedCount"] == 0
    assert response.json()["data"]["scanMode"] == "incremental"
    rows = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-partial"},
    ).json()["data"]
    assert [item["groupName"] for item in rows] == ["暂时不可见群"]


def test_group_batch_contents_can_be_saved_and_bulk_replaced(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert _heartbeat(client, "wechat-batch").status_code == 200
    created = _native_group(client, "wechat-batch", "批次测试群").json()["data"]

    updated = client.patch(
        f"/api/automation/group-candidates/{created['id']}",
        headers=OPERATOR_HEADERS,
        json={
            "topic": "资料",
            "groupCodes": ["g1001", "g1002", "g1001"],
            "batchContents": [
                {"batchNo": 1, "cardId": "act-001", "text": "第一批文字"},
                {"batchNo": 2, "text": "第二批文字"},
            ],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["groupCodes"] == ["g1001", "g1002"]
    assert [item["batchNo"] for item in updated.json()["data"]["batchContents"]] == [1, 2]

    replaced = client.post(
        "/api/automation/group-candidates/batch-contents/bulk-replace",
        headers=OPERATOR_HEADERS,
        json={"oldCardId": "act-001", "newCardId": "act-009", "oldText": "第一批文字", "newText": "更新后的文字"},
    )
    assert replaced.status_code == 200
    assert replaced.json()["data"] == {"updatedGroups": 1, "updatedBatches": 1}

    rows = client.get(
        "/api/automation/group-candidates",
        headers=OPERATOR_HEADERS,
        params={"wechatAccountId": "wechat-batch"},
    ).json()["data"]
    assert rows[0]["batchContents"][0]["cardId"] == "act-009"
    assert rows[0]["batchContents"][0]["text"] == "更新后的文字"


def test_card_asset_catalog_and_daily_limit_are_persisted(client, monkeypatch):
    monkeypatch.setattr(settings, "automation_operator_token", "automation-operator-test-token")
    monkeypatch.setattr(settings, "automation_device_token", "automation-device-test-token")
    assert _heartbeat(client, "wechat-card-catalog").status_code == 200
    created = _native_group(client, "wechat-card-catalog", "卡片目录测试群").json()["data"]

    asset = client.post(
        "/api/automation/card-assets",
        headers=OPERATOR_HEADERS,
        json={"cardId": "act-001", "deepLink": "#小程序://资料整理助手/test", "cardTitle": "资料整理助手"},
    )
    assert asset.status_code == 200
    assert client.get("/api/automation/card-assets", headers=OPERATOR_HEADERS).json()["data"][0]["cardId"] == "act-001"

    updated = client.patch(
        f"/api/automation/group-candidates/{created['id']}",
        headers=OPERATOR_HEADERS,
        json={"dailySendLimit": 3, "batchContents": [{"batchNo": 1, "cardId": "act-001"}]},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["dailySendLimit"] == 3
