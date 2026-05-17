# F1Strategist — Progress and Roadmap

Date: 2026-05-17

This file documents what has been implemented so far, the final project goal, and a detailed, actionable plan for the remaining work with commands, file locations, and suggested AI prompts to accelerate development. It is written to help another agent (or a human) pick up where we left off and complete the project end-to-end.

---

## Final goal

Build an automated strategy engine for Formula 1 race pit-stop planning that:

- Ingests historical race lap data (FastF1 / external APIs) and cleans it.
- Estimates pit-loss distributions per circuit/compound and fits per-stint lap-time degradation models.
- Stores fitted models and metadata in a Postgres cache for fast lookups.
- Exposes a FastAPI service that accepts `StrategyRequest` payloads and returns optimized pit stop plans (PitPlan) using a dynamic programming + heuristic optimizer.
- Supports live predictions via background workers and a lightweight caching layer; production-ready with tests, CI, and monitoring.

---

## What we've completed (summary)

- Project scaffold and core files
  - `plan.md` — project spec and initial plan (working doc).
  - OpenAPI spec skeleton: `specs/openapi.yaml` and Pydantic models in `app/schemas.py`.

- Data ingestion / cleaning
  - `scripts/load_and_clean.py` — race session loader using FastF1 that saves cleaned per-lap CSVs.
  - `lib/cleaner.py` — centralized cleaning utility `clean_laps_df(df, season, round)` used by the script.
  - Unit tests: `tests/test_cleaner.py`.

- Pit-loss estimation
  - `lib/pit_loss.py` — `extract_pit_losses(...)` and `median_pit_loss_with_ci(...)` with bootstrap CIs.
  - Unit tests: `tests/test_pit_loss.py`.

- Degradation model fitting
  - `lib/degradation.py` — fitting routines for `linear`, `quadratic`, and `exponential` models; AIC/BIC computation and selection helpers (`fit_all_models`).
  - Unit tests: `tests/test_degradation.py`.

- Persistence
  - `migrations/0001_create_models.sql` — Postgres schema for `fitted_models`, `strategy_cache`, `circuit_metadata`.
  - `lib/persistence.py` — `get_engine()` and `save_fitted_model(...)` helper with Postgres JSONB usage and SQLite fallback.
  - Unit tests: `tests/test_persistence.py`.

- Testing and developer workflow
  - `requirements.txt` updated with runtime, test and dev dependencies (`fastf1`, `pytest`, `black`, `ruff`, etc.).
  - `tests/conftest.py` and `pytest.ini` added to ensure test runner imports project root.
  - All test suites pass locally (6 tests in current suite).

- Repo hygiene / automation
  - `docker-compose.yml` for Postgres + Adminer and migrations mounted for DB init.
  - `.env.example` with default Postgres env vars.

All changes are committed; recent commits include the cleaning refactor, pit-loss, persistence helper, and degradation model code/tests.

---

## Immediate goals (next work items)

We should now implement the remaining core pieces in this order (each step is actionable and includes commands, files to change, and suggested AI prompts):

1) Persist degradation fits into the DB (fitted_models)
   - Purpose: compute and store one fitted model per `(circuit_id, season, compound, model_version)`.
   - Files to add/update:
     - Add `scripts/fit_and_save.py` (CLI) that:
       - Loads cleaned CSVs (from `data/cleaned_*.csv`) or queries DB/cache.
       - Calls `lib.degradation.fit_all_models(...)` per stint/circuit/compound.
       - Selects best model and calls `lib.persistence.save_fitted_model(conn, ...)` to persist parameters and metadata.
     - Optionally add `lib/model_serialization.py` to convert numpy arrays/cov matrices to JSON-friendly objects.
   - Commands:
     - Run locally (sqlite dev):
       ```bash
       python scripts/fit_and_save.py --input data/cleaned_2023_1.csv --db sqlite:///./dev.db
       ```
     - Run against Postgres using `DATABASE_URL` env var and `get_engine()` from `lib.persistence`.
   - AI prompt (for code generation):
     - "Create a Python CLI script `scripts/fit_and_save.py` that reads cleaned per-lap CSVs or a directory, groups data by `circuit` and `compound`, fits degradation models with `lib.degradation.fit_all_models`, chooses the best model (by AIC), and persists the selected model parameters and provenance to Postgres using `lib.persistence.save_fitted_model`. Include logging and a `--dry-run` flag."

2) Improve pit-loss estimator & persist summaries
   - Purpose: compute per-circuit/compound pit-loss summary and store in `fitted_models` (or a new `pit_loss_summary` table) for quick lookup by the optimizer.
   - Actions:
     - Add a wrapper in `lib/pit_loss.py` to compute per-circuit medians and store via `save_fitted_model` (or add `save_pit_loss_summary` to `lib/persistence.py`).
     - Decide schema: store under `model_type = 'pit_loss'` with `parameters = {median, ci_low, ci_high, count}`.
   - AI prompt:
     - "Add a persistence wrapper that takes the output of `median_pit_loss_with_ci` and upserts records into `fitted_models` with `model_type='pit_loss'` and appropriate provenance fields. Provide tests using in-memory SQLite."

3) Implement the optimizer
   - Purpose: given current state and fitted models, compute an optimal pit plan (DP with heuristics).
   - Files to create:
     - `lib/optimizer.py` — core optimizer with a `compute_strategy(request, models)` API. Include a fallback greedy heuristic.
     - `tests/test_optimizer.py` with small deterministic scenarios (synthetic lap times and pit losses).
   - Key algorithm outline:
     - Discretize race time axis by lap.
     - Use dynamic programming to compute minimal expected total race time for reachable pit-stop schedules, using fitted degradation to predict lap times and pit-loss medians for cost of pitting.
     - Add constraints: maximum pit stops, compound availability, safety car adjustments.
   - AI prompt:
     - "Implement a DP-based pit stop optimizer `lib/optimizer.py` that consumes a `StrategyRequest` (start lap, fuel window, compounds, number of stops) and returns an optimal sequence of pit laps. Include a greedy fallback and unit tests."

4) FastAPI service + routers
   - Purpose: expose endpoints for `strategy`, `models`, and `health`.
   - Files to create:
     - `app/main.py` — FastAPI app with startup event to configure DB engine and cache.
     - `app/routers/strategy.py` — main `POST /strategy` endpoint that validates request, looks up models from DB, calls `lib.optimizer.compute_strategy`, and returns `StrategyResponse`.
     - `app/routers/models.py` — endpoints to list/get fitted models and reload cache.
   - Implementation notes:
     - Use dependency injection for DB (`get_engine`) and caching layer.
     - Use background tasks or Celery for long-running computations (fit jobs, re-training).
   - Commands to run locally:
     ```bash
     uvicorn app.main:app --reload
     curl -X POST http://localhost:8000/strategy -d @example_request.json
     ```
   - AI prompt:
     - "Generate a FastAPI app scaffold with endpoints `POST /strategy` and `GET /models/{circuit}` that wire into `lib.persistence` and `lib.optimizer`. Include Pydantic request/response models aligned with `app/schemas.py`."

5) Background workers and live predictions
   - Purpose: schedule re-fitting jobs, warm caches, and make streaming predictions.
   - Options: Celery + Redis or RQ; initial implementation can use FastAPI `BackgroundTasks` then migrate to Celery.
   - Steps:
     - Add `worker/` module and `docker-compose` service for Redis + worker.
     - Implement tasks: `fit_models_for_season`, `update_pit_loss_summaries`, `refresh_cache`.

6) Tests, CI and quality gate
   - Add GitHub Actions workflow `.github/workflows/ci.yml` to run tests, lint (ruff), format check (black --check), and build docs.
   - Ensure DB integration tests run with a Postgres service or use sqlite fallbacks.

7) Production readiness
   - Add Alembic migrations and a `manage.py` or `make` targets to run migrations on deploy.
   - Add metrics, logging, Sentry integration, and health checks.
   - Containerize app with a small `Dockerfile` and provide `docker-compose.prod.yml` for production.

---

## Developer notes, commands, and examples

- Run tests locally:
```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
pytest -q
```

- Start Postgres + Adminer locally (docker-compose):
```bash
docker-compose up -d
# Adminer: http://localhost:8080 (default creds in .env.example)
```

- Run the loader for a race (race example):
```bash
python scripts/load_and_clean.py --season 2023 --round 1 --session R --out data/cleaned_2023_1.csv
```

- Fit and persist models (dev idea):
```bash
# (after implementing scripts/fit_and_save.py)
python scripts/fit_and_save.py --input data/ --db "$DATABASE_URL"
```

---

## Suggested AI prompts for recurring tasks

- Generate CLI to fit and persist models:
  - "Create a CLI `scripts/fit_and_save.py` that consumes cleaned CSVs, groups by `circuit` and `compound`, runs `fit_all_models` per group, selects the best model by AIC, and persists the model via `lib.persistence.save_fitted_model`. Include `--dry-run` and `--db` flags."

- Implement DP optimizer with heuristics and tests:
  - "Implement `lib/optimizer.py` with a DP algorithm computing optimal pit laps minimizing race time using fitted degradation and pit-loss models; provide a greedy fallback and unit tests with synthetic scenarios."

- FastAPI endpoints wiring:
  - "Scaffold `app/main.py` + routers that expose `POST /strategy` and `GET /models/{circuit}` backed by `lib.persistence` and `lib.optimizer`. Include dependency injection for DB engine and caching."

---

## Potential pitfalls and recommendations

- Data Quality: FastF1 sessions can have missing fields or inconsistent column names; `lib.cleaner.clean_laps_df` centralizes heuristics but more edge-case tests are needed for telemetry-based TrackStatus, lap numbering gaps, and multi-driver stint overlaps.
- Statistical stability: Small sample sizes for pit-loss might inflate CIs. Consider pooling by circuit family or using hierarchical models later.
- Safety Car handling: The optimizer must consider safety car events; for now, the optimizer can use conservative estimates or query historical SC frequencies via Ergast when available.

---

If you want, I can now:

- Implement `scripts/fit_and_save.py` and a `save_pit_loss_summary` upsert in `lib.persistence` (small PR).
- Start the optimizer with a simple DP implementation and tests.
- Add the GitHub Actions CI workflow.

Tell me which item to start with and I will implement it and create commits.
