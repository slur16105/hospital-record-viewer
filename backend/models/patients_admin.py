from __future__ import annotations
from datetime import date
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class PatientUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    birth_date: date | None = None
    phone: str | None = Field(None, min_length=1, max_length=20)
    is_active: bool | None = None

    @field_validator("name", "phone")
    @classmethod
    def strip_str(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("공백만으로 구성될 수 없습니다")
        return v


class PatientOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    email: str
    birth_date: date
    phone: str
    is_active: bool
    created_at: str
