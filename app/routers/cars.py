from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas, ticket_service
from ..auth import require_admin
from ..database import get_db

router = APIRouter(prefix="/cars", tags=["車"])


@router.get("/", response_model=list[schemas.CarResponse])
def list_cars(db: Session = Depends(get_db)):
    return db.query(models.Car).order_by(models.Car.id).all()


@router.get("/{car_id}", response_model=schemas.CarResponse)
def get_car(car_id: int, db: Session = Depends(get_db)):
    car = db.query(models.Car).filter(models.Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="車が見つかりません")
    return car


@router.post(
    "/",
    response_model=schemas.CarResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_car(car: schemas.CarCreate, db: Session = Depends(get_db)):
    data = car.model_dump()
    seat_capacity = data.pop("seat_capacity", 4)
    db_car = models.Car(**data)
    db.add(db_car)
    db.flush()
    db_car.profile = models.CarProfile(
        car_id=db_car.id, seat_capacity=seat_capacity
    )
    db.commit()
    db.refresh(db_car)
    return db_car


@router.put(
    "/{car_id}",
    response_model=schemas.CarResponse,
    dependencies=[Depends(require_admin)],
)
def update_car(
    car_id: int, car: schemas.CarCreate, db: Session = Depends(get_db)
):
    db_car = db.query(models.Car).filter(models.Car.id == car_id).first()
    if not db_car:
        raise HTTPException(status_code=404, detail="車が見つかりません")

    data = car.model_dump()
    seat_capacity = data.pop("seat_capacity", 4)
    for key, value in data.items():
        setattr(db_car, key, value)
    profile = ticket_service.ensure_car_profile(db, db_car)
    profile.seat_capacity = seat_capacity

    db.commit()
    db.refresh(db_car)
    return db_car


@router.delete(
    "/{car_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_car(car_id: int, db: Session = Depends(get_db)):
    car = db.query(models.Car).filter(models.Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="車が見つかりません")

    has_reservation = (
        db.query(models.Reservation.id)
        .filter(models.Reservation.car_id == car_id)
        .first()
    )
    if has_reservation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="この車には予約があるため削除できません。先に予約をキャンセルしてください。",
        )

    has_key = (
        db.query(models.DigitalKey.id)
        .filter(models.DigitalKey.car_id == car_id)
        .first()
    )
    if has_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="この車にはデジタルキーの履歴があるため削除できません。",
        )

    db.delete(car)
    db.commit()
