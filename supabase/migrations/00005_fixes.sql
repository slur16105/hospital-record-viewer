-- ============================================================
-- Migration 00005: Schema & RLS Fixes
-- ============================================================
-- Fixes:
--   1. Patient self-registration RLS (user_profiles + patients INSERT)
--   2. doctors.is_active + patients.is_active columns added
--   3. medical_records.updated_at column + trigger added
--   4. patients.updated_at column + trigger added
--   5. doctors.updated_at column + trigger added
--   6. user_profiles.created_at column added
--   7. Redundant index on user_profiles(user_id) removed
--   8. Redundant index on doctors(user_id) removed
--   9. user_profiles_select policy consolidated (ensures relaxed
--      version is active regardless of 00004 apply order)
-- ============================================================

------------------------------------------------------------
-- 1. Fix patient self-registration RLS
------------------------------------------------------------
-- user_profiles: was admin-only INSERT, blocking patient signup.
-- Allow users to self-insert their own profile with role='patient'.
-- Admin can still insert any role (for doctor account creation).

DROP POLICY IF EXISTS user_profiles_insert ON user_profiles;

CREATE POLICY user_profiles_insert ON user_profiles
    FOR INSERT WITH CHECK (
        is_admin()
        OR (user_id = auth.uid() AND role = 'patient')
    );

-- patients: was admin-only INSERT, blocking patient self-registration.
-- Allow users to insert their own patients row.
-- Admin can still insert (e.g. seeding).

DROP POLICY IF EXISTS patients_insert ON patients;

CREATE POLICY patients_insert ON patients
    FOR INSERT WITH CHECK (
        is_admin()
        OR user_id = auth.uid()
    );

------------------------------------------------------------
-- 2. doctors.is_active column
------------------------------------------------------------
-- Allows admins to soft-disable a doctor without deleting the row
-- (deleting would violate medical_records.doctor_id FK constraint).

ALTER TABLE doctors ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

-- Deactivation is enforced via user_profiles.is_active (blocks login).
-- doctors/patients.is_active allows role-level filtering without deleting rows
-- that are referenced by medical_records FK constraints.

------------------------------------------------------------
-- 3. medical_records.updated_at column + trigger
------------------------------------------------------------
-- Required for incremental sync and to track when corrections
-- (is_corrected, correction_note) were applied.

ALTER TABLE medical_records ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Backfill existing rows
UPDATE medical_records SET updated_at = created_at WHERE updated_at IS NULL;

CREATE TRIGGER tr_medical_records_updated_at
    BEFORE UPDATE ON medical_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

------------------------------------------------------------
-- 4. patients.updated_at column + trigger
------------------------------------------------------------

ALTER TABLE patients ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

UPDATE patients SET updated_at = now() WHERE updated_at IS NULL;

CREATE TRIGGER tr_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

------------------------------------------------------------
-- 5. doctors.updated_at column + trigger
------------------------------------------------------------

ALTER TABLE doctors ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

UPDATE doctors SET updated_at = now() WHERE updated_at IS NULL;

CREATE TRIGGER tr_doctors_updated_at
    BEFORE UPDATE ON doctors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

------------------------------------------------------------
-- 6. user_profiles.created_at column
------------------------------------------------------------
-- user_profiles was created without a created_at column.
-- Add with a default so existing rows get a sensible value.

ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();

------------------------------------------------------------
-- 6. Remove redundant index on user_profiles(user_id)
------------------------------------------------------------
-- user_id is the PRIMARY KEY of user_profiles, which already
-- creates a unique B-tree index. This duplicate adds overhead.

DROP INDEX IF EXISTS idx_user_profiles_user_id;

------------------------------------------------------------
-- 7. Remove redundant index on doctors(user_id)
------------------------------------------------------------
-- doctors.user_id has a UNIQUE constraint, which implicitly
-- creates a unique B-tree index. The explicit index is redundant.

DROP INDEX IF EXISTS idx_doctors_user_id;

------------------------------------------------------------
-- Drop unused helper function
------------------------------------------------------------
-- get_current_patient_id() is defined in 00001 but never referenced
-- in any RLS policy, keeping it causes schema drift risk.

DROP FUNCTION IF EXISTS get_current_patient_id();

------------------------------------------------------------
-- Consolidate user_profiles_select policy
------------------------------------------------------------
-- 00002 creates a restrictive policy, 00004 relaxes it.
-- Ensure the final relaxed version is always active.

DROP POLICY IF EXISTS user_profiles_select ON user_profiles;

CREATE POLICY user_profiles_select ON user_profiles
    FOR SELECT USING (auth.uid() IS NOT NULL);
