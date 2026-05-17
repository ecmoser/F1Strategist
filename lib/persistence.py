from typing import Any, Dict, Optional
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

    return res
