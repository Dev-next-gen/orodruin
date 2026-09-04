from fastapi import APIRouter

from app.config import settings
from app.llm import available

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def client_config():
    """Runtime config the frontend needs (feature flags + client keys)."""
    return {
        "google_maps_key": settings.google_maps_key or None,
        "google_3d_enabled": bool(settings.google_maps_key),
        "llm_available": available(),
        "public_mode": settings.public_mode,
    }
