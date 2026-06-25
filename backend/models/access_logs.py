from __future__ import annotations
from datetime import date, datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel


class AccessLogOut(BaseModel):
    id: UUID
    user_id: UUID
    accessor_name: str
    record_id: UUID | None
    patient_name: str
    action: str
    ip_address: str | None
    created_at: datetime


class AccessLogPage(BaseModel):
    data: list[AccessLogOut]
    total: int
    page: int
    page_size: int
