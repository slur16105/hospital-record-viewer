-- =====================================================
-- ERDCloud 임포트용 DDL
-- 병원 진료기록 조회 시스템 (hospital-record-viewer)
-- =====================================================
-- 사용법: ERDCloud → 새 ERD 생성 → SQL 가져오기 → 이 파일 내용 붙여넣기
--
-- 참고: Supabase의 auth.users는 users 테이블로 표현
--       INET 타입은 ERDCloud 호환을 위해 VARCHAR(45)로 대체
-- =====================================================

-- 1. 사용자 계정 (Supabase Auth 대표)
CREATE TABLE users (
    id          UUID         PRIMARY KEY,
    email       VARCHAR(255) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ  DEFAULT now()
);

-- 2. 사용자 프로필 (역할 및 기본 정보)
CREATE TABLE user_profiles (
    id                   UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id              UUID        NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    role                 VARCHAR(20) NOT NULL,   -- admin | doctor | patient
    name                 VARCHAR(100) NOT NULL,
    must_change_password BOOLEAN     DEFAULT false,
    is_active            BOOLEAN     DEFAULT true,
    created_at           TIMESTAMPTZ DEFAULT now(),
    updated_at           TIMESTAMPTZ DEFAULT now()
);

-- 3. 진료과목
CREATE TABLE departments (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name       VARCHAR(50) NOT NULL UNIQUE,
    is_active  BOOLEAN     DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. 진료실
CREATE TABLE examination_rooms (
    id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    department_id UUID        NOT NULL REFERENCES departments(id),
    room_number   VARCHAR(20) NOT NULL,
    is_active     BOOLEAN     DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (department_id, room_number)
);

-- 5. 의사
CREATE TABLE doctors (
    id             UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id        UUID        NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    department_id  UUID        NOT NULL REFERENCES departments(id),
    license_number VARCHAR(50) NOT NULL,
    is_active      BOOLEAN     DEFAULT true,
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);

-- 6. 환자
CREATE TABLE patients (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID        NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    birth_date DATE        NOT NULL,
    phone      VARCHAR(20) NOT NULL,
    is_active  BOOLEAN     DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 7. 진료기록
CREATE TABLE medical_records (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id      UUID        NOT NULL REFERENCES patients(id),
    doctor_id       UUID        NOT NULL REFERENCES doctors(id),
    room_id         UUID        NOT NULL REFERENCES examination_rooms(id),
    visited_at      TIMESTAMPTZ NOT NULL,
    chief_complaint TEXT,
    diagnosis       TEXT        NOT NULL,
    prescription    TEXT,
    is_corrected    BOOLEAN     DEFAULT false,
    correction_note TEXT,
    corrected_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 8. 접근 로그 (Append-only)
CREATE TABLE access_logs (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID        NOT NULL REFERENCES users(id),
    record_id  UUID        REFERENCES medical_records(id),
    action     VARCHAR(20) NOT NULL,   -- view_list | view_detail
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ DEFAULT now()
);
