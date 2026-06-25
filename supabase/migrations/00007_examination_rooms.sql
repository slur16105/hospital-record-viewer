-- Migration 00007: Create examination_rooms table

CREATE TABLE examination_rooms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  room_number VARCHAR(20) NOT NULL,
  department_id UUID NOT NULL REFERENCES departments(id),
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (department_id, room_number)
);

-- updated_at trigger (reuse function defined in initial schema)
CREATE TRIGGER set_examination_rooms_updated_at
  BEFORE UPDATE ON examination_rooms
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS
ALTER TABLE examination_rooms ENABLE ROW LEVEL SECURITY;

CREATE POLICY "examination_rooms_select" ON examination_rooms
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "examination_rooms_insert" ON examination_rooms
  FOR INSERT TO authenticated WITH CHECK (is_admin());

CREATE POLICY "examination_rooms_update" ON examination_rooms
  FOR UPDATE TO authenticated USING (is_admin()) WITH CHECK (is_admin());
