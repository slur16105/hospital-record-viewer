-- Hospital Medical Records System - Initial Schema
-- Supabase (PostgreSQL) Migration

-- Enable UUID extension (usually already enabled in Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

------------------------------------------------------------
-- ENUMS
------------------------------------------------------------

CREATE TYPE user_role AS ENUM ('admin', 'doctor', 'patient');
CREATE TYPE access_action AS ENUM ('view_list', 'view_detail');

------------------------------------------------------------
-- TABLES
------------------------------------------------------------

-- 1. user_profiles (extends Supabase auth.users)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    role user_role NOT NULL,
    name VARCHAR(100) NOT NULL,
    must_change_password BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_user_profiles_role ON user_profiles(role);

-- 2. departments (진료과목)
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 3. examination_rooms (진료실)
CREATE TABLE examination_rooms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    department_id UUID NOT NULL REFERENCES departments(id),
    room_number VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_room_per_department UNIQUE (department_id, room_number)
);

CREATE INDEX idx_examination_rooms_department ON examination_rooms(department_id);

-- 4. doctors (의사)
CREATE TABLE doctors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(id),
    license_number VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_doctors_department ON doctors(department_id);
CREATE INDEX idx_doctors_user_id ON doctors(user_id);

-- 5. patients (환자)
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    birth_date DATE NOT NULL,
    phone VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_patients_user_id ON patients(user_id);
CREATE INDEX idx_patients_birth_date ON patients(birth_date);

-- 6. medical_records (진료기록)
CREATE TABLE medical_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id),
    doctor_id UUID NOT NULL REFERENCES doctors(id),
    room_id UUID NOT NULL REFERENCES examination_rooms(id),
    visited_at TIMESTAMPTZ NOT NULL,
    chief_complaint TEXT,
    diagnosis TEXT NOT NULL,
    prescription TEXT,
    is_corrected BOOLEAN DEFAULT false,
    correction_note TEXT,
    corrected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_medical_records_patient ON medical_records(patient_id);
CREATE INDEX idx_medical_records_doctor ON medical_records(doctor_id);
CREATE INDEX idx_medical_records_visited_at ON medical_records(visited_at DESC);

-- 7. access_logs (접근 로그) - Append-only
CREATE TABLE access_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    record_id UUID REFERENCES medical_records(id),
    action access_action NOT NULL,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_access_logs_user ON access_logs(user_id);
CREATE INDEX idx_access_logs_record ON access_logs(record_id);
CREATE INDEX idx_access_logs_created ON access_logs(created_at DESC);

------------------------------------------------------------
-- TRIGGERS: Auto-update updated_at
------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_departments_updated_at
    BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_examination_rooms_updated_at
    BEFORE UPDATE ON examination_rooms
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_doctors_updated_at
    BEFORE UPDATE ON doctors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_medical_records_updated_at
    BEFORE UPDATE ON medical_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

------------------------------------------------------------
-- HELPER FUNCTIONS
------------------------------------------------------------

-- Get current user's role
CREATE OR REPLACE FUNCTION get_user_role()
RETURNS user_role AS $$
    SELECT role FROM user_profiles WHERE user_id = auth.uid();
$$ LANGUAGE sql SECURITY DEFINER;

-- Check if current user is admin
CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM user_profiles
        WHERE user_id = auth.uid() AND role = 'admin'
    );
$$ LANGUAGE sql SECURITY DEFINER;

-- Check if current user is the doctor for a medical record
CREATE OR REPLACE FUNCTION is_attending_doctor(record_id UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM medical_records mr
        JOIN doctors d ON mr.doctor_id = d.id
        WHERE mr.id = record_id AND d.user_id = auth.uid()
    );
$$ LANGUAGE sql SECURITY DEFINER;

-- Check if current user is the patient for a medical record
CREATE OR REPLACE FUNCTION is_own_record(record_id UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM medical_records mr
        JOIN patients p ON mr.patient_id = p.id
        WHERE mr.id = record_id AND p.user_id = auth.uid()
    );
$$ LANGUAGE sql SECURITY DEFINER;

-- Get doctor_id for current user
CREATE OR REPLACE FUNCTION get_current_doctor_id()
RETURNS UUID AS $$
    SELECT id FROM doctors WHERE user_id = auth.uid();
$$ LANGUAGE sql SECURITY DEFINER;

-- Get patient_id for current user
CREATE OR REPLACE FUNCTION get_current_patient_id()
RETURNS UUID AS $$
    SELECT id FROM patients WHERE user_id = auth.uid();
$$ LANGUAGE sql SECURITY DEFINER;
