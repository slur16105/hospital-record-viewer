-- Add room_id to medical_records to link consultations to examination rooms

ALTER TABLE medical_records
    ADD COLUMN IF NOT EXISTS room_id UUID REFERENCES examination_rooms(id);

CREATE INDEX IF NOT EXISTS idx_medical_records_room ON medical_records(room_id);
