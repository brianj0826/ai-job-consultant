# 配置参考

应用通过环境变量配置。Docker Compose 从项目根目录 `.env` 读取并显式传入后端；直接运行 FastAPI 时由调用者负责设置同名变量。不要提交 `.env`。

## AI 与 RAG

| 变量 | 示例/默认 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 无 | DeepSeek 密钥；正常运行必填 |
| `DEEPSEEK_API_URL` | `https://api.deepseek.com/chat/completions` | OpenAI 兼容聊天端点；测试可指向 mock |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 普通回答、工具调用与职业建议提取使用的模型 |
| `CAREER_SUGGESTIONS_ENABLED` | `true` | 是否从已审核 AI 回复中生成新的职业数据建议；关闭后已有建议仍可处理 |
| `CAREER_SUGGESTION_TIMEOUT_SECONDS` | `8` | 独立建议提取调用的超时秒数；失败时降级为空建议，不中断聊天 |
| `RAG_DISABLED` | `false` | 仅受控测试/CI 使用；生产保持 `false` |
| `CHROMA_DB_PATH` | 直接运行 `./chroma_db`；Compose 固定为容器内 `/app/chroma_db` | Chroma 持久目录；Compose 固定值与 bind mount 对齐，直接运行时可覆盖 |
| `RAG_CHUNK_SIZE` | `500` | 文本分块字符数 |
| `RAG_CHUNK_OVERLAP` | `100` | 相邻分块重叠字符数；必须小于分块大小 |
| `UPLOAD_MAX_BYTES` | `10485760` | 单个上传最大 10 MiB；允许配置 1 KiB–100 MiB |
| `RAG_MAX_PDF_PAGES` | `100` | PDF 最大页数；允许 1–5000 |
| `RAG_MAX_TEXT_CHARS` | `200000` | 单文档提取文本上限；允许 1000–5000000 |
| `RAG_MAX_CHUNKS` | `500` | 单次索引最终分块上限；允许 1–10000 |

反向代理的请求体限制必须不小于 `UPLOAD_MAX_BYTES`，否则请求会先由 Nginx 拒绝。调大上限会同时增加解析时间、内存、嵌入成本和磁盘占用，应结合用户配额评估。

## URL 抓取

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CRAWLER_MAX_RESPONSE_BYTES` | `2097152` | 页面响应体上限 2 MiB；允许 1 KiB–25 MiB |
| `CRAWLER_MAX_REDIRECTS` | `5` | 最大重定向次数；允许 0–10，每个目标都重新校验 |
| `CRAWLER_MAX_TEXT_CHARS` | `20000` | 返回/索引的页面文本上限；允许 1000–1000000 |
| `FETCH_URL_RATE_LIMIT_PER_MINUTE` | `10` | 每用户 URL 抓取/导入共用的每分钟次数；允许 1–120 |

这些值限制资源消耗，不替代网络出口 ACL。生产环境仍应在基础设施层阻断私网、link-local 和云 metadata 网段的非预期出口。

## 应用、密码与限流

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `development` | `development` / `test` 为本地模式；其他值按非本地安全要求校验 |
| `LOG_LEVEL` | `INFO` | Python 日志级别，如 `DEBUG`、`INFO`、`WARNING`、`ERROR`；同时影响 stdout 与 `logs/app.log` |
| `RATE_LIMIT_PER_MINUTE` | `30` | 每用户聊天等通用业务请求限制，最小按 1 处理 |
| `LOGIN_FAILURE_LIMIT` | `5` | IP+用户名窗口内登录尝试上限；约束 1–50 |
| `LOGIN_FAILURE_WINDOW_SECONDS` | `900` | 登录窗口；约束 60–86400 秒 |
| `PASSWORD_PBKDF2_ITERATIONS` | `310000` | 新密码哈希轮数；运行时夹在 100000–2000000 |
| `CHAT_REQUEST_LEASE_SECONDS` | `300` | 聊天幂等处理租约；运行时夹在 30–3600 秒 |

修改 PBKDF2 轮数只影响新哈希；用户成功登录时可按当前参数重新哈希旧格式。调高前先做容量测试。

## Cookie、会话与来源

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `SESSION_TTL_HOURS` | `168` | 登录会话 1–720 小时 |
| `SESSION_COOKIE_SECURE` | 本地 `false`，其他环境 `true` | 生产必须为 `true` |
| `SESSION_COOKIE_SAMESITE` | `lax` | `lax` / `strict` / `none`；`none` 要求 Secure |
| `SESSION_COOKIE_DOMAIN` | 空 | 可选裸域名；不要包含协议、端口、路径或通配符 |
| `AUTH_SESSION_RETENTION_DAYS` | `30` | 过期/撤销会话记录保留 1–3650 天 |
| `AUTH_SESSION_CLEANUP_INTERVAL_SECONDS` | `3600` | 清理周期 60–86400 秒 |
| `CORS_ALLOWED_ORIGINS` | 本地地址列表 | 逗号分隔的精确 `http(s)` origin；Cookie 模式拒绝 `*` |
| `TRUST_PROXY_HEADERS` | Compose 中 `true` | 是否采信受信代理传入的客户端 IP 头 |
| `TRUSTED_PROXY_CIDRS` | Compose 前端容器 `/32` | 只有直接对端在这些 CIDR 中才采信转发头 |
| `BUSINESS_TIMEZONE` | `Asia/Shanghai` | 管理员“今日”指标的 IANA 时区 |

直连本地后端时通常应设置 `TRUST_PROXY_HEADERS=false`。生产代理地址与 Compose 默认不同，必须把 `TRUSTED_PROXY_CIDRS` 收窄到实际代理，不能使用任意来源网段。

## Redis 与管理员引导

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `REDIS_URL` | Compose: `redis://redis:6379/0` | 共享限流后端 |
| `RATE_LIMIT_ALLOW_MEMORY_FALLBACK` | `.env.example`: `true`；Compose 默认 `false` | 只允许 local/test 在 Redis 不可用时降级；生产拒绝内存模式 |
| `RATE_LIMIT_KEY_PREFIX` | `ai-job-consultant` | Redis key 前缀，非空且不能含空白 |
| `ADMIN_BOOTSTRAP_USERNAME` | 空 | 首次超级管理员用户名；与密码同时设置 |
| `ADMIN_BOOTSTRAP_PASSWORD` | 空 | 一次性引导密码；成功后从环境移除 |

多实例部署必须使用共享 Redis；进程内 fallback 无法提供跨实例一致限流。

## MySQL 与 Compose

| 变量 | 示例/默认 | 说明 |
| --- | --- | --- |
| `MYSQL_ROOT_PASSWORD` | 无安全默认 | MySQL 容器管理密码；后端不使用 |
| `DB_HOST` | 本地 `127.0.0.1`；Compose `mysql` | 数据库主机 |
| `DB_PORT` | `3306` | 数据库端口 |
| `DB_USER` | `aiagent` | 独立应用账号；非本地环境禁止 `root` |
| `DB_PASSWORD` | 无安全默认 | 应用账号密码；非本地环境不能为空 |
| `DB_NAME` | `ai_assistant` | 应用数据库 |
| `BACKEND_PORT` | `8000` | Compose 后端本机绑定端口 |
| `ADMINER_PORT` | `8088` | 可选 Adminer 本机绑定端口 |

生产密钥应来自部署平台 secret store，而不是保存在镜像、Compose 文件、shell 历史或仓库。环境变量变更后需要重建或重启后端容器：

```bash
docker compose config --quiet
docker compose up -d --build --wait backend frontend
```

启动日志会显示部分非敏感运行模式，但不会证明外部模型可用。部署后同时检查 `/api/health/ready` 和一条经授权的实际业务流程。
