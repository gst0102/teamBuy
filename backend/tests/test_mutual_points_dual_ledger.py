from __future__ import annotations

from app.api.dependencies import get_ops_console_store
from app.core.config import settings


def login(client, openid: str, nickname: str) -> dict:
    response = client.post(
        "/api/auth/mock-login",
        json={"openid": openid, "nickname": nickname},
    )
    assert response.status_code == 200
    return response.json()["data"]


def recharge(client, user_id: str, transaction_id: str) -> None:
    order = client.post(
        "/api/scrm/mutual-help/recharge/orders",
        json={"userId": user_id, "points": 100},
    )
    assert order.status_code == 200
    confirmed = client.post(
        f"/api/scrm/mutual-help/recharge/orders/{order.json()['data']['order']['id']}/test-confirm",
        json={"transactionId": transaction_id},
    )
    assert confirmed.status_code == 200


def points(client, user_id: str) -> dict:
    response = client.get(f"/api/scrm/mutual-help?userId={user_id}")
    assert response.status_code == 200
    return response.json()["data"]["points"]


def test_recharge_point_task_reserves_budget_and_credits_executor(client):
    owner = login(client, "openid_dual_ledger_owner", "充值任务发布者")
    executor = login(client, "openid_dual_ledger_executor", "充值任务执行者")
    second_executor = login(client, "openid_dual_ledger_second_executor", "第二位执行者")
    recharge(client, owner["id"], "dual-ledger-recharge-1")

    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner["id"],
            "taskKind": "ordinary",
            "title": "充值积分奖励任务",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交完成说明"}],
            "rewardPointType": "reward",
            "rewardPoints": 10,
            "executorReward": 8,
            "remaining": 3,
        },
    )
    assert created.status_code == 200
    task = created.json()["data"]["task"]
    assert task["rewardPointType"] == "reward"
    assert task["rewardBudgetReserved"] == 30
    assert points(client, owner["id"]) == {"total": 170, "base": 100, "reward": 70}

    submitted = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
        json={"userId": executor["id"], "text": "已完成"},
    )
    assert submitted.status_code == 200
    submission = submitted.json()["data"]["submission"]
    assert submitted.json()["data"]["reward"]["pointType"] == "reward"
    # The full 30-point budget was reserved at publish time. A submission
    # moves 10 points from the task's reserved portion to used portion; the
    # available reward balance therefore remains 70.
    assert points(client, owner["id"])["reward"] == 70

    approved = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions/{submission['id']}/approve",
        json={"userId": owner["id"]},
    )
    assert approved.status_code == 200
    assert points(client, executor["id"]) == {"total": 108, "base": 100, "reward": 8}

    second_submitted = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
        json={"userId": second_executor["id"], "text": "已完成第二次"},
    )
    assert second_submitted.status_code == 200
    second_submission = second_submitted.json()["data"]["submission"]
    rejected = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions/{second_submission['id']}/reject",
        json={"userId": owner["id"], "reason": "请补充完成说明"},
    )
    assert rejected.status_code == 200
    assert points(client, owner["id"])["reward"] == 70


def test_platform_admin_reward_tasks_use_separate_budget(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "dual-ledger-ops-secret")
    headers = {"X-Admin-Token": "dual-ledger-ops-secret"}

    budget = client.post(
        "/api/ops-admin/mutual-help/platform-budget",
        headers=headers,
        json={"delta": 30, "reason": "平台任务测试预算"},
    )
    assert budget.status_code == 200
    assert budget.json()["data"]["budget"]["availablePoints"] == 30

    created = client.post(
        "/api/ops-admin/mutual-help/tasks",
        headers=headers,
        json={
            "taskKind": "ordinary",
            "title": "平台充值积分任务",
            "acceptanceText": "提交完成说明",
            "rewardPointType": "reward",
            "rewardPoints": 10,
            "executorReward": 8,
            "remaining": 2,
        },
    )
    assert created.status_code == 200
    task = created.json()["data"]["task"]
    assert task["ownerUserId"] == "platform_admin"
    assert task["rewardBudgetReserved"] == 20

    after_publish = client.get("/api/ops-admin/mutual-help", headers=headers)
    assert after_publish.status_code == 200
    assert after_publish.json()["data"]["platformRewardBudget"]["availablePoints"] == 10
    assert after_publish.json()["data"]["platformRewardBudget"]["reservedPoints"] == 20

    deleted = client.patch(
        f"/api/scrm/mutual-help/tasks/{task['id']}",
        json={"ownerUserId": "platform_admin", "status": "deleted"},
    )
    assert deleted.status_code == 200
    after_delete = client.get("/api/ops-admin/mutual-help", headers=headers)
    assert after_delete.json()["data"]["platformRewardBudget"]["availablePoints"] == 30
    assert after_delete.json()["data"]["platformRewardBudget"]["reservedPoints"] == 0


def test_recharge_point_withdrawal_is_pc_reviewed_and_failed_request_returns_points(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "withdrawal-ops-secret")
    headers = {"X-Admin-Token": "withdrawal-ops-secret"}
    ops_store = client.app.dependency_overrides[get_ops_console_store]()
    ops_store.set_mutual_help_config(withdrawal_enabled=True, withdrawal_visible=True, operator_name="test")

    user = login(client, "openid_withdrawal_manual_review", "提现审核用户")
    recharge(client, user["id"], "withdrawal-recharge-1")
    created = client.post(
        "/api/scrm/mutual-help/withdrawals",
        json={"userId": user["id"], "points": 100},
    )
    assert created.status_code == 200
    withdrawal = created.json()["data"]["withdrawal"]
    rules = created.json()["data"]["rules"]
    assert rules["minimumPoints"] == 100
    assert rules["pointsPerYuan"] == 10
    assert rules["feePercent"] == 20.0
    assert "PC 管理员审核" in rules["reviewTimeText"]
    assert "基础积分不可提现" in rules["accountScopeText"]
    assert withdrawal["grossAmountFen"] == 1000
    assert withdrawal["feeFen"] == 200
    assert withdrawal["amountFen"] == 800
    assert withdrawal["status"] == "pending"
    assert points(client, user["id"]) == {"total": 100, "base": 100, "reward": 0}

    pending = client.get("/api/ops-admin/mutual-help/withdrawals?status=pending", headers=headers)
    assert pending.status_code == 200
    assert pending.json()["data"]["items"][0]["id"] == withdrawal["id"]

    settled = client.post(
        f"/api/ops-admin/mutual-help/withdrawals/{withdrawal['id']}/settle",
        headers=headers,
        params={"reason": "测试人工确认到账"},
    )
    assert settled.status_code == 200
    assert settled.json()["data"]["withdrawal"]["status"] == "paid"

    second_user = login(client, "openid_withdrawal_cancel", "提现撤销用户")
    recharge(client, second_user["id"], "withdrawal-recharge-2")
    second = client.post(
        "/api/scrm/mutual-help/withdrawals",
        json={"userId": second_user["id"], "points": 100},
    )
    assert second.status_code == 200
    second_id = second.json()["data"]["withdrawal"]["id"]
    cancelled = client.post(
        f"/api/ops-admin/mutual-help/withdrawals/{second_id}/cancel",
        headers=headers,
        params={"reason": "测试撤销"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["withdrawal"]["status"] == "cancelled"
    assert points(client, second_user["id"]) == {"total": 200, "base": 100, "reward": 100}
