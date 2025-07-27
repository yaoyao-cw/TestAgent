#!/usr/bin/env python3
"""
API服务器中间件
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..config.logging_config import get_logger
from ..security.audit_logger import get_security_audit_logger
from ..security.auth import get_jwt_authenticator
from ..security.data_encryption import get_sensitive_data_masker
from ..security.input_validator import get_input_validator
from ..security.rate_limiter import get_rate_limiter

logger = get_logger("api_middleware")


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        start_time = time.time()

        # 记录请求信息
        logger.info(f"请求开始: {request.method} {request.url}")

        # 处理请求
        response = await call_next(request)

        # 计算处理时间
        process_time = time.time() - start_time

        # 记录响应信息
        logger.info(
            f"请求完成: {request.method} {request.url} "
            f"状态码: {response.status_code} "
            f"处理时间: {process_time:.3f}s"
        )

        # 添加处理时间头
        response.headers["X-Process-Time"] = str(process_time)

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""

    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = get_rate_limiter()

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 获取用户信息（如果已认证）
        user_id = None
        user_role = None

        try:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
                jwt_auth = get_jwt_authenticator()
                token_payload = jwt_auth.verify_token(token)
                if token_payload:
                    user_id = token_payload.user_id
                    user_role = token_payload.role
        except Exception:
            pass  # 忽略认证错误，继续进行速率限制检查

        # 检查速率限制
        rate_check = await self.rate_limiter.check_rate_limit(
            request, user_id, user_role
        )

        if not rate_check["allowed"]:
            logger.warning(
                f"速率限制触发: {request.client.host if request.client else 'unknown'}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "请求过于频繁，请稍后再试",
                    "reason": rate_check["reason"],
                    "retry_after": rate_check.get("retry_after", 60),
                },
                headers={"Retry-After": str(rate_check.get("retry_after", 60))},
            )

        # 处理请求
        response = await call_next(request)

        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件"""

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 添加安全头
        response = await call_next(request)

        # 安全响应头
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
        }

        for header, value in security_headers.items():
            response.headers[header] = value

        return response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """认证中间件"""

    def __init__(self, app, protected_paths: list = None):
        super().__init__(app)
        self.protected_paths = protected_paths or ["/api/v1/"]
        self.jwt_auth = get_jwt_authenticator()
        self.audit_logger = get_security_audit_logger()

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent")

        # 检查是否需要认证
        if self._requires_auth(request.url.path):
            # 验证认证
            auth_result = await self._verify_auth(request)
            if not auth_result["valid"]:
                self.audit_logger.log_security_event(
                    "authentication_failed",
                    "warning",
                    f"认证失败: {auth_result['reason']}",
                    {
                        "path": request.url.path,
                        "reason": auth_result["reason"],
                        "client_ip": client_ip,
                    },
                    source_ip=client_ip,
                    user_agent=user_agent,
                    result="failure",
                )

                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "未授权访问",
                        "message": "请提供有效的认证信息",
                        "reason": auth_result["reason"],
                    },
                )

            # 将用户信息添加到请求状态
            request.state.user = auth_result.get("user")

        # 处理请求
        response = await call_next(request)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _requires_auth(self, path: str) -> bool:
        """检查路径是否需要认证"""
        # 公开路径
        public_paths = [
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
        ]

        if path in public_paths:
            return False

        # 检查受保护路径
        return any(path.startswith(protected) for protected in self.protected_paths)

    async def _verify_auth(self, request: Request) -> Dict[str, Any]:
        """验证认证信息"""
        # 检查API密钥
        api_key = request.headers.get("X-API-Key")
        if api_key:
            if await self._verify_api_key(api_key):
                return {"valid": True, "method": "api_key"}
            else:
                return {"valid": False, "reason": "invalid_api_key"}

        # 检查Bearer Token
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:]
            token_payload = self.jwt_auth.verify_token(token)
            if token_payload:
                return {"valid": True, "method": "bearer_token", "user": token_payload}
            else:
                return {"valid": False, "reason": "invalid_bearer_token"}

        return {"valid": False, "reason": "no_credentials"}

    async def _verify_api_key(self, api_key: str) -> bool:
        """验证API密钥"""
        # 简单的API密钥验证（实际应用中应该从数据库或配置中获取）
        valid_keys = ["test-api-key", "demo-key"]
        return api_key in valid_keys


class CacheMiddleware(BaseHTTPMiddleware):
    """缓存中间件"""

    def __init__(self, app, cache_ttl: int = 300):
        super().__init__(app)
        self.cache_ttl = cache_ttl
        self.cache: Dict[str, Dict[str, Any]] = {}

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 只缓存GET请求
        if request.method != "GET":
            return await call_next(request)

        # 生成缓存键
        cache_key = self._generate_cache_key(request)

        # 检查缓存
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            logger.debug(f"缓存命中: {cache_key}")
            return JSONResponse(
                content=cached_response["content"],
                status_code=cached_response["status_code"],
                headers={"X-Cache": "HIT"},
            )

        # 处理请求
        response = await call_next(request)

        # 缓存响应（只缓存成功响应）
        if response.status_code == 200:
            await self._cache_response(cache_key, response)

        return response

    def _generate_cache_key(self, request: Request) -> str:
        """生成缓存键"""
        return f"{request.method}:{request.url}"

    def _get_cached_response(self, cache_key: str) -> Dict[str, Any]:
        """获取缓存响应"""
        if cache_key not in self.cache:
            return None

        cached_item = self.cache[cache_key]

        # 检查是否过期
        if datetime.now() > cached_item["expires_at"]:
            del self.cache[cache_key]
            return None

        return cached_item

    async def _cache_response(self, cache_key: str, response: Response):
        """缓存响应"""
        try:
            # 读取响应内容
            content = b""
            async for chunk in response.body_iterator:
                content += chunk

            # 缓存响应
            self.cache[cache_key] = {
                "content": content.decode(),
                "status_code": response.status_code,
                "expires_at": datetime.now() + timedelta(seconds=self.cache_ttl),
            }

            logger.debug(f"响应已缓存: {cache_key}")

        except Exception as e:
            logger.error(f"缓存响应失败: {e}")


class InputValidationMiddleware(BaseHTTPMiddleware):
    """输入验证中间件"""

    def __init__(self, app):
        super().__init__(app)
        self.input_validator = get_input_validator()
        self.audit_logger = get_security_audit_logger()
        self.masker = get_sensitive_data_masker()

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        client_ip = self._get_client_ip(request)

        # 验证请求头
        validation_issues = []

        # 验证User-Agent
        user_agent = request.headers.get("user-agent", "")
        if user_agent:
            ua_result = self.input_validator.validate_string(
                user_agent, max_length=512, check_injections=True
            )
            if not ua_result.is_valid:
                validation_issues.extend(ua_result.issues)

        # 验证查询参数
        for key, value in request.query_params.items():
            param_result = self.input_validator.validate_string(
                str(value), max_length=1024, check_injections=True
            )
            if not param_result.is_valid:
                validation_issues.extend(
                    [
                        {**issue, "location": f"query_param_{key}"}
                        for issue in param_result.issues
                    ]
                )

        # 如果有严重的验证问题，阻止请求
        critical_issues = [
            issue for issue in validation_issues if issue.get("severity") == "critical"
        ]

        if critical_issues:
            self.audit_logger.log_security_event(
                "input_validation_blocked",
                "critical",
                "输入验证失败，请求被阻止",
                {
                    "path": str(request.url),
                    "client_ip": client_ip,
                    "issues": critical_issues,
                },
                source_ip=client_ip,
                user_agent=user_agent,
                result="blocked",
            )

            return JSONResponse(
                status_code=400,
                content={
                    "error": "输入验证失败",
                    "message": "请求包含潜在的安全威胁",
                    "issues": len(critical_issues),
                },
            )

        # 处理请求
        response = await call_next(request)

        # 脱敏响应中的敏感信息（仅在开发模式下）
        if hasattr(response, "body") and response.status_code >= 400:
            try:
                # 对错误响应进行脱敏
                pass  # 实际实现中可以对响应内容进行脱敏
            except Exception:
                pass

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


class CompressionMiddleware(BaseHTTPMiddleware):
    """压缩中间件"""

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        response = await call_next(request)

        # 检查是否支持压缩
        accept_encoding = request.headers.get("Accept-Encoding", "")

        if "gzip" in accept_encoding:
            # TODO: 实现gzip压缩
            response.headers["Content-Encoding"] = "gzip"

        return response
