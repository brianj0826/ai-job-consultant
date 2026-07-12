import sys
import os
import logging
import time
from urllib.parse import urlsplit
sys.path.append(os.path.dirname(__file__))
from fastapi import FastAPI, Request, status
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
_session_cleanup_worker = None

app = FastAPI(title="职达 - AI 求职顾问 API", version="2.0")


def _cors_allowed_origins() -> list[str]:
    defaults = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:80",
        "http://127.0.0.1:80",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    raw = os.getenv("CORS_ALLOWED_ORIGINS")
    origins = defaults if raw is None else [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    if not origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS must contain at least one origin")
    for origin in origins:
        parsed = urlsplit(origin)
        if origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError(f"Invalid CORS origin: {origin}")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise RuntimeError(f"CORS origin must not contain a path/query/fragment: {origin}")
    return list(dict.fromkeys(origins))

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
    allow_origins=_cors_allowed_origins(),
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
from backend.routers import admin, auth, career, chat, documents, users, sessions, feedback, analytics, mcp

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(career.router, prefix="/api/career", tags=["career"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(mcp.router, prefix="/api/mcp", tags=["mcp"])

@app.on_event("startup")
def startup_check():
    global _session_cleanup_worker
    """启动时校验关键配置"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("DEEPSEEK_API_KEY 未设置！AI 功能将不可用。")
    else:
        logger.info("DEEPSEEK_API_KEY 已配置")

    from backend.services.auth import (
        AuthConfigurationError,
        BootstrapConfigurationError,
        bootstrap_first_admin_from_environment,
        validate_auth_configuration,
    )
    try:
        validate_auth_configuration()
        from backend.services.admin import validate_admin_configuration
        validate_admin_configuration()
        from backend.services.rate_limit import validate_rate_limit_configuration
        rate_limit_backend = validate_rate_limit_configuration()
        logger.info("Rate-limit backend: %s", rate_limit_backend)
    except AuthConfigurationError as e:
        logger.critical("Invalid authentication configuration: %s", e)
        raise
    except Exception as e:
        logger.critical("Invalid administrator configuration: %s", e)
        raise

    try:
        from backend.services.database import (
            check_database_readiness,
            cleanup_expired_auth_sessions,
            init_database,
            validate_database_configuration,
        )
        validate_database_configuration()
        from backend.services.migrations import run_migrations, schema_migration_lock
        with schema_migration_lock():
            init_database()
            applied_migrations = run_migrations(acquire_lock=False)
        if applied_migrations:
            logger.info("Applied database migrations: %s", applied_migrations)
        check_database_readiness()
        retention_days = int(os.getenv("AUTH_SESSION_RETENTION_DAYS", "30"))
        retention_days = max(1, min(retention_days, 3650))
        removed_sessions = cleanup_expired_auth_sessions(retention_days)
        logger.info("数据库表结构已就绪")
        if removed_sessions:
            logger.info("已清理 %s 条过期认证会话", removed_sessions)
    except Exception as e:
        logger.critical("数据库初始化或 schema readiness 校验失败: %s", e)
        raise

    # Bootstrap credentials are optional, but when either value is supplied a
    # malformed configuration must stop startup rather than leave an unknown
    # administrator state. The service never logs or persists the raw secret.
    try:
        bootstrap = bootstrap_first_admin_from_environment()
        if bootstrap and bootstrap["created"]:
            logger.warning("Initial super-admin created for username: %s", bootstrap["username"])
        elif bootstrap:
            logger.info("A super-admin already exists; bootstrap credentials were not applied")
    except BootstrapConfigurationError as e:
        logger.critical("Invalid administrator bootstrap configuration: %s", e)
        raise
    except Exception as e:
        logger.critical("Administrator bootstrap failed: %s", e)
        raise

    try:
        from backend.services.database import get_connection
        conn = get_connection()
        conn.close()
        logger.info("数据库连接正常")
    except Exception as e:
        logger.warning(f"数据库连接失败: {e}")

    if os.getenv("RAG_DISABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        from backend.services.rag import get_collection, validate_rag_configuration
        validate_rag_configuration()
        try:
            get_collection(0)
            logger.info("ChromaDB 向量数据库可用")
        except Exception as e:
            logger.warning(f"ChromaDB 初始化失败: {e}")
    else:
        logger.info("RAG is disabled by configuration")

    rate_limit = os.getenv("RATE_LIMIT_PER_MINUTE", "30")
    logger.info(f"频率限制: {rate_limit} 次/分钟")
    cleanup_interval = int(os.getenv("AUTH_SESSION_CLEANUP_INTERVAL_SECONDS", "3600"))
    cleanup_interval = max(60, min(cleanup_interval, 86_400))
    from backend.services.maintenance import PeriodicSessionCleanup
    if _session_cleanup_worker:
        _session_cleanup_worker.stop()
    _session_cleanup_worker = PeriodicSessionCleanup(
        cleanup_interval,
        retention_days,
        logger=logger,
    )
    _session_cleanup_worker.start()
    logger.info("服务启动完成")


@app.on_event("shutdown")
def shutdown_cleanup_worker():
    global _session_cleanup_worker
    if _session_cleanup_worker:
        _session_cleanup_worker.stop()
        _session_cleanup_worker = None


@app.get("/")
def root():
    return {"message": "AI 文档助手后端运行中"}

@app.get("/api/health/live")
def liveness():
    """Process liveness: does not depend on external services."""
    return {"status": "alive"}


def _readiness_response():
    try:
        from backend.services.database import check_database_readiness
        from backend.services.rate_limit import check_rate_limit_readiness
        details = check_database_readiness()
        details["rate_limit"] = check_rate_limit_readiness()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready", **details})
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "database": "unavailable"},
        )


@app.get("/api/health/ready")
def readiness():
    """Dependency readiness for orchestrators and load balancers."""
    return _readiness_response()


@app.get("/api/health")
def health():
    """Backwards-compatible readiness endpoint."""
    return _readiness_response()
