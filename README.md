# 职达 —— AI 求职顾问

> 基于大模型 RAG 技术的智能求职辅助平台  
> Vue 3 + FastAPI + DeepSeek + ChromaDB + MySQL + Docker

---

## 📋 项目简介

**职达** 是一款面向大学生求职场景的 AI 助手，帮助解决求职三大痛点：

| 痛点             | 解决方案                       |
| -------------- | -------------------------- |
| 简历没人帮你审查       | 上传简历 → AI 多维度分析评分 + 改进建议   |
| JD 看不懂、不知道怎么匹配 | 粘贴 JD → AI 量化匹配度 + 技能差距清单  |
| 面试没人陪着练        | AI 扮演面试官出题 → 你回答 → AI 打分点评 |

系统上传简历后自动构建**个人知识库**，所有分析均基于你的真实经历，而非泛泛的通用模板。

---

## 🛠 技术架构

```
┌─────────────────────────────────────────────────┐
│                    前端 (Vue 3)                    │
│  WelcomePage → Dashboard → ChatWindow            │
│  + ResumeReport / JobMatchPanel / AnalyticsPanel │
│  Element Plus + ECharts + Marked + Axios         │
└───────────────────┬─────────────────────────────┘
                    │ RESTful + SSE
┌───────────────────▼─────────────────────────────┐
│                后端 (FastAPI)                     │
│  routers: users / sessions / documents / chat    │
│           analytics / mcp                        │
│  services: rag / tools / deepseek_api / crawler  │
│            security / database / preprocessing   │
└───────┬───────────────────────┬─────────────────┘
        │                       │
┌───────▼────────┐   ┌──────────▼──────────┐
│   MySQL 8.0    │   │  DeepSeek API       │
│  用户·会话·消息 │   │  deepseek-chat 模型  │
└────────────────┘   └─────────────────────┘
        │
┌───────▼────────┐
│  ChromaDB      │
│  向量知识库     │
└────────────────┘
```

---

## ✨ 核心功能

### 1. 📋 简历智能分析

- 支持 PDF / DOCX / TXT / MD 四种格式上传
- 自动构建个人向量知识库（ChromaDB）
- AI 从技术栈、项目经验、成果量化等维度分析评分
- **ECharts 雷达图** 可视化展示能力画像

### 2. 🎯 岗位精准匹配

- 手动粘贴 JD 或 **爬虫自动抓取** 在线招聘页面
- AI 对比简历与 JD，输出匹配度百分比
- **仪表盘** 可视化 + 双栏技能对比（✅ 匹配 / ⚠️ 缺失）

### 3. 🎤 模拟面试训练

- AI 根据 JD 自动生成 5 道面试题（技术题 + 行为题 6:4 比例）
- 支持输入回答后 AI 打分 + 点评 + 改进示范

### 4. 📊 数据分析面板

- 对话概览（总会话数、消息数）
- 反馈统计（赞/踩比例）
- 近 7 天消息趋势图

### 5. 🏠 工作台首页

- 登录后展示功能卡片导航 + 求职小贴士
- 一键跳转对话并触发对应操作

### 6. 🔧 其他特性

- **10 个 Agent 工具**：支持大模型自动调用（分析、匹配、出题、计算等）
- **MCP 协议**：JSON-RPC 2.0 标准端点，外部系统可发现并调用所有工具
- **SSE 流式输出**：AI 回复逐字显示，配合"正在输入"动画
- **暗色模式**：全局暗色切换，localStorage 持久化
- **网页爬虫**：URL 导入在线内容到知识库
- **安全模块**：PBKDF2 密码哈希 + 敏感词审核 + 频率限制

---

## 🚀 快速开始

### 前置要求

- Docker Desktop 4.x+
- DeepSeek API Key（[申请地址](https://platform.deepseek.com/)）

### 1. 克隆项目

```bash
git clone <repo-url>
cd 职达-AI求职顾问
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY
```

### 3. 一键启动

```bash
docker compose up -d
```

### 4. 访问

| 服务     | 地址                               | 说明                         |
| ------ | -------------------------------- | -------------------------- |
| 前端主界面  | http://localhost                 | Nginx + Vue 生产模式           |
| 后端 API | http://localhost:8000            | FastAPI 服务                 |
| 健康检查   | http://localhost:8000/api/health | 服务状态                       |
| 数据库管理  | http://localhost:8088            | Adminer（账号 root / root123） |
| MCP 服务 | http://localhost:8000/api/mcp/   | JSON-RPC 2.0               |

### 5. 前端开发模式（可选）

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173（支持热重载）
```

---

## 📁 项目结构

```
├── docker-compose.yml           # 容器编排（4 服务）
├── .env.example                 # 环境变量模板
├── TEST_PLAN.md                 # 测试清单
│
├── backend/                     # 后端服务
│   ├── main.py                  # 启动入口（日志/中间件/健康检查）
│   ├── requirements.txt         # Python 依赖
│   ├── Dockerfile               # 后端镜像
│   ├── routers/                 # API 路由（6 模块 20+ 端点）
│   │   ├── users.py             # 用户注册/登录
│   │   ├── sessions.py          # 会话 CRUD
│   │   ├── documents.py         # 文档上传/删除/URL 导入
│   │   ├── chat.py              # 对话（流式 + 非流式 + 工具调用）
│   │   ├── analytics.py         # 数据统计（概览/反馈/趋势）
│   │   └── mcp.py               # MCP 协议（JSON-RPC 2.0）
│   └── services/                # 业务逻辑层
│       ├── rag.py               # RAG 引擎（ChromaDB + 语义检索）
│       ├── tools.py             # Agent 工具链（10 个工具）
│       ├── deepseek_api.py      # DeepSeek API 封装
│       ├── crawler.py           # 网页爬虫（HTMLParser）
│       ├── security.py          # 安全模块（审核/限流/净化）
│       ├── database.py          # MySQL 数据库操作
│       ├── preprocessing.py     # 文本预处理
│       ├── analytics.py         # 数据统计 SQL
│       ├── memory.py            # 记忆管理
│       └── intent.py            # 意图识别
│
├── frontend/                    # 前端应用
│   ├── index.html               # 入口（含 ECharts CDN）
│   ├── package.json             # 依赖声明
│   ├── vite.config.js           # Vite 配置
│   ├── Dockerfile               # 前端镜像（多阶段构建）
│   ├── nginx.conf               # Nginx 配置
│   └── src/
│       ├── App.vue              # 主框架（面板集成 + 状态管理）
│       ├── main.js              # Vue 入口
│       ├── api/index.js         # 10 个 API 封装函数
│       └── components/
│           ├── WelcomePage.vue      # 欢迎页（登录/注册）
│           ├── Dashboard.vue        # 工作台首页
│           ├── ChatWindow.vue       # 聊天窗口（SSE 流式）
│           ├── Sidebar.vue          # 侧边栏（会话/KB/工具箱）
│           ├── ResumeReport.vue     # 简历报告（ECharts 雷达图）
│           ├── JobMatchPanel.vue    # 匹配面板（仪表盘 + 技能对比）
│           └── AnalyticsPanel.vue   # 数据分析面板
│
└── database/
    └── init.sql                 # MySQL 建表脚本
```

---

## 🔌 API 接口一览

| 方法     | 路径                            | 说明              |
| ------ | ----------------------------- | --------------- |
| POST   | `/api/users/register`         | 用户注册            |
| POST   | `/api/users/login`            | 用户登录            |
| GET    | `/api/sessions`               | 会话列表            |
| POST   | `/api/sessions`               | 创建会话            |
| DELETE | `/api/sessions/{id}`          | 删除会话            |
| PUT    | `/api/sessions/{id}/rename`   | 重命名会话           |
| GET    | `/api/sessions/{id}/messages` | 会话历史消息          |
| POST   | `/api/documents/upload`       | 上传文档            |
| GET    | `/api/documents/status`       | 知识库状态           |
| DELETE | `/api/documents/source`       | 删除来源            |
| POST   | `/api/documents/import-url`   | URL 导入知识库       |
| POST   | `/api/documents/fetch-url`    | URL 抓取文本        |
| POST   | `/api/chat/`                  | 非流式对话           |
| POST   | `/api/chat/stream`            | SSE 流式对话        |
| GET    | `/api/analytics/overview`     | 对话概览            |
| GET    | `/api/analytics/feedback`     | 反馈统计            |
| GET    | `/api/analytics/trend`        | 消息趋势            |
| GET    | `/api/mcp/`                   | MCP 服务信息        |
| POST   | `/api/mcp/`                   | MCP JSON-RPC 端点 |

---

## 🤖 Agent 工具列表

| 工具名                       | 功能      | 类型   |
| ------------------------- | ------- | ---- |
| `get_knowledge_info`      | 查询知识库状态 | 知识检索 |
| `search_knowledge`        | 语义搜索知识库 | 知识检索 |
| `summarize_document`      | 文档摘要    | 知识检索 |
| `analyze_resume`          | 简历深度分析  | 求职业务 |
| `match_job`               | 简历-岗位匹配 | 求职业务 |
| `generate_questions`      | 生成面试题   | 求职业务 |
| `mock_interview_feedback` | 面试回答点评  | 求职业务 |
| `get_current_time`        | 获取当前时间  | 辅助   |
| `calculate`               | 安全数学计算  | 辅助   |
| `fetch_job_page`          | 网页内容抓取  | 辅助   |

---

## 👥 团队成员

| 姓名  | 角色            | 核心职责                                            |
| --- | ------------- | ----------------------------------------------- |
| 胡振文 | 后端核心 + DevOps | RAG 引擎、Agent 工具链、DeepSeek API、爬虫、安全模块、Docker 部署 |
| 马子勋 | 前端开发          | Vue3 架构、8 个组件开发、UI 美化、SSE 流式交互、前后端联调            |
| 姜一成 | 后端开发          | FastAPI 架构、20+ API 接口、MySQL 数据库设计、MCP 协议实现      |

---
