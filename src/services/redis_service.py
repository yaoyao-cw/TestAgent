"""
Redis缓存服务

集成Redis缓存服务，支持会话存储和性能优化。
"""

import asyncio
import json
import logging
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

try:
    import redis as redis_sync
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    redis_sync = None

from ..config.logging_config import get_logger
from .health_monitor import (HealthChecker, HealthCheckResult, HealthStatus,
                             register_health_check)
from .service_registry import (ServiceInfo, ServicePriority, ServiceType,
                               register_service)

logger = get_logger("redis_service")


@dataclass
class RedisConfig:
    """Redis配置"""

    url: str = "redis://localhost:6379/0"
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    username: Optional[str] = None
    ssl: bool = False
    ssl_cert_reqs: Optional[str] = None
    ssl_ca_certs: Optional[str] = None
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    max_connections: int = 50
    retry_on_timeout: bool = True
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    health_check_interval: int = 30
    decode_responses: bool = True
    encoding: str = "utf-8"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RedisMetrics:
    """Redis指标"""

    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_keys: int = 0
    memory_usage: int = 0
    avg_response_time: float = 0.0
    last_operation_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_operations == 0:
            return 0.0
        return (self.successful_operations / self.total_operations) * 100

    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        total_requests = self.cache_hits + self.cache_misses
        if total_requests == 0:
            return 0.0
        return (self.cache_hits / total_requests) * 100

    def update_operation_metrics(
        self, success: bool, response_time: float, is_hit: Optional[bool] = None
    ):
        """更新操作指标"""
        self.total_operations += 1
        self.last_operation_time = datetime.now()

        if success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1

        if is_hit is not None:
            if is_hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

        # 更新平均响应时间
        if self.total_operations == 1:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (
                self.avg_response_time * (self.total_operations - 1) + response_time
            ) / self.total_operations


class RedisHealthChecker(HealthChecker):
    """Redis健康检查器"""

    def __init__(self, config: RedisConfig):
        self.config = config

    async def check_health(self) -> HealthCheckResult:
        """执行健康检查"""
        start_time = time.time()
        service_name = "redis"

        try:
            if not REDIS_AVAILABLE:
                return HealthCheckResult(
                    service_name=service_name,
                    status=HealthStatus.UNHEALTHY,
                    response_time=time.time() - start_time,
                    timestamp=datetime.now(),
                    message="Redis客户端未安装",
                )

            # 创建Redis连接
            if self.config.url:
                client = redis.from_url(
                    self.config.url,
                    decode_responses=self.config.decode_responses,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )
            else:
                client = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    username=self.config.username,
                    decode_responses=self.config.decode_responses,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )

            # 执行ping测试
            await client.ping()

            # 获取Redis信息
            info = await client.info()

            response_time = time.time() - start_time

            # 检查内存使用情况
            memory_usage = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)

            status = HealthStatus.HEALTHY
            message = "Redis服务正常"

            # 检查内存使用率
            if max_memory > 0:
                memory_usage_percent = (memory_usage / max_memory) * 100
                if memory_usage_percent > 90:
                    status = HealthStatus.DEGRADED
                    message = f"Redis内存使用率过高: {memory_usage_percent:.1f}%"
                elif memory_usage_percent > 80:
                    status = HealthStatus.DEGRADED
                    message = f"Redis内存使用率较高: {memory_usage_percent:.1f}%"

            await client.close()

            return HealthCheckResult(
                service_name=service_name,
                status=status,
                response_time=response_time,
                timestamp=datetime.now(),
                message=message,
                details={
                    "redis_version": info.get("redis_version", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": memory_usage,
                    "used_memory_human": info.get("used_memory_human", "0B"),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                    "total_commands_processed": info.get("total_commands_processed", 0),
                },
            )

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=datetime.now(),
                message=f"Redis健康检查失败: {str(e)}",
            )


class RedisService:
    """Redis服务"""

    def __init__(self, config: RedisConfig):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis客户端未安装，请运行: pip install redis")

        self.config = config
        self.metrics = RedisMetrics()
        self._client: Optional[redis.Redis] = None
        self._sync_client: Optional[redis_sync.Redis] = None
        self._connected = False
        self._connection_pool = None

        self._initialize_redis()

    def _initialize_redis(self):
        """初始化Redis连接"""
        try:
            # 创建连接池
            if self.config.url:
                self._connection_pool = redis.ConnectionPool.from_url(
                    self.config.url,
                    max_connections=self.config.max_connections,
                    retry_on_timeout=self.config.retry_on_timeout,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                    decode_responses=self.config.decode_responses,
                    encoding=self.config.encoding,
                )
            else:
                self._connection_pool = redis.ConnectionPool(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    username=self.config.username,
                    max_connections=self.config.max_connections,
                    retry_on_timeout=self.config.retry_on_timeout,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                    decode_responses=self.config.decode_responses,
                    encoding=self.config.encoding,
                )

            # 创建异步客户端
            self._client = redis.Redis(connection_pool=self._connection_pool)

            # 创建同步客户端
            if self.config.url:
                self._sync_client = redis_sync.from_url(
                    self.config.url,
                    decode_responses=self.config.decode_responses,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                )
            else:
                self._sync_client = redis_sync.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    username=self.config.username,
                    decode_responses=self.config.decode_responses,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                )

            # 注册健康检查
            health_checker = RedisHealthChecker(self.config)
            register_health_check("redis", health_checker)

            # 注册服务
            service_info = ServiceInfo(
                name="redis",
                service_type=ServiceType.CACHE,
                priority=ServicePriority.PRIMARY,
                endpoint=self.config.url or f"{self.config.host}:{self.config.port}",
                config=self.config.__dict__,
                tags=["cache", "redis", "session"],
            )
            register_service(service_info)

            logger.info("Redis服务已初始化")

        except Exception as e:
            logger.error(f"初始化Redis服务失败: {e}")
            raise

    async def _ensure_connected(self):
        """确保连接"""
        if not self._connected:
            try:
                await self._client.ping()
                self._connected = True
            except Exception as e:
                logger.error(f"Redis连接失败: {e}")
                raise

    async def get(self, key: str, default: Any = None) -> Any:
        """获取值"""
        start_time = time.time()

        try:
            await self._ensure_connected()

            value = await self._client.get(key)
            response_time = time.time() - start_time

            if value is not None:
                # 尝试反序列化
                try:
                    if isinstance(value, (bytes, str)):
                        # 首先尝试JSON反序列化
                        try:
                            result = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            # 如果JSON失败，尝试pickle
                            try:
                                result = pickle.loads(
                                    value
                                    if isinstance(value, bytes)
                                    else value.encode()
                                )
                            except:
                                # 如果都失败，返回原始值
                                result = value
                    else:
                        result = value

                    self.metrics.update_operation_metrics(True, response_time, True)
                    return result
                except Exception:
                    self.metrics.update_operation_metrics(True, response_time, True)
                    return value
            else:
                self.metrics.update_operation_metrics(True, response_time, False)
                return default

        except Exception as e:
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(False, response_time)
            logger.error(f"Redis GET操作失败 {key}: {e}")
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """设置值"""
        start_time = time.time()

        try:
            await self._ensure_connected()

            # 序列化值
            if isinstance(value, (dict, list, tuple)):
                serialized_value = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, (str, int, float, bool)):
                serialized_value = value
            else:
                # 使用pickle序列化复杂对象
                serialized_value = pickle.dumps(value)

            result = await self._client.set(
                key, serialized_value, ex=ex, px=px, nx=nx, xx=xx
            )

            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(True, response_time)

            return bool(result)

        except Exception as e:
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(False, response_time)
            logger.error(f"Redis SET操作失败 {key}: {e}")
            return False

    async def delete(self, *keys: str) -> int:
        """删除键"""
        start_time = time.time()

        try:
            await self._ensure_connected()

            result = await self._client.delete(*keys)
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(True, response_time)

            return result

        except Exception as e:
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(False, response_time)
            logger.error(f"Redis DELETE操作失败 {keys}: {e}")
            return 0

    async def exists(self, *keys: str) -> int:
        """检查键是否存在"""
        start_time = time.time()

        try:
            await self._ensure_connected()

            result = await self._client.exists(*keys)
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(True, response_time)

            return result

        except Exception as e:
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(False, response_time)
            logger.error(f"Redis EXISTS操作失败 {keys}: {e}")
            return 0

    async def expire(self, key: str, time: int) -> bool:
        """设置过期时间"""
        start_time = time.time()

        try:
            await self._ensure_connected()

            result = await self._client.expire(key, time)
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(True, response_time)

            return bool(result)

        except Exception as e:
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(False, response_time)
            logger.error(f"Redis EXPIRE操作失败 {key}: {e}")
            return False

    async def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配的键"""
        start_time = time.time()

        try:
            await self._ensure_connected()

            result = await self._client.keys(pattern)
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(True, response_time)

            return result

        except Exception as e:
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(False, response_time)
            logger.error(f"Redis KEYS操作失败 {pattern}: {e}")
            return []

    async def flushdb(self) -> bool:
        """清空当前数据库"""
        start_time = time.time()

        try:
            await self._ensure_connected()

            result = await self._client.flushdb()
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(True, response_time)

            return bool(result)

        except Exception as e:
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(False, response_time)
            logger.error(f"Redis FLUSHDB操作失败: {e}")
            return False

    async def info(self) -> Dict[str, Any]:
        """获取Redis信息"""
        start_time = time.time()

        try:
            await self._ensure_connected()

            result = await self._client.info()
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(True, response_time)

            return result

        except Exception as e:
            response_time = time.time() - start_time
            self.metrics.update_operation_metrics(False, response_time)
            logger.error(f"Redis INFO操作失败: {e}")
            return {}

    # 会话存储相关方法
    async def set_session(
        self, session_id: str, data: Dict[str, Any], ttl: int = 3600
    ) -> bool:
        """设置会话数据"""
        session_key = f"session:{session_id}"
        return await self.set(session_key, data, ex=ttl)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话数据"""
        session_key = f"session:{session_id}"
        return await self.get(session_key)

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        session_key = f"session:{session_id}"
        result = await self.delete(session_key)
        return result > 0

    async def extend_session(self, session_id: str, ttl: int = 3600) -> bool:
        """延长会话有效期"""
        session_key = f"session:{session_id}"
        return await self.expire(session_key, ttl)

    # 缓存相关方法
    async def cache_get(self, key: str) -> Any:
        """获取缓存"""
        cache_key = f"cache:{key}"
        return await self.get(cache_key)

    async def cache_set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存"""
        cache_key = f"cache:{key}"
        return await self.set(cache_key, value, ex=ttl)

    async def cache_delete(self, key: str) -> bool:
        """删除缓存"""
        cache_key = f"cache:{key}"
        result = await self.delete(cache_key)
        return result > 0

    def get_metrics(self) -> RedisMetrics:
        """获取指标"""
        return self.metrics

    def reset_metrics(self):
        """重置指标"""
        self.metrics = RedisMetrics()
        logger.info("Redis指标已重置")

    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            info = await self.info()

            return {
                "connected": self._connected,
                "redis_version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "operations": {
                    "total": self.metrics.total_operations,
                    "success_rate": self.metrics.success_rate,
                    "avg_response_time": self.metrics.avg_response_time,
                    "cache_hit_rate": self.metrics.hit_rate,
                },
            }
        except Exception as e:
            logger.error(f"获取Redis统计信息失败: {e}")
            return {
                "connected": self._connected,
                "error": str(e),
                "operations": {
                    "total": self.metrics.total_operations,
                    "success_rate": self.metrics.success_rate,
                    "avg_response_time": self.metrics.avg_response_time,
                    "cache_hit_rate": self.metrics.hit_rate,
                },
            }

    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.close()
        if self._sync_client:
            self._sync_client.close()
        self._connected = False
        logger.info("Redis连接已关闭")


# 全局Redis服务实例
_redis_service: Optional[RedisService] = None


def get_redis_service() -> Optional[RedisService]:
    """获取全局Redis服务实例"""
    return _redis_service


def initialize_redis_service(config: RedisConfig) -> RedisService:
    """初始化Redis服务"""
    global _redis_service
    if _redis_service is None:
        _redis_service = RedisService(config)
    return _redis_service
