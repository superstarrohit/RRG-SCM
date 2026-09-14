"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.config import get_settings
from app.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RRG-SCM API",
    description=(
        "Supply Chain Analytics, Material Planning, Sourcing, Costing & FG "
        "Planning. Ingest daily dumps from Excel/CSV/SQL Server/MySQL/Postgres/"
        "MS Access/ODBC and analyse them."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"app": settings.app_name, "version": __version__, "docs": "/docs"}
