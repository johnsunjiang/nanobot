"""Deterministic meal, recipe, and shopping decisions for the food tool.

The model may call this, but quantities, allergen exclusions, unit merging,
and session preference rules are decided here. Nothing in this module contacts
a shop, sends a message, or reads a live price.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

FOOD_PREFERENCES_KEY = "food_preferences"

QUESTION_PEOPLE = "几个人吃？"
QUESTION_MINUTES = "大概有多少分钟可以做饭或吃饭？"
QUESTION_BUDGET = (
    "预算按什么把握？直接说你的原话就行，例如“随便”或“人均30元以内”。"
    "我不会把它换成市场价格。"
)
QUESTION_DISH = "要做哪一道菜？"

SESSION_SCOPE_NOTE = (
    "这份饮食偏好只写在当前会话元数据里。新的 WebUI 对话、另一个飞书私聊和其他渠道读不到这份元数据。"
    "这不是端到端隔离：对话里说过的原话，仍可能经现有共享记忆、历史摘要或会话搜索被其他会话读到。"
    "这一版不能删除已保存的过敏。"
)
GROUP_PREFERENCE_REFUSAL = (
    "群会话，或无法确认是飞书私聊的会话，不能保存、修改或读取饮食偏好。"
    "请改在 WebUI 对话或飞书私聊里操作。"
)
UNSUPPORTED_CHANNEL_REFUSAL = "饮食偏好只接受 WebUI 和飞书私聊。这个渠道不能保存或读取。"
SHARED_SESSION_SAVE_REFUSAL = (
    "当前开启了所有渠道共用的会话。饮食偏好不能保存在这里，否则其他聊天会看到过敏和忌口。"
    "这次没有保存。请在各自的 WebUI 对话或飞书私聊里使用分开的会话后再保存。"
)
SHARED_SESSION_READ_WARNING = "所有渠道共用的会话里不读取饮食偏好，避免把过敏和忌口带进其他聊天。"
INTERNAL_SESSION_REFUSAL = "这不是用户聊天会话，饮食偏好不能保存在这里。"
NO_SESSION_REFUSAL = "没有当前聊天会话，饮食偏好不能保存，也不会写到长期记忆。"
EPHEMERAL_SESSION_REFUSAL = "这一回合不保留会话，饮食偏好没有保存。"
UNREADABLE_PREFERENCE_WARNING = "当前会话里的饮食偏好无法读取，这次没有套用。"

ESTIMATE_NOTE = "用量是按人数换算的家常估计，不是实测营养或价格。不判断食疗或医疗效果。"
ALLERGY_LIMIT = (
    "名称包含关系只覆盖菜名、食材和步骤里写出的字，不是医学核对，也不能证明没有过敏风险。"
    "交叉接触、共用器具、酱料和供应商未标明的成分都无法判断。"
)
ALLERGY_APPEND_ONLY = "这一版不能删除已保存的过敏。保存、更新和清除都只会保留或追加。"
UNVERIFIED_RECIPE_MESSAGE = (
    "这道菜不在已核对的家常菜谱里。临时菜名、用量和步骤无法核实酱料、包装配料或供应商成分，"
    "所以不返回可执行做法。交叉接触和共用器具也无法判断。名称没有对上，也不表示可以安全食用。"
)
_MAX_QUANTITY = 100_000.0
_MASS_TO_G = {"g": 1.0, "kg": 1000.0}
_VOLUME_TO_ML = {"ml": 1.0, "l": 1000.0}
NO_CITY_NOTE = (
    "没有得到城市，所以不推荐具体饭店。下面只有菜系和菜品方向，"
    "没有商家、实时价格、销量、评价、配送时长或链接。"
)
ALLERGY_BLOCK_MESSAGE = (
    "这道菜碰到已确认的过敏原，已经停住，不提供做法。"
    "口味或“今天想吃”不能取消过敏。要改过敏记录，请明确说保存、更新或清除当前会话的饮食偏好。"
)

_MAX_ITEMS = 20
_MAX_ITEM_CHARS = 32
_MAX_PEOPLE = 20
_MAX_MINUTES = 240
_CATEGORIES = ("蔬菜", "肉蛋海鲜", "调味", "主食", "其他")
_COUNT_UNITS = frozenset({"个", "只", "颗", "枚", "瓣", "根", "把", "片"})
_UNIT_ALIASES = {
    "克": "g",
    "g": "g",
    "千克": "kg",
    "公斤": "kg",
    "kg": "kg",
    "毫升": "ml",
    "ml": "ml",
    "升": "l",
    "l": "l",
}
_FIELD_LABELS = {"tastes": "口味", "avoid": "忌口", "allergies": "过敏"}
_ALIASES = {
    "西红柿炒蛋": "番茄炒蛋",
    "西红柿炒鸡蛋": "番茄炒蛋",
    "番茄炒鸡蛋": "番茄炒蛋",
}
_SAFETY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("鸡", "猪", "牛", "羊", "肉", "虾", "鱼", "海鲜", "蛋"),
        "生熟分开：处理生肉、生海鲜或生蛋后洗手，并换砧板和刀具，再接触熟食或直接入口的食材。",
    ),
    (("虾", "鱼", "海鲜"), "海鲜要做熟；气味不正常就不要用。"),
    (("蛋",), "鸡蛋要全熟，不要用不凝固的蛋液拌直接入口的菜。"),
    (("四季豆", "豆角"), "四季豆和豆角必须炒熟到没有生豆味。"),
    (("米饭", "剩饭"), "剩饭要彻底热透后再吃。"),
    (("花生",), "这道菜含花生。过敏者不要和这道菜共用未清洗的器具。"),
    (("生菜", "黄瓜", "凉拌"), "生食蔬菜要洗净；生熟器具不要混用。"),
    (("豆腐",), "豆腐按包装日期使用，切开后尽快做完。"),
)


@dataclass(frozen=True)
class Ingredient:
    name: str
    quantity: float | None
    unit: str
    category: str


@dataclass(frozen=True)
class Dish:
    name: str
    base_servings: int
    minutes: int
    tags: tuple[str, ...]
    allergens: tuple[str, ...]
    ingredients: tuple[Ingredient, ...]
    steps: tuple[str, ...]


@dataclass(frozen=True)
class EatOutDirection:
    cuisine: str
    dishes: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class FoodPrefs:
    tastes: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    allergies: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not self.tastes and not self.avoid and not self.allergies

    def to_json(self) -> dict[str, list[str]]:
        return {
            "tastes": list(self.tastes),
            "avoid": list(self.avoid),
            "allergies": list(self.allergies),
        }


@dataclass(frozen=True)
class MealConstraints:
    tastes: tuple[str, ...]
    avoid: tuple[str, ...]
    allergies: tuple[str, ...]
    allow_avoid: tuple[str, ...]
    ignored_allergy_exceptions: tuple[str, ...]
    taste_overridden_by_allergy: tuple[str, ...]
    preference_source: str

    def public(self) -> dict[str, Any]:
        return {
            "tastes": list(self.tastes),
            "avoid": list(self.avoid),
            "allergies": list(self.allergies),
            "allow_avoid": list(self.allow_avoid),
            "ignored_allergy_exceptions": list(self.ignored_allergy_exceptions),
            "taste_overridden_by_allergy": list(self.taste_overridden_by_allergy),
            "source": self.preference_source,
            "scope": "session",
        }


def limits() -> dict[str, Any]:
    return {
        "quantity_basis": "household_estimate",
        "nutrition_measured": False,
        "prices_measured": False,
        "merchants": False,
        "medical_claims": False,
        "external_actions": [],
        "preference_scope": "session_metadata",
        "conversation_text_isolation": False,
        "writes_long_term_memory": False,
        "allergy_match": "listed_name_contains",
        "allergy_text_match_is_clearance": False,
        "cross_contact_known": False,
        "supplier_ingredients_known": False,
        "allergies_append_only": True,
    }


def normalize_name(value: str) -> str:
    return "".join(value.strip().casefold().split())


def normalize_unit(value: str) -> str:
    compact = "".join(value.strip().casefold().split())
    return _UNIT_ALIASES.get(compact, compact)


def names_conflict(left: str, right: str) -> bool:
    """True when either normalized name contains the other."""
    a = normalize_name(left)
    b = normalize_name(right)
    if not a or not b:
        return False
    return a in b or b in a


def json_quantity(value: float) -> int | float:
    rounded = round(value, 2)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def _envelope(action: str, status: str, **fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": status, "action": action, "limits": limits()}
    payload.update(fields)
    return payload


def _ing(name: str, quantity: float, unit: str, category: str) -> Ingredient:
    return Ingredient(name, quantity, normalize_unit(unit), category)


def _dish(
    name: str,
    *,
    minutes: int,
    tags: tuple[str, ...],
    allergens: tuple[str, ...] = (),
    ingredients: tuple[Ingredient, ...],
    steps: tuple[str, ...],
) -> Dish:
    return Dish(name, 2, minutes, tags, allergens, ingredients, steps)


CATALOG: tuple[Dish, ...] = (
    _dish(
        "蒜蓉生菜",
        minutes=10,
        tags=("素", "清淡", "快手", "家常"),
        ingredients=(
            _ing("生菜", 300, "g", "蔬菜"),
            _ing("大蒜", 3, "瓣", "调味"),
            _ing("食用油", 10, "ml", "调味"),
            _ing("盐", 2, "g", "调味"),
        ),
        steps=(
            "生菜洗净沥水，大蒜切末。",
            "热锅冷油，蒜末炒香。",
            "下生菜快速翻炒，加盐，断生即可。",
        ),
    ),
    _dish(
        "番茄炒蛋",
        minutes=15,
        tags=("家常", "快手", "蛋"),
        allergens=("蛋",),
        ingredients=(
            _ing("鸡蛋", 3, "个", "肉蛋海鲜"),
            _ing("番茄", 2, "个", "蔬菜"),
            _ing("食用油", 15, "ml", "调味"),
            _ing("盐", 2, "g", "调味"),
            _ing("葱", 10, "g", "蔬菜"),
        ),
        steps=(
            "鸡蛋打散，番茄切块。",
            "热锅下油，倒入蛋液炒到刚凝固，盛出。",
            "用同一口锅把番茄炒软，加盐，倒回鸡蛋，翻匀即可。",
            "出锅前确认蛋液已经凝固、番茄已经炒软。",
        ),
    ),
    _dish(
        "青椒土豆丝",
        minutes=20,
        tags=("素", "家常", "快手"),
        ingredients=(
            _ing("土豆", 2, "个", "蔬菜"),
            _ing("青椒", 2, "个", "蔬菜"),
            _ing("食用油", 15, "ml", "调味"),
            _ing("盐", 2, "g", "调味"),
            _ing("醋", 5, "ml", "调味"),
        ),
        steps=(
            "土豆切丝后用水冲去多余淀粉，青椒切丝。",
            "热锅下油，下土豆丝翻炒到断生。",
            "加入青椒、盐和醋，快速翻匀即可。",
        ),
    ),
    _dish(
        "紫菜蛋花汤",
        minutes=15,
        tags=("清淡", "汤", "快手", "蛋"),
        allergens=("蛋",),
        ingredients=(
            _ing("鸡蛋", 2, "个", "肉蛋海鲜"),
            _ing("紫菜", 5, "g", "其他"),
            _ing("香油", 5, "ml", "调味"),
            _ing("盐", 2, "g", "调味"),
            _ing("葱", 5, "g", "蔬菜"),
        ),
        steps=(
            "水烧开，放入紫菜和盐。",
            "淋入打散的鸡蛋，轻轻推动，等蛋花凝固。",
            "撒葱花，滴香油后关火。",
        ),
    ),
    _dish(
        "蛋炒饭",
        minutes=15,
        tags=("快手", "蛋", "主食"),
        allergens=("蛋",),
        ingredients=(
            _ing("米饭", 300, "g", "主食"),
            _ing("鸡蛋", 2, "个", "肉蛋海鲜"),
            _ing("葱", 15, "g", "蔬菜"),
            _ing("食用油", 15, "ml", "调味"),
            _ing("盐", 2, "g", "调味"),
        ),
        steps=(
            "米饭尽量拨散。剩饭必须彻底热透后再吃。",
            "鸡蛋炒到完全凝固，盛出。",
            "下米饭炒散，加盐，倒回鸡蛋和葱花翻匀。",
        ),
    ),
    _dish(
        "红烧豆腐",
        minutes=25,
        tags=("素", "家常"),
        ingredients=(
            _ing("北豆腐", 400, "g", "其他"),
            _ing("葱", 10, "g", "蔬菜"),
            _ing("姜", 5, "g", "调味"),
            _ing("生抽", 15, "ml", "调味"),
            _ing("食用油", 15, "ml", "调味"),
            _ing("糖", 3, "g", "调味"),
            _ing("盐", 1, "g", "调味"),
        ),
        steps=(
            "豆腐切块，用厨房纸吸去表面水分。",
            "热锅下油，豆腐煎到表面稍硬。",
            "加葱姜、生抽、糖、盐和少量水，煮到入味。",
        ),
    ),
    _dish(
        "米饭",
        minutes=30,
        tags=("主食", "清淡"),
        ingredients=(
            _ing("大米", 150, "g", "主食"),
            _ing("水", 220, "ml", "其他"),
        ),
        steps=(
            "大米淘洗后加水。",
            "煮到米心没有硬芯，焖几分钟再开盖。",
        ),
    ),
    _dish(
        "清炒虾仁",
        minutes=15,
        tags=("快手", "荤", "海鲜"),
        allergens=("虾", "海鲜"),
        ingredients=(
            _ing("虾仁", 200, "g", "肉蛋海鲜"),
            _ing("黄瓜", 1, "根", "蔬菜"),
            _ing("姜", 5, "g", "调味"),
            _ing("食用油", 15, "ml", "调味"),
            _ing("盐", 2, "g", "调味"),
        ),
        steps=(
            "虾仁洗净沥干，黄瓜切片，姜切末。",
            "热锅下油，姜末和虾仁炒到变色并且中心不透明。",
            "下黄瓜和盐，快速翻匀即可。",
        ),
    ),
    _dish(
        "番茄肉酱面",
        minutes=35,
        tags=("荤", "面食", "家常"),
        ingredients=(
            _ing("挂面", 200, "g", "主食"),
            _ing("番茄", 2, "个", "蔬菜"),
            _ing("猪肉末", 150, "g", "肉蛋海鲜"),
            _ing("洋葱", 1, "个", "蔬菜"),
            _ing("食用油", 10, "ml", "调味"),
            _ing("盐", 3, "g", "调味"),
        ),
        steps=(
            "番茄和洋葱切小块。肉末用单独的砧板处理。",
            "热锅下油，肉末炒到变色，再下洋葱和番茄炒软。",
            "加盐煮成酱。面条另煮熟，拌匀后再吃。",
        ),
    ),
    _dish(
        "凉拌花生米",
        minutes=10,
        tags=("快手", "凉"),
        allergens=("花生",),
        ingredients=(
            _ing("花生米", 80, "g", "其他"),
            _ing("黄瓜", 1, "根", "蔬菜"),
            _ing("盐", 1, "g", "调味"),
            _ing("醋", 5, "ml", "调味"),
            _ing("香油", 5, "ml", "调味"),
        ),
        steps=(
            "花生米用熟花生。黄瓜洗净切丁。",
            "加盐、醋和香油拌匀。",
            "这是凉菜，不要和生肉共用未清洗的器具。",
        ),
    ),
)

EAT_OUT: tuple[EatOutDirection, ...] = (
    EatOutDirection("面食", ("汤面", "拌面", "饺子"), ("快手",)),
    EatOutDirection("家常热炒", ("番茄炒蛋", "青菜", "家常豆腐"), ("家常",)),
    EatOutDirection("清淡蒸煮", ("蒸鱼", "清炒时蔬", "白粥"), ("清淡",)),
    EatOutDirection("川味", ("麻婆豆腐", "鱼香茄子", "回锅肉"), ("辣",)),
)


def find_dish(name: str) -> Dish | None:
    key = normalize_name(name)
    canonical = _ALIASES.get(key, key)
    for dish in CATALOG:
        if normalize_name(dish.name) == canonical:
            return dish
    return None


def _as_dict(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    mapping = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        return None
    return cast(dict[str, Any], mapping)


def _as_str_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = cast(list[object], value)
    if any(not isinstance(item, str) for item in items):
        return None
    return cast(list[str], items)


def parse_stored_prefs(metadata: object) -> tuple[FoodPrefs | None, bool]:
    """Return stored prefs and whether the stored value was unusable."""
    stored = _as_dict(metadata)
    if stored is None:
        return None, False
    raw = stored.get(FOOD_PREFERENCES_KEY)
    if raw is None:
        return None, False
    blob = _as_dict(raw)
    if blob is None:
        return None, True
    tastes = _as_str_list(blob.get("tastes"))
    avoid = _as_str_list(blob.get("avoid"))
    allergies = _as_str_list(blob.get("allergies"))
    if tastes is None or avoid is None or allergies is None:
        return None, True
    prefs = FoodPrefs(tuple(tastes), tuple(avoid), tuple(allergies))
    if prefs.is_empty():
        return None, False
    return prefs, False


def clean_items(values: object, *, field: str) -> tuple[list[str] | None, str | None]:
    if values is None:
        return None, None
    label = _FIELD_LABELS.get(field, field)
    items = _as_str_list(values)
    if items is None:
        return None, f"{label}必须是文字列表。"
    if len(items) > _MAX_ITEMS:
        return None, f"{label}最多{_MAX_ITEMS}项。"
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in items:
        item = " ".join(raw.split()).strip()
        if not item:
            continue
        if len(item) > _MAX_ITEM_CHARS:
            return None, f"{label}里有一项超过{_MAX_ITEM_CHARS}个字。"
        key = normalize_name(item)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned, None


def _dedupe(values: list[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = normalize_name(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return tuple(result)


def _matching_terms(parts: list[str], terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if any(names_conflict(part, term) for part in parts)]


def _strip_tastes(
    tastes: tuple[str, ...], allergies: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    kept: list[str] = []
    overridden: list[str] = []
    for taste in tastes:
        if _matching_terms([taste], allergies):
            overridden.append(taste)
        else:
            kept.append(taste)
    return tuple(kept), tuple(overridden)


def build_constraints(
    saved: FoodPrefs | None,
    *,
    tastes: list[str] | None,
    avoid: list[str] | None,
    allergies: list[str] | None,
    allow_avoid: list[str] | None,
    saved_state: str,
) -> tuple[MealConstraints | None, str | None]:
    """Merge this request onto session prefs. Request allergies only add."""
    cleaned_tastes, taste_error = clean_items(tastes, field="tastes")
    cleaned_avoid, avoid_error = clean_items(avoid, field="avoid")
    cleaned_allergies, allergy_error = clean_items(allergies, field="allergies")
    cleaned_allow, allow_error = clean_items(allow_avoid, field="avoid")
    error = taste_error or avoid_error or allergy_error or allow_error
    if error is not None:
        return None, error
    stored = saved or FoodPrefs()
    merged_allergies = _dedupe([*stored.allergies, *(cleaned_allergies or [])])
    merged_avoid = _dedupe([*stored.avoid, *(cleaned_avoid or [])])
    merged_tastes, overridden = _strip_tastes(
        _dedupe([*stored.tastes, *(cleaned_tastes or [])]),
        merged_allergies,
    )
    requested_allow = cleaned_allow or []
    ignored = tuple(item for item in requested_allow if _matching_terms([item], merged_allergies))
    allowed = tuple(item for item in requested_allow if item not in ignored)
    request_used = any(value is not None for value in (tastes, avoid, allergies, allow_avoid))
    if saved_state == "ok" and request_used:
        source = "session_and_request"
    elif saved_state == "ok":
        source = "session"
    elif request_used:
        source = "request"
    else:
        source = "none"
    return MealConstraints(
        tastes=merged_tastes,
        avoid=merged_avoid,
        allergies=merged_allergies,
        allow_avoid=allowed,
        ignored_allergy_exceptions=ignored,
        taste_overridden_by_allergy=overridden,
        preference_source=source,
    ), None


def _replace_field(
    current: tuple[str, ...],
    supplied: list[str] | None,
    allergies: tuple[str, ...],
    *,
    is_taste: bool,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if supplied is None:
        values = current
    else:
        values = tuple(supplied)
    if is_taste:
        return _strip_tastes(values, allergies)
    return values, ()


def apply_preference_change(
    current: FoodPrefs | None,
    *,
    operation: str,
    tastes: list[str] | None,
    avoid: list[str] | None,
    allergies: list[str] | None,
    fields: list[str] | None,
) -> tuple[FoodPrefs | None, list[str], str | None]:
    """Return the next prefs, warnings, and a validation error."""
    stored = current or FoodPrefs()
    cleaned_tastes, taste_error = clean_items(tastes, field="tastes")
    cleaned_avoid, avoid_error = clean_items(avoid, field="avoid")
    cleaned_allergies, allergy_error = clean_items(allergies, field="allergies")
    error = taste_error or avoid_error or allergy_error
    if error is not None:
        return None, [], error
    if operation == "clear":
        if fields is not None and not fields:
            return None, [], "要清除哪一项？可以是口味、忌口、过敏或全部。"
        selected = list(fields) if fields is not None else ["all"]
        unknown = [field for field in selected if field not in {"tastes", "avoid", "allergies", "all"}]
        if unknown:
            return None, [], "清除字段只能是口味、忌口、过敏或全部。"
        clear_tastes = "all" in selected or "tastes" in selected
        clear_avoid = "all" in selected or "avoid" in selected
        warnings = [ALLERGY_APPEND_ONLY] if stored.allergies and (
            "all" in selected or "allergies" in selected
        ) else []
        prefs = FoodPrefs(
            () if clear_tastes else stored.tastes,
            () if clear_avoid else stored.avoid,
            stored.allergies,
        )
        return (None if prefs.is_empty() else prefs), warnings, None
    if operation not in {"save", "update"}:
        return None, [], "偏好动作只能是 get、save、update 或 clear。"
    if cleaned_tastes is None and cleaned_avoid is None and cleaned_allergies is None:
        return None, [], "保存或更新时，至少要给出口味、忌口或过敏中的一项。"
    next_allergies = _dedupe([*stored.allergies, *(cleaned_allergies or [])])
    kept_allergies = _allergies_kept_from_removal(stored.allergies, cleaned_allergies)
    if operation == "save":
        next_avoid, _ = _replace_field(stored.avoid, cleaned_avoid, next_allergies, is_taste=False)
        next_tastes, overridden = _replace_field(
            stored.tastes, cleaned_tastes, next_allergies, is_taste=True
        )
    else:
        next_avoid = _dedupe([*stored.avoid, *(cleaned_avoid or [])])
        next_tastes, overridden = _strip_tastes(
            _dedupe([*stored.tastes, *(cleaned_tastes or [])]),
            next_allergies,
        )
    warnings = [f"{ALLERGY_APPEND_ONLY}仍保留：{'、'.join(kept_allergies)}。"] if kept_allergies else []
    warnings.extend(
        f"已保留过敏「{item}」，没有把它记成口味。"
        for item in overridden
    )
    prefs = FoodPrefs(next_tastes, next_avoid, next_allergies)
    return (None if prefs.is_empty() else prefs), warnings, None


def _allergies_kept_from_removal(
    stored: tuple[str, ...], supplied: list[str] | None,
) -> list[str]:
    if supplied is None:
        return []
    supplied_keys = {normalize_name(item) for item in supplied}
    return [item for item in stored if normalize_name(item) not in supplied_keys]


def _integer_in_range(value: int | None, *, upper: int, label: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not 0 <= value <= upper:
        return f"{label}需要是0到{upper}的整数。"
    return None


def _people_error(people: object, *, required: bool) -> str | None:
    if people is None:
        return QUESTION_PEOPLE if required else None
    if isinstance(people, bool) or not isinstance(people, int) or not 1 <= people <= _MAX_PEOPLE:
        return f"人数需要是1到{_MAX_PEOPLE}的整数。"
    return None


def _budget_text(budget: str | None) -> tuple[str | None, str | None]:
    if budget is None:
        return None, None
    text = " ".join(budget.split()).strip()
    if not text:
        return None, None
    if len(text) > 80:
        return None, "预算请用不超过80个字的原话。"
    return text, None


def _budget_is_tight(budget: str) -> bool:
    return any(token in budget for token in ("紧", "省", "便宜", "少花"))


def _term_allowed(term: str, allows: tuple[str, ...]) -> bool:
    return any(names_conflict(term, allow) for allow in allows)


def _dish_parts(dish: Dish) -> list[str]:
    return [
        dish.name,
        *dish.tags,
        *dish.allergens,
        *(ingredient.name for ingredient in dish.ingredients),
        *dish.steps,
    ]


def _hits(parts: list[str], terms: tuple[str, ...]) -> list[str]:
    return _matching_terms(parts, terms)


def _exclude_reason(dish: Dish, constraints: MealConstraints) -> str | None:
    if _hits(_dish_parts(dish), constraints.allergies):
        return "allergy"
    avoid_hits = _hits(_dish_parts(dish), constraints.avoid)
    if any(not _term_allowed(hit, constraints.allow_avoid) for hit in avoid_hits):
        return "avoid"
    return None


def _matched_on_hand(dish: Dish, on_hand: list[str]) -> tuple[str, ...]:
    found: list[str] = []
    for name in on_hand:
        if any(names_conflict(name, ingredient.name) for ingredient in dish.ingredients):
            found.append(name)
    return tuple(found)


def _safety_notes(parts: list[str]) -> list[str]:
    notes: list[str] = []
    for keywords, note in _SAFETY_RULES:
        if any(names_conflict(part, keyword) for part in parts for keyword in keywords):
            if note not in notes:
                notes.append(note)
    notes.append(ESTIMATE_NOTE)
    notes.append(ALLERGY_LIMIT)
    return notes


def _eat_out(
    *,
    offered: bool,
    minutes: int,
    constraints: MealConstraints,
    reason: str | None = None,
) -> dict[str, Any]:
    if not offered:
        return {
            "offered": False,
            "reason": reason,
            "city": None,
            "local_restaurants": [],
            "directions": [],
            "note": reason,
        }
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, direction in enumerate(EAT_OUT):
        tag_hits = _hits(list(direction.tags), constraints.avoid)
        if any(not _term_allowed(hit, constraints.allow_avoid) for hit in tag_hits):
            continue
        dishes = [
            dish
            for dish in direction.dishes
            if not _hits([dish], constraints.allergies)
            and not any(
                not _term_allowed(hit, constraints.allow_avoid)
                for hit in _hits([dish], constraints.avoid)
            )
        ]
        if not dishes:
            continue
        score = 0
        if _hits([direction.cuisine, *direction.tags], constraints.tastes):
            score += 5
        if minutes <= 20 and "快手" in direction.tags:
            score += 2
        ranked.append((
            score,
            index,
            {"cuisine": direction.cuisine, "dishes": dishes},
        ))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return {
        "offered": True,
        "city": None,
        "local_restaurants": [],
        "directions": [item[2] for item in ranked],
        "note": NO_CITY_NOTE,
    }


def plan_meal(
    *,
    people: int | None,
    minutes: int | None,
    budget: str | None,
    mode: str | None,
    on_hand: list[str],
    constraints: MealConstraints,
) -> dict[str, Any]:
    if mode not in {None, "cook", "eat_out", "either"}:
        return _envelope("suggest", "invalid", message="mode 只能是 cook、eat_out 或 either。")
    questions: list[str] = []
    people_error = _people_error(people, required=False)
    if people is None:
        questions.append(QUESTION_PEOPLE)
    elif people_error is not None:
        return _envelope("suggest", "invalid", message=people_error)
    minutes_error = _integer_in_range(minutes, upper=_MAX_MINUTES, label="可用分钟")
    if minutes is None:
        questions.append(QUESTION_MINUTES)
    elif minutes_error is not None:
        return _envelope("suggest", "invalid", message=minutes_error)
    stated_budget, budget_error = _budget_text(budget)
    if budget_error is not None:
        return _envelope("suggest", "invalid", message=budget_error)
    if stated_budget is None:
        questions.append(QUESTION_BUDGET)
    common = {
        "assumptions": [],
        "not_assumed": ["city", "household_size", "dietary_restrictions"],
        "preferences_applied": constraints.public(),
    }
    if questions:
        return _envelope("suggest", "need_info", questions=questions, cook=[], eat_out=None, **common)
    assert people is not None and minutes is not None and stated_budget is not None
    selected_mode = mode or "either"
    tight = _budget_is_tight(stated_budget)
    excluded_allergy: list[str] = []
    excluded_avoid: list[str] = []
    too_slow: list[str] = []
    ranked: list[tuple[int, int, int, Dish, tuple[str, ...]]] = []
    for index, dish in enumerate(CATALOG):
        reason = _exclude_reason(dish, constraints)
        if reason == "allergy":
            excluded_allergy.append(dish.name)
            continue
        if reason == "avoid":
            excluded_avoid.append(dish.name)
            continue
        if dish.minutes > minutes:
            too_slow.append(dish.name)
            continue
        matched = _matched_on_hand(dish, on_hand)
        score = len(matched) * 10
        if any(names_conflict(tag, taste) for tag in dish.tags for taste in constraints.tastes):
            score += 5
        if "家常" in dish.tags:
            score += 1
        if tight and "家常" in dish.tags:
            score += 2
        ranked.append((score, dish.minutes, index, dish, matched))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    cook = [
        {
            "dish": dish.name,
            "minutes": dish.minutes,
            "servings": people,
            "why": _why(dish, matched),
            "allergens": list(dish.allergens),
            "uses_on_hand": list(matched),
        }
        for _score, _minutes, _index, dish, matched in ranked[:3]
    ]
    if selected_mode == "eat_out":
        cook = []
    eat_out = _eat_out(
        offered=selected_mode != "cook",
        minutes=minutes,
        constraints=constraints,
        reason="这次按自己做来安排，没有展开外食。" if selected_mode == "cook" else None,
    )
    note = "按你说的预算优先安排家常菜，没有查询真实价格。" if tight else None
    return _envelope(
        "suggest",
        "ok",
        stated={
            "people": people,
            "minutes": minutes,
            "budget": stated_budget,
            "mode": selected_mode,
        },
        questions=[],
        cook=cook,
        excluded_for_allergy=excluded_allergy,
        excluded_for_avoid=excluded_avoid,
        too_slow=too_slow,
        eat_out=eat_out,
        budget_note=note,
        **common,
    )


def _why(dish: Dish, matched: tuple[str, ...]) -> str:
    text = f"大约{dish.minutes}分钟"
    if matched:
        text += "，可以用上" + "、".join(matched)
    return text


def scale_quantity(quantity: float, base_servings: int, people: int, unit: str) -> float:
    scaled = quantity * people / base_servings
    if unit in _COUNT_UNITS:
        rounded = math.floor(scaled * 2 + 0.5) / 2
        if rounded == 0 and scaled > 0:
            return round(scaled, 2)
        return rounded
    if quantity <= 0:
        return 0.0
    return round(scaled, 3)


def _ingredient_json(ingredient: Ingredient, *, quantity: float) -> dict[str, Any]:
    return {
        "name": ingredient.name,
        "quantity": json_quantity(quantity),
        "unit": ingredient.unit,
        "category": ingredient.category,
    }


def _recipe_from_dish(dish: Dish, people: int, *, source: str) -> dict[str, Any]:
    parts = _dish_parts(dish)
    return _envelope(
        "recipe",
        "ok",
        dish=dish.name,
        people=people,
        base_servings=dish.base_servings,
        source=source,
        minutes=dish.minutes,
        ingredients=[
            _ingredient_json(
                ingredient,
                quantity=scale_quantity(
                    ingredient.quantity or 0,
                    dish.base_servings,
                    people,
                    ingredient.unit,
                ),
            )
            for ingredient in dish.ingredients
        ],
        steps=list(dish.steps),
        allergens=list(dish.allergens),
        safety_notes=_safety_notes(parts),
    )


def _blocked_recipe(dish_name: str, people: int | None, allergens: list[str]) -> dict[str, Any]:
    return _envelope(
        "recipe",
        "blocked_allergy",
        dish=dish_name,
        people=people,
        recipe=None,
        allergens=allergens,
        message=ALLERGY_BLOCK_MESSAGE,
        safety_notes=["过敏原仍然排除。不判断食疗或医疗效果。", ALLERGY_LIMIT],
    )


def parse_ingredient_dict(raw: object) -> tuple[Ingredient | None, str | None]:
    blob = _as_dict(raw)
    if blob is None:
        return None, "食材需要包含名称。"
    name = blob.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "食材缺少名称。"
    display = " ".join(name.split()).strip()
    if len(display) > 40:
        return None, f"食材“{display[:8]}”的名称太长。"
    quantity = blob.get("quantity")
    if quantity is None:
        parsed_quantity: float | None = None
    elif (
        isinstance(quantity, bool)
        or not isinstance(quantity, (int, float))
        or isinstance(quantity, float) and not math.isfinite(quantity)
        or quantity < 0
        or quantity > _MAX_QUANTITY
    ):
        return None, f"食材“{display}”的数量无效或超出可汇总范围。"
    else:
        parsed_quantity = float(quantity)
    unit_value = blob.get("unit")
    unit = "" if unit_value is None else unit_value
    if not isinstance(unit, str) or len(unit) > 16:
        return None, f"食材“{display}”的单位无效。"
    category_value = blob.get("category")
    category = category_value if isinstance(category_value, str) else "其他"
    if category not in _CATEGORIES:
        category = "其他"
    return Ingredient(display, parsed_quantity, normalize_unit(unit), category), None


def _unverified_recipe(dish_name: str, *, caller_supplied_recipe: bool) -> dict[str, Any]:
    return _envelope(
        "recipe",
        "unverified",
        dish=dish_name,
        recipe=None,
        caller_supplied_recipe_ignored=caller_supplied_recipe,
        questions=["请改用内置菜谱中的菜名。临时配方不能提供可执行做法。"],
        message=UNVERIFIED_RECIPE_MESSAGE,
        safety_notes=[ALLERGY_LIMIT],
    )


def build_recipe(
    *,
    dish: str | None,
    people: int | None,
    base_servings: int | None,
    base_ingredients: Sequence[object] | None,
    steps: Sequence[object] | None,
    constraints: MealConstraints,
) -> dict[str, Any]:
    if dish is None or not dish.strip():
        return _envelope("recipe", "need_info", questions=[QUESTION_DISH], recipe=None)
    catalog_dish = find_dish(dish)
    if catalog_dish is None:
        supplied = bool(base_servings is not None or base_ingredients or steps)
        return _unverified_recipe(dish.strip(), caller_supplied_recipe=supplied)
    people_error = _people_error(people, required=False)
    if people is None:
        return _envelope("recipe", "need_info", questions=[QUESTION_PEOPLE], recipe=None)
    if people_error is not None:
        return _envelope("recipe", "invalid", message=people_error)
    hits = _hits(_dish_parts(catalog_dish), constraints.allergies)
    if hits:
        return _blocked_recipe(catalog_dish.name, people, hits)
    return _recipe_from_dish(catalog_dish, people, source="builtin_catalog")


@dataclass
class _MergedLine:
    name: str
    quantity: float
    unit: str
    category: str
    recipes: list[str]


def _canonicalize(ingredient: Ingredient) -> tuple[Ingredient | None, str | None]:
    if ingredient.quantity is None:
        return ingredient, None
    if ingredient.unit in _MASS_TO_G:
        quantity = ingredient.quantity * _MASS_TO_G[ingredient.unit]
        unit = "g"
    elif ingredient.unit in _VOLUME_TO_ML:
        quantity = ingredient.quantity * _VOLUME_TO_ML[ingredient.unit]
        unit = "ml"
    else:
        quantity = ingredient.quantity
        unit = ingredient.unit
    if quantity > _MAX_QUANTITY:
        return None, f"“{ingredient.name}”换算后的数量超出可汇总范围。"
    return Ingredient(ingredient.name, quantity, unit, ingredient.category), None


def _add_line(
    merged: dict[tuple[str, str], _MergedLine],
    ingredient: Ingredient,
    *,
    recipe: str,
) -> str | None:
    if ingredient.quantity is None:
        return f"“{ingredient.name}”没有数量，无法汇总。"
    canonical, error = _canonicalize(ingredient)
    quantity = None if canonical is None else canonical.quantity
    if error is not None or canonical is None or quantity is None:
        return error or f"“{ingredient.name}”的数量无效。"
    key = (normalize_name(canonical.name), canonical.unit)
    current = merged.get(key)
    if current is None:
        merged[key] = _MergedLine(
            canonical.name,
            quantity,
            canonical.unit,
            canonical.category,
            [recipe] if recipe else [],
        )
        return None
    current.quantity += quantity
    if current.category == "其他" and canonical.category != "其他":
        current.category = canonical.category
    if recipe and recipe not in current.recipes:
        current.recipes.append(recipe)
    return None


def _conflict(name: str, units: list[str], reason: str) -> dict[str, Any]:
    return {"name": name, "units": units, "reason": reason}


def build_shopping_list(
    *,
    dishes: Sequence[object] | None,
    lines: Sequence[object] | None,
    people: int | None,
    pantry: Sequence[object] | None,
    pantry_confirmed: bool,
    constraints: MealConstraints,
) -> dict[str, Any]:
    people_error = _people_error(people, required=False)
    if people is not None and people_error is not None:
        return _envelope("shopping_list", "invalid", message=people_error)
    if lines and people is not None:
        return _envelope(
            "shopping_list",
            "need_info",
            questions=[
                "采购行和人数不能一起用。请只传内置菜和人数，或只传已经算好数量的采购行并且不要带人数。"
                "我不会猜测这些行要不要按人数放大。"
            ],
            groups=[],
        )
    merged: dict[tuple[str, str], _MergedLine] = {}
    excluded: list[str] = []
    for request in dishes or []:
        blob = _as_dict(request)
        if blob is None:
            return _envelope("shopping_list", "invalid", message="采购菜名无效。")
        name = blob.get("name")
        if not isinstance(name, str) or not name.strip():
            return _envelope("shopping_list", "invalid", message="采购菜名无效。")
        dish_people: object = blob.get("people", people)
        if dish_people is None:
            return _envelope("shopping_list", "need_info", questions=[QUESTION_PEOPLE], groups=[])
        if isinstance(dish_people, bool) or not isinstance(dish_people, int):
            return _envelope("shopping_list", "invalid", message="人数需要是1到20的整数。")
        dish_people_error = _people_error(dish_people, required=True)
        if dish_people_error is not None:
            return _envelope("shopping_list", "invalid", message=dish_people_error)
        dish = find_dish(name)
        if dish is None:
            return _envelope(
                "shopping_list",
                "need_info",
                questions=[
                    f"“{name.strip()}”不在内置菜谱里。请改传 lines，每行包含名称、数量和单位；我不会替这道菜编造用量。"
                ],
                groups=[],
            )
        hits = _hits(_dish_parts(dish), constraints.allergies)
        if hits:
            excluded.append(dish.name)
            continue
        for ingredient in dish.ingredients:
            scaled = Ingredient(
                ingredient.name,
                scale_quantity(ingredient.quantity or 0, dish.base_servings, dish_people, ingredient.unit),
                ingredient.unit,
                ingredient.category,
            )
            error = _add_line(merged, scaled, recipe=dish.name)
            if error is not None:
                return _envelope("shopping_list", "invalid", message=error)
    for raw in lines or []:
        ingredient, error = parse_ingredient_dict(raw)
        if error is not None or ingredient is None:
            return _envelope("shopping_list", "invalid", message=error or "食材无效。")
        if _hits([ingredient.name], constraints.allergies):
            excluded.append(ingredient.name)
            continue
        add_error = _add_line(merged, ingredient, recipe="")
        if add_error is not None:
            return _envelope("shopping_list", "need_info", questions=[add_error], groups=[])
    if not dishes and not lines:
        return _envelope(
            "shopping_list",
            "need_info",
            questions=["要为哪些菜准备采购清单？"],
            groups=[],
        )
    conflicts: list[dict[str, Any]] = []
    units_by_name: dict[str, list[str]] = {}
    display_by_name: dict[str, str] = {}
    for line in merged.values():
        key = normalize_name(line.name)
        display_by_name.setdefault(key, line.name)
        units = units_by_name.setdefault(key, [])
        if line.unit not in units:
            units.append(line.unit)
    for key, units in units_by_name.items():
        if len(units) > 1:
            conflicts.append(_conflict(
                display_by_name[key],
                units,
                "同名食材单位不同，未换算，也未合并。",
            ))
    deducted: list[dict[str, Any]] = []
    pantry_applied = False
    pantry_note = None
    if pantry and not pantry_confirmed:
        pantry_note = "还没有确认家里已有这些食材，清单未扣除。"
    elif pantry_confirmed and not pantry:
        pantry_note = "已确认可以扣除，但没有给出家里已有的食材，所以没有扣除。"
    elif pantry_confirmed:
        pantry_applied = True
        for raw in pantry or []:
            ingredient, error = parse_ingredient_dict(raw)
            if error is not None or ingredient is None:
                return _envelope("shopping_list", "invalid", message=error or "家里的食材无效。")
            canonical, canon_error = _canonicalize(ingredient)
            if canon_error is not None or canonical is None:
                return _envelope("shopping_list", "invalid", message=canon_error or "家里的食材无效。")
            ingredient = canonical
            key_name = normalize_name(ingredient.name)
            same_name = [line for line in merged.values() if normalize_name(line.name) == key_name]
            if not same_name:
                continue
            if ingredient.quantity is None:
                conflicts.append(_conflict(
                    ingredient.name,
                    [line.unit for line in same_name],
                    "家里已有食材没有数量，未扣除。",
                ))
                continue
            matched = [line for line in same_name if line.unit == ingredient.unit]
            other_units = [line.unit for line in same_name if line.unit != ingredient.unit]
            if not matched:
                conflicts.append(_conflict(
                    ingredient.name,
                    [ingredient.unit, *other_units],
                    "家里已有食材的单位和清单不同，未换算，也未扣除。",
                ))
                continue
            line = matched[0]
            used = min(line.quantity, ingredient.quantity)
            line.quantity -= used
            deducted.append({
                "name": line.name,
                "quantity": json_quantity(used),
                "unit": line.unit,
                "remaining_to_buy": json_quantity(max(line.quantity, 0)),
            })
    groups: dict[str, list[dict[str, Any]]] = {category: [] for category in _CATEGORIES}
    for line in merged.values():
        if line.quantity <= 1e-9:
            continue
        groups[line.category].append({
            "name": line.name,
            "quantity": json_quantity(line.quantity),
            "unit": line.unit,
            "recipes": line.recipes,
        })
    visible = [
        {"category": category, "items": items}
        for category, items in groups.items()
        if items
    ]
    return _envelope(
        "shopping_list",
        "ok",
        pantry_confirmed=pantry_confirmed,
        pantry_applied=pantry_applied,
        pantry_note=pantry_note,
        groups=visible,
        unit_conflicts=conflicts,
        deducted=deducted,
        excluded_for_allergy=excluded,
        lines_are_not_rescaled=True,
    )
