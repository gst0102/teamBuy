from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


NOTE_SHARE_CARD_STYLE_ID = "share_card_backend_v8"
NOTE_SHARE_CARD_RENDER_REVISION = "business_card_layout_v4"
MUTUAL_TASK_SHARE_CARD_STYLE_ID = "mutual_task_backend_v5"
SHARE_CARD_WIDTH = 750
SHARE_CARD_HEIGHT = 600
SHARE_CARD_FOOTER = "少来回解释，资料一页讲清"
BUSINESS_CARD_FOOTER = "点击查看完整名片"
UNIVERSAL_INFO_ARTWORK_PATH = (
    Path(__file__).resolve().parents[1] / "static" / "share-card-assets" / "universal-info-artwork.png"
)


class ShareCardRenderError(ValueError):
    """Raised when a server-side share card cannot be rendered safely."""


class ShareCardRenderer:
    """Render the small, public-safe share image from server-owned entities.

    The renderer deliberately accepts model-like objects instead of a client
    supplied source dictionary. This keeps the image content authoritative on
    the API side while allowing the layout to evolve independently of the
    mini-program canvas implementation.
    """

    width = SHARE_CARD_WIDTH
    height = SHARE_CARD_HEIGHT

    def __init__(self, font_path: str | Path | None = None):
        self.font_path = str(font_path or "").strip()
        self._font_cache: dict[tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
        self._universal_info_artwork: Image.Image | None = None

    def render_note(
        self,
        note: Any,
        owner: Any = None,
        storage_service: Any = None,
        *,
        include_owner_contacts: bool = False,
    ) -> bytes:
        data = self._as_dict(note)
        config = self._as_dict(data.get("visibilityConfig"))
        structured = self._as_dict(config.get("structuredData"))
        card_type = str(config.get("cardType") or data.get("cardType") or "text_note").strip().lower()
        image_url = self._note_image_url(data, structured, storage_service)
        image_is_managed = bool(
            image_url
            and storage_service
            and storage_service.is_managed_url(image_url)
        )
        if card_type == "business_card":
            image = self._render_business_card(
                data,
                structured,
                owner,
                image_url,
                storage_service,
                config=config,
                include_owner_contacts=include_owner_contacts,
            )
        elif (card_type == "image_ocr" and image_is_managed) or (image_is_managed and card_type in {"text_note", "link", "article"}):
            image = self._render_image_note(data, structured, card_type, image_url, storage_service)
        else:
            image = self._render_info_card(data, structured, card_type, image_url if image_is_managed else "", storage_service)
        return self._encode(image)

    def render_mutual_task(self, task: Any, storage_service: Any = None) -> bytes:
        data = self._as_dict(task)
        task_kind = str(data.get("taskKind") or "ordinary").strip().lower()
        if task_kind not in {"miniapp", "ordinary", "wool"}:
            task_kind = "ordinary"
        # A task may contain a client-visible URL that is not a server-owned
        # media asset (for example, an old temporary URL or an external
        # article image). It can still be shown in the task detail, but the
        # backend share renderer must not let that URL abort the whole share
        # snapshot. Only use an image that this storage backend can read;
        # otherwise render the intentional no-image task visual.
        image_url = self._task_image_url(data, storage_service)
        image = Image.new("RGB", (self.width, self.height), "#fff8f0")
        draw = ImageDraw.Draw(image)
        accent = "#e8692e" if task_kind != "wool" else "#7b4bd9"
        pale = "#fff0e3" if task_kind != "wool" else "#f0e8ff"
        self._rounded(draw, (30, 28, 720, 572), 30, "#ffffff", outline="#f0ded1", width=3)
        self._pill(draw, (54, 54, 190, 96), self._task_badge(task_kind), pale, accent, bold=True, text_size=26)
        reward = self._task_reward(data, task_kind)
        self._pill(draw, (535, 54, 696, 96), reward, "#fff1e3", accent, bold=True, text_size=26)
        self._text_block(draw, data.get("title") or "互帮互助任务", (54, 124), 44, "#19202f", 630, max_lines=1)
        summary = self._task_summary(data, task_kind)
        self._text_block(draw, summary, (54, 174), 34, "#657080", 630, max_lines=1)

        facts = self._task_facts(data, task_kind)
        x = 54
        for fact in facts[:3]:
            width = max(136, min(215, self._measure(fact, 29) + 38))
            self._pill(draw, (x, 250, x + width, 292), fact, "#f4f7fb", accent, bold=False, text_size=29)
            x += width + 12

        image_top = 318
        if image_url:
            try:
                self._paste_managed_image(image, image_url, (54, image_top, 696, 470), storage_service, rounded=20)
            except ShareCardRenderError:
                # A previously managed asset can still be missing after
                # cleanup or an interrupted upload. Keep the task shareable
                # and use the same no-image visual as an external URL.
                image_url = ""
        if not image_url:
            self._rounded(draw, (54, image_top, 696, 470), 20, "#f7f9fc", outline="#e1e6ed", width=2)
            description = self._clip(data.get("description") or "按任务说明完成后提交记录", 84)
            self._text_block(draw, description, (82, image_top + 46), 31, "#3e4857", 580, max_lines=3)

        footer = "查看福利说明 · 觉得有用再参与" if task_kind == "wool" else "更多人可参与，选任务就能轻松互动"
        self._rounded(draw, (54, 494, 696, 548), 18, pale)
        self._text(draw, footer, (375, 521), 38, accent, bold=True, anchor="mm")
        return self._encode(image)

    def _render_business_card(
        self,
        data,
        structured,
        owner,
        avatar_url,
        storage_service,
        config=None,
        include_owner_contacts=False,
    ):
        image = Image.new("RGB", (self.width, self.height), "#eff7ff")
        draw = ImageDraw.Draw(image)
        self._rounded(draw, (28, 28, 722, 572), 32, "#ffffff", outline="#d9e8f5", width=3)
        self._pill(draw, (54, 54, 190, 96), "电子名片", "#e6f4ff", "#2273c8", bold=True, text_size=23)
        self._text(draw, "资料整理助手", (654, 75), 23, "#75849a", bold=True, anchor="rm")

        avatar_box = (62, 138, 222, 298)
        self._paste_avatar(image, avatar_url, avatar_box, storage_service, fallback=self._initials(data, owner))
        owner_data = self._as_dict(owner)
        name = self._first(structured, "name", "displayName", "contactName") or self._first(owner_data, "nickname") or data.get("title") or "我的名片"
        role = self._first(structured, "role", "jobTitle", "position", "title")
        company = self._first(structured, "company", "companyName", "organization")
        service_scope = self._first(structured, "serviceScope", "service", "industry")
        if not service_scope:
            keywords = structured.get("serviceKeywords")
            service_scope = "、".join(str(item).strip() for item in keywords if str(item).strip()) if isinstance(keywords, list) else ""
        bio = self._first(structured, "bio", "introduction", "headline") or data.get("summary") or ""
        self._text(draw, self._clip(name, 12), (260, 150), 46, "#182538", bold=True)
        info_y = 208
        role_company = self._clip(" · ".join(item for item in [role, company] if item), 16)
        if role_company:
            self._text(draw, role_company, (260, info_y), 29, "#6b7b90")
            info_y += 36
        if service_scope:
            self._text_block(draw, service_scope, (260, info_y), 29, "#2b78bf", 410, max_lines=1)
            info_y += 36
        contact_line = self._business_contact_line(
            structured,
            owner_data,
            config or {},
            allow_full_contacts=include_owner_contacts,
        )
        if contact_line:
            self._text_block(draw, contact_line, (260, info_y), 30, "#4f6074", 410, max_lines=1)
        self._rounded(draw, (54, 326, 696, 454), 22, "#f6fbff")
        self._text(draw, "我能提供", (80, 350), 29, "#2273c8", bold=True)
        self._text_block(draw, self._clip(bio or "欢迎查看我的服务与合作信息", 20, suffix="..."), (80, 390), 29, "#4f6074", 575, max_lines=1)
        self._rounded(draw, (54, 486, 696, 548), 18, "#e9f5ff")
        self._text(draw, BUSINESS_CARD_FOOTER, (375, 517), 38, "#2273c8", bold=True, anchor="mm")
        return image

    def _business_contact_line(self, structured, owner_data, config, *, allow_full_contacts=False):
        """Return a safe contact line for the static card image."""
        structured = self._as_dict(structured)
        owner_data = self._as_dict(owner_data)
        sales_profile = self._as_dict(owner_data.get("salesProfile"))
        conversion = self._as_dict(config.get("conversionConfig"))

        phone = self._first(structured, "phone", "contactPhone", "mobile", "tel", "contact")
        if not phone:
            phone = self._first(sales_profile, "phone", "contactPhone") or self._first(owner_data, "phone")
        wechat = self._first(structured, "wechat", "contactWechat", "customerWechat", "weixin", "wx")
        if not wechat:
            wechat = self._first(sales_profile, "wechat", "contactWechat") or self._first(owner_data, "wechat")
        email = self._first(structured, "email", "mail") or self._first(sales_profile, "email")
        if conversion.get("showContactPhone") is False:
            phone = ""
        if conversion.get("enablePrivateConsultation") is False:
            wechat = ""

        if self._business_market_enabled(config) and not allow_full_contacts:
            # The share image is public, so never put the complete contact in
            # it. Still show a useful phone hint when the owner has opted into
            # phone display; the detail page remains the unlock boundary.
            return (
                f"电话 {self._mask_phone(phone)} · 详情页查看"
                if phone
                else "联系方式已保护 · 详情页查看"
            )

        values = []
        for label, value in (("电话", phone), ("微信", wechat), ("邮箱", email)):
            if value and value not in {item[1] for item in values}:
                values.append((label, value))
        return " · ".join(f"{label} {value}" for label, value in values[:2])

    @staticmethod
    def _business_market_enabled(config):
        opportunity = config.get("businessOpportunity") if isinstance(config, dict) else None
        if not isinstance(opportunity, dict):
            return False
        scoped_pairs = (("resourceEnabled", "resourceDiscoverable"), ("intentEnabled", "intentDiscoverable"))
        if any(key in opportunity for pair in scoped_pairs for key in pair):
            return any(
                opportunity.get(enabled) is not False and opportunity.get(discoverable) is not False
                for enabled, discoverable in scoped_pairs
                if enabled in opportunity or discoverable in opportunity
            )
        return (
            ("enabled" in opportunity or "discoverable" in opportunity)
            and opportunity.get("enabled") is not False
            and opportunity.get("discoverable") is not False
        )

    def _render_image_note(self, data, structured, card_type, image_url, storage_service):
        image = Image.new("RGB", (self.width, self.height), "#f7fafc")
        draw = ImageDraw.Draw(image)
        accent, pale = self._info_palette(card_type)
        self._draw_info_shell(draw, accent)
        self._draw_info_header(draw, card_type, True, accent, pale)

        visual_box = (42, 124, 348, 500)
        detail_box = (372, 124, 708, 500)
        self._paste_managed_image(image, image_url, visual_box, storage_service, rounded=20)
        self._render_info_details(
            draw,
            data,
            structured,
            card_type,
            detail_box,
            accent,
            include_price=False,
        )
        self._draw_info_footer(draw, accent, pale, SHARE_CARD_FOOTER)
        return image

    def _render_info_card(self, data, structured, card_type, image_url, storage_service):
        image = Image.new("RGB", (self.width, self.height), "#f7fafc")
        draw = ImageDraw.Draw(image)
        accent, pale = self._info_palette(card_type)
        self._draw_info_shell(draw, accent)
        self._draw_info_header(draw, card_type, bool(image_url), accent, pale)

        visual_box = (42, 124, 348, 500)
        detail_box = (372, 124, 708, 500)
        if image_url:
            self._paste_managed_image(image, image_url, visual_box, storage_service, rounded=20)
        else:
            self._paste_universal_info_artwork(image, visual_box)
        self._render_info_details(
            draw,
            data,
            structured,
            card_type,
            detail_box,
            accent,
            include_price=True,
        )
        self._draw_info_footer(draw, accent, pale, SHARE_CARD_FOOTER)
        return image

    def _draw_info_shell(self, draw, accent):
        self._rounded(draw, (28, 28, 722, 572), 30, "#ffffff", outline=accent, width=3)

    def _draw_info_header(self, draw, card_type, has_image, accent, pale):
        badge = self._info_badge(card_type)
        badge_width = max(150, min(245, self._measure(badge, 23) + 48))
        self._pill(draw, (48, 48, 48 + badge_width, 92), badge, pale, accent, bold=True, text_size=27)
        status_left = 48 + badge_width + 14
        status_fill = "#edf5ff" if has_image else "#f4f7fb"
        self._pill(draw, (status_left, 48, status_left + 96, 92), "有图" if has_image else "无图", status_fill, accent, bold=True, text_size=26)

    def _draw_info_footer(self, draw, accent, pale, footer):
        self._rounded(draw, (42, 520, 708, 560), 16, accent)
        self._text(draw, footer, (375, 540), 38, "#ffffff", bold=True, anchor="mm")

    def _render_info_details(self, draw, data, structured, card_type, box, accent, include_price=True):
        left, top, right, bottom = box
        title = self._clip(data.get("title") or self._info_badge(card_type), 20)
        summary = str(data.get("summary") or "").strip()
        body = data.get("body") or ""
        blocks = data.get("contentBlocks") if isinstance(data.get("contentBlocks"), list) else []
        body_text = body or next((item.get("text") for item in blocks if isinstance(item, dict) and item.get("type") == "text"), "")
        facts = self._note_facts(card_type, structured, data)
        price = self._note_price(card_type, structured) if include_price else ""
        detail_facts = facts[1:] if price and facts else facts

        self._text_block(draw, title, (left, top + 14), 38, "#172337", right - left, max_lines=1, bold=True)
        line_top = top + 100
        draw.rounded_rectangle((left, line_top, left + 72, line_top + 8), radius=4, fill=accent)
        content_top = line_top + 36
        if price:
            self._text_block(draw, price, (left, content_top), 52, accent, right - left, max_lines=1, bold=True)
            content_top += 78

        secondary = summary if summary and summary != title else ""
        if not secondary and body_text and body_text != title:
            secondary = body_text
        if secondary:
            self._text_block(draw, self._clip(secondary, 20), (left, content_top), 29, "#526276", right - left, max_lines=2)
            content_top += 84

        remaining = [item for item in detail_facts if str(item).strip() and str(item).strip() not in {title, secondary}]
        if remaining:
            facts_text = self._clip(" · ".join(remaining[:3]), 20)
            self._text_block(draw, facts_text, (left, min(content_top, bottom - 78)), 28, "#526276", right - left, max_lines=2)
        elif not secondary:
            self._text_block(draw, "点击查看完整资料", (left, content_top), 29, "#526276", right - left, max_lines=2)

    def _info_badge(self, card_type):
        return {
            "property_listing": "房源资料",
            "groupbuy_product": "电商资料",
            "product": "电商资料",
            "service_offer": "服务资料",
            "service": "服务资料",
            "manufacturing": "制造业资料",
            "manufacturing_offer": "制造业资料",
            "link": "链接资料",
            "article": "文章资料",
            "image_ocr": "图片资料",
            "text_note": "普通资料",
        }.get(card_type, "普通资料")

    def _note_image_url(self, data, structured, storage_service=None) -> str:
        candidates = [data.get("coverUrl"), structured.get("coverUrl"), structured.get("imageUrl")]
        blocks = data.get("contentBlocks") if isinstance(data.get("contentBlocks"), list) else []
        media = data.get("media") if isinstance(data.get("media"), list) else []
        candidates.extend(item.get("url") for item in blocks if isinstance(item, dict) and item.get("type") == "image")
        candidates.extend(item.get("url") for item in media if isinstance(item, dict) and item.get("type") == "image")
        normalized = [str(item).strip() for item in candidates if str(item or "").strip()]
        if storage_service:
            managed = next((item for item in normalized if storage_service.is_managed_url(item)), "")
            if managed:
                return managed
        return normalized[0] if normalized else ""

    def _task_image_url(self, data, storage_service=None) -> str:
        blocks = []
        blocks.extend(data.get("contentBlocks") if isinstance(data.get("contentBlocks"), list) else [])
        if str(data.get("taskKind") or "") != "wool":
            blocks.extend(data.get("acceptanceCriteriaBlocks") if isinstance(data.get("acceptanceCriteriaBlocks"), list) else [])
        candidates = [
            str(item.get("url") or item.get("displayUrl") or "").strip()
            for item in blocks
            if isinstance(item, dict)
            and item.get("type") == "image"
            and str(item.get("url") or item.get("displayUrl") or "").strip()
        ]
        if storage_service:
            return next(
                (value for value in candidates if storage_service.is_managed_url(value)),
                "",
            )
        return candidates[0] if candidates else ""

    def _note_facts(self, card_type, structured, data):
        if card_type == "property_listing":
            keys = ("layout", "area", "address")
        elif card_type in {"groupbuy_product", "product"}:
            variants = structured.get("variants") if isinstance(structured.get("variants"), list) else []
            first_variant = next((item for item in variants if isinstance(item, dict) and str(item.get("name") or "").strip()), {})
            keys = (
                ("spec",) if str(structured.get("spec") or "").strip() else (),
                ("pickupMethod",) if str(structured.get("pickupMethod") or "").strip() else (),
                ("deadline",) if str(structured.get("deadline") or "").strip() else (),
            )
            values = [self._note_price(card_type, structured)]
            if first_variant.get("name") and not str(structured.get("spec") or "").strip():
                values.append(str(first_variant["name"]).strip())
            for key_group in keys:
                for key in key_group:
                    value = str(structured.get(key) or "").strip()
                    if value:
                        values.append(value)
            return [value for value in values if value]
        elif card_type in {"service_offer", "service"}:
            keys = ("targetAudience", "pricingNote", "scene")
        else:
            keys = ()
        values = [self._note_price(card_type, structured)] if card_type == "property_listing" else []
        values.extend(str(structured.get(key) or "").strip() for key in keys if str(structured.get(key) or "").strip())
        return [value for value in values if value]

    def _info_palette(self, card_type):
        palettes = {
            "property_listing": ("#258c68", "#e7f7f0"),
            "groupbuy_product": ("#e58c28", "#fff1df"),
            "product": ("#e58c28", "#fff1df"),
            "service_offer": ("#4775dc", "#eaf0ff"),
            "service": ("#4775dc", "#eaf0ff"),
            "manufacturing": ("#e87920", "#fff0e1"),
            "manufacturing_offer": ("#e87920", "#fff0e1"),
            "link": ("#2572d3", "#eaf3ff"),
            "article": ("#2572d3", "#eaf3ff"),
        }
        return palettes.get(card_type, ("#2572d3", "#eaf3ff"))

    def _note_price(self, card_type, structured):
        if card_type not in {"property_listing", "groupbuy_product", "product"}:
            return ""
        value = str(structured.get("price") or "").strip()
        if not value and card_type in {"groupbuy_product", "product"}:
            variants = structured.get("variants") if isinstance(structured.get("variants"), list) else []
            priced_variants = [
                item for item in variants
                if isinstance(item, dict)
                and str(item.get("priceFen") or "").strip() != ""
                and str(item.get("priceFen")) not in {"nan", "None"}
            ]
            available = [item for item in priced_variants if item.get("stockStatus") != "sold_out"] or priced_variants
            cents = [int(item.get("priceFen")) for item in available if str(item.get("priceFen")).lstrip("-").isdigit() and int(item.get("priceFen")) >= 0]
            if cents:
                amount = cents and min(cents) / 100
                amount_text = f"{amount:.2f}".rstrip("0").rstrip(".")
                return f"¥{amount_text}{' 起' if len(priced_variants) > 1 else ''}"
        if not value:
            return ""
        if card_type == "property_listing" and not any(mark in value for mark in ("元", "万", "/月", "每月", "¥", "￥")):
            listing_mode = str(structured.get("listingMode") or structured.get("dealType") or "rent").strip().lower()
            return f"{value}{'万元' if listing_mode in {'sale', 'sell', '出售'} else '元/月'}"
        if card_type in {"groupbuy_product", "product"} and not any(mark in value for mark in ("¥", "￥", "元", "万")):
            return f"¥{value}"
        return value

    def _paste_universal_info_artwork(self, image, box):
        """Paste the approved no-image artwork into the real-image slot."""
        left, top, right, bottom = box
        artwork = self._load_universal_info_artwork().copy()
        max_width = max(1, right - left - 16)
        max_height = max(1, bottom - top - 16)
        artwork.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        paste_x = left + ((right - left) - artwork.width) // 2
        paste_y = top + ((bottom - top) - artwork.height) // 2
        image.paste(artwork, (paste_x, paste_y), artwork)

    def _load_universal_info_artwork(self):
        if self._universal_info_artwork is None:
            if not UNIVERSAL_INFO_ARTWORK_PATH.is_file():
                raise ShareCardRenderError(
                    f"无图资料插画资源不存在: {UNIVERSAL_INFO_ARTWORK_PATH}"
                )
            try:
                with Image.open(UNIVERSAL_INFO_ARTWORK_PATH) as source:
                    self._universal_info_artwork = source.convert("RGBA")
            except Exception as exc:
                raise ShareCardRenderError("无图资料插画资源无法读取") from exc
        return self._universal_info_artwork

    def _task_badge(self, task_kind):
        return {"miniapp": "小程序任务", "wool": "羊毛福利", "ordinary": "普通任务"}.get(task_kind, "互助任务")

    def _task_reward(self, data, task_kind):
        if task_kind == "wool":
            policy = self._as_dict(data.get("woolPolicy"))
            fee = int(policy.get("unlockFeePoints") or 0)
            return f"查看 {fee} 分" if fee > 0 else "免费查看"
        return f"+{int(data.get('executorReward') or 0)} 分"

    def _task_facts(self, data, task_kind):
        if task_kind == "wool":
            policy = self._as_dict(data.get("woolPolicy"))
            fee = int(policy.get("unlockFeePoints") or 0)
            return [f"解锁 {fee} 分" if fee > 0 else "免费查看", "按说明使用", data.get("deadlineText") or "长期开放"]
        repeat = "每天一次" if data.get("repeatPolicy") == "daily" else "每人一次"
        return [repeat, data.get("deadlineText") or "长期开放", "更多人可参与"]

    def _task_summary(self, data, task_kind):
        summary = str(data.get("description") or "").strip()
        if summary and not summary.startswith("#小程序://") and not summary.startswith("http"):
            return summary
        if task_kind == "miniapp":
            return "打开目标小程序，按任务说明体验后返回提交记录"
        if task_kind == "wool":
            return "查看福利说明，确认适合自己后再按步骤使用"
        return "按任务说明完成后提交文字或图片材料"

    def _paste_managed_image(self, canvas, url, box, storage_service, rounded=0):
        source = self._load_image(url, storage_service)
        if source is None:
            raise ShareCardRenderError("分享图所需图片暂时不可用，请稍后重试")
        fitted = ImageOps.fit(source, (box[2] - box[0], box[3] - box[1]), method=Image.Resampling.LANCZOS)
        if rounded:
            mask = Image.new("L", fitted.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, fitted.width, fitted.height), radius=rounded, fill=255)
            canvas.paste(fitted, (box[0], box[1]), mask)
        else:
            canvas.paste(fitted, (box[0], box[1]))

    def _paste_avatar(self, canvas, url, box, storage_service, fallback):
        source = self._load_image(url, storage_service, required=False) if url else None
        size = (box[2] - box[0], box[3] - box[1])
        avatar = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS) if source else Image.new("RGB", size, "#dcefff")
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size[0], size[1]), fill=255)
        canvas.paste(avatar, (box[0], box[1]), mask)
        draw = ImageDraw.Draw(canvas)
        draw.ellipse((box[0], box[1], box[2], box[3]), outline="#7db8e2", width=4)
        if not source:
            self._text(draw, fallback, ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), 40, "#2273c8", bold=True, anchor="mm")

    def _load_image(self, url, storage_service, required=True):
        value = str(url or "").strip()
        if not value or not storage_service:
            return None
        try:
            managed = bool(storage_service.is_managed_url(value))
        except Exception:
            managed = False
        if not managed:
            return None
        content = storage_service.read_bytes(value)
        if not content:
            if required:
                raise ShareCardRenderError("分享图所需图片暂时不可用，请稍后重试")
            return None
        try:
            source = Image.open(BytesIO(content)).convert("RGB")
            source.load()
            return source
        except Exception as exc:
            raise ShareCardRenderError("分享图所需图片不是有效图片") from exc

    def _encode(self, image):
        output = BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=92, optimize=True)
        return output.getvalue()

    def _font(self, size, bold=False):
        key = (size, bold)
        if key in self._font_cache:
            return self._font_cache[key]
        candidates = []
        if self.font_path:
            candidates.append(self.font_path)
        candidates.extend([
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansSC-Bold.otf" if bold else "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf",
            "/app/fonts/NotoSansSC-Bold.ttf" if bold else "/app/fonts/NotoSansSC-Regular.ttf",
            "/app/fonts/NotoSansSC-Regular.ttf",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc" if bold else "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ])
        for path in candidates:
            try:
                if Path(path).exists():
                    font = ImageFont.truetype(path, size=size)
                    self._font_cache[key] = font
                    return font
            except Exception:
                continue
        font = ImageFont.load_default()
        self._font_cache[key] = font
        return font

    def _text(self, draw, value, xy, size, fill, bold=False, anchor=None):
        draw.text(xy, str(value or ""), font=self._font(size, bold), fill=fill, anchor=anchor)

    def _text_block(self, draw, value, xy, size, fill, max_width, max_lines=2, bold=False):
        lines = self._wrap(str(value or ""), size, max_width, max_lines)
        line_height = size + 10
        for index, line in enumerate(lines):
            self._text(draw, line, (xy[0], xy[1] + index * line_height), size, fill, bold=bold)

    def _wrap(self, value, size, max_width, max_lines):
        chars = []
        lines = []
        current = ""
        for char in value.replace("\n", " "):
            candidate = current + char
            if current and self._measure(candidate, size) > max_width:
                lines.append(current)
                current = char
                if len(lines) >= max_lines:
                    break
            else:
                current = candidate
        if len(lines) < max_lines and current:
            lines.append(current)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        if len(lines) == max_lines and value and "".join(lines) != value.replace("\n", " "):
            lines[-1] = self._clip(lines[-1], max(1, max_width // max(size, 1)))
        return lines or [""]

    def _measure(self, value, size):
        font = self._font(size)
        box = font.getbbox(str(value or ""))
        return box[2] - box[0]

    def _clip(self, value, max_chars, suffix="…"):
        text = str(value or "").strip()
        if len(text) <= max_chars:
            return text
        suffix = str(suffix or "…")
        if len(suffix) >= max_chars:
            return suffix[:max_chars]
        return text[: max(1, max_chars - len(suffix))] + suffix

    def _pill(self, draw, box, value, background, foreground, bold=False, text_size=20):
        self._rounded(draw, box, 20, background)
        self._text(draw, self._clip(value, 16), ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), text_size, foreground, bold=bold, anchor="mm")

    @staticmethod
    def _rounded(draw, box, radius, fill, outline=None, width=1):
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width if outline else 1)

    @staticmethod
    def _as_dict(value):
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        return {}

    @staticmethod
    def _first(data, *keys):
        return next((str(data.get(key) or "").strip() for key in keys if str(data.get(key) or "").strip()), "")

    @staticmethod
    def _mask_phone(value):
        text = str(value or "").strip()
        if len(text) <= 7:
            return text
        return f"{text[:3]}****{text[-4:]}"

    def _initials(self, data, owner):
        owner_data = self._as_dict(owner)
        name = self._first(data, "title") or self._first(owner_data, "nickname") or "名片"
        return name[:1]
