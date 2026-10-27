import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import get_settings

_settings = get_settings()

_serializer = URLSafeTimedSerializer(
    _settings.session_secret, salt="reservation-app-session"
)

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


def verify_password(password: str) -> bool:
    return secrets.compare_digest(
        password.encode("utf-8"), _settings.app_password.encode("utf-8")
    )


def create_session_token() -> str:
    return _serializer.dumps({"authenticated": True})


def is_valid_token(token: str) -> bool:
    try:
        data = _serializer.loads(token, max_age=_settings.session_max_age)
    except (BadSignature, SignatureExpired):
        return False
    return bool(data.get("authenticated"))


def require_auth(request: Request) -> None:
    token = request.cookies.get(_settings.cookie_name)
    if not token or not is_valid_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ログインが必要です",
        )
