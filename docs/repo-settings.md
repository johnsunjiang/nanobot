# 仓库保护设置

这些规则需要仓库所有者在 GitHub 网页上亲手配置。本文不改仓库设置，自动化也不会改。

配置入口：仓库页面 → **Settings** → **Rules** → **Rulesets**。

CI 检查名以下面 PR 上出现的为准。当前工作流把每个 job 的 `name` 设成这些字符串：

- `ruff`
- `pytest`
- `gitleaks`
- `uv.lock`
- `config-lint`

如果 Ruleset 的搜索框里显示的是带工作流前缀的名字（例如 `CI / ruff`），用搜索框里的完整字符串，不要手改。

## 分支 ruleset：`main`

1. **New ruleset** → **New branch ruleset**。
2. **Ruleset Name**：`main`。
3. **Enforcement status**：**Active**。
4. **Bypass list**：留空。不要给 Admin、Maintain、Write 或任何应用旁路。
5. **Target branches** → **Add target** → **Include by pattern** → 填 `main`。也可以改用 **Include default branch**（本仓库默认分支是 `main`）。不要加其他分支。
6. 勾选这些 **Branch rules**，其余不要勾：
   - **Restrict deletions**
   - **Block force pushes**
   - **Require a pull request before merging**
     - **Required approvals** 填 `0`（只要求走 pull request，不要求评审人数）。如果界面默认是 1，改成 0。
     - 不要勾 Dismiss stale pull request approvals、Require review from Code Owners、Require approval of the most recent reviewable push、Require conversation resolution。
   - **Require status checks to pass**
     - 在搜索框加入上面五个检查：`ruff`、`pytest`、`gitleaks`、`uv.lock`、`config-lint`。
     - **Require branches to be up to date before merging** 不勾。本清单没有要求这项。
7. 不要勾 **Restrict creations**、**Restrict updates**。勾了之后普通合并也会被挡住。
8. 保存 ruleset。

验收：直接 `git push` 到 `main` 被拒绝；没有绿色的上述五个检查时不能合并。

## 标签 ruleset：`family-v*`

1. **New ruleset** → **New tag ruleset**。
2. **Ruleset Name**：`family-v`。
3. **Enforcement status**：**Active**。
4. **Bypass list**：只加仓库所有者本人。
   - **Add bypass** → 选择用户 `johnsunjiang`。
   - 不要加 Maintain、Write，也不要加整个 Admin 角色。如果界面只能选角色、不能选人，选 **Repository admin**，并且不要再把其他人设为 Admin。
5. **Target tags** → **Add target** → **Include by pattern** → 填 `family-v*`。
6. 勾选这些 **Tag rules**，其余不要勾：
   - **Restrict creations**
   - **Restrict updates**
   - **Restrict deletions**
   - **Block force pushes**
7. 保存 ruleset。

验收：其他人不能创建、移动或删除 `family-v*` 标签；所有者可以通过 bypass 操作这些标签。
