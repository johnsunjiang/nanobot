# PR #1 审查跟进

对应审查 `pr1_review`（head `135c4e6`）。检查名保持 `ruff`、`pytest`、`gitleaks`、`uv.lock`、`config-lint`。

## 这次没有改代码的项

### 严重 1

`main` 的 ruleset 仍由仓库所有者在网页上配置，本 PR 不改仓库设置。步骤在 `docs/repo-settings.md`。审查时 ruleset 还是空的；若所有者已经配好并要求上述五个检查名，不要改名。

### 次要 2 的格式检查和 shellcheck

`ruff check ext deploy scripts` 已进 CI。`ruff format --check` 跑 `ext`、`deploy` 和 `scripts/family`。家庭 Python 脚本放在 `scripts/family/`，`config_lint.py` 在这里。

对整个 `scripts/` 跑 `ruff format --check` 会改写 15 个上游脚本。上游 CONTRIBUTING 写明这棵树早于 `ruff format`，不要把格式化混进功能改动，同步时也会变成大冲突。shellcheck 同样没加：审查建议过，这次要求的是 ruff 范围；仓库里家庭侧的 shell 仍是 `scripts/sync-upstream.sh` 这一个占位脚本。

### 次要 8

不要在这个 PR 里删除上游发布 workflow。它们是从 `main` 继承的，删掉会在下次同步时再冲突。请所有者在 GitHub → Actions 里把下面四个 workflow 设为 Disabled（只点设置，不改文件）：

- `tui-release.yml`（Publish Terminal UI）
- `release-approve.yml`（Approve Exact Release）
- `release-candidate.yml`（Verify Release Candidate）
- `native-acceptance.yml`（Native package acceptance）

### 次要 9

第一份核心补丁（`patches/tool-policy-gate`）合入之前，再加跑上游 pytest 的 job，并排除 `tests/scripts/test_ci_workflows.py`（它仍断言旧的上游 `ci.yml`）。D5/M1 之前不加这个 job，也不把它列为必需检查。

### 次要 12

计划 v3 §9.0.1 写的上游 v0.4.0 是 `1c66b90`，那是错的。tag `v0.4.0` 指向 `8f7a7d17590de7ab187650381894dba2b9e060ab`。仓库和本文用后者。这是计划文档要改的地方，不是代码改动。
