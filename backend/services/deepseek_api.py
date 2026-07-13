"""Small DeepSeek chat-completions client used by all model call paths."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

import requests
try:
    from dotenv import load_dotenv
except ImportError:  # Keep lightweight unit-test and tooling imports usable.
    def load_dotenv(*args, **kwargs):
        return False


logger = logging.getLogger("aiagent.deepseek")

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = (
    os.getenv("DEEPSEEK_API_URL")
    or "https://api.deepseek.com/chat/completions"
).strip()
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_MODEL = (os.getenv("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL).strip()


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }


def get_ai_response(messages, max_retries=2, timeout=30):
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "stream": False,
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=_headers(),
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as error:
            if attempt < max_retries:
                wait = 2**attempt
                logger.warning(
                    "DeepSeek request failed (attempt %s/%s); retrying in %ss: %s",
                    attempt + 1,
                    max_retries + 1,
                    wait,
                    error,
                )
                time.sleep(wait)
            else:
                logger.error("DeepSeek request failed after all attempts: %s", error)
                return "抱歉，我现在遇到了一些问题，请稍后再试。"


def get_ai_response_with_tools(
    messages,
    tools=None,
    max_retries=2,
    timeout=30,
    *,
    tool_choice: Optional[dict[str, Any] | str] = None,
):
    """Return the full completion response, including optional tool calls."""
    payload: dict[str, Any] = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "stream": False,
        "tools": tools or [],
    }
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=_headers(),
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as error:
            if attempt < max_retries:
                wait = 2**attempt
                logger.warning(
                    "DeepSeek tool request failed (attempt %s/%s); retrying in %ss: %s",
                    attempt + 1,
                    max_retries + 1,
                    wait,
                    error,
                )
                time.sleep(wait)
            else:
                logger.error("DeepSeek tool request failed after all attempts: %s", error)
                return None


def get_ai_response_stream(messages):
    """Stream text tokens from the DeepSeek chat-completions API."""
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "stream": True,
    }
    response = requests.post(
        DEEPSEEK_API_URL,
        headers=_headers(),
        json=payload,
        timeout=120,
        stream=True,
    )
    response.raise_for_status()

    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data_str = line[6:]
        if data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if content:
                yield content
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            continue
