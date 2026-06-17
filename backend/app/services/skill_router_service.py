from __future__ import annotations

import re
from urllib.parse import urlparse
from datetime import datetime, timezone

from app.schemas.skills import (
    ContentObjectPayload,
    IntentResultPayload,
    RunContentToNoteResponse,
    SkillCommandPayload,
    SkillRunPayload,
    UserNoteDraftPayload,
)
from app.services.helpers import new_id


URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")
PRICE_PATTERN = re.compile(r"(?:¥|￥)?\s*\d+(?:\.\d+)?\s*(?:元|块|/月|每月|包邮)?")
FIELD_LINE_PATTERN = re.compile(r"^\s*([^:：\s]{1,8})\s*[:：]\s*(.+?)\s*$")


PROPERTY_FIELD_ALIASES = {
    "community": ["小区", "楼盘", "项目", "房源", "社区"],
    "layout": ["户型", "房型", "格局"],
    "price": ["价格", "租金", "房租", "售价", "总价"],
    "utilities": ["水电", "水电物业", "物业", "物业费"],
    "businessArea": ["商圈", "区域", "板块"],
    "address": ["地址", "位置"],
    "serviceFee": ["服务费", "中介费"],
    "remark": ["备注", "描述", "亮点"],
    "contact": ["电话", "联系电话", "联系方式", "联系人"],
}

GROUPBUY_FIELD_ALIASES = {
    "productName": ["商品", "商品名", "品名", "名称", "产品"],
    "price": ["价格", "团购价", "售价"],
    "spec": ["规格", "数量", "份量", "重量"],
    "deadline": ["截止", "截止时间", "结束时间"],
    "pickupMethod": ["自提", "取货", "提货", "配送", "发货"],
    "pickupLocation": ["取货地点", "自提点", "地址", "位置"],
    "stockNote": ["库存", "余量", "限量"],
    "remark": ["备注", "描述", "卖点"],
    "contact": ["电话", "联系电话", "联系方式", "联系人"],
}


class SkillRouterService:
    """Deterministic first-pass router for shortcut commands and simple rules."""

    def __init__(self) -> None:
        self._commands = [
            SkillCommandPayload(
                commandText="整理笔记",
                aliases=["笔记", "生成笔记", "资料整理"],
                skillId="content-to-note",
                intent="content_to_note",
                inputAdapter="input.wecom-thread",
            ),
            SkillCommandPayload(
                commandText="整理聊天",
                aliases=["聊天总结", "总结聊天", "整理对话"],
                skillId="content-to-note",
                intent="content_to_note",
                inputAdapter="input.chat-thread",
            ),
            SkillCommandPayload(
                commandText="整理链接",
                aliases=["链接总结", "文章总结", "整理文章"],
                skillId="content-to-note",
                intent="content_to_note",
                inputAdapter="input.link-article",
            ),
            SkillCommandPayload(
                commandText="生成漫画图",
                aliases=["漫画图", "宣传图", "生成长图"],
                skillId="note-to-comic-image",
                intent="note_to_comic_image",
                inputAdapter="input.user-note",
                requiresPayment=True,
            ),
            SkillCommandPayload(
                commandText="创建展示页",
                aliases=["展示页", "我的店铺", "资料店铺"],
                skillId="showcase-builder",
                intent="showcase_builder",
                inputAdapter="input.note-selection",
            ),
            SkillCommandPayload(
                commandText="我的资料",
                aliases=["我的笔记", "资料库", "笔记库"],
                skillId="note-library-core",
                intent="help",
            ),
            SkillCommandPayload(
                commandText="购买套餐",
                aliases=["支付", "续费", "套餐"],
                skillId="billing-core",
                intent="billing",
            ),
        ]

    def list_commands(self) -> list[SkillCommandPayload]:
        return self._commands

    def route(self, text: str, content: ContentObjectPayload | None = None) -> IntentResultPayload:
        normalized = text.strip()
        command = self._match_command(normalized)
        if command:
            return IntentResultPayload(
                intent=command.intent,
                skillId=command.skillId,
                confidence=1,
                source="exact_command",
                needsConfirm=False,
                inputAdapter=command.inputAdapter,
                commandText=command.commandText,
                message="已匹配快捷指令",
            )

        if content and content.sourceType == "link_article":
            return self._rule_result("link_bookmark", "link-bookmark", 0.92, "input.link-article")
        if URL_PATTERN.search(normalized):
            return self._rule_result("link_bookmark", "link-bookmark", 0.9, "input.link-article")
        if self._contains_any(normalized, ["漫画", "长图", "宣传图", "海报"]):
            return self._rule_result("note_to_comic_image", "note-to-comic-image", 0.86, "input.user-note")
        if self._contains_any(normalized, ["展示页", "店铺", "橱窗", "主页"]):
            return self._rule_result("showcase_builder", "showcase-builder", 0.86, "input.note-selection")
        if self._contains_any(normalized, ["购买", "套餐", "支付", "续费", "额度"]):
            return self._rule_result("billing", "billing-core", 0.86, None)
        if self._contains_any(normalized, ["整理", "总结", "归纳", "笔记", "资料", "客户需求"]):
            adapter = self._adapter_for_content(content) if content else "input.manual-text"
            return self._rule_result("content_to_note", "content-to-note", 0.82, adapter)

        return IntentResultPayload(
            intent="unknown",
            skillId=None,
            confidence=0,
            source="confirm_menu",
            needsConfirm=True,
            message="未能确定要执行的功能，请让用户从确认菜单中选择。",
        )

    def run_content_to_note(
        self,
        owner_user_id: str | None,
        content: ContentObjectPayload,
    ) -> RunContentToNoteResponse:
        intent = self._rule_result(
            "content_to_note",
            "content-to-note",
            1,
            self._adapter_for_content(content),
        )
        note = self._build_note_draft(owner_user_id, content)
        now = self._now()
        run = SkillRunPayload(
            id=new_id("skill_run"),
            skillId="content-to-note",
            status="success",
            inputSnapshot=content.model_dump(),
            outputRef=None,
            modelProvider="rule",
            startedAt=now,
            endedAt=now,
        )
        return RunContentToNoteResponse(intent=intent, skillRun=run, noteDraft=note)

    def run_link_bookmark(
        self,
        owner_user_id: str | None,
        content: ContentObjectPayload,
    ) -> RunContentToNoteResponse:
        intent = self._rule_result(
            "link_bookmark",
            "link-bookmark",
            1,
            "input.link-article",
        )
        note = self._build_link_bookmark_draft(owner_user_id, content)
        now = self._now()
        run = SkillRunPayload(
            id=new_id("skill_run"),
            skillId="link-bookmark",
            status="success",
            inputSnapshot=content.model_dump(),
            outputRef=None,
            modelProvider="rule",
            startedAt=now,
            endedAt=now,
        )
        return RunContentToNoteResponse(intent=intent, skillRun=run, noteDraft=note)

    def _match_command(self, text: str) -> SkillCommandPayload | None:
        for command in self._commands:
            candidates = [command.commandText, *command.aliases]
            if text in candidates:
                return command
        return None

    def _rule_result(
        self,
        intent: str,
        skill_id: str,
        confidence: float,
        input_adapter: str | None,
    ) -> IntentResultPayload:
        return IntentResultPayload(
            intent=intent,
            skillId=skill_id,
            confidence=confidence,
            source="rule",
            needsConfirm=False,
            inputAdapter=input_adapter,
            message="已通过规则匹配",
        )

    def _build_note_draft(self, owner_user_id: str | None, content: ContentObjectPayload) -> UserNoteDraftPayload:
        text = "\n".join(block.strip() for block in content.textBlocks if block.strip())
        link_text = "\n".join(self._format_link(link) for link in content.links)
        body_parts = [part for part in [text, link_text] if part]
        body = "\n\n".join(body_parts) or "暂无正文，可在小程序中继续编辑。"
        title = self._guess_title(content, body)
        summary = self._truncate(self._first_sentence(body), 120)
        link_cover_url = next((link.coverUrl for link in content.links if link.coverUrl), None)
        media_cover_url = next((media.url for media in content.media if media.type == "image" and media.url), None)
        cover_url = link_cover_url if content.sourceType == "link_article" else media_cover_url
        cover_url = cover_url or media_cover_url or link_cover_url
        phone_match = PHONE_PATTERN.search(body)
        location_text = self._extract_prefixed_value(body, "位置：")
        typed_config = self._build_typed_note_config(content, title, body)
        return UserNoteDraftPayload(
            ownerUserId=owner_user_id,
            title=title,
            summary=summary,
            body=body,
            coverUrl=cover_url,
            media=content.media,
            phone=phone_match.group(0) if phone_match else None,
            locationText=location_text,
            sourceRefs=content.sourceRefs or content.rawMessageIds,
            visibilityConfig={
                **typed_config,
                "showPhone": bool(phone_match),
                "showSource": True,
            },
        )

    def _build_link_bookmark_draft(self, owner_user_id: str | None, content: ContentObjectPayload) -> UserNoteDraftPayload:
        link = next((item for item in content.links if item.url), None)
        title = self._guess_title(content, link.title if link else "已收藏链接") if link else self._guess_title(content, "已收藏链接")
        description = (link.description or "").strip() if link else ""
        url = link.url if link else ""
        host = urlparse(url).netloc if url else ""
        rule_tags = self._build_rule_tags(content, host)
        body_parts = [part for part in [description, url] if part]
        body = "\n".join(body_parts) or "已收藏，稍后可整理为笔记。"
        summary = description or "已收藏，待整理。"
        return UserNoteDraftPayload(
            ownerUserId=owner_user_id,
            title=title,
            summary=self._truncate(summary, 120),
            body=body,
            coverUrl=link.coverUrl if link else None,
            media=content.media,
            sourceRefs=content.sourceRefs or content.rawMessageIds,
            visibilityConfig={
                "contentMode": "bookmark",
                "cardType": "link",
                "cardState": "collected",
                "structuredData": {
                    "url": url,
                    "domain": host,
                    "title": title,
                    "description": description,
                    "coverUrl": link.coverUrl if link else None,
                    "parseStatus": "meta_done" if link else "pending",
                },
                "typeSuggestions": [],
                "sourceType": "link",
                "systemCategory": "文章",
                "tags": rule_tags,
                "userTags": [],
                "tagLevels": {"rule": rule_tags, "light": [], "deep": []},
                "tagStatus": "rule_done",
                "category": "文章收藏",
                "showSource": True,
                "canDeepOrganize": True,
                "sourceUrl": url,
                "sourceName": host or "链接来源",
                "sourceLabel": "公众号文章" if "mp.weixin.qq.com" in host else "网页链接",
                "openAction": "official_account_article" if "mp.weixin.qq.com" in host else "copy_link",
                "topicIds": [],
                "topics": [],
            },
        )

    def _build_typed_note_config(self, content: ContentObjectPayload, title: str, body: str) -> dict:
        detection = self._detect_card_type(title, body, content)
        rule_tags = self._build_rule_tags(content)
        for tag in detection["tags"]:
            if tag not in rule_tags:
                rule_tags.insert(max(len(rule_tags) - 1, 0), tag)
        return {
            "contentMode": "structured_card" if detection["cardType"] in {"property_listing", "groupbuy_product"} else "note",
            "cardType": detection["cardType"],
            "cardState": "collected",
            "structuredData": detection["structuredData"],
            "typeSuggestions": detection["typeSuggestions"],
            "sourceType": self._note_source_type(content),
            "systemCategory": detection["systemCategory"],
            "tags": rule_tags,
            "userTags": [],
            "tagLevels": {"rule": rule_tags, "light": [], "deep": []},
            "tagStatus": "rule_done",
            "canDeepOrganize": True,
            "topicIds": [],
            "topics": [],
        }

    def _detect_card_type(self, title: str, body: str, content: ContentObjectPayload) -> dict:
        property_fields = self._extract_fields(body, PROPERTY_FIELD_ALIASES)
        groupbuy_fields = self._extract_fields(body, GROUPBUY_FIELD_ALIASES)
        property_score = self._score_property(body, property_fields)
        groupbuy_score = self._score_groupbuy(body, groupbuy_fields)
        images = [media.url for media in content.media if media.type == "image" and media.url]

        if property_score >= 3 and property_score >= groupbuy_score:
            data = self._build_property_data(title, body, property_fields, images)
            return {
                "cardType": "property_listing",
                "systemCategory": "房源",
                "structuredData": data,
                "typeSuggestions": [],
                "tags": ["房产", "房源"],
            }
        if groupbuy_score >= 3 and groupbuy_score > property_score:
            data = self._build_groupbuy_data(title, body, groupbuy_fields, images)
            return {
                "cardType": "groupbuy_product",
                "systemCategory": "团购",
                "structuredData": data,
                "typeSuggestions": [],
                "tags": ["团购", "商品"],
            }

        suggestions = []
        if property_score >= 2:
            suggestions.append({"cardType": "property_listing", "label": "可能是房源信息", "confidence": min(property_score / 5, 0.8)})
        if groupbuy_score >= 2:
            suggestions.append({"cardType": "groupbuy_product", "label": "可能是团购商品", "confidence": min(groupbuy_score / 5, 0.8)})
        card_type = "image_ocr" if content.media and not body.strip() else "text_note"
        return {
            "cardType": card_type,
            "systemCategory": "图片" if card_type == "image_ocr" else "待整理",
            "structuredData": {"rawText": body, "images": images},
            "typeSuggestions": suggestions,
            "tags": [],
        }

    def _extract_fields(self, text: str, aliases: dict[str, list[str]]) -> dict:
        alias_to_key = {alias: key for key, names in aliases.items() for alias in names}
        fields: dict[str, str] = {}
        for line in text.splitlines():
            match = FIELD_LINE_PATTERN.match(line)
            if not match:
                continue
            label, value = match.groups()
            key = alias_to_key.get(label.strip())
            if key and value.strip():
                fields[key] = value.strip()
        return fields

    def _score_property(self, text: str, fields: dict) -> int:
        score = len(fields)
        keywords = ["小区", "户型", "租金", "水电", "物业", "商圈", "房源", "公寓", "一房", "两房", "三房"]
        score += sum(1 for keyword in keywords if keyword in text)
        if "price" in fields or re.search(r"\d+\s*(?:元/月|/月|每月|万|元)", text):
            score += 1
        return score

    def _score_groupbuy(self, text: str, fields: dict) -> int:
        score = len(fields)
        keywords = ["团购", "拼单", "包邮", "自提", "接龙", "截止", "取货", "现摘", "现发", "规格"]
        score += sum(1 for keyword in keywords if keyword in text)
        if "price" in fields or PRICE_PATTERN.search(text):
            score += 1
        return score

    def _build_property_data(self, title: str, body: str, fields: dict, images: list[str]) -> dict:
        return {
            "community": fields.get("community") or title,
            "layout": fields.get("layout", ""),
            "price": fields.get("price") or self._first_price(body),
            "utilities": fields.get("utilities", ""),
            "businessArea": fields.get("businessArea", ""),
            "address": fields.get("address", ""),
            "serviceFee": fields.get("serviceFee", ""),
            "remark": fields.get("remark") or self._truncate(body, 160),
            "contact": fields.get("contact") or (PHONE_PATTERN.search(body).group(0) if PHONE_PATTERN.search(body) else ""),
            "images": images,
            "rawText": body,
        }

    def _build_groupbuy_data(self, title: str, body: str, fields: dict, images: list[str]) -> dict:
        return {
            "productName": fields.get("productName") or title,
            "price": fields.get("price") or self._first_price(body),
            "spec": fields.get("spec", ""),
            "deadline": fields.get("deadline", ""),
            "pickupMethod": fields.get("pickupMethod", ""),
            "pickupLocation": fields.get("pickupLocation", ""),
            "stockNote": fields.get("stockNote", ""),
            "remark": fields.get("remark") or self._truncate(body, 160),
            "contact": fields.get("contact") or (PHONE_PATTERN.search(body).group(0) if PHONE_PATTERN.search(body) else ""),
            "images": images,
            "rawText": body,
        }

    def _first_price(self, text: str) -> str:
        match = PRICE_PATTERN.search(text)
        return match.group(0).strip() if match else ""

    def _note_source_type(self, content: ContentObjectPayload) -> str:
        if content.media and not content.textBlocks and not content.links:
            return "media"
        if content.sourceType == "chat_thread":
            return "chat"
        if content.sourceType == "image_ocr":
            return "media"
        return "note"

    def _build_rule_tags(self, content: ContentObjectPayload, host: str = "") -> list[str]:
        haystack = "\n".join([content.title or "", *content.textBlocks, host, " ".join(link.url for link in content.links)]).lower()
        tags: list[str] = []
        if "mp.weixin.qq.com" in haystack:
            tags.append("微信文章")
        if host:
            tags.append("链接")
        keyword_tags = {
            "房源": ["房产", "房源"],
            "小区": ["房产"],
            "团购": ["团购"],
            "拼单": ["团购"],
            "草莓": ["草莓", "水果"],
            "露营": ["露营", "出行"],
            "亲子": ["亲子"],
            "装备": ["装备"],
            "合同": ["合同"],
            "python": ["Python"],
        }
        for keyword, values in keyword_tags.items():
            if keyword in haystack:
                tags.extend(values)
        tags.append("待整理")
        return list(dict.fromkeys(tags))

    def _guess_title(self, content: ContentObjectPayload, body: str) -> str:
        if content.title and content.title.strip():
            return self._truncate(content.title.strip(), 40)
        for link in content.links:
            if link.title:
                return self._truncate(link.title.strip(), 40)
        first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
        return self._truncate(first_line, 40) or "未命名笔记"

    def _format_link(self, link) -> str:
        parts = [part for part in [link.title, link.description, link.url] if part]
        return "\n".join(parts)

    def _extract_prefixed_value(self, text: str, prefix: str) -> str | None:
        for line in text.splitlines():
            if line.startswith(prefix):
                value = line.removeprefix(prefix).strip()
                if value:
                    return value
        return None

    def _first_sentence(self, text: str) -> str:
        for separator in ["。", "\n", ".", "！", "？"]:
            if separator in text:
                return text.split(separator, 1)[0].strip() + separator
        return text.strip()

    def _adapter_for_content(self, content: ContentObjectPayload | None) -> str:
        if not content:
            return "input.manual-text"
        mapping = {
            "wecom_thread": "input.wecom-thread",
            "chat_thread": "input.chat-thread",
            "link_article": "input.link-article",
            "manual_text": "input.manual-text",
            "image_ocr": "input.image-ocr",
        }
        return mapping.get(content.sourceType, "input.manual-text")

    def _contains_any(self, text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _truncate(self, text: str, limit: int) -> str:
        value = text.strip()
        return value if len(value) <= limit else value[: limit - 1] + "..."

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
