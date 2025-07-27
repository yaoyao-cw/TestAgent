#!/usr/bin/env python3
"""
API服务器中间件
"""

import time
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..config.logging_config import get_logger

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

    def __init__(self, app, calls_per_minute: int = 60):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.requests = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 获取客户端IP
        client_ip = self._get_client_ip(request)

        # 检查速率限制
        if self._is_rate_limited(client_ip):
            logger.warning(f"速率限制触发: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"error": "请求过于频繁，请稍后再试", "retry_after": 60},
            )

        # 记录请求
        self._record_request(client_ip)

        # 处理请求
        response = await call_next(request)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        # 检查代理头
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 使用客户端IP
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, client_ip: str) -> bool:
        """检查是否超过速率限制"""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        # 清理过期请求
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip] if req_time > minute_ago
        ]

        # 检查请求数量
        return len(self.requests[client_ip]) >= self.calls_per_minute

    def _record_request(self, client_ip: str):
        """记录请求"""
        self.requests[client_ip].append(datetime.now())


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

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 检查是否需要认证
        if self._requires_auth(request.url.path):
            # 验证认证
            if not await self._verify_auth(request):
                return JSONResponse(
                    status_code=401,
                    content={"error": "未授权访问", "message": "请提供有效的认证信息"},
                )

        # 处理请求
        response = await call_next(request)

        return response

    def _requires_auth(self, path: str) -> bool:
        """检查路径是否需要认证"""
        # 公开路径
        public_paths = ["/", "/health", "/docs", "/redoc", "/openapi.json"]

        if path in public_paths:
            return False

        # 检查受保护路径
        return any(path.startswith(protected) for protected in self.protected_paths)

    async def _verify_auth(self, request: Request) -> bool:
        """验证认证信息"""
        # 检查API密钥
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return await self._verify_api_key(api_key)

        # 检查Bearer Token
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:]
            return await self._verify_bearer_token(token)

        return False

    async def _verify_api_key(self, api_key: str) -> bool:
        """验证API密钥"""
        # TODO: 实现API密钥验证逻辑
        # 这里可以从数据库或配置文件中验证API密钥
        valid_keys = ["test-api-key", "demo-key"]  # 示例密钥
        return api_key in valid_keys

    async def _verify_bearer_token(self, token: str) -> bool:
        """验证Bearer Token"""
        # TODO: 实现JWT或其他token验证逻辑
        try:
            # 这里可以解析和验证JWT token
            # 或者从数据库验证session token
            return len(token) > 10  # 简单示例
        except Exception as e:
            logger.error(f"Token验证失败: {e}")
            return False


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
