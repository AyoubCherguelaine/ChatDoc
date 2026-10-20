-- Enable pgcrypto (provides gen_random_uuid(), used by backend/schema.sql)
-- before the schema is applied. Idempotent and harmless if the function is built-in.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
