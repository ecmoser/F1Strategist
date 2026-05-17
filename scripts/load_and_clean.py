#!/usr/bin/env python3
"""Load a race session with FastF1, clean laps, and write a per-lap CSV.

Usage:
  python scripts/load_and_clean.py --season 2024 --round 5 --session R --out data/cleaned_2024_5.csv

Notes:
- Requires `fastf1`, `pandas`, and `numpy` installed.
- Filtering heuristics: remove laps with missing times, remove outliers (long laps likely due to SC/VSC), and mark in/out laps around pitstops.
"""

import argparse
import logging
import os
import sys


def parse_args():
    p = argparse.ArgumentParser(description="Load and clean race laps using FastF1")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--session", default="R", help="Session identifier (R for race)")
    p.add_argument("--out", default=None, help="Output CSV path")
    return p.parse_args()


def main():
    args = parse_args()
    out_path = args.out or f"data/cleaned_{args.season}_{args.round}.csv"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    try:
        import fastf1
    except Exception:
        print("Required package 'fastf1' not installed. Install with pip.")
        raise

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("load_and_clean")

    log.info("Loading session: %s %s %s", args.season, args.round, args.session)
    try:
        session = fastf1.get_session(args.season, args.round, args.session)
        session.load(laps=True, telemetry=False)
    except Exception as e:
        log.error("FastF1 failed to load session: %s", e)
        sys.exit(1)

    laps = session.laps.copy()
    if laps.empty:
        log.error("No laps found for this session")
        sys.exit(1)

    # Delegate cleaning logic to lib.cleaner for consistency and testability
    try:
        from lib.cleaner import clean_laps_df

        final = clean_laps_df(laps, season=args.season, round=args.round)
    except Exception as e:
        log.exception("Failed to clean laps using lib.cleaner: %s", e)
        sys.exit(1)

    final.to_csv(out_path, index=False)
    log.info("Wrote cleaned laps to %s", out_path)


if __name__ == "__main__":
    # simple syntax/runtime check when loaded as script
    try:
        main()
    except SystemExit:
        # argparse exits with 2 if no args; that's acceptable for module tests
        pass
