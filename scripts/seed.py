#!/usr/bin/env python3
"""
Seed script for hospital-record-viewer demo data (RBAC v3).

Requirements:
  pip install supabase python-dotenv  (or run from backend venv)

Usage:
  cd <project-root>
  python scripts/seed.py

Environment variables are read from backend/.env
(or set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY directly).

What it creates (idempotent — safe to re-run):
  - departments / examination_rooms (fixed UUIDs / natural-key lookup)
  - auth accounts + user_profiles (admin 1, doctors 10, patients 20, staff 1)
  - user_roles       — primary role per account (00011 fixed role UUIDs)
  - profile_field_values — doctor license/department, patient birth_date/phone
                           (00011 fixed role_fields UUIDs, typed EAV)
  - legacy doctors/patients rows + user_profiles.role  # TODO(00013): drop
  - medical_records with explicit patient_user_id/doctor_user_id (no trigger reliance)
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Load env from backend/.env
# ---------------------------------------------------------------------------
env_file = Path(__file__).parent.parent / "backend" / ".env"
if env_file.exists():
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("supabase_url", "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("supabase_service_role_key", "")
)

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")
    print("  Set them in backend/.env or as environment variables.")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase package not found. Run: pip install supabase")
    sys.exit(1)

admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# ---------------------------------------------------------------------------
# RBAC fixed UUIDs — must match supabase/migrations/00011_rbac_seed.sql
# (and backend/core/permissions.py ROLE_* constants)
# ---------------------------------------------------------------------------
ROLE_ADMIN_ID = "a0000000-0000-0000-0000-000000000001"   # 관리자 (is_system)
ROLE_DOCTOR_ID = "a0000000-0000-0000-0000-000000000002"  # 의사
ROLE_PATIENT_ID = "a0000000-0000-0000-0000-000000000003" # 환자
ROLE_STAFF_ID = "a0000000-0000-0000-0000-000000000004"   # 원무과

FIELD_DOCTOR_LICENSE_ID = "c0000000-0000-0000-0000-000000000001"   # text
FIELD_DOCTOR_DEPARTMENT_ID = "c0000000-0000-0000-0000-000000000002"  # reference→departments
FIELD_PATIENT_BIRTH_DATE_ID = "c0000000-0000-0000-0000-000000000003"  # date
FIELD_PATIENT_PHONE_ID = "c0000000-0000-0000-0000-000000000004"       # phone(text)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEPT_IDS = {
    "내과":    "d1000000-0000-0000-0000-000000000001",
    "외과":    "d1000000-0000-0000-0000-000000000002",
    "소아과":  "d1000000-0000-0000-0000-000000000003",
    "정형외과": "d1000000-0000-0000-0000-000000000004",
    "피부과":  "d1000000-0000-0000-0000-000000000005",
}

ROOMS = [
    ("내과",    "101호"), ("내과",    "102호"),
    ("외과",    "201호"), ("외과",    "202호"),
    ("소아과",  "301호"), ("소아과",  "302호"),
    ("정형외과", "401호"), ("정형외과", "402호"),
    ("피부과",  "501호"), ("피부과",  "502호"),
]

DOCTORS = [
    ("doctor01@hospital.test", "김민준", "내과",    "L001"),
    ("doctor02@hospital.test", "이서연", "내과",    "L002"),
    ("doctor03@hospital.test", "박도현", "외과",    "L003"),
    ("doctor04@hospital.test", "최수아", "외과",    "L004"),
    ("doctor05@hospital.test", "정예준", "소아과",  "L005"),
    ("doctor06@hospital.test", "강지아", "소아과",  "L006"),
    ("doctor07@hospital.test", "조현우", "정형외과", "L007"),
    ("doctor08@hospital.test", "윤서윤", "정형외과", "L008"),
    ("doctor09@hospital.test", "장민서", "피부과",  "L009"),
    ("doctor10@hospital.test", "임하은", "피부과",  "L010"),
]

PATIENTS = [
    ("patient01@hospital.test", "홍길동", "1985-03-15", "010-1234-0001"),
    ("patient02@hospital.test", "김영희", "1990-07-22", "010-1234-0002"),
    ("patient03@hospital.test", "이철수", "1978-11-05", "010-1234-0003"),
    ("patient04@hospital.test", "박지수", "1995-01-30", "010-1234-0004"),
    ("patient05@hospital.test", "최민준", "1988-06-18", "010-1234-0005"),
    ("patient06@hospital.test", "정수현", "1972-09-14", "010-1234-0006"),
    ("patient07@hospital.test", "강다은", "1993-12-03", "010-1234-0007"),
    ("patient08@hospital.test", "조성민", "1981-04-27", "010-1234-0008"),
    ("patient09@hospital.test", "윤지영", "1998-08-09", "010-1234-0009"),
    ("patient10@hospital.test", "장현수", "1965-02-11", "010-1234-0010"),
    ("patient11@hospital.test", "임소연", "1992-05-25", "010-1234-0011"),
    ("patient12@hospital.test", "한민재", "1976-10-07", "010-1234-0012"),
    ("patient13@hospital.test", "오지현", "1987-03-19", "010-1234-0013"),
    ("patient14@hospital.test", "서준혁", "1969-07-31", "010-1234-0014"),
    ("patient15@hospital.test", "나은서", "1996-11-22", "010-1234-0015"),
    ("patient16@hospital.test", "류태양", "1983-01-08", "010-1234-0016"),
    ("patient17@hospital.test", "문수아", "1991-06-14", "010-1234-0017"),
    ("patient18@hospital.test", "백준서", "1974-09-03", "010-1234-0018"),
    ("patient19@hospital.test", "신하린", "1999-04-17", "010-1234-0019"),
    ("patient20@hospital.test", "안도영", "1960-12-29", "010-1234-0020"),
]

# 원무과 데모 계정 — 진료기록 권한 없음, 역할별 입력필드 없음
STAFF = [
    ("staff01@hospital.test", "한사랑"),
]

DIAGNOSES = [
    ("급성 위염", "소화불량, 속쓰림", "판토프라졸 40mg 1일 1회, 7일"),
    ("고혈압", "두통, 어지러움", "암로디핀 5mg 1일 1회"),
    ("당뇨병 2형", "다뇨, 다갈증", "메트포르민 500mg 1일 2회"),
    ("요추 추간판 탈출증", "허리 통증, 하지 방사통", "물리치료 2주, NSAIDs"),
    ("알레르기성 비염", "콧물, 재채기", "세티리진 10mg 1일 1회"),
    ("급성 기관지염", "기침, 가래, 발열", "아목시실린 500mg 1일 3회, 5일"),
    ("무릎 관절염", "무릎 통증, 부종", "셀레콕시브 200mg 1일 2회"),
    ("아토피 피부염", "피부 가려움, 발진", "하이드로코르티손 크림 1일 2회"),
    ("편도선염", "인후통, 발열", "아지스로마이신 500mg 1일 1회, 3일"),
    ("골절 (요골)", "손목 통증, 부종", "깁스 고정 4주"),
    ("고지혈증", "무증상", "로수바스타틴 10mg 1일 1회"),
    ("불면증", "수면 장애", "졸피뎀 5mg 취침 전"),
    ("지루성 피부염", "두피 각질, 가려움", "케토코나졸 샴푸 주 2회"),
    ("맹장염 (급성)", "우하복부 통증, 발열", "수술 후 항생제 치료"),
    ("소아 감기", "발열, 콧물, 기침", "해열제, 충분한 수분 섭취"),
]

# Doctor index → patient indices (which patients this doctor sees)
DOCTOR_PATIENTS = {
    0: [0, 1, 2, 3],        # doctor01 (내과) → patient01-04
    1: [4, 5, 6, 7],        # doctor02 (내과) → patient05-08
    2: [8, 9, 10, 11],      # doctor03 (외과) → patient09-12
    3: [12, 13],             # doctor04 (외과) → patient13-14
    4: [14, 15, 16],        # doctor05 (소아과) → patient15-17
    5: [17, 18, 19],        # doctor06 (소아과) → patient18-20
    6: [2, 6, 10],          # doctor07 (정형외과) → patient03,07,11 (cross-specialty)
    7: [13, 17],             # doctor08 (정형외과) → patient14,18
    8: [1, 5, 9],           # doctor09 (피부과) → patient02,06,10
    9: [15, 19],             # doctor10 (피부과) → patient16,20
}

# Diagnoses suitable per department (index into DIAGNOSES list)
DEPT_DIAG = {
    "내과":    [0, 1, 2, 4, 5, 10, 11],
    "외과":    [3, 8, 13],
    "소아과":  [5, 8, 14],
    "정형외과": [3, 6, 9, 10],
    "피부과":  [4, 7, 12],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_existing_users() -> dict[str, str]:
    """Return {email: user_id} for all existing auth users."""
    result = admin.auth.admin.list_users()
    if not result:
        return {}
    return {u.email: str(u.id) for u in result if u.email}


def get_or_create_user(email: str, password: str, existing: dict[str, str]) -> str:
    if email in existing:
        print(f"  skip (exists): {email}")
        return existing[email]
    resp = admin.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
    })
    user_id = str(resp.user.id)
    print(f"  created: {email} → {user_id}")
    return user_id


def upsert_profile(user_id: str, name: str, legacy_role: str) -> None:
    # TODO(00013): user_profiles.role(user_role enum)은 레거시 NOT NULL 컬럼 —
    # RBAC 판정에는 미사용(판정은 user_roles/role_permissions). 00013 적용 시
    # legacy_role 인자와 "role" 키를 함께 제거할 것.
    admin.table("user_profiles").upsert(
        {"user_id": user_id, "role": legacy_role, "name": name, "must_change_password": False},
        on_conflict="user_id",
    ).execute()


def assign_role(user_id: str, role_id: str, is_primary: bool = True) -> None:
    """user_roles 멱등 부여 (PK user_id,role_id upsert)."""
    admin.table("user_roles").upsert(
        {"user_id": user_id, "role_id": role_id, "is_primary": is_primary},
        on_conflict="user_id,role_id",
    ).execute()


def upsert_field_value(user_id: str, role_field_id: str, column: str, value) -> None:
    """profile_field_values 멱등 upsert — typed EAV: 해당 value_* 하나만 채움."""
    row = {
        "user_id": user_id,
        "role_field_id": role_field_id,
        "value_text": None,
        "value_number": None,
        "value_date": None,
        "value_boolean": None,
        "value_json": None,
    }
    row[column] = value
    admin.table("profile_field_values").upsert(
        row, on_conflict="user_id,role_field_id"
    ).execute()


def now_minus(days: int, hours: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days, hours=hours)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Seed steps
# ---------------------------------------------------------------------------

def seed_departments():
    print("\n[1/7] Departments")
    for name, dept_id in DEPT_IDS.items():
        admin.table("departments").upsert(
            {"id": dept_id, "name": name, "is_active": True},
            on_conflict="id",
        ).execute()
    print(f"  {len(DEPT_IDS)} departments OK")


def seed_rooms() -> dict[str, str]:
    """Return {(dept_name, room_number): room_id}"""
    print("\n[2/7] Examination Rooms")
    room_map: dict[str, str] = {}
    for dept_name, room_number in ROOMS:
        dept_id = DEPT_IDS[dept_name]
        existing = (
            admin.table("examination_rooms")
            .select("id")
            .eq("department_id", dept_id)
            .eq("room_number", room_number)
            .execute()
        )
        if existing.data:
            room_id = existing.data[0]["id"]
            print(f"  skip (exists): {dept_name} {room_number}")
        else:
            result = (
                admin.table("examination_rooms")
                .insert({"department_id": dept_id, "room_number": room_number, "is_active": True})
                .execute()
            )
            room_id = result.data[0]["id"]
            print(f"  created: {dept_name} {room_number} → {room_id}")
        room_map[f"{dept_name}|{room_number}"] = room_id
    return room_map


def seed_admin(existing: dict[str, str]) -> str:
    print("\n[3/7] Admin account")
    user_id = get_or_create_user("admin@hospital.test", "Admin123!", existing)
    upsert_profile(user_id, "관리자", "admin")
    assign_role(user_id, ROLE_ADMIN_ID)
    return user_id


def seed_staff(existing: dict[str, str]) -> list[str]:
    print("\n[4/7] Staff (원무과) accounts")
    user_ids = []
    for email, name in STAFF:
        user_id = get_or_create_user(email, "Staff123!", existing)
        # TODO(00013): 레거시 user_role enum('admin','doctor','patient')에 원무과가
        # 없어 'patient'를 필러로 사용 (users.py _LEGACY_ROLE_BY_ID 폴백과 동일).
        # 실제 권한은 user_roles의 원무과 역할이 결정한다.
        upsert_profile(user_id, name, "patient")
        assign_role(user_id, ROLE_STAFF_ID)
        user_ids.append(user_id)
    return user_ids


def seed_doctors(existing: dict[str, str]) -> list[dict]:
    """Return list of {user_id, doctor_id, dept_name, email}"""
    print("\n[5/7] Doctor accounts")
    doctor_rows = []
    for email, name, dept_name, license_number in DOCTORS:
        user_id = get_or_create_user(email, "Doctor123!", existing)
        dept_id = DEPT_IDS[dept_name]

        upsert_profile(user_id, name, "doctor")
        assign_role(user_id, ROLE_DOCTOR_ID)

        # RBAC v3 필드값 (00011 role_fields 고정 UUID)
        upsert_field_value(user_id, FIELD_DOCTOR_LICENSE_ID, "value_text", license_number)
        upsert_field_value(user_id, FIELD_DOCTOR_DEPARTMENT_ID, "value_text", dept_id)

        # TODO(00013): 레거시 doctors 테이블 — 00013 적용 전까지 병존, 이후 블록 제거
        existing_doctor = (
            admin.table("doctors").select("id").eq("user_id", user_id).execute()
        )
        if existing_doctor.data:
            doctor_id = existing_doctor.data[0]["id"]
        else:
            result = (
                admin.table("doctors")
                .insert({"user_id": user_id, "department_id": dept_id, "license_number": license_number})
                .execute()
            )
            doctor_id = result.data[0]["id"]

        doctor_rows.append({
            "user_id": user_id,
            "doctor_id": doctor_id,
            "dept_name": dept_name,
            "email": email,
        })
    return doctor_rows


def seed_patients(existing: dict[str, str]) -> list[dict]:
    """Return list of {user_id, patient_id, email}"""
    print("\n[6/7] Patient accounts")
    patient_rows = []
    for email, name, birth_date, phone in PATIENTS:
        user_id = get_or_create_user(email, "Patient123!", existing)

        upsert_profile(user_id, name, "patient")
        assign_role(user_id, ROLE_PATIENT_ID)

        # RBAC v3 필드값 (00011 role_fields 고정 UUID)
        upsert_field_value(user_id, FIELD_PATIENT_BIRTH_DATE_ID, "value_date", birth_date)
        upsert_field_value(user_id, FIELD_PATIENT_PHONE_ID, "value_text", phone)

        # TODO(00013): 레거시 patients 테이블 — 00013 적용 전까지 병존, 이후 블록 제거
        existing_patient = (
            admin.table("patients").select("id").eq("user_id", user_id).execute()
        )
        if existing_patient.data:
            patient_id = existing_patient.data[0]["id"]
        else:
            result = (
                admin.table("patients")
                .insert({"user_id": user_id, "birth_date": birth_date, "phone": phone})
                .execute()
            )
            patient_id = result.data[0]["id"]

        patient_rows.append({"user_id": user_id, "patient_id": patient_id, "email": email})
    return patient_rows


def seed_medical_records(
    doctor_rows: list[dict],
    patient_rows: list[dict],
    room_map: dict[str, str],
):
    print("\n[7/7] Medical records")

    # Check existing count (멱등 가드 — 이미 시드됐으면 건너뜀)
    existing = admin.table("medical_records").select("id", count="exact").execute()
    if (existing.count or 0) >= 50:
        print(f"  skip — {existing.count} records already exist")
        return

    records = []
    day_offset = 180  # start 6 months ago

    for doctor_idx, patient_indices in DOCTOR_PATIENTS.items():
        doctor = doctor_rows[doctor_idx]
        dept_name = doctor["dept_name"]
        diag_indices = DEPT_DIAG.get(dept_name, [0])

        # Pick rooms for this department
        dept_rooms = [
            room_map[k] for k in room_map if k.startswith(f"{dept_name}|")
        ]

        for visit_num, patient_idx in enumerate(patient_indices):
            patient = patient_rows[patient_idx]

            # 3 visits per patient-doctor pair
            for visit in range(3):
                offset_days = day_offset - (visit_num * 30) - (visit * 10)
                diag = DIAGNOSES[diag_indices[visit % len(diag_indices)]]
                room_id = dept_rooms[visit % len(dept_rooms)] if dept_rooms else None

                record: dict = {
                    # 신컬럼 (RBAC v3) — 트리거 백필에 의존하지 않고 명시 기입
                    "patient_user_id": patient["user_id"],
                    "doctor_user_id": doctor["user_id"],
                    # TODO(00013): 레거시 FK — 00013 적용 시 아래 두 키 제거
                    "patient_id": patient["patient_id"],
                    "doctor_id": doctor["doctor_id"],
                    "visited_at": now_minus(offset_days, hours=visit * 3),
                    "diagnosis": diag[0],
                    "chief_complaint": diag[1],
                    "prescription": diag[2],
                }
                if room_id:
                    record["room_id"] = room_id
                records.append(record)

        day_offset -= 5

    # Batch insert
    BATCH = 20
    total = 0
    for i in range(0, len(records), BATCH):
        batch = records[i : i + BATCH]
        admin.table("medical_records").insert(batch).execute()
        total += len(batch)

    print(f"  inserted {total} medical records")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 50)
    print("Hospital Record Viewer — Seed Script (RBAC v3)")
    print("=" * 50)
    print(f"Supabase: {SUPABASE_URL}")

    existing_users = get_existing_users()
    print(f"Existing auth users: {len(existing_users)}")

    seed_departments()
    room_map = seed_rooms()
    seed_admin(existing_users)
    seed_staff(existing_users)
    doctor_rows = seed_doctors(existing_users)
    patient_rows = seed_patients(existing_users)
    seed_medical_records(doctor_rows, patient_rows, room_map)

    print("\n" + "=" * 50)
    print("Seed complete!")
    print()
    print("Test accounts:")
    print("  Admin:   admin@hospital.test    / Admin123!")
    print("  Staff:   staff01@hospital.test  / Staff123!")
    print("  Doctor:  doctor01@hospital.test / Doctor123!")
    print("  Patient: patient01@hospital.test/ Patient123!")
    print("=" * 50)


if __name__ == "__main__":
    main()
