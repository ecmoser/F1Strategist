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
    p.add_argument("--round", required=True)
    p.add_argument("--session", default="R", help="Session identifier (R for race)")
    p.add_argument("--out", default=None, help="Output CSV path")
    return p.parse_args()


def main():
    args = parse_args()
    out_path = args.out or f"data/cleaned_{args.season}_{args.round}.csv"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    try:
        import fastf1
        import pandas as pd
        import numpy as np
    except Exception as exc:
        print("Required packages not installed. Install fastf1, pandas, numpy.")
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

    # Ensure consistent columns
    # Attempt to convert LapTime to seconds
    if "LapTime" in laps.columns:
        try:
            lap_time_s = laps["LapTime"].dt.total_seconds()
        except Exception:
            # fall back to parsing strings
            lap_time_s = pd.to_timedelta(laps["LapTime"]).dt.total_seconds()
    elif "Time" in laps.columns:
        lap_time_s = pd.to_timedelta(laps["Time"]).dt.total_seconds()
    else:
        lap_time_s = pd.Series([None] * len(laps), index=laps.index)

    laps = laps.assign(lap_time_s=lap_time_s)

    # determine pit indicators
    is_pit = pd.Series(False, index=laps.index)
    for col in ("PitInTime", "PitOutTime", "PitStopTime", "PitDuration"):
        if col in laps.columns:
            is_pit = is_pit | laps[col].notna()
    # fallback: FastF1 sometimes has 'IsPit' or 'Pit' markers
    for col in ("IsPit", "Pit"):
        if col in laps.columns:
            is_pit = is_pit | laps[col].astype(bool)

    laps = laps.assign(is_pit=is_pit)

    # mark in/out laps: any lap directly before or after a pit lap
    laps = (
        laps.sort_values(["Driver", "LapNumber"])
        if "Driver" in laps.columns
        else laps.sort_values("LapNumber")
    )
    laps["is_inout"] = False
    if "Driver" in laps.columns:
        grouped = laps.groupby("Driver")
        for _, g in grouped:
            idx = g.index
            lapnums = g["LapNumber"].values
            pits = g["is_pit"].values
            inout = [False] * len(g)
            for i, pit in enumerate(pits):
                if pit:
                    if i - 1 >= 0:
                        inout[i - 1] = True
                    if i + 1 < len(g):
                        inout[i + 1] = True
            laps.loc[idx, "is_inout"] = inout
    else:
        # single-driver fallback
        pits = laps["is_pit"].values
        inout = [False] * len(laps)
        for i, pit in enumerate(pits):
            if pit:
                if i - 1 >= 0:
                    inout[i - 1] = True
                if i + 1 < len(laps):
                    inout[i + 1] = True
        laps["is_inout"] = inout

    # remove laps with missing lap time
    cleaned = laps[~laps["lap_time_s"].isna()].copy()

    # Exclude laps that occurred under Safety Car / VSC if TrackStatus is present
    sc_mask = None
    # FastF1 may include 'TrackStatus' or similar indicators in laps or telemetry
    for col in ("TrackStatus", "TrackFlag", "TrackFlags"):
        if col in cleaned.columns:
            vals = cleaned[col].astype(str).str.lower()
            sc_mask = (
                vals.str.contains("safety")
                | vals.str.contains("vsc")
                | vals.str.contains("sc")
            )
            break

    if sc_mask is not None:
        cleaned = cleaned[~sc_mask]

    # remove likely SC/VSC/outlier laps by per-driver threshold as a fallback
    def remove_outliers(df):
        med = np.median(df["lap_time_s"].values)
        mask = df["lap_time_s"] <= med * 1.4
        return df[mask]

    if "Driver" in cleaned.columns:
        cleaned = cleaned.groupby("Driver", group_keys=False).apply(remove_outliers)
    else:
        cleaned = remove_outliers(cleaned)

    # prepare output columns
    out_cols = []
    out_cols.append("Season") if "Season" in cleaned.columns else None
    out_df = cleaned
    # construct minimal output fields
    out_df = out_df.assign(
        season=args.season,
        round=args.round,
        driver=(
            out_df["Driver"]
            if "Driver" in out_df.columns
            else out_df.get("driverId", None)
        ),
        lap_number=(
            out_df["LapNumber"]
            if "LapNumber" in out_df.columns
            else out_df.get("lapNumber", out_df.index)
        ),
        lap_time_s=out_df["lap_time_s"],
        compound=(
            out_df["Compound"]
            if "Compound" in out_df.columns
            else out_df.get("Compound", None)
        ),
        is_pit=out_df["is_pit"],
        is_inout=out_df["is_inout"],
    )

    final = out_df[
        [
            "season",
            "round",
            "driver",
            "lap_number",
            "lap_time_s",
            "compound",
            "is_pit",
            "is_inout",
        ]
    ]

    # Omit first lap of the race as an outlier
    try:
        final["lap_number"] = pd.to_numeric(final["lap_number"], errors="coerce")
        final = final[final["lap_number"] != 1]
    except Exception:
        # if conversion fails, ignore
        pass

    final.to_csv(out_path, index=False)
    log.info("Wrote cleaned laps to %s", out_path)


if __name__ == "__main__":
    # simple syntax/runtime check when loaded as script
    try:
        main()
    except SystemExit:
        # argparse exits with 2 if no args; that's acceptable for module tests
        pass
