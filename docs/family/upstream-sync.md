# 上游同步

本仓库是 [johnsunjiang/nanobot](https://github.com/johnsunjiang/nanobot)。`main` 的文件树从上游 [HKUDS/nanobot](https://github.com/HKUDS/nanobot) tag `v0.4.0`（`8f7a7d17590de7ab187650381894dba2b9e060ab`）导入。

每个克隆配置一次只读 remote：

```bash
git remote add upstream https://github.com/HKUDS/nanobot.git
git fetch upstream --tags
```

规则：

- `upstream` 只用于 fetch。不要向 HKUDS/nanobot 推送，也不要向上游开 pull request。
- 只跟上游 **release tag**。不要合并该 tag 之后的上游 `main` 提交。
- 在分支上整理同步结果，向本仓库的 `main` 开 pull request。禁止 force-push。
- `scripts/sync-upstream.sh` 只打印这些步骤，不会 fetch，也不会 push。

## 同步时会冲突的文件

家庭改动碰过这些上游文件。同步 release tag 时按下面处理，不要整文件用上游版本盖掉。

| 文件 | 家庭侧保留什么 | 怎么处理 |
|---|---|---|
| `.github/workflows/ci.yml` | D1 的五项检查：`ruff`、`pytest`、`gitleaks`、`uv.lock`、`config-lint`。ruff 和 pytest 还要保留美食工具与 `tests/agent/tools/test_food.py`、`tests/agent/test_builtin_food_skill.py` | 保留本仓库的 workflow。不要换回上游的 Test Suite，也不要删掉美食检查。 |
| `.gitignore` | 跟踪 `uv.lock`（上游忽略它） | 保留「不忽略 `uv.lock`」这一行。`poetry.lock` 继续忽略。 |
| `README.md` | 指向本文的一行链接 | 保留那一行，其余用上游 README。 |

`CONTRIBUTING.md` 已改回与上游 v0.4.0 相同，不再作为固定冲突文件。家庭仓库的同步规则只写在这里。
