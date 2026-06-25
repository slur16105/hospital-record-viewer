from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator


class DoctorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    department_id: UUID
    license_number: str = Field(..., min_length=1, max_length=50)

    @field_validator("name", "license_number")
    @classmethod
    def strip_str(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("공백만으로 구성될 수 없습니다")
        return v


class DoctorUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    department_id: UUID | None = None
    license_number: str | None = Field(None, min_length=1, max_length=50)
    is_active: bool | None = None

    @field_validator("name", "license_number")
    @classmethod
    def strip_str(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("공백만으로 구성될 수 없습니다")
        return v


class DoctorOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    email: str
    department_id: UUID
    department_name: str
    license_number: str
    is_active: bool


class DoctorCreatedOut(DoctorOut):
    temp_password: str
