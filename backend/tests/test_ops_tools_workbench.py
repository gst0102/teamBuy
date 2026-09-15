from __future__ import annotations

from app.api.dependencies import get_app_service
from app.core.config import settings
from app.models.domain import MutualHelpTask


def login(client, openid: str, nickname: str) -> dict:
    return client.post(
        "/api/auth/mock-login",
        json={"openid": openid, "nickname": nickname},
    ).json()["data"]


def test_tools_dashboard_and_mobile_tool_admins_are_admin_protected(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = login(client, "ops_tool_admin", "手机运营员")
    headers = {"X-Admin-Token": "ops-secret"}

    assert client.get("/api/ops-admin/tools-dashboard").status_code == 403
    dashboard = client.get("/api/ops-admin/tools-dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert set(dashboard.json()["data"]["periods"]) == {"today", "sevenDays", "total"}
    assert set(dashboard.json()["data"]["periods"]["today"]) == {"points", "mutualHelp", "groupResource", "businessOpportunity"}

    enabled = client.put(
        f"/api/ops-admin/mobile-tool-admins/{user['id']}",
        headers=headers,
        json={"tool": "business_opportunity", "enabled": True, "operatorName": "测试管理员"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["data"]["permissions"]["business_opportunity"] is True
    admins = client.get("/api/ops-admin/mobile-tool-admins", headers=headers)
    assert admins.status_code == 200
    assert admins.json()["data"][0]["id"] == user["id"]


def test_tool_records_can_mark_and_delete_explicit_test_tasks(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "ops_tool_test_owner", "测试任务发布者")
    service = client.app.dependency_overrides[get_app_service]()
    task = MutualHelpTask(
        id="mutual_task_ops_cleanup",
        ownerUserId=owner["id"],
        title="后台清理测试任务",
        acceptanceCriteriaBlocks=[{"type": "text", "text": "完成测试"}],
        rewardPoints=5,
        executorReward=4,
        isTest=True,
        createdAt="2026-09-04T08:00:00+08:00",
        updatedAt="2026-09-04T08:00:00+08:00",
    )
    state = service._load()
    state.mutual_help_tasks.append(task)
    service._save(state)
    headers = {"X-Admin-Token": "ops-secret"}

    records = client.get(
        "/api/ops-admin/tools-records",
        headers=headers,
        params={"tool": "mutual_help", "testOnly": "true"},
    )
    assert records.status_code == 200
    assert records.json()["data"]["items"][0]["id"] == task.id
    assert records.json()["data"]["items"][0]["isTest"] is True

    deleted = client.post(
        "/api/ops-admin/tools-records/bulk-action",
        headers=headers,
        json={
            "tool": "mutual_help",
            "recordIds": [task.id],
            "action": "delete",
            "testOnly": True,
            "operatorName": "测试管理员",
            "reason": "清理测试任务",
        },
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] == 1
    assert service.repo.get_mutual_help_task(task.id) is None

    hidden_task = task.model_copy(
        update={
            "id": "mutual_task_ops_archived",
            "title": "后台已删除任务",
            "status": "deleted",
        }
    )
    state = service._load()
    state.mutual_help_tasks.append(hidden_task)
    service._save(state)
    default_records = client.get(
        "/api/ops-admin/tools-records",
        headers=headers,
        params={"tool": "mutual_help", "testOnly": "true"},
    )
    assert default_records.status_code == 200
    assert hidden_task.id not in {item["id"] for item in default_records.json()["data"]["items"]}
    explicit_deleted_records = client.get(
        "/api/ops-admin/tools-records",
        headers=headers,
        params={"tool": "mutual_help", "status": "deleted", "testOnly": "true"},
    )
    assert explicit_deleted_records.status_code == 200
    assert hidden_task.id in {item["id"] for item in explicit_deleted_records.json()["data"]["items"]}


def test_admin_can_publish_a_platform_mutual_task_without_a_fake_owner(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    response = client.post(
        "/api/ops-admin/mutual-help/tasks",
        headers={"X-Admin-Token": "ops-secret"},
        json={
            "taskKind": "ordinary",
            "title": "平台体验任务",
            "description": "请体验后提交一句反馈",
            "acceptanceText": "提交体验反馈",
            "rewardPoints": 5,
            "executorReward": 4,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sourceType"] == "platform_admin"
    assert data["task"]["ownerUserId"] == "platform_admin"
    assert data["task"]["status"] == "published"


def test_formal_mutual_task_cannot_be_permanently_deleted_but_can_be_archived(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "ops_formal_task_owner", "正式任务发布者")
    service = client.app.dependency_overrides[get_app_service]()
    task = MutualHelpTask(
        id="mutual_task_formal_cleanup_guard",
        ownerUserId=owner["id"],
        title="正式任务不可误删",
        acceptanceCriteriaBlocks=[{"type": "text", "text": "完成测试"}],
        createdAt="2026-09-04T08:00:00+08:00",
        updatedAt="2026-09-04T08:00:00+08:00",
    )
    state = service._load()
    state.mutual_help_tasks.append(task)
    service._save(state)
    headers = {"X-Admin-Token": "ops-secret"}

    deleted = client.post(
        "/api/ops-admin/tools-records/bulk-action",
        headers=headers,
        json={"tool": "mutual_help", "recordIds": [task.id], "action": "delete", "testOnly": True},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] == 0
    assert deleted.json()["data"]["skipped"][0]["reason"] == "未标记为测试数据"

    archived = client.post(
        "/api/ops-admin/tools-records/bulk-action",
        headers=headers,
        json={"tool": "mutual_help", "recordIds": [task.id], "action": "archive"},
    )
    assert archived.status_code == 200
    assert archived.json()["data"]["updated"] == 1
    assert service.repo.get_mutual_help_task(task.id).status == "paused"


def test_test_group_with_view_ledger_is_safely_hidden_not_deleted(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "ops_group_cleanup_owner", "测试群发布者")
    viewer = login(client, "ops_group_cleanup_viewer", "测试群查看者")
    created = client.post(
        "/api/group-resources",
        json={
            "ownerUserId": owner["id"],
            "name": "有流水的测试群",
            "cityMode": "national",
            "cityLabel": "全国",
            "industry": "互助",
            "purpose": "找同行",
            "qrImageUrl": "/media/cleanup-test.png",
            "expiresInDays": 7,
        },
    )
    assert created.status_code == 200
    resource_id = created.json()["data"]["id"]
    service = client.app.dependency_overrides[get_app_service]()
    state = service._load()
    resource = next(item for item in state.group_resources if item.id == resource_id)
    resource.isTest = True
    service._save(state)

    viewed = client.post(
        f"/api/group-resources/{resource_id}/view",
        json={"userId": viewer["id"]},
    )
    assert viewed.status_code == 200

    cleaned = client.post(
        "/api/ops-admin/tools-records/bulk-action",
        headers={"X-Admin-Token": "ops-secret"},
        json={
            "tool": "group_resource",
            "recordIds": [resource_id],
            "action": "delete",
            "testOnly": True,
        },
    )
    assert cleaned.status_code == 200
    result = cleaned.json()["data"]
    assert result["deleted"] == 0
    assert result["archived"] == 1
    assert result["skipped"] == []
    assert service.repo.get_group_resource(resource_id).status == "deleted"
    assert client.get("/api/group-resources").json()["data"] == []
    assert client.get(f"/api/group-resources/mine?ownerUserId={owner['id']}").json()["data"] == []
