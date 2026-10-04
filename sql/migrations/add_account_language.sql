-- Per-user UI preference. Existing and newly created accounts default to English.
ALTER TABLE public.accounts
  ADD COLUMN IF NOT EXISTS language text NOT NULL DEFAULT 'en'
  CHECK (language IN ('en', 'es'));

-- Backout: deploy the previous app version first. Leaving this column is harmless;
-- optionally remove it afterward with ALTER TABLE public.accounts DROP COLUMN language.
