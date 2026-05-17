from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit


def linear_model(lap, a, b):
    return a + b * lap


def quadratic_model(lap, a, b, c):
    return a + b * lap + c * lap * lap


def exponential_model(lap, a, b, c):
    # a + b * exp(c * lap)
    return a + b * np.exp(c * lap)


def compute_aic_bic(n: int, rss: float, k: int) -> Tuple[float, float]:
    # Avoid log(0)
    s2 = rss / n if rss > 0 else 1e-12
    aic = 2 * k + n * np.log(s2)
    bic = k * np.log(n) + n * np.log(s2)
    return aic, bic


def fit_model(laps: pd.DataFrame, model: str = "exponential") -> Dict[str, Any]:
    """Fit a degradation model to `laps` DataFrame.

    Expects `laps` to have columns: `tire_age`, `lap_time_s`.
    Returns dict with: model, params, cov, rss, aic, bic, n, k
    """
    if laps is None or laps.empty:
        raise ValueError("laps must be a non-empty DataFrame")

    if not {"tire_age", "lap_time_s"}.issubset(laps.columns):
        raise ValueError("laps must contain 'tire_age' and 'lap_time_s' columns")

    x = laps["tire_age"].astype(float).values
    y = laps["lap_time_s"].astype(float).values
    n = len(y)

    if model == "linear":
        p0 = [np.median(y), 0.0]
        func = linear_model
    elif model == "quadratic":
        p0 = [np.median(y), 0.0, 0.0]
        func = quadratic_model
    elif model == "exponential":
        p0 = [np.min(y), (np.median(y) - np.min(y)) or 1.0, -0.001]
        func = exponential_model
    else:
        raise ValueError(f"Unknown model: {model}")

    try:
        popt, pcov = curve_fit(func, x, y, p0=p0, maxfev=10000)
    except Exception:
        # fallback: return empty fit
        return {
            "model": model,
            "params": None,
            "cov": None,
            "rss": float("inf"),
            "aic": float("inf"),
            "bic": float("inf"),
            "n": n,
            "k": 0,
        }

    y_hat = func(x, *popt)
    resid = y - y_hat
    rss = float(np.sum(resid**2))
    k = len(popt)
    aic, bic = compute_aic_bic(n, rss, k)

    return {
        "model": model,
        "params": popt.tolist(),
        "cov": pcov.tolist() if pcov is not None else None,
        "rss": rss,
        "aic": aic,
        "bic": bic,
        "n": n,
        "k": k,
    }


def fit_all_models(laps: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Fit multiple candidate models and return stats for each, plus best by AIC."""
    results = {}
    for m in ("linear", "quadratic", "exponential"):
        results[m] = fit_model(laps, model=m)

    # determine best by AIC
    aics = {m: r["aic"] for m, r in results.items()}
    best = min(aics, key=lambda k: aics[k])
    results["best"] = best
    return results
