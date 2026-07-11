from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.services.access import current_user_id, require_owned_session
from backend.services.auth import require_business_csrf, require_current_user
from backend.services.database import (
    create_session,
    delete_session,
    get_session_messages,
    get_user_sessions,
    rename_session,
)


router = APIRouter()


@router.get("/")
def list_sessions(current_user: dict = Depends(require_current_user)):
    """List only the authenticated user's conversations."""
    sessions = get_user_sessions(current_user_id(current_user))
    return [{"id": s[0], "name": s[1], "created_at": s[2]} for s in sessions]


class SessionCreate(BaseModel):
    name: str = "新对话"


@router.post("/", dependencies=[Depends(require_business_csrf)])
def new_session(
    data: SessionCreate,
    current_user: dict = Depends(require_current_user),
):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="会话名称不能为空")
    if len(name) > 255:
        raise HTTPException(status_code=400, detail="会话名称不能超过 255 个字符")

    session_id = create_session(current_user_id(current_user), name)
    return {"session_id": session_id}


def _fmt_ts(dt):
    """Format database datetimes consistently for browser clients."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/{session_id}/messages")
def get_messages(
    session_id: int,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_current_user),
):
    require_owned_session(session_id, current_user)
    messages = get_session_messages(session_id, limit)
    return [
        {
            "id": message[0],
            "role": message[1],
            "content": message[2],
            "feedback": message[3],
            "timestamp": _fmt_ts(message[4]),
        }
        for message in messages
    ]


class RenameRequest(BaseModel):
    name: str


@router.put("/{session_id}/rename", dependencies=[Depends(require_business_csrf)])
def rename(
    session_id: int,
    req: RenameRequest,
    current_user: dict = Depends(require_current_user),
):
    require_owned_session(session_id, current_user)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="名称不能为空")
    if len(name) > 255:
        raise HTTPException(status_code=400, detail="名称不能超过 255 个字符")
    rename_session(session_id, name)
    return {"ok": True, "name": name}


@router.delete("/{session_id}", dependencies=[Depends(require_business_csrf)])
def remove_session(
    session_id: int,
    current_user: dict = Depends(require_current_user),
):
    require_owned_session(session_id, current_user)
    delete_session(session_id)
    return {"ok": True}
