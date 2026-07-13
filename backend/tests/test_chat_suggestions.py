import asyncio
from contextlib import contextmanager
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
    "backend.services.tools",
    TOOLS=[],
    execute_tool=lambda *args, **kwargs: "",
)

from backend.routers import chat as chat_router


def _payloads(events):
    return [json.loads(event.removeprefix("data: ").strip()) for event in events]


def test_suggestion_completion_uses_career_guard_before_chat_transaction(monkeypatch):
    events = []

    @contextmanager
    def guard(user_id):
        events.append(("guard-enter", user_id))
        yield
        events.append(("guard-exit", user_id))

    monkeypatch.setattr(chat_router.career_service, "career_data_guard", guard)
    monkeypatch.setattr(
        chat_router,
        "complete_chat_request",
        lambda *args, **kwargs: events.append(("persist", kwargs["suggestions"])) or 42,
    )

    drafts = [{"resource_type": "skills", "payload": {"skill": "Redis"}}]
    assert chat_router._complete_request(7, 3, "request-1", "owner-1", "answer", drafts) == 42
    assert events == [
        ("guard-enter", 7),
        ("persist", drafts),
        ("guard-exit", 7),
    ]


def test_busy_career_guard_drops_optional_drafts_but_completes_chat(monkeypatch):
    @contextmanager
    def busy_guard(user_id):
        raise chat_router.career_service.CareerConflictError("busy")
        yield

    persisted = []
    monkeypatch.setattr(chat_router.career_service, "career_data_guard", busy_guard)
    monkeypatch.setattr(
        chat_router,
        "complete_chat_request",
        lambda *args, **kwargs: persisted.append(kwargs["suggestions"]) or 42,
    )

    drafts = [{"resource_type": "skills", "payload": {"skill": "Redis"}}]
    assert chat_router._complete_request(7, 3, "request-1", "owner-1", "answer", drafts) == 42
    assert persisted == [[]]


def test_stream_done_contains_persisted_suggestions(monkeypatch):
    drafts = [
        {
            "resource_type": "skills",
            "title": "Add Redis plan",
            "reason": "Target role requires caching",
            "payload": {"skill": "Redis", "status": "planned", "progress": 0},
            "relation_hints": {},
        }
    ]
    public = [{"id": 91, **drafts[0], "status": "pending", "revision": 1}]
    persisted = []
    monkeypatch.setattr(chat_router, "get_ai_response_stream", lambda messages: iter(["answer"]))
    monkeypatch.setattr(chat_router, "moderate_text", lambda *args: (True, ""))
    monkeypatch.setattr(chat_router, "extract_career_suggestions", lambda *args, **kwargs: drafts)
    monkeypatch.setattr(
        chat_router,
        "_complete_request",
        lambda *args: persisted.append(args[5]) or 42,
    )
    monkeypatch.setattr(chat_router, "_message_suggestions", lambda *args: public)

    payloads = _payloads(
        list(
            chat_router._stream_events(
                [{"role": "user", "content": "请添加 Redis 学习计划"}],
                [],
                7,
                3,
                None,
                None,
            )
        )
    )

    assert payloads[0] == {"token": "answer"}
    assert payloads[-1]["suggestions"] == public
    assert persisted == [drafts]


def test_extractor_exception_does_not_change_successful_stream(monkeypatch):
    monkeypatch.setattr(chat_router, "get_ai_response_stream", lambda messages: iter(["answer"]))
    monkeypatch.setattr(chat_router, "moderate_text", lambda *args: (True, ""))
    monkeypatch.setattr(
        chat_router,
        "extract_career_suggestions",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("slow")),
    )
    monkeypatch.setattr(chat_router, "_complete_request", lambda *args: 42)
    monkeypatch.setattr(chat_router, "_message_suggestions", lambda *args: [])

    payloads = _payloads(
        list(
            chat_router._stream_events(
                [{"role": "user", "content": "hello"}], [], 7, 3, None, None
            )
        )
    )

    assert payloads[0] == {"token": "answer"}
    assert payloads[-1]["done"] is True
    assert payloads[-1]["suggestions"] == []


def test_nonstream_replay_reuses_saved_suggestion_ids_without_extraction(monkeypatch):
    saved = [{"id": 91, "resource_type": "skills", "status": "pending", "revision": 1}]
    monkeypatch.setattr(chat_router, "current_user_id", lambda user: 7)
    monkeypatch.setattr(chat_router, "require_owned_session", lambda *args: None)
    monkeypatch.setattr(chat_router, "check_rate_limit", lambda *args: (True, 0))
    monkeypatch.setattr(chat_router, "sanitize_input", lambda value: value)
    monkeypatch.setattr(chat_router, "moderate_text", lambda *args: (True, ""))
    monkeypatch.setattr(
        chat_router,
        "_reserve_request",
        lambda *args: ({"id": 42, "content": "prior answer"}, None),
    )
    monkeypatch.setattr(chat_router, "_message_suggestions", lambda *args: saved)
    monkeypatch.setattr(
        chat_router,
        "extract_career_suggestions",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("re-extracted")),
    )

    result = chat_router.chat(
        chat_router.ChatRequest(
            message="请添加 Redis 学习计划",
            session_id=3,
            client_request_id="same-request",
        ),
        {"id": 7},
    )

    assert result["replayed"] is True
    assert result["msg_id"] == 42
    assert result["suggestions"] == saved


def test_stream_replay_returns_same_persisted_suggestions(monkeypatch):
    saved = [{"id": 91, "resource_type": "skills", "status": "pending", "revision": 1}]
    monkeypatch.setattr(chat_router, "current_user_id", lambda user: 7)
    monkeypatch.setattr(chat_router, "require_owned_session", lambda *args: None)
    monkeypatch.setattr(chat_router, "check_rate_limit", lambda *args: (True, 0))
    monkeypatch.setattr(chat_router, "sanitize_input", lambda value: value)
    monkeypatch.setattr(chat_router, "moderate_text", lambda *args: (True, ""))
    monkeypatch.setattr(
        chat_router,
        "_reserve_request",
        lambda *args: ({"id": 42, "content": "prior answer"}, None),
    )
    monkeypatch.setattr(chat_router, "_message_suggestions", lambda *args: saved)

    response = chat_router.chat_stream(
        chat_router.ChatRequest(
            message="请添加 Redis 学习计划",
            session_id=3,
            client_request_id="same-request",
        ),
        {"id": 7},
    )
    async def collect():
        return [chunk async for chunk in response.body_iterator]

    payloads = _payloads(asyncio.run(collect()))

    assert payloads[-1]["replayed"] is True
    assert payloads[-1]["suggestions"] == saved
