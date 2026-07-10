# memory.py
from backend.services.deepseek_api import get_ai_response

def trim_history(messages, max_turns=5):
    """
    保留最近 max_turns 轮对话（1轮 = 用户 + 助手），
    返回截断后的消息列表。
    messages 格式: [{"role": ..., "content": ...}, ...]
    """
    keep_count = max_turns * 2
    if len(messages) > keep_count:
        return messages[-keep_count:]
    return messages

def generate_summary(messages, max_summary_chars=200):
    """
    用 AI 把完整的对话历史总结成简短摘要。
    返回摘要字符串，失败时返回空字符串。
    """
    if not messages:
        return ""

    # 拼接历史（取最近 10 轮作为总结依据，避免 token 过多）
    recent_for_summary = messages[-20:]  # 最多取最近 20 条消息
    history_text = "\n".join(
        [f"{m['role']}: {m['content']}" for m in recent_for_summary]
    )

    prompt = f"""请用不超过{max_summary_chars}字总结以下对话的关键信息，不要遗漏重要事实或用户偏好：
---
{history_text}
---
摘要："""

    try:
        summary = get_ai_response(
            [{"role": "user", "content": prompt}],
            max_retries=0  # 摘要失败不要重试，避免太慢
        )
        return summary.strip()
    except Exception:
        return ""