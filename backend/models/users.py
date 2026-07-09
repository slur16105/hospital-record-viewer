"""통합 사용자 관리 요청 모델 (Story 8.1~8.3, FR-20~22).

코어 모듈 — 병원 도메인 지식 금지 (AD-14).
"""
from __future__ import annotations

import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

# EmailStr(email-validator)는 데모 도메인(@hospital.test 등 예약 TLD)을 거부하므로
# 형식 검사만 수행한다 — core.field_values의 email 필드 검증과 동일 수준.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _strip_nonempty(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("공백만으로 구성될 수 없습니다")
    return v


class UserCreate(BaseModel):
    email: str = Field(..., max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if _EMAIL_RE.fullmatch(v) is None:
            raise ValueError("올바른 이메일 형식이 아닙니다")
        return v
    name: str = Field(..., min_length=1, max_length=100)
    role_ids: list[UUID] = Field(..., min_length=1)
    primary_role_id: UUID
    field_values: dict[str, Any] = Field(default_factory=dict)
    delivery: Literal["invite", "temp_password"]

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_nonempty(v)

    @field_validator("role_ids")
    @classmethod
    def unique_role_ids(cls, v: list[UUID]) -> list[UUID]:
        if len(set(v)) != len(v):
            raise ValueError("role_ids에 중복이 있습니다")
        return v

    @model_validator(mode="after")
    def primary_in_roles(self) -> "UserCreate":
        if self.primary_role_id not in self.role_ids:
            raise ValueError("primary_role_id는 role_ids에 포함되어야 합니다")
        return self


class UserUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(None, min_length=1, max_length=100)
    avatar_url: str | None = Field(None, max_length=2000)
    field_values: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        return v if v is None else _strip_nonempty(v)


class UserRolesUpdate(BaseModel):
    role_ids: list[UUID] = Field(..., min_length=1)
    primary_role_id: UUID

    @field_validator("role_ids")
    @classmethod
    def unique_role_ids(cls, v: list[UUID]) -> list[UUID]:
        if len(set(v)) != len(v):
            raise ValueError("role_ids에 중복이 있습니다")
        return v

    @model_validator(mode="after")
    def primary_in_roles(self) -> "UserRolesUpdate":
        if self.primary_role_id not in self.role_ids:
            raise ValueError("primary_role_id는 role_ids에 포함되어야 합니다")
        return self
