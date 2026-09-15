from __future__ import annotations


def login(client, openid: str) -> dict:
    response = client.post(
        "/api/auth/mock-login",
        json={"openid": openid, "nickname": openid},
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_mutual_help_chat_is_one_to_one_and_mirrors_sender_identity(client):
    owner = login(client, "openid_chat_owner")
    executor = login(client, "openid_chat_executor")
    stranger = login(client, "openid_chat_stranger")
    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner["id"],
            "taskKind": "miniapp",
            "title": "体验目标小程序",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "提交体验感受"}],
            "taskLinks": [{"type": "miniapp", "title": "体验入口", "shortLink": "#小程序://体验入口/首页"}],
            "rewardPoints": 5,
            "executorReward": 4,
        },
    )
    assert created.status_code == 200
    task_id = created.json()["data"]["task"]["id"]

    opened = client.post(
        "/api/scrm/mutual-help/activity",
        json={"userId": executor["id"], "eventType": "opened", "taskId": task_id, "taskKind": "miniapp"},
    )
    assert opened.status_code == 200

    executor_room = client.post(
        f"/api/scrm/mutual-help/tasks/{task_id}/chat/conversation",
        json={"userId": executor["id"]},
    )
    owner_room = client.post(
        f"/api/scrm/mutual-help/tasks/{task_id}/chat/conversation",
        json={"userId": owner["id"], "executorUserId": executor["id"]},
    )
    assert executor_room.status_code == owner_room.status_code == 200
    conversation_id = executor_room.json()["data"]["conversation"]["id"]
    assert owner_room.json()["data"]["conversation"]["id"] == conversation_id

    message_payload = {
        "userId": executor["id"],
        "messageType": "text",
        "text": "我已打开小程序，马上体验。",
        "idempotencyKey": "chat-message-once",
    }
    first_send = client.post(f"/api/scrm/mutual-help/chat/{conversation_id}/messages", json=message_payload)
    retry_send = client.post(f"/api/scrm/mutual-help/chat/{conversation_id}/messages", json=message_payload)
    assert first_send.status_code == retry_send.status_code == 200

    owner_participants = client.get(
        f"/api/scrm/mutual-help/tasks/{task_id}/chat/participants?userId={owner['id']}"
    )
    assert owner_participants.status_code == 200
    assert owner_participants.json()["data"]["items"][0]["unreadCount"] == 1

    owner_messages = client.get(
        f"/api/scrm/mutual-help/chat/{conversation_id}/messages?userId={owner['id']}"
    )
    assert owner_messages.status_code == 200
    room_data = owner_messages.json()["data"]
    assert len(room_data["items"]) == 1
    message = room_data["items"][0]
    assert message["senderUserId"] == executor["id"]
    assert message["recipientUserId"] == owner["id"]
    assert room_data["conversation"]["unreadByUser"][owner["id"]] == 0

    executor_messages = client.get(
        f"/api/scrm/mutual-help/chat/{conversation_id}/messages?userId={executor['id']}"
    )
    assert executor_messages.status_code == 200
    assert executor_messages.json()["data"]["items"][0]["senderUserId"] == executor["id"]

    hidden_from_stranger = client.get(
        f"/api/scrm/mutual-help/chat/{conversation_id}/messages?userId={stranger['id']}"
    )
    assert hidden_from_stranger.status_code == 404


def test_mutual_help_chat_only_allows_task_miniapp_cards_and_report_shows_started_task(client):
    owner = login(client, "openid_chat_card_owner")
    executor = login(client, "openid_chat_card_executor")
    created = client.post(
        "/api/scrm/mutual-help/tasks",
        json={
            "ownerUserId": owner["id"],
            "taskKind": "miniapp",
            "title": "体验小程序入口",
            "acceptanceCriteriaBlocks": [{"type": "text", "text": "返回并提交体验"}],
            "taskLinks": [{"type": "miniapp", "title": "已配置入口", "shortLink": "#小程序://已配置/页面"}],
            "rewardPoints": 5,
            "executorReward": 4,
        },
    )
    assert created.status_code == 200
    task_id = created.json()["data"]["task"]["id"]
    assert client.post(
        "/api/scrm/mutual-help/activity",
        json={"userId": executor["id"], "eventType": "opened", "taskId": task_id, "taskKind": "miniapp"},
    ).status_code == 200
    room = client.post(
        f"/api/scrm/mutual-help/tasks/{task_id}/chat/conversation",
        json={"userId": executor["id"]},
    ).json()["data"]["conversation"]

    valid_card = client.post(
        f"/api/scrm/mutual-help/chat/{room['id']}/messages",
        json={
            "userId": executor["id"],
            "messageType": "mini_program",
            "miniProgram": {"title": "篡改的标题也不会被采纳", "shortLink": "#小程序://已配置/页面"},
        },
    )
    assert valid_card.status_code == 200
    assert valid_card.json()["data"]["message"]["miniProgram"]["title"] == "已配置入口"

    invalid_card = client.post(
        f"/api/scrm/mutual-help/chat/{room['id']}/messages",
        json={
            "userId": executor["id"],
            "messageType": "mini_program",
            "miniProgram": {"title": "外部入口", "shortLink": "#小程序://其他/页面"},
        },
    )
    assert invalid_card.status_code == 400

    unowned_image = client.post(
        f"/api/scrm/mutual-help/chat/{room['id']}/messages",
        json={"userId": executor["id"], "messageType": "image", "imageUrl": "https://example.com/not-owned.png"},
    )
    assert unowned_image.status_code == 400

    report = client.get(f"/api/scrm/mutual-help/report?userId={executor['id']}")
    assert report.status_code == 200
    assert report.json()["data"]["summary"]["participationCount"] == 1
    assert report.json()["data"]["items"][0]["taskId"] == task_id
    assert report.json()["data"]["items"][0]["status"] == "in_progress"
