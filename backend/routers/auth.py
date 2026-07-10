"""Authentication endpoints backed by HttpOnly cookie sessions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.services.auth import (
    clear_auth_cookies,
    clear_failed_logins,
    current_session_id,
    create_auth_session,
    login_retry_after,
    normalize_username,
    record_failed_login,
    request_metadata,
    require_csrf,
    require_current_user,
    revoke_auth_session,
    set_auth_cookies,
    validate_password,
)
from backend.services.admin import record_admin_auth_event
from backend.services.database import authenticate_user, get_user_by_id, register_user


router = APIRouter()


class CredentialsRequest(BaseModel):
    username: str
    password: str


def _validated_credentials(request: CredentialsRequest) -> tuple[str, str]:
    try:
        return normalize_username(request.username), validate_password(request.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _write_login_cookies(
    response: Response,
    request: Request,
    user_id: int,
    metadata: dict | None = None,
) -> None:
    metadata = metadata or request_metadata(request)
    credentials = create_auth_session(user_id, **metadata)
    set_auth_cookies(response, credentials)
    response.headers["Cache-Control"] = "no-store"


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: CredentialsRequest, request: Request, response: Response):
    """Create a normal-user account and establish its first secure session."""
    username, password = _validated_credentials(payload)
    user_id = register_user(username, password)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already in use")

    # A newly registered account is a regular user by construction; privileged
    # roles are only assigned by the super-admin API.
    _write_login_cookies(response, request, user_id)
    user = get_user_by_id(user_id)
    return {"user": user}


@router.post("/login")
def login(payload: CredentialsRequest, request: Request, response: Response):
    """Authenticate by password and issue session/CSRF cookies."""
    username, password = _validated_credentials(payload)
    metadata = request_metadata(request)
    retry_after = login_retry_after(metadata["ip_address"], username)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts; please try again later",
            headers={"Retry-After": str(retry_after)},
        )
    user = authenticate_user(username, password)
    if not user:
        record_failed_login(metadata["ip_address"], username)
        # Keep disabled and unknown accounts indistinguishable from an invalid
        # password to avoid account-status disclosure.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    clear_failed_logins(metadata["ip_address"], username)
    record_admin_auth_event(user, "admin.login", metadata)
    _write_login_cookies(response, request, user["id"], metadata)
    return {"user": user}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    current_user: dict = Depends(require_current_user),
    _: None = Depends(require_csrf),
):
    """Revoke the current server-side session and clear both browser cookies."""
    record_admin_auth_event(current_user, "admin.logout", request_metadata(request))
    revoke_auth_session(current_session_id(request), current_user["id"])
    clear_auth_cookies(response)
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}


@router.get("/me")
def me(
    response: Response,
    current_user: dict = Depends(require_current_user),
):
    """Return the authenticated user without exposing session secrets."""
    response.headers["Cache-Control"] = "no-store"
    return {"user": current_user}
