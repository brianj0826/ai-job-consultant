# 职达 — AI 求职顾问

职达是一个面向求职者的 AI 工作台。项目将简历知识库、岗位信息、投递进度、模拟面试、分析报告和技能计划放在同一账号空间内，并提供带来源的 RAG 对话、流式回复、个人统计与管理员控制台。

## 能力概览

- 上传 PDF、DOCX、TXT 或 Markdown 文档，或从公开网页导入内容，建立用户隔离的知识库。
- 结合知识库和岗位上下文进行简历分析、岗位匹配与求职问答。
- 在职业中心管理简历、岗位、投递、面试题、报告和技能计划。
- 通过 Cookie 会话、CSRF、RBAC、共享限流、用户级数据锁、数据库约束和审计日志保护业务操作。
- 使用 Vue 3、FastAPI、MySQL、ChromaDB、Redis、DeepSeek API 和 Docker Compose 构建。

## 快速启动

要求：Docker Engine 与 Docker Compose v2。首次启动 RAG 时需要下载嵌入模型，请确保主机具备足够磁盘空间并能访问模型源。

```bash
cp .env.example .env
```

至少替换 `.env` 中的以下值，不能沿用示例密码：

```dotenv
DEEPSEEK_API_KEY=sk-your-real-key
MYSQL_ROOT_PASSWORD=<long-random-root-password>
DB_USER=aiagent
DB_PASSWORD=<long-random-application-password>
```

启动并等待健康检查：

```bash
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
```

| 服务 | 默认地址 |
| --- | --- |
| Web 应用 | <http://localhost> |
| OpenAPI | <http://localhost:8000/docs> |
| 存活检查 | <http://localhost:8000/api/health/live> |
| 就绪检查 | <http://localhost:8000/api/health/ready> |
| Adminer（仅本机、可选） | 运行 `docker compose --profile tools up -d adminer` 后访问 <http://localhost:8088> |

生产部署前必须完成 TLS、Cookie、可信代理、CORS、密钥和备份配置，参见[部署指南](docs/deployment.md)。

## 文档

| 文档 | 内容 |
| --- | --- |
| [架构说明](docs/architecture.md) | 分层、数据流、存储边界与扩展规则 |
| [用户指南](docs/user-guide.md) | 从注册到简历、岗位、投递、面试和数据管理 |
| [AI 职业数据建议](docs/ai-suggestions.md) | 对话建议卡、确认写入、状态与安全边界 |
| [管理员指南](docs/admin-guide.md) | 管理员初始化、角色、账号与审计 |
| [API 说明](docs/api.md) | 认证、CSRF、SSE、MCP 与职业中心接口 |
| [配置参考](docs/configuration.md) | 全部环境变量、默认值与生产要求 |
| [部署与备份](docs/deployment.md) | Compose、健康检查、备份、恢复与升级 |
| [测试指南](docs/testing.md) | 后端、前端、浏览器和完整容器测试 |
| [迭代路线图](docs/roadmap.md) | 已完成基线、上线门禁与后续新板块 |
| [安全说明](SECURITY.md) | 安全边界、部署责任与漏洞报告 |
| [隐私说明](PRIVACY.md) | 数据类型、存储、外部处理与现有删除能力 |
| [视觉规范](DESIGN.md) | 前端设计令牌、组件和响应式约定 |

## 本地开发与测试

后端（Python 3.11）：

```bash
python -m pip install -r backend/requirements-dev.txt
pytest -q backend/tests
python -m compileall -q backend
```

前端（Node.js 22）：

```bash
cd frontend
npm ci
npm run dev
```

完整测试命令见[测试指南](docs/testing.md)。

## 数据与分支约定

- MySQL 数据在 `mysql_data` 命名卷中；ChromaDB 默认在工作区内、已忽略的 `chroma_db/` 挂载目录中；Redis 仅承载可重建的限流状态。
- `.env`、`chroma_db/` 与 `logs/` 均不应提交。MySQL 与 ChromaDB 必须作为同一个备份批次处理。
- 职业写入、职业数据导出和知识库写入会按用户串行化；导出当前在后端内存中组装完整 JSON，大数据账号需评估容量，详见[架构说明](docs/architecture.md)。
- `main` 保持可构建、可测试、可部署。功能和修复从最新 `main` 创建短生命周期分支，通过 CI 和 Pull Request 合入。

本项目的运行行为以代码、OpenAPI 和本仓库文档为准；部署方仍需根据自身场景完成安全与隐私评估。
