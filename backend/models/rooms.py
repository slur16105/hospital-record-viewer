from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class RoomCreate(BaseModel):
    room_number: str = Field(..., min_length=1, max_length=20)
    department_id: UUID

    @field_validator("room_number")
    @classmethod
    def strip_room_number(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("진료실 번호는 공백만으로 구성될 수 없습니다")
        return v


class RoomUpdate(BaseModel):
    room_number: str | None = Field(None, min_length=1, max_length=20)
    department_id: UUID | None = None
    is_active: bool | None = None

    @field_validator("room_number")
    @classmethod
    def strip_room_number(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("진료실 번호는 공백만으로 구성될 수 없습니다")
        return v


class RoomOut(BaseModel):
    id: UUID
    room_number: str
    department_id: UUID
    department_name: str
    is_active: bool
