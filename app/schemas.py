from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class StrategyRequest(BaseModel):
    season: int = Field(..., json_schema_extra={"example": 2024})
    round: int = Field(..., json_schema_extra={"example": 5})
    circuit_id: Optional[str] = Field(None, json_schema_extra={"example": "hungaroring"})
    total_laps: int = Field(..., json_schema_extra={"example": 56})
    current_lap: int = Field(..., json_schema_extra={"example": 28})
    starting_compound: str = Field(..., json_schema_extra={"example": "SOFT"})
    current_tire_age: int = Field(..., description="laps on current tire", json_schema_extra={"example": 12})
    allowed_compounds: Optional[List[str]] = Field(
        None, json_schema_extra={"example": ["HARD", "MEDIUM", "SOFT"]}
    )
    max_pitstops: Optional[int] = None
    driver_id: Optional[str] = None
    weather_override: Optional[Dict[str, Any]] = None
    custom_pit_loss_override: Optional[float] = None


class PitPlan(BaseModel):
    pit_laps: List[int]
    compounds: List[str]
    predicted_remaining_time: float = Field(..., description="Estimated seconds to finish from current_lap")
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
