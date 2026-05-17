import os
from fastapi import FastAPI, Depends
from sqlalchemy.engine import Engine
from app.routers import strategy, circuits
from app.dependencies import get_db

app = FastAPI(title="F1Strategist API")

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(strategy.router, prefix="/strategy", tags=["strategy"])
app.include_router(circuits.router, prefix="/circuits", tags=["circuits"])
