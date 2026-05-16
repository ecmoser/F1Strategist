# External APIs: jolpica (primary) and Ergast (fallback)

Summary
- Primary HTTP metadata API: jolpica-f1 — base: http://api.jolpi.ca/ergast/f1/
- Fallback/reference: Ergast — base: http://ergast.com/api/f1/
- Telemetry & lap-level data: FastF1 (python package), used via library calls.

Required endpoints (jolpica)
- GET /ergast/f1/circuits/ — circuit metadata (id, name, location)
- GET /ergast/f1/{season}/{round}/laps/ — lap-level times and structure
- GET /ergast/f1/{season}/{round}/pitstops/ — pitstop records (lap, duration, stop)
- GET /ergast/f1/{season}/{round}/results/ — race results
- GET /ergast/f1/{season}/{round}/qualifying/ — qualifying results (grid)

Ergast (fallback) example endpoints
- GET /{season}/{round}/laps.json
- GET /{season}/{round}/pitstops.json
- Docs: http://ergast.com/mrd/

Sample JSON snippets (representative)

Laps (simplified Ergast-style)
{
  "MRData": {
    "RaceTable": {
      "Races": [
        {
          "season": "2024",
          "round": "5",
          "raceName": "Example GP",
          "Laps": [
            {
              "number": "1",
              "Timings": [
                { "driverId": "hamilton", "time": "90.123" }
              ]
            },
            {
              "number": "2",
              "Timings": [
                { "driverId": "hamilton", "time": "89.456" }
              ]
            }
          ]
        }
      ]
    }
  }
}

Pitstops (simplified)
{
  "MRData": {
    "RaceTable": {
      "Races": [
        {
          "season": "2024",
          "round": "5",
          "PitStops": [
            { "driverId": "hamilton", "lap": "23", "time": "27.5" },
            { "driverId": "verstappen", "lap": "24", "time": "25.8" }
          ]
        }
      ]
    }
  }
}

Notes on fields we will use
- lap time: seconds (string or numeric) — convert to float seconds
- pitstop lap: lap number and pit duration (seconds) — used to estimate pit-loss
- circuit id: mapping to FastF1 circuit names/ids

Rate-limit and caching strategy
- Cache all fetched endpoints locally (Postgres or file cache) keyed by `season,round,endpoint`.
- Add short TTL for live data (e.g., 30s) and longer TTL for historical data (24h+).
- Implement exponential backoff for HTTP 429/5xx with jitter.
- Bulk prefetch during precompute step; avoid repeated calls in optimizer flow.

Authentication & stability
- Both jolpica and Ergast are public; no auth required. Still implement retries and local caching.
- Validate responses against expected shapes and fail gracefully when missing fields.

Implementation notes / examples
- Use `requests` or `httpx` with a session, timeouts, and retry/backoff policy.
- Example URL: `http://api.jolpi.ca/ergast/f1/2024/5/laps/` (returns laps for season 2024 round 5)

Next actions
- Implement a small `scripts/sample_fetch.py` to fetch and save sample JSON for a target `season`/`round` (used for testing and to validate parsing code). 
- Wire caching layer (DB or file) when building the data loader in step 4.
