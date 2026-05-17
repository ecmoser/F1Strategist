#!/usr/bin/env python3
"""Fit degradation models to cleaned lap data and save to database.

Usage:
  python scripts/fit_and_save.py --input data/ --db sqlite:///./dev.db
  python scripts/fit_and_save.py --input data/cleaned_2023_1.csv --dry-run
"""

import argparse
import logging
import os
import sys
import pandas as pd
from typing import Optional

# Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lib.degradation import fit_all_models
from lib.pit_loss import median_pit_loss_with_ci, save_pit_loss_results
from lib.persistence import get_engine, save_fitted_model


def parse_args():
    p = argparse.ArgumentParser(description="Fit and save degradation models")
    p.add_argument("--input", required=True, help="Input CSV file or directory of CSVs")
    p.add_argument("--db", help="SQLAlchemy database URL (optional, defaults to DATABASE_URL env)")
    p.add_argument("--version", default="v1", help="Model version string")
    p.add_argument("--dry-run", action="store_true", help="Do not save to database")
    return p.parse_args()


def process_file(file_path: str, engine, version: str, dry_run: bool, log: logging.Logger):
    log.info("Processing %s", file_path)
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        log.error("Failed to read %s: %s", file_path, e)
        return

    required = {"circuit_id", "compound", "tire_age", "lap_time_s", "season"}
    if not required.issubset(df.columns):
        log.error("Missing columns in %s. Required: %s", file_path, required)
        return

    # Filter out pit laps for degradation fitting
    df_fit = df[~df["is_pit"]].copy()

    # 1. Fit Degradation Models
    # Group by circuit and compound (and season)
    for (circuit_id, season, compound), group in df_fit.groupby(["circuit_id", "season", "compound"]):
        if len(group) < 5:
            log.warning("Skipping %s %s: too few laps (%d)", circuit_id, compound, len(group))
            continue

        log.info("Fitting degradation for %s %s (season %d)...", circuit_id, compound, season)
        results = fit_all_models(group)
        best_type = results["best"]
        best_model = results[best_type]

        if best_model["params"] is None:
            log.error("Fitting failed for %s %s", circuit_id, compound)
            continue

        log.info("Best model for %s %s: %s (AIC: %.2f)", 
                 circuit_id, compound, best_type, best_model["aic"])

        if not dry_run:
            provenance = {
                "source_file": os.path.basename(file_path),
                "n_laps": best_model["n"],
                "rss": best_model["rss"],
                "all_models": {m: {"aic": results[m]["aic"], "bic": results[m]["bic"]} 
                               for m in ("linear", "quadratic", "exponential")}
            }
            try:
                with engine.begin() as conn:
                    save_fitted_model(
                        conn,
                        circuit_id=str(circuit_id),
                        season=int(season),
                        compound=str(compound),
                        model_version=version,
                        model_type=best_type,
                        parameters=best_model,
                        provenance=provenance
                    )
                log.info("Saved degradation %s %s to database", circuit_id, compound)
            except Exception as e:
                log.error("Failed to save degradation %s %s: %s", circuit_id, compound, e)

    # 2. Estimate Pit Loss
    log.info("Estimating pit loss for %s (season %d)...", os.path.basename(file_path), int(df["season"].iloc[0]))
    try:
        # Compute pit loss per circuit (already grouping by circuit_id in the file)
        pit_results = median_pit_loss_with_ci(df, group_cols=["circuit_id"])
        if not dry_run:
            with engine.begin() as conn:
                save_pit_loss_results(conn, pit_results, season=int(df["season"].iloc[0]), model_version=version)
            log.info("Saved pit loss results to database")
    except Exception as e:
        log.error("Failed to compute/save pit loss: %s", e)


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    log = logging.getLogger("fit_and_save")

    engine = None
    if not args.dry_run:
        try:
            engine = get_engine(args.db)
        except Exception as e:
            log.error("Database initialization failed: %s", e)
            return

    if os.path.isdir(args.input):
        files = [os.path.join(args.input, f) for f in os.listdir(args.input) if f.endswith(".csv")]
    else:
        files = [args.input]

    for f in files:
        process_file(f, engine, args.version, args.dry_run, log)


if __name__ == "__main__":
    main()
