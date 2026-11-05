# patches/tool-policy-gate

计划中的唯一核心补丁：通用工具策略闸门。本目录现在只有这份说明，没有补丁文件，也没有实现。

闸门的入口是 `decide(tool, params, role, session_kind)`。`session_kind` 预计为 `private`、`group`、`cron`、`subagent`、`dream`、`webui`。返回值是三级之一：

- `allow`：可以执行
- `deny`：拒绝
- `require_approval`：不执行，留给以后的审批流

约定：

- 未知工具、未知角色或未知 `session_kind` 一律 `deny`（fail-closed）。
- 第一版只做拒绝。表上标成 `require_approval` 的调用，在审批流落地之前也按 `deny` 处理。
- 生活实例里默认拒绝的包括：主动 `message`（当前私聊回复除外，且仍受角色限制）、`send_session_message`、`search_sessions`、`read_session`、内置 `cron`、`exec`、`cli_apps`、`mcp_*`、`image_generation`，以及 `write_file` / `edit_file` / `apply_patch`。
- 自研能力（账本、提醒、画像、审批、转发）走 `ext/family_tools/`，由同一套 `decide` 判定，不在上游里各写一套判断。

补丁以后由脚本 `git apply` 到可部署树上。同步上游 release tag 时再解决冲突。
