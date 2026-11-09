"""料金・券・予約ルールの計算ロジック。"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

import jpholiday

JST = timezone(timedelta(hours=9))

PLAN_NONE = "none"
PLAN_LIGHT = "light"
PLAN_STANDARD = "standard"

HOURLY_RATE = 700
SIX_HOUR_PRICE = 4200
EXTRA_SIX_HOUR_PRICE = 3800
OVERFLOW_HOURLY_RATE = 700
OVERFLOW_CAP = 2400
TICKET_HOURS = 6
KEY_VALID_BEFORE_MINUTES = 10
KEY_VALID_AFTER_MINUTES = 15
KEY_ISSUE_BEFORE_MINUTES = 10
RESERVATION_BUFFER_MINUTES = 30
WEEKEND_RESERVATION_LIMIT = 2
TICKET_BOOKING_DAYS = 30
TIME_BOOKING_DAYS = 14
CARPOOL_NEAR_FEE = 300
CARPOOL_FAR_FEE = 500


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    monthly_fee: int
    included_tickets: int
    extra_six_hour_price: int
    hourly_rate: int
    ticket_value: int
    carry_over: bool

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "monthly_fee": self.monthly_fee,
            "included_tickets": self.included_tickets,
            "extra_six_hour_price": self.extra_six_hour_price,
            "hourly_rate": self.hourly_rate,
            "ticket_value": self.ticket_value,
            "carry_over": self.carry_over,
        }


PLANS: dict[str, Plan] = {
    PLAN_NONE: Plan(
        code=PLAN_NONE,
        name="時間券のみ",
        monthly_fee=0,
        included_tickets=0,
        extra_six_hour_price=SIX_HOUR_PRICE,
        hourly_rate=HOURLY_RATE,
        ticket_value=SIX_HOUR_PRICE,
        carry_over=False,
    ),
    PLAN_LIGHT: Plan(
        code=PLAN_LIGHT,
        name="ライト",
        monthly_fee=3900,
        included_tickets=1,
        extra_six_hour_price=EXTRA_SIX_HOUR_PRICE,
        hourly_rate=HOURLY_RATE,
        ticket_value=3900,
        carry_over=True,
    ),
    PLAN_STANDARD: Plan(
        code=PLAN_STANDARD,
        name="スタンダード",
        monthly_fee=8000,
        included_tickets=3,
        extra_six_hour_price=EXTRA_SIX_HOUR_PRICE,
        hourly_rate=HOURLY_RATE,
        ticket_value=2667,
        carry_over=True,
    ),
}


def plan_for(code: str | None) -> Plan:
    return PLANS.get(code or PLAN_NONE, PLANS[PLAN_NONE])


def now_jst() -> datetime:
    """現在時刻をJSTのnaive datetimeで返す。"""
    return datetime.now(JST).replace(tzinfo=None)


def to_jst_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(JST).replace(tzinfo=None)
    return value


def billable_hours(start: datetime, end: datetime) -> int:
    seconds = (end - start).total_seconds()
    hours = int(seconds // 3600)
    if seconds % 3600:
        hours += 1
    return max(1, hours)


def overflow_amount(hours: int) -> int:
    return min(OVERFLOW_HOURLY_RATE * max(0, hours - TICKET_HOURS), OVERFLOW_CAP)


def is_weekend_or_holiday(value: datetime | date) -> bool:
    day = value.date() if isinstance(value, datetime) else value
    return day.weekday() >= 5 or jpholiday.is_holiday(day)


def month_period(value: datetime | date) -> str:
    day = value.date() if isinstance(value, datetime) else value
    return f"{day.year:04d}-{day.month:02d}"


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    index = month - 1 + delta
    return year + index // 12, index % 12 + 1


def period_expiry(period: str) -> datetime:
    """発行月の翌月末23:59:59。"""
    year, month = (int(part) for part in period.split("-"))
    next_year, next_month = _add_months(year, month, 2)
    return datetime.combine(
        date(next_year, next_month, 1) - timedelta(days=1),
        time(23, 59, 59),
    )


def booking_window_days(payment_type: str) -> int:
    if payment_type in ("ticket", "ticket_2", "ticket_overflow"):
        return TICKET_BOOKING_DAYS
    return TIME_BOOKING_DAYS


def days_ahead(start: datetime, now: datetime | None = None) -> int:
    now = now or now_jst()
    return (to_jst_naive(start).date() - now.date()).days


def key_validity(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    return (
        start - timedelta(minutes=KEY_VALID_BEFORE_MINUTES),
        end + timedelta(minutes=KEY_VALID_AFTER_MINUTES),
    )


def key_issue_after(start: datetime) -> datetime:
    return start - timedelta(minutes=KEY_ISSUE_BEFORE_MINUTES)


def handover_buffer() -> timedelta:
    return timedelta(minutes=RESERVATION_BUFFER_MINUTES)


def cancellation_deadline(start: datetime) -> datetime:
    day = to_jst_naive(start).date()
    days_before = 7 if is_weekend_or_holiday(day) else 3
    deadline_day = day - timedelta(days=days_before)
    return datetime.combine(deadline_day, time(23, 59, 59))


def can_return_ticket(start: datetime, now: datetime | None = None) -> bool:
    now = now or now_jst()
    return now <= cancellation_deadline(start)


def time_option(hours: int, plan_code: str) -> dict:
    plan = plan_for(plan_code)
    if hours <= TICKET_HOURS:
        amount = plan.hourly_rate * hours
        overflow = 0
    else:
        amount = SIX_HOUR_PRICE + overflow_amount(hours)
        overflow = overflow_amount(hours)
    return {
        "type": "time",
        "label": f"時間券（1時間{plan.hourly_rate}円）",
        "hours": hours,
        "total": amount,
        "vehicle_value": amount,
        "incremental_amount": amount,
        "overflow_amount": overflow,
        "ticket_id": None,
        "ticket_source": None,
        "ticket_value": None,
        "ticket_expires_at": None,
    }


def ticket_option(hours: int, ticket) -> dict:
    overflow = overflow_amount(hours)
    value = ticket.price or plan_for(
        getattr(ticket.user, "plan", None) if ticket.user else None
    ).ticket_value
    return {
        "type": "ticket",
        "label": "6時間券を使う",
        "hours": hours,
        "total": overflow,
        "vehicle_value": value + overflow,
        "incremental_amount": overflow,
        "overflow_amount": overflow,
        "ticket_id": ticket.id,
        "ticket_source": ticket.source,
        "ticket_value": value,
        "ticket_expires_at": ticket.expires_at,
    }


def reservation_payment_options(
    hours: int,
    plan: Plan,
    available_tickets: list,
    ticket_allowed: bool,
    time_allowed: bool,
) -> list[dict]:
    opts: list[dict] = []
    if hours <= TICKET_HOURS:
        if ticket_allowed and available_tickets:
            opts.append(ticket_option(hours, available_tickets[0]))
        if time_allowed:
            opts.append(time_option(hours, plan.code))
        return opts
    # hours > 6
    if plan.code == PLAN_NONE:
        if time_allowed:
            opts.append(time_option(hours, plan.code))
        return opts
    # light / standard: 3 options
    if len(available_tickets) >= 2:
        t1, t2 = available_tickets[0], available_tickets[1]
        v1 = t1.price or plan.ticket_value
        v2 = t2.price or plan.ticket_value
        opts.append(
            {
                "type": "ticket_2",
                "label": "6時間券2枚分で予約（追加課金なし）",
                "hours": hours,
                "total": 0,
                "vehicle_value": v1 + v2,
                "incremental_amount": 0,
                "overflow_amount": 0,
                "ticket_id": t1.id,
                "ticket_source": t1.source,
                "ticket_value": v1,
                "ticket_expires_at": t1.expires_at,
                "ticket_2_id": t2.id,
                "ticket_2_source": t2.source,
                "ticket_2_value": v2,
            }
        )
    if ticket_allowed and available_tickets:
        t = available_tickets[0]
        v = t.price or plan.ticket_value
        ov = overflow_amount(hours)
        opts.append(
            {
                "type": "ticket_overflow",
                "label": "6時間券＋超過分時間料金（上限2,400円）",
                "hours": hours,
                "total": ov,
                "vehicle_value": v + ov,
                "incremental_amount": ov,
                "overflow_amount": ov,
                "ticket_id": t.id,
                "ticket_source": t.source,
                "ticket_value": v,
                "ticket_expires_at": t.expires_at,
            }
        )
    if time_allowed:
        opts.append(
            {
                "type": "time_all",
                "label": f"すべて時間料金（1時間{plan.hourly_rate}円）",
                "hours": hours,
                "total": plan.hourly_rate * hours,
                "vehicle_value": plan.hourly_rate * hours,
                "incremental_amount": plan.hourly_rate * hours,
                "overflow_amount": 0,
                "ticket_id": None,
                "ticket_source": None,
                "ticket_value": None,
                "ticket_expires_at": None,
            }
        )
    return opts


def carpool_seat_fee(area: str) -> int:
    return CARPOOL_FAR_FEE if area == "far" else CARPOOL_NEAR_FEE


def current_month_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or now_jst()
    start = datetime(now.year, now.month, 1)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    return start, end


def month_range(period: str) -> tuple[datetime, datetime]:
    year, month = (int(part) for part in period.split("-"))
    start = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = start + timedelta(days=last_day)
    return start, end
