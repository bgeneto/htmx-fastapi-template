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
async def test_production_middleware_configuration(monkeypatch):
    """Test middleware configuration with production URL."""
    from app.main import get_allowed_hosts, get_cors_origins
    import app.main
    
    # Create mock settings for production
    class MockSettings:
        APP_BASE_URL = "https://example.com"
    
    # Use monkeypatch to override settings
    monkeypatch.setattr(app.main, "settings", MockSettings())
    
    hosts = get_allowed_hosts()
    assert "example.com" in hosts, "Domain should be in allowed hosts"
    assert "*.example.com" in hosts, "Wildcard subdomain should be in allowed hosts"
    assert "localhost" in hosts, "localhost should still be allowed for development"
    assert "127.0.0.1" in hosts, "127.0.0.1 should still be allowed for development"
    
    origins = get_cors_origins()
    assert "https://example.com" in origins, "Production URL should be in CORS origins"
    assert "http://localhost:8000" in origins, "localhost should be in CORS origins for dev"


@pytest.mark.asyncio
async def test_ip_address_handling(monkeypatch):
    """Test that IP addresses don't get wildcard subdomains."""
    from app.main import get_allowed_hosts
    import app.main
    
    # Test with IPv4
    class IPv4Settings:
        APP_BASE_URL = "http://192.168.1.1:8000"
    
    monkeypatch.setattr(app.main, "settings", IPv4Settings())
    hosts = get_allowed_hosts()
    
    assert "192.168.1.1" in hosts, "IPv4 should be in allowed hosts"
    assert "*.192.168.1.1" not in hosts, "IPv4 should not have wildcard subdomain"
    
    # Test with IPv6
    class IPv6Settings:
        APP_BASE_URL = "http://[2001:db8::1]:8000"
    
    monkeypatch.setattr(app.main, "settings", IPv6Settings())
    hosts = get_allowed_hosts()
    
    assert "2001:db8::1" in hosts, "IPv6 should be in allowed hosts"
    assert "*.2001:db8::1" not in hosts, "IPv6 should not have wildcard subdomain"


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
    import os
    
    # Get the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Check start.py contains proxy-headers
    start_py = os.path.join(project_root, "start.py")
    if os.path.exists(start_py):
        with open(start_py, "r") as f:
            content = f.read()
            assert "proxy-headers" in content, "start.py should configure --proxy-headers"
    
    # Check Dockerfile contains proxy-headers
    dockerfile = os.path.join(project_root, "Dockerfile")
    if os.path.exists(dockerfile):
        with open(dockerfile, "r") as f:
            content = f.read()
            assert "proxy-headers" in content, "Dockerfile should configure --proxy-headers"
