"""Tests for custom exception handlers."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_404_html_response(initialized_app):
    """Test that 404 returns custom HTML template for HTML requests."""
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        resp = await client.get("/nonexistent-page", headers={"Accept": "text/html"})
        assert resp.status_code == 404
        assert "text/html" in resp.headers["content-type"]
        # Check that our custom 404 template is used
        assert b"Page Not Found" in resp.content
        assert b"404" in resp.content
        assert b"Go Home" in resp.content


@pytest.mark.asyncio
async def test_404_api_json_response(initialized_app):
    """Test that 404 returns JSON for API requests."""
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        resp = await client.get("/api/nonexistent", headers={"Accept": "application/json"})
        assert resp.status_code == 404
        assert "application/json" in resp.headers["content-type"]
        data = resp.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_403_html_response(client: AsyncClient):
    """Test that 403 returns custom HTML template for HTML requests."""
    # We need to trigger a 403 - we can do this by accessing a protected route
    # For now, we'll simulate it by checking the HTTPException handler logic
    # This would require creating a route that raises HTTPException(403)
    # Since we don't have such a route, we'll test the handler exists
    from fastapi import HTTPException
    from app.main import custom_http_exception_handler, app
    from starlette.requests import Request
    
    # Create a mock request
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "query_string": b"",
        "headers": [],
        "app": app,
    }
    request = Request(scope)
    
    # Test 403 handling
    exc = HTTPException(status_code=403, detail="Forbidden")
    response = await custom_http_exception_handler(request, exc)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_500_handling(client: AsyncClient):
    """Test that 500 errors are handled gracefully."""
    # This tests that the exception handler exists and works
    # In a real scenario, we'd need a route that raises an exception
    from app.main import internal_error_handler, app
    from starlette.requests import Request
    
    # Create a mock request
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "query_string": b"",
        "headers": [],
        "app": app,
    }
    request = Request(scope)
    
    # Test 500 handling
    exc = Exception("Test error")
    response = await internal_error_handler(request, exc)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_general_exception_handler(client: AsyncClient):
    """Test that general exceptions are caught and handled."""
    from app.main import general_exception_handler, app
    from starlette.requests import Request
    
    # Create a mock request
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "query_string": b"",
        "headers": [],
        "app": app,
    }
    request = Request(scope)
    
    # Test general exception handling
    exc = RuntimeError("Unexpected error")
    response = await general_exception_handler(request, exc)
    assert response.status_code == 500
