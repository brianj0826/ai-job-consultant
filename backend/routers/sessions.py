from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.database import (
    get_user_sessions, create_session, get_session_messages,
    delete_session, rename_session
)

router = APIRouter()

@router.get("/")
def list_sessions(user_id: int):
    sessions = get_user_sessions(user_id)
    return [{"id": s[0], "name": s[1], "created_at": s[2]} for s in sessions]

class SessionCreate(BaseModel):
    user_id: int
    name: str = "新对话"

@router.post("/")
def new_session(data: SessionCreate):
    session_id = create_session(data.user_id, data.name)
    return {"session_id": session_id}

def _fmt_ts(dt):
    """格式化时间为 ISO UTC 字符串，带 Z 后缀让前端正确解析"""
    if dt is None:
        return None
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

@router.get("/{session_id}/messages")
def get_messages(session_id: int, limit: int = 50):
    msgs = get_session_messages(session_id, limit)
    return [{"id": m[0], "role": m[1], "content": m[2], "feedback": m[3], "timestamp": _fmt_ts(m[4])} for m in msgs]

class RenameRequest(BaseModel):
    name: str

@router.put("/{session_id}/rename")
def rename(session_id: int, req: RenameRequest):
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="名称不能为空")
    rename_session(session_id, req.name.strip())
    return {"ok": True, "name": req.name.strip()}

@router.delete("/{session_id}")
def remove_session(session_id: int):
    delete_session(session_id)
    return {"ok": True}