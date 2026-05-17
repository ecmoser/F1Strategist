from typing import Optional
import pandas as pd
import numpy as np


def clean_laps_df(df: pd.DataFrame, season: int, round: int, circuit_id: Optional[str] = None) -> pd.DataFrame:
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

    # In/out laps are already marked by the data as pit laps (via PitInTime/PitOutTime)
    # We do not mark adjacent laps.
    df["is_inout"] = df["is_pit"]

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
                | vals.str.contains("4")
                | vals.str.contains("6")
                | vals.str.contains("7")
            )
            break
    if sc_mask is not None:
        df = df[~sc_mask]

    # remove outliers per driver (lap_time > median*1.4)
    if "Driver" in df.columns:
        meds = df.groupby("Driver")["lap_time_s"].transform("median")
        df = df[df["lap_time_s"] <= meds * 1.4]
    else:
        med = df["lap_time_s"].median()
        df = df[df["lap_time_s"] <= med * 1.4]

    # Compute tire age per driver stint
    if "Driver" in df.columns and "Compound" in df.columns and "LapNumber" in df.columns:
        df = df.sort_values(["Driver", "LapNumber"])
        # A stint change is a change in driver or compound
        # Or if there was a pit stop? Usually compound change implies pit stop.
        # But same compound after pit stop is also a new stint.
        # We can use is_pit to mark stint boundaries too.
        stint_boundary = (df["Driver"] != df["Driver"].shift()) | \
                         (df["Compound"] != df["Compound"].shift()) | \
                         (df["is_pit"].shift(fill_value=False))
        df["stint_id"] = stint_boundary.cumsum()
        df["tire_age"] = df.groupby("stint_id").cumcount() + 1
    else:
        df["tire_age"] = np.nan

    # standardize output columns
    out = pd.DataFrame()
    out["season"] = season
    out["round"] = round
    out["circuit_id"] = circuit_id
    out["driver"] = df["Driver"] if "Driver" in df.columns else df.get("driverId")
    out["lap_number"] = pd.to_numeric(
        df["LapNumber"] if "LapNumber" in df.columns else df.get("lapNumber", df.index),
        errors="coerce",
    )
    out["lap_time_s"] = df["lap_time_s"]
    out["compound"] = df["Compound"] if "Compound" in df.columns else df.get("compound")
    out["tire_age"] = df["tire_age"]
    out["is_pit"] = df["is_pit"]
    out["is_inout"] = df["is_inout"]

    # omit first lap
    out = out[out["lap_number"] != 1]

    return out.reset_index(drop=True)
