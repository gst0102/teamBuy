"""Scene-aware showcase template rules.

The editor can present templates, but the backend is the authority.  A saved
showcase must never publish a presentation that is incompatible with the
kind of notes it contains.
"""

from __future__ import annotations


SCENE_TEMPLATE_MAP: dict[str, tuple[str, ...]] = {
    "property": ("featured_window", "catalog_list"),
    "groupbuy": ("moments_story", "catalog_list", "featured_window"),
    "service": ("moments_story", "catalog_list", "featured_window"),
    "notes": ("catalog_list", "moments_story", "featured_window"),
    "mixed": ("catalog_list", "moments_story", "featured_window"),
    "business_card": ("brand_card",),
}

SCENE_DEFAULTS = {scene: templates[0] for scene, templates in SCENE_TEMPLATE_MAP.items()}
TEMPLATE_ALIASES = {"property_batch_collection": "featured_window"}

_CATEGORY_SCENE = {
    "房源": "property",
    "房产": "property",
    "property": "property",
    "商品": "groupbuy",
    "团购": "groupbuy",
    "groupbuy": "groupbuy",
    "服务": "service",
    "案例": "service",
    "service": "service",
    "名片": "business_card",
    "电子名片": "business_card",
    "business_card": "business_card",
    "资料": "notes",
    "日常": "notes",
    "日常资料": "notes",
    "notes": "notes",
    "mixed": "mixed",
}


def normalize_scene_type(
    scene_type: str | None = None,
    active_category: str | None = None,
    card_types: list[str] | None = None,
) -> str:
    """Resolve a stable scene from an explicit value, category, then notes."""
    explicit = _CATEGORY_SCENE.get(str(scene_type or "").strip().lower())
    if explicit:
        return explicit
    category = _CATEGORY_SCENE.get(str(active_category or "").strip().lower())
    if category:
        return category
    types = {str(item or "").strip().lower() for item in (card_types or []) if str(item or "").strip()}
    if types and types <= {"property_listing"}:
        return "property"
    if types and types <= {"groupbuy_product"}:
        return "groupbuy"
    if types and types <= {"business_card"}:
        return "business_card"
    if types and types <= {"service_offer"}:
        return "service"
    if types and any(item in {"property_listing", "groupbuy_product", "business_card", "service_offer"} for item in types):
        return "mixed"
    return "notes"


def allowed_template_ids(scene_type: str | None) -> tuple[str, ...]:
    return SCENE_TEMPLATE_MAP.get(normalize_scene_type(scene_type), SCENE_TEMPLATE_MAP["notes"])


def default_template_id(scene_type: str | None) -> str:
    return SCENE_DEFAULTS.get(normalize_scene_type(scene_type), SCENE_DEFAULTS["notes"])


def normalize_template_id(scene_type: str | None, template_id: str | None) -> str:
    candidate = TEMPLATE_ALIASES.get(str(template_id or "").strip(), str(template_id or "").strip())
    allowed = allowed_template_ids(scene_type)
    return candidate if candidate in allowed else allowed[0]


def note_scene_type(card_type: str | None) -> str:
    value = str(card_type or "").strip().lower()
    if value == "property_listing":
        return "property"
    if value == "groupbuy_product":
        return "groupbuy"
    if value == "business_card":
        return "business_card"
    if value == "service_offer":
        return "service"
    return "notes"


def scene_accepts_note(scene_type: str | None, card_type: str | None) -> bool:
    scene = normalize_scene_type(scene_type)
    note_scene = note_scene_type(card_type)
    if scene in {"notes", "mixed"}:
        return note_scene == "notes" or scene == "mixed"
    if scene == "service":
        return note_scene in {"service", "business_card"}
    return scene == note_scene
