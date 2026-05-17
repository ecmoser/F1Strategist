from typing import Any, Dict, Optional, List
import os
import json
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str] = None) -> Engine:
    """Return a SQLAlchemy Engine using DATABASE_URL or provided URL."""
    url = db_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set and no db_url provided")
    return create_engine(url)


def save_fitted_model(
    conn,
    circuit_id: str,
    season: int,
    compound: str,
    model_version: str,
    model_type: str,
    parameters: Dict[str, Any],
    provenance: Optional[Dict[str, Any]] = None,
):
    """Insert a fitted model record into `fitted_models` table.

    `conn` can be a SQLAlchemy Connection or Engine; caller is responsible for committing when needed.
    """
    params_json = json.dumps(parameters)
    prov_json = json.dumps(provenance) if provenance is not None else None

    sql = text("""
        INSERT INTO fitted_models (circuit_id, season, compound, model_version, model_type, parameters, provenance)
        VALUES (:circuit_id, :season, :compound, :model_version, :model_type, :parameters::jsonb, :provenance::jsonb)
        RETURNING id, created_at
        """)

    # Some DBs (SQLite) don't support ::jsonb; try without cast if execution fails
    try:
        res = conn.execute(
            sql,
            {
                "circuit_id": circuit_id,
                "season": season,
                "compound": compound,
                "model_version": model_version,
                "model_type": model_type,
                "parameters": params_json,
                "provenance": prov_json,
            },
        )
    except Exception:
        # fallback SQL without PG jsonb cast
        sql2 = text("""
            INSERT INTO fitted_models (circuit_id, season, compound, model_version, model_type, parameters, provenance)
            VALUES (:circuit_id, :season, :compound, :model_version, :model_type, :parameters, :provenance)
            RETURNING id, created_at
            """)
        res = conn.execute(
            sql2,
            {
                "circuit_id": circuit_id,
                "season": season,
                "compound": compound,
                "model_version": model_version,
                "model_type": model_type,
                "parameters": params_json,
                "provenance": prov_json,
            },
        )
    
    # Consume to avoid open cursors in some DBs/drivers
    try:
        res.fetchone()
    except Exception:
        pass

    return None


def get_circuit_models(conn, circuit_id: str, season: int) -> List[Dict[str, Any]]:
    """Retrieve all fitted models for a circuit and season."""
    sql = text("""
        SELECT compound, model_type, parameters
        FROM fitted_models
        WHERE circuit_id = :circuit_id AND season = :season
    """)
    res = conn.execute(sql, {"circuit_id": circuit_id, "season": season})
    
    models = []
    pit_loss = 20.0 # Default
    
    for row in res:
        data = dict(row._mapping)
        if isinstance(data["parameters"], str):
            data["parameters"] = json.loads(data["parameters"])
        
        if data["model_type"] == "pit_loss":
            pit_loss = data["parameters"].get("median", 20.0)
        else:
            models.append(data)
            
    # Attach pit_loss to each model entry for the schema
    for m in models:
        m["pit_loss_seconds"] = pit_loss
        
    return models
