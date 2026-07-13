# API 说明

## 通用约定

- 默认前缀：`/api`。浏览器应通过前端同源代理访问，并在请求中启用 Cookie。
- 时间戳使用 UTC ISO 8601；日期字段使用 `YYYY-MM-DD`。
- 读取接口需要有效会话；除登录、注册和健康检查外，改变状态的接口都需要 `X-CSRF-Token`。
- 当前用户由 `session_token` 确定。业务请求不接受 `user_id` 作为授权依据。
- FastAPI 常规错误形态为 `{"detail":"message"}`；Pydantic 结构错误返回 `422` 和字段错误数组。
- 跨用户资源与不存在的资源都返回 `404`，客户端不能据此探测其他账号数据。

浏览器写请求示例：

```http
PATCH /api/career/jobs/12 HTTP/1.1
Content-Type: application/json
Cookie: session_token=...; csrf_token=...
X-CSRF-Token: <csrf_token-cookie-value>

{"status":"active"}
```

常用状态码：

| 状态 | 含义 |
| --- | --- |
| `200` / `201` | 成功 / 已创建 |
| `400` | 业务参数、确认文本、状态转换或报告 payload 大小无效 |
| `401` | 未登录、会话过期或凭据错误 |
| `403` | CSRF 错误、权限不足或必须先改密 |
| `404` | 资源不存在或不属于当前用户 |
| `409` | 唯一性/引用冲突、幂等请求正在处理，或当前用户的数据锁繁忙 |
| `413` | 上传文件的字节、PDF 页数、提取文本或分块超过服务端限制；URL 抓取策略/大小错误当前返回 `400` |
| `422` | JSON、查询参数或字段类型不符合模型 |
| `429` | 频率限制；读取 `Retry-After` |
| `503` | 服务或 RAG 功能尚未就绪 |

## 认证

| 方法 | 路径 | 请求 | 响应/说明 |
| --- | --- | --- | --- |
| POST | `/auth/register` | `{username,password}` | `201 {user}` 并设置两个 Cookie |
| POST | `/auth/login` | `{username,password}` | `{user}` 并设置两个 Cookie |
| GET | `/auth/me` | — | `{user}`；`Cache-Control: no-store` |
| POST | `/auth/logout` | — | `{ok:true}`；需要 CSRF |
| POST | `/auth/change-password` | `{current_password,new_password}` | `{user}`，撤销旧会话并签发新 Cookie |

`session_token` 是 HttpOnly 凭据；`csrf_token` 可由前端读取并原样放入 `X-CSRF-Token`。两者原值不存入数据库，服务端保存摘要。`/api/users/login` 与 `/api/users/register` 仅为弃用兼容别名，新客户端不得使用。

用户对象包含 `id`、`username`、`role`、`status`、`must_change_password`、`last_login_at` 与 `created_at`，不包含密码或会话密钥。

## 职业中心

### 通用资源操作

资源名为 `resumes`、`jobs`、`applications`、`interviews`、`reports`、`skills`。

| 方法 | 路径 | 响应 |
| --- | --- | --- |
| GET | `/career/{resource}?limit=100` | `{items:[...],total:number}`；limit 为 1–500 |
| POST | `/career/{resource}` | 创建后的实体 |
| GET | `/career/{resource}/{id}` | 单个实体 |
| PATCH | `/career/{resource}/{id}` | 更新后的实体；只发送要修改的字段 |
| DELETE | `/career/{resource}/{id}` | `{ok:true}` |

创建字段：

| 资源 | 必填 | 可选与约束 |
| --- | --- | --- |
| resume | `title`, `content` | `target_role`, `source_name`, `is_primary` |
| job | `title`, `description` | `company`, `source_url`, `status`: `saved` / `active` / `archived` |
| application | `job_id` | `stage`: `saved` / `applied` / `screening` / `interview` / `offer` / `rejected` / `withdrawn`；`next_action`, `deadline`, `notes` |
| interview | `title` | `job_id`, `status`: `planned` / `in_progress` / `completed` / `cancelled`；`overall_score` |
| report | `kind`, `title`, `summary` | `kind`: `resume_analysis` / `job_match` / `interview_review` / `career_plan`；`entity_type`, `entity_id`, `payload`；payload 的紧凑 JSON UTF-8 编码最多 262144 字节 |
| skill | `skill` | `target_level`, `status`: `planned` / `in_progress` / `completed` / `paused`；`progress` 0–100, `due_date`, `notes` |

报告的 `entity_type` 可为 `resume`、`job`、`application`、`interview` 或 `skill`。`entity_type` 与 `entity_id` 必须同时为空或同时提供；目标必须属于当前用户。PATCH 是部分更新；必填表示创建时必须提供，不表示每次 PATCH 都要重复发送。删除被关联实体后报告作为历史快照保留，关联字段不会级联清空。payload 超过 256 KiB 返回 `400`。

`GET /career/reports` 还可用 `kind` 精确过滤。一个账号最多有一个同名技能、一个岗位最多有一条投递、一个面试内题目 position 不可重复；冲突返回 `409`。把简历设为主要简历会自动取消同账号其他主要标记，数据库唯一约束提供并发兜底。投递和面试的 `(user_id, job_id)` 使用复合外键。通过 API 删除岗位时，对应投递会被删除，历史面试会保留并将 `job_id` 置空；删除面试会级联删除其问题。

所有 career 写接口和 `/career/export` 都获取当前用户的 MySQL advisory lock；文档上传、URL 导入和知识库来源删除使用同一把用户锁。这样可避免协作请求在职业清空期间重新写入数据。获取锁超时返回 `409`，客户端应在当前请求结束后再重试；该锁不代表 MySQL 与 Chroma 构成同一事务。

### 面试题

| 方法 | 路径 | 请求/响应 |
| --- | --- | --- |
| POST | `/career/interviews/{id}/questions` | 必填 `question`；可选 `position`, `answer`, `score` 0–100, `feedback`；返回题目 |
| PATCH | `/career/interviews/{id}/questions/{question_id}` | 部分更新；返回题目 |
| DELETE | `/career/interviews/{id}/questions/{question_id}` | `{ok:true}` |

面试详情包含其问题。题目 ID 仍需与路径中的面试 ID 和当前用户同时匹配。

### 导出与清空

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/career/export` | 返回当前用户全部六类职业数据；面试包含题目；响应在内存中一次性组装，不是流式导出 |
| DELETE | `/career/data` | 请求体必须为 `{confirmation:"DELETE"}`；删除职业数据与当前用户 Chroma 集合，返回 `{ok:true,deleted:{...},vector_collection_deleted:boolean}` |

清空不删除账号、认证会话、聊天消息、反馈或审计数据。这不是账号删除 API。清空跨 MySQL/Chroma 不具备分布式原子性；失败时可用相同确认安全重试，部署方应验证两侧状态。

## 会话与聊天

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET / POST | `/sessions/` | 列表 / 创建 `{name}` |
| GET | `/sessions/{id}/messages?limit=50` | 读取 1–100 条消息 |
| PUT | `/sessions/{id}/rename` | `{name}`，最多 255 字符 |
| DELETE | `/sessions/{id}` | 删除会话及消息 |
| POST | `/chat/` | 非流式聊天 |
| POST | `/chat/stream` | SSE 流式聊天 |

聊天请求：

```json
{
  "message": "请结合我的简历分析这个岗位",
  "session_id": 42,
  "client_request_id": "01J..."
}
```

`client_request_id` 可省略，但客户端应为一次逻辑发送生成 1–128 字符的稳定 ID，并在网络重试时复用。相同 ID 与不同内容返回 `409`；处理中返回 `409` 和 `Retry-After: 2`；完成后重试会回放结果。

非流式响应包含 `response`、`msg_id`、`sources` 与 `suggestions`。会话历史中的 assistant 消息也包含同一建议数组。SSE 使用无命名的 `data:` 事件，每个 data 是 JSON：

```text
data: {"token":"逐步输出的文本"}

data: {"done":true,"msg_id":123,"sources":[{"id":1,"source":"resume.pdf","title":"resume.pdf"}],"suggestions":[]}
```

失败可能在 HTTP 200 后出现：

```text
data: {"error":"错误说明"}
```

客户端必须缓冲 token，在 `done` 后保存最终状态，在 `error` 或断流时提供可重试状态。服务端为了统一输出审核，会先收完整模型回复再发送已批准 token，所以不要把较长的首 token 等待误判为断流。代理仍需关闭 SSE buffering 并配置足够读取超时。

### AI 职业建议

建议对象包含 `id`、`action=create`、`resource_type`、`title`、`reason`、`payload`、`relation_hints`、`status`、`revision`、`source_message_id`、时间与可选 `created_resource`。支持 `resumes`、`jobs`、`applications`、`interviews`、`reports`、`skills` 和 `interview_questions`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| PATCH | `/career/suggestions/{id}` | `{revision,payload}`；保存待确认草稿并增加 revision |
| POST | `/career/suggestions/{id}/accept` | `{revision}`；复验并原子创建目标记录 |
| POST | `/career/suggestions/{id}/dismiss` | `{revision}`；忽略建议 |
| POST | `/career/suggestions/{id}/restore` | `{revision}`；恢复已忽略建议 |

所有写请求需要 Cookie、CSRF 与当前用户职业数据锁。客户端不能更改建议的 `user_id`、`resource_type` 或 `action`。其他用户的建议表现为 `404`；旧 revision、非法状态、关系失效或唯一性冲突返回 `409`。重复接受返回第一次创建的结果，不会重复创建。

面试题建议批次最多十题，使用 `reference_answer` 和 `coaching_notes` 保存 AI 示例；真实 `answer`、`feedback` 和 `score` 保持为空。详细行为见 [AI 职业数据建议](ai-suggestions.md)。

## 文档与 RAG

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/documents/upload` | multipart `file`；支持 `.pdf`、`.docx`、`.txt`、`.md` |
| GET | `/documents/status` | `{doc_count,sources}`；禁用时额外返回 `disabled:true` |
| POST | `/documents/import-url` | `{url}`；抓取并索引 |
| POST | `/documents/fetch-url` | `{url}`；只返回 `{title,text}`，不保存 |
| DELETE | `/documents/source` | `{source}`；删除当前用户来源 |

上述三个写/代理操作都需要 CSRF。URL 仅允许公开 HTTP/HTTPS 目标，DNS 结果和每次重定向都应通过地址检查；响应体与提取文本受配置限制，`import-url` 和 `fetch-url` 共用每用户频率限制。上传在写入向量前检查文件大小、PDF 页数、提取字符数和最终分块数。

## 反馈、统计与管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/feedback/` | `{msg_id,feedback}`，feedback 为 `like` 或 `dislike` |
| GET | `/analytics/overview` | 当前用户概览 |
| GET | `/analytics/feedback` | 当前用户反馈统计 |
| GET | `/analytics/trend?days=7` | 1–30 天消息趋势 |
| GET | `/admin/overview` | admin / super_admin |
| GET | `/admin/users` | `page`, `page_size`, `search` |
| PATCH | `/admin/users/{id}/status` | `{status}`；需要管理权限与 CSRF |
| PATCH | `/admin/users/{id}/role` | `{role}`；仅 super_admin |
| POST | `/admin/users/{id}/reset-password` | 返回一次性 `temporary_password`；仅 super_admin |
| GET | `/admin/feedback` | 管理反馈分页 |
| GET | `/admin/audit-logs` | 管理审计分页 |

## MCP

`GET /mcp/` 返回服务信息；`POST /mcp/` 接收 JSON-RPC 2.0，并需要会话与 CSRF。支持 `initialize`、`tools/list`、`tools/call`、`resources/list` 与 `resources/read`。

MCP 没有独立 Bearer Token/API Key 模式。工具调用和 `kb://{user_id}/{source}` 资源都绑定当前 Cookie 会话；请求参数不能切换用户。

## 健康检查

- `GET /health/live`：进程存活，不检查外部依赖。
- `GET /health/ready`：检查 MySQL 和限流后端；失败返回 `503`。
- `GET /health`：向后兼容的 readiness 别名。

OpenAPI 由运行实例的 `/docs` 与 `/openapi.json` 提供；实现与本文冲突时，应先核对当前提交的 OpenAPI 和测试，再修正文档。
