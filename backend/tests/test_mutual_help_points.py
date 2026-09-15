from __future__ import annotations

from app.api.dependencies import get_app_service
from app.core.config import settings


def login(client, openid: str):
    return client.post(
        "/api/auth/mock-login",
        json={"openid": openid, "nickname": "互助积分测试用户"},
    ).json()["data"]


def test_mutual_help_initial_points_recharge_and_admin_switches(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "mutual-ops-secret")
    user = login(client, "openid_mutual_points_user")

    initial = client.get(f"/api/scrm/mutual-help?userId={user['id']}")
    assert initial.status_code == 200
    assert initial.json()["data"]["account"]["balance"] == 100
    assert initial.json()["data"]["points"] == {"total": 100, "base": 100, "reward": 0}
    assert initial.json()["data"]["accounts"]["base"]["pointType"] == "base"
    assert initial.json()["data"]["accounts"]["reward"]["pointType"] == "reward"
    assert initial.json()["data"]["recentLedgers"][0]["ledgerType"] == "initial_grant"
    assert initial.json()["data"]["recentLedgers"][0]["accountType"] == "mutual_help"
    assert initial.json()["data"]["config"]["rechargeEnabled"] is True
    assert initial.json()["data"]["config"]["withdrawalEnabled"] is False

    order = client.post(
        "/api/scrm/mutual-help/recharge/orders",
        json={"userId": user["id"], "points": 100},
    )
    assert order.status_code == 200
    assert order.json()["data"]["testMode"] is True

    confirmed = client.post(
        f"/api/scrm/mutual-help/recharge/orders/{order.json()['data']['order']['id']}/test-confirm",
        json={"transactionId": "mutual-test-transaction-1"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["account"]["balance"] == 200
    assert confirmed.json()["data"]["points"] == {"total": 200, "base": 100, "reward": 100}
    assert confirmed.json()["data"]["accounts"]["reward"]["balance"] == 100
    assert confirmed.json()["data"]["ledger"]["idempotencyKey"] == f"recharge:{order.json()['data']['order']['id']}"
    assert confirmed.json()["data"]["ledger"]["pointType"] == "reward"
    assert confirmed.json()["data"]["ledger"]["sourceType"] == "mutual_recharge_order"

    duplicate = client.post(
        f"/api/scrm/mutual-help/recharge/orders/{order.json()['data']['order']['id']}/test-confirm",
        json={"transactionId": "mutual-test-transaction-1"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True

    ledger = client.get(f"/api/scrm/mutual-help/ledger?userId={user['id']}&limit=10")
    assert ledger.status_code == 200
    assert [item["ledgerType"] for item in ledger.json()["data"][:2]] == ["recharge", "initial_grant"]
    reward_ledger = client.get(f"/api/scrm/mutual-help/ledger?userId={user['id']}&pointType=reward&limit=10")
    assert reward_ledger.status_code == 200
    assert reward_ledger.json()["data"][0]["pointType"] == "reward"

    assert client.post(
        "/api/scrm/mutual-help/activity",
        json={"userId": user["id"], "eventType": "published", "taskId": "task-1"},
    ).status_code == 200
    assert client.post(
        "/api/scrm/mutual-help/activity",
        json={"userId": user["id"], "eventType": "completed", "taskId": "task-2"},
    ).status_code == 200

    headers = {"X-Admin-Token": "mutual-ops-secret"}
    operations = client.get("/api/ops-admin/mutual-help", headers=headers)
    assert operations.status_code == 200
    periods = operations.json()["data"]["periods"]
    assert periods["today"]["publishedTasks"] == 1
    assert periods["today"]["completedTasks"] == 1
    assert periods["today"]["rechargeOrders"] == 1
    assert periods["today"]["rechargePoints"] == 100

    updated = client.put(
        "/api/ops-admin/mutual-help",
        headers=headers,
        json={"rechargeVisible": False, "withdrawalVisible": True},
    )
    assert updated.status_code == 200
    config = updated.json()["data"]
    assert config["rechargeVisible"] is False
    assert config["withdrawalVisible"] is True

    public_after_update = client.get(f"/api/scrm/mutual-help?userId={user['id']}")
    assert public_after_update.json()["data"]["config"]["rechargeVisible"] is False
    assert public_after_update.json()["data"]["config"]["withdrawalVisible"] is True


def test_mutual_help_recharge_can_be_closed_at_backend(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "mutual-ops-secret")
    user = login(client, "openid_mutual_points_closed_user")
    headers = {"X-Admin-Token": "mutual-ops-secret"}

    response = client.put(
        "/api/ops-admin/mutual-help",
        headers=headers,
        json={"rechargeEnabled": False},
    )
    assert response.status_code == 200

    blocked = client.post(
        "/api/scrm/mutual-help/recharge/orders",
        json={"userId": user["id"], "points": 100},
    )
    assert blocked.status_code == 403


def test_mutual_help_non_wool_task_accepts_empty_wool_policy_object(client):
    user = login(client, "openid_mutual_help_empty_wool_policy")
    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": user["id"],
            "taskKind": "miniapp",
            "title": "普通小程序任务",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交体验反馈"}],
            "taskLinks": [{"type": "miniapp", "shortLink": "#小程序://示例/入口"}],
            "rewardPoints": 5,
            "executorReward": 4,
            "woolPolicy": {},
        },
    )
    assert created.status_code == 200
    assert created.json()["data"]["task"]["woolPolicy"] == {}


def test_mutual_help_task_share_falls_back_when_content_image_is_external(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_storage_dir", tmp_path / "media")
    user = login(client, "openid_mutual_task_external_image")
    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": user["id"],
            "taskKind": "ordinary",
            "title": "关注公众号即可",
            "description": "关注公众号截图即可",
            "contentBlocks": [{"type": "image", "url": "https://mp.weixin.qq.com/s/example-image"}],
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交关注截图"}],
            "rewardPoints": 5,
            "executorReward": 4,
            "taskLinks": [{"type": "web", "url": "https://mp.weixin.qq.com/s/example-article"}],
        },
    )
    assert created.status_code == 200
    task = created.json()["data"]["task"]

    snapshot = client.get(
        f"/api/scrm/mutual-help/tasks/{task['id']}/share-snapshot"
        "?styleId=mutual_task_backend_v5"
    )

    assert snapshot.status_code == 200
    assert snapshot.json()["data"]["snapshot"]["status"] == "ready"
    assert snapshot.json()["data"]["snapshot"]["url"]


def test_mutual_help_task_share_falls_back_when_acceptance_image_is_temporary(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_storage_dir", tmp_path / "media")
    user = login(client, "openid_mutual_task_temporary_acceptance_image")
    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": user["id"],
            "taskKind": "ordinary",
            "title": "打卡公众号",
            "description": "关注即可",
            "contentBlocks": [],
            "acceptanceCriteriaBlocks": [{"type": "image", "url": "wxfile://tmp_CnHKKm.jpg"}],
            "rewardPoints": 5,
            "executorReward": 4,
            "taskLinks": [{"type": "web", "url": "https://mp.weixin.qq.com/s/example-article"}],
        },
    )
    assert created.status_code == 200
    task = created.json()["data"]["task"]

    snapshot = client.get(
        f"/api/scrm/mutual-help/tasks/{task['id']}/share-snapshot"
        "?styleId=mutual_task_backend_v5"
    )

    assert snapshot.status_code == 200
    assert snapshot.json()["data"]["snapshot"]["status"] == "ready"
    assert snapshot.json()["data"]["snapshot"]["url"]


def test_mutual_help_status_read_does_not_write_a_full_stale_snapshot(client, monkeypatch):
    user = login(client, "openid_mutual_points_no_snapshot_write")
    service = client.app.dependency_overrides[get_app_service]()
    service.get_mutual_help_status(user["id"])

    def fail_full_state_save(_state):
        raise AssertionError("mutual-help status reads must not save the full application snapshot")

    monkeypatch.setattr(service, "_save", fail_full_state_save)
    status = service.get_mutual_help_status(user["id"])
    assert status["account"]["balance"] == 100


def test_legacy_mixed_points_are_split_without_inventing_reward_points(tmp_path):
    import json

    from app.services.repository import JsonRepository

    data_file = tmp_path / "legacy-runtime.json"
    data_file.write_text(json.dumps({
        "mutual_point_accounts": [{
            "id": "mutual_help_points_user-legacy",
            "userId": "user-legacy",
            "accountType": "mutual_help",
            "balance": 195,
            "totalGranted": 200,
            "totalConsumed": 5,
            "createdAt": "2026-08-01T00:00:00+08:00",
            "updatedAt": "2026-08-02T00:00:00+08:00",
        }],
        "mutual_point_ledgers": [
            {
                "id": "legacy-initial",
                "userId": "user-legacy",
                "accountType": "mutual_help",
                "ledgerType": "initial_grant",
                "pointsDelta": 100,
                "balanceAfter": 100,
                "reason": "首次进入互帮互助赠送积分",
                "idempotencyKey": "initial:mutual_help:user-legacy",
                "sourceType": "system",
                "sourceId": "mutual_help_points_user-legacy",
                "metadata": {},
                "createdAt": "2026-08-01T00:00:00+08:00",
            },
            {
                "id": "legacy-recharge",
                "userId": "user-legacy",
                "accountType": "mutual_help",
                "ledgerType": "recharge",
                "pointsDelta": 100,
                "balanceAfter": 200,
                "reason": "旧积分入账",
                "idempotencyKey": "recharge:legacy-order",
                "sourceType": "mutual_recharge_order",
                "sourceId": "legacy-order",
                "metadata": {},
                "createdAt": "2026-08-01T01:00:00+08:00",
            },
            {
                "id": "legacy-consume",
                "userId": "user-legacy",
                "accountType": "mutual_help",
                "ledgerType": "consume",
                "pointsDelta": -5,
                "balanceAfter": 195,
                "reason": "旧任务消耗",
                "idempotencyKey": "consume:legacy-task",
                "sourceType": "mutual_task",
                "sourceId": "legacy-task",
                "metadata": {},
                "createdAt": "2026-08-02T00:00:00+08:00",
            },
        ],
    }, ensure_ascii=False), encoding="utf-8")

    repository = JsonRepository(data_file)
    state = repository.load()
    accounts = {(item.pointType, item.balance) for item in state.mutual_point_accounts}
    assert ("base", 95) in accounts
    assert ("reward", 100) in accounts
    assert next(item for item in state.mutual_point_ledgers if item.id == "legacy-recharge").pointType == "reward"
    assert next(item for item in state.mutual_point_ledgers if item.id == "legacy-consume").pointType == "base"

    repository.save(state)
    reloaded = repository.load()
    assert {(item.pointType, item.balance) for item in reloaded.mutual_point_accounts} == {("base", 95), ("reward", 100)}


def test_platform_rewards_are_migrated_to_base_once(client):
    user = login(client, "openid_platform_reward_migration")
    service = client.app.dependency_overrides[get_app_service]()
    state = service._load()
    reward = service._ensure_points_account_persisted(
        state,
        user["id"],
        point_type="reward",
        initial_points=0,
        initial_reason="历史充值积分账户初始化",
    )
    service.points_core.grant(
        state,
        user["id"],
        20,
        ledger_type="group_resource_publish_reward",
        reason="旧发布奖励",
        idempotency_key="legacy-group-reward-20",
        point_type="reward",
        source_type="group_resource",
        source_id="legacy-group",
    )
    service._save(state)

    first = client.get(f"/api/scrm/mutual-help?userId={user['id']}").json()["data"]
    second = client.get(f"/api/scrm/mutual-help?userId={user['id']}").json()["data"]
    assert first["points"] == {"total": 120, "base": 120, "reward": 0}
    assert second["points"] == first["points"]
    assert not any(item["sourceType"] == "points_account_migration" for item in first["recentLedgers"])


def test_platform_reward_migration_does_not_move_recharge_points(client):
    user = login(client, "openid_platform_reward_recharge_boundary")
    service = client.app.dependency_overrides[get_app_service]()
    state = service._load()
    service._ensure_mutual_point_accounts(state, user["id"])
    service.points_core.grant(
        state,
        user["id"],
        100,
        ledger_type="recharge",
        reason="历史充值积分",
        idempotency_key="legacy-recharge-boundary",
        point_type="reward",
        source_type="mutual_recharge_order",
        source_id="legacy-recharge-boundary-order",
    )
    service.points_core.grant(
        state,
        user["id"],
        20,
        ledger_type="task_reward",
        reason="历史平台任务奖励",
        idempotency_key="legacy-platform-boundary-grant",
        point_type="reward",
        source_type="mutual_task",
        source_id="legacy-platform-boundary-task",
    )
    service.points_core.consume(
        state,
        user["id"],
        10,
        ledger_type="task_settlement_cost",
        reason="历史平台任务扣除",
        idempotency_key="legacy-platform-boundary-spend",
        point_type="reward",
        source_type="mutual_task",
        source_id="legacy-platform-boundary-task",
    )
    service._save(state)

    status = client.get(f"/api/scrm/mutual-help?userId={user['id']}").json()["data"]
    assert status["points"] == {"total": 210, "base": 110, "reward": 100}


def test_legacy_resource_wallet_merges_without_duplicate_initial_grant(client):
    user = login(client, "openid_resource_wallet_migration")
    service = client.app.dependency_overrides[get_app_service]()
    wallet = service._ensure_resource_wallet(user["id"])
    wallet.balance = 130
    service.repo.save_resource_wallet(wallet)

    status = client.get(f"/api/scrm/mutual-help?userId={user['id']}").json()["data"]
    projected = client.get("/api/resource-wallet/me", params={"ownerUserId": user["id"]}).json()["data"]["wallet"]
    assert status["points"] == {"total": 130, "base": 130, "reward": 0}
    assert projected["balance"] == 130


def test_shared_consumption_uses_base_before_recharge_points(client):
    user = login(client, "openid_shared_spend_priority")
    order = client.post(
        "/api/scrm/mutual-help/recharge/orders",
        json={"userId": user["id"], "points": 100},
    ).json()["data"]["order"]
    assert client.post(
        f"/api/scrm/mutual-help/recharge/orders/{order['id']}/test-confirm",
        json={"transactionId": "shared-spend-priority"},
    ).status_code == 200

    consumed = client.post(
        "/api/resource-wallet/consume",
        json={
            "ownerUserId": user["id"],
            "actionType": "business_card_contact_unlock",
            "targetType": "business_card",
            "targetId": "shared-spend-card",
            "pointsCost": 105,
        },
    )
    assert consumed.status_code == 200
    assert consumed.json()["data"]["wallet"]["balance"] == 95
    status = client.get(f"/api/scrm/mutual-help?userId={user['id']}").json()["data"]
    assert status["points"] == {"total": 95, "base": 0, "reward": 95}
