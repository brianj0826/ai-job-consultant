import importlib.util
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[1] / "services" / "deepseek_api.py"
_SPEC = importlib.util.spec_from_file_location("deepseek_api_model_config_test", _MODULE_PATH)
deepseek_api = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(deepseek_api)


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}

    def iter_lines(self, decode_unicode=True):
        yield 'data: {"choices":[{"delta":{"content":"token"}}]}'
        yield "data: [DONE]"


def test_all_deepseek_call_paths_use_configured_model(monkeypatch):
    payloads = []

    def post(*args, **kwargs):
        payloads.append(kwargs["json"])
        return _Response()

    monkeypatch.setattr(deepseek_api, "DEEPSEEK_MODEL", "configured-model")
    monkeypatch.setattr(deepseek_api.requests, "post", post)

    assert deepseek_api.get_ai_response([{"role": "user", "content": "hi"}]) == "ok"
    deepseek_api.get_ai_response_with_tools(
        [{"role": "user", "content": "hi"}],
        tools=[{"type": "function"}],
        tool_choice="required",
        max_retries=0,
    )
    assert list(deepseek_api.get_ai_response_stream([{"role": "user", "content": "hi"}])) == [
        "token"
    ]

    assert [payload["model"] for payload in payloads] == [
        "configured-model",
        "configured-model",
        "configured-model",
    ]
    assert payloads[1]["tool_choice"] == "required"


def test_default_model_is_v4_flash():
    assert deepseek_api.DEFAULT_DEEPSEEK_MODEL == "deepseek-v4-flash"
