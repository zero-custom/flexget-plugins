#!/usr/bin/env bash
#
# sync-upstream.sh — 同步本仓库派生插件所基于的官方 FlexGet 插件源码
# sync-upstream.sh — re-sync the official FlexGet plugin sources this repo derives from
#
# 用法 / Usage:
#   ./scripts/sync-upstream.sh check   # 仅检查官方文件是否有更新（退出码 1=有更新）/ check only (exit 1 = updates available)
#   ./scripts/sync-upstream.sh sync    # 执行同步（改写历史）/ perform the sync (rewrites history)
#
# 原理 / How it works:
#   根提交存放官方原始文件；派生修改版在其之后。官方更新时，在根提交后插入
#   「更新版」提交，再把派生修改版 rebase 到更新版之后。
#   The root commit holds the pristine upstream files; the derived plugins follow.
#   On upstream change, insert an "updated" commit after the root commit, then
#   rebase the derived commits on top of it.
set -euo pipefail

# ---------------------------------------------------------------------------
# 配置 / Configuration
# ---------------------------------------------------------------------------
UPSTREAM_REPO="Flexget/Flexget"
UPSTREAM_RAW="https://raw.githubusercontent.com/${UPSTREAM_REPO}"
UPSTREAM_API="https://api.github.com/repos/${UPSTREAM_REPO}"

# 官方文件路径 -> 仓库内的原始文件名（根提交中的名字）
# upstream file path -> pristine filename as stored at the root commit
FILES=(
  "flexget/components/notify/notifiers/gotify.py:gotify.py"
  "flexget/components/notify/notifiers/ntfysh.py:ntfysh.py"
  "flexget/plugins/filter/regexp.py:regexp.py"
)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
UPSTREAM_MD="${REPO_ROOT}/UPSTREAM.md"

# ---------------------------------------------------------------------------
# 工具函数 / Helpers
# ---------------------------------------------------------------------------
log()  { printf '\033[1;34m[sync]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[sync]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[sync]\033[0m %s\n' "$*" >&2; exit 1; }

# 取官方文件在默认分支的最新 commit（输出 "SHA 日期" 一行）
# Fetch the latest commit of a file on the default branch (prints "SHA DATE")
upstream_latest() {
  local path="$1" out
  out="$(curl -fsS "${UPSTREAM_API}/commits?path=${path}&per_page=1" 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
if d:
    print(d[0]["sha"][:12], d[0]["commit"]["author"]["date"][:10])
' 2>/dev/null)" || true
  printf '%s\n' "${out}"
}

# 从 UPSTREAM.md 读取已跟踪文件的 SHA（第二列为路径，第三列为 commit，以 | 分隔）
# Read the tracked SHA for a file (col 2 = path, col 3 = commit, separated by |)
tracked_sha() {
  local filename="$1"
  awk -F'|' -v f="${filename}" '
    index($3, f) > 0 { gsub(/[ `]/, "", $4); print $4 }
  ' "${UPSTREAM_MD}"
}

# 更新 UPSTREAM.md：改写该文件的 commit/日期/状态行与检查日期
# Update UPSTREAM.md: rewrite the file row (commit/date/status) and last-checked date
update_upstream_md() {
  local path="$1" sha="$2" date="$3" today
  today="$(date +%F)"
  python3 - "${path}" "${sha}" "${date}" "${today}" <<'PY'
import sys
path, sha, date, today = sys.argv[1:5]
with open("UPSTREAM.md", encoding="utf-8") as f:
    lines = f.readlines()
out = []
for line in lines:
    if line.startswith("| `") and "`" + path + "`" in line:
        plugin = line.split("`")[1]
        line = "| `%s` | `%s` | `%s` | %s | 已同步 / synced |\n" % (plugin, path, sha, date)
    elif line.startswith("检查日期"):
        line = "检查日期 / Last checked: %s\n" % today
    out.append(line)
with open("UPSTREAM.md", "w", encoding="utf-8") as f:
    f.writelines(out)
PY
}

# ---------------------------------------------------------------------------
# check 模式：只读对比上游与跟踪记录
# check mode: read-only comparison
# ---------------------------------------------------------------------------
check() {
  cd "${REPO_ROOT}"
  local changed=0
  local path filename line sha lsha
  for entry in "${FILES[@]}"; do
    path="${entry%%:*}"
    filename="${entry##*:}"
    line="$(upstream_latest "${path}")"
    sha="${line% *}"
    if [[ -z "${sha}" ]]; then
      warn "无法获取 ${path} 的上游 SHA（网络或限流）/ could not fetch ${path} (network/rate-limit)"
      continue
    fi
    lsha="$(tracked_sha "${filename}")"
    if [[ "${sha}" != "${lsha}" ]]; then
      log "${filename}: 上游 ${lsha} -> ${sha}（有更新 / update available）"
      changed=1
    else
      log "${filename}: ${lsha}（最新 / up to date）"
    fi
  done
  if [[ "${changed}" -eq 1 ]]; then
    warn "有更新可用 / updates available — run: ./scripts/sync-upstream.sh sync"
    return 1
  fi
  log "全部最新 / all up to date"
  return 0
}

# ---------------------------------------------------------------------------
# sync 模式：插入更新版提交并 rebase 派生改动
# sync mode: insert the updated commit and rebase the derived commits
# ---------------------------------------------------------------------------
sync() {
  cd "${REPO_ROOT}"
  if [[ "$(git symbolic-ref --short HEAD)" != "main" ]]; then
    die "请在 main 分支执行 / run from 'main'"
  fi
  if ! git diff --quiet; then
    die "工作区有未提交改动 / working tree not clean"
  fi

  # 收集需要更新的文件（path:filename:newsha:newdate:oldsha）
  # Collect files that need updating
  local -a affected=()
  local path filename line sha date lsha entry
  for entry in "${FILES[@]}"; do
    path="${entry%%:*}"
    filename="${entry##*:}"
    line="$(upstream_latest "${path}")"
    sha="${line% *}"
    if [[ -z "${sha}" ]]; then
      die "无法获取 ${path} 的上游 SHA / could not fetch ${path}"
    fi
    date="${line#* }"
    lsha="$(tracked_sha "${filename}")"
    if [[ "${sha}" != "${lsha}" ]]; then
      affected+=("${path}:${filename}:${sha}:${date}:${lsha}")
    fi
  done
  if [[ "${#affected[@]}" -eq 0 ]]; then
    log "上游无更新 / upstream unchanged"
    exit 0
  fi

  local root branch updated_msg
  root="$(git rev-list --max-parents=0 HEAD)"
  branch="sync-upstream"
  log "根提交 / root commit: ${root}"

  # 组装「更新版」提交信息
  # Build the "updated" commit message
  updated_msg="feat: 同步官方原始源码\n\n将官方插件文件更新至上游最新 commit,便于 diff 对照。\nUpdates the pristine upstream plugin files to the latest upstream commits for diff tracing.\n"
  for item in "${affected[@]}"; do
    updated_msg+="- $(echo "${item}" | cut -d: -f1) @ $(echo "${item}" | cut -d: -f3)\n"
  done

  # 1. 在根提交处开分支，更新官方原始文件
  #    Branch off the root commit and refresh the pristine files
  git branch -D "${branch}" >/dev/null 2>&1 || true
  git checkout -q -b "${branch}" "${root}"
  for item in "${affected[@]}"; do
    path="$(echo "${item}" | cut -d: -f1)"
    filename="$(echo "${item}" | cut -d: -f2)"
    sha="$(echo "${item}" | cut -d: -f3)"
    log "下载 / downloading ${path} @ ${sha}"
    curl -fsS "${UPSTREAM_RAW}/${sha}/${path}" -o "${filename}"
  done
  git add -A
  git commit -q -m "$(printf '%b' "${updated_msg}")"

  # 2. 把派生修改版 + README 等重放到更新版之后
  #    Replay derived commits (plugins, README, etc.) on top of the updated version
  log "rebase 派生提交到更新版之后 / rebasing derived commits..."
  if ! git rebase --onto "${branch}" "${root}" main; then
    warn "rebase 冲突 / rebase conflicts:"
    warn "  解决后执行 / resolve, then run: git add <files> && git rebase --continue"
    warn "  放弃本次同步 / abort: git rebase --abort && git checkout main"
    exit 1
  fi
  git checkout -q main
  git branch -q -D "${branch}"

  # 3. 更新 UPSTREAM.md 的跟踪记录
  #    Update the tracking record
  for item in "${affected[@]}"; do
    path="${item%%:*}"
    sha="$(echo "${item}" | cut -d: -f3)"
    date="$(echo "${item}" | cut -d: -f4)"
    update_upstream_md "${path}" "${sha}" "${date}"
  done
  git add "${UPSTREAM_MD}"
  git commit -q -m "docs: 更新上游跟踪记录

记录官方插件文件的最新 commit。
Records the latest upstream commits of the official plugin files."

  log "完成 / done — 检查后推送 / review then push: git push --force"
  log "建议 / suggested: git log --stat -3"
}

# ---------------------------------------------------------------------------
usage() {
  cat <<'HELP'
用法 / Usage:
  ./scripts/sync-upstream.sh check   # 检查官方文件更新 / check only
  ./scripts/sync-upstream.sh sync    # 执行同步（改写历史）/ sync (rewrites history)
HELP
}

case "${1:-}" in
  check) check ;;
  sync)  sync ;;
  *)     usage; exit 1 ;;
esac