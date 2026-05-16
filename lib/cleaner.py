from typing import Optional
import pandas as pd
import numpy as np


def clean_laps_df(df: pd.DataFrame, season: int, round: int) -> pd.DataFrame:
    """Clean a laps DataFrame (in-memory) and return standardized rows.

    Expects columns like `LapNumber` or `lapNumber`, `LapTime` (timedelta) or
    `lap_time_s` (seconds), `Driver`, `Compound`, and optional pit markers
    (`PitInTime`, `PitOutTime`, `PitDuration`, `IsPit`) and `TrackStatus`.
    """
    df = df.copy()

    # Normalize lap time to seconds
    if "lap_time_s" not in df.columns:
        if "LapTime" in df.columns:
            try:
                df["lap_time_s"] = df["LapTime"].dt.total_seconds()
            except Exception:
                df["lap_time_s"] = pd.to_timedelta(df["LapTime"]).dt.total_seconds()
        elif "Time" in df.columns:
            df["lap_time_s"] = pd.to_timedelta(df["Time"]).dt.total_seconds()
        else:
            df["lap_time_s"] = np.nan

    # detect pit laps
    is_pit = pd.Series(False, index=df.index)
    for col in ("PitInTime", "PitOutTime", "PitStopTime", "PitDuration"):
        if col in df.columns:
            is_pit = is_pit | df[col].notna()
    for col in ("IsPit", "Pit"):
        if col in df.columns:
            is_pit = is_pit | df[col].astype(bool)
    df["is_pit"] = is_pit

    # mark in/out laps (per driver)
    df = (
        df.sort_values(["Driver", "LapNumber"])
        if "Driver" in df.columns
        else df.sort_values("LapNumber")
    )
    df["is_inout"] = False
    if "Driver" in df.columns:
        for _, g in df.groupby("Driver"):
            idx = g.index
            pits = g["is_pit"].values
            inout = [False] * len(g)
            for i, pit in enumerate(pits):
                if pit:
                    if i - 1 >= 0:
                        inout[i - 1] = True
                    if i + 1 < len(g):
                        inout[i + 1] = True
            df.loc[idx, "is_inout"] = inout
    else:
        pits = df["is_pit"].values
        inout = [False] * len(df)
        for i, pit in enumerate(pits):
            if pit:
                if i - 1 >= 0:
                    inout[i - 1] = True
                if i + 1 < len(df):
                    inout[i + 1] = True
        df["is_inout"] = inout

    # drop missing lap times
    df = df[~df["lap_time_s"].isna()].copy()

    # exclude laps under SC/VSC if TrackStatus exists
    sc_mask = None
    for col in ("TrackStatus", "TrackFlag", "TrackFlags"):
        if col in df.columns:
            vals = df[col].astype(str).str.lower()
            sc_mask = (
                vals.str.contains("safety")
                | vals.str.contains("vsc")
                | vals.str.contains("sc")
            )
            break
    if sc_mask is not None:
        df = df[~sc_mask]

    # remove outliers per driver (lap_time > median*1.4)
    def remove_outliers(g):
        med = np.median(g["lap_time_s"].values)
        return g[g["lap_time_s"] <= med * 1.4]

    if "Driver" in df.columns:
        # pass include_groups=False to avoid pandas FutureWarning about grouping columns
        df = df.groupby("Driver", group_keys=False).apply(
            remove_outliers, include_groups=False
        )
    else:
        df = remove_outliers(df)

    # standardize output columns
    out = pd.DataFrame()
    out["season"] = season
    out["round"] = round
    out["driver"] = df["Driver"] if "Driver" in df.columns else df.get("driverId")
    out["lap_number"] = pd.to_numeric(
        df["LapNumber"] if "LapNumber" in df.columns else df.get("lapNumber", df.index),
        errors="coerce",
    )
    out["lap_time_s"] = df["lap_time_s"]
    out["compound"] = df["Compound"] if "Compound" in df.columns else df.get("compound")
    out["is_pit"] = df["is_pit"]
    out["is_inout"] = df["is_inout"]

    # omit first lap
    out = out[out["lap_number"] != 1]

    return out.reset_index(drop=True)
