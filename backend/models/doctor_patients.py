from __future__ import annotations
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel


class MyPatientItem(BaseModel):
    id: UUID  # = user_id (00013: 레거시 patients.id 대체 — 필드명은 프론트 호환 유지)
    user_id: UUID
    name: str
    birth_date: date
    latest_visited_at: datetime | None = None


class PatientSearchItem(BaseModel):
    id: UUID  # = user_id (00013: 레거시 patients.id 대체 — 필드명은 프론트 호환 유지)
    user_id: UUID
    name: str
    birth_date: date
    phone: str


class DoctorProfile(BaseModel):
    doctor_id: UUID  # = user_id (00013: 레거시 doctors.id 대체 — 필드명은 프론트 호환 유지)
    user_id: UUID
    name: str
    department_id: UUID
    department_name: str
    license_number: str
