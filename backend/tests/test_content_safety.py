from __future__ import annotations

import json

from app.core.config import settings
from app.services.content_safety_service import ContentSafetyService
from app.services.repository import JsonRepository


def test_content_safety_normalizes_text_and_hides_exact_match(tmp_path):
    service = ContentSafetyService(JsonRepository(tmp_path / "state.json"), cache_ttl_seconds=0)
    service.create_rule({
        "term": "违规词",
        "action": "block",
        "category": "custom_block",
        "scopes": ["user_note.body"],
    })

    result = service.assess(
        "user_note",
        "note-1",
        {"title": "普通标题", "body": "违\u200b规词"},
        owner_user_id="user-1",
        content_revision="1",
    )

    assert result.decision == "block"
    assert result.status == "blocked"
    assert result.public_payload()["fields"] == ["body"]
    assert "违规词" not in json.dumps(result.public_payload(), ensure_ascii=False)


def test_content_safety_manual_approval_survives_lifecycle_revision(tmp_path):
    service = ContentSafetyService(JsonRepository(tmp_path / "state.json"), cache_ttl_seconds=0)
    service.create_rule({"term": "待确认", "action": "review"})
    first = service.assess(
        "mutual_help_task",
        "task-1",
        {"title": "待确认任务"},
        owner_user_id="user-1",
        content_revision="created-at",
    )
    assert first.decision == "review"
    service.review_assessment(first.assessmentId, "approve", "ops", "人工确认")

    retried = service.assess(
        "mutual_help_task",
        "task-1",
        {"title": "待确认任务"},
        owner_user_id="user-1",
        content_revision="published-at",
    )
    assert retried.decision == "allow"
    assert retried.status == "overridden"


def test_content_safety_admin_rule_and_test_api(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "content-safety-secret")
    headers = {"X-Admin-Token": "content-safety-secret"}
    created = client.post(
        "/api/ops-admin/content-safety/rules",
        headers=headers,
        json={"term": "试测拦截", "action": "block", "category": "test"},
    )
    assert created.status_code == 200
    assert created.json()["data"]["action"] == "block"

    tested = client.post(
        "/api/ops-admin/content-safety/test",
        headers=headers,
        json={"contentType": "user_note", "fields": {"body": "试\u200b测拦截"}},
    )
    assert tested.status_code == 200
    assert tested.json()["data"]["code"] == "CONTENT_BLOCKED"
    assert "试测拦截" not in json.dumps(tested.json()["data"], ensure_ascii=False)

    denied = client.get("/api/ops-admin/content-safety/rules")
    assert denied.status_code == 403


def test_content_safety_blocks_capture_and_requires_review_before_task_publish(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "content-safety-workflow-secret")
    headers = {"X-Admin-Token": "content-safety-workflow-secret"}
    logged_in = client.post(
        "/api/auth/mock-login",
        json={"openid": "openid_content_safety_workflow", "nickname": "内容安全测试用户"},
    )
    assert logged_in.status_code == 200
    user_id = logged_in.json()["data"]["id"]

    created = client.post(
        "/api/ops-admin/content-safety/rules",
        headers=headers,
        json={"term": "禁止发布词", "action": "block", "category": "hard_block"},
    )
    assert created.status_code == 200
    blocked = client.post(
        "/api/notes/quick-capture",
        json={"ownerUserId": user_id, "rawText": "这是一段禁止发布词内容"},
    )
    assert blocked.status_code == 422
    assert blocked.json()["detail"]["code"] == "CONTENT_BLOCKED"

    review_rule = client.post(
        "/api/ops-admin/content-safety/rules",
        headers=headers,
        json={"term": "需要人工确认", "action": "review", "category": "manual_review"},
    )
    assert review_rule.status_code == 200
    created_task = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": user_id,
            "taskKind": "ordinary",
            "title": "需要人工确认任务",
            "description": "普通互助任务",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交完成说明"}],
            "rewardPoints": 5,
            "executorReward": 4,
        },
    )
    assert created_task.status_code == 200
    task = created_task.json()["data"]["task"]
    assert task["status"] == "pending_review"

    queue = client.get("/api/ops-admin/content-safety/queue", headers=headers, params={"status": "reviewing"})
    assert queue.status_code == 200
    assessment = next(item for item in queue.json()["data"]["items"] if item["targetId"] == task["id"])
    approved = client.post(
        f"/api/ops-admin/content-safety/queue/{assessment['id']}/review",
        headers=headers,
        json={"action": "approve", "operatorName": "测试运营"},
    )
    assert approved.status_code == 200
    published = client.patch(
        f"/api/scrm/mutual-help/tasks/{task['id']}",
        json={"ownerUserId": user_id, "status": "published"},
    )
    assert published.status_code == 200
    assert published.json()["data"]["task"]["status"] == "published"
