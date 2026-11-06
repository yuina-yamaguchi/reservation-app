import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ROOM_NUMBER_PATTERN = re.compile(r"^[A-Za-z]?-?\d+(?:-\d+)?(?:号室)?$")


# ── 車 ──────────────────────────────────────────


class CarBase(BaseModel):
    name: str = Field(max_length=100)
    plate: str = Field(max_length=100)
    color: str = Field(max_length=50)
    seat_capacity: int = Field(default=4, ge=1, le=10)

    @field_validator("name", "plate", "color")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("入力してください")
        return value


class CarCreate(CarBase):
    pass


class CarResponse(BaseModel):
    id: int
    name: str
    plate: str
    color: str
    seat_capacity: int = 4
    key_supported: bool = False

    model_config = {"from_attributes": True}


# ── 住人 ──────────────────────────────────────────


class MemberBase(BaseModel):
    name: str = Field(max_length=100)


class MemberCreate(MemberBase):
    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("入力してください")
        if ROOM_NUMBER_PATTERN.fullmatch(value):
            raise ValueError("部屋番号は登録できません。名字を入力してください")
        return value


class MemberResponse(MemberBase):
    id: int

    model_config = {"from_attributes": True}


# ── ユーザー ──────────────────────────────────────


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    role: Literal["admin", "user"] = "user"
    member_id: int | None = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("入力してください")
        return value


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: Literal["admin", "user"] | None = None
    member_id: int | None = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("入力してください")
        return value


class UserResponse(BaseModel):
    id: int
    username: str
    role: Literal["admin", "user"]
    member_id: int | None
    member_name: str | None = None
    plan: str = "none"
    gender: str = "unspecified"
    provider_recipient_id: str | None = None


class UserPlanUpdate(BaseModel):
    plan: Literal["none", "light", "standard"]


class UserProfileUpdate(BaseModel):
    gender: Literal["unspecified", "male", "female"] | None = None
    provider_recipient_id: str | None = Field(default=None, max_length=200)

    @field_validator("provider_recipient_id")
    @classmethod
    def normalize_recipient(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TicketGrant(BaseModel):
    source: Literal["extra", "pack", "included"] = "extra"
    count: int = Field(default=1, ge=1, le=10)


# ── 券・料金 ──────────────────────────────────────


class TicketResponse(BaseModel):
    id: int
    user_id: int
    period: str
    source: str
    slot: int
    status: str
    hours: int
    price: int
    expires_at: datetime
    granted_at: datetime
    reservation_id: int | None = None

    model_config = {"from_attributes": True}


class PlanResponse(BaseModel):
    code: str
    name: str
    monthly_fee: int
    included_tickets: int
    extra_six_hour_price: int
    hourly_rate: int
    ticket_value: int
    carry_over: bool


class ChargeResponse(BaseModel):
    id: int
    reservation_id: int | None
    ticket_user_id: int | None
    ticket_id: int | None
    payment_type: str
    duration_minutes: int
    vehicle_value: int
    incremental_amount: int
    overflow_amount: int
    seat_fee_total: int
    discount_applied: int
    actual_burden: int = 0
    status: str

    model_config = {"from_attributes": True}


class ReservationOption(BaseModel):
    type: Literal["ticket", "time"]
    label: str
    hours: int
    total: int
    vehicle_value: int
    incremental_amount: int
    overflow_amount: int
    ticket_id: int | None = None
    ticket_source: str | None = None
    ticket_value: int | None = None
    ticket_expires_at: datetime | None = None


class ReservationOptionsRequest(BaseModel):
    car_id: int
    member_id: int
    start_time: datetime
    end_time: datetime
    ticket_user_id: int | None = None

    @model_validator(mode="after")
    def check_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("終了日時は開始日時より後にしてください")
        return self


class ReservationOptionsResponse(BaseModel):
    car_available: bool
    blocked_reason: str | None = None
    hours: int
    plan: str
    ticket_user_id: int | None = None
    options: list[ReservationOption] = []


# ── 予約 ──────────────────────────────────────────


class ReservationCreate(BaseModel):
    car_id: int
    member_id: int
    start_time: datetime
    end_time: datetime
    note: str = Field(default="", max_length=500)
    payment_type: Literal["ticket", "time"] = "time"
    ticket_user_id: int | None = None

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def check_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("終了日時は開始日時より後にしてください")
        return self


class ReservationResponse(BaseModel):
    id: int
    car_id: int
    member_id: int
    start_time: datetime
    end_time: datetime
    note: str
    car: CarResponse
    member: MemberResponse
    charge: ChargeResponse | None = None
    digital_key: "DigitalKeyResponse | None" = None

    model_config = {"from_attributes": True}


# ── 相乗り ────────────────────────────────────────


class CarpoolCreate(BaseModel):
    reservation_id: int
    area: Literal["near", "far"] = "near"
    gender_filter: Literal["any", "male", "female"] = "any"
    seats_offered: int = Field(default=1, ge=1, le=10)
    driver_guest_seats: int = Field(default=0, ge=0, le=10)
    note: str = Field(default="", max_length=500)
    driver_user_id: int | None = None

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()


class CarpoolUpdate(BaseModel):
    area: Literal["near", "far"] | None = None
    gender_filter: Literal["any", "male", "female"] | None = None
    seats_offered: int | None = Field(default=None, ge=1, le=10)
    driver_guest_seats: int | None = Field(default=None, ge=0, le=10)
    note: str | None = Field(default=None, max_length=500)
    status: Literal["open", "closed", "cancelled"] | None = None

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class RideApplicationResponse(BaseModel):
    id: int
    ride_id: int
    applicant_user_id: int
    applicant_name: str | None = None
    status: str
    seat_fee: int
    created_at: datetime
    decided_at: datetime | None = None

    model_config = {"from_attributes": True}


class CarpoolResponse(BaseModel):
    id: int
    reservation_id: int
    driver_user_id: int
    driver_name: str | None = None
    car_id: int
    car_name: str | None = None
    start_time: datetime
    end_time: datetime
    area: str
    seat_fee: int
    gender_filter: str
    seats_offered: int
    driver_guest_seats: int
    remaining_seats: int
    note: str
    status: str
    applications: list[RideApplicationResponse] = []

    model_config = {"from_attributes": True}


# ── 月別利用額 ────────────────────────────────────


class BillingEntry(BaseModel):
    kind: str
    date: str
    description: str
    payment_type: str | None = None
    vehicle_value: int = 0
    incremental_amount: int = 0
    seat_fee_total: int = 0
    discount_applied: int = 0
    actual_burden: int = 0
    amount: int = 0


class MonthlyBillingResponse(BaseModel):
    month: str
    user_id: int
    plan: str
    plan_fee: int
    ticket_purchases: int
    usage_charges: int
    carpool_seat_fees_paid: int
    carpool_discount_received: int
    total: int
    entries: list[BillingEntry] = []


# ── デジタルキー ──────────────────────────────────


class KeyDeviceCreate(BaseModel):
    car_id: int
    provider: str = Field(default="mock", max_length=50)
    provider_device_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(default="", max_length=200)
    status: Literal["active", "inactive"] = "active"

    @field_validator("provider_device_id", "display_name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class KeyDeviceUpdate(BaseModel):
    provider: str | None = Field(default=None, max_length=50)
    provider_device_id: str | None = Field(default=None, min_length=1, max_length=200)
    display_name: str | None = Field(default=None, max_length=200)
    status: Literal["active", "inactive"] | None = None


class KeyDeviceResponse(BaseModel):
    id: int
    car_id: int
    car_name: str | None = None
    provider: str
    provider_device_id: str
    display_name: str
    status: str
    last_synced_at: datetime | None

    model_config = {"from_attributes": True}


class DigitalKeyResponse(BaseModel):
    id: int
    reservation_id: int | None
    car_id: int
    recipient_user_id: int | None
    provider_key_id: str | None
    purpose: str
    valid_from: datetime
    valid_to: datetime
    issue_after: datetime | None
    status: str
    issued_at: datetime | None
    revoked_at: datetime | None
    last_error: str
    reason: str
    was_in_use: bool

    model_config = {"from_attributes": True}


class MasterKeyRequest(BaseModel):
    password: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)
    confirm_in_use: bool = False

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("利用理由を入力してください")
        return value


class RemoteUnlockRequest(BaseModel):
    password: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)
    confirm_in_use: bool = False


class KeyAuditResponse(BaseModel):
    id: int
    car_id: int
    actor_user_id: int | None
    actor_name: str | None = None
    digital_key_id: int | None
    action: str
    result: str
    reason: str
    ip: str
    user_agent: str
    detail: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 状態 ──────────────────────────────────────────


class StateResponse(BaseModel):
    cars: list[CarResponse]
    members: list[MemberResponse]
    reservations: list[ReservationResponse]
    users: list[UserResponse] = []
    plans: list[PlanResponse] = []
    profile: UserResponse | None = None
    tickets: list[TicketResponse] = []
    carpools: list[CarpoolResponse] = []
    my_applications: list[RideApplicationResponse] = []
    key_devices: list[KeyDeviceResponse] = []
    digital_keys: list[DigitalKeyResponse] = []
    master_keys: list[DigitalKeyResponse] = []


ReservationResponse.model_rebuild()
