import sys
import types

import pytest


def _stub_module(name, **attributes):
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


def _prepare_route(monkeypatch):
    monkeypatch.setattr(chat_router, "current_user_id", lambda user: 7)
    monkeypatch.setattr(chat_router, "require_owned_session", lambda *args: None)
    monkeypatch.setattr(chat_router, "check_rate_limit", lambda *args: (True, 0))
    monkeypatch.setattr(chat_router, "sanitize_input", lambda value: value.strip())
    monkeypatch.setattr(chat_router, "moderate_text", lambda *args: (True, ""))
    monkeypatch.setattr(chat_router, "_reserve_request", lambda *args: (None, "owner-token"))


@pytest.mark.parametrize("endpoint", [chat_router.chat, chat_router.chat_stream])
def test_chat_rate_limit_includes_retry_after_header(monkeypatch, endpoint):
    _prepare_route(monkeypatch)
    monkeypatch.setattr(chat_router, "check_rate_limit", lambda *args: (False, 17))

    with pytest.raises(chat_router.HTTPException) as caught:
        endpoint(
            chat_router.ChatRequest(message="hello", session_id=3),
            {"id": 7},
        )

    assert caught.value.status_code == 429
    assert caught.value.headers == {"Retry-After": "17"}


def test_nonstream_preprocessing_failure_releases_reservation(monkeypatch):
    _prepare_route(monkeypatch)
    released = []
    monkeypatch.setattr(
        chat_router,
        "_complete_nonstream_chat",
        lambda *args: (_ for _ in ()).throw(RuntimeError("model failed")),
    )
    monkeypatch.setattr(chat_router, "_release_request", lambda *args: released.append(args))
    with pytest.raises(RuntimeError, match="model failed"):
        chat_router.chat(
            chat_router.ChatRequest(
                message="hello",
                session_id=3,
                client_request_id="request-1",
            ),
            {"id": 7},
        )
    assert released == [(7, 3, "request-1", "owner-token")]


def test_stream_preprocessing_failure_releases_reservation(monkeypatch):
    _prepare_route(monkeypatch)
    released = []
    monkeypatch.setattr(
        chat_router,
        "_prepare_stream_chat",
        lambda *args: (_ for _ in ()).throw(RuntimeError("rag failed")),
    )
    monkeypatch.setattr(chat_router, "_release_request", lambda *args: released.append(args))
    with pytest.raises(RuntimeError, match="rag failed"):
        chat_router.chat_stream(
            chat_router.ChatRequest(
                message="hello",
                session_id=3,
                client_request_id="request-2",
            ),
            {"id": 7},
        )
    assert released == [(7, 3, "request-2", "owner-token")]


def test_stream_model_failure_before_output_releases_reservation(monkeypatch):
    released = []

    def broken_stream(messages):
        raise RuntimeError("stream failed")
        yield  # pragma: no cover

    monkeypatch.setattr(chat_router, "get_ai_response_stream", broken_stream)
    monkeypatch.setattr(chat_router, "_release_request", lambda *args: released.append(args))
    events = list(chat_router._stream_events([], [], 7, 3, "request-3", "owner-token"))
    assert released == [(7, 3, "request-3", "owner-token")]
    assert "stream failed" in events[-1]


def test_stream_save_failure_after_partial_output_releases_reservation(monkeypatch):
    released = []

    def partial_stream(messages):
        yield "partial"
        raise RuntimeError("upstream failed")

    monkeypatch.setattr(chat_router, "get_ai_response_stream", partial_stream)
    monkeypatch.setattr(
        chat_router,
        "_complete_request",
        lambda *args: (_ for _ in ()).throw(RuntimeError("database failed")),
    )
    monkeypatch.setattr(chat_router, "_release_request", lambda *args: released.append(args))
    events = list(chat_router._stream_events([], [], 7, 3, "request-4", "owner-token"))
    assert released == [(7, 3, "request-4", "owner-token")]
    assert "database failed" in events[-1]


def test_stream_client_disconnect_releases_incomplete_reservation(monkeypatch):
    released = []
    monkeypatch.setattr(chat_router, "get_ai_response_stream", lambda messages: iter(["one", "two"]))
    monkeypatch.setattr(chat_router, "_release_request", lambda *args: released.append(args))
    events = chat_router._stream_events([], [], 7, 3, "request-5", "owner-token")
    assert "one" in next(events)
    events.close()
    assert released == [(7, 3, "request-5", "owner-token")]
