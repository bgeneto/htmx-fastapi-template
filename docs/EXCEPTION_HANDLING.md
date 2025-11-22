# Exception Handling

This document describes the custom exception handling implementation in the FastAPI Alpine Starter application.

## Overview

The application implements custom exception handlers using Starlette's `@app.exception_handler()` decorator to provide user-friendly error pages with dark/light theme support and i18n translations.

## Exception Handlers

### HTTPException Handler

Located in `app/main.py`, this handler intercepts all `HTTPException` instances raised by FastAPI.

**Handled Status Codes:**
- **401 Unauthorized** - Redirects to login page (admin or user based on path)
- **403 Forbidden** - Shows custom 403 error page
- **404 Not Found** - Shows custom 404 error page
- **500 Internal Server Error** - Shows custom 500 error page

**API vs HTML Requests:**
The handler automatically detects API requests (paths starting with `/api/`) and returns JSON responses instead of HTML templates.

```python
# Example: API requests get JSON
GET /api/nonexistent
Response: {"detail": "Not found"}

# HTML requests get custom template
GET /nonexistent-page
Response: Custom 404 HTML page
```

### Specific Status Code Handlers

#### 404 Not Found Handler
```python
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors with custom template for HTML requests."""
```

Handles routes that don't exist in the application.

#### 500 Internal Server Error Handler
```python
@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors with custom template for HTML requests."""
```

Handles internal server errors and logs them for debugging.

#### General Exception Handler
```python
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler for unhandled errors."""
```

Catches any unhandled exceptions and displays a 500 error page.

## Error Templates

All error templates are located in `templates/errors/` and extend the base template (`_base.html`).

### Template Structure

Each error page includes:
- **Gradient icon** - Color-coded by error type
- **Error code** - Large, prominent display (404, 403, 500)
- **Error message** - Clear, user-friendly description
- **Action buttons** - Navigation options (Go Home, Go Back, etc.)
- **Helpful links** - Quick access to common pages
- **Theme toggle** - Dark/light mode switcher
- **Language selector** - i18n support (if enabled)

### Template Files

#### 404.html - Page Not Found
- **Color scheme:** Blue/purple gradient
- **Icon:** Sad face
- **Actions:** Go Home, Go Back
- **Links:** Contacts, Books, Login

#### 403.html - Access Denied
- **Color scheme:** Yellow/amber gradient
- **Icon:** Lock
- **Actions:** Go Home, Login
- **Message:** Permission denied notice

#### 500.html - Internal Server Error
- **Color scheme:** Red/orange gradient
- **Icon:** Warning triangle
- **Actions:** Go Home, Try Again
- **Message:** Something went wrong notice

## Internationalization (i18n)

All error pages support multiple languages. Translations are managed through Babel.

### Translatable Strings

Error page strings in Portuguese (pt_BR):
- "Page Not Found" → "Página Não Encontrada"
- "Access Denied" → "Acesso Negado"
- "Internal Server Error" → "Erro Interno do Servidor"
- "Go Home" → "Voltar ao Início"
- "Go Back" → "Voltar"
- "Try Again" → "Tentar Novamente"

### Adding New Translations

1. Extract strings: `bash scripts/translate.sh extract`
2. Update locale: `bash scripts/translate.sh update`
3. Edit `.po` files in `translations/{locale}/LC_MESSAGES/`
4. Compile: `bash scripts/translate.sh compile`

## Theme Support

Error pages automatically respect the user's theme preference (dark/light mode).

### Implementation

The theme toggle is included via `_theme_toggle.html` component:
```html
{% include "components/_theme_toggle.html" %}
```

Theme state is persisted in `localStorage` and applied before page render to prevent flash.

## Testing

Exception handlers are tested in `tests/test_exception_handlers.py`.

### Test Coverage

- ✅ 404 HTML response for non-existent pages
- ✅ 404 JSON response for API requests
- ✅ 403 Forbidden error handling
- ✅ 500 Internal error handling
- ✅ General exception catching

### Running Tests

```bash
pytest tests/test_exception_handlers.py -v
```

## Usage Examples

### Raising Exceptions in Routes

```python
from fastapi import HTTPException

@app.get("/protected")
async def protected_route():
    # Raise 403 Forbidden
    raise HTTPException(status_code=403, detail="Access denied")

@app.get("/resource/{id}")
async def get_resource(id: int):
    # Raise 404 Not Found
    resource = await get_resource_by_id(id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
```

### Testing Error Pages Locally

1. Start the development server:
   ```bash
   uvicorn app.main:app --reload
   ```

2. Test different error codes:
   - 404: Navigate to `http://localhost:8000/nonexistent`
   - 403: Access protected route without auth
   - 500: Trigger an internal error (if test endpoint exists)

## Best Practices

1. **Always use HTTPException** - Don't return raw error responses
2. **Provide meaningful details** - Include helpful error messages
3. **Log errors appropriately** - Use logger for debugging
4. **Test both JSON and HTML** - Ensure API and web requests work
5. **Keep templates consistent** - Follow existing design patterns

## Security Considerations

- **No sensitive information** - Error pages don't expose internal details
- **Logging** - Errors are logged securely for admin review
- **API responses** - Return minimal JSON to prevent information leakage
- **HTML responses** - User-friendly messages without stack traces

## Future Enhancements

Potential improvements:
- Add 429 Rate Limit error page
- Custom 502 Bad Gateway page
- Error tracking integration (Sentry, etc.)
- Animated error illustrations
- Error search/help integration
