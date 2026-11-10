"""Local schematic art and channel text for food results.

Illustrations are original drawings shipped with the WebUI. They are not
photographs. The tool never accepts an image path or URL from the model.
"""

from __future__ import annotations

import re
from typing import Any, cast

from nanobot.agent.tools._food import find_dish

_ART_ID = re.compile(r"^[a-z0-9-]{1,40}$")
DISH_ART: dict[str, str] = {
    "蒜蓉生菜": "garlic-lettuce",
    "番茄炒蛋": "tomato-egg",
    "青椒土豆丝": "pepper-potato",
    "紫菜蛋花汤": "seaweed-egg-soup",
    "蛋炒饭": "egg-fried-rice",
    "红烧豆腐": "braised-tofu",
    "米饭": "rice",
    "清炒虾仁": "shrimp",
    "番茄肉酱面": "tomato-meat-noodles",
    "凉拌花生米": "peanut-salad",
}
ART_IDS = frozenset(DISH_ART.values())
_SCHEMATIC_NOTE = "图片是示意图，不是实拍，也不能说明这道菜对你是否安全。"
_FEISHU_IMAGE_NOTE = "示意图只在网页聊天里显示。飞书这里不发送图片。"


def art_id_for_dish(name: str) -> str | None:
    return DISH_ART.get(name)


def local_art_path(art_id: object) -> str | None:
    """Return the only image URL the WebUI may request for a catalog id."""
    if not isinstance(art_id, str) or _ART_ID.fullmatch(art_id) is None:
        return None
    if art_id not in ART_IDS:
        return None
    return f"/food-art/{art_id}.svg"


def build_presentation(payload: dict[str, Any], *, channel: str) -> dict[str, Any]:
    """Attach a display plan. Blocked and unverified results stay text-only."""
    status = payload.get("status")
    action = payload.get("action")
    notice = _notice(payload)
    cards: list[dict[str, Any]] = []
    shopping: list[dict[str, Any]] = []
    if status == "ok" and action == "suggest":
        for item in _cook_items(payload):
            card = _suggest_card(item)
            if card is not None:
                cards.append(card)
    elif status == "ok" and action == "recipe":
        card = _recipe_card(payload)
        if card is not None:
            cards = [card]
    elif status == "ok" and action == "shopping_list":
        shopping = _shopping_groups(payload)
    image_policy = "schematic_local" if cards else "none"
    web_markdown = _web_markdown(
        action=action if isinstance(action, str) else "",
        notice=notice,
        cards=cards,
        shopping=shopping,
        payload=payload,
    )
    feishu_text = _feishu_text(
        action=action if isinstance(action, str) else "",
        notice=notice,
        cards=cards,
        shopping=shopping,
        payload=payload,
    )
    reply = web_markdown if _web_channel(channel) else feishu_text
    return {
        "image_policy": image_policy,
        "photograph": False,
        "cards": cards if image_policy == "schematic_local" else [],
        "shopping": shopping,
        "notice": notice,
        "web_markdown": web_markdown,
        "feishu_text": feishu_text,
        "reply_markdown": reply,
    }


def _web_channel(channel: str) -> bool:
    return channel == "websocket"


def _notice(payload: dict[str, Any]) -> str:
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    status = payload.get("status")
    if status == "need_info":
        lines = _strings(payload.get("questions"))
        if lines:
            return "\n".join(lines)
    if status == "ok":
        return _SCHEMATIC_NOTE
    return "这次没有可展示的菜品图。"


def _mapping(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    raw = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in raw):
        return None
    return cast(dict[str, Any], raw)


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [item.strip() for item in items if isinstance(item, str) and item.strip()]


def _dicts(value: object) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return found
    items = cast(list[object], value)
    for item in items:
        parsed = _mapping(item)
        if parsed is not None:
            found.append(parsed)
    return found


def _cook_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return _dicts(payload.get("cook"))


def _suggest_card(item: dict[str, Any]) -> dict[str, Any] | None:
    title = item.get("dish")
    if not isinstance(title, str) or title not in DISH_ART:
        return None
    art_id = DISH_ART[title]
    ingredients = _key_ingredients(title, _strings(item.get("uses_on_hand")))
    minutes = item.get("minutes")
    servings = item.get("servings")
    meta_parts: list[str] = []
    if isinstance(servings, int) and not isinstance(servings, bool):
        meta_parts.append(f"{servings}人")
    if isinstance(minutes, int) and not isinstance(minutes, bool):
        meta_parts.append(f"约{minutes}分钟")
    return {
        "art_id": art_id,
        "alt": f"{title}示意图",
        "title": title,
        "meta": " · ".join(meta_parts),
        "ingredients": ingredients,
    }


def _recipe_card(payload: dict[str, Any]) -> dict[str, Any] | None:
    title = payload.get("dish")
    if not isinstance(title, str) or title not in DISH_ART:
        return None
    if "steps" not in payload or "ingredients" not in payload:
        return None
    step_lines = _strings(payload.get("steps"))
    ingredient_lines = [line for line in (_ingredient_line(item) for item in _dicts(payload.get("ingredients"))) if line]
    if not step_lines or not ingredient_lines:
        return None
    people = payload.get("people")
    minutes = payload.get("minutes")
    meta_parts: list[str] = []
    if isinstance(people, int) and not isinstance(people, bool):
        meta_parts.append(f"{people}人")
    if isinstance(minutes, int) and not isinstance(minutes, bool):
        meta_parts.append(f"约{minutes}分钟")
    return {
        "art_id": DISH_ART[title],
        "alt": f"{title}示意图",
        "title": title,
        "meta": " · ".join(meta_parts),
        "ingredients": ingredient_lines,
        "steps": step_lines,
    }


def _ingredient_line(item: object) -> str:
    mapping = _mapping(item)
    if mapping is None:
        return ""
    name = mapping.get("name")
    quantity = mapping.get("quantity")
    unit = mapping.get("unit")
    if not isinstance(name, str) or not name.strip():
        return ""
    amount = ""
    if isinstance(quantity, int | float) and not isinstance(quantity, bool):
        amount = str(int(quantity)) if float(quantity).is_integer() else str(quantity)
    unit_text = unit if isinstance(unit, str) else ""
    return f"{name.strip()} {amount}{unit_text}".strip()


def _key_ingredients(name: str, uses_on_hand: list[str]) -> list[str]:
    names: list[str] = []
    for item in uses_on_hand:
        cleaned = item.strip()
        if cleaned and cleaned not in names:
            names.append(cleaned)
    dish = find_dish(name)
    if dish is not None:
        for ingredient in dish.ingredients:
            if ingredient.name not in names:
                names.append(ingredient.name)
            if len(names) >= 3:
                break
    return names[:3]


def _shopping_groups(payload: dict[str, Any]) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for group in _dicts(payload.get("groups")):
        category = group.get("category")
        if not isinstance(category, str):
            continue
        lines = [line for line in (_ingredient_line(item) for item in _dicts(group.get("items"))) if line]
        if lines:
            visible.append({"category": category, "lines": lines})
    return visible


def _eat_out_lines(payload: dict[str, Any]) -> list[str]:
    eat_out = _mapping(payload.get("eat_out"))
    if eat_out is None:
        return []
    lines: list[str] = []
    for direction in _dicts(eat_out.get("directions")):
        cuisine = direction.get("cuisine")
        if not isinstance(cuisine, str):
            continue
        names = _strings(direction.get("dishes"))
        if names:
            lines.append(f"{cuisine}：{'、'.join(names)}")
        else:
            lines.append(cuisine)
    return lines


def _web_markdown(
    *,
    action: str,
    notice: str,
    cards: list[dict[str, Any]],
    shopping: list[dict[str, Any]],
    payload: dict[str, Any],
) -> str:
    lines = [notice, ""]
    if cards:
        lines.append(_SCHEMATIC_NOTE)
        lines.append("")
    for card in cards:
        path = local_art_path(card.get("art_id"))
        lines.append(f"### {card['title']}")
        if path is not None:
            lines.append(f"![{card['alt']}]({path})")
        if card.get("meta"):
            lines.append(str(card["meta"]))
        ingredients = _strings(card.get("ingredients"))
        if ingredients:
            label = "用量" if card.get("steps") else "关键食材"
            lines.append(f"{label}：{'、'.join(ingredients)}")
        steps = _strings(card.get("steps"))
        if steps:
            lines.append("")
            for index, step in enumerate(steps, start=1):
                lines.append(f"{index}. {step}")
        lines.append("")
    lines.extend(_shopping_lines(shopping))
    if action == "suggest":
        for line in _eat_out_lines(payload):
            lines.append(f"外食方向：{line}")
    return "\n".join(lines).strip()


def _feishu_text(
    *,
    action: str,
    notice: str,
    cards: list[dict[str, Any]],
    shopping: list[dict[str, Any]],
    payload: dict[str, Any],
) -> str:
    lines = [notice, ""]
    if cards:
        lines.append(_FEISHU_IMAGE_NOTE)
        lines.append(_SCHEMATIC_NOTE)
        lines.append("")
    for index, card in enumerate(cards, start=1):
        lines.append(f"{index}. {card['title']}")
        if card.get("meta"):
            lines.append(str(card["meta"]))
        ingredients = _strings(card.get("ingredients"))
        if ingredients:
            label = "用量" if card.get("steps") else "关键食材"
            lines.append(f"{label}：{'、'.join(ingredients)}")
        steps = _strings(card.get("steps"))
        for step_index, step in enumerate(steps, start=1):
            lines.append(f"{step_index}. {step}")
        lines.append("")
    lines.extend(_shopping_lines(shopping))
    if action == "suggest":
        for line in _eat_out_lines(payload):
            lines.append(f"外食方向：{line}")
    return "\n".join(lines).strip()


def _shopping_lines(shopping: list[dict[str, Any]]) -> list[str]:
    if not shopping:
        return []
    lines = ["采购清单", "没有查询市场价格。", ""]
    for group in shopping:
        lines.append(str(group["category"]))
        for line in _strings(group.get("lines")):
            lines.append(f"- {line}")
        lines.append("")
    return lines
