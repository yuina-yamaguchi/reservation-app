from . import models
from .auth import hash_password
from .config import get_settings
from .database import SessionLocal


def ensure_default_admin() -> None:
    """ユーザーが1人もいない場合に管理者アカウントを作成する。"""
    db = SessionLocal()
    try:
        if db.query(models.User).count() > 0:
            return

        settings = get_settings()
        db.add(
            models.User(
                username=settings.admin_username,
                password_hash=hash_password(settings.app_password),
                role="admin",
            )
        )
        db.commit()
    finally:
        db.close()
