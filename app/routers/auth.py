from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..auth import (
    _settings,
    create_session_token,
    ensure_login_allowed,
    record_login_failure,
    require_auth,
    reset_login_attempts,
    user_to_dict,
    verify_password_hash,
)
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["認証"])


class LoginRequest(BaseModel):
    username: str = Field(default="admin", min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ensure_login_allowed(request)

    username = payload.username.strip()
    user = (
        db.query(models.User)
        .filter(func.lower(models.User.username) == username.lower())
        .first()
    )
    if not user or not verify_password_hash(payload.password, user.password_hash):
        record_login_failure(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが違います",
        )

    reset_login_attempts(request)
    response.set_cookie(
        key=_settings.cookie_name,
        value=create_session_token(user),
        max_age=_settings.session_max_age,
        httponly=True,
        samesite="lax",
        secure=_settings.cookie_secure,
        path="/",
    )
    return {"authenticated": True, "user": user_to_dict(user)}


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
def me(current_user: models.User = Depends(require_auth)):
    return {"authenticated": True, "user": user_to_dict(current_user)}
