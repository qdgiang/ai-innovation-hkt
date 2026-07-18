-- EverMind canonical Postgres DDL (postgres:17).
-- Applied automatically by infra/docker-compose.yml (initdb mount); Railway gets
-- it via Alembic from Phase 2. SQLite dev uses SQLAlchemy create_all instead and
-- enforces the citation rule app-side (backend/app/repository.py) — the trigger
-- below is the Postgres-side enforcement. Keep in sync with backend/app/models.py.

CREATE TABLE teams (
    name         text PRIMARY KEY,
    display_name text
);

CREATE TABLE messages (
    id         text PRIMARY KEY,
    source     text NOT NULL CHECK (source IN ('telegram', 'transcript', 'replay')),
    channel    text NOT NULL,
    team       text REFERENCES teams (name),
    author     text NOT NULL,
    ts         timestamptz NOT NULL,
    text       text NOT NULL,
    thread_ref text,
    raw_ref    text NOT NULL
);

CREATE INDEX idx_messages_channel_ts ON messages (channel, ts);
CREATE INDEX idx_messages_team_ts ON messages (team, ts);

CREATE TABLE records (
    id           text PRIMARY KEY,
    type         text NOT NULL CHECK (type IN ('decision', 'blocker', 'status')),
    title        text NOT NULL,
    body         jsonb NOT NULL,
    team         text REFERENCES teams (name),
    created_from text NOT NULL CHECK (created_from IN ('marker', 'llm')),
    confidence   real NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status       text NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'superseded', 'rejected')),
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_records_team_type_status ON records (team, type, status);

CREATE TABLE record_sources (
    record_id  text NOT NULL REFERENCES records (id) ON DELETE CASCADE,
    message_id text NOT NULL REFERENCES messages (id),
    PRIMARY KEY (record_id, message_id)
);

CREATE TABLE digests (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team         text REFERENCES teams (name),
    period_start date NOT NULL,
    period_end   date NOT NULL,
    content_md   text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- Contract: every record has >=1 citation. Deferred to commit so a record and
-- its record_sources rows can be inserted in the same transaction.
CREATE FUNCTION assert_record_has_citation() RETURNS trigger AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM record_sources WHERE record_id = NEW.id) THEN
        RAISE EXCEPTION 'record % has no citations — contract violation', NEW.id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER records_require_citation
    AFTER INSERT ON records
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION assert_record_has_citation();

-- Contract: messages are immutable once ingested.
CREATE FUNCTION messages_are_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'messages are immutable source evidence (id %)', OLD.id;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER messages_no_update
    BEFORE UPDATE ON messages
    FOR EACH ROW EXECUTE FUNCTION messages_are_immutable();
