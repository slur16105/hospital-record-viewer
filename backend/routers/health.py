from fastapi import APIRouter
from core.config import APP_VERSION

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "version": APP_VERSION}
