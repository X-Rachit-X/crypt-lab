"""
Pytest configuration and fixtures for Cyber Project Template.
"""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_gemini_api_key(monkeypatch):
    """Mock Gemini API key for testing."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-12345")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
