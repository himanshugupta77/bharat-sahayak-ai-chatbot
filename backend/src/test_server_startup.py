"""Test to verify server startup configuration."""

import pytest
from main import app
import uvicorn


def test_uvicorn_config_in_main():
    """Test that main.py has correct uvicorn configuration."""
    # Read the main.py file to verify uvicorn configuration
    import os
    main_path = os.path.join(os.path.dirname(__file__), "main.py")
    with open(main_path, "r") as f:
        content = f.read()
    
    # Verify uvicorn configuration
    assert 'host="0.0.0.0"' in content
    assert 'port=8000' in content
    assert 'uvicorn.run' in content


def test_lifespan_configured():
    """Test that lifespan is configured for startup/shutdown."""
    # Verify app has lifespan configured
    assert app.router.lifespan_context is not None


def test_startup_logging_message():
    """Test that startup logging includes host and port."""
    import os
    main_path = os.path.join(os.path.dirname(__file__), "main.py")
    with open(main_path, "r") as f:
        content = f.read()
    
    # Verify startup logging message
    assert "Server listening on host 0.0.0.0, port 8000" in content


def test_all_routers_included():
    """Test that all route modules are imported and registered."""
    import os
    main_path = os.path.join(os.path.dirname(__file__), "main.py")
    with open(main_path, "r") as f:
        content = f.read()
    
    # Verify imports
    assert "from routes.chat import router as chat_router" in content
    assert "from routes.eligibility import router as eligibility_router" in content
    assert "from routes.schemes import router as schemes_router" in content
    assert "from routes.session import router as session_router" in content
    assert "from routes.voice import router as voice_router" in content
    
    # Verify registrations
    assert "app.include_router(chat_router" in content
    assert "app.include_router(eligibility_router" in content
    assert "app.include_router(schemes_router" in content
    assert "app.include_router(session_router" in content
    assert "app.include_router(voice_router" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
