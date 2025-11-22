# Authentication & Authorization System

This document describes the passwordless magic link authentication system with role-based access control (RBAC) implemented in this FastAPI application.

## Overview

The authentication system features:

- **Passwordless Magic Link Login** - Users receive a secure, time-limited login link via email (except bootstrap admin)
- **User Self-Registration** - Users can register themselves with pending approval status
- **Admin Approval Workflow** - New registrations require admin approval before activation
- **Role-Based Access Control** - Four user roles: Pending, User, Moderator, Admin
- **Bootstrap Admin** - Initial admin account with password-based login for setup
- **Email Integration** - Transactional emails via Resend API
- **Session Management** - Secure, signed cookie-based sessions with expiration
- **i18n Support** - All auth flows fully translated

## User Roles

### Role Hierarchy

```
pending < user < moderator < admin
```

### Role Definitions

| Role          | Description                              | Capabilities                                  |
| ------------- | ---------------------------------------- | --------------------------------------------- |
| **Pending**   | Newly registered users awaiting approval | Cannot log in (except to see pending message) |
| **User**      | Standard authenticated user              | Basic application access                      |
| **Moderator** | Elevated privileges                      | Can perform moderation tasks (extensible)     |
| **Admin**     | Full system access                       | User management, full admin panel access      |

## Authentication Flow

### 1. User Self-Registration

**Endpoint:** `GET /auth/register`

1. User visits registration page
2. Enters email and full name
3. System creates user with `pending` role
4. Admin receives email notification
5. User sees success message informing them approval is needed

**Implementation:**
```python
POST /auth/register
- Validates email and name
- Checks if email already exists
- Creates user with role=PENDING
- Sends notification to first admin
- Returns success message
```

### 2. Magic Link Login

**Endpoints:** `GET /auth/login`, `POST /auth/login`, `GET /auth/verify/{token}`

1. User enters email address
2. System validates user exists and is active
3. Generates secure random token (32 bytes, hashed SHA-256)
4. Stores hashed token in `logintoken` table with expiration
5. Sends email with magic link: `{APP_BASE_URL}/auth/verify/{raw_token}`
6. User clicks link (valid for 15 minutes by default)
7. System validates token, marks as used, creates session
8. Redirects user to appropriate page based on role

**Security Features:**
- Tokens are hashed before storage (SHA-256)
- Short expiration window (configurable via `MAGIC_LINK_EXPIRY_MINUTES`)
- Single-use tokens (marked `used_at` after consumption)
- No email enumeration (always shows "check email" page)

### 3. Bootstrap Admin Login

**Endpoint:** `POST /admin/login`

The bootstrap admin is the only account that can use password-based login. This allows initial system setup before magic link email is configured.

1. Admin enters email and password
2. System verifies user has `hashed_password` field populated
3. System checks role is `ADMIN`
4. Password verified with bcrypt
5. Session created

**Setup:**
1. Configure in `.env`:
   ```env
   BOOTSTRAP_ADMIN_EMAIL=admin@example.com
   BOOTSTRAP_ADMIN_PASSWORD=your-secure-password
   ```
2. Run migration to create admin user:
   ```bash
   alembic upgrade head
   ```

### 4. Session Management

Sessions are stored in signed cookies with the following data:

```python
{
    "user_id": int,
    "email": str,
    "role": str,  # "pending", "user", "moderator", "admin"
    "expires_at": ISO datetime string
}
```

**Session Configuration:**
- Cookie name: `session`
- Signed with `SECRET_KEY` using `itsdangerous.URLSafeSerializer`
- `httponly=True` (not accessible to JavaScript)
- `samesite="lax"` (CSRF protection)
- `secure=True` in production (HTTPS only)
- Default expiry: 30 days (configurable via `SESSION_EXPIRY_DAYS`)

## Admin User Management

**Endpoint:** `GET /admin/users`

Admins can:

### 1. Approve Pending Users

```python
POST /admin/users/{user_id}/approve
- Changes role from PENDING to USER (or specified role)
- Marks email_verified=True
- Sends approval email to user
```

### 2. Create New Users

```python
POST /admin/users/create
- Email, full name, role required
- Optional password (for admin-created accounts)
- User created as active and verified
- No approval needed
```

### 3. Update User Roles & Status

```python
POST /admin/users/{user_id}/update-role
- Change user role (pending/user/moderator/admin)
- Toggle active status (disable accounts)
- Cannot deactivate own account
```

## Email Templates

All emails sent via Resend API (`app/email.py`):

### Magic Link Email

- **Subject:** "Your login link"
- **Expiry:** Shown in email (default: 15 minutes)
- **Content:** Personalized greeting, login button, text link fallback

### Registration Notification (to Admin)

- **Subject:** "New user registration: {name}"
- **Content:** User details, link to admin panel
- **Recipient:** First admin in system

### Account Approved (to User)

- **Subject:** "Your account has been approved"
- **Content:** Welcome message, login instructions
- **Trigger:** Admin approves pending user

## API Endpoints

### Public Endpoints

```
GET  /auth/register        - Registration form
POST /auth/register        - Submit registration
GET  /auth/login           - Magic link request form
POST /auth/login           - Request magic link
GET  /auth/verify/{token}  - Verify and consume magic link
GET  /auth/logout          - Destroy session
```

### Admin Endpoints

```
GET  /admin/login             - Bootstrap admin password login form
POST /admin/login             - Bootstrap admin password login
GET  /admin/users             - User management dashboard
POST /admin/users/create      - Create new user
POST /admin/users/{id}/approve           - Approve pending user
POST /admin/users/{id}/update-role       - Update user role/status
```

### Protected Endpoints (Examples)

```python
# Require any authenticated user
@app.get("/dashboard")
async def dashboard(user: User = Depends(require_user)):
    ...

# Require moderator or admin
@app.get("/moderate")
async def moderate(user: User = Depends(require_moderator)):
    ...

# Require admin only
@app.get("/admin/settings")
async def settings(user: User = Depends(require_admin)):
    ...

# Optional authentication
@app.get("/profile")
async def profile(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    user = await get_current_user(request, session)
    if user:
        # Authenticated flow
    else:
        # Anonymous flow
```

## Database Schema

### User Table

```sql
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    email VARCHAR(320) UNIQUE NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    hashed_password VARCHAR(255),  -- NULL for magic-link-only users
    role ENUM('PENDING', 'USER', 'MODERATOR', 'ADMIN') NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

### LoginToken Table

```sql
CREATE TABLE logintoken (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user(id),
    token_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash
    expires_at DATETIME NOT NULL,
    used_at DATETIME,  -- NULL until consumed
    created_at DATETIME NOT NULL
);

CREATE INDEX idx_token_hash ON logintoken(token_hash);
CREATE INDEX idx_user_id ON logintoken(user_id);
CREATE INDEX idx_expires_at ON logintoken(expires_at);
```

## Configuration

### Required Environment Variables

```env
# Authentication
SESSION_EXPIRY_DAYS=30
MAGIC_LINK_EXPIRY_MINUTES=15
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=strong-password-here

# Resend Email
EMAIL_API_KEY=your-api-key
EMAIL_FROM_ADDRESS=noreply@example.com
EMAIL_FROM_NAME=Your App Name

# Application
APP_BASE_URL=https://yourdomain.com
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
```

### Resend Setup

1. Sign up at https://resend.com
2. Navigate to Settings → API Keys
3. Create a new API key
4. Add to `.env` as `EMAIL_API_KEY`
5. Note: Resend doesn't require sender email verification

## Security Considerations

### Password Storage

- Bootstrap admin password hashed with **bcrypt** (via passlib)
- Cost factor: 12 rounds (default)
- Passwords stored in `hashed_password` column (nullable)

### Token Security

- Magic link tokens: 32-byte random (256-bit)
- Hashed with SHA-256 before database storage
- Short expiration window (default: 15 minutes)
- Single-use enforcement (via `used_at` timestamp)

### Session Security

- Signed cookies prevent tampering
- HttpOnly flag prevents XSS theft
- SameSite=Lax mitigates CSRF
- Secure flag enforced in production (HTTPS)
- Expiration validated on every request

### Attack Mitigations

| Attack Vector     | Mitigation                                                    |
| ----------------- | ------------------------------------------------------------- |
| Email enumeration | Always show "check email" page regardless of user existence   |
| Token brute force | 32-byte random tokens (2^256 space), short expiry, single-use |
| Session hijacking | HttpOnly + Secure cookies, expiration checks                  |
| CSRF              | SameSite cookies, can add CSRF tokens for forms               |
| Password attacks  | Bcrypt with 12 rounds, only for bootstrap admin               |
| Timing attacks    | Constant-time password verification (bcrypt)                  |

## Development Workflow

### Initial Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Run migrations:**
   ```bash
   alembic upgrade head
   ```
   This creates the `user` and `logintoken` tables and seeds the bootstrap admin.

4. **Start server:**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Login as admin:**
   - Visit: `http://localhost:8000/admin/login`
   - Email: (from `BOOTSTRAP_ADMIN_EMAIL`)
   - Password: (from `BOOTSTRAP_ADMIN_PASSWORD`)

### Testing Authentication

1. **Test user registration:**
   ```bash
   curl -X POST http://localhost:8000/auth/register \
     -F "email=user@example.com" \
     -F "full_name=Test User"
   ```

2. **Check admin notifications:**
   - Login to admin panel: `/admin/users`
   - See pending user

3. **Approve user:**
   - Click "Approve" button
   - User receives approval email

4. **Test magic link login:**
   - Visit `/auth/login`
   - Enter approved user email
   - Check email for magic link
   - Click link to log in

## Extending the System

### Adding New Roles

1. Update `UserRole` enum in `app/models.py`:
   ```python
   class UserRole(str, Enum):
       PENDING = "pending"
       USER = "user"
       MODERATOR = "moderator"
       EDITOR = "editor"  # NEW
       ADMIN = "admin"
   ```

2. Create migration:
   ```bash
   alembic revision --autogenerate -m "add editor role"
   alembic upgrade head
   ```

3. Add dependency in `app/auth.py`:
   ```python
   async def require_editor(
       request: Request,
       session: AsyncSession = Depends(repository.get_session)
   ) -> User:
       user = await get_current_user(request, session)
       if not user:
           raise HTTPException(status_code=401)
       if user.role not in [UserRole.EDITOR, UserRole.ADMIN]:
           raise HTTPException(status_code=403)
       return user
   ```

4. Use in routes:
   ```python
   @app.get("/editor/dashboard")
   async def editor_dashboard(user: User = Depends(require_editor)):
       ...
   ```

### Adding Password Reset

Since we use magic links, password reset is only needed for bootstrap admin. For regular password reset:

1. Create `PasswordResetToken` model (similar to `LoginToken`)
2. Add `/auth/forgot-password` endpoint
3. Generate reset token, email link
4. Add `/auth/reset-password/{token}` endpoint
5. Validate token, allow password update

### Adding Social Login

To add OAuth providers (Google, GitHub, etc.):

1. Install: `pip install authlib`
2. Configure OAuth clients in `app/config.py`
3. Add routes: `/auth/login/{provider}`, `/auth/callback/{provider}`
4. Create or link user on successful OAuth
5. Set role based on provider data or default to `pending`

## Internationalization

All authentication strings use i18n:

```python
from .i18n import gettext as _

_("Welcome back!")  # Translated based on user locale
```

**Translation files:**
- `translations/{locale}/LC_MESSAGES/messages.po`
- Extract: `./translate.sh extract`
- Update: `./translate.sh update`
- Compile: `./translate.sh compile`

**Add auth-related translations:**
1. Wrap strings in `_('...')` in Python
2. Use `{{ _('...') }}` in templates
3. Run `./translate.sh refresh`
4. Edit `.po` files for each locale
5. Run `./translate.sh compile`

## Troubleshooting

### Issue: Magic link emails not sending

**Check:**
1. `EMAIL_API_KEY` is set correctly
2. Check logs for Resend API errors
3. Verify API key is valid and has correct permissions

### Issue: Cannot log in as bootstrap admin

**Check:**
1. Migration ran successfully: `alembic current`
2. Admin user exists: `SELECT * FROM user WHERE role='ADMIN';`
3. Password in `.env` matches what you're entering
4. Email is lowercase in database (normalized)

### Issue: Sessions expire immediately

**Check:**
1. `SECRET_KEY` hasn't changed (invalidates all sessions)
2. System clock is accurate (affects expiration checks)
3. `SESSION_EXPIRY_DAYS` is set to reasonable value
4. Cookie `secure` flag matches HTTPS/HTTP context

### Issue: Users not receiving approval emails

**Check:**
1. Admin user exists in database
2. Admin email is correct
3. Resend API key has correct permissions
4. Check spam folder
5. Review logs for email sending errors

## Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Use strong `SECRET_KEY` (generate with: `openssl rand -hex 32`)
- [ ] Change `BOOTSTRAP_ADMIN_PASSWORD` from default
- [ ] Use PostgreSQL instead of SQLite
- [ ] Set `APP_BASE_URL` to production domain (HTTPS)
- [ ] Configure Resend domain and verify email sending
- [ ] Set `SESSION_EXPIRY_DAYS` appropriately (30 default)
- [ ] Set `MAGIC_LINK_EXPIRY_MINUTES` conservatively (15 default)
- [ ] Enable HTTPS (for `secure` cookie flag)
- [ ] Set up log aggregation
- [ ] Configure backup for database
- [ ] Test all email flows in production
- [ ] Rate limit login endpoints (consider `slowapi`)
- [ ] Add monitoring for failed login attempts
- [ ] Set up email alerts for new user registrations

## Related Documentation

- [I18N.md](I18N.md) - Internationalization guide
- [MIGRATIONS.md](MIGRATIONS.md) - Database migration guide
- [TAILWIND_SETUP.md](TAILWIND_SETUP.md) - Tailwind CSS configuration

## License

This authentication system is part of the fastapi-alpine-starter template project.
