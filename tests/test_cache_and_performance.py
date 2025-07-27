#!/usr/bin/env python3
"""
缓存和性能优化系统测试
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cache.cache_manager import (CacheEntry, CacheManager, MemoryCache,
                                     cache)
from src.cache.llm_cache import LLMCache
from src.cache.rag_cache import RAGCache
from src.performance.optimizer import (ConcurrencyManager, MemoryManager,
                                       PerformanceConfig, PerformanceOptimizer,
                                       ResourceMonitor)


class TestMemoryCache:
    """测试内存缓存"""

    def setup_method(self):
        """设置测试"""
        self.cache = MemoryCache(max_size=10, default_ttl=60)

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """测试设置和获取缓存"""
        await self.cache.set("test_key", "test_value")
        value = await self.cache.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """测试TTL过期"""
        await self.cache.set("expire_key", "expire_value", ttl=1)

        # 立即获取应该成功
        value = await self.cache.get("expire_key")
        assert value == "expire_value"

        # 等待过期
        await asyncio.sleep(1.1)
        value = await self.cache.get("expire_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """测试删除缓存"""
        await self.cache.set("delete_key", "delete_value")

        # 确认存在
        assert await self.cache.exists("delete_key")

        # 删除
        success = await self.cache.delete("delete_key")
        assert success

        # 确认不存在
        assert not await self.cache.exists("delete_key")

    @pytest.mark.asyncio
    async def test_clear(self):
        """测试清空缓存"""
        await self.cache.set("key1", "value1")
        await self.cache.set("key2", "value2")

        # 确认有数据
        keys = await self.cache.keys()
        assert len(keys) == 2

        # 清空
        await self.cache.clear()

        # 确认已清空
        keys = await self.cache.keys()
        assert len(keys) == 0

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """测试LRU淘汰"""
        # 填满缓存
        for i in range(10):
            await self.cache.set(f"key_{i}", f"value_{i}")

        # 添加一个新键，应该淘汰最旧的
        await self.cache.set("new_key", "new_value")

        # 检查最旧的键是否被淘汰
        value = await self.cache.get("key_0")
        assert value is None

        # 检查新键是否存在
        value = await self.cache.get("new_key")
        assert value == "new_value"

    @pytest.mark.asyncio
    async def test_stats(self):
        """测试统计信息"""
        # 设置一些数据
        await self.cache.set("key1", "value1")
        await self.cache.get("key1")  # 命中
        await self.cache.get("nonexistent")  # 未命中

        stats = await self.cache.stats()

        assert stats["type"] == "memory"
        assert stats["entries"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5


class TestCacheManager:
    """测试缓存管理器"""

    def setup_method(self):
        """设置测试"""
        backend = MemoryCache()
        self.cache_manager = CacheManager(backend)

    @pytest.mark.asyncio
    async def test_get_or_set(self):
        """测试获取或设置"""
        call_count = 0

        def expensive_function():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # 第一次调用，应该执行函数
        result1 = await self.cache_manager.get_or_set("test_key", expensive_function)
        assert result1 == "result_1"
        assert call_count == 1

        # 第二次调用，应该从缓存获取
        result2 = await self.cache_manager.get_or_set("test_key", expensive_function)
        assert result2 == "result_1"
        assert call_count == 1  # 函数没有再次调用

    def test_generate_key(self):
        """测试键生成"""
        key1 = self.cache_manager.generate_key("arg1", "arg2", kwarg1="value1")
        key2 = self.cache_manager.generate_key("arg1", "arg2", kwarg1="value1")
        key3 = self.cache_manager.generate_key("arg1", "arg2", kwarg1="value2")

        # 相同参数应该生成相同键
        assert key1 == key2

        # 不同参数应该生成不同键
        assert key1 != key3

    def test_enable_disable(self):
        """测试启用/禁用缓存"""
        assert self.cache_manager.is_enabled()

        self.cache_manager.disable()
        assert not self.cache_manager.is_enabled()

        self.cache_manager.enable()
        assert self.cache_manager.is_enabled()


class TestLLMCache:
    """测试LLM缓存"""

    def setup_method(self):
        """设置测试"""
        self.llm_cache = LLMCache()

    @pytest.mark.asyncio
    async def test_cache_llm_response(self):
        """测试缓存LLM响应"""
        provider = "openai"
        model = "gpt-3.5-turbo"
        messages = [{"role": "user", "content": "Hello"}]
        response = {"choices": [{"message": {"content": "Hi there!"}}]}

        # 缓存响应
        success = await self.llm_cache.cache_response(
            provider, model, messages, response
        )
        assert success

        # 获取缓存的响应
        cached_response = await self.llm_cache.get_cached_response(
            provider, model, messages
        )
        assert cached_response is not None
        assert cached_response["response"] == response
        assert cached_response["_cached"] == True

    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """测试缓存键生成"""
        provider = "openai"
        model = "gpt-3.5-turbo"
        messages1 = [{"role": "user", "content": "Hello"}]
        messages2 = [{"role": "user", "content": "Hi"}]

        key1 = self.llm_cache._generate_cache_key(provider, model, messages1)
        key2 = self.llm_cache._generate_cache_key(provider, model, messages1)
        key3 = self.llm_cache._generate_cache_key(provider, model, messages2)

        # 相同参数应该生成相同键
        assert key1 == key2

        # 不同消息应该生成不同键
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_invalidate_cache(self):
        """测试清除缓存"""
        provider = "openai"
        model = "gpt-3.5-turbo"
        messages = [{"role": "user", "content": "Hello"}]
        response = {"choices": [{"message": {"content": "Hi there!"}}]}

        # 缓存响应
        await self.llm_cache.cache_response(provider, model, messages, response)

        # 确认缓存存在
        cached_response = await self.llm_cache.get_cached_response(
            provider, model, messages
        )
        assert cached_response is not None

        # 清除缓存
        count = await self.llm_cache.invalidate_cache(provider, model)
        assert count >= 1

        # 确认缓存已清除
        cached_response = await self.llm_cache.get_cached_response(
            provider, model, messages
        )
        assert cached_response is None


class TestRAGCache:
    """测试RAG缓存"""

    def setup_method(self):
        """设置测试"""
        self.rag_cache = RAGCache()

    @pytest.mark.asyncio
    async def test_cache_retrieval_result(self):
        """测试缓存检索结果"""
        query = "test query"
        results = [{"content": "result1"}, {"content": "result2"}]

        # 缓存检索结果
        success = await self.rag_cache.cache_retrieval_result(query, results)
        assert success

        # 获取缓存的结果
        cached_results = await self.rag_cache.get_cached_retrieval(query)
        assert cached_results == results

    @pytest.mark.asyncio
    async def test_cache_vector(self):
        """测试缓存向量"""
        text = "test text"
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        model = "test_model"

        # 缓存向量
        success = await self.rag_cache.cache_vector(text, vector, model)
        assert success

        # 获取缓存的向量
        cached_vector = await self.rag_cache.get_cached_vector(text, model)
        assert cached_vector == vector

    @pytest.mark.asyncio
    async def test_cache_document(self):
        """测试缓存文档"""
        document_id = "doc123"
        document_data = {"title": "Test Document", "content": "Test content"}

        # 缓存文档
        success = await self.rag_cache.cache_document(document_id, document_data)
        assert success

        # 获取缓存的文档
        cached_doc = await self.rag_cache.get_cached_document(document_id)
        assert cached_doc["data"] == document_data


class TestPerformanceOptimizer:
    """测试性能优化器"""

    def setup_method(self):
        """设置测试"""
        config = PerformanceConfig(max_workers=2, max_concurrent_requests=5)
        self.optimizer = PerformanceOptimizer(config)
        self.optimizer.initialize()

    def teardown_method(self):
        """清理测试"""
        self.optimizer.shutdown()

    @pytest.mark.asyncio
    async def test_optimize_async_function(self):
        """测试优化异步函数"""

        async def test_func(value):
            await asyncio.sleep(0.1)
            return value * 2

        result = await self.optimizer.optimize_async_function(test_func, 5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_optimize_sync_function(self):
        """测试优化同步函数"""

        def test_func(value):
            time.sleep(0.1)
            return value * 2

        result = await self.optimizer.optimize_sync_function(test_func, 5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_batch_process(self):
        """测试批处理"""
        items = list(range(10))

        def processor(item):
            return item * 2

        results = await self.optimizer.batch_process(items, processor, batch_size=3)
        expected = [i * 2 for i in items]
        assert results == expected

    def test_get_performance_stats(self):
        """测试获取性能统计"""
        stats = self.optimizer.get_performance_stats()

        assert "resource_stats" in stats
        assert "memory_stats" in stats
        assert "config" in stats
        assert stats["config"]["max_workers"] == 2


class TestResourceMonitor:
    """测试资源监控器"""

    def setup_method(self):
        """设置测试"""
        config = PerformanceConfig()
        self.monitor = ResourceMonitor(config)

    def teardown_method(self):
        """清理测试"""
        self.monitor.stop_monitoring()

    def test_start_stop_monitoring(self):
        """测试启动和停止监控"""
        assert not self.monitor._monitoring

        self.monitor.start_monitoring()
        assert self.monitor._monitoring

        self.monitor.stop_monitoring()
        assert not self.monitor._monitoring

    def test_get_stats(self):
        """测试获取统计信息"""
        stats = self.monitor.get_stats()

        assert "memory_usage" in stats
        assert "cpu_usage" in stats
        assert "active_threads" in stats
        assert "gc_collections" in stats


class TestConcurrencyManager:
    """测试并发管理器"""

    def setup_method(self):
        """设置测试"""
        config = PerformanceConfig(max_workers=2)
        self.manager = ConcurrencyManager(config)

    def teardown_method(self):
        """清理测试"""
        self.manager.shutdown()

    @pytest.mark.asyncio
    async def test_run_in_thread(self):
        """测试在线程中运行"""

        def cpu_bound_task(n):
            return sum(i * i for i in range(n))

        result = await self.manager.run_in_thread(cpu_bound_task, 1000)
        expected = sum(i * i for i in range(1000))
        assert result == expected

    @pytest.mark.asyncio
    async def test_run_concurrent(self):
        """测试并发运行"""

        async def async_task(value):
            await asyncio.sleep(0.1)
            return value * 2

        tasks = [async_task(i) for i in range(5)]
        results = await self.manager.run_concurrent(tasks, max_concurrent=2)

        expected = [i * 2 for i in range(5)]
        assert results == expected

    @pytest.mark.asyncio
    async def test_run_with_timeout(self):
        """测试带超时运行"""

        async def slow_task():
            await asyncio.sleep(2)
            return "completed"

        # 应该超时
        with pytest.raises(asyncio.TimeoutError):
            await self.manager.run_with_timeout(slow_task(), timeout=0.5)


class TestMemoryManager:
    """测试内存管理器"""

    def setup_method(self):
        """设置测试"""
        config = PerformanceConfig()
        self.manager = MemoryManager(config)

    def test_cache_object(self):
        """测试缓存对象"""
        test_obj = {"key": "value"}
        self.manager.cache_object("test_key", test_obj)

        cached_obj = self.manager.get_cached_object("test_key")
        assert cached_obj == test_obj

    def test_get_memory_usage(self):
        """测试获取内存使用情况"""
        usage = self.manager.get_memory_usage()

        # 检查是否包含预期的键
        if usage:  # 如果psutil可用
            assert "rss" in usage or "percent" in usage


class TestDecorators:
    """测试装饰器"""

    @pytest.mark.asyncio
    async def test_cache_decorator(self):
        """测试缓存装饰器"""
        call_count = 0

        @cache(ttl=60)
        async def cached_function(value):
            nonlocal call_count
            call_count += 1
            return value * 2

        # 第一次调用
        result1 = await cached_function(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次调用，应该从缓存获取
        result2 = await cached_function(5)
        assert result2 == 10
        assert call_count == 1  # 没有再次调用


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
