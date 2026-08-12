# FlexGet 自定义插件集<br>Custom FlexGet Plugins

[FlexGet](https://flexget.com/) 的自定义插件集合，为个人使用场景定制。 <br>
A collection of [FlexGet](https://flexget.com/) plugins customized for personal use.

| 插件<br>Plugin | 类型<br>Type | 说明<br>Description | 基于官方插件源码<br>Based on upstream |
|---|---|---|---|
| [`gotify_mtls`](#gotify_mtls) | 通知器<br>notifier | 支持双向 TLS（mTLS）的 Gotify 通知<br>Gotify notification with mutual TLS (mTLS) support | `gotify` · 上游 @ `1579cadc07ba`（2025-04-15）|
| [`ntfysh_mtls`](#ntfysh_mtls) | 通知器<br>notifier | 支持双向 TLS（mTLS）的 ntfy.sh 通知<br>ntfy.sh notification with mutual TLS (mTLS) support | `ntfysh` · 上游 @ `1579cadc07ba`（2025-04-15）|
| [`regexp_nest`](#regexp_nest) | 过滤器<br>filter | 内置 `regexp` 的超集，支持嵌套 `within` 子模式路由<br>Superset of built-in `regexp` with nested `within` sub-pattern routing | `regexp` · 上游 @ `c32454658f60`（2025-07-13）|

> 各插件均基于对应官方插件源码二次开发，新增功能另行标注；官方代码的既有行为与 schema 保持不变。官方插件源码在上述 commit 之后长期未修改，因此**不标注 FlexGet 版本号**——本插件的官方部分对应的是上游固定 commit 处的源码，而非任何随版本演化的 FlexGet 发行版。
>
> Each plugin is derived from the corresponding upstream plugin source; additions are marked separately and the upstream behavior and schema are kept unchanged. The upstream sources have not been modified since the commits above, so this repo deliberately **does not reference any FlexGet release version** — the official portion of these plugins corresponds to the fixed upstream commits, not to an evolving FlexGet distribution.

## 安装<br>Installation

将需要的 `.py` 文件放入 FlexGet 配置目录下的 `plugins/` 文件夹（例如 `/config/plugins/`），重启 FlexGet 即可自动加载。插件名即配置中的关键字，可同时使用多个插件。 <br>
Drop the desired `.py` files into the `plugins/` folder of your FlexGet config directory (e.g. `/config/plugins/`) and restart FlexGet — they are loaded automatically. The plugin name is the config keyword; multiple plugins can be used at once.

> 要求 FlexGet 版本支持 `api_ver=2` 插件（FlexGet 2.x 及以上）。
> Requires FlexGet with `api_ver=2` plugin support (FlexGet 2.x or later).

---

## gotify_mtls

Gotify 通知插件，在官方 `gotify` 插件的基础上增加**双向 TLS（mTLS）**支持：可配置客户端证书、私钥与 CA 证书，适合对接启用 mTLS 的自建 Gotify 实例。 <br>
Gotify notifier built on the upstream `gotify` plugin, adding **mutual TLS (mTLS)** support: configurable client certificate, private key and CA certificate — for self-hosted Gotify instances that enforce mTLS.

### 配置<br>Configuration

```yaml
notify:
  entries:
    via:
      - gotify_mtls:
          url: https://gotify.example.com   # 必填
          token: <GOTIFY_TOKEN>             # 必填
          priority: 4                       # 可选，默认 4
          content_type: text/plain          # 可选，text/plain | text/markdown，默认 text/plain
          client_cert: /certs/client.pem    # 可选，mTLS 客户端证书（须与 client_key 成对）
          client_key: /certs/client-key.pem # 可选，mTLS 客户端私钥（须与 client_cert 成对）
          ca_cert: /certs/ca.pem            # 可选，CA 证书，设置后取代 verify
          verify: true                      # 可选，默认 true
```

### 参数说明<br>Parameters

| 参数<br>Param | 必填<br>Required | 默认<br>Default | 说明<br>Description |
|---|---|---|---|
| `url` | ✅ | — | Gotify 服务地址，请求发送至 `<url>/message`<br>Server URL, requests go to `<url>/message` |
| `token` | ✅ | — | Gotify 应用令牌，作为查询参数传递<br>App token, passed as query param |
| `priority` | — | `4` | 通知优先级（1–10）<br>Notification priority (1–10) |
| `content_type` | — | `text/plain` | 消息渲染类型：`text/plain` 或 `text/markdown`<br>Message content type: `text/plain` or `text/markdown` |
| `client_cert` | — | — | mTLS 客户端证书路径；与 `client_key` 必须成对出现<br>mTLS client cert path; must pair with `client_key` |
| `client_key` | — | — | mTLS 客户端私钥路径；与 `client_cert` 必须成对出现<br>mTLS client key path; must pair with `client_cert` |
| `ca_cert` | — | — | 自定义 CA 证书路径；设置后以它校验服务端证书（取代 `verify`）<br>Custom CA path; used to verify the server cert instead of `verify` |
| `verify` | — | `true` | 是否校验服务端证书；`false` 关闭校验（不推荐）<br>Verify the server cert; `false` disables it (not recommended) |

### 行为<br>Behavior

- 请求：`POST <url>/message?token=<TOKEN>`，JSON 载荷为 `{title, message, priority, extras}`
- Request: `POST <url>/message?token=<TOKEN>` with JSON body `{title, message, priority, extras}`
- mTLS：同时配置 `client_cert` + `client_key` 时以 `cert=(client_cert, client_key)` 建立双向 TLS 会话
- mTLS: when both `client_cert` and `client_key` are set, the session is established with `cert=(client_cert, client_key)`
- 错误：令牌无效（401/403）提示「Invalid Gotify access token」；其他 HTTP 错误透出服务端返回的错误信息；网络异常透出异常文本
- Errors: invalid token (401/403) reports "Invalid Gotify access token"; other HTTP errors surface the server's error message; network errors surface the exception text

---

## ntfysh_mtls

ntfy.sh 通知插件，在官方 `ntfysh` 插件的基础上增加**双向 TLS（mTLS）**支持，同时保留官方插件的全部能力（Basic Auth、延时、标签等）。 <br>
ntfy.sh notifier built on the upstream `ntfysh` plugin, adding **mutual TLS (mTLS)** support while keeping all upstream capabilities (Basic Auth, delay, tags, etc.).

### 配置<br>Configuration

```yaml
notify:
  entries:
    via:
      - ntfysh_mtls:
          url: https://ntfy.example.com/    # 可选，默认 https://ntfy.sh/
          topic: <NTFY_TOPIC>               # 必填
          priority: 3                       # 可选，默认 3
          delay: 30s                        # 可选，延时发布
          tags: tag1,tag2                   # 可选，标签（逗号分隔）
          username: <USER>                  # 可选，Basic Auth 用户名
          password: <PASS>                  # 可选，Basic Auth 密码
          client_cert: /certs/client.pem    # 可选，mTLS 客户端证书（须与 client_key 成对）
          client_key: /certs/client-key.pem # 可选，mTLS 客户端私钥（须与 client_cert 成对）
          ca_cert: /certs/ca.pem            # 可选，CA 证书，设置后取代 verify
          verify: true                      # 可选，默认 true
```

### 参数说明<br>Parameters

| 参数<br>Param | 必填<br>Required | 默认<br>Default | 说明<br>Description |
|---|---|---|---|
| `url` | — | `https://ntfy.sh/` | ntfy 服务地址，请求发送至 `<url>/<topic>`<br>Server URL, requests go to `<url>/<topic>` |
| `topic` | ✅ | — | 订阅主题，拼接在 URL 路径上<br>Topic, appended to the URL path |
| `priority` | — | `3` | 通知优先级（1–5）<br>Notification priority (1–5) |
| `delay` | — | — | 延时发布时间，如 `30s`、`1h`<br>Delayed publish time, e.g. `30s`, `1h` |
| `tags` | — | — | 通知标签，逗号分隔字符串<br>Notification tags, comma-separated string |
| `username` / `password` | — | — | Basic Auth 凭据（ntfy 的访问令牌认证），与 mTLS 相互独立、可同时使用<br>Basic Auth credentials (ntfy access-token auth), independent of mTLS, can be combined |
| `client_cert` / `client_key` | — | — | mTLS 客户端证书/私钥，必须成对出现<br>mTLS client cert/key, must be paired |
| `ca_cert` | — | — | 自定义 CA 证书，设置后取代 `verify`<br>Custom CA cert, replaces `verify` when set |
| `verify` | — | `true` | 是否校验服务端证书<br>Verify the server cert |

### 行为<br>Behavior

- 请求：`POST <url>/<topic>`，消息文本作为请求体，`title`、`priority`、`delay`、`tags` 作为查询参数
- Request: `POST <url>/<topic>` with the message text as body and `title`, `priority`, `delay`, `tags` as query params
- 认证：配置 `username` / `password` 时使用 HTTP Basic Auth；mTLS 凭据独立生效，两者可叠加
- Auth: HTTP Basic Auth when `username`/`password` are set; mTLS credentials apply independently, both can be combined
- 错误：凭据无效（401/403）提示「Invalid username and password」；其他 HTTP 错误透出服务端响应文本
- Errors: invalid credentials (401/403) report "Invalid username and password"; other HTTP errors surface the server response text

---

## regexp_nest

内置 `regexp` 过滤插件的超集：支持相同的操作（`accept`、`reject`、`accept_excluding`、`reject_excluding`）、选项（`path`、`set`、`not`、`from`）与 `rest` 处理，并新增递归的 **`within`** 子模式：外层模式匹配后设定基础 `path`，内层 `within` 子模式继续匹配则把 `path` 细化到**最深匹配**的那一层。适合「一个大类 + 多个子类」的目录路由场景。 <br>
A superset of the built-in `regexp` filter plugin: same operations (`accept`, `reject`, `accept_excluding`, `reject_excluding`), options (`path`, `set`, `not`, `from`) and `rest` handling, plus a new recursive **`within`** sub-pattern: after the outer pattern matches and sets a base `path`, matching inner `within` sub-patterns refine `path` down to the **deepest** matched level. Ideal for "one category + many sub-categories" directory routing.

### 配置<br>Configuration

```yaml
regexp_nest:
  accept:
    - (?:.*Movies)(?:.*(?:1080p|720p)):
        path: /downloads/movies
        not: (?:.*(CHS|CHT))
        within:
          - (?:.*Action):
              path: /downloads/movies/Action
          - (?:.*SciFi):
              path: /downloads/movies/SciFi
```

### 参数说明<br>Parameters

与内置 `regexp` 一致的顶层配置： <br>
Top-level config, same as built-in `regexp`:

| 参数<br>Param | 说明<br>Description |
|---|---|
| `accept` / `reject` | 匹配时接受 / 拒绝条目<br>Accept / reject entries on match |
| `accept_excluding` / `reject_excluding` | 不匹配时接受 / 拒绝条目<br>Accept / reject entries on non-match |
| `rest` | 其余（未匹配任何正则的）条目统一执行 `accept` 或 `reject`<br>Entries matching no pattern get `accept` or `reject` |
| `from` | 对所有正则生效的搜索字段<br>Search fields applied to all regexes |

每个正则条目可携带的选项： <br>
Options per regex entry:

| 选项<br>Option | 说明<br>Description |
|---|---|
| `path` | 条目匹配时写入的 `path` 字段<br>`path` field written on match |
| `set` | 条目匹配时通过 `set` 插件写入的字段集合<br>Fields written via the `set` plugin on match |
| `not` | 反匹配正则（字符串或列表），命中则该条目不匹配<br>Negative regex (string or list); hitting it makes the entry not match |
| `from` | 指定该条目仅从这些字段搜索<br>Restrict this entry to search only these fields |
| `within` | **regexp_nest 新增**：递归的子模式列表，结构与顶层一致；子模式匹配时其 `path` 覆盖父级 `path`<br>**regexp_nest addition**: recursive sub-pattern list, same structure as top level; a matching sub-pattern's `path` overrides the parent's |

### 行为<br>Behavior

- 路由：条目匹配外层模式后，`within` 中子模式逐个递归匹配，`path` 取**最深**命中项的值
- Routing: after the entry matches the outer pattern, `within` sub-patterns are matched recursively; `path` takes the value of the **deepest** match
- 匹配的条目执行对应的操作（如 `Entry.accept`），`set` 会沿着命中的分支链逐层应用
- Matched entries execute the configured action (e.g. `Entry.accept`); `set` applies along the matched branch chain
- 未匹配任何模式的条目进入 `rest` 处理（若配置了 `rest`）
- Entries matching nothing fall to `rest` handling (if `rest` is configured)
- 同一任务只需配置一个操作（`accept` 系列或 `reject` 系列，勿混用）
- Configure only one action family per task (`accept`-series or `reject`-series, don't mix)

### 与内置 regexp 的差异<br>Differences vs. built-in regexp

| 能力<br>Capability | 内置 `regexp`<br>built-in | `regexp_nest` |
|---|---|---|
| 顶层操作 / 选项<br>Top-level ops / options | ✅ | ✅ |
| `rest` 处理<br>`rest` handling | ✅ | ✅ |
| 嵌套 `within` 子模式<br>Nested `within` sub-patterns | ❌ | ✅ |
| 最深 `path` 路由<br>Deepest-`path` routing | ❌ | ✅ |

---

## 许可<br>License

个人使用 / 自部署场景定制，按需自取。 <br>
Customized for personal / self-hosted use. Use as you see fit.