from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, pricing


def ensure_user_profile(db: Session, user: models.User) -> models.UserProfile:
    if user.profile is None:
        profile = models.UserProfile(user_id=user.id)
        user.profile = profile
        db.add(profile)
        db.flush()
    return user.profile


def ensure_car_profile(db: Session, car: models.Car) -> models.CarProfile:
    if car.profile is None:
        profile = models.CarProfile(car_id=car.id, seat_capacity=4)
        car.profile = profile
        db.add(profile)
        db.flush()
    return car.profile


def ensure_monthly_plan_charge(
    db: Session, user: models.User, now: datetime | None = None
) -> models.MonthlyPlanCharge:
    now = now or pricing.now_jst()
    profile = ensure_user_profile(db, user)
    plan = pricing.plan_for(profile.plan)
    period = pricing.month_period(now)

    charge = (
        db.query(models.MonthlyPlanCharge)
        .filter(
            models.MonthlyPlanCharge.user_id == user.id,
            models.MonthlyPlanCharge.period == period,
        )
        .first()
    )
    if charge is None:
        charge = models.MonthlyPlanCharge(
            user_id=user.id,
            period=period,
            plan=plan.code,
            plan_fee=plan.monthly_fee,
        )
        db.add(charge)
    else:
        charge.plan = plan.code
        charge.plan_fee = plan.monthly_fee
    db.flush()
    return charge


def ensure_monthly_tickets(
    db: Session, user: models.User, now: datetime | None = None
) -> None:
    now = now or pricing.now_jst()
    profile = ensure_user_profile(db, user)
    plan = pricing.plan_for(profile.plan)
    if plan.included_tickets <= 0:
        return
    if profile.plan_started_on and profile.plan_started_on > now.date():
        return

    period = pricing.month_period(now)
    existing = (
        db.query(func.count(models.TimeTicket.id))
        .filter(
            models.TimeTicket.user_id == user.id,
            models.TimeTicket.period == period,
            models.TimeTicket.source == "included",
        )
        .scalar()
    )
    if existing >= plan.included_tickets:
        return

    expiry = pricing.period_expiry(period)
    for slot in range(existing + 1, plan.included_tickets + 1):
        db.add(
            models.TimeTicket(
                user_id=user.id,
                period=period,
                source="included",
                slot=slot,
                status="available",
                hours=pricing.TICKET_HOURS,
                price=plan.ticket_value,
                expires_at=expiry,
                granted_at=now,
            )
        )
    db.flush()


def sweep_tickets(db: Session, now: datetime | None = None) -> None:
    now = now or pricing.now_jst()

    db.query(models.TimeTicket).filter(
        models.TimeTicket.status == "available",
        models.TimeTicket.expires_at < now,
    ).update({models.TimeTicket.status: "expired"}, synchronize_session=False)

    ended = (
        db.query(models.TimeTicket)
        .join(models.Reservation, models.TimeTicket.reservation_id == models.Reservation.id)
        .filter(
            models.TimeTicket.status == "reserved",
            models.Reservation.end_time < now,
        )
        .all()
    )
    for ticket in ended:
        ticket.status = "used"

    users = (
        db.query(models.User)
        .join(models.UserProfile, models.User.id == models.UserProfile.user_id)
        .filter(models.UserProfile.plan.in_(["light", "standard"]))
        .all()
    )
    for user in users:
        ensure_monthly_plan_charge(db, user, now)
        ensure_monthly_tickets(db, user, now)

    db.commit()


def find_available_ticket(
    db: Session, user_id: int, valid_at: datetime
) -> models.TimeTicket | None:
    return (
        db.query(models.TimeTicket)
        .filter(
            models.TimeTicket.user_id == user_id,
            models.TimeTicket.status == "available",
            models.TimeTicket.expires_at >= valid_at,
        )
        .order_by(models.TimeTicket.expires_at, models.TimeTicket.id)
        .first()
    )


def grant_tickets(
    db: Session,
    user: models.User,
    source: str,
    count: int,
    now: datetime | None = None,
) -> list[models.TimeTicket]:
    now = now or pricing.now_jst()
    profile = ensure_user_profile(db, user)
    plan = pricing.plan_for(profile.plan)
    period = pricing.month_period(now)
    expiry = pricing.period_expiry(period)

    if source == "pack":
        price = pricing.SIX_HOUR_PRICE
    elif source == "included":
        price = plan.ticket_value
    else:
        price = plan.extra_six_hour_price

    max_slot = (
        db.query(func.max(models.TimeTicket.slot))
        .filter(
            models.TimeTicket.user_id == user.id,
            models.TimeTicket.period == period,
            models.TimeTicket.source == source,
        )
        .scalar()
        or 0
    )

    tickets = []
    for offset in range(1, count + 1):
        ticket = models.TimeTicket(
            user_id=user.id,
            period=period,
            source=source,
            slot=max_slot + offset,
            status="available",
            hours=pricing.TICKET_HOURS,
            price=price,
            expires_at=expiry,
            granted_at=now,
        )
        db.add(ticket)
        tickets.append(ticket)
    db.commit()
    for ticket in tickets:
        db.refresh(ticket)
    return tickets


def reserve_ticket(ticket: models.TimeTicket, reservation_id: int) -> None:
    ticket.status = "reserved"
    ticket.reservation_id = reservation_id


def release_ticket(ticket: models.TimeTicket) -> None:
    ticket.status = "available"
    ticket.reservation_id = None


def consume_ticket(ticket: models.TimeTicket) -> None:
    ticket.status = "used"
