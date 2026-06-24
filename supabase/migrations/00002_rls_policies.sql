-- Hospital Medical Records System - RLS Policies

------------------------------------------------------------
-- Enable RLS
------------------------------------------------------------

ALTER TABLE user_profiles   ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments     ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctors         ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients        ENABLE ROW LEVEL SECURITY;
ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE access_logs     ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------
-- user_profiles policies
------------------------------------------------------------

-- SELECT: 본인 프로필 또는 admin
-- ※ 00004_relax_user_profiles_rls.sql 에서 이 정책을 DROP 후 재정의함
--   (의사 이름 조회를 위해 인증된 전체 사용자로 완화)
CREATE POLICY user_profiles_select ON user_profiles
    FOR SELECT USING (user_id = auth.uid() OR is_admin());

-- INSERT: admin(원무팀)만 생성 가능 — 환자 자가가입 차단
CREATE POLICY user_profiles_insert ON user_profiles
    FOR INSERT WITH CHECK (is_admin());

-- UPDATE: 본인 또는 admin
CREATE POLICY user_profiles_update ON user_profiles
    FOR UPDATE USING (user_id = auth.uid() OR is_admin());

------------------------------------------------------------
-- departments policies
------------------------------------------------------------

CREATE POLICY departments_select ON departments
    FOR SELECT USING (auth.uid() IS NOT NULL);

CREATE POLICY departments_insert ON departments
    FOR INSERT WITH CHECK (is_admin());

CREATE POLICY departments_update ON departments
    FOR UPDATE USING (is_admin());

------------------------------------------------------------
-- doctors policies
------------------------------------------------------------

CREATE POLICY doctors_select ON doctors
    FOR SELECT USING (auth.uid() IS NOT NULL);

CREATE POLICY doctors_insert ON doctors
    FOR INSERT WITH CHECK (is_admin());

CREATE POLICY doctors_update ON doctors
    FOR UPDATE USING (is_admin());

------------------------------------------------------------
-- patients policies
------------------------------------------------------------

CREATE POLICY patients_select ON patients
    FOR SELECT USING (
        user_id = auth.uid() OR
        is_admin() OR
        EXISTS (
            SELECT 1 FROM medical_records mr
            JOIN doctors d ON mr.doctor_id = d.id
            WHERE mr.patient_id = patients.id AND d.user_id = auth.uid()
        )
    );

CREATE POLICY patients_insert ON patients
    FOR INSERT WITH CHECK (is_admin());

CREATE POLICY patients_update ON patients
    FOR UPDATE USING (is_admin());

------------------------------------------------------------
-- medical_records policies
------------------------------------------------------------

CREATE POLICY medical_records_select ON medical_records
    FOR SELECT USING (
        is_own_record(id) OR
        is_attending_doctor(id) OR
        is_admin()
    );

CREATE POLICY medical_records_insert ON medical_records
    FOR INSERT WITH CHECK (
        doctor_id = get_current_doctor_id()
    );

CREATE POLICY medical_records_update ON medical_records
    FOR UPDATE USING (is_attending_doctor(id));

------------------------------------------------------------
-- access_logs policies
------------------------------------------------------------

CREATE POLICY access_logs_select ON access_logs
    FOR SELECT USING (is_admin());

CREATE POLICY access_logs_insert ON access_logs
    FOR INSERT WITH CHECK (user_id = auth.uid());

------------------------------------------------------------
-- Prevent modification of immutable fields in medical_records
------------------------------------------------------------

CREATE OR REPLACE FUNCTION prevent_immutable_field_update()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.visited_at IS DISTINCT FROM NEW.visited_at THEN
        RAISE EXCEPTION 'visited_at cannot be modified';
    END IF;
    IF OLD.doctor_id IS DISTINCT FROM NEW.doctor_id THEN
        RAISE EXCEPTION 'doctor_id cannot be modified';
    END IF;
    IF OLD.patient_id IS DISTINCT FROM NEW.patient_id THEN
        RAISE EXCEPTION 'patient_id cannot be modified';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_medical_records_immutable
    BEFORE UPDATE ON medical_records
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_field_update();
