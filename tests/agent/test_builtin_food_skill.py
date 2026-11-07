"""Static loading checks for the built-in food skill.

These tests do not call a model. A loaded instruction is not a guarantee that
a model will follow it; the food tool tests cover the executable behavior.
"""

from pathlib import Path

from nanobot.agent.skill_metadata import valid_skill_metadata
from nanobot.agent.skills import BUILTIN_SKILLS_DIR, SkillsLoader


def test_food_skill_loads_with_session_and_safety_limits(tmp_path: Path) -> None:
    loader = SkillsLoader(tmp_path, builtin_skills_dir=BUILTIN_SKILLS_DIR)
    entries = [entry for entry in loader.list_skills() if entry["name"] == "food"]
    assert entries == [{
        "name": "food",
        "path": str(BUILTIN_SKILLS_DIR / "food" / "SKILL.md"),
        "source": "builtin",
    }]
    content = loader.load_skill("food")
    assert content is not None
    metadata = loader.get_skill_metadata("food")
    assert metadata is not None
    assert valid_skill_metadata(metadata, "food")
    assert "今天吃什么" in loader.get_skill_description("food")
    summary = loader.build_skills_summary()
    assert "**food**" in summary

    for phrase in (
        "调用 `food` 工具",
        "不要猜测城市",
        "不要猜测家庭人数",
        "不要猜测饮食禁忌",
        "不能用口味取消",
        "家常估计",
        "不是实测营养或价格",
        "不要编造商家",
        "不要下单",
        "不要创建定时任务",
        "不要写入 `USER.md`",
        "不要写入 `memory/MEMORY.md`",
        "local_restaurants",
        "external_actions",
        "当前会话",
        "都不能删除已保存的过敏",
        "不能变成可执行做法",
        "交叉接触",
        "群会话不能保存或读取",
        "不是分支点之前的历史偏好",
        "端到端隐私",
    ):
        assert phrase in content
