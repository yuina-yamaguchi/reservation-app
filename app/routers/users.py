from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import hash_password, require_admin, user_to_dict
from ..database import get_db

router = APIRouter(prefix="/users", tags=["ユーザー"])


def _get_user(db: Session, user_id: int) -> models.User:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    return user


def _ensure_member_exists(db: Session, member_id: int | None) -> None:
    if member_id is None:
        return
    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="住人が見つかりません")


def _ensure_username_available(
    db: Session, username: str, exclude_id: int | None = None
) -> None:
    query = db.query(models.User).filter(
        func.lower(models.User.username) == username.lower()
    )
    if exclude_id is not None:
        query = query.filter(models.User.id != exclude_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="このユーザー名は既に使われています",
        )


def _admin_count(db: Session) -> int:
    return db.query(models.User).filter(models.User.role == "admin").count()


@router.get("/", response_model=list[schemas.UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    users = db.query(models.User).order_by(models.User.id).all()
    return [user_to_dict(user) for user in users]


@router.post(
    "/",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    _ensure_username_available(db, payload.username)
    _ensure_member_exists(db, payload.member_id)

    user = models.User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        member_id=payload.member_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_to_dict(user)


@router.put("/{user_id}", response_model=schemas.UserResponse)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    user = _get_user(db, user_id)
    data = payload.model_dump(exclude_unset=True)

    if data.get("username") is not None:
        _ensure_username_available(db, data["username"], exclude_id=user.id)
        user.username = data["username"]

    if data.get("password") is not None:
        user.password_hash = hash_password(data["password"])

    if data.get("role") is not None:
        if (
            user.role == "admin"
            and data["role"] != "admin"
            and _admin_count(db) <= 1
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="最後の管理者は利用者に変更できません",
            )
        user.role = data["role"]

    if "member_id" in data:
        _ensure_member_exists(db, data["member_id"])
        user.member_id = data["member_id"]

    db.commit()
    db.refresh(user)
    return user_to_dict(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    user = _get_user(db, user_id)

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="自分自身は削除できません",
        )

    if user.role == "admin" and _admin_count(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="最後の管理者は削除できません",
        )

    db.delete(user)
    db.commit()
