# backend/services/security.py
"""安全模块：内容审核 + 频率限制"""
import re
import time
from collections import defaultdict

# ==================== 敏感词列表 ====================
# 按类别组织，方便理解和扩展
SENSITIVE_PATTERNS = {
    # 涉政敏感词（示例，实际应用需更完善）
    "politics": [
        r"反动", r"颠覆.*政权", r"分裂.*国家",
    ],
    # 色情/低俗
    "adult": [
        r"色情", r"裸体", r"性交",
    ],
    # 暴力/恐怖
    "violence": [
        r"杀人.*方法", r"制作.*炸弹", r"恐怖.*袭击",
    ],
    # 人身攻击
    "hate": [
        r"傻[逼屄叉]", r"[操艹草].*妈", r"去死",
    ],
    # 隐私信息泄露模式
    "privacy": [
        r"\d{15,19}",                    # 身份证号
        r"\d{11}",                        # 手机号
    ],
}


def moderate_text(text: str, user_id: int = None) -> tuple:
    """
    审核文本内容
    返回: (is_safe: bool, reason: str)
      - is_safe=True: 内容安全
      - is_safe=False: 包含违规内容
    """
    if not text:
        return True, ""

    for category, patterns in SENSITIVE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False, f"内容包含敏感信息（{category}），请修改后重试。"

    return True, ""


# ==================== 频率限制 ====================
# 默认限制：每个用户每分钟最多 30 次请求
DEFAULT_RATE_LIMIT = int(__import__('os').getenv('RATE_LIMIT_PER_MINUTE', '30'))
_request_log = defaultdict(list)  # {user_id: [timestamp, timestamp, ...]}


def check_rate_limit(user_id: int, max_requests: int = None) -> tuple:
    """
    检查频率限制
    返回: (allowed: bool, wait_seconds: int)
    """
    if max_requests is None:
        max_requests = DEFAULT_RATE_LIMIT

    now = time.time()
    window = 60  # 1分钟窗口

    # 清理过期记录
    _request_log[user_id] = [t for t in _request_log[user_id] if now - t < window]

    if len(_request_log[user_id]) >= max_requests:
        wait = int(window - (now - _request_log[user_id][0])) + 1
        return False, max(wait, 1)

    _request_log[user_id].append(now)
    return True, 0


# ==================== 输入净化 ====================
def sanitize_input(text: str) -> str:
    """
    净化用户输入：去除首尾空白、限制长度、去除潜在危险字符
    """
    if not text:
        return ""

    # 限制最大长度（防止滥用）
    text = text[:2000]

    # 去除首尾空白
    text = text.strip()

    # 去除零宽字符（可能用来绕过审核）
    text = re.sub(r'[​‌‍‎‏﻿]', '', text)

    return text
