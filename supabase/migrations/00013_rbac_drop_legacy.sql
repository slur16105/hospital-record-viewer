-- ============================================================
-- Migration 00013: 레거시 스키마 제거 (파괴적) — ⛔ 적용 게이트 있음
-- ============================================================
-- ⚠️⚠️ 이 파일은 Story 6.1에서 "작성만" 된 것이다. ⚠️⚠️
--
-- 적용 조건 (전부 충족 후에만):
--   1. Epic 9 (프론트 기능 URL 재편) 배포 완료
--   2. Epic 10.1 (백엔드 API 권한 전환 — patient_id/doctor_id 참조 제거) 배포 완료
--   3. scripts/verify_rbac_migration.py 전 항목 PASS를 사람이 확인
--   4. Slur 승인 (Sprint Change Proposal 2026-07-09 게이트)
--
-- 이 시점 전에 적용하면 운영 중인 백엔드·프론트가 즉시 파손된다
-- (user_profiles.role, doctors, patients를 아직 읽고 있음).
-- ============================================================

------------------------------------------------------------
-- 0. 신 컬럼 NOT NULL 승격 + 병행 기간 동기화 트리거 제거
------------------------------------------------------------

ALTER TABLE medical_records
    ALTER COLUMN patient_user_id SET NOT NULL,
    ALTER COLUMN doctor_user_id  SET NOT NULL;

DROP TRIGGER  IF EXISTS tr_medical_records_sync_user_ids ON medical_records;
DROP FUNCTION IF EXISTS sync_medical_record_user_ids();

DROP TRIGGER  IF EXISTS tr_access_logs_sync_resource ON access_logs;
DROP FUNCTION IF EXISTS sync_access_log_resource();

------------------------------------------------------------
-- 1. 진료기록 불변 필드 트리거를 신 컬럼 기준으로 교체
------------------------------------------------------------
-- 구버전(00002)은 patient_id/doctor_id를 검사 — 컬럼 삭제 전에 교체 필수.

CREATE OR REPLACE FUNCTION prevent_immutable_field_update()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.visited_at IS DISTINCT FROM NEW.visited_at THEN
        RAISE EXCEPTION 'visited_at cannot be modified';
    END IF;
    IF OLD.doctor_user_id IS DISTINCT FROM NEW.doctor_user_id THEN
        RAISE EXCEPTION 'doctor_user_id cannot be modified';
    END IF;
    IF OLD.patient_user_id IS DISTINCT FROM NEW.patient_user_id THEN
        RAISE EXCEPTION 'patient_user_id cannot be modified';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
-- 트리거 tr_medical_records_immutable 자체는 유지(함수 본문만 교체됨)

------------------------------------------------------------
-- 2. 구 RLS 정책 제거 (role enum·헬퍼 함수 의존 정책 전부)
------------------------------------------------------------
-- 백엔드는 service_role로 접근(RLS 우회)하므로 정책 제거 후에도 동작.
-- RLS ENABLE 상태는 유지 → anon/authenticated 직접 접근 전면 차단.
-- 출처: 00002, 00004, 00005

DROP POLICY IF EXISTS user_profiles_select   ON user_profiles;
DROP POLICY IF EXISTS user_profiles_insert   ON user_profiles;
DROP POLICY IF EXISTS user_profiles_update   ON user_profiles;
DROP POLICY IF EXISTS departments_select     ON departments;
DROP POLICY IF EXISTS departments_insert     ON departments;
DROP POLICY IF EXISTS departments_update     ON departments;
DROP POLICY IF EXISTS medical_records_select ON medical_records;
DROP POLICY IF EXISTS medical_records_insert ON medical_records;
DROP POLICY IF EXISTS medical_records_update ON medical_records;
DROP POLICY IF EXISTS access_logs_select     ON access_logs;
DROP POLICY IF EXISTS access_logs_insert     ON access_logs;
-- doctors/patients 정책은 테이블 DROP과 함께 제거됨

------------------------------------------------------------
-- 3. 구 컬럼 제거
------------------------------------------------------------

ALTER TABLE medical_records DROP COLUMN IF EXISTS patient_id;
ALTER TABLE medical_records DROP COLUMN IF EXISTS doctor_id;
ALTER TABLE access_logs     DROP COLUMN IF EXISTS record_id;
ALTER TABLE user_profiles   DROP COLUMN IF EXISTS role;

------------------------------------------------------------
-- 4. 구 테이블·enum·헬퍼 함수 제거
------------------------------------------------------------
-- 00009의 patients_user_profile_fk / doctors_user_profile_fk는 테이블과 함께 제거됨.

DROP TABLE IF EXISTS doctors  CASCADE;
DROP TABLE IF EXISTS patients CASCADE;

DROP FUNCTION IF EXISTS get_user_role();
DROP FUNCTION IF EXISTS is_admin();
DROP FUNCTION IF EXISTS is_attending_doctor(UUID);
DROP FUNCTION IF EXISTS is_own_record(UUID);
DROP FUNCTION IF EXISTS get_current_doctor_id();
-- get_current_patient_id()는 00005에서 이미 제거됨

DROP TYPE IF EXISTS user_role;

NOTIFY pgrst, 'reload schema';
