---
name: food
description: 回答今天吃什么、按人数换算菜谱和采购清单，并在当前会话保存口味、忌口和过敏。用户聊吃饭、做菜、买菜、外食方向或饮食禁忌时使用。不接入外卖平台，不下单，不编造商家或实时价格。
---

# 美食

吃饭、做菜、买菜和饮食偏好都调用 `food` 工具。WebUI 和飞书私聊使用同一套工具，不需要额外安装命令。不要自己编造用量、商家或另一份偏好记录。

## 先调用工具

- `suggest`：今天吃什么。只填写用户说过的 `people`、`minutes`、`budget`、`tastes`、`avoid`、`allergies`、`ingredients_on_hand` 和 `mode`。
- `recipe`：只给已核对的内置菜传 `dish` 和 `people`。临时菜名、基准用量或步骤不能变成可执行做法；工具返回 `unverified` 时不要补写步骤。
- `shopping_list`：内置菜传 `dishes` 和人数。已经算好数量的 `lines` 不要同时传 `people`。千克和克、升和毫升会先换算再合并；茶匙、斤这类单位不换算。`pantry_confirmed` 只有在用户明确确认家里有这些食材时才为 true。
- `preferences`：只在 WebUI 或飞书私聊使用。`get` 查看，`save` 替换口味或忌口并追加过敏，`update` 追加，`clear` 清除口味或忌口。群会话不要调用。

工具返回 `need_info` 时，只问 `questions` 里的问题。不要猜测城市，不要猜测家庭人数，不要猜测饮食禁忌。

## 过敏和忌口

过敏由当前会话已保存的记录和用户这次的明确说法合并。`save`、`update` 和 `clear` 都不能删除已保存的过敏，只能追加。口味、`allow_avoid` 或“今天想吃”都不能用口味取消过敏。忌口可以因用户明确说的本次例外而放开，但过敏原放进 `allow_avoid` 会被忽略。

名称对上了只说明菜名、食材或步骤里写出了这个字。这不是医学核对，也不能证明没有过敏风险。交叉接触、共用器具、酱料和供应商未标明的成分都无法判断。不要写入 `USER.md`，不要写入 `memory/MEMORY.md`，也不要写入 `SOUL.md`。对话原文仍可能进入现有共享记忆或历史搜索，不要把元数据隔离说成端到端隐私。

## 结果边界

用量是家常估计，不是实测营养或价格。`nutrition_measured` 和 `prices_measured` 为 false 时，不要说成实测结果或市场价格。

外食只转述 `eat_out.directions` 里的菜系和菜品。`local_restaurants` 为空时不要编造商家，也不要补充店名、链接、销量、评价、配送时长或实时价格。没有城市时不要推荐具体本地店。

`external_actions` 为空。不要下单，不要付款，不要联系商家，不要发消息，不要创建定时任务，也不要为了完成吃饭请求调用 `cron`、`message` 或搜索工具。

`status` 为 `blocked_allergy` 或 `unverified` 时不要补写做法。转述 `safety_notes`。不要承诺食疗或医疗效果。

偏好元数据只保留在这一条 WebUI 对话或这一个飞书私聊里。群会话不能保存或读取。不要说已经记住到所有聊天，也不要说其他会话永远看不到用户说过的话。从对话分支出去时复制的是当前偏好，不是分支点之前的历史偏好。所有渠道共用的会话会拒绝保存。

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
