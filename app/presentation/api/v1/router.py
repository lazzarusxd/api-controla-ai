from fastapi import APIRouter

from app.presentation.api.v1.health.router import router as health_router
from app.presentation.api.v1.authentication.router import router as authentication_router


router = APIRouter()

router.include_router(health_router)

router.include_router(authentication_router, prefix="/v1")
