from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_exact_command_routes_without_ai_fallback():
    response = client.post("/api/skills/route", json={"text": "整理笔记"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "content_to_note"
    assert data["skillId"] == "content-to-note"
    assert data["source"] == "exact_command"
    assert data["needsConfirm"] is False
    assert data["inputAdapter"] == "input.wecom-thread"


def test_link_text_routes_to_bookmark_adapter_by_default():
    response = client.post("/api/skills/route", json={"text": "我收藏一下 https://example.com/a"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "link_bookmark"
    assert data["skillId"] == "link-bookmark"
    assert data["source"] == "rule"
    assert data["inputAdapter"] == "input.link-article"


def test_explicit_link_command_routes_to_content_to_note_adapter():
    response = client.post("/api/skills/route", json={"text": "整理链接"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "content_to_note"
    assert data["skillId"] == "content-to-note"
    assert data["source"] == "exact_command"
    assert data["inputAdapter"] == "input.link-article"


def test_comic_text_routes_to_comic_skill():
    response = client.post("/api/skills/route", json={"text": "帮我把这篇笔记生成漫画图"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "note_to_comic_image"
    assert data["skillId"] == "note-to-comic-image"
    assert data["needsConfirm"] is False


def test_unknown_text_requires_confirm_menu():
    response = client.post("/api/skills/route", json={"text": "今天天气还不错"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "unknown"
    assert data["skillId"] is None
    assert data["source"] == "confirm_menu"
    assert data["needsConfirm"] is True


def test_run_content_to_note_builds_rule_based_note_draft():
    response = client.post(
        "/api/skills/content-to-note/run",
        json={
            "ownerUserId": "user_001",
            "content": {
                "sourceType": "wecom_thread",
                "title": "客户购房需求",
                "textBlocks": ["客户预算 300 万，想看三房。电话 13800138000。", "偏好地铁附近。"],
                "media": [{"type": "image", "url": "https://example.com/cover.webp"}],
                "sourceRefs": ["wecom_msg_1"],
                "rawMessageIds": ["raw_1"],
            },
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"]["intent"] == "content_to_note"
    assert data["skillRun"]["status"] == "success"
    assert data["skillRun"]["modelProvider"] == "rule"
    assert data["noteDraft"]["ownerUserId"] == "user_001"
    assert data["noteDraft"]["title"] == "客户购房需求"
    assert data["noteDraft"]["phone"] == "13800138000"
    assert data["noteDraft"]["coverUrl"] == "https://example.com/cover.webp"
    assert "偏好地铁附近" in data["noteDraft"]["body"]


def test_run_content_to_note_detects_property_listing_card():
    response = client.post(
        "/api/skills/content-to-note/run",
        json={
            "ownerUserId": "user_001",
            "content": {
                "sourceType": "wecom_thread",
                "title": "碧桂园城市之光租房",
                "textBlocks": [
                    "🍊小区：碧桂园城市之光1栋1210\n🍪户型：公寓一房\n面积：42平\n价格：1600元/月\n水电物业：自缴\n商圈：万家丽、高桥北\n备注：服务费200"
                ],
                "media": [{"type": "image", "url": "https://example.com/house.webp"}],
                "sourceRefs": ["wecom_msg_property"],
                "rawMessageIds": ["raw_property"],
            },
        },
    )

    assert response.status_code == 200
    note = response.json()["data"]["noteDraft"]
    config = note["visibilityConfig"]
    assert config["cardType"] == "property_listing"
    assert config["cardState"] == "generated"
    assert config["contentMode"] == "structured_card"
    assert config["systemCategory"] == "房源"
    assert config["recognitionConfidence"]["level"] == "high"
    assert {"房产", "房源"}.issubset(set(config["tags"]))
    assert config["structuredData"]["community"] == "碧桂园城市之光1栋1210"
    assert config["structuredData"]["layout"] == "公寓一房"
    assert config["structuredData"]["area"] == "42平"
    assert config["structuredData"]["price"] == "1600元/月"
    assert config["structuredData"]["businessArea"] == "万家丽、高桥北"
    assert config["structuredData"]["images"] == ["https://example.com/house.webp"]
    assert config["conversionConfig"]["enableLightScrm"] is True
    assert config["conversionConfig"]["enableAppointment"] is True
    assert config["conversionConfig"]["enableGroupRelay"] is False


def test_run_content_to_note_detects_groupbuy_product_card():
    response = client.post(
        "/api/skills/content-to-note/run",
        json={
            "ownerUserId": "user_001",
            "content": {
                "sourceType": "wecom_thread",
                "title": "丹东草莓团购",
                "textBlocks": ["商品：丹东草莓\n价格：39.9元\n规格：3斤装\n取货：包邮到家\n截止：今晚22点\n备注：现摘现发"],
                "media": [{"type": "image", "url": "https://example.com/strawberry.webp"}],
                "sourceRefs": ["wecom_msg_groupbuy"],
                "rawMessageIds": ["raw_groupbuy"],
            },
        },
    )

    assert response.status_code == 200
    note = response.json()["data"]["noteDraft"]
    config = note["visibilityConfig"]
    assert config["cardType"] == "groupbuy_product"
    assert config["cardState"] == "generated"
    assert config["contentMode"] == "structured_card"
    assert config["systemCategory"] == "团购"
    assert config["recognitionConfidence"]["level"] == "high"
    assert {"团购", "商品"}.issubset(set(config["tags"]))
    assert config["structuredData"]["productName"] == "丹东草莓"
    assert config["structuredData"]["price"] == "39.9元"
    assert config["structuredData"]["spec"] == "3斤装"
    assert config["structuredData"]["pickupMethod"] == "包邮到家"
    assert config["conversionConfig"]["enableLightScrm"] is True
    assert config["conversionConfig"]["enableGroupRelay"] is True
    assert config["conversionConfig"]["enablePaymentPlaceholder"] is False


def test_run_content_to_note_keeps_medium_confidence_as_plain_note_with_suggestions():
    response = client.post(
        "/api/skills/content-to-note/run",
        json={
            "ownerUserId": "user_001",
            "content": {
                "sourceType": "wecom_thread",
                "title": "今天收到的一条资料",
                "textBlocks": ["价格：1600元\n位置：万家丽附近\n有几张图片，晚点确认具体用途"],
                "media": [{"type": "image", "url": "https://example.com/item.webp"}],
                "sourceRefs": ["wecom_msg_ambiguous"],
                "rawMessageIds": ["raw_ambiguous"],
            },
        },
    )

    assert response.status_code == 200
    config = response.json()["data"]["noteDraft"]["visibilityConfig"]
    assert config["cardType"] == "text_note"
    assert config["contentMode"] == "note"
    assert config["cardState"] == "collected"
    assert config["recognitionConfidence"]["level"] == "medium"
    assert any(item["cardType"] == "property_listing" for item in config["typeSuggestions"])


def test_property_price_prefers_price_line_over_service_fee_and_area_numbers():
    response = client.post(
        "/api/skills/content-to-note/run",
        json={
            "ownerUserId": "user_001",
            "content": {
                "sourceType": "wecom_thread",
                "title": "芙蓉万国城房源",
                "textBlocks": [
                    "🍊小区：芙蓉万国城19A-1137房\n🍪户型：公寓一房\n面积：42平\n💰价格：1300🔥 密码锁\n🌿水电物业：自缴\n📍位置：汽车东站，2号线袁隆平水稻博物馆地铁口\n💫备注：合同期内收取一次性200元的服务费"
                ],
                "media": [{"type": "image", "url": "https://example.com/house.webp"}],
                "sourceRefs": ["wecom_msg_property_price"],
                "rawMessageIds": ["raw_property_price"],
            },
        },
    )

    assert response.status_code == 200
    config = response.json()["data"]["noteDraft"]["visibilityConfig"]
    assert config["cardType"] == "property_listing"
    assert config["structuredData"]["price"] == "1300"
    assert config["structuredData"]["serviceFee"] == ""


def test_property_detection_uses_title_as_community_signal():
    response = client.post(
        "/api/skills/content-to-note/run",
        json={
            "ownerUserId": "user_001",
            "content": {
                "sourceType": "wecom_thread",
                "title": "万国城北塔27050",
                "textBlocks": [
                    "户型：loft两房\n面积：42平\n价格：27050\n位置：袁隆平地铁口附近\n水电物业：自缴\n备注：带浴缸"
                ],
                "media": [{"type": "image", "url": "https://example.com/house.webp"}],
                "sourceRefs": ["wecom_msg_title_property"],
                "rawMessageIds": ["raw_title_property"],
            },
        },
    )

    assert response.status_code == 200
    config = response.json()["data"]["noteDraft"]["visibilityConfig"]
    assert config["cardType"] == "property_listing"
    assert config["recognitionConfidence"]["level"] == "high"
    assert config["structuredData"]["community"] == "万国城北塔27050"


def test_commands_include_showcase_and_billing_entries():
    response = client.get("/api/skills/commands")

    assert response.status_code == 200
    commands = response.json()["data"]
    command_texts = {command["commandText"] for command in commands}
    assert {"创建展示页", "购买套餐", "生成漫画图"}.issubset(command_texts)
