# FastAPI Users Integration Guide

This document describes the integration of `fastapi-users` library into the FastAPI Alpine Starter project.

## Overview

The project now uses **fastapi-users** (v13.0.0) for authentication and user management, while maintaining backward compatibility with the existing custom authentication system (magic links and session cookies).

## Architecture

### Dual Authentication System

The application supports two authentication approaches:

1. **FastAPI Users (JWT-based)** - Modern token-based authentication
   - Registration: `/api/auth/register`
   - Login: `/api/auth/login` (cookie transport with JWT)
   - User management: `/api/users/*`

2. **Legacy Magic Link** - Passwordless email-based authentication
   - Magic link request: `POST /auth/login`
   - Magic link verification: `GET /auth/verify/{token}`
   - Used for non-admin users who prefer passwordless flow

3. **Bootstrap Admin** - Password-based login for initial setup
   - Admin login: `POST /admin/login`
   - Only for users with `hashed_password` set
   - Used during initial system setup

## User Model Changes

### New Fields

The `User` model has been extended to support fastapi-users requirements:

```python
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    full_name: str = Field(max_length=200)
    
    # Required by fastapi-users
    hashed_password: str = Field(default="", max_length=255)  # Empty for magic link users
    is_superuser: bool = Field(default=False)  # Maps to ADMIN role
    is_verified: bool = Field(default=False)   # Email verification status
    
    # Custom RBAC
    role: UserRole = Field(default=UserRole.PENDING)
    
    # Backward compatibility
    is_active: bool = Field(default=True)
    email_verified: bool = Field(default=False)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### Field Mapping

- `is_superuser` ↔ `role == UserRole.ADMIN`
- `is_verified` ↔ `email_verified`
- `hashed_password` = empty string for magic link users, hashed password for admin

## Custom SQLModel Adapter

Due to compatibility issues with the official `fastapi-users-db-sqlmodel` package, we created a custom database adapter:

**File**: `app/db_adapter.py`

The custom adapter properly handles async SQLModel operations:

```python
class SQLModelUserDatabase(Generic[UP], BaseUserDatabase[UP, int]):
    async def get(self, id: int) -> Optional[UP]:
        result = await self.session.execute(
            select(self.user_model).where(self.user_model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[UP]:
        result = await self.session.execute(
            select(self.user_model).where(self.user_model.email == email)
        )
        return result.scalar_one_or_none()
    # ... more methods
```

## FastAPI Users Configuration

**File**: `app/users.py`

### Key Components

1. **UserManager** - Handles user lifecycle events
   ```python
   class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
       async def on_after_register(self, user: User, request: Optional[Request] = None):
           # Custom post-registration logic
       
       async def on_after_forgot_password(self, user: User, token: str, ...):
           # Password reset logic
   ```

2. **Authentication Backend** - Cookie-based JWT transport
   ```python
   cookie_transport = CookieTransport(
       cookie_name="session",
       cookie_max_age=settings.SESSION_EXPIRY_DAYS * 24 * 60 * 60,
       cookie_httponly=True,
       cookie_secure=not settings.debug,
       cookie_samesite="lax",
   )
   ```

3. **Custom Dependencies** - Role-based access control
   ```python
   async def require_admin(user: User = Depends(current_active_user)) -> User:
       if user.role != UserRole.ADMIN and not user.is_superuser:
           raise HTTPException(status_code=403, detail="Admin access required")
       return user
   ```

## API Endpoints

### Authentication Endpoints

#### Register a New User
```bash
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "John Doe"
}

# Response:
{
  "id": 1,
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false,
  "full_name": "John Doe",
  "role": "pending",
  "created_at": "2025-11-22T19:36:32.653140"
}
```

#### Login
```bash
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepassword123

# Sets session cookie and returns user data
```

#### Logout
```bash
POST /api/auth/logout

# Clears session cookie
```

#### Request Email Verification
```bash
POST /api/auth/request-verify-token
Content-Type: application/json

{
  "email": "user@example.com"
}
```

#### Verify Email
```bash
POST /api/auth/verify
Content-Type: application/json

{
  "token": "verification_token_here"
}
```

### User Management Endpoints

#### Get Current User
```bash
GET /api/users/me
Cookie: session=<jwt_token>

# Response: User object
```

#### Update Current User
```bash
PATCH /api/users/me
Cookie: session=<jwt_token>
Content-Type: application/json

{
  "full_name": "Jane Doe"
}
```

#### Get User by ID (Admin Only)
```bash
GET /api/users/{user_id}
Cookie: session=<jwt_token>
```

#### Update User (Admin Only)
```bash
PATCH /api/users/{user_id}
Cookie: session=<jwt_token>
Content-Type: application/json

{
  "full_name": "Updated Name",
  "is_active": true
}
```

#### Delete User (Admin Only)
```bash
DELETE /api/users/{user_id}
Cookie: session=<jwt_token>
```

## Database Migration

Migration: `e175b1167df6_add_fastapi_users_fields_to_user_model.py`

### Changes Applied

1. Added `is_superuser` column (Boolean, default False)
2. Added `is_verified` column (Boolean, default False)
3. Synced `is_verified` from existing `email_verified` values
4. Set `is_superuser=True` for users with `role='admin'`

### Running the Migration

```bash
# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

## Integration with Existing Code

### Using Auth Dependencies

Replace old auth dependencies with new ones:

**Before:**
```python
from .auth import require_admin, require_user

@app.get("/admin/dashboard")
async def admin_dashboard(user: User = Depends(require_admin)):
    ...
```

**After:**
```python
from .users import require_admin, current_active_user

@app.get("/admin/dashboard")
async def admin_dashboard(user: User = Depends(require_admin)):
    ...  # Same interface, works identically
```

### Backward Compatibility

The custom magic link authentication system continues to work:

```python
# Legacy routes still functional
@app.post("/auth/login")  # Magic link request
@app.get("/auth/verify/{token}")  # Magic link verification
@app.post("/admin/login")  # Bootstrap admin password login
```

## Best Practices

### 1. Use Appropriate Auth Method

- **API clients**: Use `/api/auth/login` (JWT tokens)
- **Web browsers**: Use legacy magic link or admin login (session cookies)
- **Mobile apps**: Use `/api/auth/login` with cookie or bearer token support

### 2. Role-Based Access Control

Always use the custom dependencies for role checks:

```python
from .users import require_user, require_moderator, require_admin

# Any authenticated user
@app.get("/profile")
async def profile(user: User = Depends(require_user)):
    ...

# Moderator or Admin
@app.post("/moderate")
async def moderate(user: User = Depends(require_moderator)):
    ...

# Admin only
@app.delete("/admin/users/{id}")
async def delete_user(user_id: int, admin: User = Depends(require_admin)):
    ...
```

### 3. Password Requirements

- Minimum 8 characters (enforced by fastapi-users)
- For magic link users: `hashed_password` is empty string
- For password users: hashed with bcrypt via fastapi-users

### 4. Email Verification

Users registered via `/api/auth/register` start with `is_verified=False`. 

To verify:
1. Request token: `POST /api/auth/request-verify-token`
2. User clicks link in email
3. Verify: `POST /api/auth/verify` with token

## Configuration

### Environment Variables

```env
# Authentication
SECRET_KEY=your-secret-key-here
SESSION_EXPIRY_DAYS=7

# Email (for verification)
RESEND_API_KEY=your-resend-api-key
APP_BASE_URL=http://localhost:8000

# Bootstrap Admin
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=secure-admin-password
```

## Testing

### Register and Login Flow

```bash
# 1. Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123456","full_name":"Test User"}'

# 2. Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=test123456" \
  -c cookies.txt

# 3. Access protected endpoint
curl http://localhost:8000/api/users/me -b cookies.txt
```

## Troubleshooting

### Issue: "AttributeError: 'coroutine' object has no attribute 'first'"

**Solution**: Make sure you're using the custom `app/db_adapter.py` instead of the official `fastapi-users-db-sqlmodel` package.

### Issue: Migration fails with "duplicate column"

**Solution**: Drop the database and rerun all migrations from scratch:
```bash
rm dev.db
alembic upgrade head
```

### Issue: User created but `is_superuser` not set for admin

**Solution**: Update the user manually or re-run the migration:
```sql
UPDATE user SET is_superuser = 1 WHERE role = 'admin';
```

## References

- [FastAPI Users Documentation](https://fastapi-users.github.io/fastapi-users/)
- [FastAPI Users GitHub](https://github.com/fastapi-users/fastapi-users)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)

## Future Enhancements

1. **OAuth2 Integration**: Add social login (Google, GitHub, etc.)
2. **Two-Factor Authentication**: Add 2FA support via fastapi-users
3. **Password Reset**: Implement forgot password flow
4. **Refresh Tokens**: Add refresh token support for long-lived sessions
5. **Rate Limiting**: Add login attempt rate limiting
6. **Audit Logging**: Track authentication events
