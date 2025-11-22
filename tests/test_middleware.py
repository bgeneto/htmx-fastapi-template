"""Tests for security middleware configuration."""
import pytest


@pytest.mark.asyncio
async def test_middleware_configuration_functions(monkeypatch):
    """Test that middleware configuration functions work correctly."""
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8000")
    
    # Import after setting environment
    from app.main import get_allowed_hosts, get_cors_origins
    
    # Test localhost configuration
    hosts = get_allowed_hosts()
    assert "localhost" in hosts, "localhost should be in allowed hosts"
    assert "127.0.0.1" in hosts, "127.0.0.1 should be in allowed hosts"
    
    origins = get_cors_origins()
    assert "http://localhost:8000" in origins, "APP_BASE_URL should be in CORS origins"


@pytest.mark.asyncio
async def test_production_middleware_configuration():
    """Test middleware configuration with production URL."""
    from app.main import get_allowed_hosts, get_cors_origins
    import app.main
    
    # Create mock settings for production
    class MockSettings:
        APP_BASE_URL = "https://example.com"
    
    # Temporarily override settings
    original_settings = app.main.settings
    app.main.settings = MockSettings()
    
    try:
        hosts = get_allowed_hosts()
        assert "example.com" in hosts, "Domain should be in allowed hosts"
        assert "*.example.com" in hosts, "Wildcard subdomain should be in allowed hosts"
        assert "localhost" in hosts, "localhost should still be allowed for development"
        assert "127.0.0.1" in hosts, "127.0.0.1 should still be allowed for development"
        
        origins = get_cors_origins()
        assert "https://example.com" in origins, "Production URL should be in CORS origins"
        assert "http://localhost:8000" in origins, "localhost should be in CORS origins for dev"
    finally:
        app.main.settings = original_settings


@pytest.mark.asyncio
async def test_no_duplicate_hosts():
    """Test that get_allowed_hosts doesn't produce duplicates."""
    from app.main import get_allowed_hosts
    
    hosts = get_allowed_hosts()
    # Check for duplicates
    assert len(hosts) == len(set(hosts)), "Allowed hosts should not contain duplicates"


@pytest.mark.asyncio
async def test_middleware_imports():
    """Test that required middleware classes are imported."""
    # Import the module and check for required classes
    from app import main
    
    # Verify the middleware classes are available
    assert hasattr(main, 'TrustedHostMiddleware'), "TrustedHostMiddleware should be imported"
    assert hasattr(main, 'CORSMiddleware'), "CORSMiddleware should be imported"


@pytest.mark.asyncio
async def test_uvicorn_configuration_in_startup_files():
    """Test that uvicorn is configured with proxy headers."""
    import subprocess
    import os
    
    # Get the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Check start.py contains proxy-headers
    start_py = os.path.join(project_root, "start.py")
    if os.path.exists(start_py):
        result = subprocess.run(
            ["grep", "-q", "proxy-headers", start_py],
            capture_output=True
        )
        assert result.returncode == 0, "start.py should configure --proxy-headers"
    
    # Check Dockerfile contains proxy-headers
    dockerfile = os.path.join(project_root, "Dockerfile")
    if os.path.exists(dockerfile):
        result = subprocess.run(
            ["grep", "-q", "proxy-headers", dockerfile],
            capture_output=True
        )
        assert result.returncode == 0, "Dockerfile should configure --proxy-headers"
