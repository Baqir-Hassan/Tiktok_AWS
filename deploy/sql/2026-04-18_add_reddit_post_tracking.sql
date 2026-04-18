ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS source_post_id VARCHAR(32);

ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS source_permalink TEXT;

CREATE INDEX IF NOT EXISTS ix_jobs_source_post_id ON jobs (source_post_id);
