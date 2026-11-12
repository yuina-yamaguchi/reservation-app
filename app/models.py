from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    plate = Column(String(100), nullable=False)
    color = Column(String(50), nullable=False)

    reservations = relationship("Reservation", back_populates="car")
    profile = relationship(
        "CarProfile",
        back_populates="car",
        uselist=False,
        cascade="all, delete-orphan",
    )
    key_device = relationship(
        "KeyDevice",
        back_populates="car",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def seat_capacity(self) -> int:
        return self.profile.seat_capacity if self.profile else 4

    @property
    def key_supported(self) -> bool:
        return bool(self.key_device and self.key_device.status == "active")


class CarProfile(Base):
    __tablename__ = "car_profiles"

    car_id = Column(Integer, ForeignKey("cars.id"), primary_key=True)
    seat_capacity = Column(Integer, nullable=False, default=4)

    car = relationship("Car", back_populates="profile")


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)

    reservations = relationship("Reservation", back_populates="member")
    users = relationship("User", viewonly=True)

    @property
    def username(self) -> str | None:
        return self.users[0].username if self.users else None


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    member_id = Column(Integer, ForeignKey("members.id"), nullable=True)

    member = relationship("Member")
    profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tickets = relationship(
        "TimeTicket",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def plan(self) -> str:
        return self.profile.plan if self.profile else "none"

    @property
    def gender(self) -> str:
        return self.profile.gender if self.profile else "unspecified"

    @property
    def provider_recipient_id(self) -> str | None:
        return self.profile.provider_recipient_id if self.profile else None


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    plan = Column(String(20), nullable=False, default="none")
    plan_started_on = Column(Date, nullable=True)
    gender = Column(String(20), nullable=False, default="unspecified")
    provider_recipient_id = Column(String(200), nullable=True)

    user = relationship("User", back_populates="profile")


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        Index("ix_reservations_car_id_start_time", "car_id", "start_time"),
    )

    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    note = Column(String(500), nullable=False, default="")
    note_public = Column(Boolean, nullable=False, default=False)

    car = relationship("Car", back_populates="reservations")
    member = relationship("Member", back_populates="reservations")
    charge = relationship(
        "ReservationCharge",
        back_populates="reservation",
        uselist=False,
    )
    ride_share = relationship(
        "RideShare",
        back_populates="reservation",
        uselist=False,
        cascade="all, delete-orphan",
    )

    digital_keys_rel = relationship(
        "DigitalKey",
        primaryjoin="and_(DigitalKey.reservation_id == Reservation.id, DigitalKey.purpose == 'reservation')",
        foreign_keys="DigitalKey.reservation_id",
        order_by="DigitalKey.id.desc()",
        lazy="select",
        viewonly=True,
    )

    @property
    def digital_key(self):
        keys = self.digital_keys_rel
        return keys[0] if keys else None


class ReservationCharge(Base):
    __tablename__ = "reservation_charges"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(
        Integer, ForeignKey("reservations.id"), nullable=True, unique=True, index=True
    )
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    ticket_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticket_id = Column(Integer, ForeignKey("time_tickets.id"), nullable=True)
    payment_type = Column(String(20), nullable=False, default="time")
    duration_minutes = Column(Integer, nullable=False, default=0)
    vehicle_value = Column(Integer, nullable=False, default=0)
    incremental_amount = Column(Integer, nullable=False, default=0)
    overflow_amount = Column(Integer, nullable=False, default=0)
    seat_fee_total = Column(Integer, nullable=False, default=0)
    discount_applied = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="active")
    reservation_start = Column(DateTime, nullable=True)
    reservation_end = Column(DateTime, nullable=True)
    snapshot = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    reservation = relationship("Reservation", back_populates="charge")
    ticket_user = relationship("User")
    ticket = relationship("TimeTicket")

    @property
    def actual_burden(self) -> int:
        return max(0, self.incremental_amount - self.discount_applied)


class TimeTicket(Base):
    __tablename__ = "time_tickets"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "period", "source", "slot", name="uq_ticket_period_slot"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    period = Column(String(7), nullable=False, index=True)
    source = Column(String(20), nullable=False, default="included")
    slot = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="available", index=True)
    hours = Column(Integer, nullable=False, default=6)
    price = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=False)
    granted_at = Column(DateTime, nullable=False, default=datetime.now)
    reservation_id = Column(
        Integer, ForeignKey("reservations.id"), nullable=True, index=True
    )

    user = relationship("User", back_populates="tickets")
    reservation = relationship("Reservation")


class RideShare(Base):
    __tablename__ = "ride_shares"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(
        Integer, ForeignKey("reservations.id"), nullable=False, unique=True
    )
    driver_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    area = Column(String(10), nullable=False, default="near")
    seat_fee = Column(Integer, nullable=False, default=300)
    gender_filter = Column(String(10), nullable=False, default="any")
    seats_offered = Column(Integer, nullable=False, default=1)
    driver_guest_seats = Column(Integer, nullable=False, default=0)
    note = Column(String(500), nullable=False, default="")
    note_public = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="open", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    reservation = relationship("Reservation", back_populates="ride_share")
    driver = relationship("User")
    applications = relationship(
        "RideApplication",
        back_populates="ride",
        cascade="all, delete-orphan",
    )


class RideApplication(Base):
    __tablename__ = "ride_applications"
    __table_args__ = (
        UniqueConstraint("ride_id", "applicant_user_id", name="uq_ride_applicant"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("ride_shares.id"), nullable=False, index=True)
    applicant_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    seat_fee = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    decided_at = Column(DateTime, nullable=True)

    ride = relationship("RideShare", back_populates="applications")
    applicant = relationship("User")


class MonthlyPlanCharge(Base):
    __tablename__ = "monthly_plan_charges"
    __table_args__ = (
        UniqueConstraint("user_id", "period", name="uq_monthly_plan_period"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    period = Column(String(7), nullable=False, index=True)
    plan = Column(String(20), nullable=False, default="none")
    plan_fee = Column(Integer, nullable=False, default=0)

    user = relationship("User")


class KeyDevice(Base):
    __tablename__ = "key_devices"

    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, unique=True)
    provider = Column(String(50), nullable=False, default="mock")
    provider_device_id = Column(String(200), nullable=False)
    display_name = Column(String(200), nullable=False, default="")
    status = Column(String(20), nullable=False, default="active")
    last_synced_at = Column(DateTime, nullable=True)
    metadata_json = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    car = relationship("Car", back_populates="key_device")


class DigitalKey(Base):
    __tablename__ = "digital_keys"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(
        Integer, ForeignKey("reservations.id"), nullable=True, index=True
    )
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    recipient_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    device_id = Column(Integer, ForeignKey("key_devices.id"), nullable=True)
    provider_key_id = Column(String(200), nullable=True)
    purpose = Column(String(20), nullable=False, default="reservation", index=True)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=False)
    issue_after = Column(DateTime, nullable=True)
    status = Column(String(30), nullable=False, default="scheduled", index=True)
    issued_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    last_error = Column(String(1000), nullable=False, default="")
    reason = Column(String(500), nullable=False, default="")
    requested_ip = Column(String(100), nullable=False, default="")
    requested_user_agent = Column(String(500), nullable=False, default="")
    was_in_use = Column(Boolean, nullable=False, default=False)
    lock_state = Column(String(20), nullable=False, default="locked")
    reservation_snapshot = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    car = relationship("Car")
    recipient = relationship("User")
    device = relationship("KeyDevice")
    reservation = relationship(
        "Reservation",
        backref="_digital_keys",
    )


class KeyAuditEvent(Base):
    __tablename__ = "key_audit_events"

    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    digital_key_id = Column(
        Integer, ForeignKey("digital_keys.id"), nullable=True, index=True
    )
    action = Column(String(30), nullable=False)
    result = Column(String(20), nullable=False)
    reason = Column(String(500), nullable=False, default="")
    ip = Column(String(100), nullable=False, default="")
    user_agent = Column(String(500), nullable=False, default="")
    detail = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    actor = relationship("User")
    digital_key = relationship("DigitalKey")



class EmergencyAlert(Base):
    __tablename__ = "emergency_alerts"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True, index=True)
    reporter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    message = Column(String(500), nullable=False, default="")
    status = Column(String(20), nullable=False, default="open", index=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    reservation = relationship("Reservation")
    reporter = relationship("User", foreign_keys=[reporter_user_id])
    car = relationship("Car")
