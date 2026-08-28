from __future__ import annotations


def test_published_note_keeps_ordered_content_blocks_and_media_security(client):
    owner = client.post(
        "/api/auth/mock-login",
        json={"nickname": "图文发布用户", "openid": "openid_content_stream_publish"},
    ).json()["data"]
    created = client.post(
        "/api/notes/quick-capture",
        json={"ownerUserId": owner["id"], "rawText": "豆姐"},
    ).json()["data"]

    update = client.put(
        f"/api/notes/{created['id']}",
        json={
            "ownerUserId": owner["id"],
            "title": "豆姐",
            "summary": "图文资料",
            "body": "豆姐",
            "contentBlocks": [
                {"id": "text_1", "type": "text", "text": "豆姐", "sortOrder": 0},
                {"id": "image_1", "type": "image", "mediaId": "asset_1", "url": "https://example.com/a.jpg", "sortOrder": 1},
                {"id": "pdf_1", "type": "pdf", "mediaId": "asset_2", "url": "https://example.com/a.pdf", "sortOrder": 2},
                {"id": "private_image", "type": "image", "url": "https://example.com/not-in-media.jpg", "sortOrder": 3},
            ],
            "coverUrl": "https://example.com/a.jpg",
            "media": [
                {"id": "asset_1", "type": "image", "url": "https://example.com/a.jpg", "sortOrder": 0},
                {"id": "asset_2", "type": "pdf", "url": "https://example.com/a.pdf", "sortOrder": 1},
            ],
            "categoryIds": [],
            "phone": "",
            "locationText": "",
            "visibilityConfig": created["visibilityConfig"],
        },
    )
    assert update.status_code == 200
    published = client.post(
        f"/api/notes/{created['id']}/publish",
        json={"ownerUserId": owner["id"], "expectedRevision": update.json()["data"]["revision"]},
    )
    assert published.status_code == 200

    public = client.get(f"/api/notes/public/{created['id']}")
    assert public.status_code == 200
    data = public.json()["data"]
    assert [(item["type"], item.get("id")) for item in data["contentBlocks"]] == [
        ("text", "text_1"),
        ("image", "image_1"),
        ("pdf", "pdf_1"),
    ]
    assert "private_image" not in {item.get("id") for item in data["contentBlocks"]}
    assert [item["type"] for item in data["media"]] == ["image", "pdf"]
