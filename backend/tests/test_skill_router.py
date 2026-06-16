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


def test_link_text_routes_to_content_to_note_adapter():
    response = client.post("/api/skills/route", json={"text": "帮我整理 https://example.com/a"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "content_to_note"
    assert data["skillId"] == "content-to-note"
    assert data["source"] == "rule"
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


def test_commands_include_showcase_and_billing_entries():
    response = client.get("/api/skills/commands")

    assert response.status_code == 200
    commands = response.json()["data"]
    command_texts = {command["commandText"] for command in commands}
    assert {"创建展示页", "购买套餐", "生成漫画图"}.issubset(command_texts)
