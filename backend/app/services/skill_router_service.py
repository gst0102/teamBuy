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
PRICE_PATTERN = re.compile(r"(?:¥|￥)?\s*\d+(?:\.\d+)?\s*(?:元/月|/月|每月|万|元|块)?")
PRICE_UNIT_PATTERN = re.compile(r"(?:¥|￥)?\s*\d+(?:\.\d+)?\s*(?:元/月|/月|每月|万|元|块)")
PRICE_KEYWORD_PATTERN = re.compile(r"(?:价格|租金|房租|售价|总价|团购价|底价|月租)\D{0,8}((?:¥|￥)?\s*\d+(?:\.\d+)?\s*(?:元/月|/月|每月|万|元|块)?)")
FIELD_LINE_PATTERN = re.compile(r"^\s*([^:：\s]{1,8})\s*[:：]\s*(.+?)\s*$")
FIELD_BRACKET_LINE_PATTERN = re.compile(r"^\s*[【\[]([^】\]\s]{1,8})[】\]]\s*(.+?)\s*$")
RENTAL_LIFESTYLE_PATTERN = re.compile(r"(押一付[一二三四五六0-9]|押二付一|民水民电|商水商电|独门独户|不养宠|禁宠|🈲️?养宠物|租客|空置|已空|以空|搬空|看房|密码锁|房屋配置|底价|拎包入住)")


PROPERTY_FIELD_ALIASES = {
    "community": ["小区", "楼盘", "项目", "房源", "社区"],
    "layout": ["户型", "房型", "格局"],
    "area": ["面积", "建面", "建筑面积"],
    "price": ["价格", "租金", "房租", "售价", "总价"],
    "utilities": ["水电", "水电物业", "物业", "物业费"],
    "businessArea": ["商圈", "区域", "板块"],
    "address": ["地址", "位置"],
    "serviceFee": ["服务费", "中介费"],
    "paymentMethod": ["押付", "付款", "付款方式", "支付方式"],
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

BUSINESS_OPPORTUNITY_FIELD_ALIASES = {
    "serviceName": ["名称", "业务", "服务", "项目", "产品"],
    "targetAudience": ["适合", "适用", "要求", "工种", "城市", "地区"],
    "serviceContent": ["内容", "范围", "优势", "品类", "类目"],
    "pricingNote": ["价格", "报价", "费用", "优惠", "批发价"],
    "serviceProcess": ["流程", "时效", "截单", "截止", "生效"],
    "serviceArea": ["城市", "地区", "口岸", "区域"],
    "caseHighlights": ["优势", "案例", "资质", "亮点"],
    "contact": ["微信", "电话", "联系方式", "联系人"],
}

CARD_TYPE_LABELS = {
    "property_listing": "房源",
    "groupbuy_product": "商品",
    "service_offer": "商机合作",
    "text_note": "普通笔记",
    "image_ocr": "图片资料",
}

FIELD_LABELS = {
    "community": "小区/楼盘",
    "layout": "户型",
    "area": "面积",
    "price": "价格",
    "utilities": "水电/物业",
    "businessArea": "商圈/区域",
    "address": "地址/位置",
    "serviceFee": "服务费",
    "paymentMethod": "押付方式",
    "remark": "描述/备注",
    "contact": "联系方式",
    "productName": "商品名",
    "spec": "规格",
    "deadline": "截止时间",
    "pickupMethod": "取货/配送",
    "pickupLocation": "取货地点",
    "stockNote": "库存说明",
    "serviceName": "服务/商机名称",
    "targetAudience": "适合对象",
    "serviceContent": "服务/合作内容",
    "pricingNote": "价格/报价",
    "serviceProcess": "流程/时效",
    "serviceArea": "地区/范围",
    "caseHighlights": "优势/背书",
}

PROPERTY_CONVERSION_DEFAULTS = {
    "showContactPhone": True,
    "enableLightScrm": True,
    "collectLeads": True,
    "enableAppointment": True,
    "enablePrivateConsultation": True,
    "enableSharePoster": True,
    "enableGroupRelay": False,
    "enablePaymentPlaceholder": False,
}

GROUPBUY_CONVERSION_DEFAULTS = {
    "showContactPhone": True,
    "enableLightScrm": True,
    "collectLeads": True,
    "enableAppointment": False,
    "enablePrivateConsultation": False,
    "enableSharePoster": True,
    "enableGroupRelay": True,
    "enablePaymentPlaceholder": False,
}

SERVICE_CONVERSION_DEFAULTS = {
    "showContactPhone": True,
    "enableLightScrm": True,
    "collectLeads": True,
    "enableAppointment": True,
    "enablePrivateConsultation": True,
    "enableSharePoster": True,
    "enableGroupRelay": False,
    "enablePaymentPlaceholder": False,
}

MINIAPP_PROPERTY_CONVERSION_DEFAULTS = {
    "showContactPhone": False,
    "enableLightScrm": True,
    "collectLeads": True,
    "enableAppointment": True,
    "enablePrivateConsultation": True,
    "enableSharePoster": True,
    "enableGroupRelay": False,
    "enablePaymentPlaceholder": False,
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
        phone_match = None if content.sourceType == "miniapp_card" else PHONE_PATTERN.search(body)
        location_text = self._extract_prefixed_value(body, "位置：")
        typed_config = self._build_typed_note_config(content, title, body)
        structured_data = typed_config.get("structuredData") if isinstance(typed_config, dict) else {}
        if typed_config.get("cardType") == "groupbuy_product" and isinstance(structured_data, dict):
            product_name = str(structured_data.get("productName") or "").strip()
            if product_name:
                title = product_name
                summary = self._truncate(product_name, 120)
        is_property_note = typed_config.get("cardType") == "property_listing"
        public_phone_match = None if is_property_note else phone_match
        return UserNoteDraftPayload(
            ownerUserId=owner_user_id,
            title=title,
            summary=summary,
            body=body,
            coverUrl=cover_url,
            media=content.media,
            phone=public_phone_match.group(0) if public_phone_match else None,
            locationText=location_text,
            sourceRefs=content.sourceRefs or content.rawMessageIds,
            visibilityConfig={
                **typed_config,
                "showPhone": bool(public_phone_match),
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
                "conversionConfig": self._default_conversion_config("link"),
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
        if content.sourceType == "miniapp_card" and "小程序" not in rule_tags:
            rule_tags.insert(0, "小程序")
        for tag in detection["tags"]:
            if tag not in rule_tags:
                rule_tags.insert(max(len(rule_tags) - 1, 0), tag)
        is_generated = detection["cardType"] in {"property_listing", "groupbuy_product", "service_offer"} and detection["recognitionConfidence"].get("level") == "high"
        structured_data = dict(detection["structuredData"])
        miniapp = content.metadata.get("miniapp") if isinstance(content.metadata, dict) else None
        miniapp_web_url = ""
        miniapp_source_name = ""
        if isinstance(miniapp, dict) and miniapp:
            structured_data["miniapp"] = {
                key: value
                for key, value in miniapp.items()
                if value
            }
            miniapp_web_url = str(miniapp.get("webUrl") or "")
            miniapp_source_name = str(miniapp.get("displayName") or miniapp.get("description") or "小程序")
        internal_miniapp = content.metadata.get("internalMiniapp") if isinstance(content.metadata, dict) else None
        if isinstance(internal_miniapp, dict) and internal_miniapp:
            structured_data["internalMiniapp"] = internal_miniapp
        service_template_config = {
            "displayTemplate": "service_business_opportunity",
            "displayTemplateName": "商机合作",
            "displayTemplateScene": "商机合作",
            "displayTemplateTone": "teal",
        } if detection["cardType"] == "service_offer" else {}
        return {
            **service_template_config,
            "contentMode": "structured_card" if detection["cardType"] in {"property_listing", "groupbuy_product", "service_offer"} else "note",
            "cardType": detection["cardType"],
            "cardState": "generated" if is_generated else "collected",
            "structuredData": structured_data,
            "conversionConfig": self._default_conversion_config(detection["cardType"], content.sourceType, detection["typeSuggestions"]),
            "typeSuggestions": detection["typeSuggestions"],
            "recognitionConfidence": detection["recognitionConfidence"],
            "recognitionExplanation": detection["recognitionExplanation"],
            "sourceType": self._note_source_type(content),
            "systemCategory": "小程序" if content.sourceType == "miniapp_card" and detection["systemCategory"] == "待整理" else detection["systemCategory"],
            "tags": rule_tags,
            "privateData": detection.get("privateData", {}),
            "privateTags": detection.get("privateTags", []),
            "userTags": [],
            "tagLevels": {"rule": rule_tags, "light": [], "deep": []},
            "tagStatus": "rule_done",
            "canDeepOrganize": True,
            "sourceUrl": miniapp_web_url,
            "sourceName": miniapp_source_name,
            "sourceLabel": "贝壳网页" if "贝壳" in miniapp_source_name and miniapp_web_url else "",
            "topicIds": [],
            "topics": [],
        }

    def _default_conversion_config(self, card_type: str, source_type: str | None = None, suggestions: list[dict] | None = None) -> dict:
        if card_type == "property_listing":
            return dict(PROPERTY_CONVERSION_DEFAULTS)
        if card_type == "groupbuy_product":
            return dict(GROUPBUY_CONVERSION_DEFAULTS)
        if card_type == "service_offer":
            return dict(SERVICE_CONVERSION_DEFAULTS)
        if source_type == "miniapp_card" and any(item.get("cardType") == "property_listing" for item in (suggestions or [])):
            return dict(MINIAPP_PROPERTY_CONVERSION_DEFAULTS)
        return {
            "showContactPhone": False,
            "enableLightScrm": True,
            "collectLeads": False,
            "enableAppointment": False,
            "enablePrivateConsultation": False,
            "enableSharePoster": False,
            "enableGroupRelay": False,
            "enablePaymentPlaceholder": False,
        }

    def _detect_card_type(self, title: str, body: str, content: ContentObjectPayload) -> dict:
        property_fields = self._extract_fields(body, PROPERTY_FIELD_ALIASES)
        inferred_community = self._infer_title_community(title, body)
        if inferred_community and "community" not in property_fields:
            property_fields["community"] = inferred_community
        property_fields = self._infer_rental_property_fields(title, body, property_fields)
        groupbuy_fields = self._extract_fields(body, GROUPBUY_FIELD_ALIASES)
        opportunity_fields = self._extract_fields(body, BUSINESS_OPPORTUNITY_FIELD_ALIASES)
        property_score = self._score_property(body, property_fields)
        groupbuy_score = self._score_groupbuy(body, groupbuy_fields)
        opportunity_score = self._score_business_opportunity(body, opportunity_fields)
        images = [media.url for media in content.media if media.type == "image" and media.url]
        parser_hints = content.metadata.get("parserHints", []) if isinstance(content.metadata, dict) else []

        if self._is_high_confidence_property(body, property_fields, property_score, groupbuy_score):
            data = self._build_property_data(title, body, property_fields, images)
            private_data = self._build_property_private_data(body)
            private_tags = self._build_property_private_tags(private_data)
            return {
                "cardType": "property_listing",
                "systemCategory": "房源",
                "structuredData": data,
                "privateData": private_data,
                "privateTags": private_tags,
                "typeSuggestions": [],
                "recognitionConfidence": {"level": "high", "score": property_score, "matchedFields": sorted(property_fields.keys())},
                "recognitionExplanation": self._recognition_explanation(
                    selected_type="property_listing",
                    level="high",
                    source_type=content.sourceType,
                    property_score=property_score,
                    groupbuy_score=groupbuy_score,
                    opportunity_score=opportunity_score,
                    property_fields=property_fields,
                    groupbuy_fields=groupbuy_fields,
                    opportunity_fields=opportunity_fields,
                    parser_hints=parser_hints,
                ),
                "tags": ["房产", "房源"],
            }
        if self._is_high_confidence_groupbuy(body, groupbuy_fields, groupbuy_score, property_score, parser_hints):
            data = self._build_groupbuy_data(title, body, groupbuy_fields, images)
            return {
                "cardType": "groupbuy_product",
                "systemCategory": "团购",
                "structuredData": data,
                "typeSuggestions": [],
                "recognitionConfidence": {"level": "high", "score": groupbuy_score, "matchedFields": sorted(groupbuy_fields.keys())},
                "recognitionExplanation": self._recognition_explanation(
                    selected_type="groupbuy_product",
                    level="high",
                    source_type=content.sourceType,
                    property_score=property_score,
                    groupbuy_score=groupbuy_score,
                    opportunity_score=opportunity_score,
                    property_fields=property_fields,
                    groupbuy_fields=groupbuy_fields,
                    opportunity_fields=opportunity_fields,
                    parser_hints=parser_hints,
                ),
                "tags": ["团购", "商品"],
            }
        if self._is_high_confidence_business_opportunity(body, opportunity_fields, opportunity_score, property_score, groupbuy_score):
            data = self._build_business_opportunity_data(title, body, opportunity_fields, images)
            return {
                "cardType": "service_offer",
                "systemCategory": "服务",
                "structuredData": data,
                "typeSuggestions": [],
                "recognitionConfidence": {"level": "high", "score": opportunity_score, "matchedFields": sorted(opportunity_fields.keys())},
                "recognitionExplanation": self._recognition_explanation(
                    selected_type="service_offer",
                    level="high",
                    source_type=content.sourceType,
                    property_score=property_score,
                    groupbuy_score=groupbuy_score,
                    opportunity_score=opportunity_score,
                    property_fields=property_fields,
                    groupbuy_fields=groupbuy_fields,
                    opportunity_fields=opportunity_fields,
                    parser_hints=parser_hints,
                ),
                "tags": ["服务", "商机", "合作"],
            }

        suggestions = []
        if property_score >= 2:
            suggestions.append(self._type_suggestion("property_listing", property_score, property_fields, "命中房源相关字段或关键词"))
        if groupbuy_score >= 2:
            suggestions.append(self._type_suggestion("groupbuy_product", groupbuy_score, groupbuy_fields, "命中商品/团购相关字段或关键词"))
        if opportunity_score >= 3:
            suggestions.append(self._type_suggestion("service_offer", opportunity_score, opportunity_fields, "命中商机/合作/服务相关关键词"))
        card_type = "image_ocr" if content.media and not body.strip() else "text_note"
        return {
            "cardType": card_type,
            "systemCategory": "图片" if card_type == "image_ocr" else "待整理",
            "structuredData": {"rawText": body, "images": images},
            "typeSuggestions": suggestions,
            "recognitionConfidence": {
                "level": "medium" if suggestions else "low",
                "propertyScore": property_score,
                "groupbuyScore": groupbuy_score,
                "opportunityScore": opportunity_score,
                "matchedFields": {
                    "property": sorted(property_fields.keys()),
                    "groupbuy": sorted(groupbuy_fields.keys()),
                    "opportunity": sorted(opportunity_fields.keys()),
                },
            },
            "recognitionExplanation": self._recognition_explanation(
                selected_type=card_type,
                level="medium" if suggestions else "low",
                source_type=content.sourceType,
                property_score=property_score,
                groupbuy_score=groupbuy_score,
                opportunity_score=opportunity_score,
                property_fields=property_fields,
                groupbuy_fields=groupbuy_fields,
                opportunity_fields=opportunity_fields,
                parser_hints=parser_hints,
            ),
            "tags": [],
        }

    def _type_suggestion(self, card_type: str, score: int, fields: dict, reason: str) -> dict:
        matched_fields = sorted(fields.keys())
        return {
            "cardType": card_type,
            "label": f"可能是{CARD_TYPE_LABELS.get(card_type, '资料')}",
            "confidence": min(score / 6, 0.75),
            "score": score,
            "matchedFields": matched_fields,
            "signals": self._field_signal_labels(matched_fields),
            "reason": reason,
        }

    def _recognition_explanation(
        self,
        selected_type: str,
        level: str,
        source_type: str,
        property_score: int,
        groupbuy_score: int,
        opportunity_score: int,
        property_fields: dict,
        groupbuy_fields: dict,
        opportunity_fields: dict,
        parser_hints: list[str],
    ) -> dict:
        property_matched = sorted(property_fields.keys())
        groupbuy_matched = sorted(groupbuy_fields.keys())
        opportunity_matched = sorted(opportunity_fields.keys())
        candidates = [
            {
                "cardType": "property_listing",
                "label": CARD_TYPE_LABELS["property_listing"],
                "score": property_score,
                "matchedFields": property_matched,
                "signals": self._field_signal_labels(property_matched),
                "reason": self._candidate_reason("property_listing", property_score, property_matched),
            },
            {
                "cardType": "groupbuy_product",
                "label": CARD_TYPE_LABELS["groupbuy_product"],
                "score": groupbuy_score,
                "matchedFields": groupbuy_matched,
                "signals": self._field_signal_labels(groupbuy_matched),
                "reason": self._candidate_reason("groupbuy_product", groupbuy_score, groupbuy_matched),
            },
            {
                "cardType": "service_offer",
                "label": CARD_TYPE_LABELS["service_offer"],
                "score": opportunity_score,
                "matchedFields": opportunity_matched,
                "signals": self._field_signal_labels(opportunity_matched),
                "reason": self._candidate_reason("service_offer", opportunity_score, opportunity_matched),
            },
        ]
        return {
            "level": level,
            "selectedType": selected_type,
            "selectedLabel": CARD_TYPE_LABELS.get(selected_type, "资料"),
            "sourceType": source_type,
            "parserHints": parser_hints,
            "candidates": candidates,
            "summary": self._recognition_summary(level, selected_type, candidates),
        }

    def _candidate_reason(self, card_type: str, score: int, matched_fields: list[str]) -> str:
        label = CARD_TYPE_LABELS.get(card_type, "资料")
        if matched_fields:
            signals = "、".join(self._field_signal_labels(matched_fields)[:4])
            return f"{label}分 {score}，命中 {signals}"
        return f"{label}分 {score}，未命中稳定字段"

    def _recognition_summary(self, level: str, selected_type: str, candidates: list[dict]) -> str:
        if level == "high":
            return f"已高置信识别为{CARD_TYPE_LABELS.get(selected_type, '资料')}。"
        if level == "medium":
            visible = [item for item in candidates if item["score"] >= 2]
            labels = " / ".join(item["label"] for item in visible) or "资料"
            return f"识别不够确定，建议人工确认：{labels}。"
        return "未命中足够稳定的类型信号，先按普通资料保存。"

    def _field_signal_labels(self, fields: list[str]) -> list[str]:
        return [FIELD_LABELS.get(field, field) for field in fields]

    def _extract_fields(self, text: str, aliases: dict[str, list[str]]) -> dict:
        alias_to_key = {alias: key for key, names in aliases.items() for alias in names}
        fields: dict[str, str] = {}
        for line in text.splitlines():
            match = FIELD_LINE_PATTERN.match(line) or FIELD_BRACKET_LINE_PATTERN.match(line)
            if not match:
                continue
            label, value = match.groups()
            key = alias_to_key.get(self._normalize_field_label(label))
            if key and value.strip():
                fields[key] = value.strip()
        return fields

    def _normalize_field_label(self, label: str) -> str:
        return re.sub(r"^[^\u4e00-\u9fffA-Za-z0-9]+", "", label.strip())

    def _infer_title_community(self, title: str, text: str) -> str:
        value = re.sub(r"(租房|出租|房源|急租|转租|整租|合租|公寓|住宅)$", "", title.strip())
        value = re.sub(r"(租房|出租|房源|急租|转租|整租|合租|公寓|住宅)", "", value).strip(" -_｜|·,，")
        if not value or len(value) < 2:
            return ""
        has_property_signal = bool(re.search(r"(户型|一房|两房|三房|三居|面积|平米|价格|租金|总价|售价|万|水电|物业|位置|地址|地铁|服务费|密码锁|毛坯|精装|阳台|南北通透|入学|小学|中学|楼层|小高层)", text))
        if not has_property_signal:
            return ""
        return value

    def _infer_rental_property_fields(self, title: str, text: str, fields: dict) -> dict:
        inferred = dict(fields)
        if inferred.get("layout"):
            inferred["layout"] = str(inferred["layout"]).replace("复试", "复式").strip()
        if inferred.get("price"):
            inferred["price"] = self._clean_property_number(self._clean_price(str(inferred["price"])) or str(inferred["price"]).strip())
        if inferred.get("area"):
            inferred["area"] = str(inferred["area"]).replace("平米", "").replace("平方", "").replace("㎡", "").replace("平", "").strip()
        if "price" not in inferred:
            price = self._first_price(text)
            if price:
                inferred["price"] = self._clean_property_number(price)
        if "area" not in inferred:
            area = self._infer_property_area(text)
            if area:
                inferred["area"] = area
        if "layout" not in inferred:
            layout = self._infer_property_layout(text)
            if layout:
                inferred["layout"] = layout
        if "utilities" not in inferred:
            utilities = self._infer_property_utilities(text)
            if utilities:
                inferred["utilities"] = utilities
        if "paymentMethod" not in inferred:
            payment = self._infer_property_payment_method(text)
            if payment:
                inferred["paymentMethod"] = payment
        if "moveInTime" not in inferred:
            move_in = self._infer_property_move_in_time(text)
            if move_in:
                inferred["moveInTime"] = move_in
        if "remark" not in inferred and RENTAL_LIFESTYLE_PATTERN.search(text):
            inferred["remark"] = self._truncate(text, 160)
        if "community" not in inferred:
            community = self._infer_property_community_from_title(title)
            if community and RENTAL_LIFESTYLE_PATTERN.search(text):
                inferred["community"] = community
        return inferred

    def _infer_property_community_from_title(self, title: str) -> str:
        value = title.strip(" \n\r\t，。,.、")
        if not value or len(value) < 2:
            return ""
        if re.search(r"(小区|楼盘|公寓|苑|园|府|里|城|花园|家园|公馆|一期|二期|三期|四期|栋|幢|号|室)", value):
            return value[:40]
        return ""

    def _infer_property_area(self, text: str) -> str:
        for line in text.splitlines():
            if "面积" in line:
                match = re.search(r"\d+(?:\.\d+)?\s*(?:平米|平方|㎡|平)?", line)
                if match:
                    return match.group(0).strip()
        match = re.search(r"\d+(?:\.\d+)?\s*(?:平米|平方|㎡)", text)
        return match.group(0).strip() if match else ""

    def _infer_property_layout(self, text: str) -> str:
        patterns = [
            r"(精装)?(?:复式|复试|loft|LOFT).{0,4}(?:一房|一室一厅|一室户|两房|二房|三房)?",
            r"(?:公寓)?(?:一房|一室一厅|一室户|两房|二房|三房|次卧|主卧|独卫|独门独户)",
            r"[一二两三四五六七八九十0-9]+(?:室|居室|房)(?:[一二两三四五六七八九十0-9]+厅)?",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(0).strip(" ，。、")
                if value:
                    return value.replace("复试", "复式")[:24]
        return ""

    def _infer_property_utilities(self, text: str) -> str:
        if "民水民电" in text:
            return "民水民电"
        if "商水商电" in text:
            return "商水商电"
        if "水电自缴" in text or "水电物业" in text:
            return "水电自缴"
        return ""

    def _infer_property_payment_method(self, text: str) -> str:
        match = re.search(r"押[一二三四五六0-9]付[一二三四五六0-9]", text)
        if match:
            return match.group(0)
        if "押二付一" in text:
            return "押二付一"
        return ""

    def _infer_property_move_in_time(self, text: str) -> str:
        if re.search(r"随时入住|拎包入住|空置|已空|以空", text):
            return "随时入住"
        match = re.search(r"租客.{0,12}(?:搬空|到期|退租)", text)
        return match.group(0) if match else ""

    def _clean_property_number(self, value: str) -> str:
        match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
        return match.group(0) if match else str(value or "").strip()

    def _is_high_confidence_property(self, text: str, fields: dict, score: int, groupbuy_score: int) -> bool:
        required = {"community", "layout", "price", "businessArea", "address", "area", "paymentMethod", "utilities", "moveInTime"}
        matched = required.intersection(fields.keys())
        has_location = bool({"community", "businessArea", "address"}.intersection(fields.keys())) or bool(re.search(r"(小区|楼盘|郡府|和府|花园|家园|公馆|府|苑|城|位置|地址|地铁|商圈|小学|中学|入学)", text))
        has_shape = bool({"layout", "area"}.intersection(fields.keys())) or bool(re.search(r"(一房|两房|三房|[一二两三四五六七八九十0-9]+室|[一二两三四五六七八九十0-9]+居室|公寓|平米|平方|㎡|平|南北通透|独梯独户|独门独户)", text))
        has_price = "price" in fields or bool(re.search(r"(?:底价|租金|房租|月租)?\D{0,4}(?:\d+|[一二两三四五六七八九十]+)\s*(?:元/月|/月|每月|万|元|块)?", text) and RENTAL_LIFESTYLE_PATTERN.search(text))
        informal_signals = sum(
            1
            for pattern in [
                r"\d+(?:\.\d+)?\s*(?:平米|平方|㎡|平)",
                r"\d+(?:\.\d+)?\s*万",
                r"[一二两三四五六七八九十0-9]+(?:室|居室|房)",
                r"(毛坯|精装|装修|阳台|阴台|南北通透|独梯独户|独门独户|小高层|楼层|采光)",
                r"(小学|中学|入学|学区)",
                r"(押一付[一二三四五六0-9]|押二付一)",
                r"(民水民电|商水商电)",
                r"(不养宠|禁宠|🈲️?养宠物|租客)",
                r"(密码锁|看房|空置|已空|以空|搬空|房屋配置|拎包入住)",
                r"1[3-9]\d{9}",
            ]
            if re.search(pattern, text)
        )
        strong_rental = bool(re.search(r"(押一付[一二三四五六0-9]|押二付一|看房)", text)) and has_location and has_price
        has_enough_fields = len(matched) >= 3 or (informal_signals >= 3 and has_location) or strong_rental
        return score >= 5 and score >= groupbuy_score + 1 and (has_price or informal_signals >= 4) and has_location and (has_shape or strong_rental) and has_enough_fields

    def _is_high_confidence_groupbuy(self, text: str, fields: dict, score: int, property_score: int, parser_hints: list[str] | None = None) -> bool:
        required = {"productName", "price", "spec", "deadline", "pickupMethod", "pickupLocation"}
        matched = required.intersection(fields.keys())
        has_parser_hint = "groupbuy_product" in (parser_hints or [])
        has_product = "productName" in fields or bool(re.search(r"(商品|团购|拼单|规格|现摘|现发|鸡蛋|草莓|水果|礼篮|礼盒|活动|优惠)", text))
        has_price = "price" in fields or bool(PRICE_PATTERN.search(text))
        has_delivery = bool({"pickupMethod", "pickupLocation", "deadline", "spec"}.intersection(fields.keys())) or bool(re.search(r"(自提|配送|包邮|取货|截止|接龙|规格|斤|盒|箱|份|个|礼篮|礼盒)", text))
        has_enough_fields = len(matched) >= 2 or (has_parser_hint and score >= 5)
        return score >= 5 and score > property_score and has_product and (has_price or has_parser_hint) and has_delivery and has_enough_fields

    def _is_high_confidence_business_opportunity(self, text: str, fields: dict, score: int, property_score: int, groupbuy_score: int) -> bool:
        has_contact = "contact" in fields or bool(PHONE_PATTERN.search(text)) or bool(re.search(r"(微信|私聊|咨询|联系|同号)", text))
        has_business_signal = bool(re.search(r"(合作|代理|招募|管理员|批发|货源|工厂|出单|投保|保险|清关|报关|进口|口岸|渠道|招商|资深业务|合作共赢)", text))
        has_service_signal = bool(re.search(r"(时效|截单|生效|适用|优势|欢迎咨询|有意请私聊|有量有价|一手货源|参观看货|服务|办理|代理)", text))
        return score >= 5 and has_contact and has_business_signal and has_service_signal and score >= max(property_score, groupbuy_score)

    def _score_property(self, text: str, fields: dict) -> int:
        score = len(fields)
        keywords = [
            "小区",
            "楼盘",
            "郡府",
            "和府",
            "花园",
            "家园",
            "公馆",
            "户型",
            "租金",
            "总价",
            "售价",
            "水电",
            "民水民电",
            "商水商电",
            "物业",
            "商圈",
            "房源",
            "公寓",
            "一房",
            "两房",
            "三房",
            "二手房",
            "新房",
            "租房",
            "贝壳找房",
            "采光",
            "楼层",
            "拎包入住",
            "毛坯",
            "精装",
            "装修",
            "阳台",
            "阴台",
            "南北通透",
            "独梯独户",
            "独门独户",
            "小高层",
            "押一付一",
            "押一付三",
            "押二付一",
            "不养宠物",
            "禁宠",
            "密码锁",
            "底价",
            "租客",
            "空置",
            "搬空",
            "看房",
            "房屋配置",
            "入学",
            "学区",
            "小学",
            "中学",
        ]
        score += sum(1 for keyword in keywords if keyword in text)
        if "price" in fields or re.search(r"(?:底价|租金|房租|月租)?\D{0,4}(?:\d+|[一二两三四五六七八九十]+)\s*(?:元/月|/月|每月|万|元|块)?", text) and RENTAL_LIFESTYLE_PATTERN.search(text):
            score += 1
        if re.search(r"\d+(?:\.\d+)?\s*(?:平米|平方|㎡|平)", text):
            score += 1
        if re.search(r"[一二两三四五六七八九十0-9]+(?:室|居室|房)", text):
            score += 1
        if PHONE_PATTERN.search(text):
            score += 1
        return score

    def _score_groupbuy(self, text: str, fields: dict) -> int:
        score = len(fields)
        keywords = ["团购", "拼单", "包邮", "自提", "接龙", "截止", "取货", "现摘", "现发", "规格", "优惠", "活动", "斤", "盒", "箱", "份", "个", "鸡蛋", "草莓", "水果", "礼篮", "礼盒"]
        score += sum(1 for keyword in keywords if keyword in text)
        if "price" in fields or PRICE_PATTERN.search(text):
            score += 1
        return score

    def _score_business_opportunity(self, text: str, fields: dict) -> int:
        score = len(fields)
        keywords = [
            "合作",
            "代理",
            "招募",
            "管理员",
            "批发",
            "货源",
            "工厂",
            "出单",
            "投保",
            "保险",
            "清关",
            "报关",
            "进口",
            "口岸",
            "渠道",
            "招商",
            "资深业务",
            "合作共赢",
            "欢迎咨询",
            "有意请私聊",
            "微信同号",
            "有量有价",
            "一手货源",
            "免费包装",
            "截单",
            "生效",
            "时效",
        ]
        score += sum(1 for keyword in keywords if keyword in text)
        if PHONE_PATTERN.search(text) or re.search(r"(微信|电话|联系|咨询|私聊|同号)", text):
            score += 2
        if re.search(r"(城市|青岛|烟台|厦门|宁波|无锡|苏州|南通|大连|珠海|澳门|广东|福建|上海|天津)", text):
            score += 1
        return score

    def _build_property_data(self, title: str, body: str, fields: dict, images: list[str]) -> dict:
        return {
            "community": fields.get("community") or title,
            "layout": fields.get("layout", ""),
            "area": fields.get("area", ""),
            "price": self._clean_property_number(self._clean_price(fields.get("price", "")) or self._first_price(body)),
            "utilities": fields.get("utilities", ""),
            "paymentMethod": fields.get("paymentMethod", ""),
            "moveInTime": fields.get("moveInTime", ""),
            "businessArea": fields.get("businessArea", ""),
            "address": fields.get("address", ""),
            "serviceFee": fields.get("serviceFee", ""),
            "remark": fields.get("remark") or self._truncate(body, 160),
            "contact": "",
            "images": images,
            "rawText": body,
        }

    def _build_property_private_data(self, body: str) -> dict:
        phones = list(dict.fromkeys(PHONE_PATTERN.findall(body or "")))
        private_data: dict = {}
        if phones:
            private_data["upstreamPhones"] = phones
        wechat = self._infer_wechat(body or "", "")
        if wechat:
            private_data["upstreamWechat"] = wechat
        private_lines = [
            line.strip()
            for line in (body or "").splitlines()
            if line.strip() and re.search(r"(上游|房东|渠道|中介费|佣金|密码|看房|带看|租客|不养宠物|禁宠)", line)
        ]
        if private_lines:
            private_data["privateRemark"] = self._truncate("；".join(private_lines), 180)
        return private_data

    def _build_property_private_tags(self, private_data: dict) -> list[str]:
        tags = []
        phones = private_data.get("upstreamPhones") if isinstance(private_data, dict) else []
        if phones:
            tags.append(f"上游电话{len(phones)}个")
        if private_data.get("upstreamWechat"):
            tags.append("上游微信")
        if private_data.get("privateRemark"):
            tags.append("上游备注")
        return tags

    def _build_groupbuy_data(self, title: str, body: str, fields: dict, images: list[str]) -> dict:
        return {
            "productName": fields.get("productName") or self._infer_groupbuy_product_name(body) or title,
            "price": self._clean_price(fields.get("price", "")) or self._first_price(body),
            "spec": fields.get("spec", "") or self._infer_groupbuy_spec(body),
            "deadline": fields.get("deadline", ""),
            "pickupMethod": fields.get("pickupMethod", ""),
            "pickupLocation": fields.get("pickupLocation", ""),
            "stockNote": fields.get("stockNote", ""),
            "remark": fields.get("remark") or self._truncate(body, 160),
            "contact": fields.get("contact") or (PHONE_PATTERN.search(body).group(0) if PHONE_PATTERN.search(body) else ""),
            "images": images,
            "rawText": body,
        }

    def _build_business_opportunity_data(self, title: str, body: str, fields: dict, images: list[str]) -> dict:
        raw_contact = fields.get("contact") or ""
        contact_match = PHONE_PATTERN.search(raw_contact) or PHONE_PATTERN.search(body)
        contact = contact_match.group(0) if contact_match else raw_contact.strip("，。、, ")
        field_service_name = fields.get("serviceName", "")
        if field_service_name and ("首选" in field_service_name or len(re.findall(r"[、,，]", field_service_name)) >= 3):
            field_service_name = ""
        service_name = field_service_name or self._infer_business_opportunity_name(title, body)
        return {
            "serviceName": service_name or title or "商机 / 合作信息",
            "headline": self._infer_business_headline(body) or "先看合作内容、适合对象和联系方式",
            "targetAudience": fields.get("targetAudience") or self._infer_business_audience(body),
            "serviceContent": fields.get("serviceContent") or self._truncate(body, 220),
            "pricingNote": fields.get("pricingNote") or self._infer_business_pricing(body),
            "serviceProcess": fields.get("serviceProcess") or self._infer_business_process(body),
            "caseHighlights": fields.get("caseHighlights") or self._infer_business_highlights(body),
            "serviceArea": fields.get("serviceArea") or self._infer_business_area(body),
            "contact": contact,
            "phone": contact,
            "wechat": self._infer_wechat(body, contact),
            "appointmentNote": "建议先发送需求、品类、城市或合作意向",
            "primaryAction": "咨询合作",
            "secondaryAction": "复制微信",
            "displayTemplate": "service_business_opportunity",
            "images": images,
            "rawText": body,
        }

    def _infer_business_opportunity_name(self, title: str, text: str) -> str:
        clean_title = re.sub(r"^\[[^\]]+\]\s*", "", title.strip())
        if "管理员" in text and ("招募" in text or "需要" in text):
            return "城市群管理员招募"
        if "清关" in text or "报关" in text:
            return self._truncate(clean_title or "进口清关代理", 28)
        if "保险" in text or "出单" in text or "投保" in text:
            return self._truncate(clean_title or "保险出单合作", 28)
        if "工厂" in text and "批发" in text:
            return self._truncate(clean_title or "工厂批发合作", 28)
        candidates = [clean_title]
        for line in text.splitlines():
            value = line.strip(" ~，。,.、")
            if not value:
                continue
            if PHONE_PATTERN.search(value) or value.startswith(("微信", "电话", "联系方式")):
                continue
            candidates.append(value)
        for value in candidates:
            if value and len(value) <= 28:
                return value
        return candidates[0][:28] if candidates and candidates[0] else ""

    def _infer_business_headline(self, text: str) -> str:
        for line in text.splitlines():
            value = line.strip()
            if any(keyword in value for keyword in ["优势", "超低", "一手", "时效", "批发", "招募", "合作", "欢迎咨询"]):
                return self._truncate(value, 42)
        return ""

    def _infer_business_audience(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        selected = [line for line in lines if any(keyword in line for keyword in ["适合", "适用", "工种", "城市", "要求", "需要"])]
        return "、".join(selected[:3]) or "适合想了解合作条件、代理机会、货源或专业服务的客户"

    def _infer_business_pricing(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        selected = [line for line in lines if any(keyword in line for keyword in ["价格", "报价", "批发价", "费用", "优惠", "超低", "有量有价", "免费"])]
        return "；".join(selected[:2])

    def _infer_business_process(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        selected = [line for line in lines if any(keyword in line for keyword in ["时效", "截单", "截止", "生效", "报名", "私聊", "咨询"])]
        return " - ".join(selected[:3]) or "了解合作 - 咨询细节 - 提交信息 - 确认合作"

    def _infer_business_highlights(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        selected = [line for line in lines if any(keyword in line for keyword in ["优势", "一手", "工厂", "资深", "强势", "合作共赢", "可参观", "全套服务"])]
        return "；".join(selected[:3])

    def _infer_business_area(self, text: str) -> str:
        city_pattern = r"(青岛|烟台|厦门|宁波|无锡|苏州|南通|大连|珠海|澳门|广东|福建|上海|天津|北京|杭州|深圳|广州|中港)"
        cities = list(dict.fromkeys(re.findall(city_pattern, text)))
        return " / ".join(cities[:8])

    def _infer_wechat(self, text: str, contact: str) -> str:
        match = re.search(r"(?:微信|微信同号|微信号)\D{0,6}([A-Za-z0-9_-]{5,20}|1[3-9]\d{9})", text)
        if match:
            return match.group(1)
        if contact and "微信" in text:
            return contact
        return ""

    def _infer_groupbuy_product_name(self, text: str) -> str:
        preferred_patterns = [
            r"([\u4e00-\u9fffA-Za-z0-9]{1,12}鸡蛋)",
            r"([\u4e00-\u9fffA-Za-z0-9]{1,12}草莓)",
            r"([\u4e00-\u9fffA-Za-z0-9]{1,12}(?:水果|礼篮|礼盒|牛肉|羊肉|蛋糕))",
        ]
        for pattern in preferred_patterns:
            match = re.search(pattern, text)
            if match:
                return re.sub(r"^(?:我们的|咱们的|精选|新鲜|现摘)", "", match.group(1).strip("，。,.、 "))
        return ""

    def _infer_groupbuy_spec(self, text: str) -> str:
        specs = []
        for pattern in [r"\d+(?:\.\d+)?\s*(?:斤|盒|箱|份|包|瓶|袋)", r"约\s*\d+\s*多个?"]:
            match = re.search(pattern, text)
            if match:
                specs.append(match.group(0).strip())
        return "，".join(dict.fromkeys(specs))

    def _first_price(self, text: str) -> str:
        for line in text.splitlines():
            if "服务费" in line or "中介费" in line:
                continue
            keyword_match = PRICE_KEYWORD_PATTERN.search(line)
            if keyword_match:
                value = self._clean_price(keyword_match.group(1))
                if value:
                    return value
        match = PRICE_UNIT_PATTERN.search(text)
        return match.group(0).strip() if match else ""

    def _clean_price(self, value: str) -> str:
        if not value:
            return ""
        keyword_match = PRICE_KEYWORD_PATTERN.search(value)
        candidate = keyword_match.group(1) if keyword_match else value
        unit_match = PRICE_PATTERN.search(candidate)
        return unit_match.group(0).strip() if unit_match else ""

    def _note_source_type(self, content: ContentObjectPayload) -> str:
        if content.media and not content.textBlocks and not content.links:
            return "media"
        if content.sourceType == "chat_thread":
            return "chat"
        if content.sourceType == "image_ocr":
            return "ocr"
        if content.sourceType == "miniapp_card":
            return "miniapp"
        return "note"

    def _build_rule_tags(self, content: ContentObjectPayload, host: str = "") -> list[str]:
        haystack = "\n".join([content.title or "", *content.textBlocks, host, " ".join(link.url for link in content.links)]).lower()
        tags: list[str] = []
        if content.sourceType == "miniapp_card":
            tags.append("小程序")
        if "mp.weixin.qq.com" in haystack:
            tags.append("微信文章")
        if host:
            tags.append("链接")
        if "贝壳找房" in haystack or "ke.com" in haystack:
            tags.append("贝壳找房")
        keyword_tags = {
            "房源": ["房产", "房源"],
            "小区": ["房产"],
            "二手房": ["房产"],
            "新房": ["房产"],
            "租房": ["房产"],
            "贝壳找房": ["房产"],
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
            "miniapp_card": "input.wecom-miniapp",
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
