import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, HTTPException, status
from itsdangerous import URLSafeSerializer, BadSignature

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret")
SESSION_EXPIRE_HOURS = int(os.getenv("SESSION_EXPIRE_HOURS", "12"))

serializer = URLSafeSerializer(SESSION_SECRET, salt="admin-session")


def create_admin_session(username: str) -> str:
    payload = {
        "user": username,
        "exp": (datetime.utcnow() + timedelta(hours=SESSION_EXPIRE_HOURS)).isoformat(),
    }
    return serializer.dumps(payload)


def get_admin_user(admin_session: Optional[str] = Cookie(default=None)) -> str:
    if not admin_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        data = serializer.loads(admin_session)
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    exp = datetime.fromisoformat(data.get("exp"))
    if exp < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return data.get("user")
