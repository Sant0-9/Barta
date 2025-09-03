"""
Prometheus metrics endpoint
"""
from fastapi import APIRouter, Response
from prometheus_client import Counter, generate_latest, REGISTRY

metrics_router = APIRouter()

# Basic counter for demo
request_counter = Counter('barta_requests_total', 'Total requests')

@metrics_router.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    request_counter.inc()  # Increment counter
    return Response(content=generate_latest(), media_type="text/plain")