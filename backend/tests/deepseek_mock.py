"""Deterministic OpenAI-compatible chat endpoint used by Docker CI smoke tests."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os


HOST = "0.0.0.0"
PORT = int(os.getenv("DEEPSEEK_MOCK_PORT", "9000"))


class Handler(BaseHTTPRequestHandler):
    server_version = "DeepSeekCIMock/1.0"

    def log_message(self, format: str, *args) -> None:
        return

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"detail": "not found"})

    def do_POST(self) -> None:
        if self.path != "/chat/completions":
            self._json(404, {"detail": "not found"})
            return
        if self.headers.get("Authorization") != "Bearer ci-mock-key":
            self._json(401, {"detail": "invalid mock credential"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"detail": "invalid JSON"})
            return

        tool_choice = payload.get("tool_choice")
        forced_function = (
            tool_choice.get("function", {}).get("name")
            if isinstance(tool_choice, dict)
            else None
        )
        if forced_function == "propose_career_suggestions":
            arguments = {
                "suggestions": [
                    {
                        "resource_type": "skills",
                        "title": "添加 Redis 技能计划",
                        "reason": "目标岗位需要缓存与限流能力",
                        "intent": "explicit",
                        "confidence": 0.99,
                        "payload": {
                            "skill": "Redis",
                            "target_level": "能够完成生产环境缓存与限流设计",
                            "status": "planned",
                            "progress": 0,
                            "notes": "Docker mock suggestion",
                        },
                        "relation_hints": {},
                    }
                ]
            }
            self._json(
                200,
                {
                    "choices": [
                        {
                            "finish_reason": "tool_calls",
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "career-suggestion-1",
                                        "type": "function",
                                        "function": {
                                            "name": "propose_career_suggestions",
                                            "arguments": json.dumps(
                                                arguments, ensure_ascii=False
                                            ),
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                },
            )
            return

        if payload.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            for token in ("Docker ", "mock ", "reply"):
                chunk = {"choices": [{"delta": {"content": token}}]}
                line = f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                self.wfile.write(line)
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return

        self._json(
            200,
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Docker mock reply"},
                    }
                ]
            },
        )


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
