from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

from app.models.domain import WecomArchiveMessage
from app.schemas.skills import ContentLinkPayload, ContentMediaPayload


BEIKE_CITY_SLUGS = {
    "150200": "baotou",
}

MEDIA_PLACEHOLDERS = {"[图片]", "[视频]", "[文件]"}


@dataclass
class ArchiveParseResult:
    title: str | None = None
    source_type: str | None = None
    text_blocks: list[str] = field(default_factory=list)
    media: list[ContentMediaPayload] = field(default_factory=list)
    links: list[ContentLinkPayload] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class ArchiveMessageParser:
    name = "base"
    msg_types: set[str] = set()

    def can_parse(self, msg_type: str) -> bool:
        return msg_type in self.msg_types

    def parse(self, message: WecomArchiveMessage, payload: dict, msg_type: str) -> ArchiveParseResult:
        raise NotImplementedError


class TextArchiveParser(ArchiveMessageParser):
    name = "text"
    msg_types = {"text"}

    def parse(self, message: WecomArchiveMessage, payload: dict, msg_type: str) -> ArchiveParseResult:
        content = payload.get("text", {}).get("content") if isinstance(payload.get("text"), dict) else payload.get("content")
        text = str(content or "").strip()
        return ArchiveParseResult(text_blocks=[text] if text else [])


class LinkArchiveParser(ArchiveMessageParser):
    name = "link"
    msg_types = {"link"}

    def parse(self, message: WecomArchiveMessage, payload: dict, msg_type: str) -> ArchiveParseResult:
        link = payload.get("link") if isinstance(payload.get("link"), dict) else payload
        return ArchiveParseResult(
            source_type="link_article",
            links=[
                ContentLinkPayload(
                    url=str(link.get("link_url") or link.get("url") or "").strip(),
                    title=str(link.get("title") or "").strip() or None,
                    description=str(link.get("description") or "").strip() or None,
                    coverUrl=str(link.get("image_url") or link.get("thumbUrl") or "").strip() or None,
                )
            ],
        )


class MediaArchiveParser(ArchiveMessageParser):
    name = "media"
    msg_types = {"image", "video", "file"}

    def parse(self, message: WecomArchiveMessage, payload: dict, msg_type: str) -> ArchiveParseResult:
        return ArchiveParseResult(
            text_blocks=[f"收到{msg_type}素材，媒体稍后转存。"],
            media=[
                ContentMediaPayload(
                    type=msg_type,
                    url=None,
                    mediaId=archive_media_id(payload, msg_type),
                    title=str(payload.get("filename") or payload.get("file", {}).get("filename") or "").strip() or None,
                    sourceRef=message.id,
                )
            ],
        )


class LocationArchiveParser(ArchiveMessageParser):
    name = "location"
    msg_types = {"location"}

    def parse(self, message: WecomArchiveMessage, payload: dict, msg_type: str) -> ArchiveParseResult:
        location = payload.get("location") if isinstance(payload.get("location"), dict) else payload
        label = str(location.get("address") or location.get("title") or "").strip()
        return ArchiveParseResult(text_blocks=[f"位置：{label}"] if label else [])


class NoteArchiveParser(ArchiveMessageParser):
    name = "note"
    msg_types = {"note"}

    def parse(self, message: WecomArchiveMessage, payload: dict, msg_type: str) -> ArchiveParseResult:
        result = ArchiveParseResult()
        items = payload.get("info", {}).get("items") if isinstance(payload.get("info"), dict) else []
        if not isinstance(items, list):
            return result
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            append_item_parts(
                result,
                part_type=item.get("msg_type") or item.get("msgType"),
                content=parse_json_content(item.get("content")),
                source_ref=f"{message.id}#{index}",
            )
        return result


class ChatRecordArchiveParser(ArchiveMessageParser):
    name = "chatrecord"
    msg_types = {"chatrecord"}

    def parse(self, message: WecomArchiveMessage, payload: dict, msg_type: str) -> ArchiveParseResult:
        result = ArchiveParseResult(
            source_type="wecom_chatrecord",
            metadata={
                "archiveParser": "chatrecord",
                "parserHints": [],
            },
        )
        chatrecord = payload.get("chatrecord") if isinstance(payload.get("chatrecord"), dict) else {}
        if not chatrecord:
            return result
        title = str(chatrecord.get("title") or "").strip()
        if title:
            result.metadata["chatrecordTitle"] = title

        items = chatrecord.get("item") or chatrecord.get("items") or []
        if not isinstance(items, list):
            return result
        placeholder_counts: dict[str, int] = {}
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            part_type = normalize_chatrecord_type(str(item.get("type") or item.get("msgtype") or item.get("msg_type") or ""))
            content = parse_json_content(item.get("content"))
            text = str(content.get("content") or "").strip()
            if text in MEDIA_PLACEHOLDERS:
                placeholder_counts[text] = placeholder_counts.get(text, 0) + 1
                continue
            append_item_parts(result, part_type=part_type, content=content, source_ref=f"{message.id}#{index}")

        if placeholder_counts:
            result.metadata["chatrecordPlaceholders"] = placeholder_counts
        body = "\n".join(result.text_blocks)
        if looks_like_groupbuy_product(body):
            result.metadata["parserHints"].append("groupbuy_product")
        return result


class WeappArchiveParser(ArchiveMessageParser):
    name = "weapp"
    msg_types = {"weapp"}

    def parse(self, message: WecomArchiveMessage, payload: dict, msg_type: str) -> ArchiveParseResult:
        miniapp_payload = payload.get("weapp") if isinstance(payload.get("weapp"), dict) else payload
        miniapp = miniapp_metadata(miniapp_payload)
        return ArchiveParseResult(
            title=miniapp.get("title") or None,
            source_type="miniapp_card",
            text_blocks=miniapp_text_blocks(miniapp),
            metadata={"miniapp": miniapp},
        )


class FallbackArchiveParser(ArchiveMessageParser):
    name = "fallback"

    def parse(self, message: WecomArchiveMessage, payload: dict, msg_type: str) -> ArchiveParseResult:
        text = payload.get("content") or payload.get("text")
        return ArchiveParseResult(text_blocks=[str(text).strip()] if text else [])


class ArchiveMessageParserRegistry:
    def __init__(self, parsers: list[ArchiveMessageParser] | None = None):
        self.parsers: list[ArchiveMessageParser] = []
        self.parsers_by_type: dict[str, ArchiveMessageParser] = {}
        self.fallback = FallbackArchiveParser()
        for parser in parsers or default_archive_parsers():
            self.register(parser)

    def register(self, parser: ArchiveMessageParser) -> None:
        if not parser.msg_types:
            raise ValueError(f"Archive parser {parser.name} must declare msg_types")
        for msg_type in parser.msg_types:
            if msg_type in self.parsers_by_type:
                existing = self.parsers_by_type[msg_type]
                raise ValueError(f"Archive msg_type {msg_type} already registered by {existing.name}")
            self.parsers_by_type[msg_type] = parser
        self.parsers.append(parser)

    def supported_types(self) -> list[str]:
        return sorted(self.parsers_by_type.keys())

    def parse(self, message: WecomArchiveMessage, payload: dict, msg_type: str) -> ArchiveParseResult:
        parser = self.parsers_by_type.get(msg_type) or self.fallback
        result = parser.parse(message, payload, msg_type)
        result.metadata = dict(result.metadata or {})
        result.metadata.setdefault("archiveParser", parser.name)
        result.metadata.setdefault("archiveMsgType", msg_type)
        if parser is self.fallback:
            result.metadata.setdefault("parserHints", [])
            result.metadata["unsupportedArchiveMsgType"] = msg_type
        return result


def default_archive_parsers() -> list[ArchiveMessageParser]:
    return [
        TextArchiveParser(),
        LinkArchiveParser(),
        MediaArchiveParser(),
        LocationArchiveParser(),
        NoteArchiveParser(),
        ChatRecordArchiveParser(),
        WeappArchiveParser(),
    ]


def append_item_parts(result: ArchiveParseResult, part_type: str | None, content: dict, source_ref: str) -> None:
    if part_type == "text":
        text = str(content.get("content") or "").strip()
        if text and text not in MEDIA_PLACEHOLDERS:
            result.text_blocks.append(text)
    elif part_type == "location":
        label = str(content.get("address") or content.get("title") or "").strip()
        if label:
            result.text_blocks.append(f"位置：{label}")
    elif part_type == "link":
        result.links.append(
            ContentLinkPayload(
                url=str(content.get("link_url") or content.get("url") or "").strip(),
                title=str(content.get("title") or "").strip() or None,
                description=str(content.get("description") or "").strip() or None,
                coverUrl=str(content.get("image_url") or content.get("thumbUrl") or "").strip() or None,
            )
        )
    elif part_type in {"image", "video", "file"}:
        result.media.append(
            ContentMediaPayload(
                type=part_type,
                url=None,
                mediaId=content.get("sdkfileid") or content.get("media_id") or content.get("md5sum"),
                title=str(content.get("filename") or "").strip() or None,
                sourceRef=source_ref,
            )
        )


def parse_json_content(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"content": value}
        return parsed if isinstance(parsed, dict) else {"content": value}
    return {}


def normalize_chatrecord_type(value: str) -> str:
    normalized = value.strip()
    mapping = {
        "ChatRecordText": "text",
        "ChatRecordImage": "image",
        "ChatRecordVideo": "video",
        "ChatRecordFile": "file",
        "ChatRecordLink": "link",
        "ChatRecordLocation": "location",
    }
    return mapping.get(normalized, normalized.lower())


def archive_media_id(payload: dict, msg_type: str) -> str | None:
    value = payload.get(msg_type)
    if isinstance(value, dict):
        return value.get("sdkfileid") or value.get("media_id") or value.get("md5sum")
    return payload.get("sdkfileid") or payload.get("media_id")


def looks_like_groupbuy_product(text: str) -> bool:
    if not text.strip():
        return False
    product_signal = any(keyword in text for keyword in ["团购", "拼单", "接龙", "商品", "鸡蛋", "草莓", "水果", "礼篮"])
    selling_signal = any(keyword in text for keyword in ["优惠", "活动", "下单", "预订", "自提", "配送", "包邮", "斤", "盒", "箱", "份", "个"])
    return product_signal and selling_signal


def miniapp_metadata(payload: dict) -> dict:
    page_path = str(payload.get("pagepath") or payload.get("pagePath") or "").strip()
    query = parse_qs(urlparse(page_path).query)
    city_id = (query.get("cityId") or query.get("city_id") or [""])[0]
    house_code = (query.get("houseCode") or query.get("house_code") or [""])[0]
    appid = str(payload.get("appid") or payload.get("appId") or "").strip()
    display_name = str(payload.get("displayname") or payload.get("displayName") or "").strip()
    description = str(payload.get("description") or payload.get("desc") or "").strip()
    metadata = {
        "appid": appid,
        "username": str(payload.get("username") or "").strip(),
        "title": str(payload.get("title") or "").strip(),
        "description": description,
        "displayName": display_name,
        "pagePath": page_path,
        "houseCode": house_code,
        "cityId": city_id,
        "source": (query.get("source") or [""])[0],
    }
    web_url = miniapp_web_url(metadata)
    if web_url:
        metadata["webUrl"] = web_url
    return metadata


def miniapp_web_url(miniapp: dict) -> str:
    source_text = " ".join(
        str(miniapp.get(key) or "")
        for key in ["appid", "username", "displayName", "description", "source"]
    )
    if "贝壳" not in source_text and "wxcfd8224218167d98" not in source_text:
        return ""
    city_slug = BEIKE_CITY_SLUGS.get(str(miniapp.get("cityId") or ""))
    house_code = str(miniapp.get("houseCode") or "").strip()
    if not city_slug or not house_code:
        return ""
    return f"https://m.ke.com/{city_slug}/ershoufang/{house_code}.html"


def miniapp_text_blocks(miniapp: dict) -> list[str]:
    parts = [
        f"小程序标题：{miniapp.get('title')}" if miniapp.get("title") else "",
        f"小程序来源：{miniapp.get('displayName') or miniapp.get('description')}" if miniapp.get("displayName") or miniapp.get("description") else "",
        f"小程序 appid：{miniapp.get('appid')}" if miniapp.get("appid") else "",
        f"房源编码：{miniapp.get('houseCode')}" if miniapp.get("houseCode") else "",
    ]
    return [part for part in parts if part]
