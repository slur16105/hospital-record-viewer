from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class DoctorInfo(BaseModel):
    id: UUID
    name: str
    department: str


class MedicalRecordListItem(BaseModel):
    id: UUID
    visited_at: datetime
    diagnosis: str
    doctor: DoctorInfo
    is_corrected: bool
    room_number: str | None = None


class MedicalRecordDetail(MedicalRecordListItem):
    chief_complaint: str | None = None
    prescription: str | None = None
    correction_note: str | None = None
    corrected_at: datetime | None = None
    created_at: datetime


class MedicalRecordPage(BaseModel):
    data: list[MedicalRecordListItem]
    total: int
    page: int
    page_size: int


class MedicalRecordCreate(BaseModel):
    patient_id: UUID
    visited_at: datetime
    diagnosis: str = Field(..., min_length=1)
    chief_complaint: str | None = None
    prescription: str | None = None
    room_id: UUID | None = None


class MedicalRecordUpdate(BaseModel):
    diagnosis: str | None = Field(None, min_length=1)
    chief_complaint: str | None = None
    prescription: str | None = None
    correction_note: str | None = None
