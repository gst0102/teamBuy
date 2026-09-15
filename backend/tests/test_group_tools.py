from __future__ import annotations

from io import BytesIO

import qrcode
import cv2
import numpy as np
from PIL import Image, ImageDraw
from app.core.config import settings


def login(client, nickname: str) -> dict:
    response = client.post(
        "/api/auth/mock-login",
        json={"nickname": nickname, "openid": f"openid_{nickname}"},
    )
    assert response.status_code == 200
    return response.json()["data"]


def group_payload(user_id: str, name: str = "长沙房产群", tags: list[str] | None = None) -> dict:
    return {
        "ownerUserId": user_id,
        "name": name,
        "cityMode": "city",
        "cityLabel": "长沙市",
        "industry": "房产",
        "purpose": "找同行",
        "tags": tags or [],
        "memberRange": "100-300",
        "activeLevel": "高",
        "qrImageUrl": "/media/group-test.png",
        "expiresInDays": 7,
    }


def qr_bytes(target: str) -> bytes:
    output = BytesIO()
    qrcode.make(target).save(output, format="PNG")
    return output.getvalue()


def styled_qr_bytes(target: str) -> bytes:
    qr = qrcode.make(target).convert("RGB").resize((420, 420))
    poster = Image.new("RGB", (700, 900), "#eef8f1")
    draw = ImageDraw.Draw(poster)
    draw.rectangle((70, 70, 630, 830), fill="#ffffff", outline="#c5e7cf", width=4)
    draw.text((95, 105), "群聊：Python 资料", fill="#172033")
    poster.paste(qr, (140, 260))
    output = BytesIO()
    poster.save(output, format="PNG")
    return output.getvalue()


def test_group_resource_public_and_mine_are_separate_with_idempotent_view(client):
    owner = login(client, "群主")
    viewer = login(client, "查看者")

    created = client.post("/api/group-resources", json=group_payload(owner["id"]))
    assert created.status_code == 200
    resource = created.json()["data"]
    assert resource["rewardState"] == "pending"
    assert resource["rewardAmount"] == 10

    public = client.get("/api/group-resources")
    assert public.status_code == 200
    assert public.json()["data"][0]["id"] == resource["id"]
    assert public.json()["data"][0]["statusText"] == "审核中"
    assert public.json()["data"][0]["qrImageUrl"] == ""
    assert client.get("/api/group-resources?cityLabel=长沙市&industry=房产&purpose=找同行").json()["data"][0]["id"] == resource["id"]
    assert client.get("/api/group-resources?industry=招聘").json()["data"] == []

    mine = client.get(f"/api/group-resources/mine?ownerUserId={owner['id']}")
    other_mine = client.get(f"/api/group-resources/mine?ownerUserId={viewer['id']}")
    assert mine.json()["data"][0]["id"] == resource["id"]
    assert other_mine.json()["data"] == []

    first_view = client.post(
        f"/api/group-resources/{resource['id']}/view",
        json={"userId": viewer["id"]},
    )
    second_view = client.post(
        f"/api/group-resources/{resource['id']}/view",
        json={"userId": viewer["id"]},
    )
    assert first_view.status_code == 200
    assert first_view.json()["data"]["charged"] is True
    assert first_view.json()["data"]["account"]["balance"] == 85
    assert first_view.json()["data"]["points"] == {"total": 85, "base": 85, "reward": 0}
    assert second_view.status_code == 200
    assert second_view.json()["data"]["charged"] is False
    assert second_view.json()["data"]["account"]["balance"] == 85

    updated = client.patch(
        f"/api/group-resources/{resource['id']}",
        json={"ownerUserId": owner["id"], "qrImageUrl": "/media/group-test-v2.png"},
    )
    assert updated.status_code == 200
    next_version_view = client.post(
        f"/api/group-resources/{resource['id']}/view",
        json={"userId": viewer["id"]},
    )
    assert next_version_view.status_code == 200
    assert next_version_view.json()["data"]["charged"] is True
    assert next_version_view.json()["data"]["account"]["balance"] == 70


def test_group_resource_daily_limit_and_owner_only_update_delete(client):
    owner = login(client, "发布者")
    other = login(client, "其他用户")
    created = client.post("/api/group-resources", json=group_payload(owner["id"]))
    resource_id = created.json()["data"]["id"]

    quota_after_publish = client.get(f"/api/group-resources/publish-quota?ownerUserId={owner['id']}")
    assert quota_after_publish.status_code == 200
    assert quota_after_publish.json()["data"]["usedToday"] == 1
    assert quota_after_publish.json()["data"]["remainingToday"] == 0

    daily_limit = client.post("/api/group-resources", json=group_payload(owner["id"], "第二个群"))
    assert daily_limit.status_code == 409

    forbidden_update = client.patch(
        f"/api/group-resources/{resource_id}",
        json={"ownerUserId": other["id"], "qrImageUrl": "/media/other.png"},
    )
    forbidden_delete = client.delete(
        f"/api/group-resources/{resource_id}?ownerUserId={other['id']}"
    )
    assert forbidden_update.status_code == 403
    assert forbidden_delete.status_code == 403

    deleted = client.delete(f"/api/group-resources/{resource_id}?ownerUserId={owner['id']}")
    assert deleted.status_code == 200
    quota_after_delete = client.get(f"/api/group-resources/publish-quota?ownerUserId={owner['id']}")
    assert quota_after_delete.status_code == 200
    assert quota_after_delete.json()["data"]["usedToday"] == 1
    assert quota_after_delete.json()["data"]["remainingToday"] == 0
    repost_after_delete = client.post("/api/group-resources", json=group_payload(owner["id"], "删除后重发"))
    assert repost_after_delete.status_code == 409


def test_group_resource_tags_search_and_pending_delete_release_reward_reservation(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "标签发布者")
    created = client.post(
        "/api/group-resources",
        json=group_payload(owner["id"], "互助工具群", ["AI工具", "长沙本地"]),
    )
    assert created.status_code == 200
    resource = created.json()["data"]
    assert resource["tags"] == ["AI工具", "长沙本地"]

    public = client.get("/api/group-resources?keyword=AI工具")
    assert public.status_code == 200
    assert public.json()["data"][0]["tags"] == ["AI工具", "长沙本地"]

    deleted = client.delete(f"/api/group-resources/{resource['id']}?ownerUserId={owner['id']}")
    assert deleted.status_code == 200
    detail = client.get(
        f"/api/ops-admin/group-resource-review/{resource['id']}",
        headers={"X-Admin-Token": "ops-secret"},
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["rewardState"] == "cancelled"
    assert detail.json()["data"]["rewardAmount"] == 0


def test_user_live_qr_upload_update_keeps_fixed_entry_and_owner_boundary(client):
    owner = login(client, "活码拥有者")
    other = login(client, "活码访客")
    first = client.post(
        "/api/live-qr-codes",
        data={"ownerUserId": owner["id"]},
        files={"file": ("group.png", qr_bytes("https://example.com/group-a"), "image/png")},
    )
    assert first.status_code == 200
    item = first.json()["data"]
    assert item["ownerUserId"] == owner["id"]
    assert item["name"] == "微信群活码 1"
    original_code = item["code"]

    updated = client.post(
        f"/api/live-qr-codes/{item['id']}/target-qr",
        data={"ownerUserId": owner["id"]},
        files={"file": ("group-2.png", qr_bytes("https://example.com/group-b"), "image/png")},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["code"] == original_code
    assert updated.json()["data"]["version"] == 2
    history = client.get(f"/api/live-qr-codes?ownerUserId={owner['id']}")
    assert history.status_code == 200
    assert history.json()["data"][0]["history"][0]["version"] == 1
    assert history.json()["data"][0]["history"][0]["targetExpiresAt"]

    forbidden = client.delete(f"/api/live-qr-codes/{item['id']}?ownerUserId={other['id']}")
    assert forbidden.status_code == 403


def test_user_live_qr_source_style_replaces_only_qr_and_can_switch_back(client):
    owner = login(client, "投放样式拥有者")
    first = client.post(
        "/api/live-qr-codes",
        data={"ownerUserId": owner["id"], "styleMode": "source"},
        files={"file": ("group-poster.png", styled_qr_bytes("https://example.com/source-style"), "image/png")},
    )
    assert first.status_code == 200
    item = first.json()["data"]
    assert item["posterMode"] == "source"
    assert item["posterImageUrl"]
    assert item["qrImageUrl"] == item["posterImageUrl"]
    poster = client.get(item["posterImageUrl"])
    assert poster.status_code == 200
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(
        cv2.imdecode(np.frombuffer(poster.content, dtype=np.uint8), cv2.IMREAD_COLOR)
    )
    assert decoded == item["publicUrl"]

    plain = client.patch(
        f"/api/live-qr-codes/{item['id']}/style",
        json={"ownerUserId": owner["id"], "styleMode": "plain"},
    )
    assert plain.status_code == 200
    assert plain.json()["data"]["posterMode"] == "plain"
    assert plain.json()["data"]["posterImageUrl"] is None
    assert plain.json()["data"]["qrImageUrl"].endswith(f"/{item['code']}.png?v=1")

    source_again = client.patch(
        f"/api/live-qr-codes/{item['id']}/style",
        json={"ownerUserId": owner["id"], "styleMode": "source"},
    )
    assert source_again.status_code == 200
    assert source_again.json()["data"]["posterMode"] == "source"
    assert source_again.json()["data"]["qrImageUrl"] == source_again.json()["data"]["posterImageUrl"]
