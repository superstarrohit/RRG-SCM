"""API package: assembles all route routers."""
from fastapi import APIRouter

from app.api.routes import analytics, data_workspace, health, ingestion

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ingestion.router)
api_router.include_router(analytics.router)
api_router.include_router(data_workspace.router)

__all__ = ["api_router"]
