# app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints import auth, files, folders, permissions

router = APIRouter()

router.include_router(auth.router)
router.include_router(folders.router, prefix="/drive")
router.include_router(files.router, prefix="/drive")
router.include_router(permissions.router, prefix="/drive")
