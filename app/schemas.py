from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class StrategyRequest(BaseModel):
    season: int = Field(..., example=2024)
    round: int = Field(..., example=5)
    circuit_id: Optional[str] = Field(None, example="hungaroring")
    total_laps: int = Field(..., example=56)
    current_lap: int = Field(..., example=28)
    starting_compound: str = Field(..., example="SOFT")
    current_tire_age: int = Field(..., description="laps on current tire", example=12)
    allowed_compounds: Optional[List[str]] = Field(
        None, example=["HARD", "MEDIUM", "SOFT"]
    )
    max_pitstops: Optional[int] = None
    driver_id: Optional[str] = None
    weather_override: Optional[Dict[str, Any]] = None
    custom_pit_loss_override: Optional[float] = None


class PitPlan(BaseModel):
    pit_laps: List[int]
    compounds: List[str]
    predicted_total_time: float  # seconds
    per_lap_times: List[float]
    confidence: Dict[str, float]


class StrategyResponse(BaseModel):
    request_id: str
    created_at: datetime
    plans: List[PitPlan]


class StrategyRecord(BaseModel):
    id: str
    request: StrategyRequest
    response: StrategyResponse


class CircuitModelEntry(BaseModel):
    compound: str
    model_type: str
    parameters: Dict[str, Any]
    pit_loss_seconds: float


class CircuitModel(BaseModel):
    circuit_id: str
    season: int
    models: List[CircuitModelEntry]
