import os
from lib.persistence import get_engine

def get_db():
    db_url = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")
    engine = get_engine(db_url)
    try:
        yield engine
    finally:
        pass
