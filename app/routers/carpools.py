from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models, pricing, schemas
from ..auth import require_auth
from ..database import get_db

router = APIRouter(prefix="/carpools", tags=["相乗り"])


def _ride_query(db: Session):
    return db.query(models.RideShare).options(
        joinedload(models.RideShare.driver),
        joinedload(models.RideShare.reservation).joinedload(models.Reservation.car),
        joinedload(models.RideShare.applications).joinedload(
            models.RideApplication.applicant
        ),
    )


def _accepted_count(ride: models.RideShare) -> int:
    return sum(1 for app in ride.applications if app.status == "accepted")


def _remaining_seats(ride: models.RideShare) -> int:
    return max(0, ride.seats_offered - _accepted_count(ride))


def _can_view_note(ride: models.RideShare, current_user: models.User) -> bool:
    if ride.note_public:
        return True
    return ride.driver_user_id == current_user.id


def _ride_response(
    ride: models.RideShare, current_user: models.User
) -> dict:
    reservation = ride.reservation
    return {
        "id": ride.id,
        "reservation_id": ride.reservation_id,
        "driver_user_id": ride.driver_user_id,
        "driver_name": ride.driver.username if ride.driver else None,
        "car_id": reservation.car_id if reservation else None,
        "car_name": reservation.car.name if reservation and reservation.car else None,
        "start_time": reservation.start_time if reservation else None,
        "end_time": reservation.end_time if reservation else None,
        "area": ride.area,
        "seat_fee": ride.seat_fee,
        "gender_filter": ride.gender_filter,
        "seats_offered": ride.seats_offered,
        "driver_guest_seats": ride.driver_guest_seats,
        "remaining_seats": _remaining_seats(ride),
        "note": ride.note if _can_view_note(ride, current_user) else "",
        "note_public": ride.note_public,
        "status": ride.status,
        "applications": [_application_response(app) for app in ride.applications],
    }


def _application_response(application: models.RideApplication) -> dict:
    return {
        "id": application.id,
        "ride_id": application.ride_id,
        "applicant_user_id": application.applicant_user_id,
        "applicant_name": (
            application.applicant.username if application.applicant else None
        ),
        "status": application.status,
        "seat_fee": application.seat_fee,
        "created_at": application.created_at,
        "decided_at": application.decided_at,
    }


def _can_manage(ride: models.RideShare, user: models.User) -> bool:
    return user.role == "admin" or ride.driver_user_id == user.id


def _get_ride(db: Session, ride_id: int) -> models.RideShare:
    ride = _ride_query(db).filter(models.RideShare.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="相乗り募集が見つかりません")
    return ride


def _validate_seats(ride: models.RideShare, seats: int, guest_seats: int) -> None:
    capacity = ride.reservation.car.seat_capacity if ride.reservation.car else 4
    if seats + guest_seats > capacity - 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"この車は運転手を除いて{max(0, capacity - 1)}人までです",
        )
    if seats < _accepted_count(ride):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="承認済みの人数より少なくはできません",
        )


@router.get("/", response_model=list[schemas.CarpoolResponse])
def list_carpools(
    include_closed: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    query = _ride_query(db)
    if not include_closed:
        application_ride_ids = db.query(models.RideApplication.ride_id).filter(
            models.RideApplication.applicant_user_id == current_user.id
        )
        query = query.filter(
            or_(
                models.RideShare.status.in_(["open", "full"]),
                models.RideShare.driver_user_id == current_user.id,
                models.RideShare.id.in_(application_ride_ids),
            ),
            models.RideShare.reservation.has(
                models.Reservation.start_time > pricing.now_jst()
            ),
        )
    rides = query.order_by(models.RideShare.id.desc()).all()
    return [_ride_response(ride, current_user) for ride in rides]


@router.post(
    "/", response_model=schemas.CarpoolResponse, status_code=status.HTTP_201_CREATED
)
def create_carpool(
    payload: schemas.CarpoolCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    reservation = (
        db.query(models.Reservation)
        .options(joinedload(models.Reservation.car))
        .filter(models.Reservation.id == payload.reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="予約が見つかりません")

    driver = current_user
    if payload.driver_user_id is not None and current_user.role == "admin":
        driver = (
            db.query(models.User)
            .filter(models.User.id == payload.driver_user_id)
            .first()
        )
        if not driver:
            raise HTTPException(status_code=404, detail="運転手が見つかりません")

    if current_user.role != "admin" and driver.member_id != reservation.member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="自分の予約にのみ相乗り募集を出せます",
        )
    if driver.member_id is not None and driver.member_id != reservation.member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="この予約の運転手ではありません",
        )

    now = pricing.now_jst()
    if reservation.start_time <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="開始前の予約にのみ相乗り募集を出せます",
        )
    existing = (
        db.query(models.RideShare)
        .filter(models.RideShare.reservation_id == reservation.id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="この予約には既に相乗り募集があります",
        )

    capacity = reservation.car.seat_capacity if reservation.car else 4
    if payload.seats_offered + payload.driver_guest_seats > capacity - 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"この車は運転手を除いて{max(0, capacity - 1)}人までです",
        )

    ride = models.RideShare(
        reservation_id=reservation.id,
        driver_user_id=driver.id,
        area=payload.area,
        seat_fee=pricing.carpool_seat_fee(payload.area),
        gender_filter=payload.gender_filter,
        seats_offered=payload.seats_offered,
        driver_guest_seats=payload.driver_guest_seats,
        note=payload.note,
        note_public=payload.note_public,
        status="open",
    )
    db.add(ride)
    db.commit()
    ride = _get_ride(db, ride.id)
    return _ride_response(ride, current_user)


@router.put("/{ride_id}", response_model=schemas.CarpoolResponse)
def update_carpool(
    ride_id: int,
    payload: schemas.CarpoolUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    ride = _get_ride(db, ride_id)
    if not _can_manage(ride, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="この相乗り募集を編集する権限がありません",
        )

    data = payload.model_dump(exclude_unset=True)
    if "area" in data and data["area"] is not None:
        ride.area = data["area"]
        ride.seat_fee = pricing.carpool_seat_fee(data["area"])
    for field in ("gender_filter", "note"):
        if field in data and data[field] is not None:
            setattr(ride, field, data[field])
    if "note_public" in data and data["note_public"] is not None:
        ride.note_public = data["note_public"]
    if "seats_offered" in data and data["seats_offered"] is not None:
        _validate_seats(
            ride, data["seats_offered"], ride.driver_guest_seats
        )
        ride.seats_offered = data["seats_offered"]
    if "driver_guest_seats" in data and data["driver_guest_seats"] is not None:
        _validate_seats(
            ride, ride.seats_offered, data["driver_guest_seats"]
        )
        ride.driver_guest_seats = data["driver_guest_seats"]
    if "status" in data and data["status"] is not None:
        ride.status = data["status"]
        if data["status"] == "cancelled":
            for application in ride.applications:
                if application.status == "pending":
                    application.status = "cancelled"
                    application.decided_at = pricing.now_jst()

    db.commit()
    ride = _get_ride(db, ride.id)
    return _ride_response(ride, current_user)


@router.delete("/{ride_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_carpool(
    ride_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    ride = _get_ride(db, ride_id)
    if not _can_manage(ride, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="この相乗り募集を中止する権限がありません",
        )
    ride.status = "cancelled"
    for application in ride.applications:
        if application.status == "pending":
            application.status = "cancelled"
            application.decided_at = pricing.now_jst()
    db.commit()


def _overlapping_reservation(
    db: Session, applicant: models.User, ride: models.RideShare
):
    if applicant.member_id is None or not ride.reservation:
        return None
    return (
        db.query(models.Reservation)
        .filter(
            models.Reservation.member_id == applicant.member_id,
            models.Reservation.car_id == ride.reservation.car_id,
            models.Reservation.id != ride.reservation_id,
            models.Reservation.start_time < ride.reservation.end_time,
            models.Reservation.end_time > ride.reservation.start_time,
        )
        .first()
    )


@router.post(
    "/{ride_id}/apply",
    response_model=schemas.RideApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_carpool(
    ride_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    ride = _get_ride(db, ride_id)
    if ride.status not in ("open",):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="この募集は受付中ではありません"
        )
    if ride.driver_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="自分の募集には申し込めません"
        )
    if ride.reservation and ride.reservation.start_time <= pricing.now_jst():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="開始済みの募集には申し込めません"
        )
    if ride.reservation and current_user.member_id == ride.reservation.member_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同じ住人アカウントでは申し込めません",
        )

    if ride.gender_filter != "any":
        if current_user.gender == "unspecified":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="この募集は性別登録が必要です。管理者に登録を依頼してください",
            )
        if current_user.gender != ride.gender_filter:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="この募集の性別条件を満たしていません",
            )

    if _remaining_seats(ride) <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="空席がありません"
        )

    overlap = _overlapping_reservation(db, current_user, ride)
    if overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同じ時間帯に自分の予約があります",
        )

    existing = (
        db.query(models.RideApplication)
        .filter(
            models.RideApplication.ride_id == ride.id,
            models.RideApplication.applicant_user_id == current_user.id,
        )
        .first()
    )
    if existing:
        if existing.status in ("pending", "accepted"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="既に申し込んでいます"
            )
        existing.status = "pending"
        existing.seat_fee = ride.seat_fee
        existing.created_at = pricing.now_jst()
        existing.decided_at = None
        application = existing
    else:
        application = models.RideApplication(
            ride_id=ride.id,
            applicant_user_id=current_user.id,
            status="pending",
            seat_fee=ride.seat_fee,
        )
        db.add(application)

    db.commit()
    db.refresh(application)
    return _application_response(application)


@router.delete(
    "/{ride_id}/applications", status_code=status.HTTP_204_NO_CONTENT
)
def cancel_application(
    ride_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    ride = _get_ride(db, ride_id)
    application = (
        db.query(models.RideApplication)
        .filter(
            models.RideApplication.ride_id == ride.id,
            models.RideApplication.applicant_user_id == current_user.id,
        )
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="申し込みが見つかりません")
    if application.status not in ("pending", "accepted"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="この申し込みは取り消せません"
        )
    application.status = "cancelled"
    application.decided_at = pricing.now_jst()
    if ride.status == "full":
        ride.status = "open"
    db.commit()


@router.post(
    "/{ride_id}/applications/{application_id}/approve",
    response_model=schemas.RideApplicationResponse,
)
def approve_application(
    ride_id: int,
    application_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    ride = _get_ride(db, ride_id)
    if not _can_manage(ride, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="承認する権限がありません"
        )
    application = next(
        (app for app in ride.applications if app.id == application_id), None
    )
    if not application:
        raise HTTPException(status_code=404, detail="申し込みが見つかりません")
    if application.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="この申し込みは処理済みです"
        )
    if _remaining_seats(ride) <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="空席がありません"
        )

    charge = (
        db.query(models.ReservationCharge)
        .filter(models.ReservationCharge.reservation_id == ride.reservation_id)
        .first()
    )
    if charge:
        accepted_total = sum(
            app.seat_fee
            for app in ride.applications
            if app.status == "accepted"
        )
        if accepted_total + application.seat_fee > charge.vehicle_value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="相乗り値引きが車両代金の上限に達します",
            )

    application.status = "accepted"
    application.decided_at = pricing.now_jst()
    if _accepted_count(ride) >= ride.seats_offered:
        ride.status = "full"
    db.commit()
    db.refresh(application)
    return _application_response(application)


@router.post(
    "/{ride_id}/applications/{application_id}/reject",
    response_model=schemas.RideApplicationResponse,
)
def reject_application(
    ride_id: int,
    application_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    ride = _get_ride(db, ride_id)
    if not _can_manage(ride, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="却下する権限がありません"
        )
    application = next(
        (app for app in ride.applications if app.id == application_id), None
    )
    if not application:
        raise HTTPException(status_code=404, detail="申し込みが見つかりません")
    if application.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="この申し込みは処理済みです"
        )
    application.status = "rejected"
    application.decided_at = pricing.now_jst()
    db.commit()
    db.refresh(application)
    return _application_response(application)
