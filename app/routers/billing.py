from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from .. import models, pricing, schemas, ticket_service
from ..auth import require_auth
from ..database import get_db

router = APIRouter(prefix="/billing", tags=["月別利用額"])


def _resolve_user(
    db: Session,
    current_user: models.User,
    user_id: int | None,
) -> models.User:
    if user_id is None or user_id == current_user.id:
        return current_user
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="他のユーザーの利用額は管理者のみ確認できます",
        )
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    return user


def _parse_month(month: str | None) -> str:
    if not month:
        return pricing.month_period(pricing.now_jst())
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="month は YYYY-MM 形式で指定してください",
        ) from exc
    return pricing.month_period(parsed)


@router.get("/me", response_model=schemas.MonthlyBillingResponse)
def my_billing(
    month: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    return _billing(db, current_user, current_user, _parse_month(month))


@router.get("/users/{user_id}", response_model=schemas.MonthlyBillingResponse)
def user_billing(
    user_id: int,
    month: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_auth),
):
    user = _resolve_user(db, current_user, user_id)
    return _billing(db, current_user, user, _parse_month(month))


def _billing(
    db: Session,
    current_user: models.User,
    user: models.User,
    month: str,
) -> dict:
    now = pricing.now_jst()
    if month == pricing.month_period(now):
        ticket_service.ensure_monthly_plan_charge(db, user, now)
        ticket_service.ensure_monthly_tickets(db, user, now)
    ticket_service.sweep_tickets(db, now)

    range_start, range_end = pricing.month_range(month)
    entries: list[dict] = []

    monthly_charge = (
        db.query(models.MonthlyPlanCharge)
        .filter(
            models.MonthlyPlanCharge.user_id == user.id,
            models.MonthlyPlanCharge.period == month,
        )
        .first()
    )
    plan = pricing.plan_for(monthly_charge.plan if monthly_charge else user.plan)
    plan_fee = monthly_charge.plan_fee if monthly_charge else 0
    if plan_fee:
        entries.append(
            {
                "kind": "plan",
                "date": range_start.date().isoformat(),
                "description": f"月額プラン（{plan.name}）",
                "amount": plan_fee,
            }
        )

    ticket_purchases = 0
    tickets = (
        db.query(models.TimeTicket)
        .filter(
            models.TimeTicket.user_id == user.id,
            models.TimeTicket.period == month,
            models.TimeTicket.source.in_(["extra", "pack"]),
        )
        .order_by(models.TimeTicket.id)
        .all()
    )
    for ticket in tickets:
        ticket_purchases += ticket.price
        source_label = "6時間パック" if ticket.source == "pack" else "追加6時間券"
        entries.append(
            {
                "kind": "ticket",
                "date": ticket.granted_at.date().isoformat(),
                "description": f"{source_label}（{ticket.period}）",
                "amount": ticket.price,
            }
        )

    usage_charges = 0
    charges = (
        db.query(models.ReservationCharge)
        .options(
            joinedload(models.ReservationCharge.reservation).joinedload(
                models.Reservation.car
            )
        )
        .filter(
            models.ReservationCharge.ticket_user_id == user.id,
            models.ReservationCharge.status == "active",
            models.ReservationCharge.reservation_start >= range_start,
            models.ReservationCharge.reservation_start < range_end,
        )
        .order_by(models.ReservationCharge.reservation_start)
        .all()
    )
    for charge in charges:
        usage_charges += charge.incremental_amount
        car_name = (
            charge.reservation.car.name
            if charge.reservation and charge.reservation.car
            else "車"
        )
        entries.append(
            {
                "kind": "usage",
                "date": charge.reservation_start.date().isoformat(),
                "description": f"{car_name}の利用"
                + ("（6時間券）" if charge.payment_type == "ticket" else "（時間券）"),
                "payment_type": charge.payment_type,
                "vehicle_value": charge.vehicle_value,
                "incremental_amount": charge.incremental_amount,
                "discount_applied": charge.discount_applied,
                "actual_burden": charge.actual_burden,
                "amount": charge.actual_burden,
            }
        )

    seat_fees_paid = 0
    my_applications = (
        db.query(models.RideApplication)
        .options(joinedload(models.RideApplication.ride).joinedload(
            models.RideShare.reservation
        ))
        .filter(
            models.RideApplication.applicant_user_id == user.id,
            models.RideApplication.status == "accepted",
        )
        .order_by(models.RideApplication.decided_at)
        .all()
    )
    for application in my_applications:
        ride = application.ride
        if not ride or ride.status == "cancelled" or not ride.reservation:
            continue
        start = ride.reservation.start_time
        if not (range_start <= start < range_end):
            continue
        seat_fees_paid += application.seat_fee
        entries.append(
            {
                "kind": "carpool_seat",
                "date": start.date().isoformat(),
                "description": "相乗り席代",
                "amount": application.seat_fee,
            }
        )

    discount_received = 0
    driven_rides = (
        db.query(models.RideShare)
        .options(
            joinedload(models.RideShare.reservation),
            joinedload(models.RideShare.applications),
        )
        .filter(models.RideShare.driver_user_id == user.id)
        .all()
    )
    for ride in driven_rides:
        if ride.status == "cancelled" or not ride.reservation:
            continue
        start = ride.reservation.start_time
        if not (range_start <= start < range_end):
            continue
        for application in ride.applications:
            if application.status == "accepted":
                discount_received += application.seat_fee
    if discount_received:
        entries.append(
            {
                "kind": "carpool_discount",
                "date": range_start.date().isoformat(),
                "description": "相乗り値引き",
                "amount": -discount_received,
            }
        )

    total = (
        plan_fee + ticket_purchases + usage_charges + seat_fees_paid - discount_received
    )
    return {
        "month": month,
        "user_id": user.id,
        "plan": plan.code,
        "plan_fee": plan_fee,
        "ticket_purchases": ticket_purchases,
        "usage_charges": usage_charges,
        "carpool_seat_fees_paid": seat_fees_paid,
        "carpool_discount_received": discount_received,
        "total": max(0, total),
        "entries": entries,
    }
