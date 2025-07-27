#!/usr/bin/env python3
"""
JWT身份认证和授权系统

提供基于JWT的用户认证、权限控制和会话管理
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from ..config.logging_config import get_logger
from ..config.settings import get_settings
from .audit_logger import SecurityAuditLogger, get_security_audit_logger

logger = get_logger("auth")


class UserRole(Enum):
    """用户角色"""

    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    API_CLIENT = "api_client"


class Permission(Enum):
    """权限类型"""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"


@dataclass
class User:
    """用户信息"""

    user_id: str
    username: str
    email: Optional[str]
    role: UserRole
    permissions: List[Permission]
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None


@dataclass
class TokenPayload:
    """JWT令牌载荷"""

    user_id: str
    username: str
    role: str
    permissions: List[str]
    session_id: str
    issued_at: datetime
    expires_at: datetime


class JWTAuthenticator:
    """JWT认证器"""

    def __init__(self, secret_key: Optional[str] = None):
        self.settings = get_settings()
        self.secret_key = secret_key or getattr(
            self.settings, "JWT_SECRET_KEY", self._generate_secret_key()
        )
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
        self.max_failed_attempts = 5
        self.lockout_duration_minutes = 15

        # 密码哈希上下文
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        # 审计日志记录器
        self.audit_logger = get_security_audit_logger()

        # 用户存储（实际应用中应该使用数据库）
        self.users: Dict[str, User] = {}
        self.user_passwords: Dict[str, str] = {}
        self.active_sessions: Dict[str, TokenPayload] = {}
        self.refresh_tokens: Dict[str, str] = {}  # refresh_token -> user_id

        # 初始化默认用户
        self._initialize_default_users()

    def _generate_secret_key(self) -> str:
        """生成密钥"""
        return secrets.token_urlsafe(32)

    def _initialize_default_users(self):
        """初始化默认用户"""
        # 管理员用户
        admin_user = User(
            user_id="admin",
            username="admin",
            email="admin@testagent.com",
            role=UserRole.ADMIN,
            permissions=[
                Permission.READ,
                Permission.WRITE,
                Permission.EXECUTE,
                Permission.DELETE,
                Permission.ADMIN,
            ],
            created_at=datetime.now(),
        )
        self.users["admin"] = admin_user
        self.user_passwords["admin"] = self.hash_password("admin123")

        # 普通用户
        user = User(
            user_id="user",
            username="user",
            email="user@testagent.com",
            role=UserRole.USER,
            permissions=[Permission.READ, Permission.WRITE, Permission.EXECUTE],
            created_at=datetime.now(),
        )
        self.users["user"] = user
        self.user_passwords["user"] = self.hash_password("user123")

        # 只读用户
        viewer = User(
            user_id="viewer",
            username="viewer",
            email="viewer@testagent.com",
            role=UserRole.VIEWER,
            permissions=[Permission.READ],
            created_at=datetime.now(),
        )
        self.users["viewer"] = viewer
        self.user_passwords["viewer"] = self.hash_password("viewer123")

    def hash_password(self, password: str) -> str:
        """哈希密码"""
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, user: User, session_id: Optional[str] = None) -> str:
        """创建访问令牌"""
        if session_id is None:
            session_id = secrets.token_urlsafe(16)

        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=self.access_token_expire_minutes)

        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "permissions": [p.value for p in user.permissions],
            "session_id": session_id,
            "iat": now,
            "exp": expires_at,
            "type": "access",
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        # 存储会话信息
        token_payload = TokenPayload(
            user_id=user.user_id,
            username=user.username,
            role=user.role.value,
            permissions=[p.value for p in user.permissions],
            session_id=session_id,
            issued_at=now,
            expires_at=expires_at,
        )
        self.active_sessions[session_id] = token_payload

        return token

    def create_refresh_token(self, user: User) -> str:
        """创建刷新令牌"""
        now = datetime.utcnow()
        expires_at = now + timedelta(days=self.refresh_token_expire_days)

        payload = {
            "user_id": user.user_id,
            "iat": now,
            "exp": expires_at,
            "type": "refresh",
        }

        refresh_token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        self.refresh_tokens[refresh_token] = user.user_id

        return refresh_token

    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """验证令牌"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # 检查令牌类型
            if payload.get("type") != "access":
                return None

            # 检查会话是否存在
            session_id = payload.get("session_id")
            if session_id not in self.active_sessions:
                return None

            # 检查用户是否仍然活跃
            user_id = payload.get("user_id")
            if user_id not in self.users or not self.users[user_id].is_active:
                return None

            return self.active_sessions[session_id]

        except jwt.ExpiredSignatureError:
            logger.warning("令牌已过期")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"无效令牌: {e}")
            return None

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """刷新访问令牌"""
        try:
            payload = jwt.decode(
                refresh_token, self.secret_key, algorithms=[self.algorithm]
            )

            # 检查令牌类型
            if payload.get("type") != "refresh":
                return None

            # 检查刷新令牌是否存在
            if refresh_token not in self.refresh_tokens:
                return None

            user_id = self.refresh_tokens[refresh_token]
            if user_id not in self.users:
                return None

            user = self.users[user_id]
            if not user.is_active:
                return None

            # 创建新的访问令牌
            return self.create_access_token(user)

        except jwt.ExpiredSignatureError:
            # 刷新令牌过期，删除记录
            if refresh_token in self.refresh_tokens:
                del self.refresh_tokens[refresh_token]
            return None
        except jwt.InvalidTokenError:
            return None

    def authenticate_user(
        self, username: str, password: str, request: Optional[Request] = None
    ) -> Optional[Dict[str, Any]]:
        """用户认证"""
        source_ip = None
        user_agent = None

        if request:
            source_ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

        # 检查用户是否存在
        if username not in self.users:
            self.audit_logger.log_security_event(
                "authentication_failed",
                "warning",
                f"用户不存在: {username}",
                {"username": username, "reason": "user_not_found"},
                source_ip=source_ip,
                user_agent=user_agent,
                result="failure",
            )
            return None

        user = self.users[username]

        # 检查用户是否被锁定
        if user.locked_until and datetime.now() < user.locked_until:
            self.audit_logger.log_security_event(
                "authentication_blocked",
                "warning",
                f"用户被锁定: {username}",
                {
                    "username": username,
                    "locked_until": user.locked_until.isoformat(),
                    "reason": "account_locked",
                },
                user_id=user.user_id,
                source_ip=source_ip,
                user_agent=user_agent,
                result="blocked",
            )
            return None

        # 检查用户是否活跃
        if not user.is_active:
            self.audit_logger.log_security_event(
                "authentication_blocked",
                "warning",
                f"用户已禁用: {username}",
                {"username": username, "reason": "account_disabled"},
                user_id=user.user_id,
                source_ip=source_ip,
                user_agent=user_agent,
                result="blocked",
            )
            return None

        # 验证密码
        if not self.verify_password(password, self.user_passwords[username]):
            # 增加失败尝试次数
            user.failed_login_attempts += 1

            # 检查是否需要锁定账户
            if user.failed_login_attempts >= self.max_failed_attempts:
                user.locked_until = datetime.now() + timedelta(
                    minutes=self.lockout_duration_minutes
                )

                self.audit_logger.log_security_event(
                    "account_locked",
                    "error",
                    f"账户因多次失败尝试被锁定: {username}",
                    {
                        "username": username,
                        "failed_attempts": user.failed_login_attempts,
                        "locked_until": user.locked_until.isoformat(),
                    },
                    user_id=user.user_id,
                    source_ip=source_ip,
                    user_agent=user_agent,
                    result="blocked",
                )
            else:
                self.audit_logger.log_security_event(
                    "authentication_failed",
                    "warning",
                    f"密码错误: {username}",
                    {
                        "username": username,
                        "failed_attempts": user.failed_login_attempts,
                        "reason": "invalid_password",
                    },
                    user_id=user.user_id,
                    source_ip=source_ip,
                    user_agent=user_agent,
                    result="failure",
                )

            return None

        # 认证成功，重置失败计数
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now()

        # 创建令牌
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)

        self.audit_logger.log_security_event(
            "authentication_success",
            "info",
            f"用户登录成功: {username}",
            {
                "username": username,
                "role": user.role.value,
                "last_login": user.last_login.isoformat(),
            },
            user_id=user.user_id,
            source_ip=source_ip,
            user_agent=user_agent,
            result="success",
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60,
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "permissions": [p.value for p in user.permissions],
            },
        }

    def logout_user(self, session_id: str, user_id: Optional[str] = None):
        """用户登出"""
        if session_id in self.active_sessions:
            token_payload = self.active_sessions[session_id]
            del self.active_sessions[session_id]

            self.audit_logger.log_security_event(
                "logout",
                "info",
                f"用户登出: {token_payload.username}",
                {"session_id": session_id},
                user_id=token_payload.user_id,
                result="success",
            )

    def revoke_refresh_token(self, refresh_token: str):
        """撤销刷新令牌"""
        if refresh_token in self.refresh_tokens:
            user_id = self.refresh_tokens[refresh_token]
            del self.refresh_tokens[refresh_token]

            self.audit_logger.log_security_event(
                "refresh_token_revoked",
                "info",
                "刷新令牌已撤销",
                {
                    "refresh_token_hash": hashlib.sha256(
                        refresh_token.encode()
                    ).hexdigest()[:16]
                },
                user_id=user_id,
                result="success",
            )

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        role: UserRole = UserRole.USER,
    ) -> Optional[User]:
        """创建用户"""
        if username in self.users:
            return None

        # 根据角色分配权限
        permissions = self._get_role_permissions(role)

        user = User(
            user_id=username,  # 简化处理，实际应用中应该生成UUID
            username=username,
            email=email,
            role=role,
            permissions=permissions,
            created_at=datetime.now(),
        )

        self.users[username] = user
        self.user_passwords[username] = self.hash_password(password)

        self.audit_logger.log_security_event(
            "user_created",
            "info",
            f"用户创建: {username}",
            {
                "username": username,
                "role": role.value,
                "permissions": [p.value for p in permissions],
            },
            user_id=user.user_id,
            result="success",
        )

        return user

    def _get_role_permissions(self, role: UserRole) -> List[Permission]:
        """根据角色获取权限"""
        role_permissions = {
            UserRole.ADMIN: [
                Permission.READ,
                Permission.WRITE,
                Permission.EXECUTE,
                Permission.DELETE,
                Permission.ADMIN,
            ],
            UserRole.USER: [Permission.READ, Permission.WRITE, Permission.EXECUTE],
            UserRole.VIEWER: [Permission.READ],
            UserRole.API_CLIENT: [Permission.READ, Permission.WRITE],
        }
        return role_permissions.get(role, [Permission.READ])

    def update_user_password(
        self, username: str, old_password: str, new_password: str
    ) -> bool:
        """更新用户密码"""
        if username not in self.users:
            return False

        if not self.verify_password(old_password, self.user_passwords[username]):
            self.audit_logger.log_security_event(
                "password_change_failed",
                "warning",
                f"密码更改失败: {username}",
                {"username": username, "reason": "invalid_old_password"},
                user_id=self.users[username].user_id,
                result="failure",
            )
            return False

        self.user_passwords[username] = self.hash_password(new_password)

        self.audit_logger.log_security_event(
            "password_changed",
            "info",
            f"密码已更改: {username}",
            {"username": username},
            user_id=self.users[username].user_id,
            result="success",
        )

        return True

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        return self.users.get(user_id)

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """获取活跃会话"""
        sessions = []
        for session_id, token_payload in self.active_sessions.items():
            sessions.append(
                {
                    "session_id": session_id,
                    "user_id": token_payload.user_id,
                    "username": token_payload.username,
                    "role": token_payload.role,
                    "issued_at": token_payload.issued_at.isoformat(),
                    "expires_at": token_payload.expires_at.isoformat(),
                }
            )
        return sessions


class AuthenticationManager:
    """认证管理器"""

    def __init__(self, jwt_authenticator: Optional[JWTAuthenticator] = None):
        self.jwt_auth = jwt_authenticator or JWTAuthenticator()
        self.security = HTTPBearer()

    async def get_current_user(
        self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
    ) -> TokenPayload:
        """获取当前用户"""
        token = credentials.credentials
        token_payload = self.jwt_auth.verify_token(token)

        if not token_payload:
            raise HTTPException(
                status_code=401,
                detail="无效的认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return token_payload

    def require_permission(self, required_permission: Permission):
        """权限检查装饰器"""

        def permission_checker(
            current_user: TokenPayload = Depends(self.get_current_user),
        ) -> TokenPayload:
            if required_permission.value not in current_user.permissions:
                raise HTTPException(
                    status_code=403, detail=f"需要 {required_permission.value} 权限"
                )
            return current_user

        return permission_checker

    def require_role(self, required_role: UserRole):
        """角色检查装饰器"""

        def role_checker(
            current_user: TokenPayload = Depends(self.get_current_user),
        ) -> TokenPayload:
            if current_user.role != required_role.value:
                raise HTTPException(
                    status_code=403, detail=f"需要 {required_role.value} 角色"
                )
            return current_user

        return role_checker


# 全局认证管理器实例
_auth_manager = None
_jwt_authenticator = None


def get_auth_manager() -> AuthenticationManager:
    """获取全局认证管理器"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthenticationManager()
    return _auth_manager


def get_jwt_authenticator() -> JWTAuthenticator:
    """获取全局JWT认证器"""
    global _jwt_authenticator
    if _jwt_authenticator is None:
        _jwt_authenticator = JWTAuthenticator()
    return _jwt_authenticator
