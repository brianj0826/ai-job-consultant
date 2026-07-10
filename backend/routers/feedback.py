from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services.access import require_owned_message
from backend.services.auth import require_csrf, require_current_user
from backend.services.database import set_message_feedback


router = APIRouter()


class FeedbackRequest(BaseModel):
    msg_id: int
    feedback: Literal["like", "dislike"]


@router.post("/", dependencies=[Depends(require_csrf)])
def submit_feedback(
    req: FeedbackRequest,
    current_user: dict = Depends(require_current_user),
):
    message = require_owned_message(req.msg_id, current_user)
    if message["role"] != "assistant":
        raise HTTPException(status_code=400, detail="只能评价 AI 回复")

    set_message_feedback(req.msg_id, req.feedback)
    return {"ok": True}
