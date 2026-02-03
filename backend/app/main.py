from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import router as api_router

app = FastAPI(title="AgentOps Replay API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check route
@app.get("/health")
def health_check():
    return {"status": "ok"}


# Include v1 routers
app.include_router(api_router, prefix="/api/v1")
