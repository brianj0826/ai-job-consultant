# 部署、备份与恢复

## 部署前检查

生产环境至少需要：

- 支持 Docker Compose v2 的 Linux 主机或等价容器平台。
- TLS 终止、稳定域名和只允许预期来源的防火墙。
- DeepSeek 密钥、独立非 root MySQL 账号、强随机密码和共享 Redis。
- MySQL 与 ChromaDB 的持久卷、容量监控和异地备份位置。
- 明确的日志、隐私、密钥轮换、故障响应与恢复责任人。

复制 `.env.example` 后，按[配置参考](configuration.md)设置生产值。关键基线：

```dotenv
APP_ENV=production
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=lax
CORS_ALLOWED_ORIGINS=https://jobs.example.com
TRUST_PROXY_HEADERS=true
TRUSTED_PROXY_CIDRS=<only-the-real-proxy-cidrs>
RATE_LIMIT_ALLOW_MEMORY_FALLBACK=false
REDIS_URL=redis://redis:6379/0
DB_USER=aiagent
DB_PASSWORD=<long-random-application-password>
MYSQL_ROOT_PASSWORD=<different-long-random-root-password>
```

不要把 `ADMIN_BOOTSTRAP_PASSWORD` 长期留在环境中。首次超级管理员创建并验证后立即移除。

## 使用 Compose 发布

先渲染配置并确认不会出现空值、错误 origin 或错误端口：

```bash
docker compose config --quiet
docker compose build
docker compose up -d --wait
docker compose ps
```

默认 Compose 将后端绑定到 `127.0.0.1:8000`，Adminer 绑定到 `127.0.0.1:8088` 且不默认启动；MySQL 与 Redis不映射宿主机端口。生产只应公开 TLS 反向代理入口。若在 Compose 外增加代理，应同步调整网络、CORS、Cookie 和可信代理 CIDR。

Adminer 只用于短时本机维护：

```bash
docker compose --profile tools up -d adminer
docker compose stop adminer
```

## 健康检查与观测

```bash
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready
docker compose ps
docker compose logs --tail=200 backend frontend mysql redis
```

- liveness 失败时由编排器重启进程。
- readiness 失败时停止向实例导流并检查 MySQL/Redis；它不覆盖 DeepSeek、Chroma 的每一次读写或外部网页。
- 监控容器重启、HTTP 5xx/429、SSE 失败、磁盘、MySQL 连接、Chroma 目录与模型调用延迟/错误。
- 后端同时写 stdout 和工作目录下的 `logs/app.log`。Compose 没有为容器内 `/app/logs` 配置持久卷，因此生产观测应采集 stdout；若确需文件落盘，应挂载仓库外的受控目录并设置轮换。项目内 `logs/` 已被忽略。
- 日志不得记录 Cookie、CSRF、密码、API 密钥、完整简历或模型请求/回复正文；日志不纳入业务备份，应单独设置访问与保留策略。

## 备份

### 一致性原则

MySQL 是账号、聊天和职业实体的权威数据；`chroma_db/` 保存知识库向量和文本片段。应用用 MySQL 用户级 advisory lock 协调职业写入、导出、知识库写入与用户清空，但两者仍没有跨存储事务，因此必须在同一维护窗口形成一个有共同批次号/时间戳的备份集。

最安全的简单流程是短暂停止后端写入：

1. 通知维护并停止后端或从负载均衡摘除所有实例。
2. 导出 MySQL。
3. 复制/快照整个 ChromaDB 持久目录。
4. 记录应用提交 SHA、镜像摘要、`.env` 中非密钥配置、数据库备份和 Chroma 快照的校验和。
5. 恢复后端并执行 readiness 与冒烟测试。

示例（命令中的凭据由安全 secret 机制提供，不要写进 shell 历史）：

```bash
docker compose stop backend
docker compose exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_PASSWORD" mysqldump --single-transaction --no-tablespaces --routines --triggers -u"$MYSQL_USER" "$MYSQL_DATABASE"' \
  > /secure-backups/ai_assistant.sql
```

随后使用主机/存储平台的快照或归档工具复制 `chroma_db/`。不要在 Chroma 正在写入时直接逐文件复制。Redis 当前配置不持久化，只保存可重建的限流窗口，无需纳入业务备份。

`mysql_data` 是 Docker 命名卷，`chroma_db/` 是 bind mount；不要把删除容器等同于删除数据，也不要在未验证路径时执行 `down --volumes`。

## 恢复演练

恢复必须先在隔离环境演练：

1. 使用与备份提交兼容的应用镜像启动 MySQL。
2. 导入 SQL，恢复同批次的 Chroma 目录并校正所有权权限。
3. 启动 Redis、后端和前端。
4. 检查 `/health/ready`、登录、跨用户隔离、职业实体、知识库来源、RAG 检索、SSE、管理员审计。
5. 比较备份清单中的记录量和校验和，记录恢复点目标（RPO）与恢复耗时（RTO）的实际结果。

备份只有通过定期恢复演练后才可信。备份本身含用户内容和密钥相关数据，必须加密、限制访问并按部署方策略保留。

## 升级与回滚

当前后端对遗留基础表执行幂等建表/补列，对职业域执行版本迁移。两段流程在启动时共用同一个 MySQL schema advisory lock，防止多个实例交错修改；迁移账本保存规范化 SQL 的 SHA-256 checksum，已应用版本的名称或内容变化会使启动失败。因此每次升级：

1. 阅读提交与配置差异，确认 `.env.example` 新增项。
2. 创建 MySQL + Chroma 同批备份。
3. 在预发布环境用生产数据副本运行后端测试、前端测试和 Docker smoke。
4. 拉取确定的提交/镜像，执行 `docker compose config --quiet` 后滚动或维护窗口发布。
5. 验证认证/CSRF、职业数据、文档导入、聊天幂等/SSE 和管理操作。

如果升级已改变数据库结构，单独切回旧镜像未必安全。迁移只允许追加新版本，不应修改已发布 migration；checksum 不匹配不是可忽略告警，必须恢复与账本一致的代码或按审计后的迁移流程处理。回滚方案必须同时说明应用版本、数据库恢复点和 Chroma 快照；不得用 `git reset --hard` 或删除卷替代恢复流程。

`/api/career/export` 当前把一个用户的全部职业数据和面试题一次性装入后端内存，并在期间持有该用户的数据锁。生产应监控导出延迟、进程内存和相关 `409`；大数据量场景上线前需压测，未来应改为分页/流式导出或异步任务。

旧 MySQL 卷首次切换到独立 `DB_USER` 时，镜像不会在已有数据目录自动创建新账号。由数据库管理员先执行最小授权，再切换后端配置；后端在非本地环境会拒绝 `DB_USER=root`。

## 停机与数据清理

日常停止：

```bash
docker compose stop
```

删除容器但保留数据可使用 `docker compose down`。任何带 `--volumes` 的命令都会影响 MySQL 数据卷，只能在已验证备份、确认目标环境且获得明确授权后执行。用户级职业数据清理由受认证的 `/api/career/data` 完成，不应通过手工删除共享 Chroma 文件模拟。清空失败可安全重试，但由于 MySQL 与 Chroma 并非原子事务，部署方必须检查职业表计数和用户向量集合两侧结果。
