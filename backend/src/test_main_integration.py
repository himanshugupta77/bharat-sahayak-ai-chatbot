"""Integration tests for main FastAPI application."""

import pytest
from fastapi.testclient import TestClient
from main import app

# Create client with raise_server_exceptions=False to test error handling
client = TestClient(app, raise_server_exceptions=False)


def test_app_initialization():
    """Test that the FastAPI app initializes correctly."""
    assert app.title == "Bharat Sahayak API"
    assert app.version == "1.0.0"


def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "bharat-sahayak-api"
    assert data["version"] == "1.0.0"


def test_all_routes_registered():
    """Test that all expected routes are registered."""
    routes = [route.path for route in app.routes]
    
    # Expected routes
    expected_routes = [
        "/health",
        "/chat",
        "/eligibility",
        "/schemes",
        "/schemes/{schemeId}",
        "/session/info",
        "/session",
        "/voice/text-to-speech",
        "/voice/speech-to-text"
    ]
    
    for expected_route in expected_routes:
        assert expected_route in routes, f"Route {expected_route} not found in registered routes"


def test_cors_middleware_configured():
    """Test that CORS middleware is properly configured."""
    # Make a request and check CORS headers
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    # CORS headers should be present
    assert "access-control-allow-origin" in response.headers


def test_chat_route_exists():
    """Test that chat route is accessible."""
    # This will fail validation but confirms route exists
    response = client.post("/chat", json={})
    # Should return 422 (validation error) not 404 (not found)
    assert response.status_code in [400, 422]


def test_eligibility_route_exists():
    """Test that eligibility route is accessible."""
    response = client.post("/eligibility", json={})
    assert response.status_code in [400, 422]


def test_schemes_list_route_exists():
    """Test that schemes list route is accessible."""
    response = client.get("/schemes")
    # Should not return 404 (route exists)
    # May return 500 if environment variables not set, but that's OK for this test
    assert response.status_code != 404


def test_schemes_detail_route_exists():
    """Test that schemes detail route is accessible."""
    response = client.get("/schemes/test-scheme")
    # Should not return 404 for route (route exists)
    # May return 500 if environment variables not set, but that's OK for this test
    assert response.status_code != 404


def test_session_info_route_exists():
    """Test that session info route is accessible."""
    response = client.get("/session/info")
    # Should return 400 (missing header) not 404 (not found)
    assert response.status_code == 400


def test_session_delete_route_exists():
    """Test that session delete route is accessible."""
    response = client.delete("/session")
    # Should return 400 (missing header) not 404 (not found)
    assert response.status_code == 400


def test_voice_tts_route_exists():
    """Test that text-to-speech route is accessible."""
    response = client.post("/voice/text-to-speech", json={})
    assert response.status_code in [400, 422]


def test_voice_stt_route_exists():
    """Test that speech-to-text route is accessible."""
    response = client.post("/voice/speech-to-text", json={})
    assert response.status_code in [400, 422]


def test_error_handling_middleware():
    """Test that error handling middleware catches exceptions."""
    # Try to trigger an error by accessing a non-existent route
    response = client.get("/non-existent-route")
    assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
