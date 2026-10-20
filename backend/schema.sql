-- DocuChat backend database schema.
-- Run once against the PostgreSQL+pgvector database:
--   PGPASSWORD=docuchat123 psql -h 127.0.0.1 -p 5436 -U postgres -d docuchat -f backend/schema.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS docuchat;

-- Users (auth)
CREATE TABLE IF NOT EXISTS docuchat.users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    name          TEXT,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- Uploaded documents
CREATE TABLE IF NOT EXISTS docuchat.documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES docuchat.users(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size       BIGINT NOT NULL,
    mime_type       TEXT NOT NULL,
    page_count      INT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Chunk text + metadata (FAISS holds the embeddings on disk; this is for
-- listing, preview and index rebuild on server restart)
CREATE TABLE IF NOT EXISTS docuchat.chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES docuchat.documents(id) ON DELETE CASCADE,
    page_index    INT,
    chunk_index   INT,
    text          TEXT NOT NULL,
    metadata      JSONB,
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- Per-document chat sessions
CREATE TABLE IF NOT EXISTS docuchat.sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES docuchat.users(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES docuchat.documents(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Persisted chat messages
CREATE TABLE IF NOT EXISTS docuchat.messages (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES docuchat.sessions(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chunks_doc     ON docuchat.chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_msgs_session   ON docuchat.messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_doc   ON docuchat.sessions(document_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user  ON docuchat.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_docs_user      ON docuchat.documents(user_id);
