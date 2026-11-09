from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from .. import key_service, models, pricing, schemas, ticket_service
from ..auth import require_auth, user_to_dict
from ..database import get_db
from .carpools import _application_response, _ride_query, _ride_response
from .key_devices import _to_response as _device_response
from .reservations import reservation_to_response

router = APIRouter(prefix="/state", tags=["状態"])


@router.get("/", response_model=schemas.StateResponse)
def get_state(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    now = pricing.now_jst()
    key_service.issue_due(db, now)

    ticket_service.ensure_monthly_plan_charge(db, current_user, now)
    ticket_service.ensure_monthly_tickets(db, current_user, now)
    ticket_service.sweep_tickets(db, now)

    cars = db.query(models.Car).order_by(models.Car.id).all()
    members = db.query(models.Member).order_by(models.Member.id).all()
    reservations = [
        reservation_to_response(reservation, current_user)
        for reservation in (
            db.query(models.Reservation)
            .options(
                joinedload(models.Reservation.car),
                joinedload(models.Reservation.member).selectinload(
                    models.Member.users
                ),
                joinedload(models.Reservation.charge),
            )
            .order_by(models.Reservation.start_time)
            .all()
        )
    ]

    users = []
    if current_user.role == "admin":
        users = [
            user_to_dict(user)
            for user in db.query(models.User)
            .options(joinedload(models.User.member))
            .order_by(models.User.id)
            .all()
        ]

    tickets = (
        db.query(models.TimeTicket)
        .filter(models.TimeTicket.user_id == current_user.id)
        .order_by(
            models.TimeTicket.status,
            models.TimeTicket.expires_at,
            models.TimeTicket.id,
        )
        .all()
    )

    application_ride_ids = db.query(models.RideApplication.ride_id).filter(
        models.RideApplication.applicant_user_id == current_user.id
    )
    rides = (
        _ride_query(db)
        .filter(
            or_(
                models.RideShare.status.in_(["open", "full"]),
                models.RideShare.driver_user_id == current_user.id,
                models.RideShare.id.in_(application_ride_ids),
            ),
            models.RideShare.reservation.has(
                models.Reservation.start_time > now
            ),
        )
        .order_by(models.RideShare.id.desc())
        .all()
    )
    carpools = [_ride_response(ride, current_user) for ride in rides]

    my_applications = [
        _application_response(application)
        for application in db.query(models.RideApplication)
        .options(joinedload(models.RideApplication.applicant))
        .filter(models.RideApplication.applicant_user_id == current_user.id)
        .order_by(models.RideApplication.id.desc())
        .all()
    ]

    devices = (
        db.query(models.KeyDevice)
        .options(joinedload(models.KeyDevice.car))
        .order_by(models.KeyDevice.id)
        .all()
    )

    digital_keys = (
        db.query(models.DigitalKey)
        .filter(
            models.DigitalKey.recipient_user_id == current_user.id,
            models.DigitalKey.purpose == "reservation",
        )
        .order_by(models.DigitalKey.valid_from.desc())
        .limit(50)
        .all()
    )

    master_keys = []
    if current_user.role == "admin":
        master_keys = (
            db.query(models.DigitalKey)
            .filter(models.DigitalKey.purpose == "master")
            .order_by(models.DigitalKey.id.desc())
            .limit(20)
            .all()
        )

    return {
        "cars": cars,
        "members": members,
        "reservations": reservations,
        "users": users,
        "plans": [plan.to_dict() for plan in pricing.PLANS.values()],
        "profile": user_to_dict(current_user),
        "tickets": tickets,
        "carpools": carpools,
        "my_applications": my_applications,
        "key_devices": [_device_response(device) for device in devices],
        "digital_keys": digital_keys,
        "master_keys": master_keys,
    }
