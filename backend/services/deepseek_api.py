import os
import time
import logging
from dotenv import load_dotenv
import requests

logger = logging.getLogger("aiagent.deepseek")

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
API_URL = (
    os.getenv("DEEPSEEK_API_URL")
    or "https://api.deepseek.com/chat/completions"
).strip()

def get_ai_response(messages, max_retries=2, timeout=30):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "stream": False
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']

        except Exception as e:          # ← 改这里，捕获一切异常
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(f"请求失败 (尝试 {attempt+1}/{max_retries+1})，{wait}秒后重试: {e}")
                time.sleep(wait)
            else:
                logger.error(f"所有重试均失败: {e}")
                return "抱歉，我现在有点问题，请稍后再试。"

def get_ai_response_with_tools(messages, tools=None, max_retries=2, timeout=30):
    """
    支持工具调用的 API 请求，返回完整的响应字典（可能包含 tool_calls）
    调用者需要根据返回内容判断是否有工具调用。
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "stream": False,
        "tools": tools if tools else []
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"⚠️ 工具调用请求失败 (尝试 {attempt+1}/{max_retries+1})，{wait}秒后重试... 错误: {e}")
                time.sleep(wait)
            else:
                logger.error(f"所有重试均失败: {e}")
                return None

def get_ai_response_stream(messages):
    """
    流式调用 DeepSeek API，逐个返回 token
    Yields: str (每个 token)
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "stream": True
    }

    response = requests.post(
        API_URL,
        headers=headers,
        json=payload,
        timeout=120,
        stream=True
    )
    response.raise_for_status()

    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data_str = line[6:]  # 去掉 "data: " 前缀
        if data_str == "[DONE]":
            break
        try:
            import json
            chunk = json.loads(data_str)
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content
        except (json.JSONDecodeError, KeyError, IndexError):
            continue


# --- 测试代码 ---
if __name__ == "__main__":
    test_messages = [{"role": "user", "content": "你好，请介绍一下你自己。"}]
    reply = get_ai_response(test_messages)
    print(f"AI回复: {reply}")
