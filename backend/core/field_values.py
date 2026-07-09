"""필드값 검증·저장 서비스 (AD-13) — Story 6.3.

profile_field_values(typed EAV)의 쓰기 경로는 전부 이 모듈을 경유한다:
- field_type에 맞는 value_* 컬럼 **하나에만** 저장 (나머지 NULL)
- is_required 검사, validation(jsonb) 규칙 해석·강제
- is_unique 중복 거부 (같은 role_field_id 내, 자기 자신 제외)
- reference 대상 행 존재 검증 (options.table — DB FK 없는 지점 보완)

프론트는 EAV 구조를 모른다 — 조회는 get_field_values_flat()의
{field_key: value} 평탄화 형태만 노출한다.

검증 실패는 HTTPException(400, detail={field_key: 오류 메시지}).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from fastapi import HTTPException

from .database import get_supabase_admin

# ------------------------------------------------------------
# field_type → value_* 컬럼 매핑 (typed EAV — ERD v3)
# ------------------------------------------------------------

FIELD_TYPE_COLUMNS: dict[str, str] = {
    "text": "value_text",
    "phone": "value_text",
    "email": "value_text",
    "select": "value_text",
    "reference": "value_text",   # 대상 행 UUID를 텍스트로 저장 (FK는 이 모듈이 보완)
    "number": "value_number",
    "date": "value_date",
    "boolean": "value_boolean",
    "multiselect": "value_json",
    "json": "value_json",
}

VALUE_COLUMNS: tuple[str, ...] = (
    "value_text", "value_number", "value_date", "value_boolean", "value_json",
)

# 검색 가능한 typed 컬럼 (00010의 부분 인덱스와 일치 — boolean/json 제외)
_SEARCHABLE_COLUMNS = {"value_text", "value_number", "value_date"}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def column_for_field_type(field_type: str) -> str:
    """field_type이 저장될 유일한 value_* 컬럼. 미지 타입은 ValueError."""
    try:
        return FIELD_TYPE_COLUMNS[field_type]
    except KeyError:
        raise ValueError(f"지원하지 않는 field_type: {field_type}")


# ------------------------------------------------------------
# 순수 검증 (DB 불필요 — 단위 테스트 대상)
# ------------------------------------------------------------


def apply_validation_rules(rules: dict | None, value: Any) -> str | None:
    """validation(jsonb) 규칙 해석·강제. 위반 시 오류 메시지, 통과 시 None.

    지원 규칙: min_length / max_length / pattern (문자열),
              min / max (숫자·ISO 날짜 문자열).
    """
    if not rules:
        return None
    if isinstance(value, str):
        min_length = rules.get("min_length")
        if min_length is not None and len(value) < int(min_length):
            return f"최소 {min_length}자 이상 입력해주세요"
        max_length = rules.get("max_length")
        if max_length is not None and len(value) > int(max_length):
            return f"최대 {max_length}자까지 입력할 수 있습니다"
        pattern = rules.get("pattern")
        if pattern is not None and re.search(pattern, value) is None:
            return "형식이 올바르지 않습니다"
    minimum = rules.get("min")
    maximum = rules.get("max")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if minimum is not None and value < minimum:
            return f"{minimum} 이상이어야 합니다"
        if maximum is not None and value > maximum:
            return f"{maximum} 이하여야 합니다"
    return None


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def validate_field_value(field_def: dict, value: Any) -> tuple[Any, str | None]:
    """단일 필드값의 타입 검사 + validation 규칙 적용.

    반환: (저장용으로 정규화된 값, 오류 메시지 | None). 빈 값은 호출부에서 처리.
    """
    field_type = field_def.get("field_type")
    options = field_def.get("options") or {}

    if field_type in ("text", "phone"):
        if not isinstance(value, str):
            return value, "문자열이어야 합니다"
        coerced: Any = value

    elif field_type == "email":
        if not isinstance(value, str) or _EMAIL_RE.match(value) is None:
            return value, "올바른 이메일 형식이 아닙니다"
        coerced = value

    elif field_type == "number":
        if isinstance(value, bool):
            return value, "숫자여야 합니다"
        if isinstance(value, (int, float)):
            coerced = value
        elif isinstance(value, str):
            try:
                coerced = float(value) if "." in value else int(value)
            except ValueError:
                return value, "숫자여야 합니다"
        else:
            return value, "숫자여야 합니다"

    elif field_type == "date":
        if not isinstance(value, str):
            return value, "날짜 형식(YYYY-MM-DD)이어야 합니다"
        try:
            coerced = date.fromisoformat(value).isoformat()
        except ValueError:
            return value, "날짜 형식(YYYY-MM-DD)이어야 합니다"

    elif field_type == "boolean":
        if not isinstance(value, bool):
            return value, "true/false 값이어야 합니다"
        coerced = value

    elif field_type == "select":
        if not isinstance(value, str):
            return value, "문자열이어야 합니다"
        choices = options.get("choices")
        if choices is not None and value not in choices:
            return value, "선택 가능한 값이 아닙니다"
        coerced = value

    elif field_type == "multiselect":
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            return value, "문자열 목록이어야 합니다"
        choices = options.get("choices")
        if choices is not None:
            invalid = [v for v in value if v not in choices]
            if invalid:
                return value, "선택 가능한 값이 아닙니다"
        coerced = value

    elif field_type == "reference":
        if not isinstance(value, str) or not value:
            return value, "참조 값이 올바르지 않습니다"
        coerced = value  # 대상 행 존재 검증은 DB 단계(_check_reference_exists)

    elif field_type == "json":
        if not isinstance(value, (dict, list)):
            return value, "JSON 객체 또는 배열이어야 합니다"
        coerced = value

    else:
        return value, f"지원하지 않는 field_type: {field_type}"

    error = apply_validation_rules(field_def.get("validation"), coerced)
    if error:
        return coerced, error
    return coerced, None


def build_value_row(user_id: str, field_def: dict, coerced: Any | None) -> dict:
    """upsert용 행 생성 — 해당 field_type 컬럼 하나에만 값, 나머지 value_* 는 NULL."""
    row: dict[str, Any] = {
        "user_id": str(user_id),
        "role_field_id": field_def["id"],
    }
    for column in VALUE_COLUMNS:
        row[column] = None
    if coerced is not None:
        row[column_for_field_type(field_def["field_type"])] = coerced
    return row


# ------------------------------------------------------------
# DB 서비스
# ------------------------------------------------------------


def get_field_definitions(role_id: str, active_only: bool = True) -> list[dict]:
    """역할의 입력필드 정의 목록 (sort_order 순)."""
    query = (
        get_supabase_admin()
        .table("role_fields")
        .select("*")
        .eq("role_id", str(role_id))
        .order("sort_order")
    )
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data or []


def _check_reference_exists(field_def: dict, value: str) -> str | None:
    """reference 대상 행 존재 검증 (options.table). 없으면 오류 메시지."""
    table = (field_def.get("options") or {}).get("table")
    if not table:
        return "참조 대상이 설정되지 않은 필드입니다"
    rows = (
        get_supabase_admin().table(table).select("id").eq("id", value).limit(1).execute()
    ).data or []
    if not rows:
        return "존재하지 않는 참조 값입니다"
    return None


def _check_unique(user_id: str, field_def: dict, coerced: Any) -> str | None:
    """is_unique — 같은 role_field_id 내 동일 값 존재 시 거부 (자기 자신 제외)."""
    column = column_for_field_type(field_def["field_type"])
    rows = (
        get_supabase_admin()
        .table("profile_field_values")
        .select("user_id")
        .eq("role_field_id", field_def["id"])
        .eq(column, coerced)
        .neq("user_id", str(user_id))
        .limit(1)
        .execute()
    ).data or []
    if rows:
        return "이미 사용 중인 값입니다"
    return None


def validate_and_save_field_values(
    user_id: str, role_id: str, values: dict[str, Any]
) -> dict[str, Any]:
    """역할 필드 정의에 따라 values를 검증하고 upsert한다.

    values: {field_key: raw_value}. 검증 실패 시 400 + {field_key: 오류}.
    반환: 저장된 값의 평탄화 dict {field_key: value}.
    """
    definitions = get_field_definitions(role_id, active_only=True)
    defs_by_key = {d["field_key"]: d for d in definitions}

    errors: dict[str, str] = {}
    for key in values:
        if key not in defs_by_key:
            errors[key] = "알 수 없는 필드입니다"

    rows: list[dict] = []
    saved: dict[str, Any] = {}
    for field_def in definitions:
        key = field_def["field_key"]
        value = values.get(key)
        if _is_empty(value):
            if field_def.get("is_required"):
                errors[key] = "필수 입력 항목입니다"
            elif key in values:
                # 명시적 빈 값 → 값 비우기 (모든 value_* NULL로 upsert)
                rows.append(build_value_row(user_id, field_def, None))
                saved[key] = None
            continue

        coerced, error = validate_field_value(field_def, value)
        if error is None and field_def["field_type"] == "reference":
            error = _check_reference_exists(field_def, coerced)
        if error is None and field_def.get("is_unique"):
            error = _check_unique(user_id, field_def, coerced)
        if error:
            errors[key] = error
            continue
        rows.append(build_value_row(user_id, field_def, coerced))
        saved[key] = coerced

    if errors:
        raise HTTPException(status_code=400, detail=errors)

    if rows:
        (
            get_supabase_admin()
            .table("profile_field_values")
            .upsert(rows, on_conflict="user_id,role_field_id")
            .execute()
        )
    return saved


def get_field_values_flat(user_id: str) -> dict[str, Any]:
    """사용자의 필드값 평탄화 조회 — {field_key: value}. 비활성 필드는 제외."""
    rows = (
        get_supabase_admin()
        .table("profile_field_values")
        .select(
            "value_text, value_number, value_date, value_boolean, value_json,"
            " role_fields(field_key, field_type, is_active)"
        )
        .eq("user_id", str(user_id))
        .execute()
    ).data or []

    flat: dict[str, Any] = {}
    for row in rows:
        field = row.get("role_fields") or {}
        if not field.get("is_active", True):
            continue
        field_key = field.get("field_key")
        field_type = field.get("field_type")
        if not field_key or field_type not in FIELD_TYPE_COLUMNS:
            continue
        flat[field_key] = row.get(column_for_field_type(field_type))
    return flat


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_users_by_field(
    field_key: str,
    value: Any,
    role_id: str | None = None,
    exact: bool = False,
    limit: int = 50,
) -> list[str]:
    """is_searchable 필드 기반 사용자 검색 — 일치하는 user_id 목록.

    text 계열은 기본 부분일치(ilike), exact=True 또는 비텍스트 컬럼은 완전일치.
    is_searchable=false 필드는 검색 대상이 아니다 (빈 결과).
    """
    client = get_supabase_admin()
    field_query = (
        client.table("role_fields")
        .select("id, field_type")
        .eq("field_key", field_key)
        .eq("is_searchable", True)
        .eq("is_active", True)
    )
    if role_id:
        field_query = field_query.eq("role_id", str(role_id))
    fields = field_query.execute().data or []

    user_ids: list[str] = []
    seen: set[str] = set()
    for field in fields:
        column = FIELD_TYPE_COLUMNS.get(field["field_type"])
        if column not in _SEARCHABLE_COLUMNS:
            continue  # boolean/json은 검색 인덱스 대상이 아님
        if column == "value_date":
            # 날짜 컬럼에 비날짜 검색어를 eq하면 Postgres 타입 오류(500) — 건너뜀
            try:
                date.fromisoformat(str(value))
            except ValueError:
                continue
        elif column == "value_number" and not isinstance(value, (int, float)):
            try:
                float(str(value))
            except ValueError:
                continue
        value_query = (
            client.table("profile_field_values")
            .select("user_id")
            .eq("role_field_id", field["id"])
        )
        if column == "value_text" and not exact:
            value_query = value_query.ilike(column, f"%{_escape_like(str(value))}%")
        else:
            value_query = value_query.eq(column, value)
        rows = value_query.limit(limit).execute().data or []
        for row in rows:
            uid = row["user_id"]
            if uid not in seen:
                seen.add(uid)
                user_ids.append(uid)
            if len(user_ids) >= limit:
                return user_ids
    return user_ids
