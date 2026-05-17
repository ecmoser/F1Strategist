from typing import Iterable, List, Dict, Sequence
import numpy as np
import pandas as pd


def extract_pit_losses(
    laps: pd.DataFrame, window: int = 3, require_inout: bool = False
) -> List[float]:
    """Extract pit-loss values (seconds) from a cleaned laps DataFrame.

    Strategy:
    - For each driver, find rows where `is_pit` is True.
    - For a pit event at lap i, compute a baseline lap time as the median lap
      time of non-pit laps within +/- `window` laps (excluding in/out laps if available).
    - Pit loss = pit lap_time_s - baseline.

    Returns list of pit loss seconds across all drivers and events.
    """
    if laps is None or laps.empty:
        return []

    required_cols = {"driver", "lap_number", "lap_time_s", "is_pit"}
    if not required_cols.issubset(set(laps.columns)):
        raise ValueError(f"laps DataFrame must contain columns: {required_cols}")

    losses: List[float] = []
    for driver, g in laps.groupby("driver"):
        g = g.sort_values("lap_number").reset_index(drop=True)
        for idx, row in g[g["is_pit"]].iterrows():
            lapnum = row["lap_number"]
            pit_time = float(row["lap_time_s"])

            # select nearby non-pit laps
            low = max(0, idx - window)
            high = min(len(g) - 1, idx + window)
            window_df = g.loc[low:high]
            # exclude pit and optionally in/out laps
            mask = ~window_df["is_pit"]
            if require_inout and "is_inout" in window_df.columns:
                mask = mask & ~window_df["is_inout"]
            candidates = window_df.loc[mask, "lap_time_s"].astype(float).values
            if len(candidates) == 0:
                continue
            baseline = float(np.median(candidates))
            losses.append(pit_time - baseline)

    return losses


def median_pit_loss_with_ci(
    laps: pd.DataFrame,
    group_cols: Sequence[str] = ("circuit",),
    n_boot: int = 2000,
    seed: int = 42,
) -> Dict[str, Dict[str, float]]:
    """Compute median pit loss and bootstrap 95% CI per group.

    `group_cols` is a list of columns to group by (e.g., `['circuit']` or `['season','round']`).
    Returns dict mapping group key (tuple or single value) to stats: median, ci_low, ci_high, count.
    """
    if isinstance(group_cols, str):
        group_cols = [group_cols]

    results: Dict[str, Dict[str, float]] = {}
    rng = np.random.default_rng(seed)

    grouped = laps.groupby(list(group_cols))
    for key, group in grouped:
        losses = extract_pit_losses(group)
        if len(losses) == 0:
            continue
        losses = np.array(losses)
        median = float(np.median(losses))

        # bootstrap medians
        boot_meds = []
        for _ in range(n_boot):
            sample = rng.choice(losses, size=len(losses), replace=True)
            boot_meds.append(np.median(sample))
        ci_low = float(np.percentile(boot_meds, 2.5))
        ci_high = float(np.percentile(boot_meds, 97.5))

        results_key = key if not isinstance(key, tuple) or len(group_cols) > 1 else key
        results[repr(results_key)] = {
            "median": median,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "count": int(len(losses)),
        }

    return results


def save_pit_loss_results(
    conn,
    results: Dict[str, Dict[str, float]],
    season: int,
    model_version: str = "v1",
):
    """Persist pit-loss summaries to the database using `save_fitted_model`.

    `results` is the output of `median_pit_loss_with_ci`.
    Key is repr of circuit_id or (circuit_id, compound).
    """
    from lib.persistence import save_fitted_model

    for key_repr, stats in results.items():
        # results key is repr(circuit_id) or repr((circuit_id, compound))
        # we need to extract them back if possible, or just use them as circuit_id
        try:
            import ast
            key = ast.literal_eval(key_repr)
        except Exception:
            key = key_repr

        if isinstance(key, tuple):
            circuit_id = str(key[0])
            compound = str(key[1])
        else:
            circuit_id = str(key)
            compound = "ALL"

        save_fitted_model(
            conn,
            circuit_id=circuit_id,
            season=season,
            compound=compound,
            model_version=model_version,
            model_type="pit_loss",
            parameters=stats,
            provenance={"source": "historical_bootstrap"}
        )
