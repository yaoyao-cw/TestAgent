#!/usr/bin/env python3
"""
认证相关API路由
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr

from ...config.logging_config import get_logger
from ...security.auth import (AuthenticationManager, JWTAuthenticator,
                              Permission, UserRole, get_auth_manager,
                              get_jwt_authenticator)
from ...security.input_validator import get_input_validator
from ...security.rate_limiter import get_rate_limiter

logger = get_logger("auth_routes")

router = APIRouter()
security = HTTPBearer()


# 请求模型
class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None
    role: str = "user"


# 响应模型
class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: Dict[str, Any]


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: Optional[str]
    role: str
    permissions: list
    is_active: bool
    created_at: Optional[datetime]
    last_login: Optional[datetime]


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    jwt_auth: JWTAuthenticator = Depends(get_jwt_authenticator),
):
    """用户登录"""

    # 速率限制检查
    rate_limiter = get_rate_limiter()
    rate_check = await rate_limiter.check_rate_limit(request)

    if not rate_check["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
            headers={"Retry-After": str(rate_check.get("retry_after", 60))},
        )

    # 输入验证
    input_validator = get_input_validator()

    username_result = input_validator.validate_string(
        login_data.username, max_length=50, min_length=3, check_injections=True
    )

    if not username_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名格式无效"
        )

    password_result = input_validator.validate_string(
        login_data.password, max_length=128, min_length=6, check_injections=True
    )

    if not password_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="密码格式无效"
        )

    # 用户认证
    auth_result = jwt_auth.authenticate_user(
        username_result.cleaned_value, login_data.password, request
    )

    if not auth_result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return LoginResponse(**auth_result)


@router.post("/refresh")
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    jwt_auth: JWTAuthenticator = Depends(get_jwt_authenticator),
):
    """刷新访问令牌"""

    # 速率限制检查
    rate_limiter = get_rate_limiter()
    rate_check = await rate_limiter.check_rate_limit(request)

    if not rate_check["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
        )

    # 刷新令牌
    new_access_token = jwt_auth.refresh_access_token(refresh_data.refresh_token)

    if not new_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌"
        )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": jwt_auth.access_token_expire_minutes * 60,
    }


@router.post("/logout")
async def logout(
    auth_manager: AuthenticationManager = Depends(get_auth_manager),
    current_user=Depends(lambda: get_auth_manager().get_current_user),
):
    """用户登出"""

    jwt_auth = get_jwt_authenticator()
    jwt_auth.logout_user(current_user.session_id, current_user.user_id)

    return {"message": "登出成功"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user=Depends(lambda: get_auth_manager().get_current_user),
):
    """获取当前用户信息"""

    jwt_auth = get_jwt_authenticator()
    user = jwt_auth.get_user_by_id(current_user.user_id)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        permissions=[p.value for p in user.permissions],
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.post("/change-password")
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user=Depends(lambda: get_auth_manager().get_current_user),
):
    """修改密码"""

    # 速率限制检查
    rate_limiter = get_rate_limiter()
    rate_check = await rate_limiter.check_rate_limit(request)

    if not rate_check["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
        )

    # 输入验证
    input_validator = get_input_validator()

    old_password_result = input_validator.validate_string(
        password_data.old_password, max_length=128, check_injections=True
    )

    new_password_result = input_validator.validate_string(
        password_data.new_password, max_length=128, min_length=8, check_injections=True
    )

    if not old_password_result.is_valid or not new_password_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="密码格式无效"
        )

    # 更新密码
    jwt_auth = get_jwt_authenticator()
    success = jwt_auth.update_user_password(
        current_user.username, password_data.old_password, password_data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误"
        )

    return {"message": "密码修改成功"}


@router.post("/users", response_model=UserResponse)
async def create_user(
    request: Request,
    user_data: CreateUserRequest,
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """创建用户（需要管理员权限）"""

    # 速率限制检查
    rate_limiter = get_rate_limiter()
    rate_check = await rate_limiter.check_rate_limit(request)

    if not rate_check["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
        )

    # 输入验证
    input_validator = get_input_validator()

    username_result = input_validator.validate_string(
        user_data.username,
        max_length=50,
        min_length=3,
        pattern=r"^[a-zA-Z0-9_]+$",
        check_injections=True,
    )

    password_result = input_validator.validate_string(
        user_data.password, max_length=128, min_length=8, check_injections=True
    )

    if not username_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名格式无效"
        )

    if not password_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="密码格式无效"
        )

    # 验证邮箱
    if user_data.email:
        email_result = input_validator.validate_email(user_data.email)
        if not email_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱格式无效"
            )

    # 验证角色
    try:
        role = UserRole(user_data.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="无效的用户角色"
        )

    # 创建用户
    jwt_auth = get_jwt_authenticator()
    user = jwt_auth.create_user(
        username_result.cleaned_value, user_data.password, user_data.email, role
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在"
        )

    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        permissions=[p.value for p in user.permissions],
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.get("/sessions")
async def get_active_sessions(
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """获取活跃会话（需要管理员权限）"""

    jwt_auth = get_jwt_authenticator()
    sessions = jwt_auth.get_active_sessions()

    return {"sessions": sessions, "total": len(sessions)}


@router.get("/security/statistics")
async def get_security_statistics(
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """获取安全统计信息（需要管理员权限）"""

    from ...security.audit_logger import get_security_audit_logger

    audit_logger = get_security_audit_logger()
    stats = audit_logger.get_security_statistics(hours=24)

    return stats
