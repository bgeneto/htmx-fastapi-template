from typing import Optional

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeSerializer

from .config import settings

COOKIE_NAME = "session"

_serializer = URLSafeSerializer(
    settings.SECRET_KEY.get_secret_value(), salt="session-salt"
)


def create_session_cookie(data: dict) -> str:
    return _serializer.dumps(data)


def load_session_cookie(s: str) -> Optional[dict]:
    try:
        return _serializer.loads(s)
    except BadSignature:
        return None


def require_admin(request: Request):
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = load_session_cookie(cookie)
    if not data or data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return data
