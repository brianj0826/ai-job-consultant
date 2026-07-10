from fastapi import APIRouter
from pydantic import BaseModel
from backend.services.database import set_message_feedback

router = APIRouter()

class FeedbackRequest(BaseModel):
    msg_id: int
    feedback: str  # "like" 或 "dislike"

@router.post("/")
def submit_feedback(req: FeedbackRequest):
    set_message_feedback(req.msg_id, req.feedback)
    return {"ok": True}