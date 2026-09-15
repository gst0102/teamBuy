from __future__ import annotations

from app.api.dependencies import get_app_service
from app.core.config import settings
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


def group_payload(user_id: str, name: str) -> dict:
    return {
        "ownerUserId": user_id,
        "name": name,
        "cityMode": "city",
        "cityLabel": "长沙市",
        "industry": "房产",
        "purpose": "找同行",
        "memberRange": "100-300",
        "activeLevel": "高",
        "qrImageUrl": f"/media/{name}.png",
        "expiresInDays": 7,
    }


def save_business_card(service, owner_id: str, title: str) -> str:
    note_id = new_id("pin_business")
    timestamp = now_iso()
    service.repo.save_user_note(UserNote(
        id=note_id,
        ownerUserId=owner_id,
        status="active",
        shareState="published",
        title=title,
        summary="提供外贸合作服务",
        body="合作介绍",
        createdAt=timestamp,
        updatedAt=timestamp,
        visibilityConfig={
            "cardType": "business_card",
            "structuredData": {
                "name": title,
                "headline": "提供外贸合作服务",
                "serviceKeywords": ["外贸服务"],
            },
            "businessOpportunity": {
                "enabled": True,
                "discoverable": True,
                "industry": "外贸",
                "subIndustry": "跨境电商",
            },
        },
    ))
    return note_id


def test_content_pinning_is_admin_only_and_reorders_all_three_public_lists(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "pin-ops-secret")
    owner_one = login(client, "openid_pin_owner_one", "置顶发布者一")
    owner_two = login(client, "openid_pin_owner_two", "置顶发布者二")
    viewer = login(client, "openid_pin_viewer", "置顶查看者")
    headers = {"X-Admin-Token": "pin-ops-secret"}

    first_task = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner_one["id"],
            "taskKind": "ordinary",
            "title": "普通排序任务",
            "description": "任务一",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交完成说明"}],
            "rewardPoints": 5,
            "executorReward": 4,
        },
    ).json()["data"]["task"]
    second_task = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner_two["id"],
            "taskKind": "ordinary",
            "title": "应该优先的任务",
            "description": "任务二",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交完成说明"}],
            "rewardPoints": 5,
            "executorReward": 4,
        },
    ).json()["data"]["task"]
    denied = client.put(
        f"/api/ops-admin/content-pins/mutual_help/{second_task['id']}",
        json={"pinned": True},
    )
    assert denied.status_code == 403
    pinned_task = client.put(
        f"/api/ops-admin/content-pins/mutual_help/{second_task['id']}",
        headers=headers,
        json={"pinned": True, "operatorName": "测试运营"},
    )
    assert pinned_task.status_code == 200
    assert pinned_task.json()["data"]["isPinned"] is True
    repeated_task = client.put(
        f"/api/ops-admin/content-pins/{'mutual_help'}/{second_task['id']}",
        headers=headers,
        json={"pinned": True},
    )
    assert repeated_task.json()["data"]["changed"] is False
    task_listing = client.get(
        "/api/scrm/mutual-help/tasks",
        params={"userId": viewer["id"], "cursor": "0", "limit": 50},
    )
    assert task_listing.status_code == 200
    assert [item["id"] for item in task_listing.json()["data"]["items"][:2]] == [second_task["id"], first_task["id"]]
    assert all(key not in task_listing.json()["data"]["items"][0] for key in ("isPinned", "pinnedAt", "pinnedBy"))

    first_group = client.post("/api/group-resources", json=group_payload(owner_one["id"], "普通群")).json()["data"]
    second_group = client.post("/api/group-resources", json=group_payload(owner_two["id"], "置顶群")).json()["data"]
    pinned_group = client.put(
        f"/api/ops-admin/content-pins/group_resource/{second_group['id']}",
        headers=headers,
        json={"pinned": True},
    )
    assert pinned_group.status_code == 200
    group_listing = client.get("/api/group-resources", params={"cursor": "0", "limit": 50})
    assert group_listing.status_code == 200
    assert [item["id"] for item in group_listing.json()["data"]["items"][:2]] == [second_group["id"], first_group["id"]]
    assert all(key not in group_listing.json()["data"]["items"][0] for key in ("isPinned", "pinnedAt", "pinnedBy"))

    service = client.app.dependency_overrides[get_app_service]()
    first_card_id = save_business_card(service, owner_one["id"], "普通合作名片")
    second_card_id = save_business_card(service, owner_two["id"], "置顶合作名片")
    pinned_card = client.put(
        f"/api/ops-admin/content-pins/business_opportunity/{second_card_id}",
        headers=headers,
        json={"pinned": True},
    )
    assert pinned_card.status_code == 200
    cards = client.get(
        "/api/business-opportunities/cards",
        params={"viewerUserId": viewer["id"], "mode": "capability", "cursor": "0", "limit": 20},
    )
    assert cards.status_code == 200
    assert [item["id"] for item in cards.json()["data"]["items"][:2]] == [second_card_id, first_card_id]
    assert all(key not in cards.json()["data"]["items"][0] for key in ("isPinned", "pinnedAt", "pinnedBy"))

    admin_items = client.get("/api/ops-admin/content-pins", headers=headers)
    assert admin_items.status_code == 200
    assert admin_items.json()["data"]["total"] >= 6
    assert any(item["targetId"] == second_card_id and item["isPinned"] for item in admin_items.json()["data"]["items"])

    service.repo.save_mutual_help_task(
        service.repo.get_mutual_help_task(second_task["id"]).model_copy(update={"status": "deleted"})
    )
    service.repo.save_group_resource(
        service.repo.get_group_resource(second_group["id"]).model_copy(update={"reviewStatus": "removed"})
    )
    cleaned_items = client.get("/api/ops-admin/content-pins", headers=headers)
    assert cleaned_items.status_code == 200
    cleaned_ids = {item["targetId"] for item in cleaned_items.json()["data"]["items"]}
    assert second_task["id"] not in cleaned_ids
    assert second_group["id"] not in cleaned_ids
    assert second_card_id in cleaned_ids


def test_content_pinning_validates_target_type_and_business_card_boundary(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "pin-ops-secret")
    owner = login(client, "openid_pin_boundary_owner", "置顶边界用户")
    service = client.app.dependency_overrides[get_app_service]()
    note_id = new_id("pin_plain_note")
    timestamp = now_iso()
    service.repo.save_user_note(UserNote(
        id=note_id,
        ownerUserId=owner["id"],
        status="active",
        shareState="published",
        title="普通资料",
        summary="不是合作名片",
        body="普通内容",
        createdAt=timestamp,
        updatedAt=timestamp,
    ))
    headers = {"X-Admin-Token": "pin-ops-secret"}
    invalid_type = client.put(
        f"/api/ops-admin/content-pins/not_supported/{note_id}",
        headers=headers,
        json={"pinned": True},
    )
    plain_note = client.put(
        f"/api/ops-admin/content-pins/business_opportunity/{note_id}",
        headers=headers,
        json={"pinned": True},
    )
    assert invalid_type.status_code == 400
    assert plain_note.status_code == 400
