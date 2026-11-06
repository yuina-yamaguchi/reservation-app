import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from .. import key_service, models, pricing, schemas, ticket_service
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
    buffer = pricing.handover_buffer()
    query = db.query(models.Reservation).filter(
        models.Reservation.car_id == car_id,
        models.Reservation.start_time < end_time + buffer,
        models.Reservation.end_time > start_time - buffer,
    )
    if exclude_id is not None:
        query = query.filter(models.Reservation.id != exclude_id)
    return query.first()


def _with_relations(db: Session):
    return db.query(models.Reservation).options(
        joinedload(models.Reservation.car),
        joinedload(models.Reservation.member),
        joinedload(models.Reservation.charge),
    )


def _resolve_member(
    db: Session, current_user: models.User, member_id: int
) -> models.Member:
    if current_user.role != "admin":
        if current_user.member_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="住人が紐付いていません。管理者に連絡してください。",
            )
        member_id = current_user.member_id

    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="住人が見つかりません")
    return member


def _resolve_ticket_user(
    db: Session,
    current_user: models.User,
    member: models.Member,
    requested_user_id: int | None,
) -> models.User:
    if current_user.role != "admin":
        return current_user

    if requested_user_id is not None:
        user = (
            db.query(models.User)
            .filter(models.User.id == requested_user_id)
            .first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        return user

    linked = (
        db.query(models.User)
        .filter(models.User.member_id == member.id)
        .order_by(models.User.id)
        .first()
    )
    return linked or current_user


def _weekend_reservation_count(
    db: Session, member_id: int, now: datetime
) -> int:
    reservations = (
        db.query(models.Reservation)
        .filter(
            models.Reservation.member_id == member_id,
            models.Reservation.end_time >= now,
        )
        .all()
    )
    return sum(
        1
        for reservation in reservations
        if pricing.is_weekend_or_holiday(reservation.start_time)
    )


def _build_options(
    db: Session,
    current_user: models.User,
    payload,
    member: models.Member,
    ticket_user: models.User,
) -> dict:
    now = pricing.now_jst()
    start = pricing.to_jst_naive(payload.start_time)
    end = pricing.to_jst_naive(payload.end_time)
    hours = pricing.billable_hours(start, end)
    plan = pricing.plan_for(ticket_user.plan)

    ticket_service.sweep_tickets(db, now)

    conflict = check_conflict(db, payload.car_id, start, end)
    blocked_reason = None
    options: list[dict] = []

    if conflict:
        blocked_reason = f"この時間帯は既に「{conflict.member.name}」の予約があります"
    elif current_user.role != "admin" and start <= now:
        blocked_reason = "過去の日時は予約できません"
    else:
        days = pricing.days_ahead(start, now)
        ticket = ticket_service.find_available_ticket(db, ticket_user.id, start)
        ticket_allowed = ticket is not None and (
            current_user.role == "admin" or days <= pricing.TICKET_BOOKING_DAYS
        )
        time_allowed = (
            current_user.role == "admin" or days <= pricing.TIME_BOOKING_DAYS
        )

        if (
            current_user.role != "admin"
            and pricing.is_weekend_or_holiday(start)
            and _weekend_reservation_count(db, member.id, now)
            >= pricing.WEEKEND_RESERVATION_LIMIT
        ):
            blocked_reason = "土日祝の予約は同時に2件までです"
        elif not ticket_allowed and not time_allowed:
            blocked_reason = (
                "この日付は6時間券が必要です（時間券は14日前から予約できます）"
            )
        else:
            if time_allowed:
                options.append(pricing.time_option(hours, ticket_user.plan))
            if ticket_allowed:
                options.append(pricing.ticket_option(hours, ticket))

    return {
        "car_available": conflict is None,
        "blocked_reason": blocked_reason,
        "hours": hours,
        "plan": plan.code,
        "ticket_user_id": ticket_user.id,
        "options": options,
    }


@router.get("/", response_model=list[schemas.ReservationResponse])
def list_reservations(db: Session = Depends(get_db)):
    ticket_service.sweep_tickets(db)
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
    "/options",
    response_model=schemas.ReservationOptionsResponse,
)
def reservation_options(
    payload: schemas.ReservationOptionsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    car = db.query(models.Car).filter(models.Car.id == payload.car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="車が見つかりません")
    member = _resolve_member(db, current_user, payload.member_id)
    ticket_user = _resolve_ticket_user(
        db, current_user, member, payload.ticket_user_id
    )
    return _build_options(db, current_user, payload, member, ticket_user)


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

    member = _resolve_member(db, current_user, reservation.member_id)
    ticket_user = _resolve_ticket_user(
        db, current_user, member, reservation.ticket_user_id
    )

    options = _build_options(db, current_user, reservation, member, ticket_user)
    if options["blocked_reason"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=options["blocked_reason"],
        )

    selected = next(
        (
            option
            for option in options["options"]
            if option["type"] == reservation.payment_type
        ),
        None,
    )
    if selected is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="選択した支払い方法は利用できません。日時を変更してください。",
        )

    ticket = None
    if reservation.payment_type == "ticket":
        ticket_id = selected.get("ticket_id")
        ticket = (
            db.query(models.TimeTicket)
            .filter(models.TimeTicket.id == ticket_id)
            .first()
        )
        if not ticket or ticket.status != "available":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="6時間券の空きがありません。もう一度選択してください。",
            )

    data = reservation.model_dump()
    data.pop("payment_type", None)
    data.pop("ticket_user_id", None)
    data["member_id"] = member.id
    db_reservation = models.Reservation(**data)
    db.add(db_reservation)
    db.flush()

    if ticket is not None:
        ticket_service.reserve_ticket(ticket, db_reservation.id)

    charge = models.ReservationCharge(
        reservation_id=db_reservation.id,
        car_id=db_reservation.car_id,
        ticket_user_id=ticket_user.id,
        ticket_id=ticket.id if ticket else None,
        payment_type=reservation.payment_type,
        duration_minutes=options["hours"] * 60,
        vehicle_value=selected["vehicle_value"],
        incremental_amount=selected["incremental_amount"],
        overflow_amount=selected["overflow_amount"],
        reservation_start=db_reservation.start_time,
        reservation_end=db_reservation.end_time,
        snapshot=json.dumps(
            {
                "plan": options["plan"],
                "ticket_source": selected.get("ticket_source"),
                "ticket_value": selected.get("ticket_value"),
            },
            ensure_ascii=False,
        ),
    )
    db.add(charge)

    key_service.schedule_reservation_key(
        db, db_reservation, ticket_user, pricing.now_jst()
    )

    db.commit()
    db.refresh(db_reservation)
    return db_reservation


@router.delete("/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reservation(
    reservation_id: int,
    request: Request,
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

    now = pricing.now_jst()
    charge = reservation.charge
    if charge and charge.ticket_id:
        ticket = (
            db.query(models.TimeTicket)
            .filter(models.TimeTicket.id == charge.ticket_id)
            .first()
        )
        if ticket:
            if current_user.role == "admin" or pricing.can_return_ticket(
                reservation.start_time, now
            ):
                ticket_service.release_ticket(ticket)
            else:
                ticket_service.consume_ticket(ticket)
            ticket.reservation_id = None

    if charge:
        charge.status = "cancelled"
        charge.reservation_id = None

    key_service.revoke_reservation_keys(db, reservation, current_user, request)

    if reservation.ride_share:
        db.delete(reservation.ride_share)

    db.delete(reservation)
    db.commit()
