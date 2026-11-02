from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import require_auth
from ..database import get_db

router = APIRouter(prefix="/reservations", tags=["予約"])


def check_conflict(
    db: Session,
    car_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_id: int | None = None,
):
    query = db.query(models.Reservation).filter(
        models.Reservation.car_id == car_id,
        models.Reservation.start_time < end_time,
        models.Reservation.end_time > start_time,
    )
    if exclude_id is not None:
        query = query.filter(models.Reservation.id != exclude_id)
    return query.first()


def _with_relations(db: Session):
    return db.query(models.Reservation).options(
        joinedload(models.Reservation.car),
        joinedload(models.Reservation.member),
    )


@router.get("/", response_model=list[schemas.ReservationResponse])
def list_reservations(db: Session = Depends(get_db)):
    return _with_relations(db).order_by(models.Reservation.start_time).all()


@router.get("/{reservation_id}", response_model=schemas.ReservationResponse)
def get_reservation(reservation_id: int, db: Session = Depends(get_db)):
    reservation = (
        _with_relations(db)
        .filter(models.Reservation.id == reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="予約が見つかりません")
    return reservation


@router.post(
    "/",
    response_model=schemas.ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation(
    reservation: schemas.ReservationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    car = db.query(models.Car).filter(models.Car.id == reservation.car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="車が見つかりません")

    member_id = reservation.member_id
    if current_user.role != "admin":
        if current_user.member_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="住人が紐付いていません。管理者に連絡してください。",
            )
        member_id = current_user.member_id

    member = (
        db.query(models.Member)
        .filter(models.Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="住人が見つかりません")

    conflict = check_conflict(
        db, reservation.car_id, reservation.start_time, reservation.end_time
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"この時間帯は既に「{conflict.member.name}」の予約があります",
        )

    data = reservation.model_dump()
    data["member_id"] = member_id
    db_reservation = models.Reservation(**data)
    db.add(db_reservation)
    db.commit()
    db.refresh(db_reservation)
    return db_reservation


@router.delete("/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    reservation = (
        db.query(models.Reservation)
        .filter(models.Reservation.id == reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="予約が見つかりません")

    if (
        current_user.role != "admin"
        and reservation.member_id != current_user.member_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="この予約をキャンセルする権限がありません",
        )

    db.delete(reservation)
    db.commit()
