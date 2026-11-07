"""Food tool: meals, recipes, shopping lists, and session-scoped diet preferences."""

# pyright: reportIncompatibleMethodOverride=false

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from nanobot.agent.tools._food import (
    EPHEMERAL_SESSION_REFUSAL,
    FOOD_PREFERENCES_KEY,
    GROUP_PREFERENCE_REFUSAL,
    INTERNAL_SESSION_REFUSAL,
    NO_SESSION_REFUSAL,
    SESSION_SCOPE_NOTE,
    SHARED_SESSION_READ_WARNING,
    SHARED_SESSION_SAVE_REFUSAL,
    UNREADABLE_PREFERENCE_WARNING,
    UNSUPPORTED_CHANNEL_REFUSAL,
    FoodPrefs,
    apply_preference_change,
    build_constraints,
    build_recipe,
    build_shopping_list,
    limits,
    parse_ingredient_dict,
    parse_stored_prefs,
    plan_meal,
)
from nanobot.agent.tools.base import Tool, ToolResult, tool_parameters
from nanobot.agent.tools.context import RequestContext, ToolContext, current_request_context
from nanobot.agent.tools.schema import (
    ArraySchema,
    BooleanSchema,
    IntegerSchema,
    NumberSchema,
    ObjectSchema,
    StringSchema,
    tool_parameters_schema,
)
from nanobot.runtime_context import RuntimeContextBlock, wrap_runtime_context_lines
from nanobot.session.keys import UNIFIED_SESSION_KEY, is_internal_session
from nanobot.session.state import SessionConflictError

if TYPE_CHECKING:
    from nanobot.session.manager import SessionManager


_INGREDIENT = ObjectSchema(
    name=StringSchema("食材名", min_length=1, max_length=40),
    quantity=NumberSchema(
        description="数量。没有数量就省略。超过100000不能汇总。",
        minimum=0,
        maximum=100_000,
        nullable=True,
    ),
    unit=StringSchema(
        "单位。克和g是同一种写法。千克、公斤和kg按1000倍换算成克，升按1000倍换算成毫升。茶匙和斤不换算。",
        max_length=16,
        nullable=True,
    ),
    category=StringSchema("蔬菜、肉蛋海鲜、调味、主食或其他", max_length=16, nullable=True),
    required=["name"],
    additional_properties=False,
)
_FOOD_PARAMETERS = tool_parameters_schema(
    action=StringSchema(
        "suggest 今天吃什么；recipe 按人数换算菜谱；shopping_list 汇总采购；preferences 读取或修改当前会话的饮食偏好。",
        enum=["suggest", "recipe", "shopping_list", "preferences"],
    ),
    people=IntegerSchema(description="这一餐的人数。用户没说就省略，不要猜测。", minimum=1, maximum=20, nullable=True),
    minutes=IntegerSchema(description="可用分钟数。用户没说就省略，不要猜测。", minimum=0, maximum=240, nullable=True),
    budget=StringSchema("用户的预算原话。不要改写成市场价格。", max_length=80, nullable=True),
    mode=StringSchema("cook 自己做，eat_out 外食方向，either 两种都给。", enum=["cook", "eat_out", "either"], nullable=True),
    tastes=ArraySchema(StringSchema("", max_length=32), description="口味。不能用来取消过敏。", max_items=20, nullable=True),
    avoid=ArraySchema(StringSchema("", max_length=32), description="忌口，不是过敏。", max_items=20, nullable=True),
    allergies=ArraySchema(StringSchema("", max_length=32), description="过敏食材。硬性排除。保存、更新和清除都只能追加，不能删除已有项。", max_items=20, nullable=True),
    allow_avoid=ArraySchema(StringSchema("", max_length=32), description="用户明确说这一餐可以例外的忌口。对过敏无效。", max_items=20, nullable=True),
    ingredients_on_hand=ArraySchema(_INGREDIENT, description="用户说家里已经有的食材。", max_items=40, nullable=True),
    dish=StringSchema("菜名。", max_length=40, nullable=True),
    base_servings=IntegerSchema(description="调用方给出的基准用量是按几个人写的。", minimum=1, maximum=20, nullable=True),
    base_ingredients=ArraySchema(_INGREDIENT, description="内置菜谱没有这道菜时的家常基准食材。", max_items=40, nullable=True),
    steps=ArraySchema(StringSchema("", max_length=200), description="内置菜谱没有这道菜时的家常步骤。", max_items=20, nullable=True),
    dishes=ArraySchema(
        ObjectSchema(
            name=StringSchema("内置菜名", min_length=1, max_length=40),
            people=IntegerSchema(description="这道菜的人数；省略则用顶层 people。", minimum=1, maximum=20, nullable=True),
            required=["name"],
            additional_properties=False,
        ),
        description="要汇总的内置菜。",
        max_items=12,
        nullable=True,
    ),
    lines=ArraySchema(_INGREDIENT, description="已经写好数量的采购行。传入后不再按人数缩放。", max_items=80, nullable=True),
    pantry=ArraySchema(_INGREDIENT, description="用户确认家里已有、可以从清单扣除的食材。", max_items=40, nullable=True),
    pantry_confirmed=BooleanSchema(description="只有用户明确确认 pantry 是家里已有的食材时才为 true。", nullable=True),
    preference_action=StringSchema(
        "get 查看，save 替换口味或忌口并追加过敏，update 追加，clear 清除口味或忌口。都不能删除已有过敏。",
        enum=["get", "save", "update", "clear"],
        nullable=True,
    ),
    fields=ArraySchema(
        StringSchema("", enum=["tastes", "avoid", "allergies", "all"]),
        description="clear 时要清除的字段。省略表示全部。",
        max_items=4,
        nullable=True,
    ),
    required=["action"],
)

_READ_WARNINGS = {
    "shared": SHARED_SESSION_READ_WARNING,
    "internal": "内部会话里不读取饮食偏好。",
    "ephemeral": "这一回合不保留会话，没有读取已保存的饮食偏好。",
    "no_session": "没有当前聊天会话，只使用这次明确说出的内容。",
    "unreadable": UNREADABLE_PREFERENCE_WARNING,
    "group_or_unknown": GROUP_PREFERENCE_REFUSAL,
    "unsupported_channel": UNSUPPORTED_CHANNEL_REFUSAL,
}


def preference_route(channel: str, metadata: object, session_key: str | None) -> str:
    """Return where a diet-preference read or write is allowed."""
    if not session_key:
        return "no_session"
    if session_key == UNIFIED_SESSION_KEY:
        return "shared"
    if is_internal_session(session_key):
        return "internal"
    if channel == "websocket":
        return "allowed"
    if channel == "feishu" or channel.startswith("feishu."):
        chat_type: object = None
        if isinstance(metadata, dict):
            chat_type = cast(dict[object, object], metadata).get("chat_type")
        if chat_type == "p2p":
            return "allowed"
        return "group_or_unknown"
    return "unsupported_channel"


def _dump(payload: dict[str, Any], warnings: list[str] | None = None) -> str:
    if warnings:
        payload["warnings"] = warnings
    return json.dumps(payload, ensure_ascii=False)


def _encode_values(values: tuple[str, ...]) -> str:
    encoded = json.dumps(list(values), ensure_ascii=False)
    return encoded.replace("[", "\\u005b").replace("]", "\\u005d")


@tool_parameters(_FOOD_PARAMETERS)
class FoodTool(Tool):
    """Answer meal questions without ordering food or sharing diet preferences."""

    def __init__(self, sessions: SessionManager) -> None:
        self._sessions = sessions

    @classmethod
    def enabled(cls, ctx: ToolContext) -> bool:
        return ctx.sessions is not None

    @classmethod
    def create(cls, ctx: ToolContext) -> Tool:
        if ctx.sessions is None:
            raise RuntimeError("FoodTool requires a session manager")
        return cls(sessions=ctx.sessions)

    @property
    def name(self) -> str:
        return "food"

    @property
    def description(self) -> str:
        return (
            "家庭吃饭：今天吃什么、按人数换算内置菜谱、汇总采购清单，以及在 WebUI 或飞书私聊保存口味、忌口和过敏。"
            "只使用用户明确说过的人数、时间、预算、口味、忌口、过敏和已有食材；缺人数、可用分钟或预算时只追问这些。"
            "不要猜测城市、家庭人数或饮食禁忌。过敏按菜名、食材和步骤里的名称包含排除，不能用口味取消，也不能删除已保存的过敏。"
            "名称没对上不表示没有过敏风险。临时配方不能给出可执行做法。"
            "用量是家常估计，不是实测营养或价格。外食只给菜系和菜品方向；没有城市就不要推荐具体店，"
            "也不要编造商家、价格、销量、评价、配送时长或链接。"
            "不要下单、付款、联系商家、发消息或创建定时任务。"
            "偏好只写入当前私聊会话的元数据。对话原文仍可能进入现有共享记忆或历史搜索。"
        )

    @property
    def read_only(self) -> bool:
        return False

    def runtime_context_provider(self):
        return self._provide_runtime_context

    async def _provide_runtime_context(self, request: RequestContext) -> RuntimeContextBlock | None:
        prefs, status = await self._load(request)
        if status != "ok" or prefs is None:
            return None
        lines = ["food_preferences_scope: session"]
        if prefs.allergies:
            lines.append("allergies: " + _encode_values(prefs.allergies))
        if prefs.avoid:
            lines.append("avoid: " + _encode_values(prefs.avoid))
        if prefs.tastes:
            lines.append("tastes: " + _encode_values(prefs.tastes))
        lines.append("allergies_are_hard_exclusions: true")
        return RuntimeContextBlock(source="food", content=wrap_runtime_context_lines(lines))

    async def _load(
        self, request: RequestContext | None = None,
    ) -> tuple[FoodPrefs | None, str]:
        ctx = current_request_context() if request is None else request
        if ctx is None:
            return None, "no_session"
        session_key = ctx.session_key
        route = preference_route(ctx.channel, ctx.metadata, session_key)
        if route != "allowed" or session_key is None:
            return None, "no_session" if session_key is None else route
        if not ctx.persist_session:
            return None, "ephemeral"
        payload = await self._sessions.state.read_metadata(session_key)
        if payload is None:
            return None, "absent"
        prefs, unreadable = parse_stored_prefs(payload.get("metadata"))
        if unreadable:
            return None, "unreadable"
        if prefs is None:
            return None, "absent"
        return prefs, "ok"

    async def _write(self, prefs: FoodPrefs | None) -> str | None:
        ctx = current_request_context()
        if ctx is None or not ctx.session_key:
            return NO_SESSION_REFUSAL
        header = await self._sessions.state.get_header(ctx.session_key)

        def change(metadata: dict[str, Any]) -> None:
            if prefs is None:
                metadata.pop(FOOD_PREFERENCES_KEY, None)
            else:
                metadata[FOOD_PREFERENCES_KEY] = prefs.to_json()

        try:
            await self._sessions.state.mutate_metadata(
                ctx.session_key,
                change,
                expected_generation=header.generation,
            )
        except SessionConflictError:
            return "本会话刚被替换，饮食偏好没有写入。请再明确说一次。"
        return None

    def _save_refusal(self, status: str) -> str | None:
        if status == "shared":
            return SHARED_SESSION_SAVE_REFUSAL
        if status == "internal":
            return INTERNAL_SESSION_REFUSAL
        if status == "ephemeral":
            return EPHEMERAL_SESSION_REFUSAL
        if status == "no_session":
            return NO_SESSION_REFUSAL
        if status == "group_or_unknown":
            return GROUP_PREFERENCE_REFUSAL
        if status == "unsupported_channel":
            return UNSUPPORTED_CHANNEL_REFUSAL
        return None

    async def execute(
        self,
        action: str,
        people: int | None = None,
        minutes: int | None = None,
        budget: str | None = None,
        mode: str | None = None,
        tastes: list[str] | None = None,
        avoid: list[str] | None = None,
        allergies: list[str] | None = None,
        allow_avoid: list[str] | None = None,
        ingredients_on_hand: list[dict[str, Any]] | None = None,
        dish: str | None = None,
        base_servings: int | None = None,
        base_ingredients: list[dict[str, Any]] | None = None,
        steps: list[str] | None = None,
        dishes: list[dict[str, Any]] | None = None,
        lines: list[dict[str, Any]] | None = None,
        pantry: list[dict[str, Any]] | None = None,
        pantry_confirmed: bool | None = None,
        preference_action: str | None = None,
        fields: list[str] | None = None,
    ) -> str:
        if action == "preferences":
            return await self._preferences(preference_action, tastes, avoid, allergies, fields)
        saved, status = await self._load()
        warnings = [text for key, text in _READ_WARNINGS.items() if key == status]
        constraints, error = build_constraints(
            saved if status == "ok" else None,
            tastes=tastes,
            avoid=avoid,
            allergies=allergies,
            allow_avoid=allow_avoid,
            saved_state="ok" if status == "ok" else "absent",
        )
        if error is not None or constraints is None:
            return _dump({"status": "invalid", "action": action, "message": error or "饮食条件无效。", "limits": limits()})
        if action == "suggest":
            on_hand, on_hand_error = _names(ingredients_on_hand)
            if on_hand_error is not None or on_hand is None:
                return _dump({"status": "invalid", "action": action, "message": on_hand_error or "已有食材无效。", "limits": limits()})
            return _dump(plan_meal(
                people=people,
                minutes=minutes,
                budget=budget,
                mode=mode,
                on_hand=on_hand,
                constraints=constraints,
            ), warnings)
        if action == "recipe":
            return _dump(build_recipe(
                dish=dish,
                people=people,
                base_servings=base_servings,
                base_ingredients=list(base_ingredients or []),
                steps=steps,
                constraints=constraints,
            ), warnings)
        if action == "shopping_list":
            return _dump(build_shopping_list(
                dishes=dishes,
                lines=list(lines or []),
                people=people,
                pantry=list(pantry or []),
                pantry_confirmed=bool(pantry_confirmed),
                constraints=constraints,
            ), warnings)
        return ToolResult.error("food 动作只能是 suggest、recipe、shopping_list 或 preferences。")

    async def _preferences(
        self,
        operation: str | None,
        tastes: list[str] | None,
        avoid: list[str] | None,
        allergies: list[str] | None,
        fields: list[str] | None,
    ) -> str:
        if operation is None:
            return _dump({
                "status": "need_info",
                "action": "preferences",
                "questions": ["要查看、保存、更新，还是清除当前会话的饮食偏好？"],
                "limits": limits(),
            })
        saved, status = await self._load()
        refusal = self._save_refusal(status)
        if operation == "get":
            if status == "unreadable":
                return _dump({
                    "status": "unreadable",
                    "action": "preferences",
                    "persisted": False,
                    "scope": "session",
                    "message": UNREADABLE_PREFERENCE_WARNING + "这一版不能删除其中可能存在的过敏，所以没有改动。",
                    "limits": limits(),
                })
            if refusal is not None:
                return ToolResult.error(refusal)
            return _preference_result("get", saved, [], persisted=False)
        if refusal is not None:
            return ToolResult.error(refusal)
        if status == "unreadable":
            return _dump({
                "status": "unreadable",
                "action": "preferences",
                "persisted": False,
                "message": "当前会话里的饮食偏好无法读取。这一版不能删除其中可能存在的过敏，所以没有改动。",
                "limits": limits(),
            })
        current = saved
        updated, change_warnings, error = apply_preference_change(
            current,
            operation=operation,
            tastes=tastes,
            avoid=avoid,
            allergies=allergies,
            fields=fields,
        )
        if error is not None:
            return _dump({"status": "invalid", "action": "preferences", "message": error, "persisted": False, "limits": limits()})
        write_error = await self._write(updated)
        if write_error is not None:
            return ToolResult.error(write_error)
        return _preference_result(operation, updated, change_warnings, persisted=True)


def _names(items: list[dict[str, Any]] | None) -> tuple[list[str] | None, str | None]:
    names: list[str] = []
    for raw in items or []:
        ingredient, error = parse_ingredient_dict(raw)
        if error is not None or ingredient is None:
            return None, error or "已有食材无效。"
        names.append(ingredient.name)
    return names, None


def _preference_result(
    operation: str,
    prefs: FoodPrefs | None,
    warnings: list[str],
    *,
    persisted: bool,
) -> str:
    return _dump({
        "status": "ok",
        "action": "preferences",
        "preference_action": operation,
        "preferences": None if prefs is None else prefs.to_json(),
        "warnings": warnings,
        "persisted": persisted,
        "scope": "session",
        "scope_note": SESSION_SCOPE_NOTE,
        "limits": limits(),
    })
