# 上游跟踪 / Upstream Tracking

本仓库的三个插件基于官方 [Flexget/Flexget](https://github.com/Flexget/Flexget) 源码二次开发。本文件跟踪官方插件文件的上游 commit,便于在官方更新时同步派生插件。
These three plugins are derived from the official [Flexget/Flexget](https://github.com/Flexget/Flexget) sources. This file tracks the upstream commits of the official plugin files so the derived plugins can be re-synced when upstream changes.

## 跟踪状态 / Tracking Status

| 插件 / Plugin | 上游文件 / Upstream file | 上游 commit | 修订日期 / Date | 状态 / Status |
|---|---|---|---|---|
| `gotify` | `flexget/components/notify/notifiers/gotify.py` | `1579cadc07ba` | 2025-04-15 | 最新 / up to date |
| `ntfysh` | `flexget/components/notify/notifiers/ntfysh.py` | `1579cadc07ba` | 2025-04-15 | 最新 / up to date |
| `regexp` | `flexget/plugins/filter/regexp.py` | `c32454658f60` | 2025-07-13 | 最新 / up to date |

检查日期 / Last checked: 2026-08-12

> 说明:官方文件在上述 commit 之后长期未修改,因此**不标注 FlexGet 版本号**——派生插件的官方部分对应的是上游固定 commit 处的源码,而非任何随版本演化的发行版。
> Note: the upstream files have not been modified since the commits above, so this repo deliberately does not reference any FlexGet release version — the official portion of these plugins corresponds to fixed upstream commits, not an evolving distribution.

## 同步流程 / Sync Procedure

当官方插件文件更新时,按以下步骤把变更同步进派生插件(核心是「在原始版提交后插入更新版,再把派生修改版 rebase 到更新版之后」):
When an upstream plugin file changes, sync it into the derived plugins as follows (the core is "insert an updated-version commit after the pristine commit, then rebase the derived commits onto it"):

### 1. 检查更新 / Check for updates

```bash
./scripts/sync-upstream.sh check
```

输出「up to date」即无需操作;显示 SHA 变化时进入下一步。
If it reports "up to date", nothing to do; if a SHA change is shown, proceed.

### 2. 同步 / Sync

```bash
./scripts/sync-upstream.sh sync
```

脚本自动执行:
The script automatically:

1. 从 GitHub API 取三个官方文件在 `develop` 分支的最新 commit;
   Fetches the latest `develop` commit of each official file from the GitHub API;
2. 在**根提交(原始版)**处新建 `sync-upstream` 分支,下载新版本文件,提交「更新版」;
   Creates a `sync-upstream` branch at the **root commit (pristine sources)**, downloads the new files, and commits an "updated" version;
3. `git rebase --onto sync-upstream <root> main` — 把派生修改版与 README 重放到更新版之后;
   `git rebase --onto sync-upstream <root> main` — replays the derived plugins and README on top of the updated version;
4. 更新本文件中的 SHA 与检查日期。
   Updates the SHAs and last-checked date in this file.

### 3. 处理冲突(若有)/ Resolve conflicts (if any)

若派生改动与上游改动重叠,rebase 会停在冲突处:
If derived changes overlap upstream changes, rebase stops at the conflict:

```bash
git status          # 查看冲突文件 / see conflicted files
# 手动编辑冲突文件 / manually edit the conflicted files
git add <文件>       # 标记已解决 / mark resolved
git rebase --continue
```

### 4. 推送 / Push

```bash
git checkout main && git branch -d sync-upstream
git push --force    # 历史已改写 / history was rewritten
```

## 手动同步(等价步骤)/ Manual Sync (equivalent steps)

```bash
git checkout -b sync-upstream $(git rev-list --max-parents=0 HEAD)   # 根提交处 / at root commit
curl -o gotify.py https://raw.githubusercontent.com/Flexget/Flexget/<NEW_SHA>/flexget/components/notify/notifiers/gotify.py
curl -o ntfysh.py https://raw.githubusercontent.com/Flexget/Flexget/<NEW_SHA>/flexget/components/notify/notifiers/ntfysh.py
curl -o regexp.py https://raw.githubusercontent.com/Flexget/Flexget/<NEW_SHA>/flexget/plugins/filter/regexp.py
git add -A && git commit -m "feat: 同步官方原始源码至上游 @ <NEW_SHA>"
git rebase --onto sync-upstream $(git rev-list --max-parents=0 HEAD) main
git checkout main && git branch -d sync-upstream
git push --force
```

> 注意:`git push --force` 会改写远程历史,仅当你是该仓库唯一维护者时执行。
> Caution: `git push --force` rewrites remote history; only run it if you are the sole maintainer.