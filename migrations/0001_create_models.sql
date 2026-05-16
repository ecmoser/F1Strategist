-- Migration: create tables for fitted models cache and strategy cache
-- Requires Postgres. Uses pgcrypto for gen_random_uuid(); enable if available.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Stores fitted degradation models per circuit + compound + season
CREATE TABLE IF NOT EXISTS fitted_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  circuit_id TEXT NOT NULL,
  season INTEGER NOT NULL,
  compound TEXT NOT NULL,
  model_version TEXT NOT NULL,
  model_type TEXT NOT NULL,
  parameters JSONB NOT NULL,
  provenance JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index to support fast lookup by circuit+compound+season+version
CREATE INDEX IF NOT EXISTS idx_fitted_models_lookup
  ON fitted_models (circuit_id, compound, season, model_version);
CREATE INDEX IF NOT EXISTS idx_fitted_models_season ON fitted_models (season);

-- Cache computed strategies and raw request/response payloads
CREATE TABLE IF NOT EXISTS strategy_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id TEXT,
  season INTEGER,
  round INTEGER,
  driver_id TEXT,
  request JSONB,
  response JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_by_request ON strategy_cache (request_id);
CREATE INDEX IF NOT EXISTS idx_strategy_lookup ON strategy_cache (season, round, driver_id);

-- Optional table to store circuit metadata and derived pit-lane info
CREATE TABLE IF NOT EXISTS circuit_metadata (
  circuit_id TEXT PRIMARY KEY,
  name TEXT,
  location JSONB,
  pit_lane_length_m NUMERIC,
  pit_lane_speed_limit_kph NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Retention: purge older fitted models (example: keep last 3 seasons)
-- DELETE FROM fitted_models WHERE season < extract(year from now())::int - 3;

-- Example helper query: get latest model for a circuit+compound
-- SELECT * FROM fitted_models
-- WHERE circuit_id = 'silverstone' AND compound = 'SOFT'
-- ORDER BY season DESC, created_at DESC LIMIT 1;
