"""The UnderCover backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend import claims, reference, runs
from backend.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)
app.include_router(claims.router)
app.include_router(runs.router)
app.include_router(reference.router)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}
