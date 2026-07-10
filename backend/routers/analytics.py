"""Authenticated, per-user analytics endpoints."""
from fastapi import APIRouter, Depends, Query

from backend.services.access import current_user_id
from backend.services.analytics import get_daily_trend, get_feedback_stats, get_overview
from backend.services.auth import require_current_user


router = APIRouter()


@router.get("/overview")
def overview(current_user: dict = Depends(require_current_user)):
    """Return the authenticated user's conversation summary only."""
    return get_overview(current_user_id(current_user))


@router.get("/feedback")
def feedback(current_user: dict = Depends(require_current_user)):
    """Return the authenticated user's feedback summary only."""
    return get_feedback_stats(current_user_id(current_user))


@router.get("/trend")
def trend(
    days: int = Query(7, ge=1, le=30),
    current_user: dict = Depends(require_current_user),
):
    """Return the authenticated user's daily message trend."""
    return get_daily_trend(current_user_id(current_user), days)
