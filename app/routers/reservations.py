import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload, selectinload

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
        joinedload(models.Reservation.member).selectinload(models.Member.users),
        joinedload(models.Reservation.charge),
        joinedload(models.Reservation.ride_share).joinedload(
            models.RideShare.applications
        ),
    )


def can_view_reservation_note(
    reservation: models.Reservation, current_user: models.User
) -> bool:
    if reservation.note_public:
        return True
    return (
        current_user.member_id is not None
        and reservation.member_id == current_user.member_id
    )


def reservation_to_response(
    reservation: models.Reservation, current_user: models.User
) -> dict:
    data = schemas.ReservationResponse.model_validate(reservation).model_dump()
    if not can_view_reservation_note(reservation, current_user):
        data["note"] = ""

    charge = data.get("charge")
    if charge:
        is_owner = current_user.role == "admin" or charge.get("ticket_user_id") == current_user.id
        if not is_owner:
            charge["payment_type"] = ""
            charge["vehicle_value"] = 0
            charge["incremental_amount"] = 0
            charge["overflow_amount"] = 0
            charge["seat_fee_total"] = 0
            charge["discount_applied"] = 0
            charge["actual_burden"] = 0

    ride_share = reservation.ride_share
    data["ride_share"] = (
        {
            "status": ride_share.status,
            "driver_user_id": ride_share.driver_user_id,
            "applications": [
                {
                    "applicant_user_id": application.applicant_user_id,
                    "status": application.status,
                }
                for application in ride_share.applications
            ],
        }
        if ride_share
        else None
    )
    return data


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
        available_tickets: list[models.TimeTicket] = []
        if ticket:
            available_tickets.append(ticket)
            second = (
                db.query(models.TimeTicket)
                .filter(
                    models.TimeTicket.user_id == ticket_user.id,
                    models.TimeTicket.status == "available",
                    models.TimeTicket.expires_at >= start,
                    models.TimeTicket.id != ticket.id,
                )
                .order_by(models.TimeTicket.expires_at, models.TimeTicket.id)
                .first()
            )
            if second:
                available_tickets.append(second)
        ticket_allowed = bool(available_tickets) and (
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
            options.extend(
                pricing.reservation_payment_options(
                    hours, plan, available_tickets, ticket_allowed, time_allowed
                )
            )

    return {
        "car_available": conflict is None,
        "blocked_reason": blocked_reason,
        "hours": hours,
        "plan": plan.code,
        "ticket_user_id": ticket_user.id,
        "options": options,
    }


@router.get("/", response_model=list[schemas.ReservationResponse])
def list_reservations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    ticket_service.sweep_tickets(db)
    reservations = (
        _with_relations(db).order_by(models.Reservation.start_time).all()
    )
    return [
        reservation_to_response(reservation, current_user)
        for reservation in reservations
    ]


@router.get("/{reservation_id}", response_model=schemas.ReservationResponse)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    reservation = (
        _with_relations(db)
        .filter(models.Reservation.id == reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="予約が見つかりません")
    return reservation_to_response(reservation, current_user)


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
    ticket_2 = None
    if reservation.payment_type in ("ticket", "ticket_overflow"):
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
    elif reservation.payment_type == "ticket_2":
        ticket_id = selected.get("ticket_id")
        ticket = (
            db.query(models.TimeTicket)
            .filter(models.TimeTicket.id == ticket_id)
            .first()
        )
        ticket_2_id = selected.get("ticket_2_id")
        ticket_2 = (
            db.query(models.TimeTicket)
            .filter(models.TimeTicket.id == ticket_2_id)
            .first()
        )
        if not ticket or ticket.status != "available":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="6時間券の空きがありません。もう一度選択してください。",
            )
        if not ticket_2 or ticket_2.status != "available":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="2枚目の6時間券の空きがありません。もう一度選択してください。",
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
    if ticket_2 is not None:
        ticket_service.reserve_ticket(ticket_2, db_reservation.id)

    snapshot_data = {
        "plan": options["plan"],
        "ticket_source": selected.get("ticket_source"),
        "ticket_value": selected.get("ticket_value"),
    }
    if reservation.payment_type == "ticket_2":
        snapshot_data["ticket_2_source"] = selected.get("ticket_2_source")
        snapshot_data["ticket_2_value"] = selected.get("ticket_2_value")

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
        snapshot=json.dumps(snapshot_data, ensure_ascii=False),
    )
    db.add(charge)

    key_service.schedule_reservation_key(
        db, db_reservation, ticket_user, pricing.now_jst()
    )

    db.commit()
    db.refresh(db_reservation)
    return reservation_to_response(db_reservation, current_user)


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

    # ticket_2 の2枚目チケットも解放/消費
    if charge and charge.payment_type == "ticket_2" and charge.snapshot:
        try:
            snapshot = json.loads(charge.snapshot)
            ticket_2_id = snapshot.get("ticket_2_id")
            if ticket_2_id:
                ticket_2 = (
                    db.query(models.TimeTicket)
                    .filter(models.TimeTicket.id == ticket_2_id)
                    .first()
                )
                if ticket_2:
                    if current_user.role == "admin" or pricing.can_return_ticket(
                        reservation.start_time, now
                    ):
                        ticket_service.release_ticket(ticket_2)
                    else:
                        ticket_service.consume_ticket(ticket_2)
                    ticket_2.reservation_id = None
        except (json.JSONDecodeError, AttributeError):
            pass

    if charge:
        charge.status = "cancelled"
        charge.reservation_id = None
        # 相乗り承認済み予約を運転者がキャンセルした旨を記録
        if reservation.ride_share:
            try:
                snapshot = json.loads(charge.snapshot) if charge.snapshot else {}
            except (json.JSONDecodeError, AttributeError):
                snapshot = {}
            snapshot["cancelled_by_driver"] = True
            charge.snapshot = json.dumps(snapshot, ensure_ascii=False)

    key_service.revoke_reservation_keys(db, reservation, current_user, request)

    if reservation.ride_share:
        db.delete(reservation.ride_share)

    db.delete(reservation)
    db.commit()
