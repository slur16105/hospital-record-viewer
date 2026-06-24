-- Hospital Medical Records System - RLS Policies
-- Row Level Security for all tables

------------------------------------------------------------
-- Enable RLS on all tables
------------------------------------------------------------

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE examination_rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctors ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE access_logs ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------
-- user_profiles policies
------------------------------------------------------------

-- SELECT: 본인 프로필 또는 admin
CREATE POLICY user_profiles_select ON user_profiles
    FOR SELECT USING (
        user_id = auth.uid() OR is_admin()
    );

-- INSERT: admin이 doctor 생성 / 자가가입 시 patient 생성
CREATE POLICY user_profiles_insert ON user_profiles
    FOR INSERT WITH CHECK (
        (is_admin() AND role = 'doctor') OR
        (user_id = auth.uid() AND role = 'patient')
    );

-- UPDATE: 본인 또는 admin
CREATE POLICY user_profiles_update ON user_profiles
    FOR UPDATE USING (
        user_id = auth.uid() OR is_admin()
    );

-- DELETE: 불가 (soft delete 사용)

------------------------------------------------------------
-- departments policies
------------------------------------------------------------

-- SELECT: 인증된 모든 사용자
CREATE POLICY departments_select ON departments
    FOR SELECT USING (auth.uid() IS NOT NULL);

-- INSERT: admin만
CREATE POLICY departments_insert ON departments
    FOR INSERT WITH CHECK (is_admin());

-- UPDATE: admin만
CREATE POLICY departments_update ON departments
    FOR UPDATE USING (is_admin());

------------------------------------------------------------
-- examination_rooms policies
------------------------------------------------------------

-- SELECT: 인증된 모든 사용자
CREATE POLICY examination_rooms_select ON examination_rooms
    FOR SELECT USING (auth.uid() IS NOT NULL);

-- INSERT: admin만
CREATE POLICY examination_rooms_insert ON examination_rooms
    FOR INSERT WITH CHECK (is_admin());

-- UPDATE: admin만
CREATE POLICY examination_rooms_update ON examination_rooms
    FOR UPDATE USING (is_admin());

------------------------------------------------------------
-- doctors policies
------------------------------------------------------------

-- SELECT: 인증된 모든 사용자 (활성 의사 목록 조회용)
CREATE POLICY doctors_select ON doctors
    FOR SELECT USING (auth.uid() IS NOT NULL);

-- INSERT: admin만
CREATE POLICY doctors_insert ON doctors
    FOR INSERT WITH CHECK (is_admin());

-- UPDATE: admin만
CREATE POLICY doctors_update ON doctors
    FOR UPDATE USING (is_admin());

------------------------------------------------------------
-- patients policies
------------------------------------------------------------

-- SELECT: 본인 / admin / 담당의사 (진료기록이 있는 경우)
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

-- INSERT: 자가 가입
CREATE POLICY patients_insert ON patients
    FOR INSERT WITH CHECK (user_id = auth.uid());

-- UPDATE: admin만
CREATE POLICY patients_update ON patients
    FOR UPDATE USING (is_admin());

------------------------------------------------------------
-- medical_records policies
------------------------------------------------------------

-- SELECT: 본인 환자 / 담당의 / admin
CREATE POLICY medical_records_select ON medical_records
    FOR SELECT USING (
        is_own_record(id) OR
        is_attending_doctor(id) OR
        is_admin()
    );

-- INSERT: 의사만 (본인이 담당의로 자동 설정됨)
CREATE POLICY medical_records_insert ON medical_records
    FOR INSERT WITH CHECK (
        doctor_id = get_current_doctor_id()
    );

-- UPDATE: 담당의만 (visited_at, doctor_id는 트리거로 보호)
CREATE POLICY medical_records_update ON medical_records
    FOR UPDATE USING (
        is_attending_doctor(id)
    );

-- DELETE: 불가

------------------------------------------------------------
-- access_logs policies
------------------------------------------------------------

-- SELECT: admin만
CREATE POLICY access_logs_select ON access_logs
    FOR SELECT USING (is_admin());

-- INSERT: 인증된 사용자 (시스템이 자동 기록)
CREATE POLICY access_logs_insert ON access_logs
    FOR INSERT WITH CHECK (user_id = auth.uid());

-- UPDATE/DELETE: 불가 (append-only)

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
