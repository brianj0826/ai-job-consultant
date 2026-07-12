# 职达 — AI 求职顾问

职达是一个面向求职场景的 Vue 3 + FastAPI 应用，提供简历知识库、岗位匹配、模拟面试、流式 AI 对话、个人分析面板和管理员控制台。

## 技术栈

- 前端：Vue 3、Element Plus、Axios、ECharts、Marked
- 后端：FastAPI、MySQL 8、ChromaDB、DeepSeek API
- 部署：Docker Compose、Nginx
- 测试：Vitest、Playwright

## 快速启动

### 1. 准备配置

```bash
cp .env.example .env
```

至少设置：

```dotenv
DEEPSEEK_API_KEY=sk-your-real-key
```

`DEEPSEEK_API_URL` 默认指向 DeepSeek 官方兼容接口。`RAG_DISABLED` 仅用于不加载嵌入模型的受控 CI smoke，正常开发和生产必须保持为 `false`。

如需在首次启动时创建超级管理员，同时设置以下两个值：

```dotenv
ADMIN_BOOTSTRAP_USERNAME=root-admin
ADMIN_BOOTSTRAP_PASSWORD=replace-with-a-strong-password
```

两个管理员引导变量必须一起设置。系统检测到已有超级管理员后不会再次提升其他账号。首次创建成功并验证可登录后，应从部署环境中移除明文引导密码。

### 2. 启动服务

```bash
docker compose up --build -d
docker compose ps
```

服务地址：

| 服务 | 地址 |
| --- | --- |
| 前端 | <http://localhost> |
| 后端 OpenAPI | <http://localhost:8000/docs> |
| 存活检查 | <http://localhost:8000/api/health/live> |
| 就绪检查 | <http://localhost:8000/api/health/ready> |
| Adminer（可选） | 执行 `docker compose --profile tools up -d adminer` 后访问 <http://localhost:8088> |

前端通过 Nginx 的同源 `/api/` 代理访问后端。浏览器不应绕过该代理直接访问容器地址。

### 3. 本地前端开发

```bash
cd frontend
npm ci
npm run dev
```

Vite 将 `/api` 代理到 `http://127.0.0.1:8000`。

## 认证与 CSRF 契约

系统不向浏览器返回 Bearer Token，而是使用服务端会话和双提交 CSRF：

- `session_token`：HttpOnly Cookie，JavaScript 不可读取。
- `csrf_token`：可读 Cookie。
- 所有改变状态的已登录请求必须同时发送 `X-CSRF-Token`，值与 `csrf_token` Cookie 完全一致。
- 登录、注册会设置两个 Cookie；退出会撤销服务端会话并清除 Cookie。
- 前端启动时通过 `GET /api/auth/me` 恢复身份，不以 localStorage 中的用户 ID 作为授权依据。

登录和注册响应统一为：

```json
{
  "user": {
    "id": 7,
    "username": "career-user",
    "role": "user",
    "status": "active",
    "must_change_password": false,
    "last_login_at": "2026-07-10T08:00:00Z",
    "created_at": "2026-07-01T08:00:00Z"
  }
}
```

密码长度为 8–128 个字符，用户名长度为 2–64 个字符。常见状态码：

| 状态码 | 含义 |
| --- | --- |
| `400` | 密码策略、当前密码或业务参数错误 |
| `401` | 未登录、会话过期或凭据错误 |
| `403` | CSRF 错误或权限不足 |
| `404` | 资源不存在，或资源不属于当前用户 |
| `409` | 用户名已存在 |
| `422` | 请求结构不符合接口模型 |
| `429` | 登录或业务请求频率受限；客户端应遵守 `Retry-After` |

## 主要 API

### 身份接口

| 方法 | 路径 | 请求体 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | `{username,password}` | 注册并建立会话 |
| POST | `/api/auth/login` | `{username,password}` | 登录并建立会话 |
| GET | `/api/auth/me` | — | 获取当前用户 |
| POST | `/api/auth/logout` | — | 需要 CSRF；撤销当前会话 |
| POST | `/api/auth/change-password` | `{current_password,new_password}` | 需要 CSRF；撤销旧会话并签发新 Cookie |

管理员重置密码后，目标用户的 `must_change_password` 会变为 `true`。该用户下次登录只能进入修改密码页，完成修改后才能使用工作台。

### 用户业务接口

所有接口均需要有效会话；表中标记“写”的接口还需要 CSRF。

| 方法 | 路径 | 类型 | 说明 |
| --- | --- | --- | --- |
| GET / POST | `/api/sessions/` | 读 / 写 | 当前用户会话列表、创建会话 |
| GET | `/api/sessions/{id}/messages` | 读 | 当前用户的会话消息 |
| PUT | `/api/sessions/{id}/rename` | 写 | 重命名会话 |
| DELETE | `/api/sessions/{id}` | 写 | 删除会话及其消息 |
| POST | `/api/chat/` | 写 | 非流式回复 |
| POST | `/api/chat/stream` | 写 | SSE 流式回复 |
| POST | `/api/documents/upload` | 写 | multipart 文档上传 |
| GET | `/api/documents/status` | 读 | 当前用户知识库状态 |
| POST | `/api/documents/import-url` | 写 | 抓取并写入知识库 |
| POST | `/api/documents/fetch-url` | 读操作 | 只抓取文本，不写知识库 |
| DELETE | `/api/documents/source` | 写 | 删除当前用户的来源 |
| POST | `/api/feedback/` | 写 | 评价当前用户的 AI 回复 |
| GET | `/api/analytics/overview` | 读 | 当前用户概览 |
| GET | `/api/analytics/feedback` | 读 | 当前用户反馈统计 |
| GET | `/api/analytics/trend` | 读 | 当前用户消息趋势 |

这些接口从 Cookie 会话确定身份。客户端不应再发送或信任 `user_id` 查询参数、JSON 字段或 multipart 字段。

聊天客户端应为每次发送生成稳定的 `client_request_id`，重试时复用同一个值。后端通过持久化 `chat_requests` 租约记录防止重复消息：已完成请求直接回放，仍在处理返回 `409`，同 ID 不同内容返回 `409`，进程异常遗留的请求在租约过期后可由新 owner 安全接管。`CHAT_REQUEST_LEASE_SECONDS` 默认 300 秒。

## 管理员控制台

角色分为：

- `user`：普通用户。
- `admin`：可查看管理概览、用户、反馈和审计日志；可停用普通用户。
- `super_admin`：包含管理员能力，并可分配角色和重置密码。

同一 Vue SPA 提供 `/admin/overview`、`/admin/users`、`/admin/feedback` 和 `/admin/audit-logs`。旧的 `/admin`、`/admin/audit` 地址会重定向到规范路径。

管理 API：

| 方法 | 路径 | 权限 |
| --- | --- | --- |
| GET | `/api/admin/overview` | admin 或 super_admin |
| GET | `/api/admin/users` | admin 或 super_admin |
| PATCH | `/api/admin/users/{id}/status` | admin；修改特权账号需 super_admin；需要 CSRF |
| PATCH | `/api/admin/users/{id}/role` | super_admin；需要 CSRF |
| POST | `/api/admin/users/{id}/reset-password` | super_admin；需要 CSRF |
| GET | `/api/admin/feedback` | admin 或 super_admin |
| GET | `/api/admin/audit-logs` | admin 或 super_admin |

重置密码请求没有业务请求体；后端生成随机临时密码，并仅在本次响应的 `temporary_password` 字段中返回一次。后端禁止修改自己的状态或角色，并保护最后一个启用的超级管理员。停用账号、重置密码会撤销目标用户的现有会话。管理员写操作会进入审计日志。

## MCP 范围

`/api/mcp/` 不是公开匿名端点：

- `GET /api/mcp/` 需要登录。
- `POST /api/mcp/` 需要登录和 `X-CSRF-Token`。
- `tools/call`、知识库资源列表和读取均使用当前 Cookie 会话对应的用户 ID，不能通过请求参数切换用户。
- 浏览器外部客户端若要使用 MCP，必须实现 Cookie 会话和 CSRF 流程；当前版本不提供独立 API Key 或 Bearer Token 模式。

支持的 JSON-RPC 方法包括 `initialize`、`tools/list`、`tools/call`、`resources/list` 和 `resources/read`。

## 从旧版本迁移

部署前请备份 MySQL 和 ChromaDB 数据。应用启动时会补齐认证会话、角色、账号状态、审计、强制改密和聊天幂等租约所需的表与字段。

若复用旧的 `mysql_data` 卷，MySQL 镜像不会在已有数据目录中自动创建新的 `DB_USER`。切换到独立应用账号前，请先使用数据库管理员执行等价授权（替换示例密码和库名）：

```sql
CREATE USER IF NOT EXISTS 'aiagent'@'%' IDENTIFIED BY '<long-random-application-password>';
GRANT ALL PRIVILEGES ON ai_assistant.* TO 'aiagent'@'%';
FLUSH PRIVILEGES;
```

随后让 `DB_USER`、`DB_PASSWORD` 与该账号一致。生产启动会拒绝空数据库密码以及 `DB_USER=root`。

旧客户端需要完成以下迁移：

1. 从 `/api/users/login|register` 切换到 `/api/auth/login|register`。旧路径仅作为临时兼容别名。
2. 从 `response.user_id` 切换到 `response.user.id`。
3. 删除所有客户端提供的 `user_id`；资源归属由后端会话决定。
4. 为所有写请求发送 CSRF 头，并在启动时调用 `/api/auth/me`。
5. 退出时调用 `/api/auth/logout`，不能只清理浏览器本地状态。
6. 旧账号若没有可验证密码，应由超级管理员重置密码，用户随后完成强制改密。

建议先在预发布环境完成登录、刷新恢复、跨用户资源隔离、改密、管理员重置和退出验收，再切换生产流量。

## 生产安全配置

生产环境必须终止 TLS，并设置：

```dotenv
APP_ENV=production
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=lax
CORS_ALLOWED_ORIGINS=https://your-domain.example
TRUST_PROXY_HEADERS=true
TRUSTED_PROXY_CIDRS=<only-your-reverse-proxy-cidrs>
REDIS_URL=redis://your-redis:6379/0
MYSQL_ROOT_PASSWORD=<long-random-root-password>
DB_USER=aiagent
DB_PASSWORD=<long-random-application-password>
```

若使用 `SESSION_COOKIE_SAMESITE=none`，`SESSION_COOKIE_SECURE` 必须为 `true`。`CORS_ALLOWED_ORIGINS` 必须列出精确来源，不允许在 Cookie 鉴权下使用通配符。只有请求确实来自受信任代理网段时，后端才应采信 `X-Forwarded-For`。Compose 仅把后端和 Adminer 绑定到本机回环地址；生产环境应继续只公开 Nginx，并把 `TRUSTED_PROXY_CIDRS` 收窄到实际代理地址。若 TLS 在外层代理终止，还需在 Nginx 中为该代理配置 `real_ip` 信任和协议透传，不能信任任意客户端传入的转发头。

Compose 使用独立 MySQL 应用账号，不再让后端使用 root。不要把 `.env`、数据库密码或管理员 bootstrap 密码提交到版本库；验证首个 super-admin 后应移除 bootstrap 明文。

## 测试

```bash
cd frontend
npx playwright install chromium
npm run lint
npm run test:run
npm run build
npm run test:e2e
```

Linux/CI 首次安装浏览器时使用 `npx playwright install --with-deps chromium`，同时安装系统依赖。

Playwright 在 `127.0.0.1:4174` 启动 Vite，并在 `127.0.0.1:8001` 启动仅用于浏览器测试的契约 Mock。可通过 `E2E_FRONTEND_PORT` 和 `E2E_API_PORT` 覆盖端口。Mock 模拟真实的 `{user}` 响应、HttpOnly Session Cookie、CSRF、资源归属和管理员权限，适合快速回归。

CI 还会通过 `docker-compose.yml` 与 `docker-compose.ci.yml` 启动真实 MySQL、Redis、FastAPI 和 Nginx/Vue 镜像，并运行：

```bash
cd frontend
DOCKER_E2E_BASE_URL=http://127.0.0.1 npm run test:e2e:docker
```

该 smoke 使用容器内的确定性 DeepSeek 兼容 Mock，不访问真实模型服务；浏览器仍通过 Nginx 同源 `/api` 完成注册、Session/CSRF、会话创建、SSE 聊天、退出与管理员登录。预发布环境仍需使用真实部署密钥完成最终 AI/RAG 验收。

一次执行完整前端门禁：

```bash
npm run test:all
```

## 项目结构

```text
backend/                 FastAPI 路由、服务与数据访问
frontend/src/            Vue 应用
frontend/e2e/            Playwright 用例与契约 Mock
frontend/nginx.conf      生产同源代理与 SSE 配置
.github/workflows/       CI 门禁
docker-compose.yml       本地和容器部署
docker-compose.ci.yml    完整 Docker smoke 的 AI Mock 覆盖配置
```
