---
name: food
description: 回答今天吃什么、按人数换算菜谱和采购清单，并在当前会话保存口味、忌口和过敏。用户聊吃饭、做菜、买菜、外食方向或饮食禁忌时使用。不接入外卖平台，不下单，不编造商家或实时价格。
---

# 美食

吃饭、做菜、买菜和饮食偏好都调用 `food` 工具。WebUI 和飞书私聊使用同一套工具，不需要额外安装命令。不要自己编造用量、商家或另一份偏好记录。

## 先调用工具

- `suggest`：今天吃什么。只填写用户说过的 `people`、`minutes`、`budget`、`tastes`、`avoid`、`allergies`、`ingredients_on_hand` 和 `mode`。
- `recipe`：菜谱。内置菜传 `dish` 和 `people`。内置菜谱没有的菜，把家常基准放进 `base_servings`、`base_ingredients` 和 `steps`，工具会标明 `caller_estimate`。
- `shopping_list`：内置菜传 `dishes`。非内置菜传已经写好数量的 `lines`，不要再按人数缩放。`pantry_confirmed` 只有在用户明确确认家里有这些食材时才为 true。
- `preferences`：`get`、`save`、`update`、`clear`。用来查看、保存、更新或清除口味、忌口和过敏。

工具返回 `need_info` 时，只问 `questions` 里的问题。不要猜测城市，不要猜测家庭人数，不要猜测饮食禁忌。

## 过敏和忌口

过敏由当前会话已保存的记录和用户这次的明确说法合并，这次调用只能增加，不能减少。口味、`allow_avoid` 或“今天想吃”都不能用口味取消过敏。忌口可以因用户明确说的本次例外而放开，但过敏原放进 `allow_avoid` 会被忽略。

要删除某一项过敏，必须由用户明确要求 `save` 一份新的完整过敏列表，或 `clear`。不要写入 `USER.md`，不要写入 `memory/MEMORY.md`，也不要写入 `SOUL.md`。

## 结果边界

用量是家常估计，不是实测营养或价格。`nutrition_measured` 和 `prices_measured` 为 false 时，不要说成实测结果或市场价格。

外食只转述 `eat_out.directions` 里的菜系和菜品。`local_restaurants` 为空时不要编造商家，也不要补充店名、链接、销量、评价、配送时长或实时价格。没有城市时不要推荐具体本地店。

`external_actions` 为空。不要下单，不要付款，不要联系商家，不要发消息，不要创建定时任务，也不要为了完成吃饭请求调用 `cron`、`message` 或搜索工具。

`status` 为 `blocked_allergy` 时不要补写做法。转述 `safety_notes`。不要承诺食疗或医疗效果。

偏好的范围是当前会话：只保留在这一条 WebUI 对话或这一个飞书会话里。不要说已经记住到所有聊天。所有渠道共用的会话会拒绝保存。

## 例子

```
food(action="suggest", people=2, minutes=30, budget="随便", tastes=["清淡"], ingredients_on_hand=[{"name": "鸡蛋"}, {"name": "番茄"}])
```

```
food(action="recipe", dish="番茄炒蛋", people=2)
```

```
food(action="shopping_list", dishes=[{"name": "番茄炒蛋", "people": 2}, {"name": "蒜蓉生菜", "people": 2}], pantry_confirmed=false)
```

```
food(action="preferences", preference_action="save", tastes=["清淡"], avoid=["香菜"], allergies=["花生"])
```
