"""
Test health endpoints
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '../apps/api'))

from main import app

client = TestClient(app)

def test_healthz_endpoint():
    """Test /healthz endpoint"""
    response = client.get("/healthz")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ok"

def test_metrics_endpoint():
    """Test /metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"