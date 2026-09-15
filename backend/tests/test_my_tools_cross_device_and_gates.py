from __future__ import annotations

from app.api.dependencies import get_app_service
from app.models.domain import UserNote
from app.services.helpers import new_id
from app.services.time_utils import now_iso


def login(client, openid: str, nickname: str) -> dict:
    response = client.post(
        "/api/auth/mock-login",
        json={"openid": openid, "nickname": nickname},
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_mutual_help_task_submission_and_settlement_are_server_backed(client):
    owner = login(client, "openid_cross_device_owner", "任务发布者")
    executor = login(client, "openid_cross_device_executor", "任务执行者")

    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner["id"],
            "taskKind": "ordinary",
            "title": "跨设备任务",
            "description": "服务端保存的任务",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交一段完成说明"}],
            "rewardPoints": 5,
            "executorReward": 4,
        },
    )
    assert created.status_code == 200
    task = created.json()["data"]["task"]

    opened = client.post(
        "/api/scrm/mutual-help/activity",
        json={
            "userId": executor["id"],
            "eventType": "opened",
            "taskId": task["id"],
            "linkId": "miniapp-entry",
            "sessionId": "session-1",
            "metadata": {"entryType": "miniapp"},
        },
    )
    returned = client.post(
        "/api/scrm/mutual-help/activity",
        json={
            "userId": executor["id"],
            "eventType": "returned",
            "taskId": task["id"],
            "linkId": "miniapp-entry",
            "sessionId": "session-1",
            "metadata": {"returnedAfterMs": "3200"},
        },
    )
    assert opened.status_code == 200
    assert returned.status_code == 200

    other_created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner["id"],
            "taskKind": "ordinary",
            "title": "另一项任务",
            "description": "不应混入当前任务统计",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交另一项任务说明"}],
            "rewardPoints": 5,
            "executorReward": 4,
        },
    )
    assert other_created.status_code == 200
    other_task = other_created.json()["data"]["task"]
    other_opened = client.post(
        "/api/scrm/mutual-help/activity",
        json={"userId": executor["id"], "eventType": "opened", "taskId": other_task["id"]},
    )
    assert other_opened.status_code == 200

    # A second request using the same openid-derived identity can read the
    # task and submit from another device/session; no localStorage state is
    # involved in the business result.
    detail = client.get(
        f"/api/scrm/mutual-help/tasks/{task['id']}?userId={executor['id']}"
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["task"]["id"] == task["id"]

    submitted = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
        json={"userId": executor["id"], "text": "已完成"},
    )
    assert submitted.status_code == 200
    submission = submitted.json()["data"]["submission"]
    assert submission["rewardSettled"] is False

    owner_detail = client.get(
        f"/api/scrm/mutual-help/tasks/{task['id']}?userId={owner['id']}"
    )
    assert owner_detail.status_code == 200
    assert owner_detail.json()["data"]["submissions"][0]["id"] == submission["id"]
    assert owner_detail.json()["data"]["submissions"][0]["statusLabel"] == "待验收"
    assert owner_detail.json()["data"]["submissions"][0]["executorLabel"] == "任务执行者"
    assert owner_detail.json()["data"]["activitySummary"] == {
        "participatedCount": 1,
        "submittedCount": 1,
        "acceptedCount": 0,
        "settledCount": 0,
    }

    approved = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions/{submission['id']}/approve",
        json={"userId": owner["id"]},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["settled"] is True

    owner_after_settlement = client.get(
        f"/api/scrm/mutual-help/tasks/{task['id']}?userId={owner['id']}"
    )
    assert owner_after_settlement.status_code == 200
    assert owner_after_settlement.json()["data"]["activitySummary"] == {
        "participatedCount": 1,
        "submittedCount": 1,
        "acceptedCount": 1,
        "settledCount": 1,
    }
    assert owner_after_settlement.json()["data"]["submissions"][0]["statusLabel"] == "已结算"

    owner_points = client.get(f"/api/scrm/mutual-help?userId={owner['id']}").json()["data"]["points"]
    executor_points = client.get(f"/api/scrm/mutual-help?userId={executor['id']}").json()["data"]["points"]
    assert owner_points == {"total": 95, "base": 95, "reward": 0}
    assert executor_points == {"total": 104, "base": 104, "reward": 0}


def test_mutual_help_comment_summary_and_completed_experience_marker_are_server_backed(client):
    owner = login(client, "openid_comment_owner", "评论任务发布者")
    early_worth_it = login(client, "openid_comment_worth_it", "先看评论用户")
    early_not_worth_it = login(client, "openid_comment_not_worth_it", "另一位评论用户")
    completed_user = login(client, "openid_comment_completed", "已完成用户")

    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner["id"],
            "taskKind": "ordinary",
            "title": "评论汇总任务",
            "description": "先看评论再决定是否参与",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交完成说明"}],
            "rewardPoints": 5,
            "executorReward": 4,
        },
    )
    assert created.status_code == 200
    task = created.json()["data"]["task"]

    early_attempt = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/comments",
        json={"userId": early_worth_it["id"], "recommendChoice": "worth_it", "text": "流程清楚"},
    )
    assert early_attempt.status_code == 403

    for executor in (early_worth_it, early_not_worth_it):
        submitted_for_comment = client.post(
            f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
            json={"userId": executor["id"], "text": "已完成任务"},
        )
        assert submitted_for_comment.status_code == 200

    worth_it = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/comments",
        json={"userId": early_worth_it["id"], "recommendChoice": "worth_it", "text": "流程清楚"},
    )
    not_worth_it = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/comments",
        json={"userId": early_not_worth_it["id"], "recommendChoice": "not_worth_it", "text": "暂时不适合我"},
    )
    assert worth_it.status_code == 200
    assert not_worth_it.status_code == 200
    assert worth_it.json()["data"]["comment"]["completed"] is True
    assert not_worth_it.json()["data"]["comment"]["completed"] is True

    submitted = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
        json={"userId": completed_user["id"], "text": "已完成任务"},
    )
    assert submitted.status_code == 200
    experienced = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/comments",
        json={"userId": completed_user["id"], "recommendChoice": "neutral", "text": "完成后再来反馈"},
    )
    assert experienced.status_code == 200
    assert experienced.json()["data"]["comment"]["completed"] is True

    listing = client.get(
        f"/api/scrm/mutual-help/tasks?userId={early_worth_it['id']}&limit=50"
    )
    assert listing.status_code == 200
    listed_task = next(item for item in listing.json()["data"]["items"] if item["id"] == task["id"])
    assert listed_task["commentSummary"] == {
        "count": 3,
        "worthIt": 1,
        "notWorthIt": 1,
        "neutral": 1,
        "recommendCount": 2,
        "worthItRate": 50,
        "worthItRateText": "50%觉得值得",
        "text": "评论 3 条 · 50%觉得值得",
    }

    detail = client.get(
        f"/api/scrm/mutual-help/tasks/{task['id']}?userId={early_worth_it['id']}"
    )
    assert detail.status_code == 200
    comments = detail.json()["data"]["comments"]
    assert len(comments) == 3
    assert all("authorId" not in comment for comment in comments)


def test_mutual_help_owner_can_execute_and_reservation_can_be_released(client):
    owner = login(client, "openid_mutual_self_executor", "自己执行任务用户")
    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner["id"],
            "taskKind": "ordinary",
            "title": "自己测试任务",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交测试结果"}],
            "rewardPoints": 5,
            "executorReward": 4,
        },
    )
    assert created.status_code == 200
    task = created.json()["data"]["task"]

    submitted = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
        json={"userId": owner["id"], "text": "我完成了自己的测试任务"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["data"]["submission"]["rewardSettled"] is False
    after_reserve = client.get(f"/api/scrm/mutual-help?userId={owner['id']}").json()["data"]["points"]
    assert after_reserve == {"total": 95, "base": 95, "reward": 0}

    comment = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/comments",
        json={"userId": owner["id"], "recommendChoice": "worth_it", "text": "自己完成后反馈"},
    )
    assert comment.status_code == 200

    submission_id = submitted.json()["data"]["submission"]["id"]
    rejected = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions/{submission_id}/reject",
        json={"userId": owner["id"], "reason": "测试退回后重新提交"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["data"]["submission"]["status"] == "rejected"
    after_release = client.get(f"/api/scrm/mutual-help?userId={owner['id']}").json()["data"]["points"]
    assert after_release == {"total": 100, "base": 100, "reward": 0}


def test_mutual_help_miniapp_submission_pays_base_points_immediately(client):
    owner = login(client, "openid_miniapp_instant_owner", "小程序任务发布者")
    executor = login(client, "openid_miniapp_instant_executor", "小程序任务执行者")
    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner["id"],
            "taskKind": "miniapp",
            "title": "点击体验小程序",
            "taskLinks": [{"type": "miniapp", "shortLink": "#小程序://测试/入口"}],
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "返回后提交完成记录"}],
        },
    )
    assert created.status_code == 200
    task = created.json()["data"]["task"]

    submitted = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
        json={"userId": executor["id"], "text": "已点击体验"},
    )
    assert submitted.status_code == 200
    data = submitted.json()["data"]
    assert data["settled"] is True
    assert data["reward"] == {"points": 4, "pointType": "base", "status": "credited", "autoApproveAt": data["submission"]["reviewDeadlineAt"]}
    assert data["submission"]["status"] == "completed"
    assert client.get(f"/api/scrm/mutual-help?userId={executor['id']}").json()["data"]["points"] == {"total": 104, "base": 104, "reward": 0}


def test_mutual_help_daily_repeat_policy_resets_by_shanghai_day(client):
    owner = login(client, "openid_daily_repeat_owner", "按天任务发布者")
    executor = login(client, "openid_daily_repeat_executor", "按天任务执行者")
    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner["id"],
            "taskKind": "miniapp",
            "title": "每天可体验一次的小程序",
            "repeatPolicy": "daily",
            "taskLinks": [{"type": "miniapp", "shortLink": "#小程序://按天任务/入口"}],
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "返回后提交体验记录"}],
        },
    )
    assert created.status_code == 200
    task = created.json()["data"]["task"]
    assert task["repeatPolicy"] == "daily"

    first = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
        json={"userId": executor["id"], "text": "今天完成第一次体验"},
    )
    assert first.status_code == 200
    assert first.json()["data"]["duplicate"] is False
    assert first.json()["data"]["submission"]["participationDay"]

    same_day = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
        json={"userId": executor["id"], "text": "同一天不应重复结算"},
    )
    assert same_day.status_code == 200
    assert same_day.json()["data"]["duplicate"] is True

    # Move the stored participation to an earlier calendar day to exercise
    # the same server-side path that a real midnight reset uses.
    service = client.app.dependency_overrides[get_app_service]()
    stored = service.repo.get_mutual_help_submission(first.json()["data"]["submission"]["id"])
    assert stored is not None
    service.repo.save_mutual_help_submission(stored.model_copy(update={"participationDay": "2000-01-01"}))

    next_day = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
        json={"userId": executor["id"], "text": "新的一天再次体验"},
    )
    assert next_day.status_code == 200
    assert next_day.json()["data"]["duplicate"] is False

    listing = client.get(f"/api/scrm/mutual-help/tasks?userId={executor['id']}&limit=50")
    assert listing.status_code == 200
    listed_task = next(item for item in listing.json()["data"]["items"] if item["id"] == task["id"])
    assert listed_task["viewerState"]["repeatPolicy"] == "daily"
    assert listed_task["viewerState"]["completedToday"] is True


def test_mutual_help_reserved_cost_can_settle_when_balance_is_fully_reserved(client):
    owner = login(client, "openid_mutual_full_reserve_owner", "预留全部余额发布者")
    executor = login(client, "openid_mutual_full_reserve_executor", "预留全部余额执行者")
    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner["id"],
            "taskKind": "ordinary",
            "title": "预留全部余额任务",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交结果"}],
            "rewardPoints": 100,
            "executorReward": 1,
        },
    )
    assert created.status_code == 200
    task = created.json()["data"]["task"]

    submitted = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions",
        json={"userId": executor["id"], "text": "已完成"},
    )
    assert submitted.status_code == 200
    assert client.get(f"/api/scrm/mutual-help?userId={owner['id']}").json()["data"]["points"] == {"total": 0, "base": 0, "reward": 0}

    approved = client.post(
        f"/api/scrm/mutual-help/tasks/{task['id']}/submissions/{submitted.json()['data']['submission']['id']}/approve",
        json={"userId": owner["id"]},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["submission"]["rewardSettled"] is True
    assert client.get(f"/api/scrm/mutual-help?userId={executor['id']}").json()["data"]["points"] == {"total": 101, "base": 101, "reward": 0}


def test_business_market_contact_gate_applies_to_public_page_and_unlock_is_reused(client):
    owner = login(client, "openid_business_gate_owner", "名片发布者")
    viewer = login(client, "openid_business_gate_viewer", "名片查看者")
    profile = client.patch(
        f"/api/auth/users/{owner['id']}/profile",
        json={"phone": "15100001111", "wechat": "business_owner"},
    )
    assert profile.status_code == 200

    # Use the fixture's service through the normal dependency override without
    # relying on a second app or a client-local cache.
    from app.api.dependencies import get_app_service

    service = client.app.dependency_overrides[get_app_service]()
    timestamp = now_iso()
    note = UserNote(
        id=new_id("business_gate_note"),
        ownerUserId=owner["id"],
        status="active",
        shareState="published",
        revision=3,
        title="名片发布者的电子名片",
        summary="外贸合作",
        body="欢迎联系名片发布者，电话 15100001111。",
        createdAt=timestamp,
        updatedAt=timestamp,
        visibilityConfig={
            "schemaVersion": 2,
            "cardType": "business_card",
            "structuredData": {
                "name": "名片发布者",
                "headline": "外贸合作",
                "serviceKeywords": ["外贸服务"],
                "bio": "欢迎合作，微信 business_owner",
                "phone": "15100001111",
                "wechat": "business_owner",
            },
            "businessOpportunity": {
                "enabled": True,
                "discoverable": True,
                "industry": "外贸",
                "subIndustry": "跨境电商",
            },
        },
    )
    service.repo.save_user_note(note)

    public_preview = client.get(
        f"/api/notes/public/{note.id}?viewerUserId={viewer['id']}"
    )
    assert public_preview.status_code == 200
    public_data = public_preview.json()["data"]
    assert public_data["businessCardContactLocked"] is True
    assert public_data["ownerProfile"]["phone"] == ""
    assert "15100001111" not in public_data["body"]
    assert "business_owner" not in public_data["visibilityConfig"]["structuredData"]["bio"]
    assert public_data["visibilityConfig"].get("shareSnapshot") is None

    locked = client.get(
        f"/api/business-opportunities/cards/{note.id}?viewerUserId={viewer['id']}"
    )
    assert locked.status_code == 200
    assert locked.json()["data"]["contactLocked"] is True
    assert locked.json()["data"]["contacts"] == []
    assert "business_owner" not in locked.json()["data"]["bio"]

    unlocked = client.post(
        f"/api/business-opportunities/cards/{note.id}/unlock",
        json={"userId": viewer["id"]},
    )
    assert unlocked.status_code == 200
    assert unlocked.json()["data"]["card"]["contacts"][0]["contactValue"] == "15100001111"

    reopened = client.get(
        f"/api/business-opportunities/cards/{note.id}?viewerUserId={viewer['id']}"
    )
    assert reopened.status_code == 200
    assert reopened.json()["data"]["contactLocked"] is False
    assert reopened.json()["data"]["contacts"]

    public_after_unlock = client.get(
        f"/api/notes/public/{note.id}?viewerUserId={viewer['id']}"
    ).json()["data"]
    assert public_after_unlock["businessCardContactLocked"] is False
    assert public_after_unlock["ownerProfile"]["phone"] == "15100001111"

    report = client.post(
        f"/api/business-opportunities/cards/{note.id}/contact-reports",
        json={"userId": viewer["id"], "reason": "联系方式失效"},
    )
    duplicate = client.post(
        f"/api/business-opportunities/cards/{note.id}/contact-reports",
        json={"userId": viewer["id"], "reason": "重复反馈"},
    )
    assert report.status_code == 200
    assert report.json()["data"]["contactInvalidReportCount"] == 1
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True


def test_business_card_resource_and_intent_publication_are_independent(client):
    owner = login(client, "openid_business_scoped_owner", "独立公开用户")
    viewer = login(client, "openid_business_scoped_viewer", "合作查看者")
    timestamp = now_iso()

    def save_card(note_id, *, resource_enabled, intent_enabled, intent_text=""):
        service = client.app.dependency_overrides[get_app_service]()
        service.repo.save_user_note(UserNote(
            id=note_id,
            ownerUserId=owner["id"],
            status="active",
            shareState="published",
            title=note_id,
            summary="可公开的合作名片",
            body="合作介绍",
            createdAt=timestamp,
            updatedAt=timestamp,
            visibilityConfig={
                "cardType": "business_card",
                "structuredData": {
                    "name": note_id,
                    "headline": "提供专业服务",
                    "serviceKeywords": ["专业服务"],
                    "cooperationIntent": {"direction": "我正在找合作", "text": intent_text},
                },
                "businessOpportunity": {
                    "resourceEnabled": resource_enabled,
                    "resourceDiscoverable": resource_enabled,
                    "intentEnabled": intent_enabled,
                    "intentDiscoverable": intent_enabled,
                    "industry": "企业服务",
                    "cooperationIntent": {"direction": "我正在找合作", "text": intent_text},
                },
            },
        ))

    save_card("scoped_resource_only", resource_enabled=True, intent_enabled=False, intent_text="不应出现在需求列表")
    save_card("scoped_intent_only", resource_enabled=False, intent_enabled=True, intent_text="寻找互补合作伙伴")
    save_card("scoped_private", resource_enabled=False, intent_enabled=False, intent_text="不应公开")

    capability = client.get(
        "/api/business-opportunities/cards",
        params={"mode": "capability", "viewerUserId": viewer["id"], "limit": 20},
    )
    intent = client.get(
        "/api/business-opportunities/cards",
        params={"mode": "intent", "viewerUserId": viewer["id"], "limit": 20},
    )
    assert capability.status_code == 200
    assert intent.status_code == 200
    assert [item["id"] for item in capability.json()["data"]["items"]] == ["scoped_resource_only"]
    assert [item["id"] for item in intent.json()["data"]["items"]] == ["scoped_intent_only"]
    assert capability.json()["data"]["items"][0]["cooperationIntent"]["text"] == ""
    resource_detail = client.get("/api/business-opportunities/cards/scoped_resource_only")
    assert resource_detail.status_code == 200
    assert resource_detail.json()["data"]["cooperationIntent"]["text"] == ""
    assert client.get("/api/business-opportunities/cards/scoped_private").status_code == 404


def test_group_resource_catalogue_returns_pages_for_lazy_loading(client):
    owners = [login(client, f"openid_group_page_{index}", f"群发布者{index}") for index in range(3)]
    for index, owner in enumerate(owners):
        response = client.post(
            "/api/group-resources",
            json={
                "ownerUserId": owner["id"],
                "name": f"分页群{index}",
                "cityMode": "city",
                "cityLabel": "长沙市",
                "industry": "电商",
                "purpose": "找合作",
                "qrImageUrl": "/media/group-page.png",
                "expiresInDays": 7,
            },
        )
        assert response.status_code == 200

    first = client.get("/api/group-resources?cursor=0&limit=2")
    assert first.status_code == 200
    first_data = first.json()["data"]
    assert len(first_data["items"]) == 2
    assert first_data["hasMore"] is True

    second = client.get(
        f"/api/group-resources?cursor={first_data['nextCursor']}&limit=2"
    )
    assert second.status_code == 200
    second_data = second.json()["data"]
    assert len(second_data["items"]) == 1
    assert second_data["hasMore"] is False
