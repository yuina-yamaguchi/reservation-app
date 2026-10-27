from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..auth import (
    _settings,
    create_session_token,
    ensure_login_allowed,
    record_login_failure,
    require_auth,
    reset_login_attempts,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["認証"])


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response):
    ensure_login_allowed(request)

    if not verify_password(payload.password):
        record_login_failure(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="パスワードが違います",
        )

    reset_login_attempts(request)
    response.set_cookie(
        key=_settings.cookie_name,
        value=create_session_token(),
        max_age=_settings.session_max_age,
        httponly=True,
        samesite="lax",
        secure=_settings.cookie_secure,
        path="/",
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key=_settings.cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_settings.cookie_secure,
    )
    return {"authenticated": False}


@router.get("/me")
def me(_: None = Depends(require_auth)):
    return {"authenticated": True}
