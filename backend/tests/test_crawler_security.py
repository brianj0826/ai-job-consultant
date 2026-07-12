import socket
from types import SimpleNamespace

import pytest

from backend.services import crawler


def _dns_result(address: str):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sockaddr = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
    return (family, socket.SOCK_STREAM, 6, "", sockaddr)


def test_url_policy_requires_http_and_rejects_credentials():
    with pytest.raises(crawler.CrawlerSecurityError, match="仅支持"):
        crawler.validate_public_url("example.com/job")
    with pytest.raises(crawler.CrawlerSecurityError, match="用户名或密码"):
        crawler.validate_public_url("https://user:secret@example.com/job")
    with pytest.raises(crawler.CrawlerSecurityError, match="端口无效"):
        crawler.validate_public_url("https://example.com:0/job")


def test_url_policy_rejects_when_any_dns_answer_is_private(monkeypatch):
    monkeypatch.setattr(
        crawler.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            _dns_result("93.184.216.34"),
            _dns_result("10.0.0.8"),
        ],
    )
    with pytest.raises(crawler.CrawlerSecurityError, match="内网"):
        crawler.validate_public_url("https://example.com/job")


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "169.254.169.254", "0.0.0.0", "224.0.0.1", "::1", "fe80::1"],
)
def test_url_policy_rejects_non_public_address_classes(monkeypatch, address):
    monkeypatch.setattr(
        crawler.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [_dns_result(address)],
    )
    with pytest.raises(crawler.CrawlerSecurityError, match="禁止访问"):
        crawler.validate_public_url("https://example.com/job")


class _FakeResponse:
    def __init__(self, status, headers=None, chunks=()):
        self.status_code = status
        self.headers = headers or {}
        self._chunks = list(chunks)
        self.raw = SimpleNamespace(_connection=None)
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise crawler.requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        yield from self._chunks

    def close(self):
        self.closed = True


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.trust_env = True

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)

    def close(self):
        pass


def test_redirect_target_is_revalidated_before_second_request(monkeypatch):
    response = _FakeResponse(302, {"Location": "http://metadata.local/latest"})
    session = _FakeSession([response])
    monkeypatch.setattr(crawler.requests, "Session", lambda: session)

    def resolve(host, *args, **kwargs):
        address = "93.184.216.34" if host == "public.example" else "169.254.169.254"
        return [_dns_result(address)]

    monkeypatch.setattr(crawler.socket, "getaddrinfo", resolve)
    result = crawler.fetch_url("https://public.example/job")

    assert result["success"] is False
    assert "禁止访问" in result["error"]
    assert len(session.calls) == 1
    assert response.closed is True
    assert session.trust_env is False


def test_response_requires_supported_content_type(monkeypatch):
    response = _FakeResponse(200, {"Content-Type": "application/octet-stream"}, [b"data"])
    session = _FakeSession([response])
    monkeypatch.setattr(crawler.requests, "Session", lambda: session)
    monkeypatch.setattr(
        crawler.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [_dns_result("93.184.216.34")],
    )

    result = crawler.fetch_url("https://example.com/file")

    assert result["success"] is False
    assert "HTML" in result["error"]


def test_streamed_response_cannot_exceed_byte_limit(monkeypatch):
    monkeypatch.setenv("CRAWLER_MAX_RESPONSE_BYTES", "1024")
    response = _FakeResponse(200, {"Content-Type": "text/html"}, [b"a" * 700, b"b" * 400])
    session = _FakeSession([response])
    monkeypatch.setattr(crawler.requests, "Session", lambda: session)
    monkeypatch.setattr(
        crawler.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [_dns_result("93.184.216.34")],
    )

    result = crawler.fetch_url("https://example.com/job")

    assert result["success"] is False
    assert "大小限制" in result["error"]


def test_safe_html_response_is_extracted(monkeypatch):
    html = b"<html><head><title>Engineer</title></head><body><p>Build useful systems</p></body></html>"
    response = _FakeResponse(
        200,
        {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(html))},
        [html],
    )
    session = _FakeSession([response])
    monkeypatch.setattr(crawler.requests, "Session", lambda: session)
    monkeypatch.setattr(
        crawler.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [_dns_result("93.184.216.34")],
    )

    result = crawler.fetch_url("https://example.com/job")

    assert result == {
        "success": True,
        "title": "Engineer",
        "text": "Engineer Build useful systems",
        "error": "",
    }
