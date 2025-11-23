# OTP Authentication Implementation

This document describes the implementation of One-Time Password (OTP) authentication using fastapi-otp-auth library alongside the existing magic link and password authentication methods.

## Overview

The application now supports three authentication methods:
- **OTP (Default)**: 6-digit verification code sent via email
- **Magic Link**: One-time login link sent via email
- **Password**: Traditional username/password (admin bootstrap only)

The authentication method is controlled by the `LOGIN_METHOD` environment variable.

## Architecture

### Configuration

**Environment Variables (.env)**
```bash
# Login method selection (otp, magic, classic)
LOGIN_METHOD=otp

# Redis for OTP storage
REDIS_URL=redis://localhost:6379

# OTP configuration
OTP_EXPIRY_MINUTES=5
```

### Core Components

1. **OTP Configuration** ([`app/otp_config.py`](../app/otp_config.py))
   - Configures fastapi-otp-auth with Redis backend
   - Integrates with existing Resend email service
   - Sets JWT compatibility with fastapi-users

2. **Authentication Strategy** ([`app/auth_strategies.py`](../app/auth_strategies.py))
   - OTP strategy redirects to verification page
   - Magic link strategy maintains existing flow
   - Strategy selection based on `LOGIN_METHOD`

3. **Email Integration** ([`app/email.py`](../app/email.py))
   - `send_otp_email()` function for OTP emails
   - Uses existing Resend configuration
   - Professional HTML email templates

### User Flow

#### OTP Authentication Flow
1. User enters email on `/auth/login`
2. System redirects to `/auth/otp/verify?email=...`
3. OTP code is automatically sent to user's email
4. User enters 6-digit code on verification page
5. Upon successful verification, user is logged in with JWT token
6. User is redirected to original destination or homepage

#### Magic Link Authentication Flow (Legacy)
1. User enters email on `/auth/login`
2. System redirects to `/auth/check_email`
3. Magic link is sent to user's email
4. User clicks link to verify and login

### Template Updates

#### Login Form ([`templates/pages/auth/login.html`](../templates/pages/auth/login.html))
- Dynamic content based on `LOGIN_METHOD`
- Different messaging for OTP vs magic link
- Alpine.js integration for method-specific UI

#### OTP Verification ([`templates/pages/auth/verify_otp.html`](../templates/pages/auth/verify_otp.html))
- 6-digit code input with validation
- Resend code functionality with countdown timer
- Real-time error handling and loading states

#### Check Email Page ([`templates/pages/auth/check_email.html`](../templates/pages/auth/check_email.html))
- Updated to handle both OTP and magic link flows
- Dynamic instructions based on authentication method

### Internationalization

New translations added to [`translations/pt_BR/LC_MESSAGES/messages.po`](../translations/pt_BR/LC_MESSAGES/messages.po):

- Verify Your Email / Verifique seu E-mail
- Send Verification Code / Enviar Código de Verificação
- Verification Code / Código de Verificação
- And many more OTP-related strings

### Docker Integration

**Redis Service** ([`compose.yaml`](../compose.yaml))
```yaml
redis:
  image: redis:7-alpine
  container_name: fastapi-starter-redis
  restart: unless-stopped
  command: redis-server --appendonly yes
  volumes:
    - redis_data:/data
```

## Security Considerations

1. **OTP Expiration**: Codes expire in 5 minutes (configurable)
2. **Rate Limiting**: Built into fastapi-otp-auth (5 attempts per minute)
3. **Secure Storage**: OTP codes stored in Redis with automatic cleanup
4. **JWT Integration**: Uses same secret as fastapi-users for token compatibility

## API Endpoints

### FastAPI-OTP-Auth Routes (mounted at `/auth/otp`)
- `POST /auth/otp/request` - Request OTP code
- `POST /auth/otp/verify` - Verify OTP code and get tokens
- `POST /auth/otp/refresh` - Refresh JWT tokens

### Custom Routes
- `GET /auth/otp/verify` - OTP verification form (UI)
- `POST /auth/login` - Login endpoint with strategy selection

## Configuration Details

### OTP Settings ([`app/otp_config.py`](../app/otp_config.py))
```python
otp_settings = Settings(
    redis_url=settings.REDIS_URL,
    jwt_secret=settings.SECRET_KEY.get_secret_value(),
    jwt_algorithm="HS256",
    access_token_expire_minutes=settings.SESSION_EXPIRY_DAYS * 24 * 60,
    refresh_token_expire_days=settings.SESSION_EXPIRY_DAYS,
    otp_expiry_seconds=settings.OTP_EXPIRY_MINUTES * 60,
)
```

### Environment Variables for fastapi-otp-auth
- `REDIS_URL` - Redis connection string
- `JWT_SECRET` - JWT signing secret (same as fastapi-users)
- `JWT_ALGORITHM` - Token signing algorithm
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token lifetime
- `REFRESH_TOKEN_EXPIRE_DAYS` - Refresh token lifetime
- `OTP_EXPIRY_SECONDS` - OTP code validity period

## Testing the Implementation

### Prerequisites
1. Redis server running (included in Docker Compose)
2. Valid Resend API key configured
3. `LOGIN_METHOD=otp` set in environment

### Testing Flow
1. Start the application: `uvicorn app.main:app --reload`
2. Navigate to `/auth/login`
3. Enter email address
4. Should redirect to OTP verification page
5. Check email for 6-digit code
6. Enter code on verification page
7. Should login successfully and redirect to homepage

## Deployment Notes

### Docker
The Dockerfile automatically installs all dependencies including fastapi-otp-auth. Redis is included in the compose.yaml configuration.

### Production Checklist
- [ ] Redis server is accessible from application
- [ ] `REDIS_URL` environment variable is set
- [ ] `LOGIN_METHOD=otp` is configured
- [ ] Resend API key is valid and configured
- [ ] Proper SSL/TLS termination for secure cookies
- [ ] Monitoring for Redis connectivity

## Migration from Magic Link to OTP

To switch existing installations from magic link to OTP:

1. Update `.env` file: `LOGIN_METHOD=otp`
2. Restart the application
3. Users will now use OTP flow instead of magic links
4. Existing user sessions remain valid until expired

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis server is running
   - Verify `REDIS_URL` configuration
   - Check network connectivity

2. **OTP Email Not Received**
   - Verify Resend API key configuration
   - Check email spam folder
   - Verify `EMAIL_FROM_ADDRESS` is properly configured

3. **OTP Code Invalid**
   - Ensure codes are used within expiration time
   - Check for clock synchronization issues
   - Verify Redis persistence

4. **Login Loop**
   - Check JWT secret consistency between services
   - Verify cookie domain configuration
   - Check for HTTPS/HTTP protocol mismatches

### Debug Commands

```bash
# Check Redis connectivity
redis-cli -u $REDIS_URL ping

# Check OTP settings
python -c "from app.otp_config import otp_settings; print(otp_settings.model_dump())"

# Test email service
python -c "from app.email import send_otp_email; import asyncio; asyncio.run(send_otp_email('test@example.com', 'Test User', '123456'))"
```

## Future Enhancements

1. **TOTP Support**: Time-based one-time passwords for authenticator apps
2. **SMS OTP**: Phone number verification as alternative to email
3. **Backup Codes**: Recovery codes for lost access scenarios
4. **Device Trust**: Remember trusted devices to reduce OTP frequency
5. **Rate Limiting Enhancement**: More granular rate limiting controls