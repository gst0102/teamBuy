from __future__ import annotations

from io import BytesIO

import qrcode

from app.core.config import settings


def test_live_qr_page_and_admin_api_require_admin_token(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")

    page = client.get("/ops/live-qr")
    assert page.status_code == 200
    assert "活码工作台" in page.text
    assert "二维码地址不变" in page.text
    assert "下载投放卡片" in page.text
    assert "真实群头像" in page.text
    assert "当前群码有效至" not in page.text

    forbidden = client.get("/api/ops-admin/live-qr-codes")
    assert forbidden.status_code == 403

    invalid = client.post(
        "/api/ops-admin/live-qr-codes",
        headers={"X-Admin-Token": "ops-secret"},
        json={"name": "无效链接", "targetUrl": "not-a-url"},
    )
    assert invalid.status_code == 400


def test_live_qr_keeps_entry_stable_when_target_changes_and_pauses(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}

    created = client.post(
        "/api/ops-admin/live-qr-codes",
        headers=headers,
        json={
            "name": "小红书入口",
            "targetUrl": "https://example.com/login",
            "description": "第一版投放",
        },
    )
    assert created.status_code == 200
    item = created.json()["data"]
    code = item["code"]
    assert item["publicUrl"].endswith(f"/live-qr/{code}")
    assert item["version"] == 1
    assert item["scanCount"] == 0
    assert item["targetExpiresAt"]
    assert item["targetExpiryState"] == "active"
    assert 6 <= item["targetExpiresInDays"] <= 7

    image = client.get(f"/live-qr/{code}.png")
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")
    assert image.content.startswith(b"\x89PNG\r\n\x1a\n")

    first_scan = client.get(f"/live-qr/{code}", follow_redirects=False)
    assert first_scan.status_code == 200
    assert "location" not in first_scan.headers
    assert "当前群二维码暂未上传" in first_scan.text

    listed = client.get("/api/ops-admin/live-qr-codes", headers=headers).json()["data"]
    assert listed[0]["scanCount"] == 1
    paginated = client.get("/api/ops-admin/live-qr-codes?page=1&pageSize=1", headers=headers).json()["data"]
    assert paginated["page"] == 1
    assert paginated["pageSize"] == 1
    assert paginated["total"] == 1
    assert len(paginated["items"]) == 1

    updated = client.patch(
        f"/api/ops-admin/live-qr-codes/{item['id']}",
        headers=headers,
        json={
            "name": "小红书入口（第二周）",
            "targetUrl": "https://example.com/activity",
            "description": "第七天更换目标",
        },
    )
    assert updated.status_code == 200
    updated_item = updated.json()["data"]
    assert updated_item["code"] == code
    assert updated_item["version"] == 2
    assert updated_item["scanCount"] == 1
    assert updated_item["targetExpiresInDays"] >= 6

    second_scan = client.get(f"/live-qr/{code}", follow_redirects=False)
    assert second_scan.status_code == 200
    assert "location" not in second_scan.headers

    paused = client.patch(
        f"/api/ops-admin/live-qr-codes/{item['id']}",
        headers=headers,
        json={"status": "paused"},
    )
    assert paused.status_code == 200
    assert paused.json()["data"]["status"] == "paused"

    paused_scan = client.get(f"/live-qr/{code}", follow_redirects=False)
    assert paused_scan.status_code == 410
    assert "入口暂时不可用" in paused_scan.text

    resumed = client.patch(
        f"/api/ops-admin/live-qr-codes/{item['id']}",
        headers=headers,
        json={"status": "active"},
    )
    assert resumed.status_code == 200

    resumed_scan = client.get(f"/live-qr/{code}", follow_redirects=False)
    assert resumed_scan.status_code == 200
    assert "location" not in resumed_scan.headers

    final_item = client.get("/api/ops-admin/live-qr-codes", headers=headers).json()["data"][0]
    assert final_item["code"] == code
    assert final_item["scanCount"] == 3

def test_live_qr_marks_expired_target_and_allows_extension_without_new_outer_code(client, monkeypatch):
    import app.api.routes_live_qr as live_qr_routes

    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}
    created = client.post(
        "/api/ops-admin/live-qr-codes",
        headers=headers,
        json={
            "name": "七天群入口",
            "targetUrl": "https://example.com/group-a",
            "targetExpiresAt": "2099-01-01T00:00:00+08:00",
        },
    ).json()["data"]
    code = created["code"]
    monkeypatch.setattr(live_qr_routes, "now_iso", lambda: "2099-01-02T00:00:00+08:00")

    expired = client.get(f"/live-qr/{code}", follow_redirects=False)
    assert expired.status_code == 410
    assert "已过期" in expired.text
    page = client.get("/api/ops-admin/live-qr-codes?page=1&pageSize=10", headers=headers).json()["data"]
    assert page["items"][0]["targetExpiryState"] == "expired"
    assert page["items"][0]["targetExpiresInDays"] == 0

    extended = client.patch(
        f"/api/ops-admin/live-qr-codes/{created['id']}",
        headers=headers,
        json={"targetUrl": "https://example.com/group-a", "targetExpiresAt": "2099-01-10T00:00:00+08:00"},
    ).json()["data"]
    assert extended["code"] == code
    assert extended["version"] == 1
    assert extended["targetExpiryState"] == "active"
    resumed = client.get(f"/live-qr/{code}", follow_redirects=False)
    assert resumed.status_code == 200
    assert "location" not in resumed.headers


def test_live_qr_decodes_uploaded_group_qr_without_mutating_live_codes(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}
    qr_image = qrcode.make("https://example.com/group-from-image")
    output = BytesIO()
    qr_image.save(output, format="PNG")

    forbidden = client.post(
        "/api/ops-admin/live-qr-decode",
        files={"file": ("group.png", output.getvalue(), "image/png")},
    )
    assert forbidden.status_code == 403

    decoded = client.post(
        "/api/ops-admin/live-qr-decode",
        headers=headers,
        files={"file": ("group.png", output.getvalue(), "image/png")},
    )
    assert decoded.status_code == 200
    assert decoded.json()["data"] == {"targetUrl": "https://example.com/group-from-image"}

    invalid = client.post(
        "/api/ops-admin/live-qr-decode",
        headers=headers,
        files={"file": ("not-an-image.txt", b"not an image", "text/plain")},
    )
    assert invalid.status_code == 400

    empty = client.get("/api/ops-admin/live-qr-codes?page=1&pageSize=10", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["data"]["total"] == 0


def test_live_qr_target_upload_persists_inner_image_and_resets_to_seven_days(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}
    created = client.post(
        "/api/ops-admin/live-qr-codes",
        headers=headers,
        json={
            "name": "落地页群",
            "targetUrl": "https://example.com/old",
            "targetExpiresAt": "2099-01-01T00:00:00+08:00",
        },
    ).json()["data"]
    qr_image = qrcode.make("https://c.weixin.com/g/new-group")
    output = BytesIO()
    qr_image.save(output, format="PNG")

    uploaded = client.post(
        f"/api/ops-admin/live-qr-codes/{created['id']}/target-qr",
        headers=headers,
        files={"file": ("group.png", output.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 200
    item = uploaded.json()["data"]
    assert item["targetQrImageUrl"].startswith("/mock-media/")
    assert item["decodedTargetUrl"] == "https://c.weixin.com/g/new-group"
    assert item["targetUrl"] == "https://c.weixin.com/g/new-group"
    assert item["version"] == created["version"] + 1
    assert 6 <= item["targetExpiresInDays"] <= 7

    landing = client.get(f"/live-qr/{item['code']}", follow_redirects=False)
    assert landing.status_code == 200
    assert "location" not in landing.headers
    assert item["targetQrImageUrl"] in landing.text
    assert '<img class="target-qr"' in landing.text
    assert "群聊：" not in landing.text
    assert "最新群入口" not in landing.text
    assert "长按二维码" not in landing.text


def test_live_qr_avatar_upload_persists_real_group_avatar(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}
    created = client.post(
        "/api/ops-admin/live-qr-codes",
        headers=headers,
        json={"name": "真实头像群", "targetUrl": "https://example.com/real-avatar"},
    ).json()["data"]
    avatar = qrcode.make("group-avatar")
    output = BytesIO()
    avatar.save(output, format="PNG")

    forbidden = client.post(
        f"/api/ops-admin/live-qr-codes/{created['id']}/avatar",
        files={"file": ("avatar.png", output.getvalue(), "image/png")},
    )
    assert forbidden.status_code == 403

    uploaded = client.post(
        f"/api/ops-admin/live-qr-codes/{created['id']}/avatar",
        headers=headers,
        files={"file": ("avatar.png", output.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 200
    item = uploaded.json()["data"]
    assert item["groupAvatarUrl"].startswith("/mock-media/")

    listed = client.get("/api/ops-admin/live-qr-codes", headers=headers).json()["data"]
    assert listed[0]["groupAvatarUrl"] == item["groupAvatarUrl"]

    invalid = client.post(
        f"/api/ops-admin/live-qr-codes/{created['id']}/avatar",
        headers=headers,
        files={"file": ("avatar.txt", b"not-an-image", "text/plain")},
    )
    assert invalid.status_code == 400


def test_live_qr_expiry_summary_and_filters_use_the_same_target_day_buckets(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}
    for name, expiry in [
        ("一天", "2099-01-03T00:00:00+08:00"),
        ("两天", "2099-01-04T00:00:00+08:00"),
        ("三天", "2099-01-05T00:00:00+08:00"),
        ("已过期", "2099-01-01T00:00:00+08:00"),
    ]:
        created = client.post(
            "/api/ops-admin/live-qr-codes",
            headers=headers,
            json={
                "name": name,
                "targetUrl": f"https://example.com/{name}",
                "targetExpiresAt": expiry,
            },
        )
        assert created.status_code == 200

    import app.api.routes_live_qr as live_qr_routes

    monkeypatch.setattr(live_qr_routes, "now_iso", lambda: "2099-01-02T00:00:00+08:00")
    all_items = client.get("/api/ops-admin/live-qr-codes?page=1&pageSize=10", headers=headers).json()["data"]
    assert all_items["expirySummary"] == {"expired": 1, "1d": 1, "2d": 1, "3d": 1}

    one_day = client.get("/api/ops-admin/live-qr-codes?page=1&pageSize=10&expiryFilter=1d", headers=headers).json()["data"]
    assert one_day["total"] == 1
    assert one_day["items"][0]["name"] == "一天"

    expired = client.get("/api/ops-admin/live-qr-codes?page=1&pageSize=10&expiryFilter=expired", headers=headers).json()["data"]
    assert expired["total"] == 1
    assert expired["items"][0]["name"] == "已过期"

    invalid_filter = client.get("/api/ops-admin/live-qr-codes?page=1&expiryFilter=7d", headers=headers)
    assert invalid_filter.status_code == 400


def test_live_qr_member_count_summary_filters_and_delete(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}
    created = {}
    for name, count in [("安全群", 50), ("提醒群", 180), ("换群", 200), ("未检查群", None)]:
        payload = {
            "name": name,
            "targetUrl": "https://example.com/" + name,
        }
        if count is not None:
            payload["groupMemberCount"] = count
        created[name] = client.post("/api/ops-admin/live-qr-codes", headers=headers, json=payload).json()["data"]

    page = client.get("/api/ops-admin/live-qr-codes?page=1&pageSize=10", headers=headers)
    assert page.status_code == 200
    data = page.json()["data"]
    assert data["memberSummary"] == {"normal": 0, "warning": 0, "replace": 0, "unknown": 4}
    assert data["serverDate"]

    warning = client.get(
        "/api/ops-admin/live-qr-codes?page=1&pageSize=10&memberFilter=warning",
        headers=headers,
    )
    assert warning.json()["data"]["total"] == 0

    replace = client.get(
        "/api/ops-admin/live-qr-codes?page=1&pageSize=10&memberFilter=replace",
        headers=headers,
    )
    assert replace.json()["data"]["total"] == 0

    deleted = client.delete(
        f"/api/ops-admin/live-qr-codes/{created['换群']['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["code"] == created["换群"]["code"]
    assert client.get(f"/live-qr/{created['换群']['code']}").status_code == 410

    forbidden = client.delete(f"/api/ops-admin/live-qr-codes/{created['安全群']['id']}")
    assert forbidden.status_code == 403
