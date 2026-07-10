from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from backend.services.rag import index_document, get_collection, ALLOWED_EXTENSIONS
from backend.services.crawler import fetch_and_index, fetch_url as crawl_fetch
import shutil
import tempfile
import os

router = APIRouter()


class ImportUrlRequest(BaseModel):
    user_id: int
    url: str


def process_document(temp_path: str, user_id: int, original_filename: str, file_type: str):
    """后台执行文档索引"""
    try:
        index_document(temp_path, user_id, original_filename, file_type)
    except Exception as e:
        print(f"后台索引失败: {e}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@router.post("/upload")
def upload_document(
        user_id: int = Form(...),
        file: UploadFile = File(...)
):
    # 校验文件类型
    _, ext = os.path.splitext(file.filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}，支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 保存临时文件（保留原始扩展名以正确识别格式）
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    # 同步处理（索引够快，不需要后台）
    try:
        index_document(temp_path, user_id, file.filename, ext)
        return {"message": f"文档 {file.filename} 已成功导入知识库"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@router.get("/status")
def document_status(user_id: int):
    """返回知识库状态，包含所有来源文件列表"""
    coll = get_collection(user_id)
    count = coll.count()

    # 从所有块的元数据中提取唯一来源
    sources = []
    if count > 0:
        try:
            all_data = coll.get(limit=min(count, 500))
            metas = all_data.get('metadatas', [])
            seen = set()
            for m in metas:
                src = m.get('source', '')
                title = m.get('title', '')
                src_type = m.get('type', 'file')  # 'file' or 'web'
                key = src or title
                if key and key not in seen:
                    seen.add(key)
                    sources.append({
                        'source': src,
                        'title': title or src.split('/')[-1].split('\\')[-1] if src else '未知',
                        'type': src_type
                    })
        except Exception:
            pass

    return {"doc_count": count, "sources": sources}


@router.post("/import-url")
def import_url(req: ImportUrlRequest):
    """抓取网页内容并导入用户知识库"""
    result = fetch_and_index(req.url, req.user_id)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    return {
        "message": f"已导入: {result['title']}",
        "title": result['title'],
        "chunks": result['chunks']
    }


class FetchUrlRequest(BaseModel):
    url: str

@router.post("/fetch-url")
def fetch_url_content(req: FetchUrlRequest):
    """抓取网页文本内容（不入库），用于 JD 快速导入"""
    result = crawl_fetch(req.url)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    return {"title": result['title'], "text": result['text']}

class DeleteSourceRequest(BaseModel):
    user_id: int
    source: str  # 来源标识（URL 或文件路径）


@router.delete("/source")
def delete_source(req: DeleteSourceRequest):
    """从知识库中删除指定来源的所有文档块"""
    coll = get_collection(req.user_id)
    try:
        coll.delete(where={"source": req.source})
        return {"message": f"已删除来源: {req.source}", "ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
