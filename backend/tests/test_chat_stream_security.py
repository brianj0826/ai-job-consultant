import json
import sys
import types


def _stub_module(name, **attributes):
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules[name] = module


_stub_module(
    "backend.services.rag",
    search_document=lambda *args, **kwargs: None,
    build_rag_context=lambda *args, **kwargs: ("", []),
)
_stub_module(
    "backend.services.deepseek_api",
    get_ai_response=lambda *args, **kwargs: None,
    get_ai_response_with_tools=lambda *args, **kwargs: None,
    get_ai_response_stream=lambda *args, **kwargs: iter(()),
)
_stub_module(
    "backend.services.memory",
    trim_history=lambda history, max_turns: history,
    generate_summary=lambda history: "",
)
_stub_module(
    "backend.services.tools",
    TOOLS=[],
    execute_tool=lambda *args, **kwargs: "",
)

from backend.routers import chat as chat_router


def _payloads(events):
    return [json.loads(event.removeprefix("data: ").strip()) for event in events]


def test_stream_buffers_complete_response_before_moderation_and_emission(monkeypatch):
    produced = []
    saved = []

    def model_stream(messages):
        produced.append("first")
        yield "first"
        produced.append("second")
        yield " second"

    def moderate(text, user_id):
        assert produced == ["first", "second"]
        assert text == "first second"
        return True, ""

    monkeypatch.setattr(chat_router, "get_ai_response_stream", model_stream)
    monkeypatch.setattr(chat_router, "moderate_text", moderate)
    monkeypatch.setattr(chat_router, "extract_career_suggestions", lambda *args, **kwargs: [])
    monkeypatch.setattr(chat_router, "_message_suggestions", lambda *args: [])
    monkeypatch.setattr(
        chat_router,
        "_complete_request",
        lambda *args: saved.append(args[4]) or 42,
    )

    payloads = _payloads(list(chat_router._stream_events([], [], 7, 3, None, None)))

    assert [payload["token"] for payload in payloads[:-1]] == ["first", " second"]
    assert payloads[-1]["done"] is True
    assert saved == ["first second"]


def test_unsafe_stream_content_is_never_emitted_or_persisted(monkeypatch):
    saved = []
    monkeypatch.setattr(
        chat_router,
        "get_ai_response_stream",
        lambda messages: iter(["unsafe ", "payload"]),
    )
    monkeypatch.setattr(
        chat_router,
        "moderate_text",
        lambda text, user_id: (False, "blocked-category"),
    )
    monkeypatch.setattr(
        chat_router,
        "extract_career_suggestions",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("extractor called")),
    )
    monkeypatch.setattr(chat_router, "_message_suggestions", lambda *args: [])
    monkeypatch.setattr(
        chat_router,
        "_complete_request",
        lambda *args: saved.append(args[4]) or 43,
    )

    payloads = _payloads(list(chat_router._stream_events([], [], 7, 3, None, None)))
    emitted_text = "".join(payload["token"] for payload in payloads if "token" in payload)

    assert "unsafe payload" not in emitted_text
    assert "安全策略拦截" in emitted_text
    assert saved == [emitted_text]


def test_unsafe_partial_response_is_audited_after_upstream_failure(monkeypatch):
    saved = []

    def interrupted_stream(messages):
        yield "unsafe partial"
        raise RuntimeError("upstream closed")

    monkeypatch.setattr(chat_router, "get_ai_response_stream", interrupted_stream)
    monkeypatch.setattr(chat_router, "moderate_text", lambda *args: (False, "blocked"))
    monkeypatch.setattr(
        chat_router,
        "extract_career_suggestions",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("extractor called")),
    )
    monkeypatch.setattr(chat_router, "_message_suggestions", lambda *args: [])
    monkeypatch.setattr(
        chat_router,
        "_complete_request",
        lambda *args: saved.append(args[-1]) or 44,
    )

    payloads = _payloads(list(chat_router._stream_events([], [], 7, 3, None, None)))
    emitted_text = "".join(payload["token"] for payload in payloads if "token" in payload)

    assert "unsafe partial" not in emitted_text
    assert "安全策略拦截" in emitted_text
    assert saved == [emitted_text]
