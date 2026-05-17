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
    
    # memo = {(lap, compound, tire_age, n_stops): (min_time, best_action)}
    # best_action: ('stay', None) or ('pit', new_compound)
    memo: Dict[Tuple[int, str, int, int], Tuple[float, Any]] = {}

    def solve(lap: int, compound: str, tire_age: int, n_stops: int) -> Tuple[float, Any]:
        if lap > total_laps:
            return 0.0, None
        
        state = (lap, compound, tire_age, n_stops)
        if state in memo:
            return memo[state]
        
        # Option 1: Stay
        model = model_dict.get(compound)
        if not model:
            # Fallback if model missing, though it shouldn't be for current compound
            lap_time = 100.0 # heavy penalty
        else:
            lap_time = predict_lap_time(tire_age, model.model_type, model.parameters["params"])
            
        stay_time, _ = solve(lap + 1, compound, tire_age + 1, n_stops)
        best_time = lap_time + stay_time
        best_action = ("stay", None)
        
        # Option 2: Pit
        if n_stops < max_stops:
            pit_loss = request.custom_pit_loss_override or (model.pit_loss_seconds if model else 20.0)
            
            for next_compound in allowed_compounds:
                # In real F1, you'd usually switch to a DIFFERENT compound unless mandatory rules are met
                # For now, allow any allowed compound
                next_model = model_dict.get(next_compound)
                if not next_model: continue
                
                # The lap where we pit takes extra time
                # Next lap we start with tire_age 1
                pit_time, _ = solve(lap + 1, next_compound, 1, n_stops + 1)
                total_pit_time = lap_time + pit_loss + pit_time
                
                if total_pit_time < best_time:
                    best_time = total_pit_time
                    best_action = ("pit", next_compound)
        
        memo[state] = (best_time, best_action)
        return best_time, best_action

    # Initial call
    # Note: We need to handle the rule of using 2 different compounds.
    # To keep it simple for now, we'll just run the DP.
    
    best_time, _ = solve(current_lap, request.starting_compound, request.current_tire_age, 0)
    
    # Reconstruct the best plan
    pit_laps = []
    compounds = []
    per_lap_times = []
    
    curr_lap = current_lap
    curr_compound = request.starting_compound
    curr_age = request.current_tire_age
    curr_stops = 0
    
    while curr_lap <= total_laps:
        time, action = solve(curr_lap, curr_compound, curr_age, curr_stops)
        
        model = model_dict.get(curr_compound)
        l_time = predict_lap_time(curr_age, model.model_type, model.parameters["params"])
        
        if action[0] == "pit":
            pit_laps.append(curr_lap)
            next_c = action[1]
            compounds.append(next_c)
            
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
        predicted_total_time=best_time,
        per_lap_times=per_lap_times,
        confidence={"score": 0.85} # Placeholder
    )
    
    return [plan]
