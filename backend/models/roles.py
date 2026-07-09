"""역할·권한·필드 관리 요청 모델 (Story 7.2~7.4).

코어 모듈 — 병원 도메인 지식 금지 (AD-14).
field_type 허용값은 core.field_values.FIELD_TYPE_COLUMNS(=DB enum과 동기화)를 따른다.
"""
from __future__ import annotations

import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from core.field_values import FIELD_TYPE_COLUMNS

# DB field_type enum과 동기화된 허용값 (AD-13 — 단일 원본은 field_values)
FIELD_TYPES = tuple(sorted(FIELD_TYPE_COLUMNS))

_FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,49}$")


def _strip_nonempty(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("공백만으로 구성될 수 없습니다")
    return v


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_nonempty(v)


class RoleUpdate(BaseModel):
    model_config = {"extra": "forbid"}  # is_system 등 비허용 필드 차단

    name: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = Field(None, max_length=500)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        return v if v is None else _strip_nonempty(v)


class RolePermissionsUpdate(BaseModel):
    permission_ids: list[UUID]


class RoleFieldCreate(BaseModel):
    field_key: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=100)
    field_type: Literal[
        "boolean", "date", "email", "json", "multiselect",
        "number", "phone", "reference", "select", "text",
    ]
    is_required: bool = False
    is_unique: bool = False
    is_searchable: bool = False
    sort_order: int = 0
    default_value: str | None = None
    placeholder: str | None = Field(None, max_length=200)
    help_text: str | None = None
    validation: dict[str, Any] | None = None
    options: dict[str, Any] | None = None

    @field_validator("field_key")
    @classmethod
    def valid_field_key(cls, v: str) -> str:
        if _FIELD_KEY_RE.fullmatch(v) is None:
            raise ValueError("field_key는 소문자·숫자·언더스코어(소문자 시작)만 허용됩니다")
        return v

    @field_validator("label")
    @classmethod
    def strip_label(cls, v: str) -> str:
        return _strip_nonempty(v)


class RoleFieldUpdate(BaseModel):
    """field_key·field_type은 수정 불가 — 저장값(typed EAV) 정합성 보호."""

    model_config = {"extra": "forbid"}

    label: str | None = Field(None, min_length=1, max_length=100)
    is_required: bool | None = None
    is_unique: bool | None = None
    is_searchable: bool | None = None
    sort_order: int | None = None
    default_value: str | None = None
    placeholder: str | None = Field(None, max_length=200)
    help_text: str | None = None
    validation: dict[str, Any] | None = None
    options: dict[str, Any] | None = None
    is_active: bool | None = None

    @field_validator("label")
    @classmethod
    def strip_label(cls, v: str | None) -> str | None:
        return v if v is None else _strip_nonempty(v)
