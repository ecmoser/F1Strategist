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
    """Insert a fitted model record into `fitted_models` table."""
    params_json = json.dumps(parameters)
    prov_json = json.dumps(provenance) if provenance is not None else None

    # Detect dialect
    is_postgres = "postgres" in str(conn.engine.url.drivername).lower()

    if is_postgres:
        sql = text("""
            INSERT INTO fitted_models (circuit_id, season, compound, model_version, model_type, parameters, provenance)
            VALUES (:circuit_id, :season, :compound, :model_version, :model_type, :parameters\\:\\:jsonb, :provenance\\:\\:jsonb)
            RETURNING id, created_at
            """)
    else:
        sql = text("""
            INSERT INTO fitted_models (circuit_id, season, compound, model_version, model_type, parameters, provenance)
            VALUES (:circuit_id, :season, :compound, :model_version, :model_type, :parameters, :provenance)
            RETURNING id, created_at
            """)

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

    # Consume result to avoid open cursors
    try:
        res.fetchone()
    except Exception:
        pass

    return None


def get_circuit_models(conn, circuit_id: str, season: int) -> List[Dict[str, Any]]:
    """Retrieve the latest fitted models for a circuit and season."""
    sql = text("""
        SELECT DISTINCT ON (compound, model_type) compound, model_type, parameters, created_at
        FROM fitted_models
        WHERE circuit_id = :circuit_id AND season = :season
        ORDER BY compound, model_type, created_at DESC
    """)
    # Fallback for SQLite which doesn't support DISTINCT ON
    try:
        res = conn.execute(sql, {"circuit_id": circuit_id, "season": season})
    except Exception:
        sql_fallback = text("""
            SELECT compound, model_type, parameters, created_at
            FROM fitted_models
            WHERE circuit_id = :circuit_id AND season = :season
            ORDER BY created_at DESC
        """)
        res = conn.execute(sql_fallback, {"circuit_id": circuit_id, "season": season})
    
    models = []
    pit_loss = 20.0
    seen_compounds = set()
    
    for row in res:
        data = dict(row._mapping)
        compound_key = (data["compound"], data["model_type"])
        if compound_key in seen_compounds and data["model_type"] != "pit_loss":
            continue
        seen_compounds.add(compound_key)

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
