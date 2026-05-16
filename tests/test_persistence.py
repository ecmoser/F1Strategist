import json
from sqlalchemy import create_engine, text

from lib.persistence import save_fitted_model


def test_save_fitted_model_sqlite():
    # use in-memory SQLite for tests
    engine = create_engine("sqlite+pysqlite:///:memory:")
    conn = engine.connect()

    # create a simplified fitted_models table for testing
    conn.execute(
        text(
            """
        CREATE TABLE fitted_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circuit_id TEXT NOT NULL,
            season INTEGER NOT NULL,
            compound TEXT NOT NULL,
            model_version TEXT NOT NULL,
            model_type TEXT NOT NULL,
            parameters TEXT NOT NULL,
            provenance TEXT
        )
        """
        )
    )

    params = {"median": 21.5, "ci_low": 20.0, "ci_high": 23.0}
    prov = {"source": "unit-test"}

    res = save_fitted_model(
        conn,
        circuit_id="testcircuit",
        season=2023,
        compound="M",
        model_version="v1",
        model_type="pit_loss",
        parameters=params,
        provenance=prov,
    )

    # verify row inserted
    r = conn.execute(text("SELECT circuit_id, season, compound, parameters, provenance FROM fitted_models"))
    rows = r.fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row[0] == "testcircuit"
    assert row[1] == 2023
    parsed = json.loads(row[3])
    assert abs(parsed["median"] - 21.5) < 1e-6
