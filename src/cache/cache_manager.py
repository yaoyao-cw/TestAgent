#!/usr/bin/env python3
"""
缓存管理器

提供统一的缓存接口，支持多种缓存后端
"""

import json
import pickle
import hashlib
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar
from datetime import datetime, timedelta
from dataclasses import dataclass
from functools import wraps
import threading

logger = logging.getLogger("cache_manager")

T = TypeVar("T")


@dataclass
class CacheEntry:
    """缓存条目"""

    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    size: int = 0
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.last_accessed is None:
            self.last_accessed = self.created_at

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def touch(self):
        """更新访问时间和计数"""
        self.last_accessed = datetime.now()
        self.access_count += 1


class CacheBackend(ABC):
    """缓存后端抽象基类"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """清空所有缓存"""
        pass

    @abstractmethod
    async def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配的键列表"""
        pass

    @abstractmethod
    async def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        pass


class MemoryCache(CacheBackend):
    """内存缓存实现"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            entry.touch()
            self._hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        with self._lock:
            # 检查是否需要清理空间
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()

            # 计算过期时间
            expires_at = None
            if ttl is not None:
                expires_at = datetime.now() + timedelta(seconds=ttl)
            elif self.default_ttl > 0:
                expires_at = datetime.now() + timedelta(seconds=self.default_ttl)

            # 计算值的大小
            try:
                size = len(pickle.dumps(value))
            except:
                size = len(str(value))

            # 创建缓存条目
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                expires_at=expires_at,
                size=size,
            )

            self._cache[key] = entry
            return True

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._cache[key]
                return False
            return True

    async def clear(self) -> bool:
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            return True

    async def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配的键列表"""
        import fnmatch

        with self._lock:
            # 清理过期条目
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]

            # 返回匹配的键
            if pattern == "*":
                return list(self._cache.keys())
            else:
                return [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]

    async def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            total_size = sum(entry.size for entry in self._cache.values())
            return {
                "type": "memory",
                "entries": len(self._cache),
                "max_size": self.max_size,
                "total_size": total_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": (
                    self._hits / (self._hits + self._misses)
                    if (self._hits + self._misses) > 0
                    else 0
                ),
                "evictions": self._evictions,
            }

    def _evict_lru(self):
        """清理最近最少使用的条目"""
        if not self._cache:
            return

        # 找到最近最少使用的条目
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        del self._cache[lru_key]
        self._evictions += 1


class RedisCache(CacheBackend):
    """Redis缓存实现"""

    def __init__(self, redis_url: str, default_ttl: int = 3600):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._redis = None
        self._connected = False

    async def _ensure_connected(self):
        """确保Redis连接"""
        if not self._connected:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(self.redis_url, decode_responses=False)
                await self._redis.ping()
                self._connected = True
                logger.info("Connected to Redis cache")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        await self._ensure_connected()
        try:
            data = await self._redis.get(key)
            if data is None:
                return None
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        await self._ensure_connected()
        try:
            data = pickle.dumps(value)
            ttl = ttl or self.default_ttl
            if ttl > 0:
                await self._redis.setex(key, ttl, data)
            else:
                await self._redis.set(key, data)
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        await self._ensure_connected()
        try:
            result = await self._redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        await self._ensure_connected()
        try:
            result = await self._redis.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {e}")
            return False

    async def clear(self) -> bool:
        """清空所有缓存"""
        await self._ensure_connected()
        try:
            await self._redis.flushdb()
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False

    async def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配的键列表"""
        await self._ensure_connected()
        try:
            keys = await self._redis.keys(pattern)
            return [key.decode() if isinstance(key, bytes) else key for key in keys]
        except Exception as e:
            logger.error(f"Error getting cache keys: {e}")
            return []

    async def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        await self._ensure_connected()
        try:
            info = await self._redis.info()
            return {
                "type": "redis",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": info.get("keyspace_hits", 0)
                / (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1)),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"type": "redis", "error": str(e)}


class CacheManager:
    """缓存管理器"""

    def __init__(self, backend: CacheBackend):
        self.backend = backend
        self._enabled = True

    def enable(self):
        """启用缓存"""
        self._enabled = True

    def disable(self):
        """禁用缓存"""
        self._enabled = False

    def is_enabled(self) -> bool:
        """检查缓存是否启用"""
        return self._enabled

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if not self._enabled:
            return None
        return await self.backend.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        if not self._enabled:
            return False
        return await self.backend.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        if not self._enabled:
            return False
        return await self.backend.delete(key)

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self._enabled:
            return False
        return await self.backend.exists(key)

    async def clear(self) -> bool:
        """清空所有缓存"""
        if not self._enabled:
            return False
        return await self.backend.clear()

    async def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配的键列表"""
        if not self._enabled:
            return []
        return await self.backend.keys(pattern)

    async def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        stats = await self.backend.stats()
        stats["enabled"] = self._enabled
        return stats

    def generate_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        # 创建一个包含所有参数的字符串
        key_data = {"args": args, "kwargs": sorted(kwargs.items()) if kwargs else {}}
        key_str = json.dumps(key_data, sort_keys=True, default=str)

        # 生成哈希值作为键
        return hashlib.md5(key_str.encode()).hexdigest()

    async def get_or_set(
        self, key: str, func: Callable, ttl: Optional[int] = None, *args, **kwargs
    ) -> Any:
        """获取缓存值，如果不存在则调用函数并缓存结果"""
        if not self._enabled:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        # 尝试从缓存获取
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value

        # 缓存未命中，调用函数
        if asyncio.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)

        # 缓存结果
        await self.set(key, result, ttl)
        return result


# 全局缓存管理器实例
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器"""
    global _cache_manager
    if _cache_manager is None:
        # 根据配置创建缓存后端
        try:
            from ..config.settings import get_settings

            settings = get_settings()

            if settings.cache.redis_url:
                backend = RedisCache(settings.cache.redis_url, settings.cache.ttl)
            else:
                backend = MemoryCache(default_ttl=settings.cache.ttl)

            _cache_manager = CacheManager(backend)

            if not settings.cache.enabled:
                _cache_manager.disable()

        except Exception as e:
            logger.warning(
                f"Failed to initialize cache from config, using memory cache: {e}"
            )
            backend = MemoryCache()
            _cache_manager = CacheManager(backend)

    return _cache_manager


def cache(ttl: Optional[int] = None, key_func: Optional[Callable] = None):
    """缓存装饰器"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()

            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__module__}.{func.__name__}:{cache_manager.generate_key(*args, **kwargs)}"

            return await cache_manager.get_or_set(cache_key, func, ttl, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 对于同步函数，需要在事件循环中运行
            try:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(async_wrapper(*args, **kwargs))
            except RuntimeError:
                # 如果没有事件循环，直接调用函数
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def cache_key(*args, **kwargs) -> str:
    """生成缓存键的便捷函数"""
    cache_manager = get_cache_manager()
    return cache_manager.generate_key(*args, **kwargs)
