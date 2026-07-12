"""Small, bounded web-page fetcher used by document import and AI tools.

The crawler deliberately does not behave like a general-purpose HTTP proxy.
Every request target (including redirect targets) must resolve exclusively to
public IP addresses and responses are accepted only when they are bounded text
or HTML documents.
"""
from __future__ import annotations

from html.parser import HTMLParser
import ipaddress
import logging
import os
import re
import socket
from urllib.parse import urljoin, urlsplit

import requests


logger = logging.getLogger("aiagent.crawler")

_ALLOWED_CONTENT_TYPES = {
    "application/xhtml+xml",
    "text/html",
    "text/plain",
}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class CrawlerSecurityError(ValueError):
    """Raised when a URL or response violates the crawler security policy."""


def _bounded_int_env(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    """Read an integer setting while retaining a safe bound on bad config."""
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def crawler_max_response_bytes() -> int:
    return _bounded_int_env(
        "CRAWLER_MAX_RESPONSE_BYTES",
        2 * 1024 * 1024,
        1024,
        25 * 1024 * 1024,
    )


def crawler_max_redirects() -> int:
    return _bounded_int_env("CRAWLER_MAX_REDIRECTS", 5, 0, 10)


def crawler_max_text_chars() -> int:
    return _bounded_int_env("CRAWLER_MAX_TEXT_CHARS", 20_000, 1_000, 1_000_000)


def _is_forbidden_address(address: ipaddress._BaseAddress) -> bool:
    """Return true for every address class that must never be fetched."""
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or not address.is_global
    )


def validate_public_url(url: str) -> tuple[str, frozenset[ipaddress._BaseAddress]]:
    """Validate a URL and resolve *all* of its addresses before a request.

    Returning the resolved addresses also lets the response peer be compared
    with the preflight resolution when the HTTP client exposes its socket.
    """
    candidate = (url or "").strip()
    if not candidate:
        raise CrawlerSecurityError("网址不能为空")
    if "\\" in candidate or any(character.isspace() for character in candidate):
        raise CrawlerSecurityError("网址包含不允许的字符")

    try:
        parsed = urlsplit(candidate)
    except ValueError as exc:
        raise CrawlerSecurityError("网址格式无效") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise CrawlerSecurityError("仅支持 http 或 https 网址")
    if parsed.username is not None or parsed.password is not None:
        raise CrawlerSecurityError("网址中不能包含用户名或密码")
    if not parsed.hostname:
        raise CrawlerSecurityError("网址缺少有效主机名")

    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise CrawlerSecurityError("网址端口无效") from exc
    port = parsed_port if parsed_port is not None else (
        443 if parsed.scheme.lower() == "https" else 80
    )
    if not 1 <= port <= 65_535:
        raise CrawlerSecurityError("网址端口无效")

    try:
        resolved = socket.getaddrinfo(
            parsed.hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except (OSError, UnicodeError) as exc:
        raise CrawlerSecurityError("无法解析目标网站地址") from exc

    addresses: set[ipaddress._BaseAddress] = set()
    for result in resolved:
        raw_address = result[4][0].split("%", 1)[0]
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise CrawlerSecurityError("目标网站解析结果无效") from exc
        if _is_forbidden_address(address):
            raise CrawlerSecurityError("禁止访问本机、内网或保留网络地址")
        addresses.add(address)

    if not addresses:
        raise CrawlerSecurityError("目标网站没有可用的公开地址")
    return candidate, frozenset(addresses)


def _response_peer_address(response: requests.Response):
    """Best-effort extraction of the connected peer from urllib3/requests."""
    connection = getattr(response.raw, "_connection", None)
    connection = connection or getattr(response.raw, "connection", None)
    sock = getattr(connection, "sock", None)
    if sock is None:
        return None
    try:
        raw_address = sock.getpeername()[0].split("%", 1)[0]
        return ipaddress.ip_address(raw_address)
    except (AttributeError, OSError, ValueError):
        return None


def _verify_response_peer(
    response: requests.Response,
    resolved_addresses: frozenset[ipaddress._BaseAddress],
) -> None:
    peer = _response_peer_address(response)
    if peer is None:
        return
    if _is_forbidden_address(peer) or peer not in resolved_addresses:
        raise CrawlerSecurityError("目标网站连接地址与安全校验结果不一致")


def _read_bounded_response(response: requests.Response) -> bytes:
    maximum = crawler_max_response_bytes()
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            announced_size = int(content_length)
        except ValueError as exc:
            raise CrawlerSecurityError("目标网站返回了无效的内容长度") from exc
        if announced_size < 0 or announced_size > maximum:
            raise CrawlerSecurityError(f"网页响应超过大小限制（最大 {maximum} 字节）")

    body = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        body.extend(chunk)
        if len(body) > maximum:
            raise CrawlerSecurityError(f"网页响应超过大小限制（最大 {maximum} 字节）")
    return bytes(body)


class TextExtractor(HTMLParser):
    """Extract visible-ish text while skipping non-content elements."""

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self.skip_tags = {"script", "style", "noscript", "iframe", "svg", "nav", "footer"}
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.skip_depth:
            self.skip_depth -= 1
        if not self.skip_depth and tag in {
            "p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"
        }:
            self.text_parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        text = data.strip()
        if text:
            self.text_parts.append(text + " ")


def extract_text_from_html(html: str) -> str:
    extractor = TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    raw = "".join(extractor.text_parts)
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    raw = re.sub(r" \n", "\n", raw)
    return raw.strip()


def extract_title_from_html(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def _decode_response(response: requests.Response, body: bytes) -> str:
    encoding = requests.utils.get_encoding_from_headers(response.headers) or "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def fetch_url(url: str, timeout: int = 15) -> dict:
    """Fetch a public HTML/text page under strict SSRF and size limits."""
    session = requests.Session()
    # Environment proxy variables can redirect a validated request through an
    # unintended network path, so this narrowly scoped crawler ignores them.
    session.trust_env = False
    headers = {
        "User-Agent": "AI-Job-Consultant/1.0 (+bounded-public-web-fetcher)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
    }
    current_url = url

    try:
        for redirect_count in range(crawler_max_redirects() + 1):
            current_url, resolved_addresses = validate_public_url(current_url)
            response = session.get(
                current_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
            try:
                _verify_response_peer(response, resolved_addresses)
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("Location", "").strip()
                    if not location:
                        raise CrawlerSecurityError("目标网站返回了无效重定向")
                    if redirect_count >= crawler_max_redirects():
                        raise CrawlerSecurityError("网页重定向次数超过限制")
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()
                content_type = (
                    response.headers.get("Content-Type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                if content_type not in _ALLOWED_CONTENT_TYPES:
                    raise CrawlerSecurityError("仅允许抓取 HTML 或纯文本网页")
                body = _read_bounded_response(response)
                html = _decode_response(response, body)
            finally:
                response.close()
            break
        else:  # pragma: no cover - loop has an explicit redirect guard
            raise CrawlerSecurityError("网页重定向次数超过限制")

        title = extract_title_from_html(html)
        text = extract_text_from_html(html)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()[:crawler_max_text_chars()]
        if not text:
            return {"success": False, "title": "", "text": "", "error": "网页内容为空"}
        return {"success": True, "title": title, "text": text, "error": ""}
    except requests.exceptions.Timeout:
        return {"success": False, "title": "", "text": "", "error": "请求超时"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "title": "", "text": "", "error": "无法连接到目标网站"}
    except (CrawlerSecurityError, requests.exceptions.RequestException) as exc:
        return {"success": False, "title": "", "text": "", "error": str(exc)}
    except Exception:
        logger.exception("Unexpected crawler failure")
        return {"success": False, "title": "", "text": "", "error": "网页抓取失败"}
    finally:
        session.close()


def fetch_and_index(url: str, user_id: int) -> dict:
    """Fetch a public web page and append its chunks to a user's collection."""
    from backend.services.preprocessing import preprocess
    from backend.services.rag import get_collection, split_text_into_chunks

    result = fetch_url(url)
    if not result["success"]:
        return {"success": False, "title": "", "chunks": 0, "error": result["error"]}

    clean = preprocess(result["text"])
    if len(clean.strip()) < 50:
        return {
            "success": False,
            "title": result["title"],
            "chunks": 0,
            "error": "网页有效内容太少",
        }
    chunks = split_text_into_chunks(clean)
    if not chunks:
        return {
            "success": False,
            "title": result["title"],
            "chunks": 0,
            "error": "文本分块失败",
        }

    collection = get_collection(user_id)
    import hashlib

    prefix = "web_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    ids = [f"{prefix}_{index}" for index in range(len(chunks))]
    metadatas = [
        {
            "source": url,
            "title": result["title"],
            "type": "web",
            "index": index,
        }
        for index in range(len(chunks))
    ]
    collection.upsert(documents=chunks, ids=ids, metadatas=metadatas)
    logger.info("Web page imported into user %s knowledge base (%s chunks)", user_id, len(chunks))
    return {"success": True, "title": result["title"], "chunks": len(chunks), "error": ""}
