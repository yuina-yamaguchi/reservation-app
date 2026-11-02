from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    plate = Column(String(100), nullable=False)
    color = Column(String(50), nullable=False)

    reservations = relationship("Reservation", back_populates="car")


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)

    reservations = relationship("Reservation", back_populates="member")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    member_id = Column(Integer, ForeignKey("members.id"), nullable=True)

    member = relationship("Member")


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

    car = relationship("Car", back_populates="reservations")
    member = relationship("Member", back_populates="reservations")
