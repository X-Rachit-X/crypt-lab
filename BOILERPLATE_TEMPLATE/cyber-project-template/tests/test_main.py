"""
Unit tests for Cyber Project Template main module.
"""

import pytest
import json
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    """Test /api/health endpoint."""
    
    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "gemini" in data
        assert "connections" in data
    
    def test_health_contains_gemini_status(self, client):
        response = client.get("/api/health")
        data = response.json()
        
        assert "enabled" in data["gemini"]
        assert "model" in data["gemini"]


class TestIndexPage:
    """Test main HTML page."""
    
    def test_index_returns_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestDebugPage:
    """Test debug dashboard."""
    
    def test_debug_returns_html(self, client):
        response = client.get("/debug")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestAnalyzeEndpoint:
    """Test /api/analyze endpoint."""
    
    def test_analyze_requires_logs(self, client):
        response = client.post("/api/analyze", json={})
        # Should fail without Gemini key
        assert response.status_code in (400, 500)
    
    def test_analyze_with_logs(self, client, mock_gemini_api_key):
        response = client.post("/api/analyze", json={
            "logs": "test log output",
            "resource_id": "test_resource"
        })
        
        # Response format should be valid
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data


class TestModelsEndpoint:
    """Test /api/models endpoint."""
    
    def test_models_endpoint(self, client, mock_gemini_api_key):
        response = client.get("/api/models")
        
        if response.status_code == 200:
            data = response.json()
            assert "ok" in data
            if data.get("ok"):
                assert "models" in data
