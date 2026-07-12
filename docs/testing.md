# 测试指南

## 测试层次

| 层次 | 工具 | 主要范围 |
| --- | --- | --- |
| 后端单元/集成 | pytest | 认证、CSRF、越权、限流、幂等、职业数据、抓取与上传边界 |
| 前端单元 | Vitest、Vue Test Utils | API client、认证恢复、组件状态、SSE 缓冲和职业表单 |
| 浏览器流程 | Playwright | 登录、普通用户、管理员、响应式、Reduced Motion |
| 容器冒烟 | Docker Compose、DeepSeek mock、Playwright | MySQL + Redis + FastAPI + Nginx/Vue 的真实连通性 |

测试不得调用真实 DeepSeek 计费端点或抓取不受控公网目标。使用测试替身和确定性夹具。

## 后端

要求 Python 3.11：

```bash
python -m pip install -r backend/requirements-dev.txt
pytest -q backend/tests
python -m compileall -q backend
```

覆盖率（用于发现缺口，不把单一百分比当作质量结论）：

```bash
pytest --cov=backend --cov-report=term-missing backend/tests
```

后端测试通过 `backend/tests/conftest.py` 隔离环境；新增测试不得依赖开发者真实 `.env`、数据库或 Redis。数据库类测试应使用 fixture/monkeypatch 或受控容器，并验证成功路径与事务回滚。

## 前端

要求 Node.js 22：

```bash
cd frontend
npm ci
npm run lint
npm run test:run
npm run build
```

交互式单元测试可运行 `npm test`。浏览器测试首次需要 Chromium：

```bash
npx playwright install chromium
npm run test:e2e
```

普通 E2E 使用本地 mock API，不要求真实后端。失败截图、trace 等产物位于 `frontend/output/playwright/`；不要把含真实用户数据的产物上传到公共 CI。

## Docker 完整冒烟

CI overlay 使用 `backend/tests/deepseek_mock.py`，并关闭 RAG 模型加载。先验证合并后的 Compose：

```bash
docker compose --env-file .env.example \
  -f docker-compose.yml -f docker-compose.ci.yml config --quiet
```

启动完整测试栈：

```bash
docker compose --env-file .env.example \
  -f docker-compose.yml -f docker-compose.ci.yml \
  up -d --build --wait --wait-timeout 420 \
  mysql redis deepseek-mock backend frontend
```

然后：

```bash
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e:docker
```

诊断与清理测试专用卷：

```bash
docker compose --env-file .env.example \
  -f docker-compose.yml -f docker-compose.ci.yml logs --no-color --tail=300

docker compose --env-file .env.example \
  -f docker-compose.yml -f docker-compose.ci.yml down --volumes --remove-orphans
```

最后一条命令只用于确认是 CI/临时测试栈的环境；不得对开发或生产数据卷执行。

## 变更验收矩阵

每个 PR 至少运行与风险匹配的项目；影响认证、数据结构或部署的 PR 应运行全部：

- 认证：注册、登录、刷新恢复、退出、强制改密、过期/撤销会话、缺失/错误 CSRF。
- 授权：普通用户访问管理员接口；用户 A 对用户 B 的会话、消息、文档及六类职业资源执行读写删，均不得成功。
- 管理：角色和状态保护、最后一个超级管理员、密码重置仅展示一次、会话撤销、审计记录。
- 职业数据：六类 CRUD、枚举与 0–100 范围、报告 payload 256 KiB UTF-8 边界、岗位复合外键、主简历并发唯一、面试题归属、报告关联、全量导出、错误确认不清空、正确确认只清理规定数据。
- 并发与容量：同一用户的 career 写入/导出/知识库写入与清空互斥，锁超时返回 409；清空中途失败可重试；大导出评估内存、耗时和锁持有时间。
- 数据迁移：legacy bootstrap 与 migration 共用 schema lock；首次应用记录 SHA-256 checksum；已应用 SQL 或名称漂移时启动失败。
- 文档安全：扩展名、字节、PDF 页数、提取文本、分块上限；失败时不应留下部分向量。
- 抓取安全：localhost、IPv4/IPv6 私网、link-local、云 metadata、DNS 解析到内网、重定向转内网、超大 Content-Length、无长度超大流、重定向过多、每用户限流。
- 聊天：输入校验、429、同 ID 回放/冲突/处理中、租约接管、SSE token/done/error、客户端断开后的记录一致性。
- 恢复：MySQL 与 Chroma 同批备份在隔离环境恢复，职业记录数量和知识库来源一致。
- UI：375、768、1024、1440px；键盘导航、焦点、加载/空/错误/重试、Reduced Motion。

## CI 门禁

`.github/workflows/ci.yml` 依次执行：

1. 前端 lint、Vitest、production build、Playwright。
2. 后端 pytest、语法编译、Compose 配置校验。
3. 完整 Docker 栈与浏览器 smoke。

不要通过跳过测试、放宽断言或把失败用例改成空测试来修复 CI。若测试依赖发生变化，应在 PR 中说明失败原因、更新的契约与新增的回归覆盖。
