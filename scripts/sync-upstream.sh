#!/usr/bin/env bash
# Placeholder for syncing this repo to an HKUDS/nanobot release tag.
# Prints the intended steps and exits 0. Does not fetch, merge, or push.
set -euo pipefail

upstream_url="https://github.com/HKUDS/nanobot.git"
tag="${1:-<upstream-release-tag>}"

cat <<EOF
upstream sync 还没实现。下面是以后要做的事。这个脚本现在不会 fetch、合并或推送。

1. 每个克隆只加一次只读 remote（不要向它 push）：
     git remote add upstream ${upstream_url}
     git fetch upstream --tags
2. 只使用上游 release tag，例如 ${tag}。不要合并该 tag 之后的上游 main。
3. 从本仓库 main 拉出分支，把该 tag 同步进来。
4. 向本仓库的 main 开 pull request。
5. 禁止 force-push。不要向 HKUDS/nanobot 推送或开 pull request。
EOF
