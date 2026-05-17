from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Engine
from datetime import datetime
import uuid
from typing import List

from app.schemas import StrategyRequest, StrategyResponse, PitPlan, CircuitModelEntry
from app.dependencies import get_db
from lib.persistence import get_circuit_models
from lib.optimizer import compute_strategy

router = APIRouter()

@router.post("/", response_model=StrategyResponse)
def post_strategy(request: StrategyRequest, db: Engine = Depends(get_db)):
    # 1. Resolve circuit_id if missing
    circuit_id = request.circuit_id
    if not circuit_id:
        # For now, we require it or we could look it up from a mapping
        raise HTTPException(status_code=400, detail="circuit_id is currently required")

    # 2. Fetch models from DB
    with db.connect() as conn:
        model_data = get_circuit_models(conn, circuit_id, request.season)
    
    if not model_data:
        # Try previous season as fallback
        with db.connect() as conn:
            model_data = get_circuit_models(conn, circuit_id, request.season - 1)
            
    if not model_data:
        raise HTTPException(
            status_code=404, 
            detail=f"No models found for circuit {circuit_id} in season {request.season} or {request.season-1}"
        )

    # 3. Convert to schema objects
    entries = [CircuitModelEntry(**m) for m in model_data]

    # 4. Run optimizer
    try:
        plans = compute_strategy(request, entries)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimizer failed: {str(e)}")

    # 5. Build response
    return StrategyResponse(
        request_id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        plans=plans
    )
