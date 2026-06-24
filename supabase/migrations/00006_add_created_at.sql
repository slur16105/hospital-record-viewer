-- Migration 00006: Add created_at to doctors and patients tables
-- These were omitted from the initial schema.

ALTER TABLE doctors ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE patients ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
