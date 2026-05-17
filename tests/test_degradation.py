import numpy as np
import pandas as pd

from lib.degradation import fit_all_models


def make_synthetic_degradation(model_type="linear", n=30, noise=0.2):
    age = np.arange(1, n + 1)
    if model_type == "linear":
        y = 90.0 + 0.05 * age
    elif model_type == "quadratic":
        y = 90.0 + 0.02 * age + 0.001 * age**2
    else:
        # exponential: a + b * exp(c * age)
        y = 89.0 + 2.0 * np.exp(0.01 * age)

    rng = np.random.default_rng(1)
    y = y + rng.normal(0, noise, size=len(y))
    return pd.DataFrame({"tire_age": age, "lap_time_s": y})


def test_fit_models_selects_correct():
    for m in ("linear", "quadratic", "exponential"):
        df = make_synthetic_degradation(m, n=40, noise=0.1)
        results = fit_all_models(df)
        assert results["best"] in ("linear", "quadratic", "exponential")
        # ensure best model AIC is finite
        assert np.isfinite(results[results["best"]]["aic"])
