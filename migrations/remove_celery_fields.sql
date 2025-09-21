-- Migration Script: Remove Celery Dependencies
-- Date: 2025-09-20
-- Purpose: Update database schema to remove Celery-specific fields

-- Start transaction
BEGIN;

-- 1. Add new columns to processing_jobs table if they don't exist
ALTER TABLE processing_jobs
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS progress_percentage INTEGER DEFAULT 0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    ADD COLUMN IF NOT EXISTS progress_message TEXT,
    ADD COLUMN IF NOT EXISTS processing_time_seconds NUMERIC,
    ADD COLUMN IF NOT EXISTS error_message TEXT,
    ADD COLUMN IF NOT EXISTS result JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10);

-- 2. Update job_type values to include 'processing'
ALTER TABLE processing_jobs
    DROP CONSTRAINT IF EXISTS processing_jobs_job_type_check;

ALTER TABLE processing_jobs
    ADD CONSTRAINT processing_jobs_job_type_check
    CHECK (job_type IN ('processing', 'text_extraction', 'chunking', 'embedding_generation', 'full_pipeline'));

-- 3. Drop celery_task_id column if it exists
ALTER TABLE processing_jobs
    DROP COLUMN IF EXISTS celery_task_id,
    DROP COLUMN IF EXISTS worker_id;

-- 4. Drop old indexes if they exist
DROP INDEX IF EXISTS idx_jobs_worker_id;
DROP INDEX IF EXISTS idx_jobs_celery_task_id;

-- 5. Create new index for user_id if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON processing_jobs(user_id);

-- 6. Update existing records with default values where needed
UPDATE processing_jobs
SET progress_percentage = COALESCE(progress_percentage, 0),
    priority = COALESCE(priority, 5),
    result = COALESCE(result, '{}')
WHERE progress_percentage IS NULL OR priority IS NULL OR result IS NULL;

-- Commit transaction
COMMIT;

-- Verify the changes
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'processing_jobs'
ORDER BY ordinal_position;