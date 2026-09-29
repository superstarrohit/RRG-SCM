"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import api_router
from app.config import get_settings
from app.database import init_db

# Present only in the Docker image, where the frontend is pre-built into this
# directory (see the repo-root Dockerfile). Absent in normal dev, where Vite
# serves the frontend itself on :5173 and proxies /api to this server.
FRONTEND_DIR = Path(__file__).resolve().parent / "static"

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

if FRONTEND_DIR.is_dir():
    # Single-container "movable" mode: this server also serves the built
    # React SPA. Routes above (/api/..., /docs, /openapi.json) are matched
    # first since they were registered earlier; anything else falls through
    # to a static asset or, failing that, index.html (client-side routing).
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = FRONTEND_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIR / "index.html")
else:
    @app.get("/")
    def root() -> dict:
        return {"app": settings.app_name, "version": __version__, "docs": "/docs"}
