from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class DoctorInfo(BaseModel):
    id: UUID
    name: str
    department: str


class RoomInfo(BaseModel):
    id: UUID
    room_number: str
    department: str


class MedicalRecordListItem(BaseModel):
    id: UUID
    visited_at: datetime
    diagnosis: str
    doctor: DoctorInfo
    room: RoomInfo
    is_corrected: bool


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
