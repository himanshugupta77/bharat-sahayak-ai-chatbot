"""Basic test to verify chat route is registered and accessible."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_chat_endpoint_exists():
    """Test that the chat endpoint is registered."""
    # Get OpenAPI schema
    response = client.get("/openapi.json")
    assert response.status_code == 200
    
    schema = response.json()
    paths = schema.get("paths", {})
    
    # Check that /chat endpoint exists
    assert "/chat" in paths, "Chat endpoint not found in API schema"
    assert "post" in paths["/chat"], "POST method not found for /chat endpoint"
    
    print("✓ Chat endpoint is registered")


def test_chat_endpoint_validation():
    """Test that the chat endpoint validates request body."""
    # Test with missing body
    response = client.post("/chat")
    assert response.status_code == 422, "Should return 422 for missing body"
    
    print("✓ Chat endpoint validates request body")


def test_chat_endpoint_empty_message():
    """Test that the chat endpoint rejects empty messages."""
    response = client.post(
        "/chat",
        json={"message": "", "language": "en"}
    )
    # Should fail validation (min_length=1)
    assert response.status_code in [400, 422], "Should reject empty message"
    
    print("✓ Chat endpoint rejects empty messages")


if __name__ == "__main__":
    test_chat_endpoint_exists()
    test_chat_endpoint_validation()
    test_chat_endpoint_empty_message()
    print("\n✅ All basic tests passed!")
