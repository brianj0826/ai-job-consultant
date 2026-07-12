import importlib
from contextlib import nullcontext
from io import BytesIO
import sys
import types

import pytest
from pypdf import PdfWriter
from starlette.datastructures import UploadFile

from backend.services import resource_limits


def test_upload_copy_stops_at_configured_byte_limit(monkeypatch):
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "1024")
    target = BytesIO()

    with pytest.raises(resource_limits.ResourceLimitExceeded, match="上传大小"):
        resource_limits.copy_upload_with_limit(BytesIO(b"x" * 1025), target)

    assert target.getvalue() == b""


def test_pdf_page_limit_is_enforced_before_text_extraction(monkeypatch, tmp_path):
    path = tmp_path / "resume.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as output:
        writer.write(output)

    monkeypatch.setenv("RAG_MAX_PDF_PAGES", "1")
    with pytest.raises(resource_limits.ResourceLimitExceeded, match="PDF 页数"):
        resource_limits._validate_pdf_page_count(str(path))


def test_extracted_text_and_chunk_limits_are_enforced(monkeypatch):
    rag_stub = types.ModuleType("backend.services.rag")
    rag_stub.DEFAULT_CHUNK_SIZE = 500
    rag_stub.DEFAULT_CHUNK_OVERLAP = 100
    rag_stub.extract_text = lambda *args: "x" * 1200
    monkeypatch.setitem(sys.modules, "backend.services.rag", rag_stub)
    monkeypatch.setenv("RAG_MAX_TEXT_CHARS", "1000")

    with pytest.raises(resource_limits.ResourceLimitExceeded, match="文本超过"):
        resource_limits.validate_document_limits("unused.txt", ".txt")

    rag_stub.extract_text = lambda *args: "word " * 300
    monkeypatch.setenv("RAG_MAX_TEXT_CHARS", "5000")
    monkeypatch.setenv("RAG_MAX_CHUNKS", "2")
    with pytest.raises(resource_limits.ResourceLimitExceeded, match="分块超过"):
        resource_limits.validate_document_limits("unused.txt", ".txt")


def _load_documents_router(monkeypatch):
    rag_stub = types.ModuleType("backend.services.rag")
    rag_stub.ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}
    rag_stub.get_collection = lambda *args: None
    rag_stub.index_document = lambda *args: None
    rag_stub.rag_disabled = lambda: False
    monkeypatch.setitem(sys.modules, "backend.services.rag", rag_stub)
    sys.modules.pop("backend.routers.documents", None)
    return importlib.import_module("backend.routers.documents")


def test_upload_endpoint_maps_resource_limit_to_413(monkeypatch):
    documents = _load_documents_router(monkeypatch)
    monkeypatch.setattr(documents, "career_data_guard", lambda *args: nullcontext())
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "1024")
    upload = UploadFile(filename="resume.txt", file=BytesIO(b"x" * 1025))

    with pytest.raises(documents.HTTPException) as caught:
        documents.upload_document(upload, {"id": 7})

    assert caught.value.status_code == 413
    assert "上传大小" in caught.value.detail


def test_fetch_url_has_csrf_dependency_and_feature_rate_limit(monkeypatch):
    documents = _load_documents_router(monkeypatch)
    route = next(route for route in documents.router.routes if route.path == "/fetch-url")
    dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
    assert documents.require_business_csrf in dependency_calls

    monkeypatch.setattr(documents, "current_user_id", lambda user: 7)
    monkeypatch.setattr(documents, "check_request_limit", lambda *args: (False, 19))
    monkeypatch.setattr(
        documents,
        "crawl_fetch",
        lambda url: (_ for _ in ()).throw(AssertionError("crawler must not run")),
    )
    with pytest.raises(documents.HTTPException) as caught:
        documents.fetch_url_content(documents.FetchUrlRequest(url="https://example.com"), {"id": 7})

    assert caught.value.status_code == 429
    assert caught.value.headers == {"Retry-After": "19"}
