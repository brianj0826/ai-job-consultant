"""Deprecated compatibility aliases for the secure authentication API.

New clients use ``/api/auth``.  Keeping these two aliases prevents an older
frontend from silently falling back to username-only identity while ensuring it
receives the exact same cookie-backed session and password policy.
"""
from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from backend.routers.auth import CredentialsRequest, login as secure_login, register as secure_register


router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED, deprecated=True)
def register(request_data: RegisterRequest, request: Request, response: Response):
    """Compatibility alias for ``POST /api/auth/register``."""
    response.headers["Deprecation"] = "true"
    return secure_register(
        CredentialsRequest(username=request_data.username, password=request_data.password),
        request,
        response,
    )


@router.post("/login", deprecated=True)
def login(request_data: LoginRequest, request: Request, response: Response):
    """Compatibility alias for ``POST /api/auth/login``."""
    response.headers["Deprecation"] = "true"
    return secure_login(
        CredentialsRequest(username=request_data.username, password=request_data.password),
        request,
        response,
    )
