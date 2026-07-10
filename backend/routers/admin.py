"""Protected administrator-console endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend.services import admin as admin_service
from backend.services.auth import require_admin, require_admin_csrf, request_metadata


router = APIRouter()


class UpdateUserStatusRequest(BaseModel):
    status: str


class UpdateUserRoleRequest(BaseModel):
    role: str


def _admin_error(error: admin_service.AdminActionError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.message)


@router.get("/overview")
def overview(_: dict = Depends(require_admin)):
    """Aggregate metrics for the administrator dashboard."""
    return admin_service.get_overview()


@router.get("/users")
def users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=64),
    _: dict = Depends(require_admin),
):
    """Page through accounts without exposing password hashes or session data."""
    try:
        return admin_service.list_users(page=page, page_size=page_size, search=search)
    except admin_service.AdminActionError as error:
        raise _admin_error(error) from error


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    payload: UpdateUserStatusRequest,
    request: Request,
    current_user: dict = Depends(require_admin_csrf),
):
    """Enable or disable a user and revoke their sessions when disabling."""
    try:
        user = admin_service.update_user_status(
            current_user,
            user_id,
            payload.status,
            request_metadata(request),
        )
        return {"user": user}
    except admin_service.AdminActionError as error:
        raise _admin_error(error) from error


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    request: Request,
    current_user: dict = Depends(require_admin_csrf),
):
    """Assign a role; the service enforces super-admin-only safeguards."""
    try:
        user = admin_service.update_user_role(
            current_user,
            user_id,
            payload.role,
            request_metadata(request),
        )
        return {"user": user}
    except admin_service.AdminActionError as error:
        raise _admin_error(error) from error


@router.get("/feedback")
def feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    feedback: Optional[str] = Query(None),
    _: dict = Depends(require_admin),
):
    """Review liked/disliked assistant responses, capped at 2,000 characters."""
    try:
        return admin_service.list_feedback(page, page_size, feedback)
    except admin_service.AdminActionError as error:
        raise _admin_error(error) from error


@router.get("/audit-logs")
def audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: Optional[str] = Query(None, max_length=100),
    _: dict = Depends(require_admin),
):
    """Return a paginated audit trail of administrator write operations."""
    try:
        return admin_service.list_audit_logs(page, page_size, action)
    except admin_service.AdminActionError as error:
        raise _admin_error(error) from error
