import os
import shutil
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.services.access import current_user_id
from backend.services.auth import require_business_csrf, require_current_user
from backend.services.crawler import fetch_and_index, fetch_url as crawl_fetch
from backend.services.rag import ALLOWED_EXTENSIONS, get_collection, index_document, rag_disabled


router = APIRouter()


class ImportUrlRequest(BaseModel):
    url: str


@router.post("/upload", dependencies=[Depends(require_business_csrf)])
def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_current_user),
):
    """Index a document in the authenticated user's private collection."""
    if rag_disabled():
        raise HTTPException(status_code=503, detail="Document indexing is disabled")
    filename = file.filename or "upload"
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}，支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        index_document(temp_path, current_user_id(current_user), filename, ext)
        return {"message": f"文档 {filename} 已成功导入知识库"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文档处理失败: {exc}") from exc
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@router.get("/status")
def document_status(current_user: dict = Depends(require_current_user)):
    """Return sources and counts from the current user's knowledge base."""
    if rag_disabled():
        return {"doc_count": 0, "sources": [], "disabled": True}
    collection = get_collection(current_user_id(current_user))
    count = collection.count()
    sources = []
    if count > 0:
        try:
            all_data = collection.get(limit=min(count, 500))
            seen = set()
            for metadata in all_data.get("metadatas", []):
                source = metadata.get("source", "")
                title = metadata.get("title", "")
                source_type = metadata.get("type", "file")
                key = source or title
                if key and key not in seen:
                    seen.add(key)
                    sources.append(
                        {
                            "source": source,
                            "title": title
                            or (os.path.basename(source) if source else "未知"),
                            "type": source_type,
                        }
                    )
        except Exception:
            # An unreadable index should not turn a status request into an
            # unrelated server error; the index operation will surface detail.
            pass

    return {"doc_count": count, "sources": sources}


@router.post("/import-url", dependencies=[Depends(require_business_csrf)])
def import_url(
    req: ImportUrlRequest,
    current_user: dict = Depends(require_current_user),
):
    """Fetch and index a web page for the authenticated user."""
    if rag_disabled():
        raise HTTPException(status_code=503, detail="Document indexing is disabled")
    result = fetch_and_index(req.url, current_user_id(current_user))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        "message": f"已导入 {result['title']}",
        "title": result["title"],
        "chunks": result["chunks"],
    }


class FetchUrlRequest(BaseModel):
    url: str


@router.post("/fetch-url")
def fetch_url_content(
    req: FetchUrlRequest,
    current_user: dict = Depends(require_current_user),
):
    """Fetch page text without storing it; login limits this proxy endpoint."""
    # Deliberately reference the dependency result so a future refactor cannot
    # accidentally remove the authenticated boundary from this endpoint.
    current_user_id(current_user)
    result = crawl_fetch(req.url)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"title": result["title"], "text": result["text"]}


class DeleteSourceRequest(BaseModel):
    source: str


@router.delete("/source", dependencies=[Depends(require_business_csrf)])
def delete_source(
    req: DeleteSourceRequest,
    current_user: dict = Depends(require_current_user),
):
    """Delete a source only from the authenticated user's collection."""
    if rag_disabled():
        raise HTTPException(status_code=503, detail="Document indexing is disabled")
    source = req.source.strip()
    if not source:
        raise HTTPException(status_code=400, detail="来源不能为空")

    collection = get_collection(current_user_id(current_user))
    try:
        collection.delete(where={"source": source})
        return {"message": f"已删除来源 {source}", "ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除失败: {exc}") from exc
