#!/usr/bin/env python3
"""
性能优化器

提供并发处理、异步优化、资源管理等性能优化功能
"""

import asyncio
import gc
import logging
import multiprocessing
import threading
import time
import weakref
from concurrent.futures import (ProcessPoolExecutor, ThreadPoolExecutor,
                                as_completed)
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache, wraps
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

logger = logging.getLogger("performance_optimizer")


@dataclass
class PerformanceConfig:
    """性能配置"""

    max_workers: int = 4
    max_concurrent_requests: int = 100
    request_timeout: float = 30.0
    memory_threshold: float = 0.8  # 80%
    cpu_threshold: float = 0.8  # 80%
    gc_threshold: int = 1000  # 对象数量阈值
    enable_profiling: bool = False


class ResourceMonitor:
    """资源监控器"""

    def __init__(self, config: PerformanceConfig):
        self.config = config
        self._monitoring = False
        self._monitor_thread = None
        self._stats = {
            "memory_usage": 0.0,
            "cpu_usage": 0.0,
            "active_threads": 0,
            "gc_collections": 0,
        }
        self._lock = threading.Lock()

    def start_monitoring(self):
        """开始资源监控"""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Resource monitoring started")

    def stop_monitoring(self):
        """停止资源监控"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Resource monitoring stopped")

    def _monitor_loop(self):
        """监控循环"""
        while self._monitoring:
            try:
                self._update_stats()
                self._check_thresholds()
                time.sleep(5)  # 每5秒检查一次
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                time.sleep(5)

    def _update_stats(self):
        """更新统计信息"""
        try:
            import psutil

            # 获取内存使用率
            memory = psutil.virtual_memory()
            memory_usage = memory.percent / 100.0

            # 获取CPU使用率
            cpu_usage = psutil.cpu_percent() / 100.0

            # 获取线程数
            active_threads = threading.active_count()

            # 获取GC统计
            gc_stats = gc.get_stats()
            gc_collections = sum(stat["collections"] for stat in gc_stats)

            with self._lock:
                self._stats.update(
                    {
                        "memory_usage": memory_usage,
                        "cpu_usage": cpu_usage,
                        "active_threads": active_threads,
                        "gc_collections": gc_collections,
                    }
                )

        except Exception as e:
            logger.error(f"Error updating resource stats: {e}")

    def _check_thresholds(self):
        """检查资源阈值"""
        with self._lock:
            stats = self._stats.copy()

        # 检查内存使用率
        if stats["memory_usage"] > self.config.memory_threshold:
            logger.warning(f"High memory usage: {stats['memory_usage']:.1%}")
            self._trigger_gc()

        # 检查CPU使用率
        if stats["cpu_usage"] > self.config.cpu_threshold:
            logger.warning(f"High CPU usage: {stats['cpu_usage']:.1%}")

    def _trigger_gc(self):
        """触发垃圾回收"""
        try:
            collected = gc.collect()
            logger.info(f"Garbage collection triggered, collected {collected} objects")
        except Exception as e:
            logger.error(f"Error during garbage collection: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取资源统计"""
        with self._lock:
            return self._stats.copy()


class ConcurrencyManager:
    """并发管理器"""

    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.thread_pool = ThreadPoolExecutor(max_workers=config.max_workers)
        self.process_pool = ProcessPoolExecutor(max_workers=config.max_workers)
        self.semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self._active_tasks = weakref.WeakSet()

    async def run_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """在线程池中运行函数"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, func, *args, **kwargs)

    async def run_in_process(self, func: Callable, *args, **kwargs) -> Any:
        """在进程池中运行函数"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.process_pool, func, *args, **kwargs)

    async def run_concurrent(
        self, tasks: List[Awaitable], max_concurrent: Optional[int] = None
    ) -> List[Any]:
        """并发运行多个任务"""
        if max_concurrent is None:
            max_concurrent = self.config.max_concurrent_requests

        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_semaphore(task):
            async with semaphore:
                return await task

        # 包装所有任务
        wrapped_tasks = [run_with_semaphore(task) for task in tasks]

        # 并发执行
        results = await asyncio.gather(*wrapped_tasks, return_exceptions=True)

        return results

    async def run_with_timeout(
        self, coro: Awaitable, timeout: Optional[float] = None
    ) -> Any:
        """带超时的异步执行"""
        timeout = timeout or self.config.request_timeout

        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Task timed out after {timeout} seconds")
            raise

    @asynccontextmanager
    async def rate_limit(self):
        """速率限制上下文管理器"""
        async with self.semaphore:
            yield

    def shutdown(self):
        """关闭并发管理器"""
        self.thread_pool.shutdown(wait=True)
        self.process_pool.shutdown(wait=True)
        logger.info("Concurrency manager shutdown")


class MemoryManager:
    """内存管理器"""

    def __init__(self, config: PerformanceConfig):
        self.config = config
        self._object_cache = weakref.WeakValueDictionary()
        self._gc_counter = 0

    def get_memory_usage(self) -> Dict[str, Any]:
        """获取内存使用情况"""
        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                "rss": memory_info.rss,
                "vms": memory_info.vms,
                "percent": process.memory_percent(),
                "available": psutil.virtual_memory().available,
            }
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {}

    def optimize_memory(self):
        """优化内存使用"""
        try:
            # 强制垃圾回收
            collected = gc.collect()

            # 清理弱引用缓存
            self._object_cache.clear()

            # 重置GC计数器
            self._gc_counter = 0

            logger.info(f"Memory optimization completed, collected {collected} objects")

        except Exception as e:
            logger.error(f"Error during memory optimization: {e}")

    def cache_object(self, key: str, obj: Any):
        """缓存对象（使用弱引用）"""
        self._object_cache[key] = obj
        self._gc_counter += 1

        # 定期触发垃圾回收
        if self._gc_counter >= self.config.gc_threshold:
            self.optimize_memory()

    def get_cached_object(self, key: str) -> Optional[Any]:
        """获取缓存的对象"""
        return self._object_cache.get(key)


class PerformanceOptimizer:
    """性能优化器主类"""

    def __init__(self, config: Optional[PerformanceConfig] = None):
        self.config = config or PerformanceConfig()
        self.resource_monitor = ResourceMonitor(self.config)
        self.concurrency_manager = ConcurrencyManager(self.config)
        self.memory_manager = MemoryManager(self.config)
        self._initialized = False

    def initialize(self):
        """初始化性能优化器"""
        if self._initialized:
            return

        self.resource_monitor.start_monitoring()
        self._initialized = True
        logger.info("Performance optimizer initialized")

    def shutdown(self):
        """关闭性能优化器"""
        if not self._initialized:
            return

        self.resource_monitor.stop_monitoring()
        self.concurrency_manager.shutdown()
        self._initialized = False
        logger.info("Performance optimizer shutdown")

    async def optimize_async_function(self, func: Callable, *args, **kwargs) -> Any:
        """优化异步函数执行"""
        async with self.concurrency_manager.rate_limit():
            return await self.concurrency_manager.run_with_timeout(
                func(*args, **kwargs)
            )

    async def optimize_sync_function(self, func: Callable, *args, **kwargs) -> Any:
        """优化同步函数执行"""
        async with self.concurrency_manager.rate_limit():
            return await self.concurrency_manager.run_in_thread(func, *args, **kwargs)

    async def batch_process(
        self, items: List[Any], processor: Callable, batch_size: int = 10
    ) -> List[Any]:
        """批量处理"""
        results = []

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]

            # 创建批处理任务
            if asyncio.iscoroutinefunction(processor):
                tasks = [processor(item) for item in batch]
            else:
                tasks = [
                    self.concurrency_manager.run_in_thread(processor, item)
                    for item in batch
                ]

            # 并发执行批处理
            batch_results = await self.concurrency_manager.run_concurrent(tasks)
            results.extend(batch_results)

        return results

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            "resource_stats": self.resource_monitor.get_stats(),
            "memory_stats": self.memory_manager.get_memory_usage(),
            "config": {
                "max_workers": self.config.max_workers,
                "max_concurrent_requests": self.config.max_concurrent_requests,
                "request_timeout": self.config.request_timeout,
            },
        }


# 全局性能优化器实例
_performance_optimizer: Optional[PerformanceOptimizer] = None


def get_performance_optimizer() -> PerformanceOptimizer:
    """获取全局性能优化器"""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
        _performance_optimizer.initialize()
    return _performance_optimizer


def optimize_performance(timeout: Optional[float] = None, use_thread: bool = False):
    """性能优化装饰器"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            optimizer = get_performance_optimizer()

            if use_thread and not asyncio.iscoroutinefunction(func):
                return await optimizer.optimize_sync_function(func, *args, **kwargs)
            else:
                return await optimizer.optimize_async_function(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 对于同步函数，在事件循环中运行
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


def batch_process(batch_size: int = 10):
    """批处理装饰器"""

    def decorator(func):
        @wraps(func)
        async def wrapper(items: List[Any], *args, **kwargs):
            optimizer = get_performance_optimizer()

            def processor(item):
                return func(item, *args, **kwargs)

            return await optimizer.batch_process(items, processor, batch_size)

        return wrapper

    return decorator


def memory_optimized(cache_key: Optional[str] = None):
    """内存优化装饰器"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            optimizer = get_performance_optimizer()
            memory_manager = optimizer.memory_manager

            # 尝试从缓存获取
            if cache_key:
                cached_result = memory_manager.get_cached_object(cache_key)
                if cached_result is not None:
                    return cached_result

            # 执行函数
            result = func(*args, **kwargs)

            # 缓存结果
            if cache_key:
                memory_manager.cache_object(cache_key, result)

            return result

        return wrapper

    return decorator


# 便捷函数
async def run_concurrent_tasks(
    tasks: List[Awaitable], max_concurrent: Optional[int] = None
) -> List[Any]:
    """并发运行任务的便捷函数"""
    optimizer = get_performance_optimizer()
    return await optimizer.concurrency_manager.run_concurrent(tasks, max_concurrent)


async def run_with_timeout(coro: Awaitable, timeout: float) -> Any:
    """带超时运行协程的便捷函数"""
    optimizer = get_performance_optimizer()
    return await optimizer.concurrency_manager.run_with_timeout(coro, timeout)


def optimize_memory():
    """优化内存的便捷函数"""
    optimizer = get_performance_optimizer()
    optimizer.memory_manager.optimize_memory()


def get_performance_stats() -> Dict[str, Any]:
    """获取性能统计的便捷函数"""
    optimizer = get_performance_optimizer()
    return optimizer.get_performance_stats()
