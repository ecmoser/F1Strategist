from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Engine
from typing import List

from app.schemas import CircuitModel, CircuitModelEntry
from app.dependencies import get_db
from lib.persistence import get_circuit_models

router = APIRouter()

@router.get("/{circuit_id}", response_model=CircuitModel)
def get_circuit(circuit_id: str, season: int = 2024, db: Engine = Depends(get_db)):
    with db.connect() as conn:
        model_data = get_circuit_models(conn, circuit_id, season)
    
    if not model_data:
        raise HTTPException(
            status_code=404, 
            detail=f"No models found for circuit {circuit_id} in season {season}"
        )

    entries = [CircuitModelEntry(**m) for m in model_data]
    
    return CircuitModel(
        circuit_id=circuit_id,
        season=season,
        models=entries
    )
