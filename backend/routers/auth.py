"""Authentication endpoints backed by HttpOnly cookie sessions."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.services.auth import (
    clear_auth_cookies,
    clear_failed_logins,
    consume_login_attempt,
    current_session_id,
    create_auth_session,
    normalize_username,
    request_metadata,
    require_csrf,
    require_authenticated_user,
    revoke_auth_session,
    set_auth_cookies,
    validate_login_password,
    validate_password,
)
from backend.services.admin import record_admin_auth_event
from backend.services.database import (
    authenticate_user,
    change_user_password,
    get_user_by_id,
    register_user,
)


router = APIRouter()


class CredentialsRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _validated_credentials(
    request: CredentialsRequest,
    *,
    legacy_login: bool = False,
) -> tuple[str, str]:
    try:
        password = (
            validate_login_password(request.password)
            if legacy_login
            else validate_password(request.password)
        )
        return normalize_username(request.username), password
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
    username, password = _validated_credentials(payload, legacy_login=True)
    metadata = request_metadata(request)
    retry_after = consume_login_attempt(metadata["ip_address"], username)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts; please try again later",
            headers={"Retry-After": str(retry_after)},
        )
    user = authenticate_user(username, password)
    if not user:
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
    current_user: dict = Depends(require_authenticated_user),
    _: None = Depends(require_csrf),
):
    """Revoke the current server-side session and clear both browser cookies."""
    record_admin_auth_event(current_user, "admin.logout", request_metadata(request))
    revoke_auth_session(current_session_id(request), current_user["id"])
    clear_auth_cookies(response)
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: dict = Depends(require_authenticated_user),
    _: None = Depends(require_csrf),
):
    """Replace the current password, clear the forced-change flag, and rotate sessions."""
    try:
        current_password = validate_login_password(payload.current_password)
        new_password = validate_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if hmac.compare_digest(current_password, new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current password",
        )

    user = change_user_password(current_user["id"], current_password, new_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    _write_login_cookies(response, request, current_user["id"])
    return {"user": user}


@router.get("/me")
def me(
    response: Response,
    current_user: dict = Depends(require_authenticated_user),
):
    """Return the authenticated user without exposing session secrets."""
    response.headers["Cache-Control"] = "no-store"
    return {"user": current_user}
