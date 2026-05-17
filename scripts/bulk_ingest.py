#!/usr/bin/env python3
"""Bulk ingest F1 seasons by calling load_and_clean.py for every round.

Usage:
  python scripts/bulk_ingest.py --season 2023
  python scripts/bulk_ingest.py --season 2024 --limit 5
"""

import argparse
import logging
import subprocess
import sys
import os

def parse_args():
    p = argparse.ArgumentParser(description="Bulk ingest F1 season data")
    p.add_argument("--season", type=int, required=True, help="Season year (e.g. 2023)")
    p.add_argument("--limit", type=int, help="Limit number of rounds to process")
    p.add_argument("--session", default="R", help="Session type (default: R for Race)")
    return p.parse_args()

def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    log = logging.getLogger("bulk_ingest")

    try:
        import fastf1
    except ImportError:
        log.error("fastf1 not installed. Run pip install fastf1")
        sys.exit(1)

    log.info(f"Fetching schedule for {args.season}...")
    try:
        schedule = fastf1.get_event_schedule(args.season)
        # Filter for actual races (exclude tests/pre-season if any)
        # RoundNumber > 0 usually indicates a championship round
        rounds = schedule[schedule['RoundNumber'] > 0]
    except Exception as e:
        log.error(f"Failed to fetch schedule: {e}")
        sys.exit(1)

    if rounds.empty:
        log.error(f"No rounds found for season {args.season}")
        return

    rounds_to_process = rounds.head(args.limit) if args.limit else rounds
    
    log.info(f"Found {len(rounds_to_process)} rounds to process.")

    for _, event in rounds_to_process.iterrows():
        round_num = event['RoundNumber']
        event_name = event['EventName']
        
        log.info(f"--- Processing Round {round_num}: {event_name} ---")
        
        out_file = f"data/cleaned_{args.season}_{round_num}.csv"
        
        cmd = [
            sys.executable, 
            "scripts/load_and_clean.py",
            "--season", str(args.season),
            "--round", str(round_num),
            "--session", args.session,
            "--out", out_file
        ]
        
        try:
            # Run load_and_clean as a subprocess to isolate FastF1 cache/loading logic
            subprocess.run(cmd, check=True)
            log.info(f"Successfully processed Round {round_num}")
        except subprocess.CalledProcessError:
            log.error(f"Failed to process Round {round_num}")
            continue

    log.info("Bulk ingestion complete.")

if __name__ == "__main__":
    main()
