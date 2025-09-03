"""
Health check endpoints
"""
from fastapi import APIRouter

health_router = APIRouter()

@health_router.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}