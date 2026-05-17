import pytest
from lib.optimizer import compute_strategy
from app.schemas import StrategyRequest, CircuitModelEntry


def test_basic_one_stop_strategy():
    # Scenario: 20 laps total, start lap 1.
    # SOFT: base 90s, +1s per lap deg.
    # HARD: base 92s, +0.1s per lap deg.
    # Pit loss: 15s.
    
    soft_model = CircuitModelEntry(
        compound="SOFT",
        model_type="linear",
        parameters={"params": [90.0, 1.0]}, # 90 + 1.0*age
        pit_loss_seconds=15.0
    )
    hard_model = CircuitModelEntry(
        compound="HARD",
        model_type="linear",
        parameters={"params": [92.0, 0.1]}, # 92 + 0.1*age
        pit_loss_seconds=15.0
    )
    
    request = StrategyRequest(
        season=2024,
        round=1,
        total_laps=20,
        current_lap=1,
        starting_compound="SOFT",
        current_tire_age=1,
        allowed_compounds=["SOFT", "HARD"],
        max_pitstops=1
    )
    
    plans = compute_strategy(request, [soft_model, hard_model])
    
    assert len(plans) == 1
    plan = plans[0]
    
    # Check if it chose to pit
    assert len(plan.pit_laps) > 0
    # For a 20 lap race, it should probably pit around the middle
    # Soft lap times: 90, 91, 92, 93, 94, 95, 96, 97, 98, 99...
    # Hard lap times: 92, 92.1, 92.2...
    # Pit at lap 5: Soft laps 1-5 (90, 91, 92, 93, 94+15), Hard laps 6-20.
    assert "HARD" in plan.compounds


def test_no_pit_if_too_expensive():
    # Pit loss 100s, SOFT tires degrade slowly
    soft_model = CircuitModelEntry(
        compound="SOFT",
        model_type="linear",
        parameters={"params": [90.0, 0.01]},
        pit_loss_seconds=100.0
    )
    
    request = StrategyRequest(
        season=2024,
        round=1,
        total_laps=10,
        current_lap=1,
        starting_compound="SOFT",
        current_tire_age=1,
        allowed_compounds=["SOFT"],
        max_pitstops=1
    )
    
    plans = compute_strategy(request, [soft_model])
    assert len(plans[0].pit_laps) == 0
