# Database schema for F1Strategist

This document describes the PostgreSQL schema used to cache fitted degradation models and computed strategies.

Tables

- `fitted_models`
  - Purpose: store per-circuit, per-compound degradation model parameters and provenance.
  - Key fields:
    - `id` (UUID): primary key
    - `circuit_id` (text)
    - `season` (int)
    - `compound` (text)
    - `model_version` (text)
    - `model_type` (text) — e.g. `exponential`, `polynomial`
    - `parameters` (jsonb) — fitted parameters and covariance information
    - `provenance` (jsonb) — source info: event, session, fitting options
    - `created_at` (timestamptz)

  - Indexes:
    - `(circuit_id, compound, season, model_version)` for fast lookup
    - `season` for retention queries

- `strategy_cache`
  - Purpose: cache computed strategy responses and associated request payloads for auditing and fast retrieval.
  - Key fields:
    - `id` (UUID)
    - `request_id` (text) — client-provided or generated id
    - `season`, `round`, `driver_id` — lookup keys
    - `request` (jsonb) — original request payload
    - `response` (jsonb) — optimizer result
    - `created_at` (timestamptz)

  - Indexes:
    - `request_id` for direct lookup
    - `(season, round, driver_id)` for query by race/driver

- `circuit_metadata`
  - Purpose: store circuit-level metadata and derived pit-lane info (optional enrichment).
  - Fields: `circuit_id`, `name`, `location` (jsonb), `pit_lane_length_m`, `pit_lane_speed_limit_kph`.

Retention policy

- Fitted models: keep last N seasons (default: 3). Example purge query:

```sql
DELETE FROM fitted_models
WHERE season < extract(year from now())::int - 3;
```

- Strategy cache: TTL-based purge (e.g., delete entries older than X days) or manual/administrative purge.

Maintenance

- Run periodic vacuum/analyze on the tables.
- Recompute and store new `fitted_models` via background precompute tasks; use `model_version` to control updates.

Examples

- Get latest fitted model for a circuit/compound:

```sql
SELECT * FROM fitted_models
WHERE circuit_id = 'silverstone' AND compound = 'SOFT'
ORDER BY season DESC, created_at DESC
LIMIT 1;
```

- Insert a new fitted model (example):

```sql
INSERT INTO fitted_models (circuit_id, season, compound, model_version, model_type, parameters, provenance)
VALUES ('silverstone', 2024, 'SOFT', 'v1', 'exponential', '{"a":1.2, "b":0.03}', '{"source":"fastf1"}');
```

Notes

- Use `jsonb` for flexible parameter storage and to make it easy to include uncertainty metadata (covariance matrices, fit diagnostics).
- Consider adding a materialized view that exposes the chosen model per `circuit_id+compound` for the current seasons to speed queries.
