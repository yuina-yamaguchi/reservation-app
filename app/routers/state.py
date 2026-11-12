from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from .. import key_service, models, pricing, schemas, ticket_service
from ..auth import require_auth, user_to_dict
from ..database import SessionLocal, get_db
from .carpools import _application_response, _ride_query, _ride_response
from .emergency import _to_response as _alert_response
from .key_devices import _to_response as _device_response
from .reservations import reservation_to_response

router = APIRouter(prefix="/state", tags=["状態"])

# 終了済み予約を返す期間（日）
_PAST_RESERVATION_DAYS = 60


def _run_background_tasks(user_id: int, now) -> None:
    """サイドエフェクト処理をバックグラウンドで実行する。"""
    db = SessionLocal()
    try:
        key_service.issue_due(db, now)
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            ticket_service.ensure_monthly_plan_charge(db, user, now)
            ticket_service.ensure_monthly_tickets(db, user, now)
        ticket_service.sweep_tickets(db, now)
    except Exception:
        pass
    finally:
        db.close()


@router.get("/", response_model=schemas.StateResponse)
def get_state(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    now = pricing.now_jst()

    # サイドエフェクトはレスポンス返却後にバックグラウンドで実行
    background_tasks.add_task(_run_background_tasks, current_user.id, now)

    cars = db.query(models.Car).order_by(models.Car.id).all()
    members = db.query(models.Member).order_by(models.Member.id).all()

    # 終了済み予約は直近60日分のみ返す（今後・使用中の予約は全件含まれる）
    cutoff = now - timedelta(days=_PAST_RESERVATION_DAYS)
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
                selectinload(models.Reservation.digital_keys_rel),
            )
            .filter(models.Reservation.end_time >= cutoff)
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
            models.RideShare.status != "cancelled",
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

    # 管理者は未解決の緊急通報を全件、利用者は自分が送ったものを返す
    alert_query = (
        db.query(models.EmergencyAlert)
        .options(
            joinedload(models.EmergencyAlert.reporter),
            joinedload(models.EmergencyAlert.car),
        )
        .order_by(models.EmergencyAlert.id.desc())
    )
    if current_user.role == "admin":
        alert_query = alert_query.filter(models.EmergencyAlert.status == "open")
    else:
        alert_query = alert_query.filter(
            models.EmergencyAlert.reporter_user_id == current_user.id
        ).limit(10)
    emergency_alerts = [_alert_response(a) for a in alert_query.all()]

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
        "emergency_alerts": emergency_alerts,
    }
