from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("진료과목 이름은 공백만으로 구성될 수 없습니다")
        return v


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("진료과목 이름은 공백만으로 구성될 수 없습니다")
        return v


class DepartmentOut(BaseModel):
    id: UUID
    name: str
    is_active: bool
