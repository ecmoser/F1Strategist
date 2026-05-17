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
    # adjacent laps should NOT be marked as in/out anymore
    assert not out.loc[out["lap_number"] == 2, "is_inout"].iloc[0]
    assert not out.loc[out["lap_number"] == 4, "is_inout"].iloc[0]
    # lap 3 is pit so it is also marked as in/out
    assert out.loc[out["lap_number"] == 3, "is_inout"].iloc[0]


def test_sc_filtering():
    df = make_base_df()
    # set lap 4 to safety
    df.loc[df["LapNumber"] == 4, "TrackStatus"] = "Safety Car"
    out = clean_laps_df(df, season=2023, round=1)
    # lap 4 should be removed
    assert 4 not in out["lap_number"].values


def test_tire_age_computation():
    # Two stints: 1-3 (Medium), 4-6 (Hard)
    rows = []
    for lap in range(1, 4):
        rows.append({"Driver": "A", "LapNumber": lap, "LapTime": pd.to_timedelta(90, unit="s"), "Compound": "M"})
    for lap in range(4, 7):
        rows.append({"Driver": "A", "LapNumber": lap, "LapTime": pd.to_timedelta(92, unit="s"), "Compound": "H"})
    df = pd.DataFrame(rows)
    out = clean_laps_df(df, season=2023, round=1)
    
    # Lap 1 is omitted, so stint 1 starts at lap 2
    # M: lap 2 (age 2), lap 3 (age 3) -> Wait, stint starts at lap 1.
    # If lap 1 is omitted AFTER computing tire age, we should see age 2, 3.
    # In clean_laps_df: tire_age is computed BEFORE omit lap 1.
    assert out.loc[out["lap_number"] == 2, "tire_age"].iloc[0] == 2
    assert out.loc[out["lap_number"] == 3, "tire_age"].iloc[0] == 3
    # Hard starts at lap 4
    assert out.loc[out["lap_number"] == 4, "tire_age"].iloc[0] == 1
    assert out.loc[out["lap_number"] == 5, "tire_age"].iloc[0] == 2
    assert out.loc[out["lap_number"] == 6, "tire_age"].iloc[0] == 3
