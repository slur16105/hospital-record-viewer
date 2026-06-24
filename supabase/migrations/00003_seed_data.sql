-- Hospital Medical Records System - Seed Data
-- Sample data for development and demonstration

------------------------------------------------------------
-- Departments (진료과목) - 5개
------------------------------------------------------------

INSERT INTO departments (id, name) VALUES
    ('d1000000-0000-0000-0000-000000000001', '내과'),
    ('d1000000-0000-0000-0000-000000000002', '외과'),
    ('d1000000-0000-0000-0000-000000000003', '소아과'),
    ('d1000000-0000-0000-0000-000000000004', '정형외과'),
    ('d1000000-0000-0000-0000-000000000005', '피부과');

------------------------------------------------------------
-- NOTE: Users, Doctors, Patients, Medical Records
--
-- These must be created via Supabase Auth API because
-- auth.users table is managed by Supabase Auth.
--
-- Use the seed script in /scripts/seed.ts to create:
-- - 1 Admin
-- - 10 Doctors
-- - 20 Patients
-- - 50+ Medical Records
--
-- Example structure for reference:
--
-- Admin:
--   email: admin@hospital.test
--   password: Admin123!
--
-- Doctors:
--   email: doctor1@hospital.test ~ doctor10@hospital.test
--   password: Doctor123!
--
-- Patients:
--   email: patient1@hospital.test ~ patient20@hospital.test
--   password: Patient123!
------------------------------------------------------------
