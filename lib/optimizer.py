from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from lib.degradation import predict_lap_time
from app.schemas import StrategyRequest, PitPlan, CircuitModelEntry


def compute_strategy(
    request: StrategyRequest, 
    models: List[CircuitModelEntry],
    max_plans: int = 3
) -> List[PitPlan]:
    """Find optimal pit strategies using Dynamic Programming.
    
    Returns a ranked list of PitPlan objects.
    """
    total_laps = request.total_laps
    current_lap = request.current_lap
    max_stops = request.max_pitstops or 3
    
    # Map compound names to model entries
    model_dict = {m.compound: m for m in models}
    allowed_compounds = request.allowed_compounds or list(model_dict.keys())
    
    # memo = {(lap, compound, tire_age, n_stops, used_multiple): (min_time, best_action)}
    # best_action: ('stay', None) or ('pit', new_compound)
    memo: Dict[Tuple[int, str, int, int, bool], Tuple[float, Any]] = {}

    def solve(lap: int, compound: str, tire_age: int, n_stops: int, used_multiple: bool) -> Tuple[float, Any]:
        if lap > total_laps:
            # Penalty if we didn't use at least 2 compounds in a full race
            if not used_multiple and total_laps > 1:
                return 1e6, None 
            return 0.0, None
        
        state = (lap, compound, tire_age, n_stops, used_multiple)
        if state in memo:
            return memo[state]
        
        # Option 1: Stay
        model = model_dict.get(compound)
        lap_time = predict_lap_time(tire_age, model.model_type, model.parameters["params"]) if model else 100.0
            
        stay_time, _ = solve(lap + 1, compound, tire_age + 1, n_stops, used_multiple)
        best_time = lap_time + stay_time
        best_action = ("stay", None)
        
        # Option 2: Pit
        if n_stops < max_stops:
            pit_loss = request.custom_pit_loss_override or (model.pit_loss_seconds if model else 20.0)
            
            for next_compound in allowed_compounds:
                next_model = model_dict.get(next_compound)
                if not next_model: continue
                
                # Check if this new compound is different from the VERY first one used
                # For simplicity, we assume starting_compound is the first one.
                is_different = (next_compound != request.starting_compound) or used_multiple
                
                pit_time, _ = solve(lap + 1, next_compound, 1, n_stops + 1, is_different)
                total_pit_time = lap_time + pit_loss + pit_time
                
                if total_pit_time < best_time:
                    best_time = total_pit_time
                    best_action = ("pit", next_compound)
        
        memo[state] = (best_time, best_action)
        return best_time, best_action

    # Initial call
    best_time, _ = solve(current_lap, request.starting_compound, request.current_tire_age, 0, False)
    
    # Reconstruct the best plan
    pit_laps = []
    compounds = []
    per_lap_times = []
    
    curr_lap = current_lap
    curr_compound = request.starting_compound
    curr_age = request.current_tire_age
    curr_stops = 0
    curr_used_multiple = False
    
    while curr_lap <= total_laps:
        time, action = solve(curr_lap, curr_compound, curr_age, curr_stops, curr_used_multiple)
        
        model = model_dict.get(curr_compound)
        l_time = predict_lap_time(curr_age, model.model_type, model.parameters["params"]) if model else 100.0
        
        if action and action[0] == "pit":
            pit_laps.append(curr_lap)
            next_c = action[1]
            compounds.append(next_c)
            
            if next_c != request.starting_compound:
                curr_used_multiple = True
            
            pit_loss = request.custom_pit_loss_override or (model.pit_loss_seconds if model else 20.0)
            per_lap_times.append(l_time + pit_loss)
            
            curr_compound = next_c
            curr_age = 1
            curr_stops += 1
        else:
            per_lap_times.append(l_time)
            curr_age += 1
            
        curr_lap += 1

    plan = PitPlan(
        pit_laps=pit_laps,
        compounds=compounds,
        predicted_remaining_time=best_time,
        per_lap_times=per_lap_times,
        confidence={"score": 0.85} # Placeholder
    )
    
    return [plan]
