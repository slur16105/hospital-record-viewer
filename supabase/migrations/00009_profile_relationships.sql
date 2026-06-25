-- PostgREST가 patients/doctors → user_profiles 임베드를 해석할 수 있도록
-- 직접 외래키 관계를 추가한다.
--
-- 기존: patients.user_id, doctors.user_id, user_profiles.user_id 가 모두
-- auth.users(id)를 각각 참조 → 둘 사이 직접 관계가 없어
-- PostgREST가 `user_profiles(...)` 임베드를 해석하지 못함
-- ("Could not find a relationship ... in the schema cache").
--
-- user_profiles.user_id 는 PRIMARY KEY, patients/doctors.user_id 는 UNIQUE 이므로
-- 아래 FK는 1:1 관계로 유효하다.

ALTER TABLE patients
    ADD CONSTRAINT patients_user_profile_fk
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE;

ALTER TABLE doctors
    ADD CONSTRAINT doctors_user_profile_fk
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE;

-- PostgREST 스키마 캐시 갱신
NOTIFY pgrst, 'reload schema';
