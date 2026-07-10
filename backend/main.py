import sys
import os
import logging
import time
sys.path.append(os.path.dirname(__file__))
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# ==================== 日志系统配置 ====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 根 logger
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("aiagent")

app = FastAPI(title="职达 - AI 求职顾问 API", version="2.0")

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(
        "%s %s → %s (%.2fs)",
        request.method, request.url.path, response.status_code, elapsed
    )
    return response

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:80",
        "http://127.0.0.1:80"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常 {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"}
    )

# 导入路由
from backend.routers import chat, documents, users, sessions, feedback, analytics, mcp

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(mcp.router, prefix="/api/mcp", tags=["mcp"])

@app.on_event("startup")
def startup_check():
    """启动时校验关键配置"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("DEEPSEEK_API_KEY 未设置！AI 功能将不可用。")
    else:
        masked = api_key[:6] + "***" + api_key[-4:]
        logger.info(f"DEEPSEEK_API_KEY 已配置: {masked}")

    try:
        from backend.services.database import init_database
        init_database()
        logger.info("数据库表结构已就绪")
    except Exception as e:
        logger.warning(f"数据库初始化失败: {e}")

    try:
        from backend.services.database import get_connection
        conn = get_connection()
        conn.close()
        logger.info("数据库连接正常")
    except Exception as e:
        logger.warning(f"数据库连接失败: {e}")

    try:
        from backend.services.rag import get_collection
        get_collection(0)
        logger.info("ChromaDB 向量数据库可用")
    except Exception as e:
        logger.warning(f"ChromaDB 初始化失败: {e}")

    rate_limit = os.getenv("RATE_LIMIT_PER_MINUTE", "30")
    logger.info(f"频率限制: {rate_limit} 次/分钟")
    logger.info("服务启动完成")


@app.get("/")
def root():
    return {"message": "AI 文档助手后端运行中"}

@app.get("/api/health")
def health():
    """Docker 健康检查端点"""
    try:
        from backend.services.database import get_connection
        conn = get_connection()
        conn.close()
        return {"status": "healthy", "database": "ok"}
    except Exception:
        return {"status": "healthy", "database": "unavailable"}