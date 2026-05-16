import pandas as pd
import numpy as np

from lib.pit_loss import extract_pit_losses, median_pit_loss_with_ci


def make_synthetic(circuit: str, losses: list):
    # baseline lap time 90s; for each loss, create a pit lap with lap_time = 90+loss
    rows = []
    lapnum = 1
    for loss in losses:
        # two normal laps, then pit lap
        rows.append(
            {
                "circuit": circuit,
                "driver": "X",
                "lap_number": lapnum,
                "lap_time_s": 90.0,
                "is_pit": False,
            }
        )
        lapnum += 1
        rows.append(
            {
                "circuit": circuit,
                "driver": "X",
                "lap_number": lapnum,
                "lap_time_s": 90.0,
                "is_pit": False,
            }
        )
        lapnum += 1
        rows.append(
            {
                "circuit": circuit,
                "driver": "X",
                "lap_number": lapnum,
                "lap_time_s": 90.0 + loss,
                "is_pit": True,
            }
        )
        lapnum += 1
    return pd.DataFrame(rows)


def test_extract_pit_losses_and_stats():
    a = make_synthetic("A", [20.0, 22.0, 19.0])
    b = make_synthetic("B", [25.0, 27.0])
    df = pd.concat([a, b], ignore_index=True)

    losses = extract_pit_losses(df)
    assert len(losses) == 5
    # medians should be close to known
    stats = median_pit_loss_with_ci(df, group_cols=("circuit",), n_boot=500, seed=1)
    # keys are repr of tuple (since groupby key is string -> repr('A'))
    assert any("'A'" in k or "A" in k for k in stats.keys())
    # find A stats
    a_key = next(k for k in stats.keys() if "A" in k)
    b_key = next(k for k in stats.keys() if "B" in k)
    assert abs(stats[a_key]["median"] - 20.0) < 1.0
    assert abs(stats[b_key]["median"] - 26.0) < 1.0
