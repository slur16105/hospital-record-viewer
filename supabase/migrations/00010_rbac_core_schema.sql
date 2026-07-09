-- ============================================================
-- Migration 00010: RBAC Core Schema (ERD v3)
-- ============================================================
-- Story 6.1 — 동적 RBAC 코어 테이블 6종 + field_type enum.
-- 가산적(additive) 마이그레이션: 기존 스키마를 변경하지 않으며
-- 운영 중인 백엔드와 병행 동작한다. (파괴적 정리는 00013)
-- 스키마 단일 원본: docs/dbdiagram-v3-rbac.dbml
-- ============================================================

------------------------------------------------------------
-- ENUM
------------------------------------------------------------

CREATE TYPE field_type AS ENUM (
    'text', 'number', 'date', 'boolean', 'phone',
    'email', 'select', 'multiselect', 'reference', 'json'
);

------------------------------------------------------------
-- 1. roles (역할 — 관리자 화면에서 생성·수정)
------------------------------------------------------------

CREATE TABLE roles (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    is_system   BOOLEAN     NOT NULL DEFAULT false,  -- true: 삭제·핵심권한 회수 불가 (백엔드 강제)
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER tr_roles_updated_at
    BEFORE UPDATE ON roles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

------------------------------------------------------------
-- 2. permissions (권한 카탈로그 — 개발자 시드 전용)
------------------------------------------------------------

CREATE TABLE permissions (
    id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    code        VARCHAR(100) NOT NULL UNIQUE,  -- backend/core/permissions.py 상수와 동기화
    name        VARCHAR(100) NOT NULL,
    category    VARCHAR(50),
    description TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

------------------------------------------------------------
-- 3. role_permissions (역할↔권한 조합)
------------------------------------------------------------

CREATE TABLE role_permissions (
    role_id       UUID        NOT NULL REFERENCES roles(id)       ON DELETE CASCADE,
    permission_id UUID        NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (role_id, permission_id)
);

CREATE INDEX idx_role_permissions_permission ON role_permissions(permission_id);

------------------------------------------------------------
-- 4. user_roles (사용자↔역할 N:N)
------------------------------------------------------------

CREATE TABLE user_roles (
    user_id     UUID        NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    role_id     UUID        NOT NULL REFERENCES roles(id)              ON DELETE RESTRICT,
    is_primary  BOOLEAN     NOT NULL DEFAULT false,  -- 로그인 기본 컨텍스트
    assigned_by UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX idx_user_roles_role ON user_roles(role_id);

-- 기본 역할은 사용자당 1개
CREATE UNIQUE INDEX uq_user_roles_primary ON user_roles(user_id) WHERE is_primary;

------------------------------------------------------------
-- 5. role_fields (역할별 입력필드 정의 — 노코드 폼 빌더)
------------------------------------------------------------

CREATE TABLE role_fields (
    id            UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id       UUID         NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    field_key     VARCHAR(50)  NOT NULL,
    label         VARCHAR(100) NOT NULL,
    field_type    field_type   NOT NULL,
    is_required   BOOLEAN      NOT NULL DEFAULT false,
    is_unique     BOOLEAN      NOT NULL DEFAULT false,  -- 역할 내 값 중복 금지 (백엔드+검증 강제)
    is_searchable BOOLEAN      NOT NULL DEFAULT false,  -- 검색 API 대상
    sort_order    INT          NOT NULL DEFAULT 0,
    default_value TEXT,
    placeholder   VARCHAR(200),
    help_text     TEXT,
    validation    JSONB,  -- {"min_length":8,"pattern":"^..."} — 프론트·백엔드 공용 규칙
    options       JSONB,  -- select: {"choices":[...]} / reference: {"table":"...","label_column":"..."}
    is_active     BOOLEAN      NOT NULL DEFAULT true,  -- 삭제 대신 숨김(저장값 보존)
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (role_id, field_key)
);

CREATE INDEX idx_role_fields_role_sort ON role_fields(role_id, sort_order);

CREATE TRIGGER tr_role_fields_updated_at
    BEFORE UPDATE ON role_fields
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

------------------------------------------------------------
-- 6. profile_field_values (사용자 입력값 — typed EAV)
------------------------------------------------------------
-- field_type에 맞는 value_* 컬럼 하나에만 저장하고 나머지는 NULL.
-- 강제는 backend/core/field_values.py(AD-13) — DB CHECK는 두지 않음.

CREATE TABLE profile_field_values (
    id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID        NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    role_field_id UUID        NOT NULL REFERENCES role_fields(id)        ON DELETE RESTRICT,
    value_text    TEXT,
    value_number  NUMERIC,
    value_date    DATE,
    value_boolean BOOLEAN,
    value_json    JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, role_field_id)
);

CREATE INDEX idx_pfv_field_text   ON profile_field_values(role_field_id, value_text);
CREATE INDEX idx_pfv_field_number ON profile_field_values(role_field_id, value_number);
CREATE INDEX idx_pfv_field_date   ON profile_field_values(role_field_id, value_date);

CREATE TRIGGER tr_profile_field_values_updated_at
    BEFORE UPDATE ON profile_field_values
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

------------------------------------------------------------
-- user_profiles: 공통 프로필 컬럼 추가 (ERD v3)
------------------------------------------------------------

ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS avatar_url TEXT;

------------------------------------------------------------
-- RLS: 신규 테이블은 백엔드(service_role) 전용
------------------------------------------------------------
-- RLS ENABLE + 정책 없음 = anon/authenticated 전면 차단 (기본 거부).
-- service_role은 RLS를 우회하므로 백엔드(get_supabase_admin)만 접근 가능.
-- NFR-4: 권한 판정은 FastAPI 인가 계층(6.2)이 담당한다.

ALTER TABLE roles                ENABLE ROW LEVEL SECURITY;
ALTER TABLE permissions          ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles           ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_fields          ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_field_values ENABLE ROW LEVEL SECURITY;

-- PostgREST 스키마 캐시 갱신
NOTIFY pgrst, 'reload schema';
