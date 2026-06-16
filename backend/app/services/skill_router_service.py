from __future__ import annotations

import re
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
            return self._rule_result("content_to_note", "content-to-note", 0.92, "input.link-article")
        if URL_PATTERN.search(normalized):
            return self._rule_result("content_to_note", "content-to-note", 0.9, "input.link-article")
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
            visibilityConfig={"showPhone": bool(phone_match), "showSource": True},
        )

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
