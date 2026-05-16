import pandas as pd
import numpy as np
from lib.cleaner import clean_laps_df


def make_base_df():
    # create a small sample for driver 'A' with 6 laps, pit at lap 3
    rows = []
    for lap in range(1, 7):
        row = {
            "Driver": "A",
            "LapNumber": lap,
            "LapTime": pd.to_timedelta(90 + (lap - 1) * 0.2, unit="s"),
            "Compound": "M",
        }
        if lap == 3:
            row["PitInTime"] = pd.Timestamp("2023-01-01 00:00:00")
        rows.append(row)
    return pd.DataFrame(rows)


def test_omit_lap1_and_pit_markers():
    df = make_base_df()
    out = clean_laps_df(df, season=2023, round=1)
    # lap 1 should be omitted
    assert 1 not in out["lap_number"].values
    # pit lap (3) should be marked as is_pit
    assert out.loc[out["lap_number"] == 3, "is_pit"].iloc[0]
    # adjacent laps should be marked as in/out
    assert out.loc[out["lap_number"] == 2, "is_inout"].iloc[0]
    assert out.loc[out["lap_number"] == 4, "is_inout"].iloc[0]


def test_sc_filtering():
    df = make_base_df()
    # set lap 4 to safety
    df.loc[df["LapNumber"] == 4, "TrackStatus"] = "Safety Car"
    out = clean_laps_df(df, season=2023, round=1)
    # lap 4 should be removed
    assert 4 not in out["lap_number"].values


def test_outlier_removal():
    df = make_base_df()
    # make lap 5 an extreme outlier
    df.loc[df["LapNumber"] == 5, "LapTime"] = pd.to_timedelta(999, unit="s")
    out = clean_laps_df(df, season=2023, round=1)
    assert 5 not in out["lap_number"].values
