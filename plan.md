# Create an application that determines the optimal pit strategy for a driver in an F1 race. 

As Claude described it:

"An API that takes a race, driver, and current lap as input and returns the mathematically optimal pit stop strategy — modeled from real historical tire degradation data via FastF1."

We will need to be able to get data about drivers and their lap times and tire wear, use that data to create trends about tire performance in relation to laps, and use that to optimize race strategy around an f1 circuit.

Data should filter out laps behind safety and virtual safety cars, as well as in or out laps (laps directly before or after pit stops).

The goal is to have 3 endpoints that can be called: a POST /strategy that predicts the optimal strategy for a race, a GET /strategy/{id} that looks back at the optimal vs the actual strategy for a race, and a GET /circuits/{id} that returns the tire deg curves and pit loss times for the requested circuit.

We will use the FastF1 python package for lap and telemetry data (docs found at https://theoehrly-fast-f1.mintlify.app/api/), the jolpica-f1 API for race metadata (https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md), and a PostgreSQL cache for our computed models.

Our engine should include a deg model with a curve fit for tire, age, and circuit, an optimizer, and a pit model which considers pit loss and undercut windows.

Here is a potential repo structure:

```
f1-strategy-engine/
├── api/
│   ├── main.py               # FastAPI app, lifespan, middleware
│   ├── routers/
│   │   ├── strategy.py       # /strategy endpoints
│   │   └── circuits.py       # /circuits endpoints
│   └── schemas/
│       ├── requests.py       # Pydantic input models
│       └── responses.py      # Pydantic output models
├── core/
│   ├── data/
│   │   └── loader.py         # FastF1 fetching + cleaning
│   ├── models/
│   │   ├── degradation.py    # Curve fitting per compound/circuit
│   │   └── optimizer.py      # DP strategy solver
│   └── db/
│       └── cache.py          # SQLAlchemy models + session
├── scripts/
│   └── precompute.py         # Offline: fit + store all deg models
├── tests/
│   ├── test_degradation.py
│   └── test_optimizer.py
├── docker-compose.yml        # App + Postgres
├── Dockerfile
├── requirements.txt
└── README.md                 # With example curl calls + screenshots
```

The project will be run inside of a virtual environment and have a requirements.txt file that contains the required packages. I'm not sure if I want the docker integration just yet, that will come at the end if we have time. 

Here is the plan for how we will approach the project:

## Plan: F1Strategist Implementation

TL;DR: Build a FastAPI service that ingests telemetry (FastF1) and race metadata (jolpica/Ergast), fits per-circuit & per-compound tire-degradation models (nonlinear), caches fitted models in PostgreSQL (recent 3 seasons), and exposes `POST /strategy`, `GET /strategy/{id}`, and `GET /circuits/{id}`. Initial choices: primary HTTP metadata API = jolpica (fallback Ergast), FastF1 backend = auto-select best available, pit-loss = median historical pitstop lap-delta, allow live predictions but accept relaxed latency (<10s) for full compute.

**Steps (detailed)**
1. Define public API schemas (OpenAPI & Pydantic)
- Action: Produce precise request and response schemas for `POST /strategy`, `GET /strategy/{id}`, `GET /circuits/{id}`. Use `season+round` race id, `current_lap`, `starting_compound`, `current_tire_age`, `max_pitstops` optional, and a `confidence` field in responses.
- Deliverables: `specs/openapi.yaml` snippets and `app/schemas.py` (Pydantic models).
- AI prompt: "Design a complete OpenAPI/Pydantic schema for `POST /strategy` that accepts `{season:int, round:int, current_lap:int, starting_compound:str, current_tire_age:int, allowed_compounds:list[str], max_pitstops:int?}` and returns a ranked list of pit plans with per-plan `predicted_total_time`, `per_lap_times`, and `confidence` intervals. Suggest sensible defaults and error codes."
- Notes: Include units (seconds, laps), field validation ranges, and error responses for missing model data.

2. Confirm external APIs & sample responses
- Action: Lock primary metadata source to jolpica (`http://api.jolpi.ca/ergast/f1/`) with Ergast (`http://ergast.com/api/f1/`) as fallback. Verify sample responses for laps, pitstops, circuits, and results.
- Deliverables: `docs/external_apis.md` with base URLs, required endpoints, sample JSON, and rate-limit strategy.
- AI prompt: "Fetch example JSON responses (or provide schema examples) for jolpica endpoints: `/ergast/f1/{season}/{round}/laps/`, `/pitstops/`, `/circuits/`, and `/results/`. Recommend caching/backoff approach for rate limits."

3. Design DB cache schema and retention policy
- Action: Create PostgreSQL schema to store fitted models and computed strategies keyed by `(circuit_id, compound, season, model_version)` and retain only last 3 seasons.
- Deliverables: `migrations/0001_create_models.sql`, `docs/db_schema.md`.
- AI prompt: "Design a PostgreSQL schema for caching per-circuit per-compound degradation models with indexes for fast lookup by circuit+compound+season and queries for purging older seasons."

4. Implement data loader & cleaning prototype
- Action: Script to load one session with FastF1 (auto backend selection), remove SC/VSC and in/out laps, extract per-lap times, compounds, and pitstop markers.
- Deliverables: `scripts/load_and_clean.py`, sample output `tests/data/sample_race.parquet`.
- AI prompt: "Write a Python script using FastF1 to load a race, detect and drop SC/VSC laps and in/out laps, and output a cleaned per-lap CSV with columns `[season, round, driver, lap_number, lap_time_s, compound, is_pit]`. Include comments on detection heuristics."

5. Define pit-loss estimation and prototype
- Action: Implement median historical pitstop lap-delta per circuit (robust to outliers). Provide confidence bounds (IQR or bootstrap).
- Deliverables: `lib/pit_loss.py`, `notebooks/pit_loss_analysis.ipynb`.
- AI prompt: "Provide Python code to compute median pit-loss per circuit from historical laps+pitstops and compute a 95% CI using bootstrap."

6. Fit degradation models (nonlinear)
- Action: Implement exponential and polynomial fits per stint, compute uncertainty and model-selection criteria (AIC/BIC), and choose best model per circuit+compound.
- Deliverables: `lib/degradation.py`, `scripts/fit_models.py`.
- AI prompt: "Give Python code that fits exponential and polynomial degradation models to per-lap time series and computes AIC/BIC to select the best model. Include uncertainty (parameter covariances)."

7. Build optimizer (DP + heuristic)
- Action: Implement dynamic programming optimizer that considers per-lap degradation, pit-loss, compound constraints, and returns top-N strategies. Add greedy heuristic fallback for speed.
- Deliverables: `lib/optimizer.py`, `tests/test_optimizer.py` with synthetic scenarios.
- AI prompt: "Write a DP algorithm to find the optimal pit lap(s) given per-lap pace projections and pit-stop cost; also include a fast greedy heuristic. Provide complexity analysis."

8. FastAPI service and routers
- Action: Scaffold FastAPI app; implement routers for `POST /strategy`, `GET /strategy/{id}`, `GET /circuits/{id}`. Wire DB, cache lookup, model fetch, optimizer call, and background task queue for live predictions.
- Deliverables: `app/main.py`, `app/routers/strategy.py`, `app/routers/circuits.py`, `app/db.py`, `app/models.py` (ORM), `app/background.py` (worker tasks).
- AI prompt: "Scaffold a FastAPI app exposing `POST /strategy` and `GET /circuits/{id}`. Show Pydantic request/response models, DB dependency injection, and example responses."
- Notes: For live predictions, use an async background worker (Celery/RQ) and websocket or polling for updates.

9. Tests, CI, and sample data
- Action: Add unit tests (pytest) for loader, pit-loss, degradation fitting, and optimizer. Add CI workflow to run tests and lint.
- Deliverables: `tests/`, `.github/workflows/ci.yml`, `requirements-dev.txt`.
- AI prompt: "Generate pytest test cases for the pit-loss estimator and optimizer using synthetic datasets. Provide CI workflow YAML for GitHub Actions to run tests."

10. Performance & production readiness
- Action: Precompute models for common circuits, implement TTL-based cache purge, add logging/metrics, and set up monitoring. Tune optimizer (vectorized computations, C extensions if needed).
- Deliverables: `tasks/precompute.py`, `docs/operational.md`, `monitoring/` notes.
- AI prompt: "Recommend caching and background-worker strategies for a FastAPI service that needs live and historical predictions; include sample Celery task signatures and TTL rules."

**APIs & Endpoints (finalized)**
- jolpica-f1 (primary)
  - Base URL: `http://api.jolpi.ca/ergast/f1/`
  - Endpoints needed:
    - `GET /ergast/f1/circuits/` — circuit metadata
    - `GET /ergast/f1/{season}/{round}/laps/` — lap times
    - `GET /ergast/f1/{season}/{round}/pitstops/` — pitstop records
    - `GET /ergast/f1/{season}/{round}/results/` — race results
    - `GET /ergast/f1/{season}/{round}/qualifying/` — qualifying data
  - Docs: `https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md`

- Ergast (fallback/reference)
  - Base URL: `http://ergast.com/api/f1/`
  - Example endpoints:
    - `GET /{season}/{round}/laps.json`
    - `GET /{season}/{round}/pitstops.json`
  - Docs: `http://ergast.com/mrd/`

- FastF1 (python package)
  - Calls used: `fastf1.get_session(...)`, `Session.load()`, `fastf1.get_event(...)`
  - Docs: `https://theoehrly-fast-f1.mintlify.app/api/`

**File-level TODO (create / modify)**
- `specs/openapi.yaml` — OpenAPI snippets for public endpoints
- `app/schemas.py` — Pydantic models
- `app/main.py` — FastAPI app entry
- `app/routers/strategy.py` — POST /strategy router
- `app/routers/circuits.py` — circuits router
- `app/db.py` — DB session and ORM wiring
- `app/models.py` — SQLAlchemy ORM models (fitted_model, strategy_cache)
- `lib/pit_loss.py` — pit-loss estimation utilities
- `lib/degradation.py` — fitting & model selection
- `lib/optimizer.py` — DP optimizer + heuristics
- `scripts/load_and_clean.py` — data loader prototype
- `scripts/fit_models.py` — batch model fitting
- `migrations/0001_create_models.sql` — DB migration
- `notebooks/pit_loss_analysis.ipynb` — analysis notebook
- `tests/` — unit and integration tests
- `docs/external_apis.md`, `docs/db_schema.md`, `docs/operational.md`

**Verification / Acceptance criteria**
1. Unit tests pass for loader, pit-loss, fitters, and optimizer.
2. Integration test: run `scripts/load_and_clean.py` on one race, fit model, store in DB, and `POST /strategy` returns plans within runtime SLO (acceptable `<10s`).
3. Statistical validation: predicted vs actual pit laps on historical sample < configured error thresholds.

**Decisions & Assumptions**
- Primary HTTP metadata API: jolpica; fallback Ergast.
- FastF1 backend: auto-select best available (user can override later).
- Pit-loss: median historical lap-delta.
- Keep cached models for recent 3 seasons.
- Live predictions supported via background tasks (may need faster SLO tuning).

**Next actions I will take if you approve**
1. Generate `specs/openapi.yaml` and `app/schemas.py` drafts.
2. Scaffold the FastAPI project tree and the `scripts/load_and_clean.py` prototype.
3. Create initial DB migration SQL for the fitted models table.