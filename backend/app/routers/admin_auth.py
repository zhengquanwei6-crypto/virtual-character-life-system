from __future__ import annotations

from fastapi import APIRouter, Depends

from app.responses import ApiError, api_success
from app.schemas import AdminLoginRequest
from app.services.admin_auth_service import create_admin_token, require_admin_auth, verify_admin_password


router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])


@router.post("/login")
def admin_login_api(payload: AdminLoginRequest):
    if not verify_admin_password(payload.password):
        raise ApiError("ADMIN_LOGIN_FAILED", "管理员密码不正确。", 401)
    return api_success(create_admin_token())


@router.get("/me")
def admin_me_api(_: None = Depends(require_admin_auth)):
    return api_success({"authenticated": True})
