-- ============================================================
-- Migration 00016: 레거시 컬럼 NULL 허용 (가산적 — 00013의 다리)
-- ============================================================
-- 목적: 00013(레거시 스키마 제거) "적용 전" 코드 정리 배포를 가능하게 한다.
--   코드는 더 이상 레거시 컬럼(medical_records.patient_id/doctor_id,
--   user_profiles.role, access_logs.record_id)을 기입하지 않는데,
--   이들 중 일부가 NOT NULL이라 INSERT가 깨진다 → NOT NULL만 해제한다.
--
-- 성격: 가산적(additive). DROP 없음, 타입·데이터 변경 없음.
--   00013 적용 전에 반드시 이 마이그레이션을 먼저 적용한 뒤
--   정리된 코드를 배포하고, 최종적으로 00013이 컬럼을 제거한다.
-- ============================================================

ALTER TABLE medical_records
    ALTER COLUMN patient_id DROP NOT NULL,
    ALTER COLUMN doctor_id  DROP NOT NULL;

-- user_profiles.role: NOT NULL만 해제, user_role enum 타입은 유지 (00013에서 DROP)
ALTER TABLE user_profiles
    ALTER COLUMN role DROP NOT NULL;

-- access_logs.record_id: 이미 NULLABLE (00001) — 명시적 no-op로 상태를 고정
ALTER TABLE access_logs
    ALTER COLUMN record_id DROP NOT NULL;

NOTIFY pgrst, 'reload schema';
