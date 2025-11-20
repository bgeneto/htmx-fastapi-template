# Authentication System - Quick Start & Testing Guide

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL or SQLite
- Brevo account with API key

### Setup Steps

```bash
# 1. Create Python environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
# Edit .env file with your settings:
# - SECRET_KEY (generate: openssl rand -hex 32)
# - DATABASE_URL
# - BOOTSTRAP_ADMIN_EMAIL
# - BOOTSTRAP_ADMIN_PASSWORD
# - BREVO_API_KEY
# - APP_BASE_URL

# 4. Initialize database
python -m app.create_db
# Or with migrations:
alembic upgrade head

# 5. Build Tailwind CSS
npm install
npm run build:css

# 6. Run application
uvicorn app.main:app --reload
```

### Access Points
- User Registration: http://localhost:8000/auth/register
- User Login: http://localhost:8000/auth/login
- Admin Login: http://localhost:8000/admin/login
- Admin Dashboard: http://localhost:8000/admin

---

## 🧪 Testing Flows

### Test 1: User Self-Registration
**What**: User registers for an account
**Expected**: User created with PENDING role, admin notified

**Steps**:
1. Go to http://localhost:8000/auth/register
2. Enter test email (e.g., user1@example.com)
3. Enter full name
4. Submit form
5. Should see success message
6. Check admin inbox for notification

**Database Check**:
```sql
SELECT id, email, role, is_active, email_verified FROM user WHERE email = 'user1@example.com';
-- Should show: PENDING role, is_active=true, email_verified=false
```

### Test 2: Admin Approval
**What**: Admin approves pending user
**Expected**: User role changes, user receives email

**Steps**:
1. Admin logs in at http://localhost:8000/admin/login
   - Email: admin@sistema.pro.br
   - Password: 12345678 (from .env)
2. Go to /admin/users
3. Find pending user from Test 1
4. Click "Approve"
5. Select role (default: USER)
6. Submit
7. Check user inbox for approval email

**Database Check**:
```sql
SELECT id, email, role, email_verified FROM user WHERE email = 'user1@example.com';
-- Should show: USER role, email_verified=true
```

### Test 3: Magic Link Login
**What**: User logs in without password
**Expected**: Magic link email sent, user can click to login

**Steps**:
1. Go to http://localhost:8000/auth/login
2. Enter approved user email (from Test 2)
3. Submit
4. Should see "Check Your Email" page
5. Check user inbox for magic link email
6. Click "Log In" button in email
7. Should be redirected to home page and logged in

**Verify Login**:
- Cookie should contain session data
- Current user should be accessible

### Test 4: Pending User Cannot Login
**What**: User tries to login before approval
**Expected**: Success message shown, but no email sent (protection)

**Steps**:
1. Register new user (Test 1)
2. DON'T approve yet
3. Go to http://localhost:8000/auth/login
4. Enter the pending user's email
5. Should see "Your account is pending admin approval"
6. Should NOT receive magic link email

### Test 5: Token Expiration
**What**: Test magic link token expires
**Expected**: Expired token shows error

**Steps**:
1. Request magic link for approved user
2. Wait for token to expire (25 minutes by default)
3. Try to use the link
4. Should see error: "Invalid or expired login link"

**In development** (to test quickly):
- Edit `.env`: Set `MAGIC_LINK_EXPIRY_MINUTES=1`
- Restart server
- Request link, wait 1 minute, try to use
- Should fail

### Test 6: Single-Use Token
**What**: Verify token can only be used once
**Expected**: Second use shows error

**Steps**:
1. Request magic link for approved user
2. Click link in email (success login)
3. Check email again
4. Try to click same link again
5. Should see error: "Invalid or expired login link"

### Test 7: Admin Password Login
**What**: Bootstrap admin logs in with password
**Expected**: Admin session created, access to /admin

**Steps**:
1. Go to http://localhost:8000/admin/login
2. Enter email: admin@sistema.pro.br
3. Enter password: 12345678 (from .env)
4. Should redirect to /admin dashboard
5. Should see contact list

### Test 8: Admin Creates User with Password
**What**: Admin creates user with optional password
**Expected**: User created, can login with password

**Steps**:
1. Admin logs in (Test 7)
2. Go to /admin/users
3. Click "Create User"
4. Fill in:
   - Email: newuser@example.com
   - Full Name: New User
   - Role: USER
   - Password: SecurePass123 (optional)
5. Submit
6. User should appear in list
7. User email_verified should be true

**Verify**:
- User NOT in PENDING state (created by admin)
- Can't use magic link (unless explicitly approved first)
- If password provided, can login with it

### Test 9: Logout
**What**: User logs out
**Expected**: Session cookie deleted, redirected to home

**Steps**:
1. Login user (Test 3)
2. Click logout button
3. Should redirect to home page
4. Session cookie should be deleted
5. Accessing admin pages should fail with 401

### Test 10: Role-Based Access Control
**What**: Non-admin cannot access /admin routes
**Expected**: 403 Forbidden error

**Steps**:
1. Create regular user with USER role
2. Login as that user
3. Try to access /admin
4. Should see 403 error or redirect
5. Regular user should not see admin links

---

## 🐛 Debugging Tips

### Check Current User
Add temporary route to see current user:
```python
@app.get("/debug/current-user")
async def debug_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await get_current_user(request, session)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
        } if user else None,
        "cookie": request.cookies.get("session"),
    }
```

### Check Tokens in Database
```sql
-- View all login tokens
SELECT id, user_id, token_hash, expires_at, used_at
FROM logintoken
ORDER BY created_at DESC
LIMIT 10;

-- Check unexpired, unused tokens
SELECT * FROM logintoken
WHERE used_at IS NULL
AND expires_at > datetime('now');
```

### Check User Status
```sql
-- View all users with roles
SELECT id, email, full_name, role, email_verified, is_active
FROM user
ORDER BY created_at DESC;

-- Find pending users
SELECT * FROM user WHERE role = 'PENDING';
```

### Enable Debug Logging
Set in `.env`:
```
DEBUG=true
LOG_FILE=logs/app.log
```

Then check logs:
```bash
tail -f logs/app.log
```

### Test Email Sending
```python
# In Python REPL or test script
from app.email import send_magic_link
import asyncio

async def test():
    result = await send_magic_link(
        "test@example.com",
        "Test User",
        "http://localhost:8000/auth/verify/test-token-here"
    )
    print(f"Email sent: {result}")

asyncio.run(test())
```

---

## 📊 Test Data Setup

### Prepare Test Users
```python
# In Python REPL with app context
from app.repository import create_user
from app.models import UserRole
from sqlmodel import Session
from app.db import AsyncSessionLocal

async def setup_test_data():
    async with AsyncSessionLocal() as session:
        # Create various test users
        users = [
            ("user1@test.com", "Test User 1", UserRole.USER, True),
            ("user2@test.com", "Test User 2", UserRole.USER, True),
            ("pending@test.com", "Pending User", UserRole.PENDING, False),
            ("mod@test.com", "Moderator User", UserRole.MODERATOR, True),
        ]

        for email, name, role, verified in users:
            from app.schemas import UserRegister
            payload = UserRegister(email=email, full_name=name)
            user = await create_user(session, payload, role=role)
            if verified:
                user.email_verified = True
                await session.commit()

# Run it
import asyncio
asyncio.run(setup_test_data())
```

---

## ✅ Production Checklist

Before deploying to production:

- [ ] Change `DEBUG=false` in .env
- [ ] Generate new SECRET_KEY: `openssl rand -hex 32`
- [ ] Set strong BOOTSTRAP_ADMIN_PASSWORD
- [ ] Configure production DATABASE_URL (PostgreSQL)
- [ ] Get real Brevo API key
- [ ] Set APP_BASE_URL to production domain
- [ ] Set `SECURE=true` in cookie settings (for HTTPS)
- [ ] Review email templates for branding
- [ ] Test all authentication flows in staging
- [ ] Setup log file rotation
- [ ] Configure HTTPS/SSL certificate
- [ ] Setup email bounce handling
- [ ] Configure rate limiting on auth endpoints
- [ ] Setup monitoring and alerting
- [ ] Run database migrations: `alembic upgrade head`
- [ ] Setup backup strategy for database
- [ ] Test disaster recovery procedures

---

## 🔗 Reference Links

- **FastAPI Docs**: https://fastapi.tiangolo.com
- **SQLModel Docs**: https://sqlmodel.tiangolo.com
- **Passlib Docs**: https://passlib.readthedocs.io
- **Brevo API**: https://developers.brevo.com
- **Pydantic Docs**: https://docs.pydantic.dev
- **Jinja2 Docs**: https://jinja.palletsprojects.com

---

## 📝 Notes

- Default session expiry: 30 days
- Default magic link expiry: 15 minutes
- Tokens are single-use (marked after verification)
- Passwords optional for admin-created users
- All user-visible strings support i18n translation
- Email sending is async (non-blocking)
- Session cookies are HttpOnly and signed

---

**Last Updated**: November 19, 2025
**Version**: 1.0 (Post-Verification Fix)
