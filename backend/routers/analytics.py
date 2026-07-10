# backend/routers/analytics.py
"""数据分析 API 路由"""
from fastapi import APIRouter, Query
from backend.services.analytics import get_overview, get_feedback_stats, get_daily_trend

router = APIRouter()


@router.get("/overview")
def overview(user_id: int = Query(None, description="用户ID，不传则全局统计")):
    """对话概览统计"""
    return get_overview(user_id)


@router.get("/feedback")
def feedback(user_id: int = Query(None, description="用户ID")):
    """用户反馈统计"""
    return get_feedback_stats(user_id)


@router.get("/trend")
def trend(user_id: int = Query(None, description="用户ID"), days: int = Query(7, ge=1, le=30)):
    """每日消息数趋势"""
    return get_daily_trend(user_id, days)
