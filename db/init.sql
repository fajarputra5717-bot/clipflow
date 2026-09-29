-- ClipFlow base schema (reconstructed 2026-09-26 after VM loss).
--
-- Runs ONCE, only when the Postgres volume is empty
-- (/docker-entrypoint-initdb.d). Everything added later lives in
-- ensure_schema() in backend/app/main.py, which runs on every boot and
-- is the real migration log. Do not add new columns here; add them there.
--
-- Rebuilt from every SQL statement in main.py / worker.py. IDs are TEXT
-- because the code joins clip_candidates.id = candidate_versions.candidate_id
-- (TEXT) and inserts Python str(uuid4()) values.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS app_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_videos (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    youtube_url  TEXT NOT NULL UNIQUE,
    title        TEXT,
    source_path  TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
    id                   TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    source_video_id      TEXT REFERENCES source_videos(id),
    job_type             TEXT NOT NULL DEFAULT 'clip_pipeline',
    status               TEXT NOT NULL DEFAULT 'queued',
    progress             INT  NOT NULL DEFAULT 0,
    message              TEXT,
    layout               TEXT NOT NULL DEFAULT 'auto',
    platform             TEXT,
    split_ratio          TEXT,
    subtitle_style       JSONB,
    subtitle_font        TEXT,
    subtitle_size        INT,
    transcript           TEXT,
    transcript_segments  JSONB,
    error_message        TEXT,
    error_stage          TEXT,
    started_at           TIMESTAMPTZ,
    completed_at         TIMESTAMPTZ,
    review_ready_at      TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs (status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs (created_at DESC);

CREATE TABLE IF NOT EXISTS clip_candidates (
    id                 TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    job_id             TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    clip_index         INT,
    start_time         DOUBLE PRECISION,
    end_time           DOUBLE PRECISION,
    duration_seconds   DOUBLE PRECISION,
    reason             TEXT,
    ai_title           TEXT,
    title              TEXT,
    manual_title       TEXT,
    subtitle_segments  JSONB,
    subtitle_override  TEXT,
    subtitle_text      TEXT,
    content_type       TEXT,
    rating             INT,
    score              DOUBLE PRECISION,
    status             TEXT NOT NULL DEFAULT 'queued',
    progress           INT  NOT NULL DEFAULT 0,
    message            TEXT,
    error_message      TEXT,
    error_stage        TEXT,
    face_crop          JSONB,
    preview_path       TEXT,
    render_path        TEXT,
    final_path         TEXT,
    thumbnail_path     TEXT,
    rendered_at        TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_candidates_job    ON clip_candidates (job_id);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON clip_candidates (status);

CREATE TABLE IF NOT EXISTS rendered_clips (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    candidate_id  TEXT NOT NULL REFERENCES clip_candidates(id) ON DELETE CASCADE,
    platform      TEXT,
    output_path   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
