-- ============================================================
-- Migration 00014: access_logs.action enum → varchar 확장 (Story 10.2)
-- ============================================================
-- 접근로그 일반화: view_list/view_detail 외에 create·update·role_change 등
-- 모든 모듈의 감사 액션을 기록할 수 있도록 enum 제약을 푼다.
-- ⚠️ 적용 순서: 00012 이후 언제든 가능 (00013보다 먼저 적용됨 — 00013은 게이트 대기)
-- 가산적·무중단: 기존 값('view_list','view_detail')은 그대로 varchar로 변환된다.
-- ============================================================

ALTER TABLE access_logs
    ALTER COLUMN action TYPE VARCHAR(50) USING action::text;

DROP TYPE IF EXISTS access_action;

NOTIFY pgrst, 'reload schema';
