"""
backend/app/main.py — FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import router as v1_router

app = FastAPI(
    title="AgentOps Replay API",
    version="1.0.0",
    description="Evidence ingestion and export service for AgentOps Replay.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the canonical TRD §4.3 router (health, ingest, export)
app.include_router(v1_router)
