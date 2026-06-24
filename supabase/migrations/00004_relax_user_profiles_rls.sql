-- Allow all authenticated users to SELECT user_profiles
-- Rationale: internal hospital system — staff/patient needs to see doctor names
-- in medical records. Previous policy (own profile only) blocked cross-user name lookups.

DROP POLICY IF EXISTS user_profiles_select ON user_profiles;

CREATE POLICY user_profiles_select ON user_profiles
    FOR SELECT USING (auth.uid() IS NOT NULL);
