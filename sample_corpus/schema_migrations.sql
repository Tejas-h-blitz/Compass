-- Database Migration: User Access and Search Telemetry Schema
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS query_telemetry (
    id BIGSERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    retrieval_strategy VARCHAR(32) NOT NULL,
    latency_milliseconds DOUBLE PRECISION NOT NULL,
    result_count INTEGER NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_telemetry_strategy ON query_telemetry(retrieval_strategy);
