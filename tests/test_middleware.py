"""Tests for security middleware configuration."""
import pytest


@pytest.mark.asyncio
async def test_middleware_configuration_functions():
    """Test that middleware configuration functions work correctly."""
    import os
    os.environ["APP_BASE_URL"] = "http://localhost:8000"
    
    from app.main import get_allowed_hosts, get_cors_origins
    
    # Test localhost configuration
    hosts = get_allowed_hosts()
    assert "localhost" in hosts, "localhost should be in allowed hosts"
    
    origins = get_cors_origins()
    assert "http://localhost:8000" in origins, "APP_BASE_URL should be in CORS origins"


@pytest.mark.asyncio
async def test_production_middleware_configuration():
    """Test middleware configuration with production URL."""
    import os
    
    # Mock settings for production
    os.environ["APP_BASE_URL"] = "https://example.com"
    
    # Need to reload to pick up new environment
    from importlib import reload
    import app.config
    reload(app.config)
    
    # Create a new app instance with updated settings
    from app.main import get_allowed_hosts, get_cors_origins
    
    # Temporarily override settings for this test
    import app.main
    class MockSettings:
        APP_BASE_URL = "https://example.com"
    
    original_settings = app.main.settings
    app.main.settings = MockSettings()
    
    try:
        hosts = get_allowed_hosts()
        assert "example.com" in hosts, "Domain should be in allowed hosts"
        assert "*.example.com" in hosts, "Wildcard subdomain should be in allowed hosts"
        assert "localhost" in hosts, "localhost should still be allowed for development"
        
        origins = get_cors_origins()
        assert "https://example.com" in origins, "Production URL should be in CORS origins"
        assert "http://localhost:8000" in origins, "localhost should be in CORS origins for dev"
    finally:
        app.main.settings = original_settings


@pytest.mark.asyncio
async def test_middleware_stack_imports():
    """Test that all required middleware are imported."""
    from app import main
    import inspect
    
    source = inspect.getsource(main)
    
    # Verify imports
    assert "TrustedHostMiddleware" in source, "TrustedHostMiddleware should be imported"
    assert "CORSMiddleware" in source, "CORSMiddleware should be imported"
    
    # Verify GZipMiddleware is commented out
    assert "# app.add_middleware(GZipMiddleware" in source or "GZipMiddleware is explicitly disabled" in source, \
        "GZipMiddleware should be disabled/commented"


@pytest.mark.asyncio
async def test_uvicorn_proxy_headers_configuration():
    """Test that proxy-headers flag is set in startup scripts."""
    # Check start.py
    with open("start.py", "r") as f:
        start_content = f.read()
        assert "--proxy-headers" in start_content, "start.py should have --proxy-headers flag"
    
    # Check Dockerfile
    with open("Dockerfile", "r") as f:
        dockerfile_content = f.read()
        assert "--proxy-headers" in dockerfile_content, "Dockerfile should have --proxy-headers flag"
