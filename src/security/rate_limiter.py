#!/usr/bin/env python3
"""
API请求频率限制器

实现基于令牌桶算法的请求频率限制，支持不同用户和端点的差异化限制
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request

from ..config.logging_config import get_logger
from .audit_logger import SecurityAuditLogger, get_security_audit_logger

logger = get_logger("rate_limiter")


class LimitType(Enum):
    """限制类型"""

    PER_SECOND = "per_second"
    PER_MINUTE = "per_minute"
    PER_HOUR = "per_hour"
    PER_DAY = "per_day"


@dataclass
class RateLimit:
    """速率限制配置"""

    requests: int  # 允许的请求数
    window: int  # 时间窗口（秒）
    burst: int = 0  # 突发请求数（令牌桶容量）


@dataclass
class TokenBucket:
    """令牌桶"""

    capacity: int  # 桶容量
    tokens: float  # 当前令牌数
    refill_rate: float  # 令牌补充速率（每秒）
    last_refill: float = field(default_factory=time.time)


@dataclass
class RequestRecord:
    """请求记录"""

    timestamp: datetime
    endpoint: str
    user_id: Optional[str]
    source_ip: str
    user_agent: Optional[str]
    status: str  # allowed, denied, throttled


class RateLimiter:
    """速率限制器"""

    def __init__(self):
        self.audit_logger = get_security_audit_logger()

        # 令牌桶存储 {key: TokenBucket}
        self.token_buckets: Dict[str, TokenBucket] = {}

        # 请求记录
        self.request_history: List[RequestRecord] = []
        self.max_history_size = 10000

        # 默认限制配置
        self.default_limits = {
            "global": RateLimit(
                requests=100, window=60, burst=20
            ),  # 全局限制：每分钟100请求
            "per_ip": RateLimit(
                requests=60, window=60, burst=10
            ),  # IP限制：每分钟60请求
            "per_user": RateLimit(
                requests=120, window=60, burst=30
            ),  # 用户限制：每分钟120请求
        }

        # 端点特定限制
        self.endpoint_limits = {
            "/api/v1/tasks": RateLimit(requests=30, window=60, burst=5),
            "/api/v1/documents/upload": RateLimit(requests=10, window=60, burst=2),
            "/api/v1/system/execute": RateLimit(requests=20, window=60, burst=3),
        }

        # 用户角色限制
        self.role_limits = {
            "admin": RateLimit(requests=200, window=60, burst=50),
            "user": RateLimit(requests=120, window=60, burst=30),
            "viewer": RateLimit(requests=60, window=60, burst=10),
            "api_client": RateLimit(requests=300, window=60, burst=100),
        }

        # 黑名单和白名单
        self.blacklisted_ips: set = set()
        self.whitelisted_ips: set = {"127.0.0.1", "::1"}  # 本地IP默认白名单

        # 动态限制调整
        self.adaptive_limits: Dict[str, RateLimit] = {}

        # 清理任务
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """启动清理任务"""

        async def cleanup_loop():
            while True:
                await asyncio.sleep(300)  # 每5分钟清理一次
                self._cleanup_old_records()
                self._cleanup_empty_buckets()

        asyncio.create_task(cleanup_loop())

    def _cleanup_old_records(self):
        """清理旧的请求记录"""
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.request_history = [
            record for record in self.request_history if record.timestamp > cutoff_time
        ]

        # 保持历史记录在合理范围内
        if len(self.request_history) > self.max_history_size:
            self.request_history = self.request_history[-self.max_history_size // 2 :]

    def _cleanup_empty_buckets(self):
        """清理空的令牌桶"""
        current_time = time.time()
        keys_to_remove = []

        for key, bucket in self.token_buckets.items():
            # 如果令牌桶长时间未使用，删除它
            if current_time - bucket.last_refill > 3600:  # 1小时
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.token_buckets[key]

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

    def _get_token_bucket(self, key: str, rate_limit: RateLimit) -> TokenBucket:
        """获取或创建令牌桶"""
        if key not in self.token_buckets:
            # 计算令牌补充速率
            refill_rate = rate_limit.requests / rate_limit.window
            capacity = rate_limit.burst if rate_limit.burst > 0 else rate_limit.requests

            self.token_buckets[key] = TokenBucket(
                capacity=capacity,
                tokens=capacity,  # 初始时桶是满的
                refill_rate=refill_rate,
            )

        return self.token_buckets[key]

    def _refill_bucket(self, bucket: TokenBucket):
        """补充令牌桶"""
        current_time = time.time()
        time_passed = current_time - bucket.last_refill

        # 计算应该添加的令牌数
        tokens_to_add = time_passed * bucket.refill_rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + tokens_to_add)
        bucket.last_refill = current_time

    def _consume_token(self, bucket: TokenBucket) -> bool:
        """消费令牌"""
        self._refill_bucket(bucket)

        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return True
        return False

    def _get_applicable_limits(
        self,
        request: Request,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
    ) -> List[Tuple[str, RateLimit]]:
        """获取适用的限制"""
        limits = []

        client_ip = self._get_client_ip(request)
        endpoint = request.url.path

        # 全局限制
        limits.append(("global", self.default_limits["global"]))

        # IP限制
        limits.append((f"ip:{client_ip}", self.default_limits["per_ip"]))

        # 用户限制
        if user_id:
            user_limit = self.default_limits["per_user"]
            if user_role and user_role in self.role_limits:
                user_limit = self.role_limits[user_role]
            limits.append((f"user:{user_id}", user_limit))

        # 端点限制
        if endpoint in self.endpoint_limits:
            limits.append((f"endpoint:{endpoint}", self.endpoint_limits[endpoint]))

        # 动态限制
        for key, limit in self.adaptive_limits.items():
            if key.startswith(f"ip:{client_ip}") or key.startswith(f"user:{user_id}"):
                limits.append((key, limit))

        return limits

    async def check_rate_limit(
        self,
        request: Request,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """检查速率限制"""
        client_ip = self._get_client_ip(request)
        endpoint = request.url.path
        user_agent = request.headers.get("user-agent")

        # 检查黑名单
        if client_ip in self.blacklisted_ips:
            self._record_request(endpoint, user_id, client_ip, user_agent, "blocked")

            self.audit_logger.log_security_event(
                "rate_limit_blocked",
                "warning",
                f"黑名单IP被阻止: {client_ip}",
                {
                    "client_ip": client_ip,
                    "endpoint": endpoint,
                    "reason": "blacklisted_ip",
                },
                user_id=user_id,
                source_ip=client_ip,
                user_agent=user_agent,
                result="blocked",
            )

            return {
                "allowed": False,
                "reason": "blacklisted_ip",
                "retry_after": None,
                "limits": {},
            }

        # 检查白名单
        if client_ip in self.whitelisted_ips:
            self._record_request(endpoint, user_id, client_ip, user_agent, "allowed")
            return {
                "allowed": True,
                "reason": "whitelisted_ip",
                "retry_after": None,
                "limits": {},
            }

        # 获取适用的限制
        applicable_limits = self._get_applicable_limits(request, user_id, user_role)

        # 检查每个限制
        limit_results = {}
        overall_allowed = True
        min_retry_after = None

        for limit_key, rate_limit in applicable_limits:
            bucket = self._get_token_bucket(limit_key, rate_limit)
            allowed = self._consume_token(bucket)

            limit_results[limit_key] = {
                "allowed": allowed,
                "remaining": int(bucket.tokens),
                "capacity": bucket.capacity,
                "refill_rate": bucket.refill_rate,
                "retry_after": int(1 / bucket.refill_rate) if not allowed else None,
            }

            if not allowed:
                overall_allowed = False
                retry_after = int(1 / bucket.refill_rate)
                if min_retry_after is None or retry_after < min_retry_after:
                    min_retry_after = retry_after

        # 记录请求
        status = "allowed" if overall_allowed else "denied"
        self._record_request(endpoint, user_id, client_ip, user_agent, status)

        # 记录审计日志
        if not overall_allowed:
            self.audit_logger.log_security_event(
                "rate_limit_exceeded",
                "warning",
                f"速率限制超出: {client_ip}",
                {
                    "client_ip": client_ip,
                    "endpoint": endpoint,
                    "user_id": user_id,
                    "limits": limit_results,
                    "retry_after": min_retry_after,
                },
                user_id=user_id,
                source_ip=client_ip,
                user_agent=user_agent,
                result="denied",
            )

        return {
            "allowed": overall_allowed,
            "reason": "rate_limit_exceeded" if not overall_allowed else "allowed",
            "retry_after": min_retry_after,
            "limits": limit_results,
        }

    def _record_request(
        self,
        endpoint: str,
        user_id: Optional[str],
        source_ip: str,
        user_agent: Optional[str],
        status: str,
    ):
        """记录请求"""
        record = RequestRecord(
            timestamp=datetime.now(),
            endpoint=endpoint,
            user_id=user_id,
            source_ip=source_ip,
            user_agent=user_agent,
            status=status,
        )

        self.request_history.append(record)

    def add_to_blacklist(self, ip: str, reason: str = "manual"):
        """添加IP到黑名单"""
        self.blacklisted_ips.add(ip)

        self.audit_logger.log_security_event(
            "ip_blacklisted",
            "warning",
            f"IP添加到黑名单: {ip}",
            {"ip": ip, "reason": reason},
            result="success",
        )

        logger.warning(f"IP {ip} 已添加到黑名单，原因: {reason}")

    def remove_from_blacklist(self, ip: str):
        """从黑名单移除IP"""
        if ip in self.blacklisted_ips:
            self.blacklisted_ips.remove(ip)

            self.audit_logger.log_security_event(
                "ip_unblacklisted",
                "info",
                f"IP从黑名单移除: {ip}",
                {"ip": ip},
                result="success",
            )

            logger.info(f"IP {ip} 已从黑名单移除")

    def add_to_whitelist(self, ip: str):
        """添加IP到白名单"""
        self.whitelisted_ips.add(ip)

        self.audit_logger.log_security_event(
            "ip_whitelisted",
            "info",
            f"IP添加到白名单: {ip}",
            {"ip": ip},
            result="success",
        )

        logger.info(f"IP {ip} 已添加到白名单")

    def set_adaptive_limit(
        self, key: str, rate_limit: RateLimit, duration_minutes: int = 60
    ):
        """设置动态限制"""
        self.adaptive_limits[key] = rate_limit

        # 设置过期时间
        async def remove_adaptive_limit():
            await asyncio.sleep(duration_minutes * 60)
            if key in self.adaptive_limits:
                del self.adaptive_limits[key]
                logger.info(f"动态限制已过期: {key}")

        asyncio.create_task(remove_adaptive_limit())

        self.audit_logger.log_security_event(
            "adaptive_limit_set",
            "info",
            f"设置动态限制: {key}",
            {
                "key": key,
                "requests": rate_limit.requests,
                "window": rate_limit.window,
                "duration_minutes": duration_minutes,
            },
            result="success",
        )

    def get_statistics(self, hours: int = 1) -> Dict[str, Any]:
        """获取统计信息"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_requests = [
            record for record in self.request_history if record.timestamp > cutoff_time
        ]

        if not recent_requests:
            return {"error": "没有最近的请求数据"}

        # 按状态统计
        status_counts = defaultdict(int)
        for record in recent_requests:
            status_counts[record.status] += 1

        # 按端点统计
        endpoint_counts = defaultdict(int)
        for record in recent_requests:
            endpoint_counts[record.endpoint] += 1

        # 按IP统计
        ip_counts = defaultdict(int)
        for record in recent_requests:
            ip_counts[record.source_ip] += 1

        # 按用户统计
        user_counts = defaultdict(int)
        for record in recent_requests:
            if record.user_id:
                user_counts[record.user_id] += 1

        # 获取最活跃的IP和用户
        top_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_endpoints = sorted(
            endpoint_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return {
            "time_period_hours": hours,
            "total_requests": len(recent_requests),
            "status_distribution": dict(status_counts),
            "top_ips": [{"ip": ip, "requests": count} for ip, count in top_ips],
            "top_users": [
                {"user_id": user, "requests": count} for user, count in top_users
            ],
            "top_endpoints": [
                {"endpoint": endpoint, "requests": count}
                for endpoint, count in top_endpoints
            ],
            "blacklisted_ips": list(self.blacklisted_ips),
            "whitelisted_ips": list(self.whitelisted_ips),
            "active_buckets": len(self.token_buckets),
            "adaptive_limits": len(self.adaptive_limits),
        }

    def detect_abuse_patterns(self) -> List[Dict[str, Any]]:
        """检测滥用模式"""
        abuse_patterns = []
        cutoff_time = datetime.now() - timedelta(minutes=10)
        recent_requests = [
            record for record in self.request_history if record.timestamp > cutoff_time
        ]

        # 检测高频请求IP
        ip_counts = defaultdict(int)
        for record in recent_requests:
            ip_counts[record.source_ip] += 1

        for ip, count in ip_counts.items():
            if count > 100:  # 10分钟内超过100请求
                abuse_patterns.append(
                    {
                        "type": "high_frequency_ip",
                        "ip": ip,
                        "request_count": count,
                        "time_window": "10_minutes",
                        "severity": "high" if count > 200 else "medium",
                    }
                )

        # 检测被拒绝请求过多的IP
        denied_counts = defaultdict(int)
        for record in recent_requests:
            if record.status == "denied":
                denied_counts[record.source_ip] += 1

        for ip, count in denied_counts.items():
            if count > 20:  # 10分钟内超过20次被拒绝
                abuse_patterns.append(
                    {
                        "type": "excessive_denials",
                        "ip": ip,
                        "denied_count": count,
                        "time_window": "10_minutes",
                        "severity": "high",
                    }
                )

        return abuse_patterns

    def auto_blacklist_abusers(self):
        """自动将滥用者加入黑名单"""
        abuse_patterns = self.detect_abuse_patterns()

        for pattern in abuse_patterns:
            if pattern["severity"] == "high":
                ip = pattern["ip"]
                if ip not in self.blacklisted_ips and ip not in self.whitelisted_ips:
                    self.add_to_blacklist(ip, f"auto_blacklist_{pattern['type']}")


# 全局速率限制器实例
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """获取全局速率限制器"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def check_rate_limit(
    request: Request, user_id: Optional[str] = None, user_role: Optional[str] = None
) -> Dict[str, Any]:
    """检查速率限制的便捷函数"""
    rate_limiter = get_rate_limiter()
    return await rate_limiter.check_rate_limit(request, user_id, user_role)
