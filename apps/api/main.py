"""
Barta API - AI News Assistant
FastAPI application entry point
"""
import sys
import os

# Add project root to Python path for package imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from routes.health import health_router
from routes.metrics import metrics_router
from routes.search import search_router
from routes.chat import chat_router
from core.config import settings

app = FastAPI(
    title="Barta API",
    description="AI News Assistant API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(search_router)
app.include_router(chat_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )