# backend/services/analytics.py
"""轻量数据分析服务 —— 基于 MySQL 统计数据"""
from backend.services.database import get_connection


def get_overview(user_id: int = None):
    """
    对话概览：总会话数、总消息数、平均每会话消息数
    user_id 为 None 时统计全局
    """
    conn = get_connection()
    cursor = conn.cursor()

    if user_id:
        user_filter = "WHERE user_id = %s"
        params = (user_id,)
    else:
        user_filter = ""
        params = ()

    # 总消息数
    cursor.execute(f"SELECT COUNT(*) AS cnt FROM messages {user_filter}", params)
    total_msgs = cursor.fetchone()['cnt']

    # 总会话数
    cursor.execute(f"SELECT COUNT(*) AS cnt FROM sessions {user_filter}", params)
    total_sessions = cursor.fetchone()['cnt']

    conn.close()

    avg_per_session = round(total_msgs / total_sessions, 1) if total_sessions > 0 else 0

    return {
        "total_sessions": total_sessions,
        "total_messages": total_msgs,
        "avg_per_session": avg_per_session
    }


def get_feedback_stats(user_id: int = None):
    """
    反馈统计：赞、踩、无反馈的数量和比例
    """
    conn = get_connection()
    cursor = conn.cursor()

    if user_id:
        user_filter = "WHERE user_id = %s"
        params = (user_id,)
    else:
        user_filter = ""
        params = ()

    where_clause = ""
    if user_id:
        where_clause = "AND user_id = %s"
    cursor.execute(
        f"""SELECT
               SUM(CASE WHEN feedback = 'like' THEN 1 ELSE 0 END) AS likes,
               SUM(CASE WHEN feedback = 'dislike' THEN 1 ELSE 0 END) AS dislikes,
               SUM(CASE WHEN feedback IS NULL THEN 1 ELSE 0 END) AS no_feedback,
               COUNT(*) AS total
           FROM messages
           WHERE role = 'assistant' {where_clause}""",
        params if user_id else ()
    )
    row = cursor.fetchone()
    conn.close()

    total = row['total'] or 0
    likes = row['likes'] or 0
    dislikes = row['dislikes'] or 0
    no_fb = row['no_feedback'] or 0

    return {
        "likes": likes,
        "dislikes": dislikes,
        "no_feedback": no_fb,
        "total_rated": total - no_fb,
        "like_rate": round(likes / (likes + dislikes) * 100, 1) if (likes + dislikes) > 0 else 0
    }


def get_daily_trend(user_id: int = None, days: int = 7):
    """
    最近 N 天每日消息数趋势
    """
    conn = get_connection()
    cursor = conn.cursor()

    if user_id:
        user_filter = "AND user_id = %s"
        params = (days, user_id)
    else:
        user_filter = ""
        params = (days,)

    cursor.execute(
        f"""SELECT DATE(timestamp) AS day, COUNT(*) AS cnt
           FROM messages
           WHERE timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY) {user_filter}
           GROUP BY DATE(timestamp)
           ORDER BY day ASC""",
        params
    )
    rows = cursor.fetchall()
    conn.close()

    # 补全没有消息的日期（填 0）
    from datetime import datetime, timedelta
    today = datetime.now().date()
    trend = {}
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        trend[d] = 0
    for row in rows:
        trend[row['day'].isoformat() if hasattr(row['day'], 'isoformat') else str(row['day'])] = row['cnt']

    return [{"date": k, "count": v} for k, v in trend.items()]
