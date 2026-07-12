"""Runtime-enforced resource limits for user-supplied documents."""
from __future__ import annotations

import math
import os
from typing import BinaryIO


class DocumentValidationError(ValueError):
    """The uploaded bytes do not form a usable supported document."""


class ResourceLimitExceeded(ValueError):
    """The uploaded document exceeds a configured resource budget."""


def _bounded_int_env(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def upload_max_bytes() -> int:
    return _bounded_int_env(
        "UPLOAD_MAX_BYTES",
        10 * 1024 * 1024,
        1024,
        100 * 1024 * 1024,
    )


def rag_max_pdf_pages() -> int:
    return _bounded_int_env("RAG_MAX_PDF_PAGES", 100, 1, 5_000)


def rag_max_text_chars() -> int:
    return _bounded_int_env("RAG_MAX_TEXT_CHARS", 200_000, 1_000, 5_000_000)


def rag_max_chunks() -> int:
    return _bounded_int_env("RAG_MAX_CHUNKS", 500, 1, 10_000)


def copy_upload_with_limit(source: BinaryIO, target: BinaryIO) -> int:
    """Copy an upload without ever accepting more than the configured bytes."""
    maximum = upload_max_bytes()
    total = 0
    while True:
        chunk = source.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > maximum:
            raise ResourceLimitExceeded(
                f"文件超过上传大小限制（最大 {maximum} 字节）"
            )
        target.write(chunk)
    return total


def _validate_pdf_page_count(file_path: str) -> None:
    from pypdf import PdfReader

    try:
        reader = PdfReader(file_path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise DocumentValidationError("不支持需要密码的 PDF 文件")
        page_count = len(reader.pages)
    except DocumentValidationError:
        raise
    except Exception as exc:
        raise DocumentValidationError("PDF 文件无效或无法读取") from exc

    maximum = rag_max_pdf_pages()
    if page_count > maximum:
        raise ResourceLimitExceeded(f"PDF 页数超过限制（最大 {maximum} 页）")


def _estimated_chunk_count(text_length: int, chunk_size: int, overlap: int) -> int:
    step = chunk_size - overlap
    if chunk_size <= 0 or overlap < 0 or step <= 0:
        raise DocumentValidationError("RAG 分块配置无效")
    if text_length <= 0:
        return 0
    # Match rag.split_text_into_chunks exactly: each iteration advances by
    # ``chunk_size - overlap`` while ``start < len(text)``.
    return math.ceil(text_length / step)


def validate_document_limits(file_path: str, file_type: str) -> dict[str, int]:
    """Validate page, extracted-text, and future embedding chunk budgets.

    Extraction is intentionally performed before indexing so an oversized
    document cannot partially mutate the user's vector collection.
    """
    if file_type == ".pdf":
        _validate_pdf_page_count(file_path)

    from backend.services.preprocessing import preprocess
    from backend.services.rag import (
        DEFAULT_CHUNK_OVERLAP,
        DEFAULT_CHUNK_SIZE,
        extract_text,
    )

    try:
        raw_text = extract_text(file_path, file_type)
    except Exception as exc:
        raise DocumentValidationError("文档无效或无法提取文本") from exc

    maximum_characters = rag_max_text_chars()
    if len(raw_text) > maximum_characters:
        raise ResourceLimitExceeded(
            f"文档文本超过限制（最大 {maximum_characters} 个字符）"
        )

    clean_text = preprocess(raw_text)
    if not clean_text.strip():
        raise DocumentValidationError("文档中没有可提取的有效文本")
    if len(clean_text) > maximum_characters:
        raise ResourceLimitExceeded(
            f"文档文本超过限制（最大 {maximum_characters} 个字符）"
        )

    chunk_count = _estimated_chunk_count(
        len(clean_text),
        DEFAULT_CHUNK_SIZE,
        DEFAULT_CHUNK_OVERLAP,
    )
    maximum_chunks = rag_max_chunks()
    if chunk_count > maximum_chunks:
        raise ResourceLimitExceeded(
            f"文档分块超过限制（最大 {maximum_chunks} 块）"
        )
    return {"text_chars": len(clean_text), "chunks": chunk_count}
