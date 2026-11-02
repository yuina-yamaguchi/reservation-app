from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import require_auth, user_to_dict
from ..database import get_db

router = APIRouter(prefix="/state", tags=["状態"])


@router.get("/", response_model=schemas.StateResponse)
def get_state(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    cars = db.query(models.Car).order_by(models.Car.id).all()
    members = db.query(models.Member).order_by(models.Member.id).all()
    reservations = (
        db.query(models.Reservation)
        .options(
            joinedload(models.Reservation.car),
            joinedload(models.Reservation.member),
        )
        .order_by(models.Reservation.start_time)
        .all()
    )
    users = []
    if current_user.role == "admin":
        users = [
            user_to_dict(user)
            for user in db.query(models.User)
            .options(joinedload(models.User.member))
            .order_by(models.User.id)
            .all()
        ]

    return {
        "cars": cars,
        "members": members,
        "reservations": reservations,
        "users": users,
    }
