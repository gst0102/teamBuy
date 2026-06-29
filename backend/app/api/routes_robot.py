from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import get_app_service
from app.core.config import settings
from app.services.app_service import AppService


router = APIRouter(prefix="/api/robot", tags=["robot"])

WECOM_EXTERNAL_BINDING_SOURCE = "wecom_external_user"


class RobotQueryRequest(BaseModel):
    corpId: str | None = None
    chatType: str = Field(default="private", pattern="^(private|group)$")
    fromUserId: str | None = None
    externalUserId: str | None = None
    roomId: str | None = None
    text: str
    limit: int = 3


def _verify_robot_token(authorization: str | None) -> None:
    if not settings.robot_gateway_token:
        raise HTTPException(status_code=403, detail="robot gateway token is not configured")
    raw_token = (authorization or "").strip()
    scheme, _, bearer_token = raw_token.partition(" ")
    if raw_token != settings.robot_gateway_token and (
        scheme.lower() != "bearer" or bearer_token != settings.robot_gateway_token
    ):
        raise HTTPException(status_code=403, detail="robot gateway token verification failed")


def _identity_key(payload: RobotQueryRequest) -> str | None:
    return payload.externalUserId or payload.fromUserId


def _robot_response(data: dict) -> dict:
    text = data.get("text", "")
    return {
        "success": True,
        "message": "ok",
        "result": text,
        "answer": text,
        "content": text,
        **data,
        "data": data,
    }


def _detect_scope(text: str, chat_type: str) -> str:
    lowered = text.lower()
    public_words = ("天气", "帮助", "怎么用", "介绍", "说明")
    room_words = ("群日报", "群总结", "广告", "群里", "这个群", "今日群")
    self_words = ("我的", "我保存", "我发过", "资料", "合集", "资源", "客户雷达")
    if any(word in text for word in public_words):
        return "public"
    if any(word in text for word in room_words):
        return "room"
    if chat_type == "group" and any(word in text for word in self_words):
        return "self_in_group"
    return "self"


def _public_reply(text: str) -> dict:
    if "天气" in text:
        return {
            "scope": "public",
            "replyType": "text",
            "text": "天气查询可以接入官方天气服务。现在先确认机器人身份和权限通路。",
            "items": [],
        }
    return {
        "scope": "public",
        "replyType": "text",
        "text": "我可以帮你找资料、发合集、看群日报。涉及个人资料时，需要先完成小程序身份绑定。",
        "items": [],
    }


def _match_query_text(text: str) -> str:
    cleaned = text.strip()
    for word in ("帮我找", "找一下", "发一下", "发我", "我的", "资料", "合集", "资源"):
        cleaned = cleaned.replace(word, " ")
    return " ".join(cleaned.split())


def _note_item(note: dict) -> dict:
    return {
        "type": "note",
        "id": note.get("id"),
        "title": note.get("title"),
        "summary": note.get("summary") or note.get("body", "")[:80],
        "path": f"/pages/note-preview/index?id={note.get('id')}",
    }


def _showcase_item(showcase: dict) -> dict:
    return {
        "type": "showcase",
        "id": showcase.get("id"),
        "title": showcase.get("name"),
        "summary": showcase.get("description") or "资料合集",
        "path": f"/pages/showcase-view/index?id={showcase.get('id')}",
    }


def _self_reply(service: AppService, owner_user_id: str, text: str, limit: int) -> dict:
    query = _match_query_text(text)
    wants_showcase = "合集" in text
    items: list[dict] = []
    if wants_showcase:
        showcases = service.list_showcases(owner_user_id)
        if query:
            lowered = query.lower()
            showcases = [
                item
                for item in showcases
                if lowered in " ".join([item.get("name") or "", item.get("description") or ""]).lower()
            ]
        items = [_showcase_item(item) for item in showcases[:limit]]
    else:
        notes = service.list_user_notes(owner_user_id, keyword=query or None, include_deleted=False)
        items = [_note_item(item) for item in notes[:limit]]

    if not items:
        return {
            "scope": "self",
            "replyType": "text",
            "text": "我只查了你自己名下的数据，暂时没找到匹配内容。可以换个标题、标签或场景词再问我。",
            "items": [],
        }
    first = items[0]
    return {
        "scope": "self",
        "replyType": "miniapp_list",
        "text": f"找到了 {len(items)} 个只属于你的结果。最匹配的是：{first['title']}",
        "items": items,
    }


@router.post("/query")
def robot_query(
    payload: RobotQueryRequest,
    authorization: str | None = Header(default=None),
    userid: str | None = Header(default=None),
    service: AppService = Depends(get_app_service),
):
    _verify_robot_token(authorization)
    scope = _detect_scope(payload.text, payload.chatType)
    if scope == "public":
        return _robot_response(_public_reply(payload.text))
    if scope == "self_in_group":
        return _robot_response({
            "scope": "self",
            "replyType": "private_required",
            "text": "这个问题涉及你的个人资料，我私聊里再帮你查。",
            "items": [],
        })
    if scope == "room":
        if not payload.roomId:
            return _robot_response({
                "scope": "room",
                "replyType": "text",
                "text": "没有拿到群 ID，暂时不能生成这个群的日报。",
                "items": [],
            })
        return _robot_response({
            "scope": "room",
            "replyType": "text",
            "text": "这个群的消息已经能进入归档。下一步可生成群日报、广告提醒和待跟进事项。",
            "items": [{"type": "room", "id": payload.roomId}],
        })

    identity = _identity_key(payload) or userid
    if not identity:
        return _robot_response({
            "scope": "self",
            "replyType": "bind_required",
            "text": "我还不知道你对应哪个小程序账号。先打开小程序完成绑定，我才能查你的资料和合集。",
            "items": [],
            "bindHint": {
                "sourceType": WECOM_EXTERNAL_BINDING_SOURCE,
                "path": "/pages/import-claim/index",
            },
        })
    binding = service.repo.get_wecom_identity_binding(WECOM_EXTERNAL_BINDING_SOURCE, identity)
    if not binding:
        return _robot_response({
            "scope": "self",
            "replyType": "bind_required",
            "text": "我还不知道你对应哪个小程序账号。先打开小程序完成绑定，我才能查你的资料和合集。",
            "items": [],
            "bindHint": {
                "identity": identity,
                "sourceType": WECOM_EXTERNAL_BINDING_SOURCE,
                "path": "/pages/import-claim/index",
            },
        })
    return _robot_response(_self_reply(service, binding.ownerUserId, payload.text, max(1, min(payload.limit, 5))))
