import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from . import models
from .config import get_settings
from .database import get_db

_settings = get_settings()

_serializer = URLSafeTimedSerializer(
    _settings.session_secret, salt="reservation-app-session"
)

PBKDF2_ITERATIONS = 260_000

_attempts: dict[str, deque[float]] = defaultdict(deque)
_attempts_lock = threading.Lock()


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def ensure_login_allowed(request: Request) -> None:
    now = time.monotonic()
    key = _client_key(request)

    with _attempts_lock:
        attempts = _attempts[key]
        while attempts and now - attempts[0] > _settings.login_window_seconds:
            attempts.popleft()

        if len(attempts) >= _settings.login_max_attempts:
            retry_after = int(
                _settings.login_window_seconds - (now - attempts[0])
            ) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="試行回数が多すぎます。しばらく待ってから再度お試しください。",
                headers={"Retry-After": str(retry_after)},
            )


def record_login_failure(request: Request) -> None:
    key = _client_key(request)
    with _attempts_lock:
        _attempts[key].append(time.monotonic())


def reset_login_attempts(request: Request) -> None:
    key = _client_key(request)
    with _attempts_lock:
        _attempts.pop(key, None)


def reset_all_login_attempts() -> None:
    with _attempts_lock:
        _attempts.clear()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password_hash(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


def user_to_dict(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "member_id": user.member_id,
        "member_name": user.member.name if user.member else None,
    }


def create_session_token(user: models.User) -> str:
    return _serializer.dumps(
        {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
        }
    )


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> models.User:
    token = request.cookies.get(_settings.cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ログインが必要です",
        )

    try:
        data = _serializer.loads(token, max_age=_settings.session_max_age)
    except (BadSignature, SignatureExpired):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ログインが必要です",
        )

    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ログインが必要です",
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ログインが必要です",
        )
    return user


def require_auth(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    return current_user


def require_admin(
    current_user: models.User = Depends(require_auth),
) -> models.User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理者権限が必要です",
        )
    return current_user
