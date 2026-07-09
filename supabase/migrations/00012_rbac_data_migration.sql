-- ============================================================
-- Migration 00012: 기존 데이터 → RBAC v3 이관 (무손실)
-- ============================================================
-- Story 6.1 — 가산적·멱등 이관. 구 스키마는 건드리지 않는다(00013에서 정리).
-- 병행 기간: 구 백엔드가 구 스키마에 쓰는 동안 트리거가 신 컬럼을 동기화하고,
-- 이 마이그레이션은 재실행해도 안전하다 (ON CONFLICT / IS NULL 가드).
-- 인라인 검증 실패 시 전체 롤백된다.
-- ============================================================

------------------------------------------------------------
-- 1. user_profiles.role → user_roles (is_primary=true)
------------------------------------------------------------

INSERT INTO user_roles (user_id, role_id, is_primary)
SELECT
    up.user_id,
    CASE up.role
        WHEN 'admin'   THEN 'a0000000-0000-0000-0000-000000000001'::uuid
        WHEN 'doctor'  THEN 'a0000000-0000-0000-0000-000000000002'::uuid
        WHEN 'patient' THEN 'a0000000-0000-0000-0000-000000000003'::uuid
    END,
    true
FROM user_profiles up
ON CONFLICT (user_id, role_id) DO NOTHING;

------------------------------------------------------------
-- 2. doctors / patients → profile_field_values
------------------------------------------------------------

-- 의사: 면허번호
INSERT INTO profile_field_values (user_id, role_field_id, value_text)
SELECT d.user_id, 'c0000000-0000-0000-0000-000000000001'::uuid, d.license_number
FROM doctors d
ON CONFLICT (user_id, role_field_id) DO NOTHING;

-- 의사: 소속 진료과 (reference 값은 uuid 문자열 — AD-13, DB FK 없음 의도)
INSERT INTO profile_field_values (user_id, role_field_id, value_text)
SELECT d.user_id, 'c0000000-0000-0000-0000-000000000002'::uuid, d.department_id::text
FROM doctors d
ON CONFLICT (user_id, role_field_id) DO NOTHING;

-- 환자: 생년월일
INSERT INTO profile_field_values (user_id, role_field_id, value_date)
SELECT p.user_id, 'c0000000-0000-0000-0000-000000000003'::uuid, p.birth_date
FROM patients p
ON CONFLICT (user_id, role_field_id) DO NOTHING;

-- 환자: 연락처
INSERT INTO profile_field_values (user_id, role_field_id, value_text)
SELECT p.user_id, 'c0000000-0000-0000-0000-000000000004'::uuid, p.phone
FROM patients p
ON CONFLICT (user_id, role_field_id) DO NOTHING;

------------------------------------------------------------
-- 3. medical_records: user 직접 참조 컬럼 추가 + 백필
------------------------------------------------------------
-- NOT NULL은 00013에서 부여 (병행 기간엔 구 백엔드 INSERT가 신 컬럼을 모름 →
-- 아래 동기화 트리거가 채워준다).

ALTER TABLE medical_records
    ADD COLUMN IF NOT EXISTS patient_user_id UUID REFERENCES user_profiles(user_id),
    ADD COLUMN IF NOT EXISTS doctor_user_id  UUID REFERENCES user_profiles(user_id);

UPDATE medical_records mr
SET patient_user_id = p.user_id
FROM patients p
WHERE mr.patient_id = p.id AND mr.patient_user_id IS NULL;

UPDATE medical_records mr
SET doctor_user_id = d.user_id
FROM doctors d
WHERE mr.doctor_id = d.id AND mr.doctor_user_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_medical_records_patient_user ON medical_records(patient_user_id);
CREATE INDEX IF NOT EXISTS idx_medical_records_doctor_user  ON medical_records(doctor_user_id);

-- 병행 기간 동기화 트리거: 구 백엔드가 patient_id/doctor_id로 INSERT하면 신 컬럼 자동 채움
CREATE OR REPLACE FUNCTION sync_medical_record_user_ids()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.patient_user_id IS NULL AND NEW.patient_id IS NOT NULL THEN
        SELECT user_id INTO NEW.patient_user_id FROM patients WHERE id = NEW.patient_id;
    END IF;
    IF NEW.doctor_user_id IS NULL AND NEW.doctor_id IS NOT NULL THEN
        SELECT user_id INTO NEW.doctor_user_id FROM doctors WHERE id = NEW.doctor_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_medical_records_sync_user_ids ON medical_records;
CREATE TRIGGER tr_medical_records_sync_user_ids
    BEFORE INSERT ON medical_records
    FOR EACH ROW EXECUTE FUNCTION sync_medical_record_user_ids();

------------------------------------------------------------
-- 4. access_logs: 자원 참조 일반화 컬럼 추가 + 소급
------------------------------------------------------------
-- 병행 기간: DEFAULT 'medical_record' + 트리거가 record_id → resource_id 복사.
-- action enum(view_list|view_detail) → varchar 확장은 10.2 범위.

ALTER TABLE access_logs
    ADD COLUMN IF NOT EXISTS resource_type VARCHAR(50) NOT NULL DEFAULT 'medical_record',
    ADD COLUMN IF NOT EXISTS resource_id   UUID;

UPDATE access_logs
SET resource_id = record_id
WHERE resource_id IS NULL AND record_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_access_logs_resource ON access_logs(resource_type, resource_id);

CREATE OR REPLACE FUNCTION sync_access_log_resource()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.resource_id IS NULL AND NEW.record_id IS NOT NULL THEN
        NEW.resource_id := NEW.record_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_access_logs_sync_resource ON access_logs;
CREATE TRIGGER tr_access_logs_sync_resource
    BEFORE INSERT ON access_logs
    FOR EACH ROW EXECUTE FUNCTION sync_access_log_resource();

------------------------------------------------------------
-- 5. 인라인 검증 — 실패 시 RAISE EXCEPTION → 전체 롤백 (SM-3)
------------------------------------------------------------

DO $$
DECLARE
    n_profiles      BIGINT; n_user_roles    BIGINT;
    n_doctors       BIGINT; n_doc_license   BIGINT; n_doc_dept BIGINT;
    n_patients      BIGINT; n_pat_birth     BIGINT; n_pat_phone BIGINT;
    n_rec_null_pat  BIGINT; n_rec_null_doc  BIGINT;
    n_log_null_res  BIGINT;
BEGIN
    SELECT count(*) INTO n_profiles   FROM user_profiles;
    SELECT count(*) INTO n_user_roles FROM user_roles;
    IF n_user_roles < n_profiles THEN
        RAISE EXCEPTION '검증 실패: user_roles(%) < user_profiles(%)', n_user_roles, n_profiles;
    END IF;

    SELECT count(*) INTO n_doctors     FROM doctors;
    SELECT count(*) INTO n_doc_license FROM profile_field_values
        WHERE role_field_id = 'c0000000-0000-0000-0000-000000000001';
    SELECT count(*) INTO n_doc_dept    FROM profile_field_values
        WHERE role_field_id = 'c0000000-0000-0000-0000-000000000002';
    IF n_doc_license <> n_doctors OR n_doc_dept <> n_doctors THEN
        RAISE EXCEPTION '검증 실패: 의사 필드값(면허 %, 소속 %) <> doctors(%)',
            n_doc_license, n_doc_dept, n_doctors;
    END IF;

    SELECT count(*) INTO n_patients  FROM patients;
    SELECT count(*) INTO n_pat_birth FROM profile_field_values
        WHERE role_field_id = 'c0000000-0000-0000-0000-000000000003';
    SELECT count(*) INTO n_pat_phone FROM profile_field_values
        WHERE role_field_id = 'c0000000-0000-0000-0000-000000000004';
    IF n_pat_birth <> n_patients OR n_pat_phone <> n_patients THEN
        RAISE EXCEPTION '검증 실패: 환자 필드값(생년월일 %, 연락처 %) <> patients(%)',
            n_pat_birth, n_pat_phone, n_patients;
    END IF;

    SELECT count(*) INTO n_rec_null_pat FROM medical_records WHERE patient_user_id IS NULL;
    SELECT count(*) INTO n_rec_null_doc FROM medical_records WHERE doctor_user_id  IS NULL;
    IF n_rec_null_pat > 0 OR n_rec_null_doc > 0 THEN
        RAISE EXCEPTION '검증 실패: medical_records 미채움 (patient_user_id NULL %건, doctor_user_id NULL %건)',
            n_rec_null_pat, n_rec_null_doc;
    END IF;

    SELECT count(*) INTO n_log_null_res FROM access_logs
        WHERE record_id IS NOT NULL AND resource_id IS NULL;
    IF n_log_null_res > 0 THEN
        RAISE EXCEPTION '검증 실패: access_logs resource_id 미채움 %건', n_log_null_res;
    END IF;

    RAISE NOTICE '✅ 00012 검증 통과 — profiles=%, user_roles=%, doctors=%, patients=%',
        n_profiles, n_user_roles, n_doctors, n_patients;
END $$;

NOTIFY pgrst, 'reload schema';
