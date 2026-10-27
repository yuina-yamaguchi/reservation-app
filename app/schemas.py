from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


# ── 車 ──────────────────────────────────────────


class CarBase(BaseModel):
    name: str = Field(max_length=100)
    plate: str = Field(max_length=100)
    color: str = Field(max_length=50)

    @field_validator("name", "plate", "color")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("入力してください")
        return value


class CarCreate(CarBase):
    pass


class CarResponse(CarBase):
    id: int

    model_config = {"from_attributes": True}


# ── 住人 ──────────────────────────────────────────


class MemberBase(BaseModel):
    name: str = Field(max_length=100)

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("入力してください")
        return value


class MemberCreate(MemberBase):
    pass


class MemberResponse(MemberBase):
    id: int

    model_config = {"from_attributes": True}


# ── 予約 ──────────────────────────────────────────


class ReservationCreate(BaseModel):
    car_id: int
    member_id: int
    start_time: datetime
    end_time: datetime
    note: str = Field(default="", max_length=500)

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

    model_config = {"from_attributes": True}
