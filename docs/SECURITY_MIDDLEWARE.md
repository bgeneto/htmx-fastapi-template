# Security Middleware Configuration

This document explains the security middleware configuration implemented in the FastAPI Alpine Starter application.

## Overview

The application uses several security middleware components to protect against common web vulnerabilities:

1. **TrustedHostMiddleware** - Prevents host header injection attacks
2. **CORSMiddleware** - Controls cross-origin resource sharing
3. **SecurityHeadersMiddleware** - Adds security-related HTTP headers
4. **LocaleMiddleware** - Handles internationalization

Additionally, **GZipMiddleware** has been explicitly disabled as compression is handled by the reverse proxy.

## TrustedHostMiddleware

### Purpose
Validates the `Host` header in incoming requests to prevent host header injection attacks.

### Configuration
- Automatically configured from the `APP_BASE_URL` environment variable
- Extracts the hostname and adds appropriate variations
- Uses Python's `ipaddress` module for proper IP address detection

### Behavior

**For domain names** (e.g., `https://example.com`):
- Allows the exact domain: `example.com`
- Allows wildcard subdomains: `*.example.com`
- Always allows `localhost` and `127.0.0.1` for development

**For IP addresses** (IPv4 or IPv6):
- Allows the exact IP address
- Does NOT add wildcard patterns (IPs cannot have subdomains)
- Always allows `localhost` and `127.0.0.1` for development

**For localhost**:
- Allows `localhost` and `127.0.0.1`
- No wildcard patterns

### Examples

```python
# APP_BASE_URL=https://example.com
# Allowed hosts: ['example.com', '*.example.com', 'localhost', '127.0.0.1']

# APP_BASE_URL=http://192.168.1.100:8000
# Allowed hosts: ['192.168.1.100', 'localhost', '127.0.0.1']

# APP_BASE_URL=http://localhost:8000
# Allowed hosts: ['localhost', '127.0.0.1']
```

## CORSMiddleware

### Purpose
Controls which origins are allowed to make cross-origin requests to the API.

### Configuration
- Configured from the `APP_BASE_URL` environment variable
- Allows credentials (cookies, authorization headers)
- Supports common HTTP methods: GET, POST, PUT, DELETE, OPTIONS

### Behavior

**For production URLs**:
- Allows the exact APP_BASE_URL
- Always includes localhost URLs for development/testing

**For localhost URLs**:
- Only allows the localhost URL

### Examples

```python
# APP_BASE_URL=https://example.com
# Allowed origins: ['https://example.com', 'http://localhost:8000', 'http://127.0.0.1:8000']

# APP_BASE_URL=http://localhost:8000
# Allowed origins: ['http://localhost:8000']
```

## GZipMiddleware (Disabled)

### Why Disabled?
The application is designed to run behind a reverse proxy (Nginx, Caddy, etc.) that handles compression more efficiently than application-level compression.

### When to Enable
If you're deploying the application WITHOUT a reverse proxy, you can uncomment the GZipMiddleware configuration in `app/main.py`:

```python
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

## Proxy Headers Support

### Configuration
The application is configured to trust proxy headers (`--proxy-headers` flag):
- `start.py` - Development server
- `Dockerfile` - Production deployment

### What it Does
Enables Uvicorn to trust and use these headers from the reverse proxy:
- `X-Forwarded-For` - Client's real IP address
- `X-Forwarded-Proto` - Original protocol (http/https)
- `X-Forwarded-Host` - Original host
- `X-Forwarded-Port` - Original port

### Security Note
Only enable `--proxy-headers` when running behind a trusted reverse proxy. If exposed directly to the internet, this could allow attackers to spoof these headers.

## Environment Variables

### Required
- `APP_BASE_URL` - The base URL of your application (e.g., `https://example.com`)

### Example Configuration

**.env for development:**
```bash
APP_BASE_URL=http://localhost:8000
```

**.env for production:**
```bash
APP_BASE_URL=https://yourdomain.com
```

## Testing

Comprehensive tests are located in `tests/test_middleware.py`:

```bash
# Run middleware tests
pytest tests/test_middleware.py -v
```

### Test Coverage
- ✅ Localhost configuration
- ✅ Production domain configuration
- ✅ IPv4 address handling
- ✅ IPv6 address handling
- ✅ No duplicate hosts
- ✅ Middleware imports
- ✅ Proxy headers configuration

## Troubleshooting

### "Invalid host header" error (400)

**Symptom:** Requests return 400 Bad Request

**Causes:**
1. The `Host` header doesn't match allowed hosts
2. `APP_BASE_URL` is not configured correctly
3. Using a custom domain not included in allowed hosts

**Solutions:**
1. Check that `APP_BASE_URL` matches your deployment URL
2. Verify the `Host` header being sent by the client
3. Check logs for details on which host was rejected

### CORS errors in browser

**Symptom:** Browser console shows CORS errors

**Causes:**
1. Frontend origin not in allowed CORS origins
2. Request includes credentials but origin not allowed
3. HTTP method not in allowed methods

**Solutions:**
1. Ensure `APP_BASE_URL` matches your frontend URL
2. For local development, localhost is automatically allowed
3. Check browser console for specific CORS error details

## Security Considerations

1. **Always use HTTPS in production** - Set `APP_BASE_URL` to use `https://`
2. **Proxy headers security** - Only use `--proxy-headers` behind a trusted reverse proxy
3. **CORS configuration** - Review allowed origins before deploying to production
4. **Host header validation** - TrustedHostMiddleware prevents host header injection
5. **Wildcard subdomains** - Use with caution; consider if you need `*.domain.com`

## Related Documentation

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Starlette Middleware](https://www.starlette.io/middleware/)
- [OWASP Host Header Injection](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/17-Testing_for_Host_Header_Injection)
