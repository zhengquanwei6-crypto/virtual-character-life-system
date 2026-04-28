from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Header

from app.config import get_settings
from app.responses import ApiError


def _b64_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64_decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(payload + padding)


def _signature(message: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return _b64_encode(digest)


def create_admin_token() -> dict[str, Any]:
    settings = get_settings()
    now = int(time.time())
    expires_at = now + settings.admin_token_expire_minutes * 60
    body = _b64_encode(json.dumps({"iat": now, "exp": expires_at}, separators=(",", ":")).encode("utf-8"))
    token = f"{body}.{_signature(body, settings.admin_token_secret)}"
    return {"token": token, "expiresAt": expires_at}


def verify_admin_password(password: str) -> bool:
    configured = get_settings().admin_password
    return hmac.compare_digest(password, configured)


def verify_admin_token(token: str) -> bool:
    settings = get_settings()
    try:
        body, signature = token.split(".", 1)
        expected_signature = _signature(body, settings.admin_token_secret)
        if not hmac.compare_digest(signature, expected_signature):
            return False
        payload = json.loads(_b64_decode(body).decode("utf-8"))
        return int(payload.get("exp", 0)) >= int(time.time())
    except Exception:
        return False


def require_admin_auth(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError("ADMIN_UNAUTHORIZED", "请先登录管理员后台。", 401)
    token = authorization.split(" ", 1)[1].strip()
    if not token or not verify_admin_token(token):
        raise ApiError("ADMIN_UNAUTHORIZED", "管理员登录已过期，请重新登录。", 401)
